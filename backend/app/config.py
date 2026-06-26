from __future__ import annotations
"""AlignX V1 -- Application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AlignX"
    app_version: str = "1.0.0"
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
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket: str = "alignx-data"
    validation_budget_limit: float = 0.0


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # Fallback: read ScraperAPI key from local file if env var is empty
    if not s.scraperapi_key:
        import os
        key_file = os.path.join(os.path.dirname(__file__), "..", ".scraperapi_key")
        try:
            with open(key_file) as f:
                s.scraperapi_key = f.read().strip()
        except FileNotFoundError:
            pass
    # Fallback: read DeepSeek key from local file
    if not s.deepseek_api_key:
        import os
        key_file = os.path.join(os.path.dirname(__file__), "..", ".deepseek_key")
        try:
            with open(key_file) as f:
                s.deepseek_api_key = f.read().strip()
        except FileNotFoundError:
            pass
    if not s.qwen_api_key:
        import os
        key_file = os.path.join(os.path.dirname(__file__), "..", ".qwen_key")
        try:
            with open(key_file) as f:
                s.qwen_api_key = f.read().strip()
        except FileNotFoundError:
            pass
    return s
