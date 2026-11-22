"""Workflow HTTP contracts over real tenant data, Redis and service transactions."""

from datetime import date
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from app.core import rate_limits
from app.core.auth import DEV_FIRM, DEV_USER, Principal, get_principal
from app.core.config import settings
from app.db.session import SessionLocal, redis_client
from app.integrations.storage import LocalPrivateStorage
from app.main import app
from app.models.entities import (
    Document,
    DocumentChunk,
    GenerationJob,
    ProcessStage,
    Profile,
    Project,
    ProjectVersion,
    StageCitation,
)
from app.schemas.auth import Role
from app.services import documents
from celery import Celery
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, select


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    ids = {name: uuid4() for name in ("project", "document", "chunk", "stage", "job")}
    ids["rate_namespace"] = f"clientexplain:test-rate:{uuid4()}"

    class IsolatedRateStore:
        def eval(self, script, numkeys, key, *args):
            return redis_client.eval(script, numkeys, f"{ids['rate_namespace']}:{key}", *args)

    monkeypatch.setattr(rate_limits, "redis_client", IsolatedRateStore())
    storage = LocalPrivateStorage(tmp_path)
    monkeypatch.setattr(documents, "get_storage", lambda: storage)
    # Queue transport alone is replaced: submission must still persist real rows.
    monkeypatch.setattr(Celery, "send_task", lambda *args, **kwargs: None)
    monkeypatch.setattr(settings, "upload_rate_limit", 1000)
    monkeypatch.setattr(settings, "analysis_rate_limit", 1000)
    with SessionLocal.begin() as db:
        db.add(Project(id=ids["project"], firm_id=DEV_FIRM, created_by=DEV_USER, name="API"))
        db.flush()
        db.add(
            Document(
                id=ids["document"],
                project_id=ids["project"],
                firm_id=DEV_FIRM,
                filename="evidence.txt",
                storage_key=f"{DEV_FIRM}/{ids['project']}/private.txt",
                media_type="text/plain",
                byte_size=20,
                sha256="a" * 64,
                status="completed",
                page_count=1,
            )
        )
        db.add(
            GenerationJob(
                id=ids["job"],
                project_id=ids["project"],
                firm_id=DEV_FIRM,
                kind="parse",
                status="completed",
                progress=100,
                request_metadata={"private": "never expose"},
            )
        )
        db.flush()
        db.add(
            DocumentChunk(
                id=ids["chunk"],
                firm_id=DEV_FIRM,
                document_id=ids["document"],
                position=0,
                content="Private evidence passage",
                page_number=1,
                source_filename="evidence.txt",
                heading="Section One",
            )
        )
        db.add(
            ProcessStage(
                id=ids["stage"],
                project_id=ids["project"],
                firm_id=DEV_FIRM,
                position=0,
                title="First",
                explanation="Read the evidence",
                responsible_party="Client",
                required_documents=["Notice"],
                estimated_duration="Unknown",
                source_backed=True,
                general_explanation=False,
                limitations=["Review"],
                verification_status="unverified",
            )
        )
        db.flush()
        db.add(
            StageCitation(
                firm_id=DEV_FIRM,
                stage_id=ids["stage"],
                document_chunk_id=ids["chunk"],
                claim_text="Evidence claim",
                excerpt="Private evidence",
                validation_status="unverified",
            )
        )
        db.add(
            ProjectVersion(
                firm_id=DEV_FIRM,
                project_id=ids["project"],
                version=1,
                snapshot={
                    "process_name": "Notice process",
                    "jurisdiction": "India",
                    "legal_area": "Civil",
                    "summary": "Process summary",
                    "applicability_date": "2026-01-01",
                    "audience": "Client",
                    "complexity": "simple",
                    "missing_information": ["Date"],
                    "limitations": ["Professional review"],
                    "review_required": True,
                    "stages": [],
                },
            )
        )
    storage.put(f"{DEV_FIRM}/{ids['project']}/private.txt", BytesIO(b"Private evidence passage"))
    with TestClient(app, headers={"Authorization": f"Bearer {settings.dev_auth_token}"}) as client:
        yield client, ids, storage
    app.dependency_overrides.clear()
    for key in redis_client.scan_iter(f"{ids['rate_namespace']}:*"):
        redis_client.delete(key)
    with SessionLocal.begin() as db:
        db.execute(delete(Project).where(Project.id == ids["project"]))


