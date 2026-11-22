import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from app.core.auth import DEV_FIRM, DEV_USER, Principal
from app.db.session import SessionLocal
from app.models.entities import Document, GenerationJob, JobRecovery, Project
from app.schemas.auth import Role
from app.schemas.jobs import JobRead
from app.services.jobs import create_job, get_job, transition_job
from celery.exceptions import Reject, SoftTimeLimitExceeded
from fastapi import HTTPException
from sqlalchemy import delete, event, func, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.orm import with_loader_criteria
from worker.celery_app import app as celery
from worker.tasks import JobSession, engine

OWNER = Principal(DEV_USER, DEV_FIRM, Role.OWNER)
DIGEST = "a" * 64
PRIVATE_MARKER = "internal-database-marker"


@pytest.fixture
def project_id():
    with SessionLocal.begin() as db:
        project = Project(firm_id=DEV_FIRM, created_by=DEV_USER, name="Job lifecycle")
        db.add(project)
        db.flush()
        project_id = project.id
    yield project_id
    with SessionLocal.begin() as db:
        db.execute(delete(JobRecovery).where(JobRecovery.project_id == project_id))
        db.execute(delete(Project).where(Project.id == project_id))


def add_document(db, project_id):
    document = Document(
        project_id=project_id,
        firm_id=DEV_FIRM,
        filename="brief.pdf",
        storage_key=str(uuid4()),
        media_type="application/pdf",
        byte_size=1,
        sha256=uuid4().hex * 2,
    )
    db.add(document)
    db.flush()
    return document


def test_job_lifecycle_and_retry_count(project_id):
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
        assert (job.status, job.progress, job.retry_count) == ("queued", 0, 0)
        assert job.started_at is job.finished_at is None
        job = transition_job(db, job.id, "queued", "running", stage="reading", progress=10)
        start = job.started_at
        assert start is not None and job.finished_at is None
        job = transition_job(db, job.id, "running", "queued", stage="retrying", progress=10)
        assert job.retry_count == 1
        job = transition_job(db, job.id, "queued", "running", stage="reading", progress=10)
        job = transition_job(db, job.id, "running", "running", stage="writing", progress=80)
        assert (job.current_stage, job.progress) == ("writing", 80)
        job = transition_job(db, job.id, "running", "completed", stage="done", progress=100)
        assert (job.progress, job.started_at, job.retry_count) == (100, start, 1)
        assert job.finished_at >= start
    with SessionLocal() as db:
        view = JobRead.model_validate(get_job(db, OWNER, job.id)).model_dump()
        assert view["status"] == "completed"
        assert {"request_metadata", "request_hash", "idempotency_key", "firm_id"}.isdisjoint(view)


@pytest.mark.parametrize(
    ("expected", "target", "progress"),
    [
        ("queued", "running", 80),  # stale claim
        ("running", "running", 40),  # regressing progress
        ("running", "running", 50),  # stale stage at the previous checkpoint
        ("running", "running", -1),
        ("running", "completed", 101),
        ("running", "completed", 99),
        ("queued", "completed", 100),
    ],
)
def test_transition_rejects_stale_or_invalid_update(project_id, expected, target, progress):
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
        transition_job(db, job.id, "queued", "running", stage="started", progress=50)
    with SessionLocal.begin() as db, pytest.raises(HTTPException) as rejected:
        transition_job(db, job.id, expected, target, stage="overwrite", progress=progress)
    assert rejected.value.status_code in (409, 422)
    with SessionLocal() as db:
        saved = db.get(GenerationJob, job.id)
        assert (saved.status, saved.current_stage, saved.progress) == ("running", "started", 50)


