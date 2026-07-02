from __future__ import annotations

"""Prelaunch pipeline: materials -> OCR/compliance/context -> AI reasoning."""

import asyncio
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

    last_error = None
    for attempt in range(2):
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
            break
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                await asyncio.sleep(3)
                continue
            result.ai_error = f"AI 调用失败（已重试1次）：{exc}"
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
    """Build a deterministic, saveable diagnosis when AI JSON parsing fails.
    
    Uses actual bullet point text to create differentiated results:
    - Very short text (<20 chars) → low score, missing detail warning
    - Short text (20-60 chars) → medium score, needs expansion
    - Good length (>60 chars) → higher score, minor suggestions
    """
    positions: list[dict[str, Any]] = []
    bullet_points = materials.get("bullet_points") or []
    impact_metrics_pool = ["CVR", "加购率", "Session%", "转化率", "浏览深度"]
    
    for index, text in enumerate(bullet_points[:5], start=1):
        if not text:
            continue
        
        text_len = len(str(text))
        has_number = any(c.isdigit() for c in str(text))
        has_cn = bool(re.search(r"[\u4e00-\u9fff]", str(text)))
        
        if text_len < 20:
            score = 2.5
            issue = f"五点{index}内容过短（{text_len}字），买家无法获取足够决策信息。"
            recommendation = f"建议将五点{index}扩展至至少60字符，补充具体数据和使用场景。"
            usable = "需优化"
            status = "需修改"
            metric = impact_metrics_pool[index % len(impact_metrics_pool)]
        elif text_len < 60:
            score = 3.5
            issue = f"五点{index}长度适中（{text_len}字），但缺少量化数据支撑卖点。"
            recommendation = f"五点{index}可增加具体数字、百分比或对比数据，增强说服力。"
            usable = "可使用但建议优化"
            status = "待验证"
            metric = impact_metrics_pool[(index + 1) % len(impact_metrics_pool)]
        else:
            score = 4.0
            issue = f"五点{index}内容充实（{text_len}字），建议用买家视角检查是否突出了最核心的购买理由。"
            recommendation = f"五点{index}基础良好，可将功能描述转化为买家可感知的结果。"
            usable = "可使用但建议优化"
            status = "待验证"
            metric = impact_metrics_pool[(index + 2) % len(impact_metrics_pool)]
        
        if has_number and text_len >= 30:
            score += 0.5
            issue += " 已包含数据，加分。"
        
        score = min(score, 4.5)
        
        positions.append({
            "position_id": f"bullet_{index}",
            "position": f"bullet_{index}",
            "position_name": f"五点{index}",
            "uploaded": True,
            "status": status,
            "issue_type": ["text_quality_fallback"],
            "issue": issue,
            "recommendation": recommendation,
            "suggested_rewrite": recommendation,
            "final_score": round(score, 1),
            "score": round(score, 1),
            "usable_status": usable,
            "risk_level": "medium" if score < 3.5 else "low",
            "validation_metric": metric,
            "impact_metrics": [metric],
        })

    return {
        "admission_result": "待验证",
        "conclusion": "AI 服务暂时不可用，已基于文本规则生成初步诊断。建议稍后重新运行 AI 分析获取完整建议。",
        "position_diagnoses": positions,
        "next_action": "完善文本内容后，重新运行 AI 诊断以获取精准建议。",
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
    attempted_positions = {
        SLOT_LABEL_MAP.get(item.get("slot", ""), item.get("slot", "")): ""
        for item in b64_list
        if item.get("slot")
    }
    try:
        ocr_results = await extract_text_from_base64_list(b64_list, product_context=product_context)
        if ocr_results:
            result.materials["ocr_texts"] = {
                **attempted_positions,
                **{
                    SLOT_LABEL_MAP.get(r.get("slot", ""), r.get("slot", "")): r["text"]
                    for r in ocr_results
                    if r.get("text")
                },
            }
            result.ocr_status = "success"
        else:
            result.materials["ocr_texts"] = attempted_positions
            result.ocr_status = "skipped"
    except Exception as exc:
        result.materials["ocr_texts"] = attempted_positions
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
