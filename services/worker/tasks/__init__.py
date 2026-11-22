from uuid import UUID

from app.db.session import SessionLocal
from app.models.entities import Document, GenerationJob
from app.schemas.jobs import JobType
from app.services.jobs import transition_job
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import and_, select
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from worker.celery_app import JobTask


def _connection_failure(exc: DBAPIError) -> bool:
    sqlstate = getattr(exc.orig, "sqlstate", None)
    if sqlstate:
        return (
            exc.connection_invalidated
            or sqlstate.startswith("08")
            or sqlstate in {"53300", "57P01", "57P02", "57P03"}
        )
    # psycopg can lose or fail to establish a socket before receiving any SQLSTATE.
    return exc.connection_invalidated or (
        isinstance(exc, OperationalError) and exc.statement is None
    )


def _failure_policy(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, SoftTimeLimitExceeded):
        return "timeout", False
    if isinstance(exc, TimeoutError):
        return "timeout", True
    if isinstance(exc, (ConnectionError, PoolTimeout)) or (
        isinstance(exc, DBAPIError) and _connection_failure(exc)
    ):
        return "database_unavailable", True
    return "job_failed", False


def record_failure(
    job_id: UUID, kind: JobType, document_id: UUID | None, error_code: str, retries: int
) -> None:
    statuses = ("queued",) if error_code == "pipeline_unavailable" else ("queued", "running")
    query = select(GenerationJob).where(
        GenerationJob.id == job_id, GenerationJob.kind == kind, GenerationJob.status.in_(statuses)
    )
    if kind == "parse":
        query = query.join(
            Document,
            and_(
                Document.id == document_id,
                Document.project_id == GenerationJob.project_id,
                Document.firm_id == GenerationJob.firm_id,
                Document.deleted_at.is_(None),
                GenerationJob.request_metadata["document_id"].as_string() == str(document_id),
            ),
        )
    with SessionLocal.begin() as db:
        job = db.scalar(query.with_for_update())
        if job is not None:
            job.retry_count += retries
            transition_job(
                db,
                job.id,
                job.status,
                "failed",
                stage="failed",
                progress=job.progress,
                error=error_code,
            )


def run_job(task: JobTask, job_id: UUID, kind: JobType, document_id: UUID | None = None) -> None:
    headers = task.request.headers or {}
    terminal_code = headers.get("job_terminal_code")
    retries = min(task.request.retries, task.processing_retry_limit)
    if terminal_code is None:
        try:
            # Tasks 6 and 8 will supply the actual pipelines here.
            record_failure(job_id, kind, document_id, "pipeline_unavailable", retries)
            return
        except Exception as exc:
            terminal_code, retryable = _failure_policy(exc)
        if retryable and retries < task.processing_retry_limit:
            task.retry_delivery()
    else:
        retries = headers["job_processing_retries"]

    try:
        record_failure(job_id, kind, document_id, terminal_code, retries)
        return
    except (SQLAlchemyError, SoftTimeLimitExceeded, ConnectionError, TimeoutError):
        pass
    # Retry only the terminal write. These headers preserve its safe cause and count.
    task.retry_delivery({"job_terminal_code": terminal_code, "job_processing_retries": retries})
