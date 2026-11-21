from uuid import UUID

from app.core.auth import Principal
from app.core.permissions import (
    PROJECT_EDITORS,
    PROJECT_MANAGERS,
    can_transition_review,
    check_roles,
)
from app.models.entities import Project
from app.repositories.projects import find_project
from app.schemas.projects import ProjectCreate, ProjectUpdate
from app.services.activity import audit
from fastapi import HTTPException
from sqlalchemy.orm import Session


def require_project(
    db: Session, principal: Principal, project_id: UUID, *, for_update: bool = False
):
    project = find_project(db, principal.firm_id, project_id, for_update=for_update)
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


def create_project(db: Session, principal: Principal, data: ProjectCreate):
    project = Project(
        **data.model_dump(),
        firm_id=principal.firm_id,
        created_by=principal.user_id,
        owner_id=principal.user_id,
    )
    db.add(project)
    db.flush()
    audit(db, principal, "project.created", project.id)
    return project


def update_project(db: Session, principal: Principal, project_id: UUID, data: ProjectUpdate):
    project = require_project(db, principal, project_id, for_update=True)
    metadata = data.model_dump(exclude_unset=True, exclude={"review_status"})
    if metadata:
        check_roles(principal, *PROJECT_EDITORS)
    if data.review_status is not None:
        if not can_transition_review(principal.role, project.review_status, data.review_status):
            raise HTTPException(403, "Your role does not permit this review transition.")
        if project.review_status != data.review_status:
            project.review_status = data.review_status
            audit(db, principal, "project.review_changed", project.id)
    if metadata:
        for field, value in metadata.items():
            setattr(project, field, value)
        audit(db, principal, "project.updated", project.id)
    db.flush()
    db.refresh(project)
    return project


def delete_project(db: Session, principal: Principal, project_id: UUID):
    project = require_project(db, principal, project_id, for_update=True)
    check_roles(principal, *PROJECT_MANAGERS)
    audit(db, principal, "project.deleted", project.id)
    db.delete(project)
    db.flush()
