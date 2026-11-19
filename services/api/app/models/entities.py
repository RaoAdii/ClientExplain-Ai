"""Relational foundation. Tenant children use composite foreign keys."""

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Computed,
    DateTime,
    FetchedValue,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
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
    role: Mapped[str] = mapped_column(String(20), server_default="lawyer")
    __table_args__ = (
        UniqueConstraint("firm_id", "profile_id"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'lawyer', 'reviewer')", name="ck_firm_members_role"
        ),
    )


class Project(Record, Tenant, Base):
    __tablename__ = "projects"
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    jurisdiction: Mapped[str] = mapped_column(String(120), default="")
    review_status: Mapped[str] = mapped_column(String(30), default="requires_review")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id"), server_default=FetchedValue()
    )
    legal_area: Mapped[str] = mapped_column(String(120), server_default="")
    language: Mapped[str] = mapped_column(String(60), server_default="")
    target_audience: Mapped[str] = mapped_column(String(120), server_default="")
    complexity: Mapped[str] = mapped_column(String(40), server_default="unspecified")
    workflow_status: Mapped[str] = mapped_column(String(30), server_default="draft")
    processing_status: Mapped[str] = mapped_column(String(30), server_default="idle")
    __table_args__ = (
        UniqueConstraint("id", "firm_id"),
        CheckConstraint("length(trim(name)) > 0"),
        CheckConstraint("review_status IN ('requires_review', 'in_review', 'approved')"),
        CheckConstraint(
            "workflow_status IN ('draft', 'active', 'archived')", name="ck_projects_workflow_status"
        ),
        CheckConstraint(
            "processing_status IN ('idle', 'queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_projects_processing_status",
        ),
        Index("ix_projects_workflow", "firm_id", "workflow_status", "updated_at"),
        Index("ix_projects_review", "firm_id", "review_status", "updated_at"),
        Index(
            "ix_projects_name_search",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
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
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    sha256: Mapped[str | None] = mapped_column(String(64))
    document_metadata: Mapped[dict] = mapped_column("metadata", JSON, server_default="{}")
    page_count: Mapped[int | None]
    parsing_error: Mapped[str | None] = mapped_column(String(300))
    ocr_required: Mapped[bool] = mapped_column(server_default=text("false"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id"))
    __table_args__ = project_constraints(
        CheckConstraint("byte_size >= 0"),
        CheckConstraint("page_count >= 0", name="ck_documents_page_count"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_documents_sha256"),
        UniqueConstraint("firm_id", "project_id", "sha256", name="uq_documents_project_sha256"),
        UniqueConstraint("id", "project_id", "firm_id", name="uq_documents_project_identity"),
    )


class ChunkEvidence:
    page_number: Mapped[int | None]
    heading: Mapped[str | None] = mapped_column(Text)
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSON, server_default="{}")
    embedding = mapped_column(Vector(1536), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    embedding_provider: Mapped[str | None] = mapped_column(String(60))
    # Step 1 vectors lack verified provider provenance and can have any dimension.
    legacy_embedding = mapped_column(Vector(), nullable=True, deferred=True)
    legacy_embedding_model: Mapped[str | None] = mapped_column(String(120), deferred=True)


def chunk_indexes_and_checks(table):
    return (
        CheckConstraint("page_number > 0", name=f"ck_{table}_page_number"),
        CheckConstraint(
            "embedding IS NULL OR (embedding_model IS NOT NULL AND embedding_provider IS NOT NULL)",
            name=f"ck_{table}_embedding_provenance",
        ),
        Index(
            f"ix_{table}_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class DocumentChunk(ChunkEvidence, Record, Tenant, Base):
    __tablename__ = "document_chunks"
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    position: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    source_filename: Mapped[str | None] = mapped_column(String(255))
    char_start: Mapped[int | None]
    char_end: Mapped[int | None]
    token_start: Mapped[int | None]
    token_end: Mapped[int | None]
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "firm_id"], ["documents.id", "documents.firm_id"], ondelete="CASCADE"
        ),
        UniqueConstraint("document_id", "position"),
        CheckConstraint("position >= 0"),
        UniqueConstraint("id", "firm_id", name="uq_document_chunks_identity"),
        UniqueConstraint("id", "document_id", "firm_id", name="uq_document_chunks_parent"),
        CheckConstraint(
            "char_start >= 0 AND char_end >= char_start", name="ck_document_chunks_char_offsets"
        ),
        CheckConstraint(
            "token_start >= 0 AND token_end >= token_start", name="ck_document_chunks_token_offsets"
        ),
        *chunk_indexes_and_checks("document_chunks"),
    )


class LegalSource(Record, Tenant, Base):
    __tablename__ = "legal_sources"
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(Text)
    jurisdiction: Mapped[str] = mapped_column(String(120))
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    source_type: Mapped[str] = mapped_column(String(40), server_default="unspecified")
    citation_reference: Mapped[str | None] = mapped_column(Text)
    effective_date: Mapped[date | None]
    repeal_date: Mapped[date | None]
    verification_status: Mapped[str] = mapped_column(String(30), server_default="unverified")
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_metadata: Mapped[dict] = mapped_column("metadata", JSON, server_default="{}")
    project_id: Mapped[uuid.UUID | None]
    document_id: Mapped[uuid.UUID | None]
    citation_scope: Mapped[str] = mapped_column(
        Text, Computed("coalesce(project_id::text, verification_status)", persisted=True)
    )
    __table_args__ = (
        UniqueConstraint("id", "firm_id"),
        UniqueConstraint("id", "citation_scope", "firm_id", name="uq_legal_sources_citation_scope"),
        ForeignKeyConstraint(
            ["project_id", "firm_id"], ["projects.id", "projects.firm_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["document_id", "project_id", "firm_id"],
            ["documents.id", "documents.project_id", "documents.firm_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "document_id IS NULL OR project_id IS NOT NULL",
            name="ck_legal_sources_document_project",
        ),
        CheckConstraint(
            "verification_status IN ('verified','unverified')", name="ck_legal_sources_verification"
        ),
        CheckConstraint("repeal_date >= effective_date", name="ck_legal_sources_dates"),
        Index(
            "ix_legal_sources_retrieval",
            "firm_id",
            "project_id",
            "jurisdiction",
            "verification_status",
        ),
    )


class SourceChunk(ChunkEvidence, Record, Tenant, Base):
    __tablename__ = "source_chunks"
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    position: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("id", "firm_id"),
        UniqueConstraint("id", "source_id", "firm_id", name="uq_source_chunks_parent"),
        UniqueConstraint("source_id", "position"),
        ForeignKeyConstraint(
            ["source_id", "firm_id"],
            ["legal_sources.id", "legal_sources.firm_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("position >= 0"),
        *chunk_indexes_and_checks("source_chunks"),
    )


class ProcessStage(ProjectChild, Base):
    __tablename__ = "process_stages"
    title: Mapped[str] = mapped_column(String(200))
    explanation: Mapped[str] = mapped_column(Text)
    responsible_party: Mapped[str | None] = mapped_column(Text)
    required_documents: Mapped[list] = mapped_column(JSON, server_default="[]")
    estimated_duration: Mapped[str | None] = mapped_column(Text)
    source_backed: Mapped[bool] = mapped_column(server_default=text("false"))
    general_explanation: Mapped[bool] = mapped_column(server_default=text("true"))
    limitations: Mapped[list] = mapped_column(JSON, server_default="[]")
    verification_status: Mapped[str] = mapped_column(String(30), server_default="unverified")
    visual_prompt: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    __table_args__ = project_constraints(
        UniqueConstraint("id", "project_id", "firm_id", name="uq_process_stages_project"),
        UniqueConstraint("project_id", "position"),
        CheckConstraint("position >= 0"),
        CheckConstraint(
            "verification_status IN ('supported','unverified','unsupported')",
            name="ck_process_stages_verification",
        ),
    )


class StageCitation(Record, Tenant, Base):
    __tablename__ = "stage_citations"
    stage_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    document_chunk_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    excerpt: Mapped[str] = mapped_column(Text)
    # PostgreSQL derives this ancestry from the stage and chunk on each write.
    project_id: Mapped[uuid.UUID] = mapped_column(server_default=FetchedValue())
    document_id: Mapped[uuid.UUID | None] = mapped_column(server_default=FetchedValue())
    legal_source_id: Mapped[uuid.UUID | None] = mapped_column(server_default=FetchedValue())
    source_scope: Mapped[str | None] = mapped_column(Text, server_default=FetchedValue())
    claim_text: Mapped[str] = mapped_column(Text, server_default="")
    validation_status: Mapped[str] = mapped_column(String(30), server_default="unverified")
    __table_args__ = (
        ForeignKeyConstraint(["stage_id", "project_id", "firm_id"],
                             ["process_stages.id", "process_stages.project_id", "process_stages.firm_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["document_chunk_id", "document_id", "firm_id"],
                             ["document_chunks.id", "document_chunks.document_id", "document_chunks.firm_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["document_id", "project_id", "firm_id"],
                             ["documents.id", "documents.project_id", "documents.firm_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["source_chunk_id", "legal_source_id", "firm_id"],
                             ["source_chunks.id", "source_chunks.source_id", "source_chunks.firm_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["legal_source_id", "source_scope", "firm_id"],
                             ["legal_sources.id", "legal_sources.citation_scope", "legal_sources.firm_id"], ondelete="CASCADE"),
        CheckConstraint("document_chunk_id IS NULL OR document_id IS NOT NULL", name="ck_stage_citations_document_parent"),
        CheckConstraint("source_chunk_id IS NULL OR (legal_source_id IS NOT NULL AND source_scope IS NOT NULL AND source_scope IN ('verified', project_id::text))", name="ck_stage_citations_source_scope"),
        ForeignKeyConstraint(
            ["stage_id", "firm_id"],
            ["process_stages.id", "process_stages.firm_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_chunk_id", "firm_id"],
            ["source_chunks.id", "source_chunks.firm_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_chunk_id", "firm_id"],
            ["document_chunks.id", "document_chunks.firm_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "num_nonnulls(source_chunk_id, document_chunk_id) = 1",
            name="ck_stage_citations_one_target",
        ),
        CheckConstraint(
            "validation_status IN ('supported','unverified','unsupported')",
            name="ck_stage_citations_validation",
        ),
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
    status: Mapped[str] = mapped_column(String(20), server_default="queued", index=True)
    kind: Mapped[str] = mapped_column(String(40))
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(String(300))
    current_stage: Mapped[str | None] = mapped_column(String(80))
    progress: Mapped[int] = mapped_column(server_default="0")
    retry_count: Mapped[int] = mapped_column(server_default="0")
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    request_metadata: Mapped[dict] = mapped_column(JSON, server_default="{}")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = project_constraints(
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_generation_jobs_status",
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_generation_jobs_progress"),
        CheckConstraint("retry_count >= 0", name="ck_generation_jobs_retry_count"),
        UniqueConstraint("id", "project_id", "firm_id", name="uq_generation_jobs_project_identity"),
        UniqueConstraint(
            "firm_id", "project_id", "kind", "idempotency_key", name="uq_generation_jobs_submission"
        ),
        Index(
            "uq_generation_jobs_active_analysis",
            "firm_id",
            "project_id",
            unique=True,
            postgresql_where=text("kind = 'analysis' AND status IN ('queued','running')"),
        ),
        Index("ix_generation_jobs_project_created", "firm_id", "project_id", "created_at"),
    )


class ProjectVersion(ProjectChild, Base):
    __tablename__ = "project_versions"
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    generation_job_id: Mapped[uuid.UUID | None] = mapped_column(unique=True)
    __table_args__ = project_constraints(
        UniqueConstraint("project_id", "version"),
        CheckConstraint("version > 0"),
        ForeignKeyConstraint(
            ["generation_job_id", "project_id", "firm_id"],
            ["generation_jobs.id", "generation_jobs.project_id", "generation_jobs.firm_id"],
        ),
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
