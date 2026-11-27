"""Analysis admission and tenant-scoped publication reads."""

import hashlib
import json

from app.core.config import settings
from app.core.permissions import PROJECT_EDITORS, check_roles
from app.db.session import SessionLocal
from app.integrations.openai_provider import ProviderUnavailable, provider_is_configured
from app.models.entities import (
    Document,
    DocumentChunk,
    GenerationJob,
    LegalSource,
    ProcessStage,
    ProjectVersion,
    SourceChunk,
    StageCitation,
)
from app.repositories.jobs import find_submission
from app.schemas.jobs import JobRead
from app.schemas.workflow import ProcessRead
from app.services.activity import audit
from app.services.documents import tenant_context
from app.services.jobs import create_job, transition_job
from app.services.projects import require_project
from app.services.prompting import SYSTEM_INSTRUCTIONS
from celery import Celery
from fastapi import HTTPException
from sqlalchemy import select


def submit_analysis(principal, project_id, request, idempotency_key, response):
    from app.core.rate_limits import rate_limit

    with SessionLocal.begin() as db:
        tenant_context(db, principal)
        project = require_project(db, principal, project_id, for_update=True)
        check_roles(principal, *PROJECT_EDITORS)
        rate_limit(principal, "analysis", response)
        documents = db.scalars(
            select(Document)
            .where(
                Document.firm_id == principal.firm_id,
                Document.project_id == project_id,
                Document.id.in_(request.selected_document_ids),
                Document.deleted_at.is_(None),
            )
            .order_by(Document.id)
            .with_for_update(read=True)
        ).all()
        if len(documents) != len(request.selected_document_ids):
            raise HTTPException(404, "Selected document not found.")
        for document in documents:
            if document.status != "completed" or document.ocr_required:
                raise HTTPException(
                    409, "Selected documents must have completed parsing without OCR."
                )
        # Configuration is checked without constructing clients or transmitting content.
        if not provider_is_configured(settings):
            raise ProviderUnavailable()
        identity = {
            "request": request.model_dump(mode="json"),
            "documents": [(str(doc.id), doc.sha256) for doc in documents],
            "provider": settings.ai_provider,
            "model": settings.ollama_analysis_model
            if settings.ai_provider == "ollama"
            else settings.groq_model
            if settings.ai_provider == "groq"
            else settings.openai_analysis_model,
            "embedding_model": settings.ollama_embedding_model
            if settings.ai_provider == "ollama"
            else None
            if settings.ai_provider == "groq"
            else settings.embedding_model,
            "embedding_dimensions": settings.embedding_dimensions,
            "prompt": SYSTEM_INSTRUCTIONS,
            "schema_version": "step2-v2",
        }
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        existing = (
            find_submission(db, principal.firm_id, project_id, "analysis", idempotency_key)
            if idempotency_key
            else None
        )
        job = create_job(db, principal, project_id, "analysis", digest, idempotency_key)
        if existing is not None:
            return JobRead.model_validate(job)
        job.request_metadata = {"analysis_request": request.model_dump(mode="json")}
        project.processing_status = "queued"
        audit(db, principal, "analysis.requested", project_id)
        db.flush()
        result = JobRead.model_validate(job)
    try:
        Celery("clientexplain-api", broker=settings.redis_url).send_task(
            "worker.analyze_project",
            args=[str(job.id)],
            queue="generation",
            serializer="json",
            retry=False,
        )
    except Exception:
        # A broker may accept before a transport failure: only an unclaimed job
        # can be failed here. A worker-owned job retains its durable state.
        with SessionLocal.begin() as db:
            tenant_context(db, principal)
            project = require_project(db, principal, project_id, for_update=True)
            current = db.scalar(
                select(GenerationJob)
                .where(
                    GenerationJob.id == job.id,
                    GenerationJob.firm_id == principal.firm_id,
                )
                .with_for_update()
            )
            if current is not None and current.status == "queued" and current.started_at is None:
                transition_job(
                    db,
                    current.id,
                    "queued",
                    "failed",
                    stage="failed",
                    progress=current.progress,
                    error="pipeline_unavailable",
                )
                project.processing_status = "failed"
        raise HTTPException(
            503, "The analysis queue is unavailable. Check job status before retrying."
        ) from None
    return result


def list_stages(db, principal, project_id):
    # Publication and deletion take this same ancestry lock. Hold it through
    # both queries so stage rows and process metadata describe one version.
    require_project(db, principal, project_id, for_update=True)
    stages = db.scalars(
        select(ProcessStage)
        .where(
            ProcessStage.firm_id == principal.firm_id,
            ProcessStage.project_id == project_id,
        )
        .order_by(ProcessStage.position, ProcessStage.id)
    ).all()
    version = db.scalar(
        select(ProjectVersion)
        .where(
            ProjectVersion.firm_id == principal.firm_id,
            ProjectVersion.project_id == project_id,
        )
        .order_by(ProjectVersion.version.desc())
        .limit(1)
    )
    metadata = {
        key: value
        for key, value in (version.snapshot if version else {}).items()
        if key in ProcessRead.model_fields and key != "stages"
    }
    return ProcessRead(**metadata, stages=stages)


def get_stage(db, principal, stage_id):
    stage = db.scalar(
        select(ProcessStage).where(
            ProcessStage.id == stage_id, ProcessStage.firm_id == principal.firm_id
        )
    )
    if stage is None:
        raise HTTPException(404, "Stage not found.")
    return stage


def list_citations(db, principal, project_id):
    require_project(db, principal, project_id)
    rows = db.execute(
        select(StageCitation, DocumentChunk, Document, SourceChunk, LegalSource)
        .join(ProcessStage, ProcessStage.id == StageCitation.stage_id)
        .outerjoin(DocumentChunk, DocumentChunk.id == StageCitation.document_chunk_id)
        .outerjoin(Document, Document.id == DocumentChunk.document_id)
        .outerjoin(SourceChunk, SourceChunk.id == StageCitation.source_chunk_id)
        .outerjoin(LegalSource, LegalSource.id == SourceChunk.source_id)
        .where(StageCitation.firm_id == principal.firm_id, StageCitation.project_id == project_id)
        .order_by(ProcessStage.position, StageCitation.created_at, StageCitation.id)
    ).all()
    results = []
    for citation, document_chunk, document, source_chunk, source in rows:
        chunk = document_chunk if document_chunk is not None else source_chunk
        if document is not None and document.deleted_at is not None:
            continue
        results.append(
            {
                **{
                    name: getattr(citation, name)
                    for name in (
                        "id",
                        "stage_id",
                        "project_id",
                        "document_chunk_id",
                        "source_chunk_id",
                        "claim_text",
                        "excerpt",
                        "validation_status",
                    )
                },
                "source_type": "user_document" if document is not None else source.source_type,
                "verification_status": "unverified"
                if document is not None
                else source.verification_status,
                "source_filename": document.filename if document is not None else None,
                "source_title": source.title if source is not None else None,
                "source_url": source.url if source is not None else None,
                "citation_reference": source.citation_reference if source is not None else None,
                "page_number": chunk.page_number,
                "heading": chunk.heading,
            }
        )
    return results
