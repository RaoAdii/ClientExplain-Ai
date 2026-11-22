import hashlib
import sys
from io import BytesIO
from uuid import UUID, uuid4
from zipfile import ZipFile

import pytest
from app.core.auth import DEV_FIRM, DEV_USER, Principal, get_principal
from app.core.config import MAX_UPLOAD_BYTES, settings
from app.db.session import SessionLocal
from app.integrations.storage import LocalPrivateStorage
from app.main import app
from app.models.entities import Document, GenerationJob, Project
from app.schemas.auth import Role
from app.services import documents
from celery import Celery
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import SessionTransaction


def docx():
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        )
        archive.writestr("word/document.xml", "<document/>")
    return output.getvalue()


@pytest.fixture
def upload_env(tmp_path, monkeypatch):
    project_id = uuid4()
    with SessionLocal.begin() as db:
        db.add(Project(id=project_id, firm_id=DEV_FIRM, created_by=DEV_USER, name="Upload"))
    storage = LocalPrivateStorage(tmp_path)
    monkeypatch.setattr(documents, "get_storage", lambda: storage)
    deliveries = []

    def dispatch(document_id, job_id):
        # A separate database connection must already see both committed rows.
        with SessionLocal() as db:
            assert db.get(Document, document_id).project_id == project_id
            assert db.get(GenerationJob, job_id).request_metadata["document_id"] == str(document_id)
        deliveries.append((document_id, job_id))

    monkeypatch.setattr(documents, "dispatch_parse", dispatch)
    with TestClient(app, headers={"Authorization": f"Bearer {settings.dev_auth_token}"}) as client:
        yield (
            client,
            f"/api/v1/projects/{project_id}/documents",
            project_id,
            tmp_path,
            deliveries,
            storage,
        )
    app.dependency_overrides.clear()
    with SessionLocal.begin() as db:
        db.execute(delete(Project).where(Project.id == project_id))


def assert_empty(env):
    _, _, project_id, root, deliveries, _ = env
    with SessionLocal() as db:
        assert db.scalars(select(Document).where(Document.project_id == project_id)).all() == []
        assert (
            db.scalars(select(GenerationJob).where(GenerationJob.project_id == project_id)).all()
            == []
        )
    assert [p for p in root.rglob("*") if p.is_file()] == []
    assert deliveries == []


@pytest.mark.parametrize(
    "filename,mime,body",
    [
        ("contract.pdf", "application/pdf", b"%PDF-1.7\nprivate"),
        (
            "contract.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            docx(),
        ),
        ("contract.txt", "text/plain", "Private text नमस्ते".encode()),
    ],
)
def test_upload_validates_hashes_and_commits_before_dispatch(upload_env, filename, mime, body):
    client, url, project_id, root, deliveries, _ = upload_env
    response = client.post(url, files={"file": (filename, body, mime)})
    assert response.status_code == 202, response.text
    data = response.json()
    document = data["document"]
    assert document["sha256"] == hashlib.sha256(body).hexdigest()
    assert document["byte_size"] == len(body)
    assert document["project_id"] == str(project_id)
    assert data["job"]["kind"] == "parse"
    assert data["job"]["status"] == "queued"
    assert len(deliveries) == 1
    assert "storage_key" not in document and "url" not in document
    objects = [p for p in root.rglob("*") if p.is_file()]
    assert len(objects) == 1 and objects[0].read_bytes() == body
    parts = objects[0].relative_to(root).parts
    assert parts[:2] == (str(DEV_FIRM), str(project_id))
    assert UUID(objects[0].stem) == UUID(document["id"])
    assert filename not in str(objects[0])