def allow_ai(monkeypatch):
    monkeypatch.setattr(settings, "ai_external_processing_allowed", True)
    monkeypatch.setattr(settings, "openai_api_key", SecretStr("offline-test-configuration"))
    monkeypatch.setattr(settings, "openai_analysis_model", "configured-test-model")


def payload(ids):
    return {
        "process_text": "Explain the notice process",
        "jurisdiction": "India",
        "selected_document_ids": [str(ids["document"])],
    }


def test_documents_list_and_detail_do_not_expose_private_paths(workflow):
    client, ids, _ = workflow
    listed = client.get(f"/api/v1/projects/{ids['project']}/documents")
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [str(ids["document"])]
    detail = client.get(f"/api/v1/documents/{ids['document']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["page_count"] == 1
    assert detail.json()["ocr_required"] is False
    assert detail.json()["download_url"] is None
    assert {"storage_key", "firm_id", "metadata"}.isdisjoint(detail.json())
    assert "download_url" not in listed.json()[0]
    assert detail.headers["cache-control"] == "no-store"


def test_document_download_url_is_requested_on_demand_and_short_lived(workflow, monkeypatch):
    client, ids, storage = workflow
    signed = []

    def sign(key, expires_seconds):
        assert key == f"{DEV_FIRM}/{ids['project']}/private.txt"
        assert 1 <= expires_seconds <= 300
        signed.append(expires_seconds)
        return f"https://private.example/object/sign/file?token={len(signed)}"

    monkeypatch.setattr(storage, "signed_url", sign)
    url = f"/api/v1/documents/{ids['document']}"
    assert client.get(url).json()["download_url"] is None
    first = client.get(url, params={"download": "true"})
    second = client.get(url, params={"download": "true"})
    assert first.status_code == second.status_code == 200
    assert first.json()["download_url"] != second.json()["download_url"]
    assert first.json()["download_url_expires_in"] == signed[0]
    with SessionLocal() as db:
        assert "token" not in str(db.get(Document, ids["document"]).document_metadata)


def test_document_deletion_removes_private_bytes_and_published_evidence(workflow):
    client, ids, storage = workflow
    result = client.delete(f"/api/v1/documents/{ids['document']}")
    assert result.status_code == 204, result.text
    assert client.get(f"/api/v1/documents/{ids['document']}").status_code == 404
    assert client.get(f"/api/v1/projects/{ids['project']}/documents").json() == []
    assert not storage._path(f"{DEV_FIRM}/{ids['project']}/private.txt").exists()
    with SessionLocal() as db:
        assert db.get(DocumentChunk, ids["chunk"]) is None
        assert db.get(ProcessStage, ids["stage"]) is None
        assert (
            db.scalar(select(ProjectVersion).where(ProjectVersion.project_id == ids["project"]))
            is None
        )


def test_storage_cleanup_failure_is_hidden_and_deletion_can_be_retried(workflow, monkeypatch):
    client, ids, storage = workflow
    original = storage.delete

    def unavailable(key):
        raise OSError("private-service-key")

    monkeypatch.setattr(storage, "delete", unavailable)
    result = client.delete(f"/api/v1/documents/{ids['document']}")
    assert result.status_code == 503
    assert "private-service-key" not in result.text
    assert client.get(f"/api/v1/documents/{ids['document']}").status_code == 404
    with SessionLocal() as db:
        assert (
            db.get(Document, ids["document"]).document_metadata["storage_cleanup_pending"] is True
        )
    monkeypatch.setattr(storage, "delete", original)
    assert client.delete(f"/api/v1/documents/{ids['document']}").status_code == 204


def test_analysis_returns_committed_job_and_persists_validated_request(workflow, monkeypatch):
    client, ids, _ = workflow
    allow_ai(monkeypatch)

    def dispatch(self, name, *, args, **kwargs):
        assert name == "worker.analyze_project" and len(args) == 1
        with SessionLocal() as db:
            job = db.get(GenerationJob, UUID(args[0]))
            assert (
                job.request_metadata["analysis_request"]["process_text"]
                == "Explain the notice process"
            )
            assert db.get(Project, ids["project"]).processing_status == "queued"

    monkeypatch.setattr(Celery, "send_task", dispatch)
    response = client.post(
        f"/api/v1/projects/{ids['project']}/analyze",
        json=payload(ids),
        headers={"Idempotency-Key": "submission-one"},
    )
    assert response.status_code == 202, response.text
    data = response.json()
    assert data["kind"] == "analysis" and data["status"] == "queued"
    polled = client.get(f"/api/v1/jobs/{data['id']}")
    assert polled.status_code == 200 and polled.json()["id"] == data["id"]
    assert {"request_metadata", "request_hash", "idempotency_key", "firm_id"}.isdisjoint(
        polled.json()
    )
    replay = client.post(
        f"/api/v1/projects/{ids['project']}/analyze",
        json=payload(ids),
        headers={"Idempotency-Key": "submission-one"},
    )
    assert replay.status_code == 202 and replay.json()["id"] == data["id"]
    changed = {**payload(ids), "process_text": "Different brief"}
    assert (
        client.post(
            f"/api/v1/projects/{ids['project']}/analyze",
            json=changed,
            headers={"Idempotency-Key": "submission-one"},
        ).status_code
        == 409
    )
    assert (
        client.post(f"/api/v1/projects/{ids['project']}/analyze", json=payload(ids)).status_code
        == 409
    )


def test_provider_disabled_is_explicit_and_does_not_create_job(workflow, monkeypatch):
    client, ids, _ = workflow
    monkeypatch.setattr(settings, "ai_external_processing_allowed", False)
    response = client.post(f"/api/v1/projects/{ids['project']}/analyze", json=payload(ids))
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "provider_unavailable"
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(GenerationJob).where(
                    GenerationJob.project_id == ids["project"], GenerationJob.kind == "analysis"
                )
            )
            is None
        )


