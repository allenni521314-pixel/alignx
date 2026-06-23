"""Competitor Analysis — ASIN-based 12-dimension analysis."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import CompetitorAnalysisRequest, CompetitorAnalysisResponse, PaginatedResponse

router = APIRouter(prefix="/api/v1/competitor-analysis", tags=["competitor-analysis"])


@router.post("/analyze", response_model=CompetitorAnalysisResponse)
async def analyze_competitor(
    req: CompetitorAnalysisRequest,
    db: AsyncSession = Depends(get_db),
):
    """Input ASIN/URL → crawl product page → AI 12-dimension competitor analysis."""
    pass


@router.get("/history", response_model=PaginatedResponse)
async def list_competitor_analyses(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List historical competitor analysis reports."""
    pass


@router.get("/{report_id}", response_model=CompetitorAnalysisResponse)
async def get_competitor_analysis(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single competitor analysis report by ID."""
    pass
