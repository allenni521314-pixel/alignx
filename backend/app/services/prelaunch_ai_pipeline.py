from __future__ import annotations

"""Prelaunch pipeline: materials -> OCR/compliance/context -> AI reasoning."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.compliance import check_compliance
from app.core.prompts import PRELAUNCH_SYSTEM, build_prelaunch_prompt
from app.core.prelaunch_rules import apply_prelaunch_rules
from app.core.scraperapi import ScraperAPIProvider
from app.core.vision import extract_text_from_base64_list
from app.models import CaptureJob
from app.schemas import PrelaunchCheckRequest
from app.services.access import require_user_id
from app.services.ai_calls import complete_json_with_log


SLOT_LABEL_MAP = {
    "main": "main_image",
    "img2": "image_2",
    "img3": "image_3",
    "img4": "image_4",
    "img5": "image_5",
    "img6": "image_6",
    "img7": "image_7",
    "aplus1": "aplus_1",
    "aplus2": "aplus_2",
    "aplus3": "aplus_3",
    "aplus4": "aplus_4",
    "aplus5": "aplus_5",
    "aplus6": "aplus_6",
    "aplus7": "aplus_7",
    "aplus8": "aplus_8",
    "aplus9": "aplus_9",
}


@dataclass
class PrelaunchAiPipelineResult:
    materials: dict[str, Any] = field(default_factory=dict)
    ai_result: dict[str, Any] | None = None
    ocr_status: str = "pending"
    market_context_status: str = "pending"
    ai_error: str | None = None

    def evidence_payload(self) -> dict[str, Any]:
        return {
            "ocr_status": self.ocr_status,
            "market_context_status": self.market_context_status,
            "image_count": self.materials.get("image_count", 0),
        }


async def run_prelaunch_ai_pipeline(
    *,
    req: PrelaunchCheckRequest,
    db: AsyncSession,
    user_id: str | None,
) -> PrelaunchAiPipelineResult:
    uid = require_user_id(user_id)
    result = PrelaunchAiPipelineResult(materials=_base_materials(req))
    await _attach_image_materials(req, result)
    _attach_compliance(req, result)
    await _attach_market_context(req, result, db=db, user_id=uid)

    try:
        prompt = build_prelaunch_prompt(result.materials)
        result.ai_result = await complete_json_with_log(
            db=db,
            user_id=uid,
            module_name="prelaunch_check",
            prompt_version="prelaunch_check:v1",
            prompt=prompt,
            system=PRELAUNCH_SYSTEM,
            input_payload={
                "product_name": req.product_name,
                "marketplace": req.marketplace,
                "materials": result.materials,
                "pipeline": result.evidence_payload(),
            },
            max_tokens=8192,
        )
        result.ai_result = apply_prelaunch_rules(result.ai_result, result.materials)
    except Exception as exc:
        result.ai_error = "AI 解析失败，已使用规则兜底诊断。"
        try:
            result.ai_result = apply_prelaunch_rules(
                _fallback_prelaunch_result(result.materials),
                result.materials,
            )
        except Exception:
            result.ai_result = None
            result.ai_error = "AI 分析失败，请稍后重试。"
    return result


def _base_materials(req: PrelaunchCheckRequest) -> dict[str, Any]:
    return {
        "product_name": req.product_name,
        "title_draft": req.title_draft,
        "key_highlights": req.key_highlights,
        "bullet_points": [req.bullet_1, req.bullet_2, req.bullet_3, req.bullet_4, req.bullet_5],
    }


def _fallback_prelaunch_result(materials: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic, saveable diagnosis when AI JSON parsing fails."""
    positions: list[dict[str, Any]] = []
    bullet_points = materials.get("bullet_points") or []
    for index, text in enumerate(bullet_points[:5], start=1):
        if not text:
            continue
        positions.append({
            "position_id": f"bullet_{index}",
            "position": f"bullet_{index}",
            "position_name": f"五点{index}",
            "position_type": "text",
            "uploaded": True,
            "status": "待验证",
            "issue_type": ["ai_fallback_diagnosis"],
            "issue": "AI 诊断未完成，已使用规则兜底。",
            "recommendation": "待验证",
            "suggested_rewrite": "待验证",
            "final_score": 3.0,
            "score": 3.0,
            "usable_status": "可使用但建议优化",
            "risk_level": "low",
            "validation_metric": "CVR",
            "impact_metrics": ["CVR"],
        })

    return {
        "admission_result": "待验证",
        "conclusion": "AI 诊断未完成，已使用规则兜底。",
        "position_diagnoses": positions,
        "next_action": "先处理硬拦截项，再重新运行 AI 诊断。",
    }


