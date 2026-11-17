from uuid import uuid4

import pytest
from app.core.config import settings
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def headers():
    return {"Authorization": f"Bearer {settings.dev_auth_token}"}


def test_health(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_auth_required(client):
    assert client.get("/api/v1/projects").status_code == 401
    assert (
        client.get("/api/v1/projects", headers={"Authorization": "Bearer wrong"}).status_code == 401
    )


def test_project_lifecycle(client, headers):
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "  Civil procedure briefing  ",
            "description": "Prepare a client explanation.",
            "jurisdiction": "To be confirmed",
        },
    )
    assert response.status_code == 201, response.text
    project = response.json()
    assert project["name"] == "Civil procedure briefing"
    assert project["review_status"] == "requires_review"
    url = f"/api/v1/projects/{project['id']}"
    assert client.get(url, headers=headers).json()["id"] == project["id"]
    assert any(
        p["id"] == project["id"] for p in client.get("/api/v1/projects", headers=headers).json()
    )
    assert (
        client.patch(url, headers=headers, json={"name": "Updated briefing"}).json()["name"]
        == "Updated briefing"
    )
    assert client.patch(url, headers=headers, json={"name": None}).status_code == 422
    assert client.patch(url, headers=headers, json={"firm_id": str(uuid4())}).status_code == 422
    assert client.delete(url, headers=headers).status_code == 204
    assert client.get(url, headers=headers).status_code == 404


def test_validation(client, headers):
    for name in ["", "   ", "x" * 201]:
        assert (
            client.post("/api/v1/projects", headers=headers, json={"name": name}).status_code == 422
        )
    assert client.get("/api/v1/projects/not-a-uuid", headers=headers).status_code == 422
    assert client.get(f"/api/v1/projects/{uuid4()}", headers=headers).status_code == 404


def test_other_tenant_is_not_visible(client, headers):
    from app.core.auth import Principal, get_principal
    from app.db.session import SessionLocal
    from app.models.entities import Firm, FirmMember, Profile

    response = client.post("/api/v1/projects", headers=headers, json={"name": "Private project"})
    project_id = response.json()["id"]
    with SessionLocal.begin() as db:
        user = Profile(id=uuid4(), display_name="Test isolation")
        firm = Firm(name="Isolation test")
        db.add_all([user, firm])
        db.flush()
        db.add(FirmMember(firm_id=firm.id, profile_id=user.id, role="owner"))
        principal = Principal(user.id, firm.id)
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        assert not any(
            p["id"] == project_id for p in client.get("/api/v1/projects", headers=headers).json()
        )
        for method in ["get", "patch", "delete"]:
            kwargs = {"json": {"name": "Changed"}} if method == "patch" else {}
            assert (
                getattr(client, method)(
                    f"/api/v1/projects/{project_id}", headers=headers, **kwargs
                ).status_code
                == 404
            )
    finally:
        app.dependency_overrides.clear()
        client.delete(f"/api/v1/projects/{project_id}", headers=headers)
        with SessionLocal.begin() as db:
            db.delete(db.get(Firm, principal.firm_id))
            db.delete(db.get(Profile, principal.user_id))
