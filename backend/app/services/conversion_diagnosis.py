from __future__ import annotations
"""Conversion diagnosis service — in-sale ASIN → capture → AI position-by-position diagnosis."""

import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import ConversionDiagnosis, CaptureJob, ListingSnapshot
from app.schemas import ConversionDiagnosisRequest, ConversionDiagnosisResponse
from app.core.scraperapi import ScraperAPIProvider
from app.core.ai import AI
from app.core.prompts import build_conversion_prompt, CONVERSION_SYSTEM
from app.constants import DEFAULT_USER_ID


async def diagnose(req: ConversionDiagnosisRequest, db: AsyncSession) -> ConversionDiagnosisResponse:
    asin = req.asin
    if not asin and req.product_url:
        import re
        match = re.search(r"/dp/([A-Z0-9]{10})", req.product_url)
        asin = match.group(1) if match else None
    if not asin:
        raise ValueError("Could not determine ASIN from input")

    # 1. Get or capture listing data
    q = select(ListingSnapshot).where(ListingSnapshot.asin == asin).order_by(desc(ListingSnapshot.created_at)).limit(1)
    existing = (await db.execute(q)).scalar_one_or_none()

    listing_data = None
    if not existing:
        capture = CaptureJob(
            user_id=DEFAULT_USER_ID,
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
                parse_status=result.capture_status,
                missing_fields=result.missing_fields,
                field_completeness_score=result.data_completeness_score,
            )
            db.add(snapshot)
            await db.flush()
            listing_data = result.extracted_fields
    else:
        listing_data = {
            "title": existing.title, "price": existing.price,
            "rating": existing.rating, "review_count": existing.review_count,
            "bullet_points": existing.bullet_points,
            "main_image": existing.main_image, "image_urls": existing.image_urls,
            "aplus_content": existing.aplus_content,
            "product_details": existing.product_details,
        }

    # 2. AI analysis
    ai_result = None
    if listing_data:
        try:
            ai = AI()
            ai_data = await ai.complete_json(
                prompt=build_conversion_prompt(asin, listing_data),
                system=CONVERSION_SYSTEM,
            )
            ai_result = ai_data
        except Exception as e:
            ai_result = {"error": str(e)}

    # 3. Save
    title = listing_data.get("title") if listing_data else None
    if ai_result and not ai_result.get("error"):
        diagnosis = ConversionDiagnosis(
            user_id=DEFAULT_USER_ID, asin=asin, product_url=req.product_url,
            marketplace=req.marketplace, product_title=title,
            overall_conclusion=ai_result.get("overall_conclusion"),
            biggest_breakpoint=ai_result.get("biggest_breakpoint"),
            priority_position=ai_result.get("priority_position"),
            priority_action=ai_result.get("priority_action"),
            impacted_ad_metrics=ai_result.get("impacted_ad_metrics"),
            current_status=ai_result.get("current_status"),
            position_diagnoses_json=ai_result.get("position_diagnoses"),
        )
    else:
        diagnosis = ConversionDiagnosis(
            user_id=DEFAULT_USER_ID, asin=asin, product_url=req.product_url,
            marketplace=req.marketplace, product_title=title,
            overall_conclusion="数据已抓取，AI 诊断待完成" if listing_data else "抓取失败",
            current_status="pending",
        )

    db.add(diagnosis)
    await db.flush()
    return ConversionDiagnosisResponse.model_validate(diagnosis, from_attributes=True)


async def list_diagnoses(page: int, page_size: int, db: AsyncSession) -> dict:
    offset = (page - 1) * page_size
    q = select(ConversionDiagnosis).order_by(desc(ConversionDiagnosis.created_at)).offset(offset).limit(page_size)
    r = await db.execute(q)
    items = [ConversionDiagnosisResponse.model_validate(x, from_attributes=True) for x in r.scalars().all()]
    total = len((await db.execute(select(ConversionDiagnosis))).scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_diagnosis(diagnosis_id: str, db: AsyncSession) -> ConversionDiagnosisResponse | None:
    r = await db.execute(select(ConversionDiagnosis).where(ConversionDiagnosis.id == diagnosis_id))
    report = r.scalar_one_or_none()
    return ConversionDiagnosisResponse.model_validate(report, from_attributes=True) if report else None
