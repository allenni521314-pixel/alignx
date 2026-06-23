from __future__ import annotations
"""Competitor Analysis — ASIN-based 12-dimension analysis."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import CompetitorAnalysisRequest, CompetitorAnalysisResponse, PaginatedResponse
from app.services.competitor_analysis import analyze_competitor, list_reports, get_report

router = APIRouter(prefix="/api/v1/competitor-analysis", tags=["competitor-analysis"])


@router.post("/analyze", response_model=CompetitorAnalysisResponse)
async def analyze_competitor_endpoint(
    req: CompetitorAnalysisRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await analyze_competitor(req, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=PaginatedResponse)
async def list_competitor_analyses(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    return await list_reports(page, page_size, db)


@router.get("/{report_id}", response_model=CompetitorAnalysisResponse)
async def get_competitor_analysis(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    report = await get_report(report_id, db)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
