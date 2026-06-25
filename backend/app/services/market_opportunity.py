from __future__ import annotations
"""Market opportunity service — keyword → capture → AI → save."""

import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import MarketOpportunityReport, CaptureJob
from app.schemas import MarketOpportunityRequest, MarketOpportunityResponse
from app.core.scraperapi import ScraperAPIProvider
from app.core.ai import AI
from app.core.prompts import build_market_prompt, MARKET_OPPORTUNITY_SYSTEM
from app.constants import DEFAULT_USER_ID


async def analyze_market(req: MarketOpportunityRequest, db: AsyncSession, user_id: str | None = None) -> MarketOpportunityResponse:
    uid = user_id or DEFAULT_USER_ID
    capture = CaptureJob(
        user_id=uid,
        input_type="keyword", input_value=req.keyword, marketplace=req.marketplace,
        provider="scraperapi", status="running",
    )
    db.add(capture)
    await db.flush()

    provider = ScraperAPIProvider()
    result = await provider.capture_top20_by_keyword(req.keyword, req.marketplace)
    capture.status = result.capture_status
    capture.error_message = result.error_message
    await db.flush()

    ai_result = None
    if result.capture_status != "failed" and result.extracted_fields.get("results"):
        try:
            ai = AI()
            ai_data = await ai.complete_json(
                prompt=build_market_prompt(req.keyword, req.marketplace, result.extracted_fields),
                system=MARKET_OPPORTUNITY_SYSTEM,
            )
            ai_result = ai_data
        except Exception as e:
            ai_result = {"error": str(e), "partial": True}

    if ai_result and not ai_result.get("error"):
        seven_layer = ai_result.get("seven_layer", result.extracted_fields)
        report = MarketOpportunityReport(
            user_id=uid, keyword=req.keyword, marketplace=req.marketplace,
            opportunity_score=ai_result.get("opportunity_score"),
            entry_level=ai_result.get("entry_level"),
            market_entry_conclusion=ai_result.get("market_entry_conclusion"),
            top20_competition_strength=ai_result.get("top20_competition_strength"),
            price_band_judgment=ai_result.get("price_band_judgment"),
            main_risk=ai_result.get("main_risk"),
            next_action=ai_result.get("next_action"),
            seven_layer_result_json={
                **seven_layer,
                "product_categories": ai_result.get("product_categories", []),
                "best_opportunity_category": ai_result.get("best_opportunity_category", ""),
                "top20_asins": result.extracted_fields.get("results", []),
            },
        )
    else:
        report = MarketOpportunityReport(
            user_id=uid, keyword=req.keyword, marketplace=req.marketplace,
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
    q = select(MarketOpportunityReport).order_by(desc(MarketOpportunityReport.created_at)).offset(offset).limit(page_size)
    r = await db.execute(q)
    items = [_enrich_report(x) for x in r.scalars().all()]
    total = len((await db.execute(select(MarketOpportunityReport))).scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_report(report_id: str, db: AsyncSession) -> MarketOpportunityResponse | None:
    r = await db.execute(select(MarketOpportunityReport).where(MarketOpportunityReport.id == report_id))
    report = r.scalar_one_or_none()
    return _enrich_report(report) if report else None


def _enrich_report(report: MarketOpportunityReport) -> MarketOpportunityResponse:
    """Extract product_categories and best_opportunity_category from seven_layer_result_json."""
    resp = MarketOpportunityResponse.model_validate(report, from_attributes=True)
    sl = report.seven_layer_result_json or {}
    if isinstance(sl, dict):
        if "product_categories" in sl:
            resp.product_categories = sl["product_categories"]
        if "best_opportunity_category" in sl:
            resp.best_opportunity_category = sl["best_opportunity_category"]
    return resp
