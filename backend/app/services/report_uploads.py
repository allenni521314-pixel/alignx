from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExecutionRecord, ReportUploadBatch, ReportUploadStagingRecord
from app.schemas import (
    ReportUploadStagingRecordResponse,
    ReportUploadStagingRequest,
    ReportUploadStagingResponse,
)
from app.services.access import TenantScope, require_user_id, user_scoped


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.lower())


def _pick(row: dict[str, Any], names: list[str]) -> str | None:
    normalized = {_key(str(k)): v for k, v in row.items()}
    for name in names:
        value = normalized.get(_key(name))
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    num = _to_float(value)
    return int(num) if num is not None else None


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    asin = _pick(row, ["asin", "advertised asin", "purchased asin", "product asin", "商品asin"])
    sku = _pick(row, ["sku", "advertised sku", "商品sku"])
    campaign = _pick(row, ["campaign", "campaign name", "广告活动", "广告活动名称"])
    ad_group = _pick(row, ["ad group", "ad group name", "adgroup", "广告组", "广告组名称"])
    keyword = _pick(row, ["keyword", "customer search term", "search term", "关键词", "搜索词"])
    target = _pick(row, ["target", "targeting", "targeting expression", "投放", "投放词"])
    report_date = _pick(row, ["date", "start date", "日期", "开始日期"])
    metrics = {
        "type": "ad_metrics",
        "impressions": _to_int(_pick(row, ["impressions", "曝光", "展示量"])),
        "clicks": _to_int(_pick(row, ["clicks", "点击", "点击量"])),
        "orders": _to_int(_pick(row, ["orders", "订单", "7 day total orders"])),
        "sales": _to_float(_pick(row, ["sales", "销售额", "7 day total sales"])),
        "spend": _to_float(_pick(row, ["spend", "cost", "花费", "广告花费"])),
        "ctr": _pick(row, ["ctr"]),
        "cpc": _pick(row, ["cpc"]),
    }
    metrics = {k: v for k, v in metrics.items() if v is not None}

    if asin and report_date and (campaign or ad_group or keyword or target):
        status = "resolved"
        note = None
    elif asin or sku:
        status = "ambiguous"
        note = "待确认"
    else:
        status = "unresolved"
        note = "无法归因"

    return {
        "asin": asin,
        "sku": sku,
        "campaign": campaign,
        "ad_group": ad_group,
        "keyword": keyword,
        "target": target,
        "report_date": report_date,
        "attribution_status": status,
        "normalized_metrics_json": metrics,
        "resolution_note": note,
    }


async def _match_asin(
    *,
    asin: str | None,
    store_id: str | None,
    marketplace: str,
    user_id: str,
    db: AsyncSession,
) -> tuple[str | None, str]:
    if not asin:
        return None, "missing"
    matched = await TenantScope.require(db, user_id).asin_record(asin, marketplace, store_id)
    if matched:
        return matched.id, "matched"
    return None, "unregistered"


async def stage_report_upload(
    req: ReportUploadStagingRequest,
    db: AsyncSession,
    user_id: str | None = None,
) -> ReportUploadStagingResponse:
    uid = require_user_id(user_id)
    batch = ReportUploadBatch(
        user_id=uid,
        store_id=req.store_id,
        marketplace=req.marketplace,
        report_type=req.report_type,
        source_filename=req.source_filename,
        total_rows=len(req.rows),
    )
    db.add(batch)
    await db.flush()

    records: list[ReportUploadStagingRecord] = []
    counts = {"resolved": 0, "ambiguous": 0, "unresolved": 0}
    for row in req.rows:
        normalized = _normalize_row(row)
        asin_id, asin_attribution_status = await _match_asin(
            asin=normalized["asin"],
            store_id=req.store_id,
            marketplace=req.marketplace,
            user_id=uid,
            db=db,
        )
        counts[normalized["attribution_status"]] += 1
        record = ReportUploadStagingRecord(
            batch_id=batch.id,
            user_id=uid,
            store_id=req.store_id,
            marketplace=req.marketplace,
            report_type=req.report_type,
            asin_id=asin_id,
            asin_attribution_status=asin_attribution_status,
            raw_row_json=row,
            **normalized,
        )
        db.add(record)
        records.append(record)

    batch.resolved_count = counts["resolved"]
    batch.ambiguous_count = counts["ambiguous"]
    batch.unresolved_count = counts["unresolved"]
    await db.flush()
    for record in records:
        record.source_record_id = record.id
    await db.flush()

    return ReportUploadStagingResponse(
        batch_id=batch.id,
        total_rows=batch.total_rows,
        resolved_count=batch.resolved_count,
        ambiguous_count=batch.ambiguous_count,
        unresolved_count=batch.unresolved_count,
        items=[ReportUploadStagingRecordResponse.model_validate(r, from_attributes=True) for r in records],
    )


async def list_staging_records(
    status: str | None,
    page: int,
    page_size: int,
    db: AsyncSession,
    user_id: str | None = None,
) -> dict:
    uid = require_user_id(user_id)
    offset = (page - 1) * page_size
    q = user_scoped(select(ReportUploadStagingRecord), ReportUploadStagingRecord, uid)
    if status:
        q = q.where(ReportUploadStagingRecord.attribution_status == status)
    q = q.order_by(desc(ReportUploadStagingRecord.created_at)).offset(offset).limit(page_size)
    rows = (await db.execute(q)).scalars().all()

    count_q = user_scoped(select(ReportUploadStagingRecord), ReportUploadStagingRecord, uid)
    if status:
        count_q = count_q.where(ReportUploadStagingRecord.attribution_status == status)
    total = len((await db.execute(count_q)).scalars().all())
    return {
        "items": [ReportUploadStagingRecordResponse.model_validate(r, from_attributes=True) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def confirm_staging_record(
    record_id: str,
    validation_task_id: str,
    db: AsyncSession,
    user_id: str | None = None,
) -> str:
    uid = require_user_id(user_id)
    q = user_scoped(select(ReportUploadStagingRecord), ReportUploadStagingRecord, uid)
    record = (await db.execute(q.where(ReportUploadStagingRecord.id == record_id))).scalar_one_or_none()
    if not record:
        raise ValueError("Staging record not found")
    if record.attribution_status != "resolved":
        raise ValueError("Staging record is not resolved")
    if record.asin_attribution_status != "matched" or not record.asin_id:
        raise ValueError("ASIN attribution is not matched")
    if record.confirmed_at:
        raise ValueError("Staging record already confirmed")

    task = await TenantScope.require(db, uid).validation_task(validation_task_id)
    if not task:
        raise ValueError("Validation task not found")
    if record.asin != task.asin:
        raise ValueError("ASIN does not match validation task")

    metrics = record.normalized_metrics_json or {}
    rec = ExecutionRecord(
        user_id=task.user_id,
        validation_task_id=task.id,
        asin=task.asin,
        action_summary=record.campaign or record.keyword or record.target or "待录入",
        cost_amount=metrics.get("spend"),
        cost_type="ad_spend",
        evidence_note=json.dumps(
            {
                **metrics,
                "source_type": record.source_type,
                "source_record_id": record.id,
                "report_date": record.report_date,
            },
            ensure_ascii=False,
        ),
    )
    db.add(rec)
    await db.flush()
    record.validation_task_id = task.id
    record.execution_record_id = rec.id
    record.confirmed_at = datetime.utcnow()
    await db.flush()
    return rec.id