@pytest.mark.parametrize("status,ocr", [("pending", False), ("failed", False), ("completed", True)])
def test_analysis_never_silently_drops_ineligible_selected_documents(
    workflow, monkeypatch, status, ocr
):
    client, ids, _ = workflow
    allow_ai(monkeypatch)
    with SessionLocal.begin() as db:
        document = db.get(Document, ids["document"])
        document.status, document.ocr_required = status, ocr
    response = client.post(f"/api/v1/projects/{ids['project']}/analyze", json=payload(ids))
    assert response.status_code == 409, response.text
    assert "evidence.txt" not in response.text and "private.txt" not in response.text


def test_analysis_dispatch_failure_releases_active_job_and_project(workflow, monkeypatch):
    client, ids, _ = workflow
    allow_ai(monkeypatch)

    def unavailable(*args, **kwargs):
        raise ConnectionError("queue-secret")

    monkeypatch.setattr(Celery, "send_task", unavailable)
    response = client.post(f"/api/v1/projects/{ids['project']}/analyze", json=payload(ids))
    assert response.status_code == 503 and "queue-secret" not in response.text
    with SessionLocal() as db:
        job = db.scalar(
            select(GenerationJob).where(
                GenerationJob.project_id == ids["project"], GenerationJob.kind == "analysis"
            )
        )
        assert job.status == "failed" and job.error_code == "pipeline_unavailable"
        assert db.get(Project, ids["project"]).processing_status == "failed"


