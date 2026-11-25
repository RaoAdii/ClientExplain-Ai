"""TDD suite for profile update, document retry, and local Ollama AI provider."""

import json
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
import pytest
from app.core.auth import Principal, get_principal
from app.core.config import Settings, settings
from app.db.session import SessionLocal
from app.integrations.ollama_provider import (
    OllamaEmbeddingProvider,
    OllamaLegalAnalysisProvider,
)
from app.integrations.openai_provider import ProviderInvalidResponse, ProviderTransportError
from app.main import app
from app.models.entities import Document, Firm, FirmMember, ProcessStage, Profile, ProjectReview
from app.schemas.analysis import AnalysisRequest, EvidenceChunk
from app.schemas.auth import Role
from app.services.documents import tenant_context
from fastapi.testclient import TestClient
from sqlalchemy import delete


@pytest.fixture
def workspace():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {settings.dev_auth_token}"}
        project = client.post(
            "/api/v1/projects", headers=headers, json={"name": "Local completion test"}
        ).json()
        try:
            yield client, headers, project
        finally:
            app.dependency_overrides.pop(get_principal, None)
            client.delete(f"/api/v1/projects/{project['id']}", headers=headers)


def test_profile_update_and_validation(workspace):
    client, headers, _ = workspace
    original = client.get("/api/v1/auth/me", headers=headers).json()["profile"]["display_name"]
    try:
        res = client.patch("/api/v1/auth/me", headers=headers, json={"display_name": "Counsel A"})
        assert res.status_code == 200, res.text
        assert res.json()["profile"]["display_name"] == "Counsel A"
        assert (
            client.get("/api/v1/auth/me", headers=headers).json()["profile"]["display_name"]
            == "Counsel A"
        )
        assert (
            client.patch(
                "/api/v1/auth/me", headers=headers, json={"display_name": "   "}
            ).status_code
            == 422
        )
    finally:
        client.patch("/api/v1/auth/me", headers=headers, json={"display_name": original})


def test_document_retry_for_failed_document_and_conflict_for_completed(workspace):
    client, headers, project = workspace
    me = client.get("/api/v1/auth/me", headers=headers).json()
    firm_id = me["firm"]["id"]
    failed_id, completed_id = uuid4(), uuid4()
    with SessionLocal.begin() as db:
        principal = Principal(me["profile"]["id"], firm_id, Role.OWNER)
        tenant_context(db, principal)
        db.add(
            Document(
                id=failed_id,
                firm_id=firm_id,
                project_id=project["id"],
                filename="broken.pdf",
                storage_key=f"{firm_id}/{project['id']}/{failed_id}.pdf",
                media_type="application/pdf",
                byte_size=128,
                sha256="a" * 64,
                status="failed",
                parsing_error="Transient parse error",
            )
        )
        db.add(
            Document(
                id=completed_id,
                firm_id=firm_id,
                project_id=project["id"],
                filename="done.txt",
                storage_key=f"{firm_id}/{project['id']}/{completed_id}.txt",
                media_type="text/plain",
                byte_size=64,
                sha256="b" * 64,
                status="completed",
            )
        )

    assert (
        client.post(f"/api/v1/documents/{completed_id}/retry", headers=headers).status_code == 409
    )
    with patch("app.services.documents.dispatch_parse") as mocked:
        retried = client.post(f"/api/v1/documents/{failed_id}/retry", headers=headers)
    assert retried.status_code == 202, retried.text
    body = retried.json()
    assert body["document"]["status"] == "queued"
    assert body["job"]["kind"] == "parse"
    mocked.assert_called_once()

    # Cross-tenant denial
    other_firm, other_user = uuid4(), uuid4()
    try:
        with SessionLocal.begin() as db:
            db.add(Firm(id=other_firm, name="Other Firm"))
            db.add(Profile(id=other_user, display_name="Other"))
            db.flush()
            db.add(FirmMember(firm_id=other_firm, profile_id=other_user, role="owner"))
        app.dependency_overrides[get_principal] = lambda: Principal(
            other_user, other_firm, Role.OWNER
        )
        assert (
            client.post(f"/api/v1/documents/{failed_id}/retry", headers=headers).status_code == 404
        )
    finally:
        app.dependency_overrides.pop(get_principal, None)
        with SessionLocal.begin() as db:
            db.execute(delete(FirmMember).where(FirmMember.firm_id == other_firm))
            db.execute(delete(Profile).where(Profile.id == other_user))
            db.execute(delete(Firm).where(Firm.id == other_firm))


