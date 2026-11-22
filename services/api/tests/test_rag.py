"""Real pgvector retrieval and quotation/provenance validation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.core.auth import DEV_FIRM, DEV_USER, Principal
from app.db.session import SessionLocal
from app.models.entities import Document, DocumentChunk, Firm, LegalSource, Project, SourceChunk
from app.schemas.analysis import EvidenceChunk, LegalProcess
from app.schemas.auth import Role
from app.schemas.sources import RetrievalFilters
from app.services.citations import validate_citations
from app.services.rag import retrieve_evidence
from fastapi import HTTPException
from sqlalchemy import delete
from test_analysis_provider import backed_process, process

OWNER = Principal(DEV_USER, DEV_FIRM, Role.OWNER)
VECTOR = [1.0] + [0.0] * 1535


def document(db, project_id, *, firm_id=DEV_FIRM, status="completed", vector=VECTOR):
    item = Document(
        project_id=project_id,
        firm_id=firm_id,
        filename="brief.txt",
        storage_key=str(uuid4()),
        media_type="text/plain",
        byte_size=10,
        status=status,
        sha256=uuid4().hex * 2,
    )
    db.add(item)
    db.flush()
    chunk = DocumentChunk(
        document_id=item.id,
        firm_id=firm_id,
        position=0,
        content="File the application with the registry.",
        source_filename="brief.txt",
        page_number=1,
        embedding=vector,
        embedding_model="text-embedding-3-small" if vector is not None else None,
        embedding_provider="openai" if vector is not None else None,
    )
    db.add(chunk)
    db.flush()
    return item, chunk


def source(
    db,
    *,
    project_id=None,
    firm_id=DEV_FIRM,
    jurisdiction="India",
    verified=True,
    source_type="legislation",
    vector=VECTOR,
    document_id=None,
):
    item = LegalSource(
        firm_id=firm_id,
        project_id=project_id,
        document_id=document_id,
        title="Filing Act",
        url="https://example.test/act",
        jurisdiction=jurisdiction,
        source_type=source_type,
        verification_status="verified" if verified else "unverified",
    )
    db.add(item)
    db.flush()
    chunk = SourceChunk(
        firm_id=firm_id,
        source_id=item.id,
        position=0,
        content="File the application under section 1.",
        embedding=vector,
        embedding_model="text-embedding-3-small",
        embedding_provider="openai",
    )
    db.add(chunk)
    db.flush()
    return item, chunk


@pytest.fixture
def corpus():
    with SessionLocal.begin() as db:
        foreign = Firm(name="Other firm")
        db.add(foreign)
        db.flush()
        projects = [
            Project(firm_id=firm, created_by=DEV_USER, name="Retrieval")
            for firm in (DEV_FIRM, DEV_FIRM, foreign.id)
        ]
        db.add_all(projects)
        db.flush()
        ids = [p.id for p in projects]
        foreign_id = foreign.id
    yield ids
    with SessionLocal.begin() as db:
        db.execute(delete(Project).where(Project.id.in_(ids)))
        db.execute(
            delete(LegalSource).where(
                LegalSource.firm_id == DEV_FIRM, LegalSource.url == "https://example.test/act"
            )
        )
        db.execute(delete(Firm).where(Firm.id == foreign_id))


def test_retrieval_enforces_firm_project_selection_and_curated_scope(corpus):
    own, other, foreign = corpus
    with SessionLocal.begin() as db:
        foreign_firm = db.get(Project, foreign).firm_id
        selected, chunk = document(db, own)
        document(db, own)
        document(db, other)
        document(db, foreign, firm_id=foreign_firm)
        _, project_chunk = source(db, project_id=own, verified=False)
        _, verified_chunk = source(db)
        source(db, verified=False)
        source(db, project_id=other)
        source(db, firm_id=foreign_firm)
        result = retrieve_evidence(
            db, OWNER, own, VECTOR, RetrievalFilters(selected_document_ids=[selected.id]), 50, 0.1
        )
        assert {r.chunk_id for r in result} == {
            str(chunk.id),
            str(project_chunk.id),
            str(verified_chunk.id),
        }
        user = next(r for r in result if r.document_id == selected.id)
        assert (user.content, user.verification_status, user.source_filename, user.page_number) == (
            "File the application with the registry.",
            "unverified",
            "brief.txt",
            1,
        )
        with pytest.raises(HTTPException) as denied:
            retrieve_evidence(db, OWNER, foreign, VECTOR, RetrievalFilters(), 5, 0.1)
        assert denied.value.status_code == 404


def test_retrieval_filters_before_global_threshold_order_and_limit(corpus):
    own, _, _ = corpus
    with SessionLocal.begin() as db:
        source(db, jurisdiction="England")
        source(db, source_type="secondary")
        _, worse = source(db, vector=[0.8, 0.6] + [0.0] * 1534)
        _, best = source(db)
        source(db, vector=[0.0, 1.0] + [0.0] * 1534)
        filters = RetrievalFilters(jurisdiction="India", source_types=["legislation"])
        result = retrieve_evidence(db, OWNER, own, VECTOR, filters, 1, 0.75)
        assert [r.chunk_id for r in result] == [str(best.id)]
        result = retrieve_evidence(db, OWNER, own, VECTOR, filters, 10, 0.75)
        assert [r.chunk_id for r in result] == [str(best.id), str(worse.id)]


def test_retrieval_excludes_deleted_failed_ocr_and_linked_unselected_documents(corpus):
    own, _, _ = corpus
    with SessionLocal.begin() as db:
        failed, _ = document(db, own, status="failed")
        ocr, _ = document(db, own)
        ocr.ocr_required = True
        deleted, _ = document(db, own)
        deleted.deleted_at = datetime.now(UTC)
        unselected, _ = document(db, own)
        source(db, project_id=own, document_id=unselected.id)
        db.flush()
        assert (
            retrieve_evidence(
                db,
                OWNER,
                own,
                VECTOR,
                RetrievalFilters(selected_document_ids=[failed.id, ocr.id, deleted.id]),
                50,
                0,
            )
            == []
        )


@pytest.mark.parametrize(
    "vector", [[1.0] * 1535, [1.0] * 1537, [float("nan")] * 1536, [0.0] * 1536]
)
def test_query_requires_exact_finite_nonzero_1536_vector(corpus, vector):
    with SessionLocal() as db, pytest.raises(ValueError):
        retrieve_evidence(db, OWNER, corpus[0], vector, RetrievalFilters(), 5, 0.5)


@pytest.mark.parametrize(
    "verification,source_type,status",
    [
        ("unverified", "user_document", "unverified"),
        ("unverified", "legislation", "unverified"),
        ("verified", "legislation", "supported"),
    ],
)
def test_citation_labels_describe_association_not_legal_proof(verification, source_type, status):
    evidence = EvidenceChunk(
        chunk_id="chunk-1",
        content="File the application with the registry.",
        verification_status=verification,
        source_type=source_type,
    )
    result = validate_citations(
        LegalProcess.model_validate(backed_process()), {"chunk-1": evidence}
    )
    assert result.valid
    assert result.stages[0].verification_status == status
    assert result.stages[0].citations[0].validation_status == status
    assert "legal correctness" in result.limitations[0]


@pytest.mark.parametrize(
    "evidence",
    [
        {},
        {
            "chunk-1": EvidenceChunk(
                chunk_id="chunk-1", content="Different text: file the application."
            )
        },
    ],
)
def test_unknown_ids_and_nonexact_quotes_are_unsupported(evidence):
    result = validate_citations(LegalProcess.model_validate(backed_process()), evidence)
    assert not result.valid
    assert result.stages[0].verification_status == "unsupported"


def test_general_without_citations_is_unverified_with_no_evidence():
    result = validate_citations(LegalProcess.model_validate(process()), {})
    assert result.valid
    assert result.stages[0].verification_status == "unverified"
    assert result.stages[0].citations == []


def test_citation_validation_rejects_bypassed_missing_citations():
    output = LegalProcess.model_validate(backed_process())
    output.stages[0].claims = []
    result = validate_citations(output, {})
    assert not result.valid
    assert result.stages[0].verification_status == "unsupported"
