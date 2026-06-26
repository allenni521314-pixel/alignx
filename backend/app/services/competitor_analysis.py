from __future__ import annotations
"""Competitor analysis service — ASIN → capture → AI 12-dimension analysis."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import CompetitorAnalysisReport
from app.schemas import CompetitorAnalysisRequest, CompetitorAnalysisResponse
from app.services.access import require_user_id, user_scoped
from app.services.listing_ai_pipeline import extract_asin, run_competitor_listing_ai_pipeline


async def analyze_competitor(req: CompetitorAnalysisRequest, db: AsyncSession, user_id: str | None = None) -> CompetitorAnalysisResponse:
    uid = require_user_id(user_id)
    asin = extract_asin(req.asin)
    if not asin and req.product_url:
        asin = extract_asin(req.product_url)
    if not asin:
        raise ValueError("Could not determine ASIN from input")

    pipeline_result = await run_competitor_listing_ai_pipeline(
        asin=asin,
        marketplace=req.marketplace,
        db=db,
        user_id=uid,
        product_url=req.product_url,
    )
    listing_data = pipeline_result.listing_data or {}
    ai_result = pipeline_result.ai_result

    title = listing_data.get("title")
    brand = None
    pd = listing_data.get("product_details")
    if isinstance(pd, dict):
        brand = pd.get("Brand")

    if ai_result and not pipeline_result.ai_error:
        report = CompetitorAnalysisReport(
            user_id=uid, asin=asin, product_url=req.product_url,
            marketplace=req.marketplace, product_title=title, brand=brand,
            price=listing_data.get("price"),
            rating=listing_data.get("rating"),
            review_count=listing_data.get("review_count"),
            overall_judgment=ai_result.get("overall_judgment"),
            main_strengths=ai_result.get("main_strengths"),
            main_weaknesses=ai_result.get("main_weaknesses"),
            attack_points=ai_result.get("attack_points"),
            worth_benchmarking=ai_result.get("worth_benchmarking"),
            twelve_dimension_result_json=ai_result.get("twelve_dimension", {}),
        )
    else:
        report = CompetitorAnalysisReport(
            user_id=uid, asin=asin, product_url=req.product_url,
            marketplace=req.marketplace, product_title=title, brand=brand,
            price=listing_data.get("price"),
            rating=listing_data.get("rating"),
            review_count=listing_data.get("review_count"),
            overall_judgment=(
                "数据已抓取，AI 分析待完成"
                if listing_data
                else f"抓取失败: {pipeline_result.capture_error}"
            ),
        )

    db.add(report)
    await db.flush()
    return CompetitorAnalysisResponse.model_validate(report, from_attributes=True)


async def list_reports(page: int, page_size: int, db: AsyncSession, user_id: str | None = None) -> dict:
    uid = require_user_id(user_id)
    offset = (page - 1) * page_size
    q = user_scoped(select(CompetitorAnalysisReport), CompetitorAnalysisReport, uid)
    q = q.order_by(desc(CompetitorAnalysisReport.created_at)).offset(offset).limit(page_size)
    r = await db.execute(q)
    items = [CompetitorAnalysisResponse.model_validate(x, from_attributes=True) for x in r.scalars().all()]
    total_q = user_scoped(select(CompetitorAnalysisReport), CompetitorAnalysisReport, uid)
    total = len((await db.execute(total_q)).scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_report(report_id: str, db: AsyncSession, user_id: str | None = None) -> CompetitorAnalysisResponse | None:
    uid = require_user_id(user_id)
    q = user_scoped(select(CompetitorAnalysisReport), CompetitorAnalysisReport, uid)
    r = await db.execute(q.where(CompetitorAnalysisReport.id == report_id))
    report = r.scalar_one_or_none()
    return CompetitorAnalysisResponse.model_validate(report, from_attributes=True) if report else None
