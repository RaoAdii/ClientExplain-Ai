from uuid import UUID

from app.models.entities import GenerationJob
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session


def insert_job(
    db: Session,
    firm_id: UUID,
    project_id: UUID,
    kind: str,
    request_hash: str,
    idempotency_key: str | None,
    document_id: UUID | None,
) -> GenerationJob | None:
    # Either the submission key or the partial active-analysis index can win a race.
    return db.scalar(
        insert(GenerationJob)
        .values(
            firm_id=firm_id,
            project_id=project_id,
            kind=kind,
            request_hash=request_hash,
            idempotency_key=idempotency_key,
            request_metadata={"document_id": str(document_id)} if document_id else {},
        )
        .on_conflict_do_nothing()
        .returning(GenerationJob)
    )


def find_submission(
    db: Session, firm_id: UUID, project_id: UUID, kind: str, key: str
) -> GenerationJob | None:
    return db.scalar(
        select(GenerationJob)
        .where(
            GenerationJob.firm_id == firm_id,
            GenerationJob.project_id == project_id,
            GenerationJob.kind == kind,
            GenerationJob.idempotency_key == key,
        )
        .execution_options(populate_existing=True)
    )


def find_job(db: Session, firm_id: UUID, job_id: UUID) -> GenerationJob | None:
    return db.scalar(
        select(GenerationJob)
        .where(GenerationJob.id == job_id, GenerationJob.firm_id == firm_id)
        .execution_options(populate_existing=True)
    )
