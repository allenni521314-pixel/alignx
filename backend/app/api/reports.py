from __future__ import annotations
"""Reports API — yesterday report + today decisions."""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.services.daily_report_push import send_all_daily_reports
from app.services.reports import generate_yesterday_report, generate_today_decisions
from app.api.deps import get_current_user_id

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])
settings = get_settings()


@router.get("/yesterday")
async def yesterday_report(db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    return await generate_yesterday_report(db, user_id=user_id)


@router.get("/today")
async def today_decisions(db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    return await generate_today_decisions(db, user_id=user_id)


@router.post("/daily-push")
async def daily_report_push(
    x_report_push_token: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    if not settings.report_push_token:
        raise HTTPException(status_code=503, detail="未设置")
    if not secrets.compare_digest(x_report_push_token, settings.report_push_token):
        raise HTTPException(status_code=403, detail="未授权")
    return await send_all_daily_reports(db)
