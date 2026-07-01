from __future__ import annotations
"""Market opportunity service — keyword → capture → AI → save."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import MarketOpportunityReport
from app.schemas import MarketOpportunityRequest, MarketOpportunityResponse
from app.services.access import require_user_id, user_scoped
from app.services.market_ai_pipeline import run_market_ai_pipeline


async def analyze_market(req: MarketOpportunityRequest, db: AsyncSession, user_id: str | None = None) -> MarketOpportunityResponse:
    uid = require_user_id(user_id)
    pipeline_result = await run_market_ai_pipeline(
        keyword=req.keyword,
        marketplace=req.marketplace,
        db=db,
        user_id=uid,
    )
    ai_result = pipeline_result.ai_result
    captured_fields = pipeline_result.captured_fields

    if ai_result and not pipeline_result.ai_error:
        seven_layer = ai_result.get("seven_layer", captured_fields)
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
                "top20_asins": captured_fields.get("results", []),
            },
        )
    else:
        report = MarketOpportunityReport(
            user_id=uid, keyword=req.keyword, marketplace=req.marketplace,
            entry_level="pending",
            market_entry_conclusion=(
                f"已抓取 {captured_fields.get('total', 0)} 个 ASIN"
                if pipeline_result.capture_status != "failed"
                else f"抓取失败: {pipeline_result.capture_error}"
            ),
            seven_layer_result_json=captured_fields if pipeline_result.capture_status != "failed" else {"error": pipeline_result.capture_error},
        )

    db.add(report)
    await db.flush()
    return _enrich_report(report)


async def list_reports(page: int, page_size: int, db: AsyncSession, user_id: str | None = None) -> dict:
    uid = require_user_id(user_id)
    offset = (page - 1) * page_size
    q = user_scoped(select(MarketOpportunityReport), MarketOpportunityReport, uid)
    q = q.order_by(desc(MarketOpportunityReport.created_at)).offset(offset).limit(page_size)
    r = await db.execute(q)
    items = [_enrich_report(x) for x in r.scalars().all()]
    total_q = user_scoped(select(MarketOpportunityReport), MarketOpportunityReport, uid)
    total = len((await db.execute(total_q)).scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_report(report_id: str, db: AsyncSession, user_id: str | None = None) -> MarketOpportunityResponse | None:
    uid = require_user_id(user_id)
    q = user_scoped(select(MarketOpportunityReport), MarketOpportunityReport, uid)
    r = await db.execute(q.where(MarketOpportunityReport.id == report_id))
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
