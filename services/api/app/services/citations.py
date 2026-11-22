"""Exact quotation and provenance association checks, never semantic legal proof."""

from typing import Literal

from app.schemas.analysis import AnalysisModel, LegalProcess
from pydantic import Field, ValidationError

AssociationStatus = Literal["supported", "unverified", "unsupported"]
ASSOCIATION_LIMITATION = "Quotation association does not establish semantic support or legal correctness; professional review is required."


class ValidatedCitation(AnalysisModel):
    evidence_chunk_id: str
    claim_text: str
    excerpt: str
    validation_status: AssociationStatus


class ValidatedStage(AnalysisModel):
    stage_number: int
    verification_status: AssociationStatus
    citations: list[ValidatedCitation] = Field(default_factory=list)


class CitationValidationResult(AnalysisModel):
    valid: bool
    stages: list[ValidatedStage]
    limitations: list[str] = Field(default_factory=lambda: [ASSOCIATION_LIMITATION])


def validate_citations(process, evidence_by_id) -> CitationValidationResult:
    try:
        process = LegalProcess.model_validate(process.model_dump())
    except (ValidationError, AttributeError, TypeError):
        return CitationValidationResult(
            valid=False,
            stages=[
                ValidatedStage(
                    stage_number=getattr(stage, "stage_number", index + 1),
                    verification_status="unsupported",
                )
                for index, stage in enumerate(getattr(process, "stages", []))
            ],
        )
    stages = []
    for stage in process.stages:
        citations = []
        for claim in stage.claims:
            if not claim.source_backed:
                continue
            chunk = evidence_by_id.get(claim.evidence_chunk_id)
            status = "unsupported"
            if (
                chunk is not None
                and chunk.chunk_id == claim.evidence_chunk_id
                and claim.excerpt in chunk.content
            ):
                status = (
                    "supported"
                    if (
                        chunk.source_type != "user_document"
                        and chunk.verification_status == "verified"
                    )
                    else "unverified"
                )
            citations.append(
                ValidatedCitation(
                    evidence_chunk_id=claim.evidence_chunk_id,
                    claim_text=claim.claim_text,
                    excerpt=claim.excerpt,
                    validation_status=status,
                )
            )
        statuses = {citation.validation_status for citation in citations}
        status = (
            "unsupported"
            if "unsupported" in statuses
            else "supported"
            if statuses == {"supported"}
            else "unverified"
        )
        stages.append(
            ValidatedStage(
                stage_number=stage.stage_number, verification_status=status, citations=citations
            )
        )
    return CitationValidationResult(
        valid=all(stage.verification_status != "unsupported" for stage in stages), stages=stages
    )
