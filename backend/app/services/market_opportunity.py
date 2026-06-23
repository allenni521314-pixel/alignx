"""Market opportunity service — keyword → capture → AI → save."""

import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import MarketOpportunityReport, CaptureJob
from app.schemas import MarketOpportunityRequest, MarketOpportunityResponse
from app.core.scraperapi import ScraperAPIProvider
from app.core.capture import MIN_DIAGNOSIS_FIELDS


async def analyze_market(
    req: MarketOpportunityRequest,
    db: AsyncSession,
) -> MarketOpportunityResponse:
    """Run full market opportunity pipeline."""

    # 1. Start capture job
    capture = CaptureJob(
        input_type="keyword",
        input_value=req.keyword,
        marketplace=req.marketplace,
        provider="scraperapi",
        status="running",
    )
    db.add(capture)
    await db.flush()

    # 2. Capture Top 20
    provider = ScraperAPIProvider()
    result = await provider.capture_top20_by_keyword(req.keyword, req.marketplace)

    # Update capture job
    capture.status = result.capture_status
    capture.raw_response_path = json.dumps(result.raw_response) if result.raw_response else None
    capture.error_message = result.error_message
    await db.flush()

    # 3. Build AI prompt (placeholder — Phase 3 wires real AI)
    report = MarketOpportunityReport(
        user_id="default",  # TODO: real auth
        keyword=req.keyword,
        marketplace=req.marketplace,
        category=None,  # populated by AI
        subcategory=None,
        category_confidence=None,
        opportunity_score=None,
        entry_level="pending",
        market_entry_conclusion=f"已抓取 {result.extracted_fields.get('total', 0)} 个 ASIN，等待 AI 分析",
        top20_competition_strength="pending",
        seven_layer_result_json=result.extracted_fields if result.capture_status != "failed" else {"error": result.error_message},
    )
    db.add(report)
    await db.flush()

    return MarketOpportunityResponse.model_validate(report, from_attributes=True)


async def list_reports(
    page: int,
    page_size: int,
    db: AsyncSession,
) -> dict:
    """List historical market opportunity reports."""
    offset = (page - 1) * page_size
    q = (
        select(MarketOpportunityReport)
        .order_by(desc(MarketOpportunityReport.created_at))
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(q)
    items = [MarketOpportunityResponse.model_validate(r, from_attributes=True) for r in result.scalars().all()]

    # Total count
    count_q = select(MarketOpportunityReport)
    count_result = await db.execute(count_q)
    total = len(count_result.scalars().all())

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_report(report_id: str, db: AsyncSession) -> MarketOpportunityResponse | None:
    """Get a single report."""
    result = await db.execute(
        select(MarketOpportunityReport).where(MarketOpportunityReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        return None
    return MarketOpportunityResponse.model_validate(report, from_attributes=True)
