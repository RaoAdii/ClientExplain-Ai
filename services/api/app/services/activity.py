from uuid import UUID

from app.core.auth import Principal
from app.models.entities import AuditEvent
from sqlalchemy import select
from sqlalchemy.orm import Session


def audit(db: Session, principal: Principal, action: str, project_id: UUID) -> None:
    db.add(
        AuditEvent(
            firm_id=principal.firm_id,
            actor_id=principal.user_id,
            action=action,
            resource_id=project_id,
        )
    )


def project_activity(db: Session, firm_id: UUID, project_id: UUID):
    return db.scalars(
        select(AuditEvent)
        .where(AuditEvent.firm_id == firm_id, AuditEvent.resource_id == project_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id)
    ).all()
