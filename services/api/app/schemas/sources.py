"""Retrieval scope and legal-source provenance; verification is explicit metadata."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from app.schemas.analysis import AnalysisModel
from pydantic import ConfigDict, Field

SourceType = Literal[
    "user_document", "legislation", "judgment", "government_publication", "secondary"
]


class RetrievalFilters(AnalysisModel):
    selected_document_ids: list[UUID] = Field(default_factory=list, max_length=50)
    jurisdiction: str | None = Field(default=None, min_length=1, max_length=120)
    source_types: list[SourceType] = Field(default_factory=list, max_length=5)
    applicability_date: date | None = None


class LegalSourceRead(AnalysisModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    title: str
    url: str
    jurisdiction: str
    source_type: str
    citation_reference: str | None
    effective_date: date | None
    repeal_date: date | None
    verification_status: Literal["verified", "unverified"]
    retrieved_at: datetime
    last_verified_at: datetime | None
    project_id: UUID | None
    document_id: UUID | None
