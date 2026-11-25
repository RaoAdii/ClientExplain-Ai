from uuid import UUID

from app.core.auth import Principal, get_principal, tenant_session
from app.schemas.analysis import AnalysisRequest
from app.schemas.editor import WorkflowRead, WorkflowWrite
from app.schemas.jobs import JobRead
from app.schemas.workflow import (
    CitationRead,
    ErrorRead,
    ProcessRead,
    StageRead,
    ValidationErrorRead,
)
from app.services.editor import read_workflow, save_workflow
from app.services.jobs import get_job
from app.services.workflow import get_stage, list_citations, list_stages, submit_analysis
from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

router = APIRouter(
    tags=["Analysis"],
    responses={
        401: {"model": ErrorRead},
        404: {"model": ErrorRead},
        422: {"model": ValidationErrorRead},
    },
)


@router.get("/projects/{project_id}/workflow", response_model=WorkflowRead)
def workflow(
    project_id: UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    return read_workflow(db, principal, project_id)


@router.patch("/projects/{project_id}/workflow", response_model=WorkflowRead)
def edit_workflow(
    project_id: UUID,
    data: WorkflowWrite,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    return save_workflow(db, principal, project_id, data)


@router.post(
    "/projects/{project_id}/analyze",
    response_model=JobRead,
    status_code=202,
    responses={code: {"model": ErrorRead} for code in (403, 409, 429, 503)},
)
def analyze(
    project_id: UUID,
    data: AnalysisRequest,
    response: Response,
    idempotency_key: str | None = Header(None, min_length=1, max_length=200),
    principal: Principal = Depends(get_principal),
):
    return submit_analysis(principal, project_id, data, idempotency_key, response)


@router.get("/jobs/{job_id}", response_model=JobRead, tags=["Jobs"])
def job(
    job_id: UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    return get_job(db, principal, job_id)


@router.get("/projects/{project_id}/stages", response_model=ProcessRead)
def stages(
    project_id: UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    return list_stages(db, principal, project_id)


@router.get("/stages/{stage_id}", response_model=StageRead)
def stage(
    stage_id: UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    return get_stage(db, principal, stage_id)


@router.get("/projects/{project_id}/citations", response_model=list[CitationRead])
def citations(
    project_id: UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    return list_citations(db, principal, project_id)
