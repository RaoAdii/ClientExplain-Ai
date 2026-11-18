from uuid import UUID

from app.core.auth import Principal, get_principal, tenant_session
from app.db.session import SessionLocal, redis_client
from app.repositories.projects import list_projects
from app.schemas.projects import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.projects import audit, create_project, require_project
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1")


@router.get("/health", tags=["Operations"])
def health():
    return {"status": "ok", "service": "clientexplain-api", "version": "0.1.0"}


@router.get("/health/ready", tags=["Operations"])
def ready():
    try:
        with SessionLocal() as db:
            revision = db.scalar(text("SELECT version_num FROM alembic_version"))
            if revision != "a27d9c4e8b11":
                raise RuntimeError("Database migrations are not current")
            db.execute(text("SELECT 1 FROM projects LIMIT 0"))
        redis_client.ping()
    except Exception as exc:
        raise HTTPException(503, "Database or queue is unavailable") from exc
    return {"status": "ready", "database": "connected", "redis": "connected"}


@router.get("/projects", response_model=list[ProjectRead], tags=["Projects"])
def index(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    return list_projects(db, principal.firm_id, limit, offset)


@router.post("/projects", response_model=ProjectRead, status_code=201, tags=["Projects"])
def create(
    data: ProjectCreate,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    return create_project(db, principal, data)


@router.get("/projects/{project_id}", response_model=ProjectRead, tags=["Projects"])
def show(
    project_id: UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    return require_project(db, principal, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectRead, tags=["Projects"])
def update(
    project_id: UUID,
    data: ProjectUpdate,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    project = require_project(db, principal, project_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    audit(db, principal, "project.updated", project.id)
    db.flush()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=204, tags=["Projects"])
def delete(
    project_id: UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    project = require_project(db, principal, project_id)
    audit(db, principal, "project.deleted", project.id)
    db.delete(project)
    db.flush()
    return Response(status_code=204)
