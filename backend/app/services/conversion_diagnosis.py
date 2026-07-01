from __future__ import annotations
"""Conversion diagnosis service — in-sale ASIN → listing AI pipeline."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import CaptureJob, ConversionDiagnosis
from app.schemas import ConversionDiagnosisRequest, ConversionDiagnosisResponse
from app.core.listing_diagnosis_validation import ListingDiagnosisValidationEngine
from app.core.scraperapi import ScraperAPIProvider
from app.core.top20_keyword_mapping import build_top20_keyword_position_data, select_core_keyword
from app.services.listing_ai_pipeline import extract_asin, run_conversion_listing_ai_pipeline
from app.services.access import require_user_id, user_scoped


async def diagnose(req: ConversionDiagnosisRequest, db: AsyncSession, user_id: str | None = None) -> ConversionDiagnosisResponse:
    uid = require_user_id(user_id)
    asin = extract_asin(req.asin)
    if not asin and req.product_url:
        asin = extract_asin(req.product_url)
    if not asin:
        raise ValueError("Could not determine ASIN from input")

    pipeline_result = await run_conversion_listing_ai_pipeline(
        asin=asin,
        marketplace=req.marketplace,
        db=db,
        user_id=uid,
        product_url=req.product_url,
    )
    listing_data = pipeline_result.listing_data
    ai_result = pipeline_result.ai_result or {}
    if listing_data:
        await _attach_top20_keyword_mapping(
            listing_data=listing_data,
            ai_result=ai_result,
            marketplace=req.marketplace,
            db=db,
            user_id=uid,
        )
    diagnosis_result = (
        ListingDiagnosisValidationEngine().analyze(
            asin=asin,
            marketplace=req.marketplace,
            listing_data=listing_data,
            ai_result=ai_result,
        )
        if listing_data
        else None
    )

    title = listing_data.get("title") if listing_data else None
    if diagnosis_result:
        top_action = (diagnosis_result.get("top_actions") or [{}])[0]
        diagnosis = ConversionDiagnosis(
            user_id=uid, asin=asin, product_url=req.product_url,
            marketplace=req.marketplace, product_title=title,
            overall_conclusion=_summary(diagnosis_result),
            biggest_breakpoint=diagnosis_result.get("primary_bottleneck"),
            priority_position=top_action.get("target_position"),
            priority_action=top_action.get("action"),
            impacted_ad_metrics=top_action.get("verification_metrics"),
            current_status=diagnosis_result.get("diagnosis_type"),
            position_diagnoses_json=diagnosis_result.get("position_gap_heatmap"),
            ai_readability_score_json=diagnosis_result,
            ai_readability_score_version=diagnosis_result.get("engine_version"),
        )
    else:
        diagnosis = ConversionDiagnosis(
            user_id=uid, asin=asin, product_url=req.product_url,
            marketplace=req.marketplace, product_title=title,
            overall_conclusion="数据已抓取，AI 诊断待完成" if listing_data else "抓取失败",
            current_status="pending",
        )

    db.add(diagnosis)
    await db.flush()
    return ConversionDiagnosisResponse.model_validate(diagnosis, from_attributes=True)


async def _attach_top20_keyword_mapping(
    *,
    listing_data: dict,
    ai_result: dict,
    marketplace: str,
    db: AsyncSession,
    user_id: str,
) -> None:
    title = listing_data.get("title") or ""
    keyword = select_core_keyword(title)
    context = {
        "source": "own_listing_title",
        "source_keyword": keyword,
        "top20_capture_status": "skipped",
        "top20_sample_count": 0,
        "top20_asins": [],
    }
    if not keyword:
        ai_result["top20_keyword_mapping_context"] = context
        return

    capture_job = CaptureJob(
        user_id=user_id,
        input_type="conversion_top20_keyword_mapping",
        input_value=keyword,
        marketplace=marketplace,
        provider="scraperapi",
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(capture_job)
    await db.flush()

    try:
        capture = await ScraperAPIProvider().capture_top20_by_keyword(keyword, marketplace)
        capture_job.status = capture.capture_status
        capture_job.finished_at = datetime.utcnow()
        capture_job.error_message = capture.error_message
        await db.flush()

        fields = capture.extracted_fields or {}
        results = fields.get("results") if isinstance(fields.get("results"), list) else []
        rows, built_context = build_top20_keyword_position_data(
            title=title,
            top20_results=results,
            source_keyword=keyword,
        )
        if not results:
            rows = []
        context.update(built_context)
        context["top20_capture_status"] = capture.capture_status
        context["capture_job_id"] = capture_job.id
        ai_result["top20_keyword_position_data"] = rows
        ai_result["top20_keyword_mapping_context"] = context
    except Exception as exc:
        capture_job.status = "failed"
        capture_job.finished_at = datetime.utcnow()
        capture_job.error_message = str(exc)
        await db.flush()
        context["top20_capture_status"] = "failed"
        context["error_message"] = str(exc)
        context["capture_job_id"] = capture_job.id
        ai_result["top20_keyword_position_data"] = []
        ai_result["top20_keyword_mapping_context"] = context


def _summary(diagnosis_result: dict) -> str:
    primary = diagnosis_result.get("primary_bottleneck") or "待录入"
    secondary = diagnosis_result.get("secondary_bottleneck") or "待录入"
    confidence = diagnosis_result.get("confidence", 0)
    evidence = diagnosis_result.get("evidence_strength", 0)
    return f"当前最大断点：{primary}。次级断点：{secondary}。置信度：{confidence}/100。证据强度：{evidence}/100。"


async def list_diagnoses(page: int, page_size: int, db: AsyncSession, user_id: str | None = None) -> dict:
    uid = require_user_id(user_id)
    offset = (page - 1) * page_size
    q = user_scoped(select(ConversionDiagnosis), ConversionDiagnosis, uid)
    q = q.order_by(desc(ConversionDiagnosis.created_at)).offset(offset).limit(page_size)
    r = await db.execute(q)
    items = [ConversionDiagnosisResponse.model_validate(x, from_attributes=True) for x in r.scalars().all()]
    total_q = user_scoped(select(ConversionDiagnosis), ConversionDiagnosis, uid)
    total = len((await db.execute(total_q)).scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_diagnosis(diagnosis_id: str, db: AsyncSession, user_id: str | None = None) -> ConversionDiagnosisResponse | None:
    uid = require_user_id(user_id)
    q = user_scoped(select(ConversionDiagnosis), ConversionDiagnosis, uid)
    r = await db.execute(q.where(ConversionDiagnosis.id == diagnosis_id))
    report = r.scalar_one_or_none()
    return ConversionDiagnosisResponse.model_validate(report, from_attributes=True) if report else None