def test_stage_list_contains_process_metadata_and_stages_in_order(workflow):
    client, ids, _ = workflow
    with SessionLocal.begin() as db:
        db.add(
            ProcessStage(
                firm_id=DEV_FIRM,
                project_id=ids["project"],
                position=1,
                title="Second",
                explanation="Next step",
            )
        )
    response = client.get(f"/api/v1/projects/{ids['project']}/stages")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["process_name"] == "Notice process" and data["summary"] == "Process summary"
    assert data["jurisdiction"] == "India" and data["legal_area"] == "Civil"
    assert data["applicability_date"] == date(2026, 1, 1).isoformat()
    assert data["missing_information"] == ["Date"] and data["review_required"] is True
    assert [stage["title"] for stage in data["stages"]] == ["First", "Second"]
    stage = client.get(f"/api/v1/stages/{ids['stage']}")
    assert stage.status_code == 200 and stage.json()["responsible_party"] == "Client"
    assert stage.json()["verification_status"] == "unverified"


def test_citation_list_preserves_document_provenance_and_review_labels(workflow):
    client, ids, _ = workflow
    response = client.get(f"/api/v1/projects/{ids['project']}/citations")
    assert response.status_code == 200, response.text
    (citation,) = response.json()
    assert citation["stage_id"] == str(ids["stage"])
    assert citation["excerpt"] == "Private evidence"
    assert citation["source_type"] == "user_document"
    assert citation["verification_status"] == "unverified"
    assert citation["source_filename"] == "evidence.txt"
    assert citation["page_number"] == 1 and citation["heading"] == "Section One"
    assert "storage_key" not in citation


@pytest.mark.parametrize("role", list(Role))
def test_each_role_can_read_but_only_editors_can_upload_analyze_delete(workflow, monkeypatch, role):
    client, ids, _ = workflow
    allow_ai(monkeypatch)
    app.dependency_overrides[get_principal] = lambda: Principal(DEV_USER, DEV_FIRM, role)
    for path in (
        f"projects/{ids['project']}/documents",
        f"documents/{ids['document']}",
        f"projects/{ids['project']}/stages",
        f"stages/{ids['stage']}",
        f"projects/{ids['project']}/citations",
        f"jobs/{ids['job']}",
    ):
        assert client.get(f"/api/v1/{path}").status_code == 200
    expected = 403 if role == Role.REVIEWER else 202
    assert (
        client.post(
            f"/api/v1/projects/{ids['project']}/documents",
            files={"file": ("new.txt", b"new content", "text/plain")},
        ).status_code
        == expected
    )
    assert (
        client.post(f"/api/v1/projects/{ids['project']}/analyze", json=payload(ids)).status_code
        == expected
    )
    assert client.delete(f"/api/v1/documents/{ids['document']}").status_code == (
        403 if role == Role.REVIEWER else 204
    )


def test_cross_firm_resources_and_selected_documents_return_404(workflow, monkeypatch):
    client, ids, _ = workflow
    allow_ai(monkeypatch)
    app.dependency_overrides[get_principal] = lambda: Principal(DEV_USER, uuid4(), Role.OWNER)
    for path in (
        f"projects/{ids['project']}/documents",
        f"documents/{ids['document']}",
        f"projects/{ids['project']}/stages",
        f"stages/{ids['stage']}",
        f"projects/{ids['project']}/citations",
        f"jobs/{ids['job']}",
    ):
        assert client.get(f"/api/v1/{path}").status_code == 404
    assert client.delete(f"/api/v1/documents/{ids['document']}").status_code == 404
    assert (
        client.post(f"/api/v1/projects/{ids['project']}/analyze", json=payload(ids)).status_code
        == 404
    )
    app.dependency_overrides.clear()
    request = {**payload(ids), "selected_document_ids": [str(uuid4())]}
    assert (
        client.post(f"/api/v1/projects/{ids['project']}/analyze", json=request).status_code == 404
    )


