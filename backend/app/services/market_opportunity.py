"""Market opportunity service — keyword → capture → AI → save."""

import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import MarketOpportunityReport, CaptureJob
from app.schemas import MarketOpportunityRequest, MarketOpportunityResponse
from app.core.scraperapi import ScraperAPIProvider
from app.core.ai import AI
from app.core.prompts import build_market_prompt, MARKET_OPPORTUNITY_SYSTEM


async def analyze_market(
    req: MarketOpportunityRequest,
    db: AsyncSession,
) -> MarketOpportunityResponse:
    """Run full market opportunity pipeline: capture → AI → save."""

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

    capture.status = result.capture_status
    capture.raw_response_path = json.dumps(result.raw_response) if result.raw_response else None
    capture.error_message = result.error_message
    capture.finished_at = None  # would be datetime.utcnow()
    await db.flush()

    # 3. AI Analysis
    ai_result = None
    if result.capture_status != "failed" and result.extracted_fields.get("results"):
        try:
            ai = AI()
            prompt = build_market_prompt(
                req.keyword,
                req.marketplace,
                result.extracted_fields,
            )
            ai_data = await ai.complete_json(
                prompt=prompt,
                system=MARKET_OPPORTUNITY_SYSTEM,
            )
            ai_result = ai_data
        except Exception as e:
            ai_result = {"error": str(e), "partial": True}

    # 4. Save report
    if ai_result and not ai_result.get("error"):
        seven_layer = ai_result.get("seven_layer", result.extracted_fields)
        report = MarketOpportunityReport(
            user_id="default",
            keyword=req.keyword,
            marketplace=req.marketplace,
            opportunity_score=ai_result.get("opportunity_score"),
            entry_level=ai_result.get("entry_level"),
            market_entry_conclusion=ai_result.get("market_entry_conclusion"),
            top20_competition_strength=ai_result.get("top20_competition_strength"),
            price_band_judgment=ai_result.get("price_band_judgment"),
            main_risk=ai_result.get("main_risk"),
            next_action=ai_result.get("next_action"),
            seven_layer_result_json=seven_layer,
        )
    else:
        report = MarketOpportunityReport(
            user_id="default",
            keyword=req.keyword,
            marketplace=req.marketplace,
            entry_level="pending",
            market_entry_conclusion=(
                f"已抓取 {result.extracted_fields.get('total', 0)} 个 ASIN"
                if result.capture_status != "failed"
                else f"抓取失败: {result.error_message}"
            ),
            seven_layer_result_json=result.extracted_fields if result.capture_status != "failed" else {"error": result.error_message},
        )

    db.add(report)
    await db.flush()

    return MarketOpportunityResponse.model_validate(report, from_attributes=True)


async def list_reports(page: int, page_size: int, db: AsyncSession) -> dict:
    offset = (page - 1) * page_size
    q = (
        select(MarketOpportunityReport)
        .order_by(desc(MarketOpportunityReport.created_at))
        .offset(offset).limit(page_size)
    )
    result = await db.execute(q)
    items = [MarketOpportunityResponse.model_validate(r, from_attributes=True) for r in result.scalars().all()]
    count_q = select(MarketOpportunityReport)
    count_result = await db.execute(count_q)
    total = len(count_result.scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_report(report_id: str, db: AsyncSession) -> MarketOpportunityResponse | None:
    result = await db.execute(select(MarketOpportunityReport).where(MarketOpportunityReport.id == report_id))
    report = result.scalar_one_or_none()
    return MarketOpportunityResponse.model_validate(report, from_attributes=True) if report else None
