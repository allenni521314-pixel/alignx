from __future__ import annotations
"""Competitor Analysis — ASIN-based 12-dimension analysis."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import CompetitorAnalysisRequest, CompetitorAnalysisResponse, PaginatedResponse
from app.services.competitor_analysis import analyze_competitor, list_reports, get_report
from app.api.deps import get_current_user_id

router = APIRouter(prefix="/api/v1/competitor-analysis", tags=["competitor-analysis"])


@router.post("/analyze", response_model=CompetitorAnalysisResponse)
async def analyze_endpoint(
    req: CompetitorAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_current_user_id),
):
    try:
        return await analyze_competitor(req, db, user_id=user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=PaginatedResponse)
async def list_competitor_analyses(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await list_reports(page, page_size, db, user_id=user_id)


@router.get("/{report_id}", response_model=CompetitorAnalysisResponse)
async def get_competitor_analysis(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    report = await get_report(report_id, db, user_id=user_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
