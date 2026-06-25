from __future__ import annotations
"""Competitor analysis service — ASIN → capture → AI 12-dimension analysis."""

import json
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import CompetitorAnalysisReport, CaptureJob, ListingSnapshot
from app.schemas import CompetitorAnalysisRequest, CompetitorAnalysisResponse
from app.core.scraperapi import ScraperAPIProvider
from app.core.ai import AI
from app.core.prompts import build_competitor_prompt, COMPETITOR_SYSTEM
from app.constants import DEFAULT_USER_ID


def _extract_asin(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    direct = re.fullmatch(r"[A-Z0-9]{10}", text.upper())
    if direct:
        return direct.group(0)
    match = re.search(r"/(?:dp|gp/product|product-reviews)/([A-Z0-9]{10})(?:[/?#]|$)", text, re.I)
    return match.group(1).upper() if match else None


async def analyze_competitor(req: CompetitorAnalysisRequest, db: AsyncSession, user_id: str | None = None) -> CompetitorAnalysisResponse:
    uid = user_id or DEFAULT_USER_ID
    asin = _extract_asin(req.asin)
    if not asin and req.product_url:
        asin = _extract_asin(req.product_url)
    if not asin:
        raise ValueError("Could not determine ASIN from input")

    capture = CaptureJob(
        user_id=uid,
        input_type="asin", input_value=asin, marketplace=req.marketplace,
        provider="scraperapi", status="running",
    )
    db.add(capture)
    await db.flush()

    provider = ScraperAPIProvider()
    result = await provider.capture_product_by_asin(asin, req.marketplace)
    capture.status = result.capture_status
    capture.error_message = result.error_message
    await db.flush()

    # 2. Save listing snapshot
    if result.capture_status != "failed":
        snapshot = ListingSnapshot(
            capture_job_id=capture.id, asin=asin, marketplace=req.marketplace,
            title=result.extracted_fields.get("title"),
            price=result.extracted_fields.get("price"),
            price_value=result.extracted_fields.get("price_value"),
            rating=result.extracted_fields.get("rating"),
            review_count=result.extracted_fields.get("review_count"),
            main_image=result.extracted_fields.get("main_image"),
            image_urls=result.extracted_fields.get("image_urls"),
            bullet_points=result.extracted_fields.get("bullet_points"),
            aplus_content=result.extracted_fields.get("aplus_content"),
            product_details=result.extracted_fields.get("product_details"),
            ocr_image_texts=result.extracted_fields.get("ocr_image_texts"),
            parse_status=result.capture_status,
            missing_fields=result.missing_fields,
            field_completeness_score=result.data_completeness_score,
        )
        db.add(snapshot)
        await db.flush()

    # 3. AI
    ai_result = None
    if result.capture_status != "failed":
        try:
            ai = AI()
            ai_data = await ai.complete_json(prompt=build_competitor_prompt(asin, result.extracted_fields), system=COMPETITOR_SYSTEM)
            ai_result = ai_data
        except Exception as e:
            ai_result = {"error": str(e)}

    # 4. Save report
    title = result.extracted_fields.get("title")
    brand = None
    pd = result.extracted_fields.get("product_details")
    if isinstance(pd, dict):
        brand = pd.get("Brand")

    if ai_result and not ai_result.get("error"):
        report = CompetitorAnalysisReport(
            user_id=uid, asin=asin, product_url=req.product_url,
            marketplace=req.marketplace, product_title=title, brand=brand,
            price=result.extracted_fields.get("price"),
            rating=result.extracted_fields.get("rating"),
            review_count=result.extracted_fields.get("review_count"),
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
            price=result.extracted_fields.get("price"),
            rating=result.extracted_fields.get("rating"),
            review_count=result.extracted_fields.get("review_count"),
            overall_judgment="数据已抓取，AI 分析待完成" if result.capture_status != "failed" else f"抓取失败: {result.error_message}",
        )

    db.add(report)
    await db.flush()
    return CompetitorAnalysisResponse.model_validate(report, from_attributes=True)


async def list_reports(page: int, page_size: int, db: AsyncSession) -> dict:
    offset = (page - 1) * page_size
    q = select(CompetitorAnalysisReport).order_by(desc(CompetitorAnalysisReport.created_at)).offset(offset).limit(page_size)
    r = await db.execute(q)
    items = [CompetitorAnalysisResponse.model_validate(x, from_attributes=True) for x in r.scalars().all()]
    total = len((await db.execute(select(CompetitorAnalysisReport))).scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_report(report_id: str, db: AsyncSession) -> CompetitorAnalysisResponse | None:
    r = await db.execute(select(CompetitorAnalysisReport).where(CompetitorAnalysisReport.id == report_id))
    report = r.scalar_one_or_none()
    return CompetitorAnalysisResponse.model_validate(report, from_attributes=True) if report else None
