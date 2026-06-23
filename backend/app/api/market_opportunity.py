"""Market Opportunity — keyword-based market analysis."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    MarketOpportunityRequest,
    MarketOpportunityResponse,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/v1/market-opportunity", tags=["market-opportunity"])


@router.post("/analyze", response_model=MarketOpportunityResponse)
async def analyze_market_opportunity(
    req: MarketOpportunityRequest,
    db: AsyncSession = Depends(get_db),
):
    """Input keyword → crawl Top20 ASINs → AI generates 7-layer market opportunity report."""
    # TODO: Phase 2 — integrate capture + AI analysis
    pass


@router.get("/history", response_model=PaginatedResponse)
async def list_market_opportunities(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List historical market opportunity reports."""
    pass


@router.get("/{report_id}", response_model=MarketOpportunityResponse)
async def get_market_opportunity(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single market opportunity report by ID."""
    pass
