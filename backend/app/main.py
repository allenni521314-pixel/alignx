from __future__ import annotations
"""AlignX V1 — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import get_settings
from app.database import engine, async_session_factory, init_db
from app.models import User
from app.constants import DEFAULT_USER_ID
from app.services.proposition_library import ensure_proposition_library

settings = get_settings()


async def ensure_default_user(db):
    """Get or create the default user for unauthenticated local dev."""
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == DEFAULT_USER_ID))
    user = result.scalar_one_or_none()
    if not user:
        user = User(id=DEFAULT_USER_ID, email="local@alignx.dev", name="Local Dev")
        db.add(user)
        await db.flush()
        print("[startup] Created default user")
    return user


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables, default user, seed proposition library."""
    await init_db()
    print("[startup] Database tables created")

    async with async_session_factory() as db:
        await ensure_default_user(db)
        try:
            result = await ensure_proposition_library(db)
            await db.commit()
            if result["propositions_created"] > 0:
                print(f"[startup] Seeded {result['propositions_created']} propositions")
        except Exception as e:
            print(f"[startup] Proposition seed skipped: {e}")

    yield

    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://alignxagent.netlify.app",
        "https://alignx-vi.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.app_version}