@pytest.mark.parametrize("initial", ["queued", "running"])
def test_cancelled_job_cannot_be_restarted(project_id, initial):
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
        if initial == "running":
            transition_job(db, job.id, "queued", initial, stage="starting", progress=0)
        job = transition_job(db, job.id, initial, "cancelled", stage="cancelled", progress=0)
        assert job.finished_at is not None
        with pytest.raises(HTTPException) as rejected:
            transition_job(db, job.id, "cancelled", "queued", stage="retrying", progress=0)
        assert rejected.value.status_code == 409


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (TimeoutError("private client document 123"), "timeout"),
        (RuntimeError("private client document 123"), "job_failed"),
        ("private client document 123", "job_failed"),
    ],
)
def test_failure_exposes_only_safe_fields(project_id, error, code):
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
        transition_job(db, job.id, "queued", "failed", stage="failed", progress=0, error=error)
    with SessionLocal() as db:
        job = get_job(db, OWNER, job.id)
        assert job.status == "failed" and job.finished_at is not None
        assert job.error_code == code and job.error_message
        assert "private client document" not in job.error_message


def test_concurrent_replay_and_conflicting_submission(project_id):
    ready = Barrier(2)

    def submit():
        with SessionLocal.begin() as db:
            ready.wait(timeout=5)
            return create_job(db, OWNER, project_id, "analysis", DIGEST, "submit").id

    with ThreadPoolExecutor(2) as pool:
        first, second = [
            future.result(timeout=10) for future in [pool.submit(submit) for _ in range(2)]
        ]
    assert first == second
    with SessionLocal.begin() as db:
        with pytest.raises(HTTPException) as changed:
            create_job(db, OWNER, project_id, "analysis", "b" * 64, "submit")
        assert changed.value.status_code == 409
        with pytest.raises(HTTPException) as active:
            create_job(db, OWNER, project_id, "analysis", DIGEST, "new")
        assert active.value.status_code == 409
        assert db.scalar(select(func.count()).where(GenerationJob.project_id == project_id)) == 1
        transition_job(db, first, "queued", "running", stage="starting", progress=0)
        transition_job(db, first, "running", "completed", stage="done", progress=100)
        assert create_job(db, OWNER, project_id, "analysis", DIGEST, "submit").id == first
        assert create_job(db, OWNER, project_id, "analysis", DIGEST, None).id != first


def test_reads_and_submissions_obey_firm_and_role(project_id):
    foreign = Principal(DEV_USER, uuid4(), Role.OWNER)
    reviewer = Principal(DEV_USER, DEV_FIRM, Role.REVIEWER)
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, "same")
        assert get_job(db, reviewer, job.id).id == job.id
        with pytest.raises(HTTPException) as denied:
            create_job(db, reviewer, project_id, "analysis", DIGEST, "same")
        assert denied.value.status_code == 403
        with pytest.raises(HTTPException) as hidden_read:
            get_job(db, foreign, job.id)
        assert hidden_read.value.status_code == 404
        with pytest.raises(HTTPException) as hidden_write:
            create_job(db, foreign, project_id, "analysis", DIGEST, "same")
        assert hidden_write.value.status_code == 404


def test_worker_registered_tasks_accept_only_ids_and_preserve_cancelled_jobs(project_id):
    celery.loader.import_default_modules()
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
        transition_job(db, job.id, "queued", "cancelled", stage="cancelled", progress=0)
    for name, prefix in [("worker.parse_document", [str(uuid4())]), ("worker.analyze_project", [])]:
        task = celery.tasks[name]
        task.apply(args=[*prefix, str(job.id)], throw=True)
        with pytest.raises(ValueError):
            task.apply(args=[*prefix, "arbitrary text"], throw=True)
        assert task.acks_late and task.ignore_result
        assert task.soft_time_limit < task.time_limit
    with SessionLocal() as db:
        assert get_job(db, OWNER, job.id).status == "cancelled"


