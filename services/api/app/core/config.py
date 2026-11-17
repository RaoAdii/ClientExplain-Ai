from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: Literal["development", "test", "production"] = "development"
    auth_mode: Literal["development", "supabase"] = "supabase"
    dev_auth_token: str = ""
    database_url: str
    redis_url: str = "redis://127.0.0.1:6379/0"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    supabase_url: str = ""

    @model_validator(mode="after")
    def validate_auth(self):
        if self.auth_mode == "development":
            if self.app_env == "production":
                raise ValueError("Development authentication is prohibited in production")
            if len(self.dev_auth_token) < 32:
                raise ValueError("DEV_AUTH_TOKEN must contain at least 32 characters")
        elif not self.supabase_url.startswith("https://"):
            raise ValueError("Supabase authentication requires an HTTPS SUPABASE_URL")
        if "*" in self.cors_origins:
            raise ValueError("Explicit CORS origins are required")
        return self


settings = Settings()
