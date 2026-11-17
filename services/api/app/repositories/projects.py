from uuid import UUID

from app.models.entities import Project
from sqlalchemy import select
from sqlalchemy.orm import Session


def list_projects(db: Session, firm_id: UUID, limit: int, offset: int):
    return db.scalars(
        select(Project)
        .where(Project.firm_id == firm_id)
        .order_by(Project.created_at.desc(), Project.id)
        .limit(limit)
        .offset(offset)
    ).all()


def find_project(db: Session, firm_id: UUID, project_id: UUID):
    return db.scalar(select(Project).where(Project.id == project_id, Project.firm_id == firm_id))