def test_unknown_fields_and_invalid_submission_keys_are_rejected(workflow, monkeypatch):
    client, ids, _ = workflow
    allow_ai(monkeypatch)
    url = f"/api/v1/projects/{ids['project']}/analyze"
    for response, field in (
        (client.post(url, json={**payload(ids), "firm_id": str(DEV_FIRM)}), "body.firm_id"),
        (
            client.post(url, json=payload(ids), headers={"Idempotency-Key": "x" * 201}),
            "header.idempotency-key",
        ),
        (
            client.get(f"/api/v1/documents/{ids['document']}", params={"download": "invalid"}),
            "query.download",
        ),
    ):
        assert response.status_code == 422, response.text
        error = response.json()["error"]
        assert error["message"] == "Check the submitted fields."
        assert [item["field"] for item in error["fields"]] == [field]
        assert all(isinstance(item["message"], str) for item in error["fields"])
    rejected = client.post(
        f"/api/v1/projects/{ids['project']}/documents",
        data={"firm_id": str(DEV_FIRM)},
        files={"file": ("new.txt", b"new content", "text/plain")},
    )
    assert rejected.status_code == 422
    assert rejected.json() == {
        "error": {
            "message": "Submit exactly one file and no unknown fields.",
            "request_id": rejected.headers["X-Request-ID"],
        }
    }


@pytest.mark.parametrize("operation", ["upload", "analysis"])
def test_redis_rate_limits_have_headers_and_are_scoped_to_user(workflow, monkeypatch, operation):
    client, ids, _ = workflow
    allow_ai(monkeypatch)
    monkeypatch.setattr(
        settings, f"{'upload' if operation == 'upload' else 'analysis'}_rate_limit", 1
    )

    def submit():
        if operation == "upload":
            return client.post(
                f"/api/v1/projects/{ids['project']}/documents",
                files={"file": ("new.txt", uuid4().hex.encode(), "text/plain")},
            )
        return client.post(f"/api/v1/projects/{ids['project']}/analyze", json=payload(ids))

    assert submit().status_code == 202
    rejected = submit()
    assert rejected.status_code == 429, rejected.text
    assert 1 <= int(rejected.headers["Retry-After"]) <= settings.rate_limit_window_seconds
    other_user = uuid4()
    with SessionLocal.begin() as db:
        db.add(Profile(id=other_user, display_name="Second rate-limit user"))
    try:
        app.dependency_overrides[get_principal] = lambda: Principal(
            other_user, DEV_FIRM, Role.OWNER
        )
        # Different user receives normal domain handling (analysis is already active).
        response = submit()
        assert response.status_code == (202 if operation == "upload" else 409), response.text
    finally:
        from app.models.entities import AuditEvent

        with SessionLocal.begin() as db:
            db.execute(delete(AuditEvent).where(AuditEvent.actor_id == other_user))
            db.execute(delete(Profile).where(Profile.id == other_user))


def test_cors_allows_idempotency_and_exposes_retry_after(workflow):
    client, ids, _ = workflow
    response = client.options(
        f"/api/v1/projects/{ids['project']}/analyze",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,idempotency-key",
        },
    )
    assert response.status_code == 200
    assert "idempotency-key" in response.headers["Access-Control-Allow-Headers"].lower()


def test_openapi_declares_workflow_responses(workflow):
    paths = app.openapi()["paths"]
    for path, method, statuses in [
        ("/api/v1/projects/{project_id}/documents", "get", ["200", "404"]),
        ("/api/v1/documents/{document_id}", "get", ["200", "404", "503"]),
        ("/api/v1/documents/{document_id}", "delete", ["204", "403", "404", "503"]),
        ("/api/v1/projects/{project_id}/analyze", "post", ["202", "409", "429", "503"]),
        ("/api/v1/jobs/{job_id}", "get", ["200", "404"]),
        ("/api/v1/projects/{project_id}/stages", "get", ["200", "404"]),
        ("/api/v1/stages/{stage_id}", "get", ["200", "404"]),
        ("/api/v1/projects/{project_id}/citations", "get", ["200", "404"]),
    ]:
        assert set(statuses) <= paths[path][method]["responses"].keys()


