"""AlignX V1 — Application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """AlignX settings loaded from env vars / .env file."""

    # App
    app_name: str = "AlignX"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/alignx"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/alignx"

    # Redis
    redis_url: str = "redis://localhost:***@lru_cache
def get_settings() -> Settings:
    return Settings()
