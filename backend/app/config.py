from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CodeSentry"
    database_url: str = "sqlite:///./codesentry.db"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
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