@pytest.mark.parametrize(
    "filename,mime,body,status",
    [
        ("fake.pdf", "application/pdf", b"not a PDF", 415),
        ("fake.pdf", "text/plain", b"%PDF-1.7", 415),
        ("fake.txt", "text/plain", b"%PDF-1.7", 415),
        (
            "fake.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            b"PK\x03\x04fake",
            415,
        ),
        ("binary.txt", "text/plain", b"\x00\xff", 415),
        ("image.png", "image/png", b"PNG", 415),
        ("empty.txt", "text/plain", b"", 422),
        ("huge.txt", "text/plain", b"a" * (MAX_UPLOAD_BYTES + 1), 413),
    ],
)
def test_invalid_upload_creates_no_row_or_private_object(upload_env, filename, mime, body, status):
    client, url, *_ = upload_env
    assert client.post(url, files={"file": (filename, body, mime)}).status_code == status
    assert_empty(upload_env)


def test_exact_25_mib_boundary_is_accepted(upload_env):
    client, url, *_ = upload_env
    response = client.post(
        url, files={"file": ("boundary.txt", b"a" * MAX_UPLOAD_BYTES, "text/plain")}
    )
    assert response.status_code == 202
    assert response.json()["document"]["byte_size"] == MAX_UPLOAD_BYTES


def test_duplicate_is_conflict_without_new_object_or_job(upload_env):
    client, url, _, root, deliveries, _ = upload_env
    files = {"file": ("private.txt", b"same bytes", "text/plain")}
    first = client.post(url, files=files).json()
    second = client.post(url, files=files)
    assert second.status_code == 409
    assert second.json()["error"]["message"] == str(
        {"document_id": first["document"]["id"], "status": "pending"}
    )
    assert len(deliveries) == 1
    assert len([p for p in root.rglob("*") if p.is_file()]) == 1


@pytest.mark.parametrize(
    "principal,status",
    [
        (Principal(DEV_USER, DEV_FIRM, Role.REVIEWER), 403),
        (Principal(DEV_USER, uuid4(), Role.OWNER), 404),
    ],
)
def test_upload_enforces_role_and_tenant(upload_env, principal, status):
    client, url, *_ = upload_env
    app.dependency_overrides[get_principal] = lambda: principal
    assert (
        client.post(url, files={"file": ("private.txt", b"secret", "text/plain")}).status_code
        == status
    )
    assert_empty(upload_env)


@pytest.mark.parametrize("failure", ["storage", "commit", "dispatch"])
def test_failure_rolls_back_rows_jobs_and_exact_object(upload_env, monkeypatch, failure):
    client, url, _, root, _, storage = upload_env
    sentinel = root / "keep.txt"
    sentinel.write_bytes(b"keep")

    def fail(*args, **kwargs):
        raise RuntimeError("sensitive detail")

    if failure == "storage":
        original = storage.put

        def partial(key, stream):
            original(key, stream)
            fail()

        monkeypatch.setattr(storage, "put", partial)
    elif failure == "dispatch":
        monkeypatch.setattr(documents, "dispatch_parse", fail)
    else:
        original_commit = SessionTransaction.commit

        def commit(self, _to_root=False):
            if self.parent is None:
                raise SQLAlchemyError("sensitive detail")
            return original_commit(self, _to_root=_to_root)

        monkeypatch.setattr(SessionTransaction, "commit", commit)
    response = client.post(url, files={"file": ("private.txt", b"private bytes", "text/plain")})
    assert response.status_code == 503
    assert "sensitive" not in response.text
    assert sentinel.read_bytes() == b"keep"
    sentinel.unlink()
    monkeypatch.undo()
    assert_empty(upload_env)


def test_api_dispatch_does_not_require_worker_package(monkeypatch):
    monkeypatch.setitem(sys.modules, "worker", None)
    published = []

    def publish(self, name, args, **options):
        published.append((name, args, options))

    monkeypatch.setattr(Celery, "send_task", publish)
    document_id, job_id = uuid4(), uuid4()
    documents.dispatch_parse(document_id, job_id)
    assert published == [
        (
            "worker.parse_document",
            [str(document_id), str(job_id)],
            {
                "queue": "generation",
                "serializer": "json",
                "retry": False,
            },
        )
    ]