def test_removing_reviewed_stage_preserves_project_review(workspace):
    client, headers, project = workspace
    identity = client.get("/api/v1/auth/me", headers=headers).json()
    principal = Principal(identity["profile"]["id"], identity["firm"]["id"], Role.OWNER)
    project_id = UUID(project["id"])
    with SessionLocal.begin() as db:
        tenant_context(db, principal)
        stage = ProcessStage(
            project_id=project_id,
            firm_id=principal.firm_id,
            position=0,
            title="Review",
            explanation="Review the supplied record.",
        )
        db.add(stage)
        db.flush()
        review = ProjectReview(
            project_id=project_id,
            firm_id=principal.firm_id,
            stage_id=stage.id,
            reviewer_id=principal.user_id,
            reviewer_name="Fixture reviewer",
            decision="comment",
            comment="Review the source.",
            project_version=1,
        )
        db.add(review)
        db.flush()
        review_id, stage_id = review.id, stage.id
        db.execute(delete(ProcessStage).where(ProcessStage.id == stage_id))
    with SessionLocal() as db:
        review = db.get(ProjectReview, review_id)
        assert review is not None
        assert review.stage_id is None
        assert review.project_id == project_id


def test_ai_status_and_ollama_providers():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {settings.dev_auth_token}"}
        status = client.get("/api/v1/ai/status", headers=headers)
        assert status.status_code == 200
        assert status.json()["available"] is False

    cfg = Settings(
        database_url=settings.database_url,
        auth_mode="development",
        dev_auth_token=settings.dev_auth_token,
        ai_provider="ollama",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_analysis_model="qwen3:4b",
        ollama_embedding_model="qwen3-embedding:4b",
    )

    def embed_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        payload = json.loads(request.content)
        assert payload["dimensions"] == 1536
        return httpx.Response(200, json={"embeddings": [[1.0] * 1536]})

    embed_client = httpx.Client(
        transport=httpx.MockTransport(embed_handler), base_url=cfg.ollama_base_url
    )
    batch = OllamaEmbeddingProvider(cfg, client=embed_client).embed(["hello world"])
    assert batch.provider == "ollama"
    assert batch.dimensions == 1536
    assert len(batch.vectors[0]) == 1536

    evidence = [
        EvidenceChunk(
            chunk_id="chunk_1",
            content="File the notice of appeal within 30 days of judgment.",
            source_type="user_document",
            verification_status="unverified",
            source_filename="guide.txt",
            page_number=1,
        )
    ]
    valid_payload = {
        "process_name": "Appeal Filing",
        "jurisdiction": "Test State",
        "legal_area": "Civil",
        "summary": "Overview of filing an appeal.",
        "applicability_date": None,
        "audience": "Client",
        "complexity": "simple",
        "stages": [
            {
                "stage_number": 1,
                "title": "File Notice of Appeal",
                "explanation": "Submit the notice to the clerk.",
                "responsible_party": "Appellant",
                "required_documents": ["Notice of Appeal"],
                "estimated_duration": "30 days",
                "evidence_chunk_ids": ["chunk_1"],
                "claims": [
                    {
                        "claim_text": "Notice must be filed within 30 days.",
                        "source_backed": True,
                        "evidence_chunk_id": "chunk_1",
                        "excerpt": "File the notice of appeal within 30 days of judgment.",
                    }
                ],
                "source_backed": True,
                "general_explanation": False,
                "limitations": ["User-supplied document; verify with counsel."],
            }
        ],
        "missing_information": [],
        "limitations": ["Requires professional review."],
        "review_required": True,
    }

    def chat_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["format"]["properties"]["stages"]["maxItems"] == 50
        return httpx.Response(
            200,
            json={"done": True, "message": {"content": json.dumps(valid_payload)}},
        )

    chat_client = httpx.Client(
        transport=httpx.MockTransport(chat_handler), base_url=cfg.ollama_base_url
    )
    req = AnalysisRequest(
        process_text="How do I appeal?", jurisdiction="Test State", selected_document_ids=[]
    )
    result = OllamaLegalAnalysisProvider(cfg, client=chat_client).analyze(req, evidence)
    assert result.process_name == "Appeal Filing"
    assert result.stages[0].claims[0].evidence_chunk_id == "chunk_1"

    def down_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    down_client = httpx.Client(
        transport=httpx.MockTransport(down_handler), base_url=cfg.ollama_base_url
    )
    with pytest.raises(ProviderTransportError):
        OllamaLegalAnalysisProvider(cfg, client=down_client).analyze(req, evidence)

    def bad_json_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "not json"}})

    bad_client = httpx.Client(
        transport=httpx.MockTransport(bad_json_handler), base_url=cfg.ollama_base_url
    )
    with pytest.raises(ProviderInvalidResponse):
        OllamaLegalAnalysisProvider(cfg, client=bad_client).analyze(req, evidence)