@pytest.mark.parametrize(
    "method,path,identifier",
    [
        ("post", "/api/v1/projects/{project_id}/documents", "project_id"),
        ("get", "/api/v1/projects/{project_id}/documents", "project_id"),
        ("get", "/api/v1/documents/{document_id}", "document_id"),
        ("delete", "/api/v1/documents/{document_id}", "document_id"),
        ("post", "/api/v1/projects/{project_id}/analyze", "project_id"),
        ("get", "/api/v1/jobs/{job_id}", "job_id"),
        ("get", "/api/v1/projects/{project_id}/stages", "project_id"),
        ("get", "/api/v1/stages/{stage_id}", "stage_id"),
        ("get", "/api/v1/projects/{project_id}/citations", "project_id"),
    ],
)
def test_workflow_openapi_validation_envelope_matches_runtime(workflow, method, path, identifier):
    client, ids, _ = workflow
    request = {}
    if method == "post":
        if path.endswith("/documents"):
            request["files"] = {"file": ("new.txt", b"data", "text/plain")}
        else:
            request["json"] = payload(ids)
    response = client.request(method, path.format(**{identifier: "invalid-uuid"}), **request)
    assert response.status_code == 422, response.text
    assert set(response.json()) == {"error"}
    error = response.json()["error"]
    assert set(error) == {"message", "fields"}
    assert error["message"] == "Check the submitted fields."
    assert len(error["fields"]) == 1
    assert error["fields"][0]["field"] == f"path.{identifier}"
    assert isinstance(error["fields"][0]["message"], str)

    contract = client.get("/openapi.json").json()
    schema = contract["paths"][path][method]["responses"]["422"]["content"]["application/json"][
        "schema"
    ]
    variants = schema.get("anyOf", [schema])
    assert {"$ref": "#/components/schemas/ValidationErrorRead"} in variants
    if method == "post" and path.endswith("/documents"):
        assert {"$ref": "#/components/schemas/ErrorRead"} in variants
    models = contract["components"]["schemas"]
    envelope = models["ValidationErrorRead"]
    assert envelope["required"] == ["error"]
    assert envelope["properties"]["error"] == {"$ref": "#/components/schemas/ValidationErrorDetail"}
    detail = models["ValidationErrorDetail"]
    assert set(detail["required"]) == {"message", "fields"}
    assert detail["properties"]["fields"]["type"] == "array"
    assert detail["properties"]["fields"]["items"] == {
        "$ref": "#/components/schemas/ValidationErrorField"
    }
    field = models["ValidationErrorField"]
    assert set(field["required"]) == {"field", "message"}
    assert field["properties"]["field"]["type"] == "string"
    assert field["properties"]["message"]["type"] == "string"


def test_every_workflow_read_requires_authentication(workflow):
    client, ids, _ = workflow
    for path in (
        f"projects/{ids['project']}/documents",
        f"documents/{ids['document']}",
        f"projects/{ids['project']}/stages",
        f"stages/{ids['stage']}",
        f"projects/{ids['project']}/citations",
        f"jobs/{ids['job']}",
    ):
        response = client.get(f"/api/v1/{path}", headers={"Authorization": ""})
        assert response.status_code == 401
        assert "error" in response.json()


def test_empty_current_process_and_unselected_general_analysis_are_honest(workflow, monkeypatch):
    client, ids, _ = workflow
    allow_ai(monkeypatch)
    assert client.delete(f"/api/v1/documents/{ids['document']}").status_code == 204
    data = client.get(f"/api/v1/projects/{ids['project']}/stages").json()
    assert data["stages"] == [] and data["summary"] is None
    assert data["review_required"] is True
    request = {**payload(ids), "selected_document_ids": []}
    response = client.post(f"/api/v1/projects/{ids['project']}/analyze", json=request)
    assert response.status_code == 202
    assert client.get(f"/api/v1/projects/{ids['project']}/stages").json()["stages"] == []


