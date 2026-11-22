"""Public workflow read models; private storage and job requests stay server-side."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from app.schemas.documents import DocumentRead
from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    message: str
    code: str | None = None
    request_id: str | None = None


class ErrorRead(BaseModel):
    error: ErrorDetail


class DocumentDetail(DocumentRead):
    page_count: int | None
    parsing_error: str | None
    ocr_required: bool
    download_url: str | None = None
    download_url_expires_in: int | None = None


class StageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    position: int
    title: str
    explanation: str
    responsible_party: str | None
    required_documents: list[str]
    estimated_duration: str | None
    source_backed: bool
    general_explanation: bool
    limitations: list[str]
    verification_status: Literal["supported", "unverified", "unsupported"]
    created_at: datetime
    updated_at: datetime


class ProcessRead(BaseModel):
    process_name: str | None = None
    jurisdiction: str | None = None
    legal_area: str | None = None
    summary: str | None = None
    applicability_date: date | None = None
    audience: str | None = None
    complexity: str | None = None
    missing_information: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    review_required: Literal[True] = True
    stages: list[StageRead]


class CitationRead(BaseModel):
    id: UUID
    stage_id: UUID
    project_id: UUID
    document_chunk_id: UUID | None
    source_chunk_id: UUID | None
    claim_text: str
    excerpt: str
    validation_status: Literal["supported", "unverified", "unsupported"]
    source_type: str
    verification_status: Literal["verified", "unverified"]
    source_filename: str | None
    source_title: str | None
    source_url: str | None
    citation_reference: str | None
    page_number: int | None
    heading: str | None
