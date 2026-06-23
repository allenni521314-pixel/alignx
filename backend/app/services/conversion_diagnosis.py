"""Conversion diagnosis service — in-sale ASIN → capture → AI position-by-position diagnosis."""

import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import ConversionDiagnosis, CaptureJob, ListingSnapshot
from app.schemas import ConversionDiagnosisRequest, ConversionDiagnosisResponse
from app.core.scraperapi import ScraperAPIProvider


async def diagnose(
    req: ConversionDiagnosisRequest,
    db: AsyncSession,
) -> ConversionDiagnosisResponse:
    """Run conversion diagnosis pipeline."""

    asin = req.asin
    if not asin and req.product_url:
        import re
        match = re.search(r"/dp/([A-Z0-9]{10})", req.product_url)
        asin = match.group(1) if match else None

    if not asin:
        raise ValueError("Could not determine ASIN from input")

    # 1. Check existing snapshot first (avoid re-capture)
    q = (
        select(ListingSnapshot)
        .where(ListingSnapshot.asin == asin)
        .order_by(desc(ListingSnapshot.created_at))
        .limit(1)
    )
    existing = (await db.execute(q)).scalar_one_or_none()

    if not existing:
        # 2a. Capture
        capture = CaptureJob(
            input_type="asin",
            input_value=asin,
            marketplace=req.marketplace,
            provider="scraperapi",
            status="running",
        )
        db.add(capture)
        await db.flush()

        provider = ScraperAPIProvider()
        result = await provider.capture_product_by_asin(asin, req.marketplace)

        capture.status = result.capture_status
        capture.raw_response_path = json.dumps(result.raw_response) if result.raw_response else None
        capture.error_message = result.error_message
        await db.flush()

        if result.capture_status != "failed":
            snapshot = ListingSnapshot(
                capture_job_id=capture.id,
                asin=asin,
                marketplace=req.marketplace,
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

        title = result.extracted_fields.get("title")
    else:
        title = existing.title

    # 3. Build diagnosis (placeholder — Phase 3 wires AI + proposition matching)
    diagnosis = ConversionDiagnosis(
        user_id="default",
        asin=asin,
        product_url=req.product_url,
        marketplace=req.marketplace,
        product_title=title,
        overall_conclusion="数据已抓取，等待 AI 转化诊断",
        current_status="pending",
    )
    db.add(diagnosis)
    await db.flush()

    return ConversionDiagnosisResponse.model_validate(diagnosis, from_attributes=True)


async def list_diagnoses(page: int, page_size: int, db: AsyncSession) -> dict:
    offset = (page - 1) * page_size
    q = select(ConversionDiagnosis).order_by(desc(ConversionDiagnosis.created_at)).offset(offset).limit(page_size)
    result = await db.execute(q)
    items = [ConversionDiagnosisResponse.model_validate(r, from_attributes=True) for r in result.scalars().all()]
    count_q = select(ConversionDiagnosis)
    count_result = await db.execute(count_q)
    total = len(count_result.scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_diagnosis(diagnosis_id: str, db: AsyncSession) -> ConversionDiagnosisResponse | None:
    result = await db.execute(select(ConversionDiagnosis).where(ConversionDiagnosis.id == diagnosis_id))
    report = result.scalar_one_or_none()
    if not report:
        return None
    return ConversionDiagnosisResponse.model_validate(report, from_attributes=True)
