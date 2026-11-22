"""Scope both halves of vector retrieval before ranking or limiting."""

from app.core.config import EMBEDDING_MODEL
from app.models.entities import Document, DocumentChunk, LegalSource, Project, SourceChunk
from sqlalchemy import String, and_, cast, literal, or_, select, union_all


def evidence_query(firm_id, project_id, vector, filters, threshold):
    selected = filters.selected_document_ids
    document_distance = DocumentChunk.embedding.cosine_distance(vector)
    document_query = (
        select(
            cast(DocumentChunk.id, String).label("chunk_id"),
            DocumentChunk.content,
            literal("user_document").label("source_type"),
            literal("unverified").label("verification_status"),
            Document.id.label("document_id"),
            literal(None, type_=LegalSource.id.type).label("source_id"),
            Document.filename.label("source_filename"),
            DocumentChunk.page_number,
            DocumentChunk.heading,
            document_distance.label("distance"),
        )
        .join(
            Document,
            and_(
                Document.id == DocumentChunk.document_id, Document.firm_id == DocumentChunk.firm_id
            ),
        )
        .join(Project, and_(Project.id == Document.project_id, Project.firm_id == Document.firm_id))
        .where(
            DocumentChunk.firm_id == firm_id,
            Document.firm_id == firm_id,
            Document.project_id == project_id,
            Document.id.in_(selected),
            Document.deleted_at.is_(None),
            Document.status == "completed",
            Document.ocr_required.is_(False),
            DocumentChunk.embedding.is_not(None),
            DocumentChunk.embedding_model == EMBEDDING_MODEL,
            DocumentChunk.embedding_provider == "openai",
            1 - document_distance >= threshold,
        )
    )
    if filters.jurisdiction:
        document_query = document_query.where(Project.jurisdiction == filters.jurisdiction)
    if filters.source_types and "user_document" not in filters.source_types:
        document_query = document_query.where(literal(False))

    linked_document = (
        select(Document.id)
        .where(
            Document.id == LegalSource.document_id,
            Document.project_id == project_id,
            Document.firm_id == firm_id,
            Document.id.in_(selected),
            Document.deleted_at.is_(None),
            Document.status == "completed",
            Document.ocr_required.is_(False),
        )
        .exists()
    )
    source_distance = SourceChunk.embedding.cosine_distance(vector)
    source_query = (
        select(
            cast(SourceChunk.id, String).label("chunk_id"),
            SourceChunk.content,
            LegalSource.source_type,
            LegalSource.verification_status,
            LegalSource.document_id,
            LegalSource.id.label("source_id"),
            literal(None, type_=String).label("source_filename"),
            SourceChunk.page_number,
            SourceChunk.heading,
            source_distance.label("distance"),
        )
        .join(
            LegalSource,
            and_(
                LegalSource.id == SourceChunk.source_id, LegalSource.firm_id == SourceChunk.firm_id
            ),
        )
        .where(
            SourceChunk.firm_id == firm_id,
            LegalSource.firm_id == firm_id,
            or_(
                LegalSource.project_id == project_id,
                and_(
                    LegalSource.project_id.is_(None), LegalSource.verification_status == "verified"
                ),
            ),
            or_(LegalSource.document_id.is_(None), linked_document),
            LegalSource.source_type.in_(
                filters.source_types
                or ["legislation", "judgment", "government_publication", "secondary"]
            ),
            SourceChunk.embedding.is_not(None),
            SourceChunk.embedding_model == EMBEDDING_MODEL,
            SourceChunk.embedding_provider == "openai",
            1 - source_distance >= threshold,
        )
    )
    if filters.jurisdiction:
        source_query = source_query.where(LegalSource.jurisdiction == filters.jurisdiction)
    if filters.applicability_date:
        source_query = source_query.where(
            or_(
                LegalSource.effective_date.is_(None),
                LegalSource.effective_date <= filters.applicability_date,
            ),
            or_(
                LegalSource.repeal_date.is_(None),
                LegalSource.repeal_date > filters.applicability_date,
            ),
        )
    combined = union_all(document_query, source_query).subquery()
    return select(combined).order_by(combined.c.distance, combined.c.chunk_id)
