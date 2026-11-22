"""Selected-document embedding, scoped retrieval, validated atomic publication."""

from app.core.auth import Principal
from app.core.config import EMBEDDING_MODEL, settings
from app.integrations.openai_provider import ProviderInvalidResponse
from app.models.entities import DocumentChunk
from app.repositories.analysis import lock_evidence, publish_analysis
from app.schemas.analysis import EmbeddingBatch, LegalProcess
from app.schemas.auth import Role
from app.schemas.sources import RetrievalFilters
from app.services.analysis import analysis_checkpoint, work_signature
from app.services.citations import validate_citations
from app.services.jobs import transition_job
from app.services.rag import retrieve_evidence, validate_query_vector
from sqlalchemy import update
from worker.tasks import _transaction


def _checkpoint(db, job_id, providers, signature=None, *, lock=False):
    work = analysis_checkpoint(db, job_id, providers.worker_task_id, lock=lock)
    if work is not None and signature is not None and work_signature(work) != signature:
        raise ValueError("Selected documents or the analysis request changed during processing.")
    return work


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
            if (
                chunk.embedding is None
                or chunk.embedding_model != EMBEDDING_MODEL
                or chunk.embedding_provider != "openai"
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
    query_vector = _query_embedding(providers.embedding, request.process_text)
    filters = RetrievalFilters(
        selected_document_ids=request.selected_document_ids,
        jurisdiction=request.jurisdiction,
        applicability_date=request.applicability_date,
    )
    with _transaction() as db:
        work = _checkpoint(db, job_id, providers, signature, lock=True)
        if work is None:
            return
        job, project, *_ = work
        evidence = (
            retrieve_evidence(
                db,
                principal,
                project.id,
                query_vector,
                filters,
                settings.retrieval_limit,
                settings.retrieval_threshold,
            )
            if request.selected_document_ids
            else []
        )
        if job.progress < 50:
            transition_job(db, job.id, "running", "running", stage="analyzing", progress=50)
        project.processing_status = "running"
    process = providers.analysis.analyze(request, evidence)
    process = LegalProcess.model_validate(
        process.model_dump(),
        context={
            "jurisdiction": request.jurisdiction,
            "evidence": {chunk.chunk_id: chunk.content for chunk in evidence},
        },
    )
    if not validate_citations(process, {chunk.chunk_id: chunk for chunk in evidence}).valid:
        raise ProviderInvalidResponse()
    with _transaction() as db:
        work = _checkpoint(db, job_id, providers, signature, lock=True)
        if work is None:
            return
        job, project, *_ = work
        lock_evidence(db, principal.firm_id, evidence)
        current = (
            retrieve_evidence(
                db,
                principal,
                project.id,
                query_vector,
                filters,
                settings.retrieval_limit,
                settings.retrieval_threshold,
            )
            if request.selected_document_ids
            else []
        )
        current_by_id = {chunk.chunk_id: chunk for chunk in current}
        if any(current_by_id.get(chunk.chunk_id) != chunk for chunk in evidence):
            raise ValueError(
                "Retrieved evidence changed during processing. No result was published."
            )
        publish_analysis(db, job, project, process, evidence)
