from uuid import UUID

from app.core.auth import Principal
from app.core.permissions import PROJECT_EDITORS, check_roles
from app.models.entities import GenerationJob
from app.repositories.jobs import find_job, find_submission, insert_job
from app.schemas.jobs import JobStatus, JobType
from app.services.projects import require_project
from fastapi import HTTPException
from sqlalchemy import func, update
from sqlalchemy.orm import Session

TRANSITIONS = {
    "queued": {"running", "cancelled", "failed"},
    "running": {"running", "queued", "cancelled", "failed", "completed"},
}
SAFE_ERRORS = {
    "timeout": "The operation timed out.",
    "pipeline_unavailable": "Processing is unavailable.",
    "job_failed": "The job could not be completed.",
}


def create_job(
    db: Session,
    principal: Principal,
    project_id: UUID,
    job_type: JobType,
    request_hash: str,
    idempotency_key: str | None,
) -> GenerationJob:
    require_project(db, principal, project_id)
    check_roles(principal, *PROJECT_EDITORS)
    if idempotency_key is not None and not 1 <= len(idempotency_key) <= 200:
        raise HTTPException(422, "A submission key must contain between 1 and 200 characters.")
    job = insert_job(db, principal.firm_id, project_id, job_type, request_hash, idempotency_key)
    if job is not None:
        return job
    if idempotency_key is not None:
        existing = find_submission(db, principal.firm_id, project_id, job_type, idempotency_key)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise HTTPException(409, "The submission key belongs to a different request.")
            return existing
    raise HTTPException(409, "An analysis job is already active for this project.")


def get_job(db: Session, principal: Principal, job_id: UUID) -> GenerationJob:
    job = find_job(db, principal.firm_id, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


def transition_job(
    db: Session,
    job_id: UUID,
    expected: JobStatus,
    target: JobStatus,
    *,
    stage: str,
    progress: int,
    error: Exception | str | None = None,
) -> GenerationJob:
    if target not in TRANSITIONS.get(expected, ()):
        raise HTTPException(409, "Invalid job transition.")
    if type(progress) is not int or not 0 <= progress <= 100:
        raise HTTPException(422, "Progress must be an integer between 0 and 100.")
    if target == "completed" and progress != 100:
        raise HTTPException(422, "A completed job requires 100 percent progress.")
    if not stage or len(stage) > 80:
        raise HTTPException(422, "Provide a valid job stage.")
    values = {"status": target, "current_stage": stage, "progress": progress}
    if target == "running" and expected == "queued":
        values["started_at"] = func.coalesce(GenerationJob.started_at, func.clock_timestamp())
    if target == "queued":
        values["retry_count"] = GenerationJob.retry_count + 1
    if target in {"completed", "failed", "cancelled"}:
        values["finished_at"] = func.clock_timestamp()
    if target == "failed":
        code = "job_failed"
        if isinstance(error, TimeoutError):
            code = "timeout"
        elif isinstance(error, str) and error in SAFE_ERRORS:
            code = error
        values.update(error_code=code, error_message=SAFE_ERRORS[code])

    checkpoint = (
        GenerationJob.progress < progress
        if expected == target
        else (GenerationJob.progress <= progress)
    )
    job = db.scalar(
        update(GenerationJob)
        .where(GenerationJob.id == job_id, GenerationJob.status == expected, checkpoint)
        .values(**values)
        .returning(GenerationJob)
        .execution_options(populate_existing=True, synchronize_session=False)
    )
    if job is None:
        raise HTTPException(409, "The job has already advanced.")
    return job
