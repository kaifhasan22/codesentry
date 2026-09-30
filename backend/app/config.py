from functools import lru_cache
import secrets
from typing import Literal
from pydantic import Field, model_validator
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CodeSentry"
    database_url: str = "sqlite:///./codesentry.db"
    redis_url: str = "redis://redis:6379/0"
    worker_queue: str = Field(default="celery", pattern=r"^[A-Za-z0-9_-]{1,80}$")
    environment: Literal["development", "production"] = "development"
    jwt_secret: str = ""
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_minutes: int = Field(default=60, ge=1, le=1440)
    cors_origins: str = "http://localhost:5173"
    max_active_scans_per_user: int = Field(default=2, ge=1, le=10)

    @model_validator(mode="after")
    def secure_configuration(self):
        weak = self.jwt_secret in {"", "dev-only-change-me", "change-me-in-production"} or len(self.jwt_secret) < 32
        if self.environment == "production" and weak:
            raise ValueError("Production requires an explicit JWT_SECRET of at least 32 characters.")
        if weak:
            self.jwt_secret = secrets.token_urlsafe(48)
        for origin in self.cors_origin_list:
            parsed = urlsplit(origin)
            if (parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username
                    or parsed.password or parsed.path or parsed.query or parsed.fragment or "*" in origin):
                raise ValueError("CORS origins must be explicit HTTP(S) origins.")
            if self.environment == "production" and parsed.scheme != "https":
                raise ValueError("Production CORS origins must use HTTPS.")
        return self

    @property
    def cors_origin_list(self):
        return [v.strip() for v in self.cors_origins.split(",") if v.strip()]
    allowed_github_hosts: str = "github.com,www.github.com"
    max_upload_bytes: int = 25 * 1024 * 1024
    scan_root: str = "/tmp/codesentry"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_github_host_set(self) -> set[str]:
        return {x.strip().lower() for x in self.allowed_github_hosts.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
