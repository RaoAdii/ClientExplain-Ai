from contextlib import contextmanager
from datetime import timedelta
from uuid import UUID

from app.core.config import settings
from app.models.entities import Document, GenerationJob
from app.schemas.jobs import JobType
from app.services.jobs import transition_job
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import String, and_, cast, create_engine, event, func, select
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.orm import sessionmaker
from worker.celery_app import JobTask, app

# Bound socket establishment, pool checkout and PostgreSQL statements independently
# of the Celery soft and hard limits, including in the standalone watchdog.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_timeout=5,
    connect_args={
        "connect_timeout": 5,
        "options": "-c lock_timeout=3000 -c statement_timeout=10000",
    },
)
JobSession = sessionmaker(engine)


@event.listens_for(engine, "handle_error")
def _discard_interrupted_connection(context):
    if isinstance(context.original_exception, SoftTimeLimitExceeded):
        # SQLAlchemy may roll back a failed flush before control returns to us.
        # Closing the interrupted socket prevents that cleanup from doing I/O.
        context.is_disconnect = True
        context.invalidate_pool_on_disconnect = False


@contextmanager
def _transaction():
    db = JobSession()
    try:
        yield db
        db.commit()
    except SoftTimeLimitExceeded:
        # Cover interruptions outside the driver's execute/commit error handler.
        db.invalidate()
        raise
    finally:
        db.close()


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
    if isinstance(exc, TimeoutError):
        return "timeout", True
    if isinstance(exc, DBAPIError) and getattr(exc.orig, "sqlstate", None) in {"55P03", "57014"}:
        return "timeout", True
    if isinstance(exc, (ConnectionError, PoolTimeout)) or (
        isinstance(exc, DBAPIError) and _connection_failure(exc)
    ):
        return "database_unavailable", True
    return "job_failed", False


def _active_jobs(kind: JobType, document_id: UUID | None = None):
    query = select(GenerationJob).where(
        GenerationJob.kind == kind, GenerationJob.status.in_(("queued", "running"))
    )
    if kind == "parse":
        query = query.join(
            Document,
            and_(
                Document.project_id == GenerationJob.project_id,
                Document.firm_id == GenerationJob.firm_id,
                Document.deleted_at.is_(None),
                GenerationJob.request_metadata["document_id"].as_string()
                == cast(Document.id, String),
            ),
        )
        if document_id is not None:
            query = query.where(Document.id == document_id)
    return query


def _stale():
    # Also expire a queued delivery lost before its first durable claim.
    return (
        (GenerationJob.status == "queued")
        & (
            GenerationJob.created_at
            <= func.now() - timedelta(seconds=app.conf.task_soft_time_limit)
        )
    ) | (
        (GenerationJob.status == "running")
        & (
            func.coalesce(GenerationJob.started_at, GenerationJob.created_at)
            <= func.now() - timedelta(seconds=app.conf.task_time_limit)
        )
    )


def _claim(task: JobTask, job_id: UUID, kind: JobType, document_id: UUID | None, retries: int):
    with _transaction() as db:
        query = _active_jobs(kind, document_id).where(GenerationJob.id == job_id, ~_stale())
        job = db.scalar(query.with_for_update())
        if job is None:
            return False
        if job.status == "running":
            if (
                job.request_metadata.get("worker_task_id") != task.request.id
                or retries <= job.retry_count
            ):
                return False
        else:
            job.request_metadata = {**job.request_metadata, "worker_task_id": task.request.id}
            transition_job(db, job.id, "queued", "running", stage="starting", progress=job.progress)
        job.retry_count = max(job.retry_count, retries)
    return True


def record_failure(
    job_id: UUID, kind: JobType, document_id: UUID | None, error_code: str, retries: int
) -> None:
    with _transaction() as db:
        query = _active_jobs(kind, document_id).where(GenerationJob.id == job_id)
        job = db.scalar(query.with_for_update())
        if job is not None:
            job.retry_count = max(job.retry_count, retries)
            transition_job(
                db,
                job.id,
                job.status,
                "failed",
                stage="failed",
                progress=job.progress,
                error=error_code,
            )


@app.task(name="worker.reconcile_stale_jobs")
def reconcile_stale_jobs() -> None:
    for kind in ("analysis", "parse"):
        with _transaction() as db:
            query = (
                _active_jobs(kind)
                .where(_stale())
                .order_by(GenerationJob.updated_at, GenerationJob.id)
                .limit(100)
                .with_for_update(skip_locked=True)
            )
            for job in db.scalars(query):
                transition_job(
                    db,
                    job.id,
                    job.status,
                    "failed",
                    stage="failed",
                    progress=job.progress,
                    error="timeout",
                )


def run_job(task: JobTask, job_id: UUID, kind: JobType, document_id: UUID | None = None) -> None:
    headers = task.request.headers or {}
    terminal_code = headers.get("job_terminal_code")
    retries = min(task.request.retries, task.processing_retry_limit)
    if terminal_code is None:
        try:
            if not _claim(task, job_id, kind, document_id, retries):
                return
            # Tasks 6 and 8 will supply the actual pipelines here.
            record_failure(job_id, kind, document_id, "pipeline_unavailable", retries)
            return
        except SoftTimeLimitExceeded:
            # The independent watchdog already has the job row. No I/O before hard kill.
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
    except SoftTimeLimitExceeded:
        return
    except (SQLAlchemyError, ConnectionError, TimeoutError):
        pass
    # Retry only the terminal write. These headers preserve its safe cause and count.
    task.retry_delivery({"job_terminal_code": terminal_code, "job_processing_retries": retries})
