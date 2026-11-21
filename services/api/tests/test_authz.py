from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from app.core import auth
from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.entities import AuditEvent, Firm, FirmMember, Profile, Project
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import select


@pytest.fixture
def client():
    with TestClient(app) as http:
        yield http


@pytest.fixture
def signed_session(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    public = jwt.algorithms.ECAlgorithm.to_jwk(key.public_key(), as_dict=True)
    issuer = "https://auth.example.test"
    jwks = jwt.PyJWKClient(issuer)
    monkeypatch.setattr(jwks, "fetch_data", lambda: {"keys": [{**public, "kid": "test-key"}]})
    monkeypatch.setattr(auth, "jwks", jwks)
    monkeypatch.setattr(settings, "auth_mode", "supabase")
    monkeypatch.setattr(settings, "supabase_url", issuer)

    def headers(subject, signing_key=key, **overrides):
        claims = {
            "sub": str(subject),
            "iss": issuer + "/auth/v1",
            "aud": "authenticated",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "role": "owner",  # Membership in the database determines the actual role.
            **overrides,
        }
        token = jwt.encode(claims, signing_key, algorithm="ES256", headers={"kid": "test-key"})
        return {"Authorization": f"Bearer {token}"}

    return headers


@pytest.fixture
def workspace():
    firm_id, user_id = uuid4(), uuid4()
    with SessionLocal.begin() as db:
        db.add_all([Firm(id=firm_id, name="Test firm"), Profile(id=user_id, display_name="Member")])
    try:
        yield firm_id, user_id
    finally:
        with SessionLocal.begin() as db:
            db.delete(db.get(Firm, firm_id))
            db.flush()
            db.delete(db.get(Profile, user_id))


def test_development_identity(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer wrong"}).status_code == 401
    )
    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {settings.dev_auth_token}"}
    )
    assert me.status_code == 200
    assert me.json()["profile"]["id"] == str(auth.DEV_USER)
    assert me.json()["firm"]["id"] == str(auth.DEV_FIRM)
    assert me.json()["role"] == "owner"


def test_expired_invalid_and_wrongly_signed_sessions(client, signed_session):
    for overrides in [
        {"exp": 0},
        {"iss": "https://other.example.test"},
        {"aud": "another-service"},
        {"sub": "invalid-subject"},
        {"signing_key": ec.generate_private_key(ec.SECP256R1())},
    ]:
        response = client.get("/api/v1/auth/me", headers=signed_session(uuid4(), **overrides))
        assert response.status_code == 401


def test_oldest_membership_wins_ties_by_membership_id(client, signed_session, workspace):
    firm_id, user_id = workspace
    other_id = uuid4()
    time = datetime.now(UTC)
    first, second = sorted([uuid4(), uuid4()])
    with SessionLocal.begin() as db:
        db.add(Firm(id=other_id, name="Another workspace"))
        db.flush()
        db.add_all(
            [
                FirmMember(
                    id=second, profile_id=user_id, firm_id=other_id, created_at=time, role="admin"
                ),
                FirmMember(
                    id=first, profile_id=user_id, firm_id=firm_id, created_at=time, role="lawyer"
                ),
            ]
        )
    try:
        response = client.get("/api/v1/auth/me", headers=signed_session(user_id))
        assert response.status_code == 200
        assert response.json() == {
            "profile": {"id": str(user_id), "display_name": "Member"},
            "firm": {"id": str(firm_id), "name": "Test firm"},
            "role": "lawyer",
        }
    finally:
        with SessionLocal.begin() as db:
            db.delete(db.get(Firm, other_id))


def test_first_session_provisions_one_owner_workspace(client, signed_session):
    user = uuid4()
    headers = signed_session(user)
    try:
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["role"] == "owner"
        assert client.get("/api/v1/auth/me", headers=headers).json() == response.json()
    finally:
        with SessionLocal.begin() as db:
            for firm_id in db.scalars(
                select(FirmMember.firm_id).where(FirmMember.profile_id == user)
            ):
                db.delete(db.get(Firm, firm_id))
            db.flush()
            if profile := db.get(Profile, user):
                db.delete(profile)


@pytest.mark.parametrize("role", ["owner", "admin", "lawyer", "reviewer"])
def test_project_permissions_and_tenant_visibility(client, workspace, signed_session, role):
    firm, user = workspace
    project_id, foreign_id = uuid4(), uuid4()
    with SessionLocal.begin() as db:
        db.add(FirmMember(firm_id=firm, profile_id=user, role=role))
        db.add(Project(id=project_id, firm_id=firm, created_by=user, name="Visible"))
        db.add(
            Project(id=foreign_id, firm_id=auth.DEV_FIRM, created_by=auth.DEV_USER, name="Other")
        )
    headers = signed_session(user)
    base = "/api/v1/projects"
    url = f"{base}/{project_id}"
    foreign = f"{base}/{foreign_id}"
    try:
        assert client.get(url, headers=headers).status_code == 200
        assert client.get(url + "/activity", headers=headers).status_code == 200
        assert client.get(base, headers=headers).json()["total"] == 1
        for method, path, body in [
            ("GET", foreign, None),
            ("GET", foreign + "/activity", None),
            ("PATCH", foreign, {"name": "Hidden"}),
            ("DELETE", foreign, None),
        ]:
            assert client.request(method, path, headers=headers, json=body).status_code == 404
        create = client.post(base, headers=headers, json={"name": "Another project"})
        assert create.status_code == (403 if role == "reviewer" else 201)
        edit = client.patch(
            url, headers=headers, json={"name": "Edited", "review_status": "in_review"}
        )
        assert edit.status_code == (403 if role == "reviewer" else 200)
        if role == "reviewer":
            assert client.get(url, headers=headers).json()["review_status"] == "requires_review"
            assert client.get(url + "/activity", headers=headers).json() == []
            assert (
                client.patch(url, headers=headers, json={"review_status": "in_review"}).status_code
                == 200
            )
        approve = client.patch(url, headers=headers, json={"review_status": "approved"})
        assert approve.status_code == (403 if role == "lawyer" else 200)
        remove = client.delete(url, headers=headers)
        assert remove.status_code == (204 if role in {"owner", "admin"} else 403)
        with SessionLocal() as db:
            actions = db.scalars(
                select(AuditEvent.action).where(AuditEvent.resource_id == project_id)
            ).all()
            assert ("project.deleted" in actions) == (role in {"owner", "admin"})
    finally:
        with SessionLocal.begin() as db:
            db.delete(db.get(Project, foreign_id))
