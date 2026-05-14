from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Bookkeeping Tax API"
    api_prefix: str = "/api"
    environment: str = Field(default="development", alias="API_ENV")
    database_url: str = Field(
        default="postgresql+psycopg://bookkeeping:bookkeeping@localhost:5432/bookkeeping_tax",
        alias="API_DATABASE_URL",
    )
    secret_key: str = Field(
        default="change-me-development-key-with-at-least-32-bytes",
        alias="API_SECRET_KEY",
    )
    allowed_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3100,http://127.0.0.1:3100,http://web:3000",
        alias="API_ALLOWED_ORIGINS",
    )
    allowed_origin_regex: str | None = Field(
        default=r"^https?://(localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})(?::\d+)?$",
        alias="API_ALLOWED_ORIGIN_REGEX",
    )
    access_token_expire_minutes: int = Field(default=60 * 8, alias="API_ACCESS_TOKEN_EXPIRE_MINUTES")
    document_storage_path: str = Field(
        default="./storage/documents",
        alias="API_DOCUMENT_STORAGE_PATH",
    )
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    journal_ai_enabled: bool = Field(default=True, alias="API_JOURNAL_AI_ENABLED")
    journal_ai_web_search_enabled: bool = Field(default=True, alias="API_JOURNAL_AI_WEB_SEARCH_ENABLED")
    journal_ai_default_model: str = Field(default="gpt-5.4-mini", alias="API_JOURNAL_AI_DEFAULT_MODEL")
    journal_ai_max_file_count: int = Field(default=5, alias="API_JOURNAL_AI_MAX_FILE_COUNT")
    journal_ai_max_file_size_bytes: int = Field(default=10 * 1024 * 1024, alias="API_JOURNAL_AI_MAX_FILE_SIZE_BYTES")
    journal_ai_max_total_size_bytes: int = Field(default=25 * 1024 * 1024, alias="API_JOURNAL_AI_MAX_TOTAL_SIZE_BYTES")
    journal_ai_request_timeout_seconds: float = Field(default=90.0, alias="API_JOURNAL_AI_REQUEST_TIMEOUT_SECONDS")
    log_level: str = Field(default="INFO", alias="API_LOG_LEVEL")
    log_json: bool = Field(default=True, alias="API_LOG_JSON")
    healthcheck_timeout_seconds: float = Field(default=2.0, alias="API_HEALTHCHECK_TIMEOUT_SECONDS")
    metrics_enabled: bool = Field(default=True, alias="API_METRICS_ENABLED")
    alert_webhook_url: str | None = Field(default=None, alias="API_ALERT_WEBHOOK_URL")
    alert_cooldown_seconds: int = Field(default=300, alias="API_ALERT_COOLDOWN_SECONDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
