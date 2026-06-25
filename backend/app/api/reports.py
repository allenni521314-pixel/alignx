from __future__ import annotations
"""Reports API — yesterday report + today decisions."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.reports import generate_yesterday_report, generate_today_decisions
from app.api.deps import get_current_user_id

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/yesterday")
async def yesterday_report(db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    return await generate_yesterday_report(db, user_id=user_id)


@router.get("/today")
async def today_decisions(db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    return await generate_today_decisions(db, user_id=user_id)
