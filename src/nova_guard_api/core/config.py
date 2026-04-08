from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Nova Guard API"
    database_url: str = Field(default="sqlite:///./nova_guard.db")
    jwt_secret: str = Field(default="dev-secret-change-in-production")
    jwt_algorithm: str = "HS256"
    # Map API key string -> allowed (keys are compared literally)
    api_keys: str = Field(
        default="test-admin-key,test-captain-key,test-operative-key,test-dealer-key",
        description="Comma-separated valid API keys",
    )
    webhook_url: str | None = Field(default=None)
    webhook_hmac_secret: str = Field(default="webhook-hmac-dev")
    rate_limit_per_minute: int = 300
    cors_origins: str = Field(default="*")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def parse_api_keys(raw: str) -> set[str]:
    return {k.strip() for k in raw.split(",") if k.strip()}
