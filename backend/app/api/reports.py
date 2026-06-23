from __future__ import annotations
"""Reports API — yesterday report + today decisions."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.reports import generate_yesterday_report, generate_today_decisions

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/yesterday")
async def yesterday_report(db: AsyncSession = Depends(get_db)):
    """Aggregate yesterday's data across all ASINs."""
    return await generate_yesterday_report(db)


@router.get("/today")
async def today_decisions(db: AsyncSession = Depends(get_db)):
    """Generate today's recommended actions."""
    return await generate_today_decisions(db)
