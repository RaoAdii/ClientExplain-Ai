"""Public workflow read models; private storage and job requests stay server-side."""

from datetime import date, datetime
from decimal import Decimal
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


class ValidationErrorField(BaseModel):
    field: str
    message: str


class ValidationErrorDetail(BaseModel):
    message: str
    fields: list[ValidationErrorField]


class ValidationErrorRead(BaseModel):
    error: ValidationErrorDetail


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
    inputs: list[str]
    actions: list[str]
    expected_outputs: list[str]
    decision_points: list[str]
    source_backed: bool
    general_explanation: bool
    limitations: list[str]
    verification_status: Literal["supported", "unverified", "unsupported"]
    created_at: datetime
    updated_at: datetime


class ExtractedFactRead(BaseModel):
    statement: str
    evidence_chunk_id: str
    excerpt: str
    source_filename: str | None = None
    page_number: int | None = None


class FinancialFactRead(BaseModel):
    kind: Literal["deposit", "proposed_deduction"]
    label: str
    amount: Decimal
    currency: str
    evidence_chunk_id: str
    excerpt: str
    source_filename: str | None = None
    page_number: int | None = None


class InformationGapRead(BaseModel):
    category: Literal[
        "missing_document", "missing_information", "unverified", "not_applicable"
    ]
    description: str


class PotentialBalanceRead(BaseModel):
    currency: str
    deposit_total: Decimal
    proposed_deductions_total: Decimal
    potential_balance: Decimal


class ProcessRead(BaseModel):
    process_name: str | None = None
    jurisdiction: str | None = None
    legal_area: str | None = None
    summary: str | None = None
    applicability_date: date | None = None
    audience: str | None = None
    complexity: str | None = None
    language: str | None = None
    main_objective: str | None = None
    parties_involved: list[str] = Field(default_factory=list)
    facts: list[ExtractedFactRead] = Field(default_factory=list)
    financial_facts: list[FinancialFactRead] = Field(default_factory=list)
    potential_balances: list[PotentialBalanceRead] = Field(default_factory=list)
    information_gaps: list[InformationGapRead] = Field(default_factory=list)
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
