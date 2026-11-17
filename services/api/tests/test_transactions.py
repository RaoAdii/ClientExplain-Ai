from app.core.config import settings
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import SessionTransaction


def test_commit_failure_does_not_return_success(monkeypatch):
    def fail_commit(self, _to_root=False):
        if self.parent is None:
            raise SQLAlchemyError("Simulated commit failure")

    monkeypatch.setattr(SessionTransaction, "commit", fail_commit)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/projects",
            headers={"Authorization": f"Bearer {settings.dev_auth_token}"},
            json={"name": "Rollback verification"},
        )
    assert response.status_code == 503
    assert response.json()["error"]["message"] == "The database is unavailable. Try again shortly."
