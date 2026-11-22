import hashlib

from app.core.config import settings
from app.integrations.storage import get_storage
from app.models.entities import Document, DocumentChunk, GenerationJob
from app.services.documents import lock_live_document
from app.services.jobs import transition_job
from sqlalchemy import delete, select, update
from worker.celery_app import JobTask, app, task_id
from worker.pipelines.chunking import chunk_document
from worker.pipelines.documents import (
    MAX_INPUT_BYTES,
    OCR_MESSAGE,
    PARSER_VERSION,
    DocumentParseError,
    parse_document_bytes,
)
from worker.tasks import _transaction, run_job


def _locked_work(db, task, job_id, document_id):
    job = db.scalar(
        select(GenerationJob).where(
            GenerationJob.id == job_id,
            GenerationJob.kind == "parse",
            GenerationJob.status == "running",
        )
    )
    if job is None or job.request_metadata.get("document_id") != str(document_id):
        return None
    document = lock_live_document(db, job.firm_id, job.project_id, document_id)
    if document is None:
        return None
    # Refresh after waiting for ancestry locks: cancellation or watchdog expiry
    # must win over a previously loaded running state.
    job = db.scalar(
        select(GenerationJob)
        .where(
            GenerationJob.id == job_id,
            GenerationJob.status == "running",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if job is None or job.request_metadata.get("worker_task_id") != task.request.id:
        return None
    return document, job


def _complete(db, job):
    transition_job(db, job.id, "running", "completed", stage="completed", progress=100)


def _already_parsed(document):
    return (
        document.status == "completed"
        and not document.ocr_required
        and document.document_metadata.get("parsed_sha256") == document.sha256
        and document.document_metadata.get("parser_version") == PARSER_VERSION
    )


def _parse_pipeline(task, job_id, document_id):
    with _transaction() as db:
        work = _locked_work(db, task, job_id, document_id)
        if work is None:
            return
        document, job = work
        if _already_parsed(document):
            _complete(db, job)
            return
        snapshot = {
            "sha256": document.sha256,
            "storage_key": document.storage_key,
            "media_type": document.media_type,
            "filename": document.filename,
            "byte_size": document.byte_size,
        }
        db.execute(
            update(Document)
            .where(Document.id == document.id)
            .values(
                status="parsing",
                parsing_error=None,
                ocr_required=False,
            )
        )
        if job.progress < 10:
            transition_job(db, job.id, "running", "running", stage="extracting", progress=10)

    extracted, chunks, error = None, [], None
    try:
        try:
            with get_storage().open(snapshot["storage_key"]) as stream:
                content = stream.read(min(settings.max_upload_bytes, MAX_INPUT_BYTES) + 1)
        except FileNotFoundError:
            raise DocumentParseError(
                "The stored document is unavailable. Upload the document again."
            ) from None
        if (
            len(content) != snapshot["byte_size"]
            or hashlib.sha256(content).hexdigest() != snapshot["sha256"]
        ):
            raise DocumentParseError(
                "The stored document could not be verified. Upload the document again."
            )
        extracted = parse_document_bytes(snapshot["media_type"], content)
        extracted.metadata["filename"] = snapshot["filename"]
        chunks = chunk_document(extracted)
        if extracted.ocr_required:
            error = OCR_MESSAGE
    except DocumentParseError as exc:
        error = str(exc)

    with _transaction() as db:
        work = _locked_work(db, task, job_id, document_id)
        if work is None:
            return
        document, job = work
        if any(getattr(document, key) != value for key, value in snapshot.items()):
            raise DocumentParseError("The document changed during processing. Submit it again.")
        if _already_parsed(document):
            _complete(db, job)
            return
        if error is not None:
            ocr_required = bool(extracted and extracted.ocr_required)
            db.execute(
                update(Document)
                .where(Document.id == document.id)
                .values(
                    status="ocr_required" if ocr_required else "failed",
                    ocr_required=ocr_required,
                    parsing_error=error,
                    page_count=len(extracted.pages) if extracted and extracted.pages else None,
                )
            )
            transition_job(
                db,
                job.id,
                "running",
                "failed",
                stage="ocr_required" if ocr_required else "failed",
                progress=job.progress,
                error="job_failed",
            )
            return
        if job.progress < 80:
            transition_job(db, job.id, "running", "running", stage="writing_chunks", progress=80)
        db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document.id,
                DocumentChunk.firm_id == document.firm_id,
            )
        )
        db.add_all(
            DocumentChunk(
                firm_id=document.firm_id,
                document_id=document.id,
                position=chunk.position,
                content=chunk.content,
                page_number=chunk.page_number,
                heading=chunk.heading,
                source_filename=chunk.source_filename,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                chunk_metadata={"parser_version": PARSER_VERSION, "sha256": document.sha256},
            )
            for chunk in chunks
        )
        db.flush()
        db.execute(
            update(Document)
            .where(Document.id == document.id)
            .values(
                status="completed",
                parsing_error=None,
                ocr_required=False,
                page_count=len(extracted.pages) if extracted.pages else None,
                document_metadata={
                    **document.document_metadata,
                    **extracted.metadata,
                    "parsed_sha256": document.sha256,
                },
            )
        )
        _complete(db, job)


@app.task(bind=True, base=JobTask, name="worker.parse_document")
def parse_document(self: JobTask, document_id: str, job_id: str) -> None:
    run_job(self, task_id(job_id), "parse", task_id(document_id), pipeline=_parse_pipeline)
