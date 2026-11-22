import codecs
import hashlib
import logging
from datetime import UTC, datetime
from pathlib import PurePosixPath
from tempfile import TemporaryFile
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZipFile

from app.core.auth import Principal
from app.core.config import settings
from app.core.permissions import PROJECT_EDITORS, check_roles
from app.db.session import SessionLocal
from app.integrations.storage import get_storage
from app.models.entities import (
    Document,
    DocumentChunk,
    GenerationJob,
    ProcessStage,
    Project,
    ProjectVersion,
)
from app.repositories.documents import find_duplicate, insert_document
from app.schemas.documents import UploadRead
from app.schemas.workflow import DocumentDetail
from app.services.activity import audit
from app.services.jobs import create_job, transition_job
from app.services.projects import require_project
from celery import Celery
from fastapi import HTTPException, UploadFile
from sqlalchemy import delete, select, text

log = logging.getLogger("clientexplain")

CHUNK_BYTES = 64 * 1024
MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}


def lock_live_document(db, firm_id: UUID, project_id: UUID, document_id: UUID):
    """Hold ancestry locks through a durable parser write, in project/document order."""
    project = db.scalar(
        select(Project.id)
        .where(Project.id == project_id, Project.firm_id == firm_id)
        .with_for_update(read=True)
    )
    if project is None:
        return None
    return db.scalar(
        select(Document)
        .where(
            Document.id == document_id,
            Document.project_id == project_id,
            Document.firm_id == firm_id,
            Document.deleted_at.is_(None),
        )
        .with_for_update()
    )


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


def compensate_dispatch(principal, project_id, document_id, job_id):
    # Each attempt owns a fresh transaction, including after commit/rollback
    # errors. Deletion is idempotent if an earlier commit's result was uncertain.
    for attempt in range(3):
        try:
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
            return
        except Exception:
            if attempt == 2:
                log.error("Dispatch compensation database cleanup failed after three attempts")
                raise


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
            audit(db, principal, "document.uploaded", project_id)
            result = UploadRead(document=document, job=job)
        committed = True
        dispatch_parse(document_id, job_id)
        return result
    except Exception as exc:
        try:
            if committed:
                compensate_dispatch(principal, project_id, document_id, job_id)
        except Exception:
            raise HTTPException(
                503, "The upload could not be completed. Try again shortly."
            ) from None
        finally:
            # Private bytes must be cleaned even when database compensation (or
            # its rollback) raises. Never broaden deletion beyond this key.
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


def list_documents(db, principal, project_id):
    require_project(db, principal, project_id)
    return db.scalars(
        select(Document)
        .where(
            Document.firm_id == principal.firm_id,
            Document.project_id == project_id,
            Document.deleted_at.is_(None),
        )
        .order_by(Document.created_at, Document.id)
    ).all()


def require_document(db, principal, document_id, *, include_deleted=False):
    query = select(Document).where(
        Document.id == document_id, Document.firm_id == principal.firm_id
    )
    if not include_deleted:
        query = query.where(Document.deleted_at.is_(None))
    document = db.scalar(query)
    if document is None:
        raise HTTPException(404, "Document not found.")
    return document


def document_detail(db, principal, document_id, *, download=False):
    document = require_document(db, principal, document_id)
    result = DocumentDetail.model_validate(document)
    if download:
        try:
            result.download_url = get_storage().signed_url(document.storage_key, 300)
            result.download_url_expires_in = 300
        except NotImplementedError:
            # Local storage never exposes filesystem paths or a public file URL.
            pass
        except Exception:
            raise HTTPException(
                503, "Document storage is unavailable. Try again shortly."
            ) from None
    return result


def delete_document(principal, document_id):
    # Hide and invalidate evidence before external cleanup. A tombstone makes a
    # storage outage retriable and stops in-flight workers from publishing it.
    with SessionLocal.begin() as db:
        tenant_context(db, principal)
        document = require_document(db, principal, document_id, include_deleted=True)
        project = require_project(db, principal, document.project_id, for_update=True)
        check_roles(principal, *PROJECT_EDITORS)
        document = db.scalar(
            select(Document)
            .where(
                Document.id == document_id,
                Document.firm_id == principal.firm_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if document is None:
            raise HTTPException(404, "Document not found.")
        key = document.storage_key
        if document.deleted_at is None:
            document.deleted_at, document.deleted_by = datetime.now(UTC), principal.user_id
            document.document_metadata = {"storage_cleanup_pending": True}
            # Snapshots and explanations can contain quotations beyond citation
            # rows. Invalidate the current publication and versions together.
            for model in (ProjectVersion, ProcessStage):
                db.execute(
                    delete(model).where(
                        model.project_id == project.id, model.firm_id == principal.firm_id
                    )
                )
            db.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.firm_id == principal.firm_id,
                )
            )
            active = db.scalars(
                select(GenerationJob)
                .where(
                    GenerationJob.project_id == project.id,
                    GenerationJob.firm_id == principal.firm_id,
                    GenerationJob.status.in_(("queued", "running")),
                )
                .order_by(GenerationJob.id)
                .with_for_update()
            ).all()
            for job in active:
                metadata = job.request_metadata
                if metadata.get("document_id") == str(document_id) or str(
                    document_id
                ) in metadata.get("analysis_request", {}).get("selected_document_ids", []):
                    transition_job(
                        db,
                        job.id,
                        job.status,
                        "cancelled",
                        stage="cancelled",
                        progress=job.progress,
                    )
                    if job.kind == "analysis":
                        project.processing_status = "cancelled"
            project.review_status = "requires_review"
            audit(db, principal, "document.deleted", project.id)
    try:
        get_storage().delete(key)
    except Exception:
        raise HTTPException(
            503, "Document storage cleanup is pending. Retry deletion shortly."
        ) from None
    with SessionLocal.begin() as db:
        tenant_context(db, principal)
        db.execute(
            delete(Document).where(
                Document.id == document_id,
                Document.firm_id == principal.firm_id,
                Document.deleted_at.is_not(None),
            )
        )