@pytest.mark.parametrize(
    ("kind", "name"),
    [
        ("parse", "worker.parse_document"),
        ("analysis", "worker.analyze_project"),
    ],
)
def test_worker_recovers_a_lost_db_connection_and_acknowledges_redelivery(project_id, kind, name):
    celery.loader.import_default_modules()
    task = celery.tasks[name]
    with SessionLocal.begin() as db:
        document_id = add_document(db, project_id).id if kind == "parse" else None
        job = create_job(db, OWNER, project_id, kind, DIGEST, None, document_id=document_id)
        prefix = [str(document_id)] if document_id else []

    def disconnect(*args):
        raise OperationalError(
            None, None, OSError("connection dropped"), connection_invalidated=True
        )

    event.listen(engine, "before_cursor_execute", disconnect, once=True)
    try:
        result = task.apply(args=[*prefix, str(job.id)], throw=False)
    finally:
        event.remove(engine, "before_cursor_execute", disconnect)
    assert result.successful(), result.result
    with SessionLocal() as db:
        saved = get_job(db, OWNER, job.id)
        assert (saved.status, saved.error_code) == ("failed", "pipeline_unavailable")
        assert saved.retry_count == 1
        finished_at = saved.finished_at
    task.apply(args=[*prefix, str(job.id)], throw=True)
    with SessionLocal() as db:
        saved = get_job(db, OWNER, job.id)
        assert (saved.finished_at, saved.retry_count) == (finished_at, 1)


@pytest.mark.parametrize(
    "case", ["different", "nonexistent", "deleted", "legacy", "different_project"]
)
def test_parse_delivery_requires_matching_live_document(project_id, case):
    celery.loader.import_default_modules()
    with SessionLocal.begin() as db:
        intended = add_document(db, project_id)
        delivered_id = intended.id
        # Seed the persisted input independently of the job submission service.
        job = GenerationJob(
            project_id=project_id,
            firm_id=DEV_FIRM,
            kind="parse",
            request_metadata={"document_id": str(intended.id)},
        )
        db.add(job)
        if case == "different":
            delivered_id = add_document(db, project_id).id
        elif case == "nonexistent":
            db.delete(intended)
        elif case == "deleted":
            intended.deleted_at = datetime.now(UTC)
        elif case == "legacy":
            job.request_metadata = {}
        else:
            other = Project(firm_id=DEV_FIRM, created_by=DEV_USER, name="Other parse job")
            db.add(other)
            db.flush()
            intended.project_id = other.id
    try:
        celery.tasks["worker.parse_document"].apply(
            args=[str(delivered_id), str(job.id)], throw=True
        )
        with SessionLocal() as db:
            saved = get_job(db, OWNER, job.id)
            assert (saved.status, saved.error_code, saved.finished_at) == ("queued", None, None)
    finally:
        if case == "different_project":
            with SessionLocal.begin() as db:
                db.execute(delete(Project).where(Project.id == other.id))


def test_parse_submission_binds_live_document_and_scopes_replay(project_id):
    with SessionLocal.begin() as db:
        intended = add_document(db, project_id)
        other = add_document(db, project_id)
        with pytest.raises(HTTPException):
            create_job(db, OWNER, project_id, "parse", DIGEST, None)
        with pytest.raises(HTTPException) as missing:
            create_job(db, OWNER, project_id, "parse", DIGEST, None, document_id=uuid4())
        assert missing.value.status_code == 404
        job = create_job(db, OWNER, project_id, "parse", DIGEST, "submit", document_id=intended.id)
        assert job.request_metadata == {"document_id": str(intended.id)}
        same = create_job(db, OWNER, project_id, "parse", DIGEST, "submit", document_id=intended.id)
        assert same.id == job.id
        with pytest.raises(HTTPException) as changed:
            create_job(db, OWNER, project_id, "parse", DIGEST, "submit", document_id=other.id)
        assert changed.value.status_code == 409


