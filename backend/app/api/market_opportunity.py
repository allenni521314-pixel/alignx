from __future__ import annotations
"""Market Opportunity — keyword-based market analysis."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import MarketOpportunityRequest, MarketOpportunityResponse, PaginatedResponse
from app.services.market_opportunity import analyze_market, list_reports, get_report
from app.api.deps import get_current_user_id

router = APIRouter(prefix="/api/v1/market-opportunity", tags=["market-opportunity"])


@router.post("/analyze", response_model=MarketOpportunityResponse)
async def analyze_market_opportunity(
    req: MarketOpportunityRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_current_user_id),
):
    """Input keyword → crawl Top20 ASINs → AI generates 7-layer market opportunity report."""
    try:
        return await analyze_market(req, db, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=PaginatedResponse)
async def list_market_opportunities(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    return await list_reports(page, page_size, db)


@router.get("/{report_id}", response_model=MarketOpportunityResponse)
async def get_market_opportunity(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    report = await get_report(report_id, db)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
