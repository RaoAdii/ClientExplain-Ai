"""Selected-document embedding, scoped retrieval, validated atomic publication."""

import re
from collections import Counter

from app.core.auth import Principal
from app.core.config import EMBEDDING_MODEL, settings
from app.integrations.openai_provider import ProviderInputError, ProviderInvalidResponse
from app.models.entities import Document, DocumentChunk
from app.repositories.analysis import lock_evidence, publish_analysis
from app.schemas.analysis import (
    AnalysisRequest,
    EmbeddingBatch,
    EvidenceChunk,
    LegalProcess,
)
from app.schemas.auth import Role
from app.schemas.sources import RetrievalFilters
from app.services.analysis import analysis_checkpoint, work_signature
from app.services.citations import validate_citations
from app.services.jobs import transition_job
from app.services.rag import retrieve_evidence, validate_query_vector
from sqlalchemy import update

from worker.tasks import _transaction

MAX_DOCUMENT_EVIDENCE_CHUNKS = 50
MAX_DOCUMENT_EVIDENCE_CHARS = 200_000
TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


def _checkpoint(db, job_id, providers, signature=None, *, lock=False):
    work = analysis_checkpoint(db, job_id, providers.worker_task_id, lock=lock)
    if work is not None and signature is not None and work_signature(work) != signature:
        raise ValueError("Selected documents or the analysis request changed during processing.")
    return work


