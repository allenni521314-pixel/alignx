from __future__ import annotations
"""Lifecycle API — detect stage, get strategy, trigger alerts."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.lifecycle_engine import detect_lifecycle, apply_lifecycle
from app.api.deps import get_current_user_id

router = APIRouter(prefix="/api/v1/lifecycle", tags=["lifecycle"])


@router.get("/{asin}")
async def get_lifecycle(asin: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    """Detect lifecycle stage for an ASIN. Returns stage + strategy + alerts."""
    return await detect_lifecycle(asin, db, user_id=user_id)


@router.post("/{asin}/apply")
async def apply(asin: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    """Apply detected lifecycle to profile and return result."""
    return await apply_lifecycle(asin, db, user_id=user_id)
