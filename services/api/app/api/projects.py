from uuid import UUID

from app.core.auth import Principal, get_principal, tenant_session
from app.core.permissions import PROJECT_EDITORS, require_roles
from app.repositories.projects import list_projects
from app.schemas.projects import (
    ActivityRead,
    ProjectCreate,
    ProjectPage,
    ProjectRead,
    ProjectUpdate,
    ReviewStatus,
    WorkflowStatus,
)
from app.services.activity import project_activity
from app.services.projects import create_project, delete_project, require_project, update_project
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=ProjectPage)
def index(
    search: str = Query("", max_length=200),
    status: WorkflowStatus | None = None,
    review_status: ReviewStatus | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    return list_projects(db, principal.firm_id, limit, offset, search, status, review_status)


@router.post("", response_model=ProjectRead, status_code=201)
def create(
    data: ProjectCreate,
    principal: Principal = Depends(require_roles(*PROJECT_EDITORS)),
    db: Session = Depends(tenant_session, scope="function"),
):
    return create_project(db, principal, data)


@router.get("/{project_id}", response_model=ProjectRead)
def show(
    project_id: UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    return require_project(db, principal, project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
def update(
    project_id: UUID,
    data: ProjectUpdate,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    return update_project(db, principal, project_id, data)


@router.delete("/{project_id}", status_code=204)
def delete(
    project_id: UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    delete_project(db, principal, project_id)
    return Response(status_code=204)


@router.get("/{project_id}/activity", response_model=list[ActivityRead])
def activity(
    project_id: UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    require_project(db, principal, project_id)
    return project_activity(db, principal.firm_id, project_id)
