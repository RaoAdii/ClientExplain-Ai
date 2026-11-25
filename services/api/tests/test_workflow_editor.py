"""Saved editor contract over real isolated PostgreSQL transactions."""

from uuid import uuid4

import pytest
from app.core.auth import DEV_USER, Principal, get_principal
from app.core.config import settings
from app.main import app
from app.schemas.auth import Role
from fastapi.testclient import TestClient


@pytest.fixture
def editor():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {settings.dev_auth_token}"}
        project = client.post(
            "/api/v1/projects", headers=headers, json={"name": "Editor test"}
        ).json()
        try:
            yield client, headers, project
        finally:
            app.dependency_overrides.pop(get_principal, None)
            client.delete(f"/api/v1/projects/{project['id']}", headers=headers)


def stage(title="Review documents"):
    return {
        "id": str(uuid4()),
        "title": title,
        "explanation": "Read the supplied documents.",
        "responsible_party": "Client",
        "required_documents": ["User-provided record"],
        "limitations": ["Requires lawyer verification"],
        "position": {"x": 20, "y": 40},
        "actions": ["Read the record"],
        "preconditions": [],
        "outcomes": [],
        "status": "pending",
    }


def test_editor_save_reload_reorder_delete_and_conflict(editor):
    client, headers, project = editor
    url = f"/api/v1/projects/{project['id']}/workflow"
    initial = client.get(url, headers=headers)
    assert initial.status_code == 200
    assert initial.json()["version"] == 0
    first, second = stage(), stage("Discuss questions")
    payload = {
        "version": 0,
        "stages": [first, second],
        "edges": [{"source": first["id"], "target": second["id"]}],
    }
    saved = client.patch(url, headers=headers, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 1
    loaded = client.get(url, headers=headers).json()
    assert loaded["stages"][0]["position"] == {"x": 20, "y": 40}
    assert loaded["stages"][0]["actions"] == ["Read the record"]
    assert loaded["edges"] == payload["edges"]
    assert client.patch(url, headers=headers, json=payload).status_code == 409
    payload.update(version=1, stages=[second, first], edges=[])
    assert client.patch(url, headers=headers, json=payload).status_code == 200
    assert client.get(url, headers=headers).json()["stages"][0]["id"] == second["id"]
    payload.update(version=2, stages=[second])
    assert client.patch(url, headers=headers, json=payload).status_code == 200
    assert len(client.get(url, headers=headers).json()["stages"]) == 1


def test_editor_validates_graph_and_denies_other_tenant(editor):
    client, headers, project = editor
    url = f"/api/v1/projects/{project['id']}/workflow"
    first, second = stage(), stage("Discuss")
    payload = {
        "version": 0,
        "stages": [first, second],
        "edges": [
            {"source": first["id"], "target": second["id"]},
            {"source": second["id"], "target": first["id"]},
        ],
    }
    assert client.patch(url, headers=headers, json=payload).status_code == 422
    payload["edges"] = [{"source": first["id"], "target": str(uuid4())}]
    assert client.patch(url, headers=headers, json=payload).status_code == 422
    payload.update(stages=[first, first], edges=[])
    assert client.patch(url, headers=headers, json=payload).status_code == 422
    app.dependency_overrides[get_principal] = lambda: Principal(DEV_USER, uuid4(), Role.OWNER)
    assert client.get(url, headers=headers).status_code == 404
    assert (
        client.patch(
            url, headers=headers, json={"version": 0, "stages": [], "edges": []}
        ).status_code
        == 404
    )
