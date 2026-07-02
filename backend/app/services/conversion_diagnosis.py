from __future__ import annotations
"""Conversion diagnosis service — in-sale ASIN → listing AI pipeline."""

import json
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import CaptureJob, ConversionDiagnosis, ExecutionRecord
from app.schemas import ConversionDiagnosisRequest, ConversionDiagnosisResponse
from app.core.listing_diagnosis_validation import ListingDiagnosisValidationEngine
from app.core.multi_source_diagnosis import MultiSourceDiagnosisEngine
from app.core.scraperapi import ScraperAPIProvider
from app.core.top20_keyword_mapping import build_top20_keyword_position_data, select_core_keyword
from app.services.listing_ai_pipeline import ListingAiPipeline, extract_asin, run_conversion_listing_ai_pipeline
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
    sources = await _auto_fetch_sources(asin, req.marketplace, uid, db)
    if listing_data and diagnosis_result:
        source_ai_result = dict(ai_result)
        source_ai_result["top20_keyword_position_data"] = sources.get("top20_keyword_position_data") or []
        source_ai_result["top20_keyword_mapping_context"] = sources.get("top20_context") or {}
        diagnosis_result = ListingDiagnosisValidationEngine().analyze(
            asin=asin,
            marketplace=req.marketplace,
            listing_data=listing_data,
            ai_result=source_ai_result,
            ad_metrics=sources.get("ad_metrics") or {},
        )

    multi_result = run_multi_source_classify({
        **sources,
        "listing_diagnosis": diagnosis_result,
        "asin": asin,
        "marketplace": req.marketplace,
    })
    unified_result = _merge_unified_result(diagnosis_result, multi_result, sources, asin, req.marketplace)

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
            ai_readability_score_json=unified_result,
            ai_readability_score_version=unified_result.get("engine_version"),
        )
    else:
        diagnosis = ConversionDiagnosis(
            user_id=uid, asin=asin, product_url=req.product_url,
            marketplace=req.marketplace, product_title=title,
            overall_conclusion="数据已抓取，AI 诊断待完成" if listing_data else "抓取失败",
            current_status="pending",
            ai_readability_score_json=unified_result,
        )

    db.add(diagnosis)
    await db.flush()
    return _response_with_unified_fields(diagnosis)


async def _auto_fetch_sources(asin: str, marketplace: str, user_id: str, db: AsyncSession) -> dict[str, Any]:
    """Auto-fetch listing, ad metrics, and TOP20 context without frontend HTTP chaining."""
    listing_result = await ListingAiPipeline(
        db=db,
        user_id=user_id,
        asin=asin,
        marketplace=marketplace,
    ).prepare_listing()
    listing_data = listing_result.listing_data or {}
    ai_context: dict[str, Any] = {}
    top20_rows: list[dict[str, Any]] = []
    top20_context: dict[str, Any] = {
        "source": "own_listing_title",
        "top20_capture_status": "skipped",
        "top20_sample_count": 0,
        "top20_asins": [],
    }
    if listing_data:
        await _attach_top20_keyword_mapping(
            listing_data=listing_data,
            ai_result=ai_context,
            marketplace=marketplace,
            db=db,
            user_id=user_id,
        )
        top20_rows = ai_context.get("top20_keyword_position_data") or []
        top20_context = ai_context.get("top20_keyword_mapping_context") or top20_context

    ad_metrics = await _fetch_ad_metrics(asin, db, user_id)
    return {
        "listing_data": listing_data,
        "ad_metrics": ad_metrics,
        "top20_keyword_position_data": top20_rows,
        "top20_context": top20_context,
        "data_sources": _data_source_status(listing_result, ad_metrics, top20_context),
    }


def run_multi_source_classify(sources: dict[str, Any]) -> dict[str, Any]:
    engine = MultiSourceDiagnosisEngine()
    ad = sources.get("ad_metrics") or {}
    listing_diag = sources.get("listing_diagnosis")
    top20 = sources.get("top20_context") or {}
    dimensions = engine._classify(ad, listing_diag, top20)
    scored = sorted(dimensions, key=lambda d: d["confidence"], reverse=True)
    primary = scored[0] if scored else {
        "dimension": "待录入",
        "label": "待录入",
        "confidence": 0,
        "evidence": "暂无",
    }
    actions = engine._build_actions(primary, listing_diag, ad)
    return {
        "asin": sources.get("asin"),
        "marketplace": sources.get("marketplace"),
        "primary_problem": primary.get("dimension"),
        "primary_label": primary.get("label"),
        "primary_confidence": primary.get("confidence"),
        "primary_evidence": primary.get("evidence"),
        "dimensions": dimensions,
        "top_actions": actions,
        "system_can_fix": [a for a in actions if a.get("system_capable")],
        "human_required": [a for a in actions if not a.get("system_capable")],
    }


