from contextlib import contextmanager
from uuid import UUID

from app.db.session import SessionLocal
from app.models.entities import GenerationJob
from app.schemas.jobs import JobType
from app.services.jobs import transition_job
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError


@contextmanager
def job_transaction():
    try:
        with SessionLocal.begin() as db:
            yield db
    except DBAPIError as exc:
        if exc.connection_invalidated:
            raise ConnectionError("The database connection was interrupted.") from None
        raise


def fail_unavailable_pipeline(job_id: UUID, kind: JobType, retries: int) -> None:
    # Until a pipeline is installed, a delivered job must have an honest durable outcome.
    with job_transaction() as db:
        job = db.scalar(
            select(GenerationJob)
            .where(
                GenerationJob.id == job_id,
                GenerationJob.kind == kind,
                GenerationJob.status == "queued",
            )
            .with_for_update()
        )
        if job is not None:
            job.retry_count += retries
            transition_job(
                db,
                job.id,
                "queued",
                "failed",
                stage="failed",
                progress=job.progress,
                error="pipeline_unavailable",
            )