@pytest.mark.parametrize(
    ("faults", "expected", "retries"),
    [
        (["connect"], "pipeline_unavailable", 1),
        (["network_timeout"], "pipeline_unavailable", 1),
        (["constraint"], "job_failed", 0),
        (["timeout"], "timeout", 0),
        (["connect"] * 4, "database_unavailable", 3),
        (["connect"] * 7, "database_unavailable", 3),
        (["constraint", "connect", "connect"], "job_failed", 0),
        (["constraint", "pool_timeout"], "job_failed", 0),
    ],
)
def test_worker_terminal_recovery_releases_project_without_leaking_errors(
    project_id, faults, expected, retries, caplog
):
    celery.loader.import_default_modules()
    task = celery.tasks["worker.analyze_project"]
    caplog.set_level(logging.INFO)
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)

    remaining = iter(faults)

    def fault(*args):
        match next(remaining, None):
            case "connect":
                raise OperationalError(None, None, ConnectionRefusedError(PRIVATE_MARKER))
            case "constraint":
                raise IntegrityError("sensitive SQL", None, Exception(PRIVATE_MARKER))
            case "timeout":
                raise SoftTimeLimitExceeded(PRIVATE_MARKER)
            case "network_timeout":
                raise TimeoutError(PRIVATE_MARKER)
            case "pool_timeout":
                raise PoolTimeout(PRIVATE_MARKER)

    event.listen(engine, "before_cursor_execute", fault)
    try:
        result = task.apply(args=[str(job.id)], throw=False)
    finally:
        event.remove(engine, "before_cursor_execute", fault)
    assert PRIVATE_MARKER not in caplog.text
    assert result.successful(), result.result
    if faults[0] == "timeout":
        age_job(job.id)
        run_watchdog_for(project_id)
    with SessionLocal.begin() as db:
        saved = get_job(db, OWNER, job.id)
        assert (saved.status, saved.error_code, saved.retry_count) == ("failed", expected, retries)
        assert saved.finished_at is not None and PRIVATE_MARKER not in saved.error_message
        assert create_job(db, OWNER, project_id, "analysis", DIGEST, None).id != job.id


def age_job(job_id):
    old = datetime.now(UTC) - timedelta(hours=2)
    with SessionLocal.begin() as db:
        db.execute(
            update(GenerationJob)
            .where(GenerationJob.id == job_id)
            .values(
                created_at=old,
                updated_at=old,
                started_at=old,
            )
        )


def run_watchdog_for(project_id):
    # Limit the integration scan to this fixture when tests use the local development DB.
    def scope(execution):
        if execution.is_select:
            execution.statement = execution.statement.options(
                with_loader_criteria(GenerationJob, GenerationJob.project_id == project_id)
            )

    event.listen(JobSession, "do_orm_execute", scope)
    try:
        celery.tasks["worker.reconcile_stale_jobs"].apply(throw=True)
    finally:
        event.remove(JobSession, "do_orm_execute", scope)


def test_soft_deadline_avoids_io_and_timeout_survives_broker_replay(project_id, monkeypatch):
    celery.loader.import_default_modules()
    task = celery.tasks["worker.analyze_project"]
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
    interrupted = False
    recovery_io = []

    def deadline(conn, cursor, statement, params, context, executemany):
        nonlocal interrupted
        if interrupted:
            recovery_io.append("sql")
            raise OperationalError(None, None, ConnectionRefusedError(PRIVATE_MARKER))
        if (
            statement.startswith("UPDATE generation_jobs")
            and "finished_at" in statement.split("WHERE")[0]
        ):
            interrupted = True
            raise SoftTimeLimitExceeded(PRIVATE_MARKER)

    def offline(*args, **kwargs):
        recovery_io.append("publish")
        raise ConnectionRefusedError("broker unavailable")

    monkeypatch.setattr(task, "retry_delivery", offline)
    event.listen(engine, "before_cursor_execute", deadline)
    try:
        task.apply(args=[str(job.id)], throw=False)
    finally:
        event.remove(engine, "before_cursor_execute", deadline)
    assert interrupted and recovery_io == []
    # The original ID-only delivery can arrive again without terminal headers.
    task.apply(args=[str(job.id)], throw=True)
    with SessionLocal() as db:
        assert get_job(db, OWNER, job.id).status == "running"
    age_job(job.id)
    run_watchdog_for(project_id)
    with SessionLocal() as db:
        assert get_job(db, OWNER, job.id).error_code == "timeout"


