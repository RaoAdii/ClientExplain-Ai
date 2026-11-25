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


@pytest.fixture
def make_settings(monkeypatch):
    def create(**overrides):
        defaults = {
            "app_env": "test",
            "auth_mode": "development",
            "dev_auth_token": "x" * 32,
            "database_url": "postgresql+psycopg://localhost/test",
        }
        return Settings(**(defaults | overrides), _env_file=None)

    for name in (
        "AI_EXTERNAL_PROCESSING_ALLOWED",
        "AI_PROVIDER",
        "EMBEDDING_DIMENSIONS",
        "EMBEDDING_MODEL",
        "MAX_UPLOAD_BYTES",
        "OPENAI_ANALYSIS_MODEL",
        "OPENAI_API_KEY",
        "OLLAMA_ANALYSIS_MODEL",
        "OLLAMA_BASE_URL",
        "OLLAMA_EMBEDDING_MODEL",
        "PRIVATE_STORAGE_ROOT",
        "STORAGE_BACKEND",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_STORAGE_BUCKET",
    ):
        monkeypatch.delenv(name, raising=False)
    return create


def test_external_ai_requires_key_model_and_embedding_pair(make_settings):
    assert make_settings().ai_external_processing_allowed is False
    enabled = {"ai_external_processing_allowed": True}
    for incomplete in (
        {"openai_api_key": "", "openai_analysis_model": "test-analysis-model"},
        {"openai_api_key": "test-only-key", "openai_analysis_model": "  "},
    ):
        with pytest.raises(ValidationError, match="OPENAI_API_KEY.*OPENAI_ANALYSIS_MODEL"):
            make_settings(**enabled, **incomplete)

    configured = enabled | {
        "openai_api_key": "test-only-key",
        "openai_analysis_model": "test-analysis-model",
    }
    with pytest.raises(ValidationError, match="EMBEDDING_MODEL.*EMBEDDING_DIMENSIONS"):
        make_settings(**configured, embedding_model="text-embedding-3-large")
    assert make_settings(**configured).ai_external_processing_allowed is True


def test_embedding_dimension_is_1536_for_initial_model(make_settings):
    settings = make_settings()
    assert (settings.embedding_model, settings.embedding_dimensions) == (
        "text-embedding-3-small",
        1536,
    )
    with pytest.raises(ValidationError, match="EMBEDDING_MODEL.*EMBEDDING_DIMENSIONS"):
        make_settings(embedding_dimensions=3072)


def test_ollama_requires_local_models_and_loopback_endpoint(make_settings):
    with pytest.raises(ValidationError, match="OLLAMA_ANALYSIS_MODEL"):
        make_settings(ai_provider="ollama")
    configured = make_settings(
        ai_provider="ollama",
        ollama_analysis_model="qwen3:4b",
        ollama_embedding_model="qwen3-embedding:4b",
        ollama_base_url="http://127.0.0.1:11434",
    )
    assert configured.ai_provider == "ollama"
    for url in (
        "https://127.0.0.1:11434",
        "http://example.com:11434",
        "http://user:pass@localhost:11434",
        "http://localhost",
    ):
        with pytest.raises(ValidationError, match="OLLAMA_BASE_URL"):
            make_settings(
                ai_provider="ollama",
                ollama_analysis_model="qwen3:4b",
                ollama_embedding_model="qwen3-embedding:4b",
                ollama_base_url=url,
            )


def test_disabled_ai_accepts_previous_blank_embedding_configuration(make_settings, monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "")
    assert make_settings().embedding_model == "text-embedding-3-small"


def test_production_rejects_local_storage(make_settings):
    local = make_settings(app_env="development")
    assert local.storage_backend == "local"
    assert local.private_storage_root.as_posix() == ".local/private-storage"
    assert make_settings(app_env="test").storage_backend == "local"
    with pytest.raises(ValidationError, match="Local storage is prohibited in production"):
        make_settings(
            app_env="production",
            auth_mode="supabase",
            supabase_url="https://project.example.test",
            storage_backend="local",
        )


@pytest.mark.parametrize("storage_root", ["", " \t"])
def test_blank_private_storage_root_is_rejected(make_settings, monkeypatch, storage_root):
    monkeypatch.setenv("PRIVATE_STORAGE_ROOT", storage_root)
    with pytest.raises(ValidationError, match="PRIVATE_STORAGE_ROOT must contain a path"):
        make_settings()


def test_supabase_storage_requires_server_configuration(make_settings):
    with pytest.raises(ValidationError, match="SUPABASE_STORAGE_BUCKET.*SUPABASE_SERVICE_ROLE_KEY"):
        make_settings(storage_backend="supabase", supabase_url="https://project.example.test")

    configured = make_settings(
        storage_backend="supabase",
        supabase_url="https://project.example.test",
        supabase_storage_bucket="private-documents",
        supabase_service_role_key="test-only-service-role-key",
    )
    assert configured.supabase_storage_bucket == "private-documents"
    assert "test-only-service-role-key" not in repr(configured)


@pytest.mark.parametrize(
    "supabase_config",
    [
        {"auth_mode": "supabase"},
        {
            "storage_backend": "supabase",
            "supabase_storage_bucket": "private-documents",
            "supabase_service_role_key": "test-only-service-role-key",
        },
    ],
    ids=["auth", "storage"],
)
@pytest.mark.parametrize("url", ["https://", "https:// ", "https:///auth", "https://[broken"])
def test_supabase_requires_https_url_with_hostname(make_settings, supabase_config, url):
    with pytest.raises(ValidationError, match="HTTPS SUPABASE_URL"):
        make_settings(**supabase_config, supabase_url=url)


def test_upload_limits_are_bounded(make_settings):
    assert make_settings().max_upload_bytes == 26214400
    assert make_settings(max_upload_bytes=1).max_upload_bytes == 1
    for invalid_limit in (0, 26214401):
        with pytest.raises(ValidationError, match="max_upload_bytes"):
            make_settings(max_upload_bytes=invalid_limit)
