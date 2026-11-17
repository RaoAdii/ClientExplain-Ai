from app.models.entities import AuditEvent, Project
from app.repositories.projects import find_project
from fastapi import HTTPException


def require_project(db, principal, project_id):
    project = find_project(db, principal.firm_id, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


def audit(db, principal, action, project_id):
    db.add(
        AuditEvent(
            firm_id=principal.firm_id,
            actor_id=principal.user_id,
            action=action,
            resource_id=project_id,
        )
    )


def create_project(db, principal, data):
    project = Project(**data.model_dump(), firm_id=principal.firm_id, created_by=principal.user_id)
    db.add(project)
    db.flush()
    audit(db, principal, "project.created", project.id)
    return project
