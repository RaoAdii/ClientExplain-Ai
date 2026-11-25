"""Bounded legal output contracts; citations identify evidence, not legal verification."""

from datetime import date
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
    summary: Description
    applicability_date: date | None
    audience: ShortText
    complexity: Complexity
    stages: list[ProcessStageOutput] = Field(min_length=1, max_length=50)
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
        if [stage.stage_number for stage in self.stages] != list(range(1, len(self.stages) + 1)):
            raise ValueError("Stages must have ordered, unique, contiguous numbers starting at one")
        if info.context is not None:
            if self.jurisdiction != info.context["jurisdiction"]:
                raise ValueError("Output jurisdiction must match the request")
            evidence = info.context["evidence"]
            for stage in self.stages:
                if not set(stage.evidence_chunk_ids).issubset(evidence):
                    raise ValueError("Unknown evidence ID")
                for claim in stage.claims:
                    if (
                        claim.source_backed
                        and claim.excerpt not in evidence[claim.evidence_chunk_id]
                    ):
                        raise ValueError("Cited excerpt must occur in the supplied evidence")
        return self


FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
EmbeddingVector = Annotated[list[FiniteFloat], Field(min_length=1536, max_length=1536)]


class EmbeddingBatch(AnalysisModel):
    provider: Literal["openai", "ollama"]
    model: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    dimensions: Literal[1536]
    vectors: list[EmbeddingVector] = Field(min_length=1, max_length=128)
