from contextlib import contextmanager
from datetime import timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from app.core.config import settings
from app.models.entities import Document, GenerationJob, JobRecovery
from app.schemas.jobs import JobType
from app.services.jobs import SAFE_ERRORS, transition_job
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import (
    String,
    and_,
    cast,
    create_engine,
    delete,
    event,
    func,
    select,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import insert
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
JobSession = sessionmaker(engine, autoflush=False)


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


def _matching_jobs(kind: JobType, document_id: UUID | None = None):
    query = select(GenerationJob).where(GenerationJob.kind == kind)
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


def _active_jobs(kind: JobType, document_id: UUID | None = None):
    return _matching_jobs(kind, document_id).where(GenerationJob.status.in_(("queued", "running")))


def _intent_scope(job):
    return (
        JobRecovery.job_id == job.id,
        JobRecovery.firm_id == job.firm_id,
        JobRecovery.project_id == job.project_id,
    )


def _pending_intent(db, job):
    intents = db.scalars(
        select(JobRecovery)
        .where(*_intent_scope(job))
        .order_by(JobRecovery.created_at, JobRecovery.id)
    ).all()
    if intents:
        return (
            intents[0].error_code,
            max(intent.retry_count for intent in intents),
            [(intent.id, intent.retry_count) for intent in intents],
        )
    return None


def _load_intent(job_id, kind, document_id):
    with _transaction() as db:
        job = db.scalar(_matching_jobs(kind, document_id).where(GenerationJob.id == job_id))
        intent = _pending_intent(db, job) if job is not None else None
        return intent[:2] if intent is not None else None


def _attempt_uuid(task_id: str) -> UUID:
    try:
        return UUID(task_id)
    except ValueError:
        # Celery accepts arbitrary transport IDs. Keep their stable identity
        # without persisting custom text in the recovery table.
        return uuid5(NAMESPACE_URL, f"clientexplain:celery-task:{task_id}")


def _remember_intent(job_id, kind, document_id, error_code, retries, attempt_id):
    with _transaction() as db:
        # A plain MVCC read validates tenant/document ancestry without waiting for
        # the job lock. No job/project FK is taken when inserting the intent.
        job = db.scalar(_matching_jobs(kind, document_id).where(GenerationJob.id == job_id))
        if job is None or job.status in {"completed", "cancelled"}:
            return
        statement = insert(JobRecovery).values(
            job_id=job.id,
            firm_id=job.firm_id,
            project_id=job.project_id,
            attempt_id=_attempt_uuid(attempt_id),
            error_code=error_code,
            retry_count=retries,
        )
        db.execute(
            statement.on_conflict_do_update(
                constraint="uq_job_recoveries_attempt",
                set_={
                    "retry_count": func.greatest(
                        JobRecovery.retry_count, statement.excluded.retry_count
                    )
                },
            )
        )


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
            transition_job(db, job.id, "queued", "running", stage="starting", progress=job.progress)
        # Keep the session clean: ORM autoflush can roll back an interrupted
        # mutation before the outer deadline handler can discard the socket.
        db.execute(
            update(GenerationJob)
            .where(GenerationJob.id == job.id)
            .values(
                request_metadata={**job.request_metadata, "worker_task_id": task.request.id},
                retry_count=func.greatest(GenerationJob.retry_count, retries),
            )
            .execution_options(synchronize_session=False)
        )
    return True


def _persist_failure(db, job, error_code, retries, *, watchdog=False):
    intent = _pending_intent(db, job)
    if intent is not None:
        error_code, intent_retries, consumed_versions = intent
        retries = max(retries, intent_retries)
    else:
        consumed_versions = []
    metadata = dict(job.request_metadata)
    default_timeout = watchdog and intent is None
    values = {"retry_count": func.greatest(GenerationJob.retry_count, retries)}
    if job.status in {"queued", "running"}:
        transition_job(
            db,
            job.id,
            job.status,
            "failed",
            stage="failed",
            progress=job.progress,
            error=error_code,
        )
        metadata["watchdog_timeout"] = default_timeout
    elif job.status == "failed":
        # A watchdog expiry is provisional until an already-pending terminal
        # delivery/intent supplies the original cause. Explicit outcomes win.
        legacy_timeout = (
            job.error_code == "timeout"
            and "watchdog_timeout" not in metadata
            and intent is not None
        )
        if (
            (
                metadata.get("watchdog_timeout")
                or legacy_timeout
                or job.error_code == "pipeline_unavailable"
            )
            and not default_timeout
            and error_code != "pipeline_unavailable"
        ):
            values.update(error_code=error_code, error_message=SAFE_ERRORS[error_code])
            metadata["watchdog_timeout"] = False
    else:
        db.execute(
            delete(JobRecovery).where(
                tuple_(JobRecovery.id, JobRecovery.retry_count).in_(consumed_versions)
            )
        )
        return
    values["request_metadata"] = metadata
    db.execute(
        update(GenerationJob)
        .where(GenerationJob.id == job.id)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    # Only consume the versions we used. A new intent or a higher retry count
    # committed after our read must survive for the next reconciliation pass.
    db.execute(
        delete(JobRecovery).where(
            tuple_(JobRecovery.id, JobRecovery.retry_count).in_(consumed_versions)
        )
    )


def record_failure(
    job_id: UUID, kind: JobType, document_id: UUID | None, error_code: str, retries: int
) -> None:
    with _transaction() as db:
        query = _matching_jobs(kind, document_id).where(GenerationJob.id == job_id)
        job = db.scalar(query.with_for_update())
        if job is not None:
            _persist_failure(db, job, error_code, retries)


@app.task(name="worker.reconcile_stale_jobs")
def reconcile_stale_jobs() -> None:
    with _transaction() as db:
        live_job = None
        for kind in ("analysis", "parse"):
            matching = (
                _matching_jobs(kind)
                .with_only_columns(GenerationJob.id)
                .where(
                    GenerationJob.id == JobRecovery.job_id,
                    GenerationJob.firm_id == JobRecovery.firm_id,
                    GenerationJob.project_id == JobRecovery.project_id,
                )
                .correlate(JobRecovery)
                .exists()
            )
            live_job = matching if live_job is None else live_job | matching
        db.execute(delete(JobRecovery).where(~live_job))
    for kind in ("analysis", "parse"):
        with _transaction() as db:
            pending = (
                select(JobRecovery.id)
                .where(
                    JobRecovery.job_id == GenerationJob.id,
                    JobRecovery.firm_id == GenerationJob.firm_id,
                    JobRecovery.project_id == GenerationJob.project_id,
                )
                .exists()
            )
            query = (
                _matching_jobs(kind)
                .where(
                    (GenerationJob.status.in_(("queued", "running")) & (_stale() | pending))
                    | (GenerationJob.status.in_(("failed", "completed", "cancelled")) & pending)
                )
                .order_by(GenerationJob.updated_at, GenerationJob.id)
                .limit(100)
                .with_for_update(skip_locked=True)
            )
            for job in db.scalars(query):
                _persist_failure(db, job, "timeout", job.retry_count, watchdog=True)


def run_job(
    task: JobTask, job_id: UUID, kind: JobType, document_id: UUID | None = None, *, pipeline=None
) -> None:
    headers = task.request.headers or {}
    terminal_code = headers.get("job_terminal_code")
    if terminal_code is not None and terminal_code not in {
        "timeout",
        "database_unavailable",
        "job_failed",
    }:
        terminal_code = "job_failed"
    retries = min(task.request.retries, task.processing_retry_limit)
    retryable = False
    if terminal_code is None:
        try:
            intent = _load_intent(job_id, kind, document_id)
            if intent is not None:
                terminal_code, original_retries = intent
                retries = original_retries
            elif not _claim(task, job_id, kind, document_id, retries):
                return
            else:
                if pipeline is not None:
                    pipeline(task, job_id, document_id)
                else:
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
        original_retries = headers.get("job_processing_retries", 0)
        if type(original_retries) is int:
            retries = min(max(original_retries, 0), task.processing_retry_limit)

    try:
        _remember_intent(job_id, kind, document_id, terminal_code, retries, task.request.id)
    except SoftTimeLimitExceeded:
        return
    except (SQLAlchemyError, ConnectionError, TimeoutError):
        pass
    try:
        record_failure(job_id, kind, document_id, terminal_code, retries)
        return
    except SoftTimeLimitExceeded:
        return
    except (SQLAlchemyError, ConnectionError, TimeoutError):
        pass
    # Retry only the terminal write. These headers preserve its safe cause and count.
    task.retry_delivery({"job_terminal_code": terminal_code, "job_processing_retries": retries})
