"""Bounded legal output contracts; citations identify evidence, not legal verification."""

import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]
ClaimText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
ChunkID = Annotated[
    str, StringConstraints(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
]
EvidenceText = Annotated[str, StringConstraints(min_length=1, max_length=12000, pattern=r"\S")]
SourceFilename = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
Jurisdiction = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
TextList = Annotated[list[ClaimText], Field(max_length=30)]
Complexity = Literal["simple", "standard", "detailed"]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


def _quoted_amount(amount: Decimal, excerpt: str) -> bool:
    for token in re.findall(
        r"(?<!\w)(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?(?!\w)", excerpt
    ):
        if Decimal(token.replace(",", "")) == amount:
            return True
    return False


def _currency_is_quoted(currency: str, excerpt: str) -> bool:
    markers = {
        "INR": r"₹|\bINR\b|\bRs\.?\b|\brupees?\b",
        "USD": r"\$|\bUSD\b|\bdollars?\b",
        "GBP": r"£|\bGBP\b|\bpounds?\b",
        "EUR": r"€|\bEUR\b|\beuros?\b",
        "JPY": r"¥|\bJPY\b|\byen\b",
    }
    return bool(re.search(markers.get(currency, rf"\b{currency}\b"), excerpt, re.IGNORECASE))


class AnalysisModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class AnalysisRequest(AnalysisModel):
    process_text: Annotated[str, StringConstraints(min_length=1, max_length=20000, pattern=r"\S")]
    jurisdiction: Jurisdiction
    legal_area: ShortText = "General"
    language: ShortText = "English"
    target_audience: ShortText = "Client"
    complexity: Complexity = "simple"
    applicability_date: date | None = None
    selected_document_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @field_validator("selected_document_ids")
    @classmethod
    def unique_documents(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Selected documents must be unique")
        return value


class EvidenceChunk(AnalysisModel):
    chunk_id: ChunkID
    content: EvidenceText
    source_type: Literal[
        "user_document", "legislation", "judgment", "government_publication", "secondary"
    ] = "user_document"
    verification_status: Literal["verified", "unverified"] = "unverified"
    document_id: UUID | None = None
    source_id: UUID | None = None
    source_filename: SourceFilename | None = None
    page_number: int | None = Field(default=None, ge=1)
    heading: ShortText | None = None

    @model_validator(mode="after")
    def user_documents_are_unverified(self) -> Self:
        if self.source_type == "user_document" and self.verification_status != "unverified":
            raise ValueError("User documents must be unverified")
        return self


class ExtractedFact(AnalysisModel):
    statement: ClaimText
    evidence_chunk_id: ChunkID
    excerpt: ClaimText


class FinancialFact(AnalysisModel):
    kind: Literal["deposit", "proposed_deduction"]
    label: ShortText
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: CurrencyCode
    evidence_chunk_id: ChunkID
    excerpt: ClaimText


class InformationGap(AnalysisModel):
    category: Literal[
        "missing_document", "missing_information", "unverified", "not_applicable"
    ]
    description: ClaimText


class CitationClaim(AnalysisModel):
    claim_text: ClaimText
    source_backed: bool = Field(strict=True)
    evidence_chunk_id: ChunkID | None
    excerpt: ClaimText | None

    @model_validator(mode="after")
    def citation_matches_claim_type(self) -> Self:
        if self.source_backed:
            if self.evidence_chunk_id is None or self.excerpt is None:
                raise ValueError("Source-backed claims require an evidence ID and excerpt")
        elif self.evidence_chunk_id is not None or self.excerpt is not None:
            raise ValueError("General claims cannot carry source citations")
        return self


class ProcessStageOutput(AnalysisModel):
    stage_number: int = Field(ge=1, le=50, strict=True)
    title: ShortText
    explanation: Description
    responsible_party: ShortText | None
    required_documents: TextList
    estimated_duration: ShortText | None
    inputs: TextList = Field(default_factory=list)
    actions: TextList = Field(default_factory=list)
    expected_outputs: TextList = Field(default_factory=list)
    decision_points: TextList = Field(default_factory=list)
    evidence_chunk_ids: list[ChunkID] = Field(max_length=50)
    claims: list[CitationClaim] = Field(max_length=30)
    source_backed: bool = Field(strict=True)
    general_explanation: bool = Field(strict=True)
    limitations: TextList

    @model_validator(mode="after")
    def consistent_claims_and_evidence(self) -> Self:
        cited = {claim.evidence_chunk_id for claim in self.claims if claim.source_backed}
        if len(self.evidence_chunk_ids) != len(set(self.evidence_chunk_ids)):
            raise ValueError("Evidence IDs must be unique")
        if set(self.evidence_chunk_ids) != cited:
            raise ValueError("Stage evidence must match cited claims")
        if self.source_backed != bool(cited) or self.general_explanation == self.source_backed:
            raise ValueError("Stage source-backed and general-explanation flags must match claims")
        return self


class LegalProcess(AnalysisModel):
    process_name: ShortText
    jurisdiction: Jurisdiction
    legal_area: ShortText
    language: ShortText = "English"
    main_objective: ShortText | None = None
    parties_involved: TextList = Field(default_factory=list)
    summary: Description
    applicability_date: date | None
    audience: ShortText
    complexity: Complexity
    stages: list[ProcessStageOutput] = Field(min_length=1, max_length=50)
    facts: list[ExtractedFact] = Field(default_factory=list, max_length=100)
    financial_facts: list[FinancialFact] = Field(default_factory=list, max_length=30)
    information_gaps: list[InformationGap] = Field(default_factory=list, max_length=50)
    missing_information: TextList
    limitations: TextList
    review_required: Literal[True]

    @field_validator("review_required", mode="before")
    @classmethod
    def require_boolean_true(cls, value):
        if value is not True:
            raise ValueError("Professional review is required")
        return value

    @model_validator(mode="after")
    def validate_order_and_grounding(self, info: ValidationInfo) -> Self:
        normalized_titles = [
            re.sub(r"[\W_]+", "", stage.title).casefold() for stage in self.stages
        ]
        if len(normalized_titles) != len(set(normalized_titles)):
            raise ValueError("Stage titles must be unique")
        if [stage.stage_number for stage in self.stages] != list(range(1, len(self.stages) + 1)):
            raise ValueError("Stages must have ordered, unique, contiguous numbers starting at one")
        if info.context is not None:
            if self.jurisdiction != info.context["jurisdiction"]:
                raise ValueError("Output jurisdiction must match the request")
            if self.language != info.context.get("language", self.language):
                raise ValueError("Output language must match the request")
            evidence = info.context["evidence"]
            if info.context.get("require_complete_workflow") and (
                len(self.stages) < 2
                or any(not stage.actions or not stage.expected_outputs for stage in self.stages)
            ):
                raise ValueError("Document analysis requires a complete multi-stage workflow")
            for stage in self.stages:
                if not set(stage.evidence_chunk_ids).issubset(evidence):
                    raise ValueError("Unknown evidence ID")
                for claim in stage.claims:
                    if (
                        claim.source_backed
                        and claim.excerpt not in evidence[claim.evidence_chunk_id]
                    ):
                        raise ValueError("Cited excerpt must occur in the supplied evidence")
            for fact in self.facts:
                if (
                    fact.evidence_chunk_id not in evidence
                    or fact.excerpt not in evidence[fact.evidence_chunk_id]
                ):
                    raise ValueError("Extracted facts require an exact supplied evidence excerpt")
            for fact in self.financial_facts:
                if (
                    fact.evidence_chunk_id not in evidence
                    or fact.excerpt not in evidence[fact.evidence_chunk_id]
                    or not _quoted_amount(fact.amount, fact.excerpt)
                    or not _currency_is_quoted(fact.currency, fact.excerpt)
                ):
                    raise ValueError(
                        "Financial facts require a quoted amount and currency from supplied evidence"
                    )
        return self


FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
EmbeddingVector = Annotated[list[FiniteFloat], Field(min_length=1536, max_length=1536)]


class EmbeddingBatch(AnalysisModel):
    provider: Literal["openai", "ollama", "groq"]
    model: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    dimensions: Literal[1536]
    vectors: list[EmbeddingVector] = Field(min_length=1, max_length=128)