def test_timeout_cause_survives_failed_recovery_publish_and_original_replay(
    project_id, monkeypatch
):
    celery.loader.import_default_modules()
    task = celery.tasks["worker.analyze_project"]
    delivery_id = str(uuid4())
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
    interrupted = False

    def deadline(conn, cursor, statement, params, context, executemany):
        nonlocal interrupted
        if interrupted:
            raise OperationalError(None, None, ConnectionRefusedError(PRIVATE_MARKER))
        if (
            statement.startswith("UPDATE generation_jobs")
            and "finished_at" in statement.split("WHERE")[0]
        ):
            interrupted = True
            raise SoftTimeLimitExceeded()

    def broker_unavailable(*args, **kwargs):
        raise Reject("Retry publication failed.", requeue=False)

    monkeypatch.setattr(task, "retry", broker_unavailable)
    event.listen(engine, "before_cursor_execute", deadline)
    try:
        task.apply(args=[str(job.id)], task_id=delivery_id, throw=False)
    finally:
        event.remove(engine, "before_cursor_execute", deadline)
    assert interrupted
    # Redis can redeliver the original message without any terminal headers.
    task.apply(args=[str(job.id)], task_id=delivery_id, throw=True)
    age_job(job.id)
    run_watchdog_for(project_id)
    with SessionLocal() as db:
        saved = get_job(db, OWNER, job.id)
        assert (saved.status, saved.error_code) == ("failed", "timeout")


@pytest.mark.parametrize("kind", ["analysis", "parse"])
@pytest.mark.parametrize("status", ["queued", "running"])
def test_watchdog_skips_lock_then_releases_abandoned_job(project_id, kind, status):
    celery.loader.import_default_modules()
    with SessionLocal.begin() as db:
        document_id = add_document(db, project_id).id if kind == "parse" else None
        job = create_job(db, OWNER, project_id, kind, DIGEST, None, document_id=document_id)
        if status == "running":
            transition_job(db, job.id, "queued", "running", stage="reading", progress=10)
    age_job(job.id)
    with SessionLocal.begin() as locker:
        locker.scalar(select(GenerationJob).where(GenerationJob.id == job.id).with_for_update())
        run_watchdog_for(project_id)
        assert get_job(locker, OWNER, job.id).status == status
    run_watchdog_for(project_id)
    run_watchdog_for(project_id)
    with SessionLocal.begin() as db:
        saved = get_job(db, OWNER, job.id)
        assert (saved.status, saved.error_code, saved.retry_count) == ("failed", "timeout", 0)
        assert (
            create_job(db, OWNER, project_id, kind, DIGEST, None, document_id=document_id).id
            != job.id
        )


@pytest.mark.parametrize(
    "boundary",
    [
        "claim_query",
        "claim_commit",
        "terminal_query",
        "terminal_commit",
        "recovery_query",
        "recovery_commit",
    ],
)
def test_soft_timeout_discards_connection_without_rollback(project_id, monkeypatch, boundary):
    celery.loader.import_default_modules()
    task = celery.tasks["worker.analyze_project"]
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
    interrupted = False
    recovery_io = []
    commits = 0
    execute = engine.dialect.do_execute
    commit = engine.dialect.do_commit
    rollback = engine.dialect.do_rollback

    def deadline_execute(cursor, statement, parameters, context=None):
        nonlocal interrupted
        if interrupted:
            recovery_io.append("execute")
        terminal = (
            statement.startswith("UPDATE generation_jobs")
            and "finished_at" in statement.split("WHERE")[0]
        )
        if (
            boundary == "claim_query"
            and statement.startswith("SELECT")
            and "FOR UPDATE" in statement
        ) or (boundary in {"terminal_query", "recovery_query"} and terminal):
            interrupted = True
            raise SoftTimeLimitExceeded(PRIVATE_MARKER)
        return execute(cursor, statement, parameters, context)

    def deadline_commit(connection):
        nonlocal interrupted, commits
        commits += 1
        if (boundary in {"claim_commit", "recovery_commit"} and commits == 2) or (
            boundary == "terminal_commit" and commits == 3
        ):
            interrupted = True
            raise SoftTimeLimitExceeded(PRIVATE_MARKER)
        return commit(connection)

    def observe_rollback(connection):
        if interrupted:
            recovery_io.append("rollback")
        return rollback(connection)

    with monkeypatch.context() as patches:
        patches.setattr(engine.dialect, "do_execute", deadline_execute)
        patches.setattr(engine.dialect, "do_commit", deadline_commit)
        patches.setattr(engine.dialect, "do_rollback", observe_rollback)
        headers = (
            {"job_terminal_code": "timeout", "job_processing_retries": 0}
            if boundary.startswith("recovery")
            else None
        )
        result = task.apply(args=[str(job.id)], headers=headers, throw=False)
    assert result.successful(), result.result
    assert interrupted and recovery_io == []
    # Once the real soft deadline has elapsed, even an unclaimed delivery is stale.
    age_job(job.id)
    task.apply(args=[str(job.id)], throw=True)
    run_watchdog_for(project_id)
    with SessionLocal() as db:
        saved = get_job(db, OWNER, job.id)
        assert (saved.status, saved.error_code) == ("failed", "timeout")


