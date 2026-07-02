from __future__ import annotations
"""AlignX V1 — Async database engine and session.

Supports both PostgreSQL (asyncpg) and SQLite (aiosqlite) for local dev.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

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
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if is_sqlite:
            await _add_sqlite_column(conn, "listing_snapshots", "ocr_image_texts", "JSON")
            await _add_sqlite_column(conn, "listing_snapshots", "ai_readability_score_json", "JSON")
            await _add_sqlite_column(conn, "listing_snapshots", "ai_readability_score_version", "VARCHAR(64)")
            await _add_sqlite_column(conn, "asins", "sp_api_product_type", "VARCHAR(128)")
            await _add_sqlite_column(conn, "asins", "sp_api_product_type_version", "VARCHAR(64)")
            await _add_sqlite_column(conn, "asins", "sp_api_product_type_schema_version", "VARCHAR(64)")
            await _add_sqlite_column(conn, "asins", "sp_api_product_type_synced_at", "DATETIME")
            await _add_sqlite_column(conn, "conversion_diagnoses", "ai_readability_score_json", "JSON")
            await _add_sqlite_column(conn, "conversion_diagnoses", "ai_readability_score_version", "VARCHAR(64)")
            await _add_sqlite_column(conn, "execution_records", "user_id", "VARCHAR(32) NOT NULL DEFAULT '00000000default0000000000000000'")
            await _add_sqlite_column(conn, "asin_operation_profiles", "marketplace", "VARCHAR(16) NOT NULL DEFAULT 'amazon.com'")
            await _add_sqlite_column(conn, "report_upload_staging_records", "asin_id", "VARCHAR(32)")
            await _add_sqlite_column(conn, "report_upload_staging_records", "asin_attribution_status", "VARCHAR(32) NOT NULL DEFAULT 'missing'")
            await _add_sqlite_column(conn, "report_upload_staging_records", "validation_task_id", "VARCHAR(32)")
            await _add_sqlite_column(conn, "report_upload_staging_records", "execution_record_id", "VARCHAR(32)")
            await _add_sqlite_column(conn, "ai_call_logs", "analysis_mode", "VARCHAR(64)")
            await _add_sqlite_column(conn, "ai_call_logs", "trust_meta", "JSON")
            await _add_sqlite_column(conn, "ai_call_logs", "ai_trace", "JSON")
            await _add_sqlite_column(conn, "validation_results", "user_id", "VARCHAR(32) NOT NULL DEFAULT '00000000default0000000000000000'")
            await _ensure_sqlite_profile_tenant_unique(conn)


async def _sqlite_columns(conn, table_name: str) -> set[str]:
    result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
    return {row[1] for row in result.fetchall()}


async def _add_sqlite_column(conn, table_name: str, column_name: str, definition: str) -> None:
    table_exists = await conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name"
    ), {"table_name": table_name})
    if not table_exists.fetchone():
        return
    columns = await _sqlite_columns(conn, table_name)
    if column_name not in columns:
        try:
            await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))
        except OperationalError as exc:
            if "duplicate column name" in str(exc).lower():
                return
            raise


async def _ensure_sqlite_profile_tenant_unique(conn) -> None:
    table_exists = await conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='asin_operation_profiles'"
    ))
    if not table_exists.fetchone():
        return
    result = await conn.execute(text("PRAGMA index_list(asin_operation_profiles)"))
    indexes = result.fetchall()
    has_legacy_asin_unique = False
    for row in indexes:
        index_name = row[1]
        is_unique = bool(row[2])
        if not is_unique:
            continue
        cols_result = await conn.execute(text(f"PRAGMA index_info({index_name})"))
        cols = [col[2] for col in cols_result.fetchall()]
        if cols == ["asin"]:
            has_legacy_asin_unique = True
            break

    if not has_legacy_asin_unique:
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_asin_operation_profiles_asin "
            "ON asin_operation_profiles (asin)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_asin_operation_profiles_marketplace "
            "ON asin_operation_profiles (marketplace)"
        ))
        return

    await conn.execute(text("""
        CREATE TABLE asin_operation_profiles_new (
            id VARCHAR(32) NOT NULL,
            user_id VARCHAR(32) NOT NULL,
            asin VARCHAR(16) NOT NULL,
            marketplace VARCHAR(16) NOT NULL DEFAULT 'amazon.com',
            product_title TEXT,
            category VARCHAR(255),
            lifecycle_stage VARCHAR(32),
            total_validation_count INTEGER NOT NULL DEFAULT 0,
            effective_count INTEGER NOT NULL DEFAULT 0,
            ineffective_count INTEGER NOT NULL DEFAULT 0,
            interfered_count INTEGER NOT NULL DEFAULT 0,
            insufficient_data_count INTEGER NOT NULL DEFAULT 0,
            successful_propositions_json JSON,
            failed_propositions_json JSON,
            repeated_failure_patterns_json JSON,
            current_main_problem TEXT,
            next_recommended_proposition VARCHAR(16),
            asin_learning_summary TEXT,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(user_id) REFERENCES users (id)
        )
    """))
    await conn.execute(text("""
        INSERT INTO asin_operation_profiles_new (
            id, user_id, asin, marketplace, product_title, category, lifecycle_stage,
            total_validation_count, effective_count, ineffective_count, interfered_count,
            insufficient_data_count, successful_propositions_json, failed_propositions_json,
            repeated_failure_patterns_json, current_main_problem, next_recommended_proposition,
            asin_learning_summary, updated_at
        )
        SELECT
            id, user_id, asin, COALESCE(marketplace, 'amazon.com'), product_title, category, lifecycle_stage,
            total_validation_count, effective_count, ineffective_count, interfered_count,
            insufficient_data_count, successful_propositions_json, failed_propositions_json,
            repeated_failure_patterns_json, current_main_problem, next_recommended_proposition,
            asin_learning_summary, updated_at
        FROM asin_operation_profiles
    """))
    await conn.execute(text("DROP TABLE asin_operation_profiles"))
    await conn.execute(text("ALTER TABLE asin_operation_profiles_new RENAME TO asin_operation_profiles"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_asin_operation_profiles_user_id ON asin_operation_profiles (user_id)"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_asin_operation_profiles_asin ON asin_operation_profiles (asin)"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_asin_operation_profiles_marketplace ON asin_operation_profiles (marketplace)"))


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
