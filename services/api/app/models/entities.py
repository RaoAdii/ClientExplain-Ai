"""Relational foundation. Tenant children use composite foreign keys."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Record:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Tenant:
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"), index=True
    )


class Profile(Record, Base):
    __tablename__ = "profiles"
    display_name: Mapped[str] = mapped_column(String(120), default="Lawyer")


class Firm(Record, Base):
    __tablename__ = "firms"
    name: Mapped[str] = mapped_column(String(200))


class FirmMember(Record, Tenant, Base):
    __tablename__ = "firm_members"
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="member")
    __table_args__ = (
        UniqueConstraint("firm_id", "profile_id"),
        CheckConstraint("role IN ('owner', 'member')"),
    )


class Project(Record, Tenant, Base):
    __tablename__ = "projects"
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    jurisdiction: Mapped[str] = mapped_column(String(120), default="")
    review_status: Mapped[str] = mapped_column(String(30), default="requires_review")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    __table_args__ = (
        UniqueConstraint("id", "firm_id"),
        CheckConstraint("length(trim(name)) > 0"),
        CheckConstraint("review_status IN ('requires_review', 'in_review', 'approved')"),
    )


def project_constraints(*extra):
    return (
        UniqueConstraint("id", "firm_id"),
        ForeignKeyConstraint(
            ["project_id", "firm_id"], ["projects.id", "projects.firm_id"], ondelete="CASCADE"
        ),
        *extra,
    )


class ProjectChild(Record, Tenant):
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)


class Document(ProjectChild, Base):
    __tablename__ = "documents"
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(Text, unique=True)
    media_type: Mapped[str] = mapped_column(String(100))
    byte_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    __table_args__ = project_constraints(CheckConstraint("byte_size >= 0"))


class DocumentChunk(Record, Tenant, Base):
    __tablename__ = "document_chunks"
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    position: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "firm_id"], ["documents.id", "documents.firm_id"], ondelete="CASCADE"
        ),
        UniqueConstraint("document_id", "position"),
        CheckConstraint("position >= 0"),
    )


class LegalSource(Record, Tenant, Base):
    __tablename__ = "legal_sources"
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(Text)
    jurisdiction: Mapped[str] = mapped_column(String(120))
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (UniqueConstraint("id", "firm_id"),)


class SourceChunk(Record, Tenant, Base):
    __tablename__ = "source_chunks"
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    position: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    __table_args__ = (
        UniqueConstraint("id", "firm_id"),
        UniqueConstraint("source_id", "position"),
        ForeignKeyConstraint(
            ["source_id", "firm_id"],
            ["legal_sources.id", "legal_sources.firm_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("position >= 0"),
    )


class ProcessStage(ProjectChild, Base):
    __tablename__ = "process_stages"
    title: Mapped[str] = mapped_column(String(200))
    explanation: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    __table_args__ = project_constraints(
        UniqueConstraint("project_id", "position"), CheckConstraint("position >= 0")
    )


class StageCitation(Record, Tenant, Base):
    __tablename__ = "stage_citations"
    stage_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    source_chunk_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    excerpt: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["stage_id", "firm_id"],
            ["process_stages.id", "process_stages.firm_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_chunk_id", "firm_id"], ["source_chunks.id", "source_chunks.firm_id"]
        ),
        UniqueConstraint("stage_id", "source_chunk_id"),
    )


class GeneratedAsset(ProjectChild, Base):
    __tablename__ = "generated_assets"
    storage_key: Mapped[str] = mapped_column(Text, unique=True)
    provider: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(150))
    requires_review: Mapped[bool] = mapped_column(default=True)
    __table_args__ = project_constraints()


class GenerationJob(ProjectChild, Base):
    __tablename__ = "generation_jobs"
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    kind: Mapped[str] = mapped_column(String(40))
    error_code: Mapped[str | None] = mapped_column(String(60))
    __table_args__ = project_constraints(
        CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')")
    )


class ProjectVersion(ProjectChild, Base):
    __tablename__ = "project_versions"
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    __table_args__ = project_constraints(
        UniqueConstraint("project_id", "version"), CheckConstraint("version > 0")
    )


class Export(ProjectChild, Base):
    __tablename__ = "exports"
    format: Mapped[str] = mapped_column(String(10))
    storage_key: Mapped[str] = mapped_column(Text, unique=True)
    __table_args__ = project_constraints(CheckConstraint("format IN ('pdf', 'png')"))


class AuditEvent(Record, Tenant, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid)