def test_watchdog_preserves_fresh_and_terminal_jobs(project_id):
    celery.loader.import_default_modules()
    with SessionLocal.begin() as db:
        finished = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
        transition_job(
            db, finished.id, "queued", "failed", stage="failed", progress=0, error="job_failed"
        )
    age_job(finished.id)
    with SessionLocal.begin() as db:
        fresh = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
        original_finish = db.get(GenerationJob, finished.id).finished_at
    run_watchdog_for(project_id)
    with SessionLocal() as db:
        assert get_job(db, OWNER, fresh.id).status == "queued"
        saved = get_job(db, OWNER, finished.id)
        assert (saved.status, saved.error_code, saved.finished_at) == (
            "failed",
            "job_failed",
            original_finish,
        )


@pytest.mark.parametrize("metadata_write", [1, 2])
def test_soft_deadline_during_metadata_write_never_rolls_back(
    project_id, monkeypatch, metadata_write
):
    celery.loader.import_default_modules()
    task = celery.tasks["worker.analyze_project"]
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
    interrupted = False
    writes = 0
    after_deadline = []
    rollback = engine.dialect.do_rollback

    def deadline(conn, cursor, statement, params, context, executemany):
        nonlocal interrupted, writes
        if statement.startswith("UPDATE generation_jobs") and "request_metadata" in statement:
            writes += 1
            if writes == metadata_write:
                interrupted = True
                raise SoftTimeLimitExceeded()

    def observe_rollback(connection):
        if interrupted:
            after_deadline.append("rollback")
        return rollback(connection)

    monkeypatch.setattr(engine.dialect, "do_rollback", observe_rollback)
    event.listen(engine, "before_cursor_execute", deadline)
    try:
        result = task.apply(args=[str(job.id)], throw=False)
    finally:
        event.remove(engine, "before_cursor_execute", deadline)
    assert result.successful(), result.result
    assert interrupted and after_deadline == []


@pytest.mark.parametrize("watchdog_first", [True, False])
def test_terminal_recovery_cause_and_count_win_over_watchdog(project_id, watchdog_first):
    celery.loader.import_default_modules()
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
    age_job(job.id)
    if watchdog_first:
        run_watchdog_for(project_id)
    celery.tasks["worker.analyze_project"].apply(
        args=[str(job.id)],
        headers={"job_terminal_code": "database_unavailable", "job_processing_retries": 3},
        throw=True,
    )
    run_watchdog_for(project_id)
    with SessionLocal() as db:
        saved = get_job(db, OWNER, job.id)
        assert (saved.status, saved.error_code, saved.retry_count) == (
            "failed",
            "database_unavailable",
            3,
        )


