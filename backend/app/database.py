from __future__ import annotations
"""AlignX V1 — Async database engine and session.

Supports both PostgreSQL (asyncpg) and SQLite (aiosqlite) for local dev.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from app.config import get_settings

settings = get_settings()

is_sqlite = "sqlite" in settings.database_url

engine_kwargs = {"echo": settings.debug}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(
    settings.database_url,
    **engine_kwargs,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables (for SQLite / dev). In production use Alembic."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if is_sqlite:
            result = await conn.execute(text("PRAGMA table_info(listing_snapshots)"))
            columns = {row[1] for row in result.fetchall()}
            if "ocr_image_texts" not in columns:
                await conn.execute(text("ALTER TABLE listing_snapshots ADD COLUMN ocr_image_texts JSON"))


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
