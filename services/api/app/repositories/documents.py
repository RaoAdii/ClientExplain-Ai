from uuid import UUID

from app.models.entities import Document
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session


def find_duplicate(db: Session, firm_id: UUID, project_id: UUID, sha256: str):
    return db.scalar(
        select(Document).where(
            Document.firm_id == firm_id,
            Document.project_id == project_id,
            Document.sha256 == sha256,
        )
    )


def insert_document(db: Session, **values):
    return db.scalar(
        insert(Document)
        .values(**values)
        .on_conflict_do_nothing(constraint="uq_documents_project_sha256")
        .returning(Document)
    )
