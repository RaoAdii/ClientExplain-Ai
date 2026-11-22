import codecs
import hashlib
from pathlib import PurePosixPath
from tempfile import TemporaryFile
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZipFile

from app.core.auth import Principal
from app.core.config import settings
from app.core.permissions import PROJECT_EDITORS, check_roles
from app.db.session import SessionLocal
from app.integrations.storage import get_storage
from app.models.entities import Document, GenerationJob
from app.repositories.documents import find_duplicate, insert_document
from app.schemas.documents import UploadRead
from app.services.jobs import create_job
from app.services.projects import require_project
from celery import Celery
from fastapi import HTTPException, UploadFile
from sqlalchemy import delete, text

CHUNK_BYTES = 64 * 1024
MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}


def tenant_context(db, principal):
    for field, value in [("firm_id", principal.firm_id), ("user_id", principal.user_id)]:
        db.execute(text(f"SELECT set_config('app.{field}', :value, true)"), {"value": str(value)})


def dispatch_parse(document_id: UUID, job_id: UUID) -> None:
    Celery("clientexplain-api", broker=settings.redis_url).send_task(
        "worker.parse_document",
        args=[str(document_id), str(job_id)],
        queue="generation",
        serializer="json",
        retry=False,
    )


def admit(upload: UploadFile, temporary):
    filename = PurePosixPath((upload.filename or "").replace("\\", "/")).name
    suffix = PurePosixPath(filename).suffix.lower()
    media_type = MEDIA_TYPES.get(suffix)
    if not media_type or (upload.content_type or "").split(";", 1)[0].lower() != media_type:
        raise HTTPException(
            415, "Upload a PDF, DOCX, or UTF-8 text file with a matching media type."
        )
    if not filename or len(filename) > 255 or any(ord(c) < 32 for c in filename):
        raise HTTPException(422, "Provide a valid filename.")
    size, prefix = 0, b""
    digest = hashlib.sha256()
    decoder = codecs.getincrementaldecoder("utf-8-sig")() if suffix == ".txt" else None
    try:
        while chunk := upload.file.read(CHUNK_BYTES):
            size += len(chunk)
            if size > settings.max_upload_bytes:
                raise HTTPException(413, "The document exceeds the upload limit.")
            if not prefix:
                prefix = chunk[:8]
            if decoder:
                text_chunk = decoder.decode(chunk)
                if any(ord(c) < 32 and c not in "\n\r\t\f" for c in text_chunk):
                    raise UnicodeError()
            digest.update(chunk)
            temporary.write(chunk)
        if decoder:
            decoder.decode(b"", final=True)
    except UnicodeError as exc:
        raise HTTPException(415, "The file is not UTF-8 text.") from exc
    if size == 0:
        raise HTTPException(422, "The document is empty.")
    if suffix == ".pdf" and not prefix.startswith(b"%PDF-"):
        raise HTTPException(415, "The file is not a PDF.")
    if suffix == ".txt" and prefix.startswith((b"%PDF-", b"PK\x03\x04")):
        raise HTTPException(415, "The file signature does not match its extension.")
    if suffix == ".docx":
        try:
            temporary.seek(0)
            with ZipFile(temporary) as archive:
                names = set(archive.namelist())
                if not prefix.startswith(b"PK\x03\x04") or not {
                    "[Content_Types].xml",
                    "word/document.xml",
                }.issubset(names):
                    raise BadZipFile()
        except (BadZipFile, OSError, ValueError) as exc:
            raise HTTPException(415, "The file is not a DOCX document.") from exc
    temporary.seek(0)
    return filename, suffix, media_type, size, digest.hexdigest()


def duplicate_error(document):
    raise HTTPException(409, {"document_id": str(document.id), "status": document.status})


def upload_document(principal: Principal, project_id: UUID, upload: UploadFile) -> UploadRead:
    check_roles(principal, *PROJECT_EDITORS)
    key = None
    storage = None
    document_id, job_id = uuid4(), None
    committed = False
    try:
        with TemporaryFile("w+b") as temporary, SessionLocal.begin() as db:
            tenant_context(db, principal)
            require_project(db, principal, project_id, for_update=True)
            filename, suffix, media_type, size, digest = admit(upload, temporary)
            if existing := find_duplicate(db, principal.firm_id, project_id, digest):
                duplicate_error(existing)
            storage = get_storage()
            key = f"{principal.firm_id}/{project_id}/{document_id}{suffix}"
            storage.put(key, temporary)
            document = insert_document(
                db,
                id=document_id,
                firm_id=principal.firm_id,
                project_id=project_id,
                filename=filename,
                storage_key=key,
                media_type=media_type,
                byte_size=size,
                sha256=digest,
            )
            if document is None:
                duplicate_error(find_duplicate(db, principal.firm_id, project_id, digest))
            job = create_job(
                db, principal, project_id, "parse", digest, None, document_id=document_id
            )
            job_id = job.id
            result = UploadRead(document=document, job=job)
        committed = True
        dispatch_parse(document_id, job_id)
        return result
    except Exception as exc:
        if committed:
            with SessionLocal.begin() as cleanup:
                tenant_context(cleanup, principal)
                cleanup.execute(
                    delete(GenerationJob).where(
                        GenerationJob.id == job_id,
                        GenerationJob.firm_id == principal.firm_id,
                        GenerationJob.project_id == project_id,
                    )
                )
                cleanup.execute(
                    delete(Document).where(
                        Document.id == document_id,
                        Document.firm_id == principal.firm_id,
                        Document.project_id == project_id,
                    )
                )
        if storage is not None and key is not None:
            try:
                storage.delete(key)
            except Exception:
                raise HTTPException(
                    503, "Document storage is unavailable. Try again shortly."
                ) from None
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(503, "The upload could not be completed. Try again shortly.") from None
