"""Atomic stage/citation/version publication, within the caller's locked transaction."""

from uuid import UUID

from app.models.entities import (
    DocumentChunk,
    LegalSource,
    ProcessStage,
    ProjectVersion,
    SourceChunk,
    StageCitation,
)
from app.services.citations import ASSOCIATION_LIMITATION, validate_citations
from app.services.jobs import transition_job
from sqlalchemy import delete, func, select


def lock_evidence(db, firm_id, evidence):
    """Stabilize retrieved provenance and passages through publication."""
    source_ids = [chunk.source_id for chunk in evidence if chunk.source_id is not None]
    sources = list(
        db.scalars(
            select(LegalSource)
            .where(LegalSource.firm_id == firm_id, LegalSource.id.in_(source_ids))
            .order_by(LegalSource.id)
            .with_for_update(read=True)
        )
    )
    source_chunks = [UUID(chunk.chunk_id) for chunk in evidence if chunk.source_id is not None]
    document_chunks = [UUID(chunk.chunk_id) for chunk in evidence if chunk.source_id is None]
    for model, ids in ((SourceChunk, source_chunks), (DocumentChunk, document_chunks)):
        list(
            db.scalars(
                select(model)
                .where(model.firm_id == firm_id, model.id.in_(ids))
                .order_by(model.id)
                .with_for_update(read=True)
            )
        )
    return sources


def publish_analysis(db, job, project, process, evidence):
    existing = db.scalar(
        select(ProjectVersion.id).where(ProjectVersion.generation_job_id == job.id)
    )
    if existing is not None:
        return
    evidence_by_id = {chunk.chunk_id: chunk for chunk in evidence}
    validation = validate_citations(process, evidence_by_id)
    if not validation.valid:
        raise ValueError("Citations could not be validated. No result was published.")
    db.execute(
        delete(ProcessStage).where(
            ProcessStage.project_id == project.id, ProcessStage.firm_id == job.firm_id
        )
    )
    snapshot = process.model_dump(mode="json")
    snapshot["limitations"] = list(
        dict.fromkeys([*snapshot["limitations"], ASSOCIATION_LIMITATION])
    )
    for output, validated, stage_snapshot in zip(
        process.stages, validation.stages, snapshot["stages"], strict=True
    ):
        stage = ProcessStage(
            project_id=project.id,
            firm_id=job.firm_id,
            position=output.stage_number - 1,
            **output.model_dump(exclude={"stage_number", "evidence_chunk_ids", "claims"}),
            verification_status=validated.verification_status,
        )
        db.add(stage)
        db.flush()
        for citation in validated.citations:
            chunk = evidence_by_id[citation.evidence_chunk_id]
            db.add(
                StageCitation(
                    stage_id=stage.id,
                    project_id=project.id,
                    firm_id=job.firm_id,
                    document_chunk_id=UUID(chunk.chunk_id) if chunk.source_id is None else None,
                    source_chunk_id=UUID(chunk.chunk_id) if chunk.source_id is not None else None,
                    claim_text=citation.claim_text,
                    excerpt=citation.excerpt,
                    validation_status=citation.validation_status,
                )
            )
        stage_snapshot["verification_status"] = validated.verification_status
        stage_snapshot["citations"] = [
            citation.model_dump(mode="json") for citation in validated.citations
        ]
    version = (
        db.scalar(
            select(func.coalesce(func.max(ProjectVersion.version), 0)).where(
                ProjectVersion.project_id == project.id, ProjectVersion.firm_id == job.firm_id
            )
        )
        + 1
    )
    db.add(
        ProjectVersion(
            project_id=project.id,
            firm_id=job.firm_id,
            version=version,
            snapshot=snapshot,
            generation_job_id=job.id,
        )
    )
    project.review_status = "requires_review"
    project.processing_status = "completed"
    transition_job(db, job.id, "running", "completed", stage="completed", progress=100)
    db.flush()
