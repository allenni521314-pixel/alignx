"""AlignX V1 — Application configuration."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──
    app_name: str = "AlignX"
    app_version: str = "1.0.0"
    debug: bool = False

    # ── Database ──
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/alignx"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/alignx"

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"

    # ── Object Storage (S3-compatible) ──
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "alignx"
    s3_region: str = "us-east-1"

    # ── Amazon Capture ──
    amazon_capture_provider: str = "scraperapi"
    scraperapi_key: str = ""
    scraperapi_base_url: str = "https://api.scraperapi.com"

    # ── AI Providers ──
    ai_default_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # ── Auth ──
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # ── CORS ──
    cors_origins: list[str] = ["http://localhost:5173", "https://alignxagent.netlify.app"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