def test_deletion_cancels_analysis_using_the_document(workflow, monkeypatch):
    client, ids, _ = workflow
    allow_ai(monkeypatch)
    response = client.post(f"/api/v1/projects/{ids['project']}/analyze", json=payload(ids))
    assert response.status_code == 202
    assert client.delete(f"/api/v1/documents/{ids['document']}").status_code == 204
    polled = client.get(f"/api/v1/jobs/{response.json()['id']}")
    assert polled.json()["status"] == "cancelled"


def test_curated_citation_uses_stored_source_metadata(workflow):
    from app.models.entities import LegalSource, SourceChunk

    client, ids, _ = workflow
    source_id, chunk_id = uuid4(), uuid4()
    with SessionLocal.begin() as db:
        db.add(
            LegalSource(
                id=source_id,
                firm_id=DEV_FIRM,
                project_id=ids["project"],
                title="Stored Act",
                url="https://authority.example/act",
                jurisdiction="India",
                source_type="legislation",
                verification_status="verified",
                citation_reference="Section 2",
            )
        )
        db.flush()
        db.add(
            SourceChunk(
                id=chunk_id,
                source_id=source_id,
                firm_id=DEV_FIRM,
                position=0,
                content="The stored statutory passage",
                page_number=2,
                heading="Notice",
            )
        )
        db.flush()
        db.add(
            StageCitation(
                firm_id=DEV_FIRM,
                stage_id=ids["stage"],
                source_chunk_id=chunk_id,
                claim_text="Stored claim",
                excerpt="stored statutory passage",
                validation_status="supported",
            )
        )
    response = client.get(f"/api/v1/projects/{ids['project']}/citations")
    assert response.status_code == 200, response.text
    (citation,) = [item for item in response.json() if item["source_type"] == "legislation"]
    assert citation["verification_status"] == "verified"
    assert (
        citation["source_title"] == "Stored Act"
        and citation["source_url"] == "https://authority.example/act"
    )
    assert citation["source_filename"] is None
    assert citation["citation_reference"] == "Section 2" and citation["page_number"] == 2


def test_download_signing_failure_is_sanitized(workflow, monkeypatch):
    client, ids, storage = workflow

    def unavailable(*args):
        raise OSError("private-storage-token")

    monkeypatch.setattr(storage, "signed_url", unavailable)
    response = client.get(f"/api/v1/documents/{ids['document']}?download=true")
    assert response.status_code == 503 and "private-storage-token" not in response.text


def test_redis_unavailability_fails_closed_without_upload_or_analysis(workflow, monkeypatch):
    from redis.exceptions import ConnectionError

    client, ids, _ = workflow
    allow_ai(monkeypatch)

    def unavailable(*args):
        raise ConnectionError("private-redis-password")

    monkeypatch.setattr(redis_client, "eval", unavailable)
    upload = client.post(
        f"/api/v1/projects/{ids['project']}/documents",
        files={"file": ("new.txt", b"unadmitted", "text/plain")},
    )
    analysis = client.post(f"/api/v1/projects/{ids['project']}/analyze", json=payload(ids))
    assert upload.status_code == analysis.status_code == 503
    assert "private-redis-password" not in upload.text + analysis.text
    with SessionLocal() as db:
        assert (
            len(db.scalars(select(Document).where(Document.project_id == ids["project"])).all())
            == 1
        )
        assert (
            len(
                db.scalars(
                    select(GenerationJob).where(GenerationJob.project_id == ids["project"])
                ).all()
            )
            == 1
        )


def test_expired_fixed_window_admits_again(workflow, monkeypatch):
    client, ids, _ = workflow
    monkeypatch.setattr(settings, "upload_rate_limit", 1)

    def submit():
        return client.post(
            f"/api/v1/projects/{ids['project']}/documents",
            files={"file": ("new.txt", uuid4().hex.encode(), "text/plain")},
        )

    assert submit().status_code == 202
    rejected = submit()
    assert rejected.status_code == 429
    assert int(rejected.headers["X-RateLimit-Remaining"]) == 0
    key = f"{ids['rate_namespace']}:clientexplain:rate:upload:{DEV_FIRM}:{DEV_USER}"
    redis_client.expire(key, 0)
    admitted = submit()
    assert admitted.status_code == 202 and admitted.headers["X-RateLimit-Remaining"] == "0"


