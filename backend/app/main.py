"""AlignX V1 — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import get_settings
from app.database import engine, async_session_factory
from app.core.proposition_engine import seed_propositions

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: seed proposition library. Shutdown: close connections."""
    # Seed the 49 propositions
    async with async_session_factory() as db:
        try:
            result = await seed_propositions(db)
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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.app_version}