@pytest.mark.parametrize("conflicting_scope", [False, True])
def test_fresh_locked_timeout_survives_failed_publication_and_headerless_replay(
    project_id, monkeypatch, conflicting_scope
):
    celery.loader.import_default_modules()
    task = celery.tasks["worker.analyze_project"]
    delivery_id = str(uuid4())
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
        if conflicting_scope:
            db.add(
                JobRecovery(
                    job_id=job.id,
                    project_id=uuid4(),
                    firm_id=DEV_FIRM,
                    attempt_id=delivery_id,
                    error_code="job_failed",
                    retry_count=0,
                )
            )

    def quick_lock_deadline(connection):
        connection.exec_driver_sql("SET LOCAL lock_timeout = '50ms'")

    def broker_unavailable(*args, **kwargs):
        raise Reject("Retry publication failed.", requeue=False)

    monkeypatch.setattr(task, "retry", broker_unavailable)
    event.listen(engine, "begin", quick_lock_deadline)
    try:
        with SessionLocal.begin() as locker:
            locker.scalar(select(GenerationJob).where(GenerationJob.id == job.id).with_for_update())
            task.apply(args=[str(job.id)], task_id=delivery_id, retries=3, throw=False)
            with SessionLocal() as db:
                intent = db.scalar(
                    select(JobRecovery).where(
                        JobRecovery.job_id == job.id, JobRecovery.project_id == project_id
                    )
                )
                assert intent is not None
                assert (intent.error_code, intent.retry_count) == ("timeout", 3)
    finally:
        event.remove(engine, "begin", quick_lock_deadline)
    # Requeue preserves neither terminal headers nor enough age for watchdog expiry.
    task.apply(args=[str(job.id)], task_id=delivery_id, retries=3, throw=True)
    run_watchdog_for(project_id)
    with SessionLocal() as db:
        saved = get_job(db, OWNER, job.id)
        assert (saved.status, saved.error_code, saved.retry_count) == ("failed", "timeout", 3)
        assert (
            db.scalar(
                select(func.count()).select_from(JobRecovery).where(JobRecovery.job_id == job.id)
            )
            == 0
        )


@pytest.mark.parametrize("stale", [False, True])
def test_watchdog_honors_pending_cause_before_default_expiry(project_id, stale):
    celery.loader.import_default_modules()
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
        db.add(
            JobRecovery(
                job_id=job.id,
                project_id=project_id,
                firm_id=DEV_FIRM,
                attempt_id=uuid4(),
                error_code="database_unavailable",
                retry_count=3,
            )
        )
    if stale:
        age_job(job.id)
    run_watchdog_for(project_id)
    with SessionLocal() as db:
        saved = get_job(db, OWNER, job.id)
        assert (saved.status, saved.error_code, saved.retry_count) == (
            "failed",
            "database_unavailable",
            3,
        )
        assert (
            db.scalar(
                select(func.count()).select_from(JobRecovery).where(JobRecovery.job_id == job.id)
            )
            == 0
        )


def test_intent_inserted_during_watchdog_snapshot_survives_to_next_pass(project_id):
    celery.loader.import_default_modules()
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
    age_job(job.id)
    inserted = False

    def late_intent(conn, cursor, statement, params, context, executemany):
        nonlocal inserted
        if not inserted and statement.startswith("SELECT job_recoveries."):
            inserted = True
            with SessionLocal.begin() as db:
                db.add(
                    JobRecovery(
                        job_id=job.id,
                        project_id=project_id,
                        firm_id=DEV_FIRM,
                        attempt_id=uuid4(),
                        error_code="database_unavailable",
                        retry_count=3,
                    )
                )

    event.listen(engine, "after_cursor_execute", late_intent)
    try:
        run_watchdog_for(project_id)
    finally:
        event.remove(engine, "after_cursor_execute", late_intent)
    with SessionLocal() as db:
        assert inserted and get_job(db, OWNER, job.id).error_code == "timeout"
        assert (
            db.scalar(
                select(func.count()).select_from(JobRecovery).where(JobRecovery.job_id == job.id)
            )
            == 1
        )
    run_watchdog_for(project_id)
    with SessionLocal() as db:
        saved = get_job(db, OWNER, job.id)
        assert (saved.error_code, saved.retry_count) == ("database_unavailable", 3)
        assert (
            db.scalar(
                select(func.count()).select_from(JobRecovery).where(JobRecovery.job_id == job.id)
            )
            == 0
        )