async def _attach_image_materials(req: PrelaunchCheckRequest, result: PrelaunchAiPipelineResult) -> None:
    image_slots = req.image_slots or []
    if not image_slots:
        result.ocr_status = "skipped"
        return

    uploaded = []
    for slot_item in image_slots:
        slot = slot_item.get("slot", "")
        uploaded.append({
            "position": SLOT_LABEL_MAP.get(slot, slot),
            "file": slot_item.get("name", ""),
            "slot_id": slot,
        })
    result.materials["uploaded_images"] = uploaded
    result.materials["image_count"] = len(uploaded)
    all_positions = list(SLOT_LABEL_MAP.values())
    result.materials["missing_images"] = [p for p in all_positions if p not in [u["position"] for u in uploaded]]

    b64_list = [
        {"url": f"data:image/jpeg;base64,{slot_item.get('base64', '')}", "slot": slot_item.get("slot", "")}
        for slot_item in image_slots
        if slot_item.get("base64")
    ][:7]
    if not b64_list:
        result.ocr_status = "skipped"
        return

    product_context = "\n".join([
        f"产品名称：{req.product_name or '暂无'}",
        f"标题草稿：{req.title_draft or '暂无'}",
        f"核心卖点：{req.key_highlights or '暂无'}",
        f"五点1：{req.bullet_1 or '暂无'}",
        f"五点2：{req.bullet_2 or '暂无'}",
        f"五点3：{req.bullet_3 or '暂无'}",
        f"五点4：{req.bullet_4 or '暂无'}",
        f"五点5：{req.bullet_5 or '暂无'}",
    ])
    try:
        ocr_results = await extract_text_from_base64_list(b64_list, product_context=product_context)
        if ocr_results:
            result.materials["ocr_texts"] = {r["slot"]: r["text"] for r in ocr_results if r.get("text")}
            result.ocr_status = "success"
        else:
            result.ocr_status = "skipped"
    except Exception as exc:
        result.ocr_status = f"failed:{exc}"


def _attach_compliance(req: PrelaunchCheckRequest, result: PrelaunchAiPipelineResult) -> None:
    texts_to_check = {
        "title": req.title_draft or "",
        "highlights": req.key_highlights or "",
        "bullet_1": req.bullet_1 or "",
        "bullet_2": req.bullet_2 or "",
        "bullet_3": req.bullet_3 or "",
        "bullet_4": req.bullet_4 or "",
        "bullet_5": req.bullet_5 or "",
    }
    violations = {}
    for field, text in texts_to_check.items():
        if text:
            hits = check_compliance(text)
            if hits:
                violations[field] = hits
    if violations:
        result.materials["compliance_violations"] = violations


async def _attach_market_context(
    req: PrelaunchCheckRequest,
    result: PrelaunchAiPipelineResult,
    *,
    db: AsyncSession,
    user_id: str,
) -> None:
    keyword = result.materials.get("product_name", "")[:60]
    if re.search(r"[\u4e00-\u9fff]", keyword):
        alt = (req.title_draft or req.key_highlights or "").strip()
        if alt and not re.search(r"[\u4e00-\u9fff]", alt):
            keyword = alt[:60]
    if not keyword:
        result.market_context_status = "skipped"
        return
    capture_job = CaptureJob(
        user_id=user_id,
        input_type="prelaunch_market_context",
        input_value=keyword,
        marketplace=req.marketplace,
        provider="scraperapi",
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(capture_job)
    await db.flush()
    try:
        provider = ScraperAPIProvider()
        capture = await provider.capture_top20_by_keyword(keyword, req.marketplace)
        capture_job.status = capture.capture_status
        capture_job.finished_at = datetime.utcnow()
        capture_job.error_message = capture.error_message
        await db.flush()
        if capture.capture_status != "failed" and capture.extracted_fields:
            result.materials["market_context"] = capture.extracted_fields
            result.materials["market_context_note"] = f"Top 20 results for '{keyword}' on {req.marketplace}"
            result.market_context_status = "success"
        else:
            result.market_context_status = "failed"
    except Exception as exc:
        capture_job.status = "failed"
        capture_job.finished_at = datetime.utcnow()
        capture_job.error_message = str(exc)
        await db.flush()
        result.market_context_status = f"failed:{exc}"
