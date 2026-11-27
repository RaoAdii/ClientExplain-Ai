from ipaddress import ip_address
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, PositiveInt, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def _is_https_url(value: str) -> bool:
    try:
        url = urlsplit(value)
    except ValueError:
        return False
    return (
        url.scheme == "https"
        and bool(url.hostname)
        and not any(character.isspace() for character in value)
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    app_env: Literal["development", "test", "production"] = "development"
    auth_mode: Literal["development", "supabase"] = "supabase"
    dev_auth_token: str = ""
    database_url: str
    redis_url: str = "redis://127.0.0.1:6379/0"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    supabase_url: str = ""
    storage_backend: Literal["local", "supabase"] = "local"
    private_storage_root: Path = Path(".local/private-storage")
    supabase_storage_bucket: str = ""
    supabase_service_role_key: SecretStr = SecretStr("")
    max_upload_bytes: int = Field(default=MAX_UPLOAD_BYTES, gt=0, le=MAX_UPLOAD_BYTES)
    openai_api_key: SecretStr = SecretStr("")
    openai_analysis_model: str = ""
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "openai/gpt-oss-20b"
    embedding_model: str = EMBEDDING_MODEL
    embedding_dimensions: int = EMBEDDING_DIMENSIONS
    ai_external_processing_allowed: bool = False
    ai_provider: Literal["openai", "ollama", "groq"] = "openai"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_analysis_model: str = ""
    ollama_embedding_model: str = ""
    retrieval_limit: int = Field(default=8, ge=1, le=50)
    retrieval_threshold: float = Field(default=0.35, ge=0, le=1)
    upload_rate_limit: PositiveInt = 10
    analysis_rate_limit: PositiveInt = 5
    rate_limit_window_seconds: PositiveInt = 60

    @field_validator("private_storage_root", mode="before")
    @classmethod
    def validate_private_storage_root(cls, value: str | Path) -> str | Path:
        if isinstance(value, str) and not value.strip():
            raise ValueError("PRIVATE_STORAGE_ROOT must contain a path")
        return value

    @model_validator(mode="after")
    def validate_auth(self):
        if self.auth_mode == "development":
            if self.app_env == "production":
                raise ValueError("Development authentication is prohibited in production")
            if len(self.dev_auth_token) < 32:
                raise ValueError("DEV_AUTH_TOKEN must contain at least 32 characters")
        elif not _is_https_url(self.supabase_url):
            raise ValueError("Supabase authentication requires an HTTPS SUPABASE_URL")
        if "*" in self.cors_origins:
            raise ValueError("Explicit CORS origins are required")
        return self

    @model_validator(mode="after")
    def validate_storage_and_ai(self) -> Self:
        if self.storage_backend == "local" and self.app_env == "production":
            raise ValueError("Local storage is prohibited in production")
        if self.storage_backend == "supabase" and (
            not _is_https_url(self.supabase_url)
            or not self.supabase_storage_bucket.strip()
            or not self.supabase_service_role_key.get_secret_value().strip()
        ):
            raise ValueError(
                "Supabase storage requires an HTTPS SUPABASE_URL, "
                "SUPABASE_STORAGE_BUCKET, and SUPABASE_SERVICE_ROLE_KEY"
            )
        if (
            self.ai_provider == "openai"
            and self.ai_external_processing_allowed
            and (
                not self.openai_api_key.get_secret_value().strip()
                or not self.openai_analysis_model.strip()
            )
        ):
            raise ValueError("External AI requires OPENAI_API_KEY and OPENAI_ANALYSIS_MODEL")
        if (
            self.ai_provider == "groq"
            and self.ai_external_processing_allowed
            and (
                not self.groq_api_key.get_secret_value().strip()
                or not self.groq_model.strip()
            )
        ):
            raise ValueError("Groq requires GROQ_API_KEY and GROQ_MODEL")
        if self.embedding_model == "" and not self.ai_external_processing_allowed:
            # The previous environment template left EMBEDDING_MODEL blank.
            self.embedding_model = EMBEDDING_MODEL
        if (self.embedding_model, self.embedding_dimensions) != (
            EMBEDDING_MODEL,
            EMBEDDING_DIMENSIONS,
        ):
            raise ValueError(
                f"EMBEDDING_MODEL and EMBEDDING_DIMENSIONS must be {EMBEDDING_MODEL} "
                f"and {EMBEDDING_DIMENSIONS}"
            )
        if self.ai_provider == "ollama":
            if not self.ollama_analysis_model.strip() or not self.ollama_embedding_model.strip():
                raise ValueError("OLLAMA_ANALYSIS_MODEL and OLLAMA_EMBEDDING_MODEL are required")
            parsed = urlsplit(self.ollama_base_url)
            host = parsed.hostname or ""
            try:
                loopback = ip_address(host).is_loopback
            except ValueError:
                loopback = host.lower() in {"localhost", "host.docker.internal"}
            try:
                port = parsed.port
            except ValueError:
                port = None
            if (
                parsed.scheme != "http"
                or not loopback
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or port is None
            ):
                raise ValueError(
                    "OLLAMA_BASE_URL must use HTTP on localhost or host.docker.internal"
                )
        return self


settings = Settings()
