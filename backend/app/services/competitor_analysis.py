"""Competitor analysis service — ASIN → capture → AI 12-dimension analysis."""

import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import CompetitorAnalysisReport, CaptureJob, ListingSnapshot
from app.schemas import CompetitorAnalysisRequest, CompetitorAnalysisResponse
from app.core.scraperapi import ScraperAPIProvider
from app.core.ai import AI
from app.core.prompts import build_competitor_prompt, COMPETITOR_SYSTEM


async def analyze_competitor(
    req: CompetitorAnalysisRequest,
    db: AsyncSession,
) -> CompetitorAnalysisResponse:
    asin = req.asin
    if not asin and req.product_url:
        import re
        match = re.search(r"/dp/([A-Z0-9]{10})", req.product_url)
        asin = match.group(1) if match else None
    if not asin:
        raise ValueError("Could not determine ASIN from input")

    # 1. Capture
    capture = CaptureJob(input_type="asin", input_value=asin, marketplace=req.marketplace, provider="scraperapi", status="running")
    db.add(capture)
    await db.flush()

    provider = ScraperAPIProvider()
    result = await provider.capture_product_by_asin(asin, req.marketplace)

    capture.status = result.capture_status
    capture.raw_response_path = json.dumps(result.raw_response) if result.raw_response else None
    capture.error_message = result.error_message
    await db.flush()

    # 2. Save listing snapshot
    if result.capture_status != "failed":
        snapshot = ListingSnapshot(
            capture_job_id=capture.id, asin=asin, marketplace=req.marketplace,
            title=result.extracted_fields.get("title"),
            price=result.extracted_fields.get("price"),
            price_value=result.extracted_fields.get("price_value"),
            currency=result.extracted_fields.get("currency"),
            rating=result.extracted_fields.get("rating"),
            review_count=result.extracted_fields.get("review_count"),
            bought_in_past_month_raw=result.extracted_fields.get("bought_in_past_month_raw"),
            bought_in_past_month_value=result.extracted_fields.get("bought_in_past_month_value"),
            main_image=result.extracted_fields.get("main_image"),
            image_urls=result.extracted_fields.get("image_urls"),
            bullet_points=result.extracted_fields.get("bullet_points"),
            aplus_content=result.extracted_fields.get("aplus_content"),
            product_details=result.extracted_fields.get("product_details"),
            parse_status=result.capture_status,
            missing_fields=result.missing_fields,
            field_completeness_score=result.data_completeness_score,
        )
        db.add(snapshot)
        await db.flush()

    # 3. AI Analysis
    ai_result = None
    if result.capture_status != "failed":
        try:
            ai = AI()
            prompt = build_competitor_prompt(asin, result.extracted_fields)
            ai_data = await ai.complete_json(prompt=prompt, system=COMPETITOR_SYSTEM)
            ai_result = ai_data
        except Exception as e:
            ai_result = {"error": str(e)}

    # 4. Save report
    if ai_result and not ai_result.get("error"):
        twelve = ai_result.get("twelve_dimension", {})
        report = CompetitorAnalysisReport(
            user_id="default", asin=asin, product_url=req.product_url, marketplace=req.marketplace,
            product_title=result.extracted_fields.get("title"),
            brand=result.extracted_fields.get("product_details", {}).get("Brand") if isinstance(result.extracted_fields.get("product_details"), dict) else None,
            price=result.extracted_fields.get("price"),
            rating=result.extracted_fields.get("rating"),
            review_count=result.extracted_fields.get("review_count"),
            bought_in_past_month_raw=result.extracted_fields.get("bought_in_past_month_raw"),
            overall_judgment=ai_result.get("overall_judgment"),
            main_strengths=ai_result.get("main_strengths"),
            main_weaknesses=ai_result.get("main_weaknesses"),
            attack_points=ai_result.get("attack_points"),
            worth_benchmarking=ai_result.get("worth_benchmarking"),
            twelve_dimension_result_json=twelve,
        )
    else:
        report = CompetitorAnalysisReport(
            user_id="default", asin=asin, product_url=req.product_url, marketplace=req.marketplace,
            product_title=result.extracted_fields.get("title"),
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