def select_document_evidence(
    request: AnalysisRequest,
    documents: list[Document],
    chunks: list[DocumentChunk],
) -> tuple[list[EvidenceChunk], int]:
    """Include all selected passages when bounded, otherwise rank within strict limits."""
    if not request.selected_document_ids:
        return [], 0

    documents_by_id = {document.id: document for document in documents}
    chunks_by_document = {document_id: [] for document_id in request.selected_document_ids}
    for chunk in chunks:
        if chunk.document_id not in chunks_by_document:
            raise ValueError("Selected document passages do not match the analysis request.")
        if not chunk.content.strip() or len(chunk.content) > 12_000:
            raise ProviderInputError()
        chunks_by_document[chunk.document_id].append(chunk)
    if set(documents_by_id) != set(request.selected_document_ids) or any(
        not document_chunks for document_chunks in chunks_by_document.values()
    ):
        raise ValueError("Every selected document must have readable parsed passages.")

    ordered_chunks = [
        chunk
        for document_id in request.selected_document_ids
        for chunk in sorted(chunks_by_document[document_id], key=lambda item: item.position)
    ]
    evidence_by_chunk = {}
    for chunk in ordered_chunks:
        document = documents_by_id[chunk.document_id]
        evidence_by_chunk[chunk.id] = EvidenceChunk(
            chunk_id=str(chunk.id),
            content=chunk.content,
            source_type="user_document",
            verification_status="unverified",
            document_id=document.id,
            source_filename=chunk.source_filename or document.filename,
            page_number=chunk.page_number,
            heading=chunk.heading,
        )

    total_chars = sum(len(chunk.content) for chunk in ordered_chunks)
    if (
        len(ordered_chunks) <= MAX_DOCUMENT_EVIDENCE_CHUNKS
        and total_chars <= MAX_DOCUMENT_EVIDENCE_CHARS
    ):
        return [evidence_by_chunk[chunk.id] for chunk in ordered_chunks], 0

    query = " ".join(
        (request.process_text, request.jurisdiction, request.legal_area, request.applicability_date.isoformat() if request.applicability_date else "")
    )
    query_terms = Counter(TOKEN_PATTERN.findall(query.casefold()))

    def relevance_text(content):
        counts = Counter(TOKEN_PATTERN.findall(content.casefold()))
        return sum(
            min(count, query_terms[term])
            for term, count in counts.items()
            if term in query_terms
        )

    def relevance(chunk):
        return relevance_text(chunk.content)

    def best_excerpt(content, max_chars):
        if len(content) <= max_chars:
            return content
        last_start = len(content) - max_chars
        starts = {0, last_start}
        for match in TOKEN_PATTERN.finditer(content):
            if match.group().casefold() in query_terms:
                starts.add(max(0, min(match.start() - max_chars // 2, last_start)))
        start = max(
            starts,
            key=lambda candidate: (
                relevance_text(content[candidate : candidate + max_chars]),
                -candidate,
            ),
        )
        return content[start : start + max_chars]

    selected = {}
    selected_content = {}
    truncated = set()
    selected_chars = 0
    per_document_chars = MAX_DOCUMENT_EVIDENCE_CHARS // len(request.selected_document_ids)
    for document_id in request.selected_document_ids:
        best = min(
            chunks_by_document[document_id],
            key=lambda chunk: (-relevance(chunk), chunk.position),
        )
        selected[best.id] = best
        excerpt = best_excerpt(best.content, per_document_chars)
        selected_content[best.id] = excerpt
        selected_chars += len(excerpt)
        if len(excerpt) < len(best.content):
            truncated.add(best.id)
    if len(selected) > MAX_DOCUMENT_EVIDENCE_CHUNKS or selected_chars > MAX_DOCUMENT_EVIDENCE_CHARS:
        raise ProviderInputError()

    remaining = sorted(
        (chunk for chunk in ordered_chunks if chunk.id not in selected),
        key=lambda chunk: (-relevance(chunk), str(chunk.document_id), chunk.position),
    )
    for chunk in remaining:
        if (
            len(selected) >= MAX_DOCUMENT_EVIDENCE_CHUNKS
            or selected_chars + len(chunk.content) > MAX_DOCUMENT_EVIDENCE_CHARS
        ):
            continue
        selected[chunk.id] = chunk
        selected_content[chunk.id] = chunk.content
        selected_chars += len(chunk.content)

    chosen = sorted(
        selected.values(), key=lambda chunk: (str(chunk.document_id), chunk.position)
    )
    evidence = [
        evidence_by_chunk[chunk.id].model_copy(
            update={"content": selected_content[chunk.id]}
        )
        for chunk in chosen
    ]
    return evidence, len(ordered_chunks) - len(chosen) + len(truncated)


def _embed(provider, texts):
    batch = EmbeddingBatch.model_validate(provider.embed(texts).model_dump())
    if len(batch.vectors) != len(texts):
        raise ProviderInvalidResponse()
    for vector in batch.vectors:
        validate_query_vector(vector)
    return batch


def _query_embedding(provider, text):
    # The analysis prompt allows 20k characters while each embedding input allows
    # 12k. Preserve every nonblank segment and pool by length for cosine search;
    # the analysis provider still receives the complete, original request.
    parts = [text[start : start + 12000] for start in range(0, len(text), 12000)]
    parts = [part for part in parts if part.strip()]
    vectors = _embed(provider, parts).vectors
    total = sum(map(len, parts))
    vector = [
        sum(values[index] * len(part) / total for part, values in zip(parts, vectors, strict=True))
        for index in range(1536)
    ]
    return validate_query_vector(vector)


def run_analysis_job(job_id, providers) -> None:
    with _transaction() as db:
        work = _checkpoint(db, job_id, providers)
        if work is None:
            return
        job, project, request, _, chunks = work
        signature = work_signature(work)
        principal = Principal(project.owner_id, project.firm_id, Role.OWNER)
        pending = [
            (chunk.id, chunk.content)
            for chunk in chunks
            if providers.embedding is not None
            if (
                chunk.embedding is None
                or chunk.embedding_model
                != getattr(providers.embedding, "model_name", EMBEDDING_MODEL)
                or chunk.embedding_provider
                != getattr(providers.embedding, "provider_name", "openai")
            )
        ]
    # Keep batches inside the provider's count and character limits. Existing
    # verified embeddings are reused, including after transient job retries.
    batches, batch, chars = [], [], 0
    for item in pending:
        if batch and (len(batch) == 128 or chars + len(item[1]) > 200000):
            batches.append(batch)
            batch, chars = [], 0
        batch.append(item)
        chars += len(item[1])
    if batch:
        batches.append(batch)
    for batch in batches:
        with _transaction() as db:
            if _checkpoint(db, job_id, providers, signature) is None:
                return
        if providers.embedding is None:
            raise ProviderInvalidResponse()
        result = _embed(providers.embedding, [content for _, content in batch])
        with _transaction() as db:
            if _checkpoint(db, job_id, providers, signature, lock=True) is None:
                return
            for (chunk_id, content), vector in zip(batch, result.vectors, strict=True):
                db.execute(
                    update(DocumentChunk)
                    .where(
                        DocumentChunk.id == chunk_id,
                        DocumentChunk.firm_id == principal.firm_id,
                        DocumentChunk.content == content,
                    )
                    .values(
                        embedding=vector,
                        embedding_model=result.model,
                        embedding_provider=result.provider,
                    )
                )
    with _transaction() as db:
        if _checkpoint(db, job_id, providers, signature) is None:
            return
    query_vector = (
        _query_embedding(providers.embedding, request.process_text)
        if request.selected_document_ids and providers.embedding is not None
        else None
    )
    filters = RetrievalFilters(
        selected_document_ids=request.selected_document_ids,
        jurisdiction=request.jurisdiction,
        applicability_date=request.applicability_date,
    )
    with _transaction() as db:
        work = _checkpoint(db, job_id, providers, signature, lock=True)
        if work is None:
            return
        job, project, _, documents, current_chunks = work
        if not request.selected_document_ids:
            evidence, omitted_chunks = [], 0
        elif providers.embedding is None:
            evidence, omitted_chunks = select_document_evidence(request, documents, current_chunks)
        else:
            evidence = retrieve_evidence(
                db,
                principal,
                project.id,
                query_vector,
                filters,
                settings.retrieval_limit,
                settings.retrieval_threshold,
            )
            omitted_chunks = 0
        if job.progress < 50:
            transition_job(db, job.id, "running", "running", stage="analyzing", progress=50)
        project.processing_status = "running"
    process = providers.analysis.analyze(request, evidence)
    process = LegalProcess.model_validate(
        process.model_dump(),
        context={
            "jurisdiction": request.jurisdiction,
            "language": request.language,
            "evidence": {chunk.chunk_id: chunk.content for chunk in evidence},
            "require_complete_workflow": (
                providers.analysis.provider_name == "groq" and bool(request.selected_document_ids)
            ),
        },
    )
    if omitted_chunks:
        process = process.model_copy(
            update={
                "limitations": list(
                    dict.fromkeys(
                        [
                            *process.limitations,
                            f"{omitted_chunks} selected passage(s) or passage portion(s) were "
                            "omitted because of provider context limits. Review the full documents "
                            "before relying on this analysis.",
                        ]
                    )
                )
            }
        )
    if not validate_citations(process, {chunk.chunk_id: chunk for chunk in evidence}).valid:
        raise ProviderInvalidResponse()
    with _transaction() as db:
        work = _checkpoint(db, job_id, providers, signature, lock=True)
        if work is None:
            return
        job, project, _, documents, current_chunks = work
        lock_evidence(db, principal.firm_id, evidence)
        if not request.selected_document_ids:
            current, current_omitted_chunks = [], 0
        elif providers.embedding is None:
            current, current_omitted_chunks = select_document_evidence(
                request, documents, current_chunks
            )
        else:
            current = retrieve_evidence(
                db,
                principal,
                project.id,
                query_vector,
                filters,
                settings.retrieval_limit,
                settings.retrieval_threshold,
            )
            current_omitted_chunks = 0
        current_by_id = {chunk.chunk_id: chunk for chunk in current}
        if (
            current_omitted_chunks != omitted_chunks
            or len(current_by_id) != len(evidence)
            or any(current_by_id.get(chunk.chunk_id) != chunk for chunk in evidence)
        ):
            raise ValueError(
                "Retrieved evidence changed during processing. No result was published."
            )
        publish_analysis(db, job, project, process, evidence)
