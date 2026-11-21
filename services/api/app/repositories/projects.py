from uuid import UUID

from app.models.entities import Project
from app.schemas.projects import ReviewStatus, WorkflowStatus
from sqlalchemy import func, or_, select, true
from sqlalchemy.orm import Session, aliased


def list_projects(
    db: Session,
    firm_id: UUID,
    limit: int,
    offset: int,
    search: str = "",
    status: WorkflowStatus | None = None,
    review_status: ReviewStatus | None = None,
):
    filters = [Project.firm_id == firm_id]
    if search := search.strip():
        filters.append(
            or_(
                *(
                    field.icontains(search, autoescape=True)
                    for field in (
                        Project.name,
                        Project.description,
                        Project.jurisdiction,
                        Project.legal_area,
                    )
                )
            )
        )
    if status is not None:
        filters.append(Project.workflow_status == status)
    if review_status is not None:
        filters.append(Project.review_status == review_status)
    totals = select(func.count().label("total")).select_from(Project).where(*filters).subquery()
    page = (
        select(Project)
        .where(*filters)
        .order_by(Project.updated_at.desc(), Project.id)
        .limit(limit)
        .offset(offset)
        .subquery()
    )
    item = aliased(Project, page)
    # Anchor the outer join on the aggregate so an empty page still carries the total.
    rows = db.execute(
        select(totals.c.total, item)
        .select_from(totals)
        .outerjoin(item, true())
        .order_by(item.updated_at.desc(), item.id)
    ).all()
    total = rows[0][0]
    items = [project for _, project in rows if project is not None]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def find_project(db: Session, firm_id: UUID, project_id: UUID, *, for_update: bool = False):
    query = select(Project).where(Project.id == project_id, Project.firm_id == firm_id)
    if for_update:
        query = query.with_for_update()
    return db.scalar(query)