def test_submission_key_replays_completed_job_and_model_changes_conflict(workflow, monkeypatch):
    client, ids, _ = workflow
    allow_ai(monkeypatch)
    url = f"/api/v1/projects/{ids['project']}/analyze"
    headers = {"Idempotency-Key": "completed-submission"}
    initial = client.post(url, json=payload(ids), headers=headers)
    assert initial.status_code == 202
    with SessionLocal.begin() as db:
        job = db.get(GenerationJob, UUID(initial.json()["id"]))
        job.status, job.progress = "completed", 100
    replay = client.post(url, json=payload(ids), headers=headers)
    assert replay.status_code == 202 and replay.json()["status"] == "completed"
    assert replay.json()["id"] == initial.json()["id"]
    monkeypatch.setattr(settings, "openai_analysis_model", "changed-model")
    assert client.post(url, json=payload(ids), headers=headers).status_code == 409


def test_reviewer_cannot_probe_cross_firm_resources(workflow, monkeypatch):
    client, ids, _ = workflow
    allow_ai(monkeypatch)
    app.dependency_overrides[get_principal] = lambda: Principal(DEV_USER, uuid4(), Role.REVIEWER)
    assert client.delete(f"/api/v1/documents/{ids['document']}").status_code == 404
    assert (
        client.post(f"/api/v1/projects/{ids['project']}/analyze", json=payload(ids)).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/projects/{ids['project']}/documents",
            files={"file": ("new.txt", b"data", "text/plain")},
        ).status_code
        == 404
    )


def test_request_logs_omit_analysis_body_and_bearer_token(workflow, caplog):
    import logging

    client, ids, _ = workflow
    with caplog.at_level(logging.INFO):
        response = client.post(
            f"/api/v1/projects/{ids['project']}/analyze",
            json={**payload(ids), "process_text": "private-body-marker-for-logs"},
        )
    assert response.status_code == 503
    assert "private-body-marker-for-logs" not in caplog.text
    assert settings.dev_auth_token not in caplog.text


def test_stage_metadata_and_stage_rows_are_one_publication_during_rerun(workflow):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from app.db.session import engine
    from sqlalchemy import event

    client, ids, _ = workflow
    published = Event()
    triggered = False
    publication = []

    def publish():
        with SessionLocal.begin() as db:
            db.scalar(select(Project).where(Project.id == ids["project"]).with_for_update())
            db.get(ProcessStage, ids["stage"]).title = "Replacement stage"
            version = db.scalar(
                select(ProjectVersion).where(ProjectVersion.project_id == ids["project"])
            )
            db.add(
                ProjectVersion(
                    firm_id=DEV_FIRM,
                    project_id=ids["project"],
                    version=2,
                    snapshot={**version.snapshot, "process_name": "Replacement process"},
                )
            )
        published.set()

    with ThreadPoolExecutor(max_workers=1) as executor:

        def after_read(conn, cursor, statement, parameters, context, executemany):
            nonlocal triggered
            if not triggered and statement.startswith("SELECT process_stages."):
                triggered = True
                publication.append(executor.submit(publish))
                # A publication must wait if a coherent reader holds the project.
                published.wait(0.5)

        event.listen(engine, "after_cursor_execute", after_read)
        try:
            response = client.get(f"/api/v1/projects/{ids['project']}/stages")
        finally:
            event.remove(engine, "after_cursor_execute", after_read)
    for future in publication:
        future.result()
    assert triggered and published.is_set()
    assert response.status_code == 200
    data = response.json()
    assert (data["stages"][0]["title"], data["process_name"]) in {
        ("First", "Notice process"),
        ("Replacement stage", "Replacement process"),
    }
