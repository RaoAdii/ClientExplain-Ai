from uuid import UUID, uuid4

import pytest
from app.core.auth import DEV_FIRM, DEV_USER
from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.entities import AuditEvent, Project
from app.repositories.projects import list_projects
from fastapi.testclient import TestClient
from sqlalchemy import delete, event

BASE = "/api/v1/projects"


@pytest.fixture
def client():
    with TestClient(app, headers={"Authorization": f"Bearer {settings.dev_auth_token}"}) as http:
        yield http


@pytest.fixture
def project_ids():
    ids = []
    yield ids
    with SessionLocal.begin() as db:
        db.execute(delete(Project).where(Project.id.in_(ids)))
        db.execute(delete(AuditEvent).where(AuditEvent.resource_id.in_(ids)))


def test_extended_fields_and_metadata_only_activity(client, project_ids):
    fields = {
        "legal_area": "Family law",
        "language": "Hindi",
        "target_audience": "Clients",
        "complexity": "moderate",
    }
    created = client.post(BASE, json={"name": "Sensitive matter", **fields})
    assert created.status_code == 201
    data = created.json()
    project_ids.append(UUID(data["id"]))
    assert data.items() >= fields.items()
    assert data["owner_id"] == str(DEV_USER)
    assert (data["workflow_status"], data["processing_status"]) == ("draft", "idle")
    url = f"{BASE}/{data['id']}"
    changes = {"workflow_status": "active", "language": " English "}
    edited = client.patch(url, json=changes)
    assert edited.status_code == 200
    assert edited.json()["language"] == "English"
    assert edited.json()["workflow_status"] == "active"
    assert client.patch(url, json={"review_status": "in_review"}).status_code == 200
    events = client.get(url + "/activity").json()
    assert [event["action"] for event in events] == [
        "project.review_changed",
        "project.updated",
        "project.created",
    ]
    assert [event["created_at"] for event in events] == sorted(
        (event["created_at"] for event in events), reverse=True
    )
    assert all(event["actor_id"] == str(DEV_USER) for event in events)
    assert all(
        set(event) == {"id", "action", "actor_id", "created_at", "resource_id"} for event in events
    )


def test_repeated_approval_records_one_review_transition(client, project_ids):
    created = client.post(BASE, json={"name": "Review retry"}).json()
    project_ids.append(UUID(created["id"]))
    url = f"{BASE}/{created['id']}"
    for _ in range(2):
        response = client.patch(url, json={"review_status": "approved"})
        assert response.status_code == 200
        assert response.json()["review_status"] == "approved"
    assert [entry["action"] for entry in client.get(url + "/activity").json()] == [
        "project.review_changed",
        "project.created",
    ]


def test_project_fields_are_bounded_and_server_fields_are_protected(client, project_ids):
    created = client.post(BASE, json={"name": "Validation"}).json()
    project_ids.append(UUID(created["id"]))
    url = f"{BASE}/{created['id']}"
    for invalid in [
        {"legal_area": "a" * 121},
        {"target_audience": "a" * 121},
        {"language": "a" * 61},
        {"complexity": "a" * 41},
        {"workflow_status": "invalid"},
        {"processing_status": "completed"},
        {"owner_id": str(uuid4())},
        {"legal_area": None},
    ]:
        assert client.post(BASE, json={"name": "Invalid", **invalid}).status_code == 422
        assert client.patch(url, json=invalid).status_code == 422
    assert (
        client.post(BASE, json={"name": "Invalid", "review_status": "approved"}).status_code == 422
    )
    assert client.patch(url, json={"review_status": "invalid"}).status_code == 422
    for params in [{"status": "invalid"}, {"review_status": "invalid"}, {"search": "a" * 201}]:
        assert client.get(BASE, params=params).status_code == 422


def test_paginated_literal_search_and_combined_filters(client, project_ids):
    marker = uuid4().hex
    literal = f"{marker} %_/"
    with SessionLocal.begin() as db:
        for name, status, review in [
            (literal + " A", "active", "in_review"),
            (literal + " B", "active", "in_review"),
            (marker + " XX/", "active", "in_review"),
            (literal + " C", "draft", "in_review"),
            (literal + " D", "active", "approved"),
        ]:
            project_ids.append(uuid4())
            db.add(
                Project(
                    id=project_ids[-1],
                    firm_id=DEV_FIRM,
                    created_by=DEV_USER,
                    name=name,
                    workflow_status=status,
                    review_status=review,
                )
            )
    filters = {
        "search": literal.upper(),
        "status": "active",
        "review_status": "in_review",
        "limit": 1,
    }
    for offset, expected in enumerate(sorted(project_ids[:2])):
        page = client.get(BASE, params={**filters, "offset": offset}).json()
        assert page["total"] == 2
        assert (page["limit"], page["offset"]) == (1, offset)
        assert [p["id"] for p in page["items"]] == [str(expected)]
    assert client.get(BASE, params={**filters, "offset": 2}).json() == {
        "items": [],
        "total": 2,
        "limit": 1,
        "offset": 2,
    }
    updated_id = max(project_ids[:2])
    assert client.patch(f"{BASE}/{updated_id}", json={"description": "Changed"}).status_code == 200
    assert client.get(BASE, params=filters).json()["items"][0]["id"] == str(updated_id)


def test_empty_offset_page_and_total_share_a_snapshot_during_insert(project_ids):
    marker = uuid4().hex

    def insert_match():
        project_id = uuid4()
        with SessionLocal.begin() as writer:
            writer.add(Project(id=project_id, firm_id=DEV_FIRM, created_by=DEV_USER, name=marker))
        project_ids.append(project_id)

    insert_match()
    statements = []

    def commit_after_first_query(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
        if len(statements) == 1:
            insert_match()

    with SessionLocal() as reader:
        event.listen(reader.connection(), "after_cursor_execute", commit_after_first_query)
        page = list_projects(reader, DEV_FIRM, limit=1, offset=1, search=marker)
        assert page == {"items": [], "total": 1, "limit": 1, "offset": 1}
        assert len(statements) == 1
    with SessionLocal() as reader:
        assert list_projects(reader, DEV_FIRM, limit=1, offset=1, search=marker)["total"] == 2