def test_recovery_intents_enforce_safe_codes_uniqueness_and_tenant_scope(project_id):
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
        attempt = uuid4()
        db.add(
            JobRecovery(
                job_id=job.id,
                project_id=project_id,
                firm_id=DEV_FIRM,
                attempt_id=attempt,
                error_code="timeout",
                retry_count=3,
            )
        )
    with SessionLocal.begin() as db:
        for code, retry_count, attempt_id in [
            ("private SQL", 3, uuid4()),
            ("timeout", -1, uuid4()),
            ("timeout", 3, attempt),
        ]:
            with pytest.raises(IntegrityError), db.begin_nested():
                db.add(
                    JobRecovery(
                        job_id=job.id,
                        project_id=project_id,
                        firm_id=DEV_FIRM,
                        attempt_id=attempt_id,
                        error_code=code,
                        retry_count=retry_count,
                    )
                )
                db.flush()
    with SessionLocal.begin() as db:
        db.execute(text("CREATE ROLE ce_test_recovery_rls NOLOGIN NOBYPASSRLS"))
        db.execute(text("GRANT USAGE ON SCHEMA public TO ce_test_recovery_rls"))
        db.execute(text("GRANT SELECT ON job_recoveries TO ce_test_recovery_rls"))
        db.execute(text("SET LOCAL ROLE ce_test_recovery_rls"))
        assert db.scalar(select(func.count()).select_from(JobRecovery)) == 0
        db.execute(text("SELECT set_config('app.firm_id', :firm, true)"), {"firm": str(uuid4())})
        assert db.scalar(select(func.count()).select_from(JobRecovery)) == 0
        db.execute(text("SELECT set_config('app.firm_id', :firm, true)"), {"firm": str(DEV_FIRM)})
        assert (
            db.scalar(
                select(func.count()).select_from(JobRecovery).where(JobRecovery.job_id == job.id)
            )
            == 1
        )
        db.rollback()  # Roll back the test role and grants, as well as SET LOCAL.


def test_watchdog_discards_intent_for_deleted_document_without_changing_job(project_id):
    celery.loader.import_default_modules()
    with SessionLocal.begin() as db:
        document = add_document(db, project_id)
        job = create_job(db, OWNER, project_id, "parse", DIGEST, None, document_id=document.id)
        db.add(
            JobRecovery(
                job_id=job.id,
                project_id=project_id,
                firm_id=DEV_FIRM,
                attempt_id=uuid4(),
                error_code="database_unavailable",
                retry_count=3,
            )
        )
        document.deleted_at = datetime.now(UTC)
    run_watchdog_for(project_id)
    with SessionLocal() as db:
        assert get_job(db, OWNER, job.id).status == "queued"
        assert (
            db.scalar(
                select(func.count()).select_from(JobRecovery).where(JobRecovery.job_id == job.id)
            )
            == 0
        )


def test_retry_count_raised_after_watchdog_snapshot_survives_cleanup(project_id):
    celery.loader.import_default_modules()
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", DIGEST, None)
        db.add(
            JobRecovery(
                job_id=job.id,
                project_id=project_id,
                firm_id=DEV_FIRM,
                attempt_id=uuid4(),
                error_code="database_unavailable",
                retry_count=1,
            )
        )
    raised_count = False

    def later_retry_count(conn, cursor, statement, params, context, executemany):
        nonlocal raised_count
        if not raised_count and statement.startswith("SELECT job_recoveries."):
            raised_count = True
            with SessionLocal.begin() as db:
                db.execute(
                    update(JobRecovery).where(JobRecovery.job_id == job.id).values(retry_count=3)
                )

    event.listen(engine, "after_cursor_execute", later_retry_count)
    try:
        run_watchdog_for(project_id)
    finally:
        event.remove(engine, "after_cursor_execute", later_retry_count)
    run_watchdog_for(project_id)
    with SessionLocal() as db:
        saved = get_job(db, OWNER, job.id)
        assert raised_count and (saved.error_code, saved.retry_count) == ("database_unavailable", 3)
