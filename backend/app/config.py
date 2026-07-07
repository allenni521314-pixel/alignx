from __future__ import annotations
"""AlignX V1 -- Application configuration."""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(BACKEND_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AlignX"
    app_version: str = "1.0.0"
    environment: str = "development"
    enable_temp_login_code: bool = False
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./alignx_v2.db"
    database_url_sync: str = "sqlite:///./alignx_v2.db"
    redis_url: str = ""
    amazon_capture_provider: str = "scraperapi"
    scraperapi_key: str = ""
    scraperapi_base_url: str = "https://api.scraperapi.com"
    ai_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    qwen_api_key: str = ""
    qwen_base_url: str = "https://api.siliconflow.cn/v1"
    qwen_model: str = "Qwen/Qwen3-VL-8B-Instruct"
    auth_secret_key: str = "alignx-local-dev-secret-change-me"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket: str = "alignx-data"
    validation_budget_limit: float = 0.0
    sendgrid_api_key: str = ""
    report_from_email: str = "report@alignx.io"
    report_from_name: str = "AlignX"
    report_push_token: str = ""


@lru_cache
def get_settings() -> Settings:
    import os
    # Auto-convert DATABASE_URL for async SQLAlchemy
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url and db_url.startswith("postgresql://"):
        os.environ["DATABASE_URL"] = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    s = Settings()

    def read_local_secret(filename: str) -> str:
        key_file = os.path.join(BACKEND_DIR, filename)
        try:
            with open(key_file) as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""

    # Fallback: read ScraperAPI key from local file if env var is empty
    if not s.scraperapi_key:
        s.scraperapi_key = read_local_secret(".scraperapi_key")
    # Fallback: read DeepSeek key from local file
    if not s.deepseek_api_key:
        s.deepseek_api_key = read_local_secret(".deepseek_key")
    if not s.qwen_api_key:
        s.qwen_api_key = read_local_secret(".qwen_key")
    qwen_base_url = read_local_secret(".qwen_base_url")
    if qwen_base_url:
        s.qwen_base_url = qwen_base_url
    qwen_model = read_local_secret(".qwen_model")
    if qwen_model:
        s.qwen_model = qwen_model
    return s
