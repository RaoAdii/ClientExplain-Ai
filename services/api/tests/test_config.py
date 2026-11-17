import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_production_rejects_dev_auth():
    with pytest.raises(ValidationError, match="prohibited"):
        Settings(
            app_env="production",
            auth_mode="development",
            dev_auth_token="x" * 32,
            database_url="postgresql+psycopg://localhost/test",
            _env_file=None,
        )


def test_empty_patch_rejected():
    from app.schemas.projects import ProjectUpdate

    with pytest.raises(ValidationError):
        ProjectUpdate()


def test_disabled_generation_fails_explicitly():
    from worker.providers.base import ImageRequest, get_provider

    with pytest.raises(RuntimeError, match="unavailable"):
        get_provider().generate(ImageRequest(prompt="A process illustration"))
