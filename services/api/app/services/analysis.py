"""Analysis checkpoints and production provider dependencies."""

from dataclasses import dataclass
from uuid import UUID

from app.integrations.openai_provider import EmbeddingProvider, LegalAnalysisProvider
from app.models.entities import Document, DocumentChunk, GenerationJob, Project
from app.schemas.analysis import AnalysisRequest
from sqlalchemy import select


@dataclass(frozen=True)
class AnalysisProviders:
    embedding: EmbeddingProvider | None
    analysis: LegalAnalysisProvider
    worker_task_id: str


def analysis_checkpoint(db, job_id: UUID, worker_task_id: str, *, lock=False):
    """Lock project, selected documents, then job; no lock crosses a provider call."""
    job = db.scalar(
        select(GenerationJob).where(
            GenerationJob.id == job_id,
            GenerationJob.kind == "analysis",
            GenerationJob.status == "running",
        )
    )
    if job is None or job.request_metadata.get("worker_task_id") != worker_task_id:
        return None
    query = select(Project).where(Project.id == job.project_id, Project.firm_id == job.firm_id)
    project = db.scalar(query.with_for_update() if lock else query)
    if project is None:
        return None
    try:
        request = AnalysisRequest.model_validate(job.request_metadata["analysis_request"])
    except (ValueError, KeyError, TypeError):
        raise ValueError("The analysis request is unavailable or invalid.") from None
    query = (
        select(Document)
        .where(
            Document.id.in_(request.selected_document_ids),
            Document.project_id == project.id,
            Document.firm_id == project.firm_id,
            Document.deleted_at.is_(None),
        )
        .order_by(Document.id)
    )
    documents = list(db.scalars(query.with_for_update() if lock else query))
    # Refresh the job after waiting for ancestry locks. A cancellation or newer
    # submission can have committed while the old read still appeared running.
    query = (
        select(GenerationJob)
        .where(
            GenerationJob.id == job_id,
            GenerationJob.project_id == project.id,
            GenerationJob.firm_id == project.firm_id,
            GenerationJob.status == "running",
        )
        .execution_options(populate_existing=True)
    )
    job = db.scalar(query.with_for_update() if lock else query)
    if job is None or job.request_metadata.get("worker_task_id") != worker_task_id:
        return None
    if request.model_dump(mode="json") != job.request_metadata.get("analysis_request"):
        raise ValueError("The analysis request changed during processing.")
    if len(documents) != len(request.selected_document_ids) or any(
        document.status != "completed" or document.ocr_required for document in documents
    ):
        raise ValueError("Selected documents must be available, parsed, and readable without OCR.")
    query = (
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id.in_(request.selected_document_ids),
            DocumentChunk.firm_id == project.firm_id,
        )
        .order_by(DocumentChunk.document_id, DocumentChunk.position)
    )
    chunks = list(db.scalars(query))
    if {chunk.document_id for chunk in chunks} != set(request.selected_document_ids):
        raise ValueError("Every selected document requires parsed passages.")
    return job, project, request, documents, chunks


def work_signature(work):
    _, _, request, documents, chunks = work
    return (
        request.model_dump(mode="json"),
        [(doc.id, doc.sha256, doc.status, doc.ocr_required) for doc in documents],
        [
            (chunk.id, chunk.document_id, chunk.content, chunk.page_number, chunk.heading)
            for chunk in chunks
        ],
    )