async def _fetch_ad_metrics(asin: str, db: AsyncSession, user_id: str) -> dict[str, Any]:
    q = user_scoped(select(ExecutionRecord), ExecutionRecord, user_id)
    q = q.where(
        ExecutionRecord.asin == asin,
        ExecutionRecord.cost_type == "ad_spend",
    ).order_by(desc(ExecutionRecord.executed_at))
    rows = (await db.execute(q)).scalars().all()
    totals = {
        "impressions": 0,
        "clicks": 0,
        "orders": 0,
        "spend": 0.0,
        "sales": 0.0,
        "source_record_count": 0,
    }
    for row in rows:
        metrics = _parse_ad_metrics(row.evidence_note)
        if not metrics:
            continue
        totals["source_record_count"] += 1
        totals["impressions"] += _to_int(metrics.get("impressions"))
        totals["clicks"] += _to_int(metrics.get("clicks"))
        totals["orders"] += _to_int(metrics.get("orders"))
        totals["sales"] += _to_float(metrics.get("sales"))
        totals["spend"] += _to_float(metrics.get("spend")) or _to_float(row.cost_amount)
    clicks = totals["clicks"]
    impressions = totals["impressions"]
    orders = totals["orders"]
    sales = totals["sales"]
    spend = totals["spend"]
    totals["ctr"] = round(clicks / impressions, 4) if impressions else None
    totals["cvr"] = round(orders / clicks, 4) if clicks else None
    totals["acos"] = round(spend / sales, 4) if sales else None
    totals["has_data"] = totals["source_record_count"] > 0
    return totals


def _parse_ad_metrics(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        data = json.loads(value)
    except Exception:
        return None
    if isinstance(data, dict) and data.get("type") == "ad_metrics":
        return data
    return data if isinstance(data, dict) else None


def _data_source_status(
    listing_result: Any,
    ad_metrics: dict[str, Any],
    top20_context: dict[str, Any],
) -> dict[str, Any]:
    top20_sample_count = int(top20_context.get("top20_sample_count") or 0)
    return {
        "listing": {
            "status": listing_result.capture_status,
            "has_data": bool(listing_result.listing_data),
            "capture_job_id": listing_result.capture_job_id,
            "listing_snapshot_id": listing_result.listing_snapshot_id,
            "ocr_status": listing_result.ocr_status,
        },
        "ad": {
            "status": "available" if ad_metrics.get("has_data") else "missing",
            "has_data": bool(ad_metrics.get("has_data")),
            "source_record_count": ad_metrics.get("source_record_count", 0),
            "metrics": ad_metrics,
        },
        "top20": {
            "status": top20_context.get("top20_capture_status") or "skipped",
            "has_data": top20_sample_count > 0,
            "source_keyword": top20_context.get("source_keyword"),
            "top20_sample_count": top20_sample_count,
            "capture_job_id": top20_context.get("capture_job_id"),
            "error_message": top20_context.get("error_message"),
        },
    }


def _merge_unified_result(
    diagnosis_result: dict[str, Any] | None,
    multi_result: dict[str, Any],
    sources: dict[str, Any],
    asin: str,
    marketplace: str,
) -> dict[str, Any]:
    diagnosis = diagnosis_result or {}
    return {
        **diagnosis,
        "asin": asin,
        "marketplace": marketplace,
        "root_cause": multi_result.get("primary_problem") or "待录入",
        "root_cause_label": multi_result.get("primary_label") or "待录入",
        "multi_source_diagnosis": multi_result,
        "overall_health_score": diagnosis.get("overall_health_score"),
        "funnel_diagnosis": diagnosis.get("funnel_diagnosis") or [],
        "heatmap": diagnosis.get("position_gap_heatmap") or [],
        "top_3_actions": diagnosis.get("top_actions") or [],
        "keyword_map": diagnosis.get("keyword_position_mapping") or [],
        "data_sources": sources.get("data_sources") or {},
        "confidence": _unified_confidence(sources.get("data_sources") or {}),
    }


def _unified_confidence(data_sources: dict[str, Any]) -> str:
    score = 0
    if data_sources.get("listing", {}).get("has_data"):
        score += 1
    if data_sources.get("ad", {}).get("has_data"):
        score += 1
    if data_sources.get("top20", {}).get("has_data"):
        score += 1
    if score >= 3:
        return "high"
    if score == 2:
        return "medium"
    return "low"


def _response_with_unified_fields(diagnosis: ConversionDiagnosis) -> ConversionDiagnosisResponse:
    response = ConversionDiagnosisResponse.model_validate(diagnosis, from_attributes=True)
    payload = diagnosis.ai_readability_score_json or {}
    for key in [
        "overall_health_score",
        "root_cause",
        "funnel_diagnosis",
        "heatmap",
        "top_3_actions",
        "keyword_map",
        "data_sources",
        "confidence",
    ]:
        setattr(response, key, payload.get(key))
    return response


def _to_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


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
