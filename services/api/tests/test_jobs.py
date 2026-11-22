import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from app.core.auth import DEV_FIRM, DEV_USER, Principal
from app.db.session import SessionLocal, engine
from app.models.entities import Document, GenerationJob, Project
from app.schemas.auth import Role
from app.schemas.jobs import JobRead
from app.services.jobs import create_job, get_job, transition_job
from celery.exceptions import SoftTimeLimitExceeded
from fastapi import HTTPException
from sqlalchemy import delete, event, func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from worker.celery_app import app as celery

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
        (["timeout", "connect", "connect"], "timeout", 0),
        (["timeout", "pool_timeout"], "timeout", 0),
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
    with SessionLocal.begin() as db:
        saved = get_job(db, OWNER, job.id)
        assert (saved.status, saved.error_code, saved.retry_count) == ("failed", expected, retries)
        assert saved.finished_at is not None and PRIVATE_MARKER not in saved.error_message
        assert create_job(db, OWNER, project_id, "analysis", DIGEST, None).id != job.id
