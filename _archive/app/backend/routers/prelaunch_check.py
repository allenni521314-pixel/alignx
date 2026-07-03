from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user, get_user_scope_ids
from schemas.auth import UserResponse
from services.prelaunch_test_results import Prelaunch_test_resultsService
from services.visual_ocr_evidence import extract_visual_ocr_evidence

router = APIRouter(prefix="/api/v1/prelaunch-check", tags=["prelaunch-check"])
logger = logging.getLogger(__name__)


class PrelaunchImageSlot(BaseModel):
    slot: str
    name: str = ""
    base64: str = ""


class PrelaunchAnalyzeRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=255)
    marketplace: str = "amazon.com"
    title_draft: Optional[str] = None
    key_highlights: Optional[str] = None
    bullet_1: Optional[str] = None
    bullet_2: Optional[str] = None
    bullet_3: Optional[str] = None
    bullet_4: Optional[str] = None
    bullet_5: Optional[str] = None
    image_count: int = 0
    image_slots: list[PrelaunchImageSlot] = []


SLOT_META: dict[str, tuple[str, str, str]] = {
    "main": ("主图", "image", "搜索结果第一视觉"),
    "img2": ("副图2", "image", "核心卖点可视化"),
    "img3": ("副图3", "image", "使用场景展示"),
    "img4": ("副图4", "image", "尺寸规格对比"),
    "img5": ("副图5", "image", "功能细节演示"),
    "img6": ("副图6", "image", "信任背书"),
    "img7": ("副图7", "image", "场景氛围"),
    "aplus1": ("A+1", "a_plus", "品牌主视觉"),
    "aplus2": ("A+2", "a_plus", "差异化对比"),
    "aplus3": ("A+3", "a_plus", "卖点1"),
    "aplus4": ("A+4", "a_plus", "卖点2"),
    "aplus5": ("A+5", "a_plus", "卖点3"),
    "aplus6": ("A+6", "a_plus", "技术规格参数"),
    "aplus7": ("A+7", "a_plus", "场景详解"),
    "aplus8": ("A+8", "a_plus", "认证质保"),
    "aplus9": ("A+9", "a_plus", "FAQ+售后"),
}

METRICS_BY_TYPE = {
    "image": ["转化率", "加购率"],
    "a_plus": ["转化率", "加购率"],
}


def _text_lines(value: str) -> list[str]:
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


def _ocr_review(position_name: str, target: str, ocr_text: str) -> tuple[str, str, float, str]:
    lines = _text_lines(ocr_text)
    unique_count = len({line.lower() for line in lines})
    line_count = len(lines)
    char_count = len(ocr_text or "")

    issue_parts = [f"OCR已提取{line_count}行文案。"]
    if line_count == 0:
        return (
            "图片已上传，文字识别尚未完成。以下建议基于图位规则推断，不代表对实际图片内容的评估。",
            f"规则参考（未读取图片内容）：确认该图是否承接：{target}。",
            0,
            "图片待识别",
        )
    if unique_count < line_count:
        issue_parts.append("存在重复文案。")
    if line_count >= 12 or char_count >= 420:
        issue_parts.append("文字密度偏高。")
    elif line_count <= 2 and position_name != "主图":
        issue_parts.append("文字信息偏少。")
    issue_parts.append(f"需确认是否承接：{target}。")

    if line_count >= 12 or char_count >= 420:
        recommendation = f"压缩长段文案，保留与「{target}」直接相关的信息。"
        score = 3.4
        usable = "可使用但建议优化"
    elif unique_count < line_count:
        recommendation = f"减少重复表达，补齐与「{target}」对应的信息。"
        score = 3.6
        usable = "可使用但建议优化"
    else:
        recommendation = f"检查该图是否完整承接：{target}。"
        score = 4.0
        usable = "可使用"

    return "".join(issue_parts), recommendation, score, usable


async def _build_position(
    slot: PrelaunchImageSlot,
    context: str,
    extracted: Optional[dict[str, str]] = None,
    *,
    batch_failed: bool = False,
) -> dict[str, Any]:
    position_name, position_type, target = SLOT_META.get(slot.slot, (slot.slot, "image", "暂无"))
    ocr_failed = batch_failed
    summary = ""
    recommendation_from_ai = ""
    text = ""
    if extracted:
        text = extracted.get("ocr_text", "")
        summary = extracted.get("summary", "")
        recommendation_from_ai = extracted.get("recommendation", "")
        ocr_failed = extracted.get("ocr_status") == "failed"

    if not text:
        return {
            "position_id": slot.slot,
            "position_name": position_name,
            "position_type": position_type,
            "uploaded": True,
            "ocr_status": "failed" if ocr_failed else "pending",
            "status": "待识别",
            "issue": "图片已上传，文字识别失败。" if ocr_failed else "图片已上传，文字识别尚未完成。以下建议基于图位规则推断，不代表对实际图片内容的评估。",
            "impact": None,
            "recommendation": f"规则参考（未读取图片内容）：确认该图是否承接：{target}。",
            "modification_example": None,
            "final_score": None,
            "usable_status": "图片待识别",
            "impact_metrics": METRICS_BY_TYPE.get(position_type, ["转化率"]),
            "evidence": None,
            "evidence_summary": None,
        }

    issue, recommendation, score, usable = _ocr_review(position_name, target, text)
    if summary:
        issue = f"{issue} 总结：{summary}"
    if recommendation_from_ai:
        recommendation = recommendation_from_ai
    return {
        "position_id": slot.slot,
        "position_name": position_name,
        "position_type": position_type,
        "uploaded": True,
        "ocr_status": "success",
        "status": "需修改" if score < 4 else "通过",
        "issue": issue,
        "impact": None,
        "recommendation": recommendation,
        "modification_example": None,
        "final_score": score,
        "usable_status": usable,
        "impact_metrics": METRICS_BY_TYPE.get(position_type, ["转化率"]),
        "evidence": text,
        "evidence_summary": summary or None,
    }


def _image_fields(req: PrelaunchAnalyzeRequest) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "main_image_path": None,
        "image_2_path": None,
        "image_3_path": None,
        "image_4_path": None,
        "image_5_path": None,
        "image_6_path": None,
        "image_7_path": None,
        "aplus_images_json": [],
    }
    slot_to_field = {
        "main": "main_image_path",
        "img2": "image_2_path",
        "img3": "image_3_path",
        "img4": "image_4_path",
        "img5": "image_5_path",
        "img6": "image_6_path",
        "img7": "image_7_path",
    }
    for image in req.image_slots:
        if not image.base64:
            continue
        url = image.base64 if image.base64.startswith("data:") else f"data:image/jpeg;base64,{image.base64}"
        if image.slot in slot_to_field:
            fields[slot_to_field[image.slot]] = url
        elif image.slot.startswith("aplus"):
            fields["aplus_images_json"].append({"slot": image.slot, "name": image.name, "url": url})
    return fields


def _response_from_record(record: Any) -> dict[str, Any]:
    full_report: dict[str, Any] = {}
    try:
        full_report = json.loads(record.full_report or "{}")
    except (TypeError, json.JSONDecodeError):
        full_report = {}

    input_snapshot = full_report.get("input_snapshot") or {}
    image_fields = full_report.get("image_fields") or {}
    return {
        "id": str(record.id),
        "product_name": input_snapshot.get("product_name") or record.title or "暂无",
        "marketplace": input_snapshot.get("marketplace") or "amazon.com",
        "title_draft": input_snapshot.get("title_draft"),
        "key_highlights": input_snapshot.get("key_highlights"),
        "bullet_1": input_snapshot.get("bullet_1"),
        "bullet_2": input_snapshot.get("bullet_2"),
        "bullet_3": input_snapshot.get("bullet_3"),
        "bullet_4": input_snapshot.get("bullet_4"),
        "bullet_5": input_snapshot.get("bullet_5"),
        "main_image_path": image_fields.get("main_image_path"),
        "image_2_path": image_fields.get("image_2_path"),
        "image_3_path": image_fields.get("image_3_path"),
        "image_4_path": image_fields.get("image_4_path"),
        "image_5_path": image_fields.get("image_5_path"),
        "image_6_path": image_fields.get("image_6_path"),
        "image_7_path": image_fields.get("image_7_path"),
        "aplus_images_json": image_fields.get("aplus_images_json") or [],
        "admission_result": full_report.get("admission_result") or record.overall_summary or "暂无",
        "conclusion": full_report.get("conclusion") or record.overall_summary or "暂无",
        "position_diagnoses_json": full_report.get("position_diagnoses_json") or [],
        "next_action": full_report.get("next_action"),
        "created_at": record.created_at.isoformat() if record.created_at else datetime.now(timezone.utc).isoformat(),
    }


@router.post("/analyze")
async def analyze_prelaunch_check(
    req: PrelaunchAnalyzeRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not req.product_name.strip():
        raise HTTPException(status_code=400, detail="产品名称不能为空")

    context = "\n".join([
        f"产品名称：{req.product_name or '暂无'}",
        f"标题草案：{req.title_draft or '暂无'}",
        f"亮点：{req.key_highlights or '暂无'}",
    ])
    positions: list[dict[str, Any]] = []
    image_slots = [slot for slot in req.image_slots if slot.base64]
    extracted_by_slot: dict[str, dict[str, str]] = {}
    failed_batch_slots: set[str] = set()
    if image_slots:
        visual_items: list[dict[str, Any]] = []
        for slot in image_slots:
            position_name, position_type, target = SLOT_META.get(slot.slot, (slot.slot, "image", "暂无"))
            visual_items.append({
                "slot": slot.slot,
                "position_id": slot.slot,
                "position_name": position_name,
                "image_group": position_type,
                "target": target,
                "base64": slot.base64,
            })
        try:
            visual_evidence = await extract_visual_ocr_evidence(
                visual_items,
                context=context,
                prompt_mode="prelaunch",
            )
            extracted_by_slot = {
                str(item.get("slot") or item.get("position_id")): {
                    "ocr_text": str(item.get("ocr_text") or ""),
                    "summary": str(item.get("summary") or item.get("image_expression") or ""),
                    "recommendation": str(item.get("recommendation") or ""),
                    "ocr_status": str(item.get("ocr_status") or ""),
                }
                for item in visual_evidence.get("items", [])
                if item.get("slot") or item.get("position_id")
            }
        except Exception as exc:
            logger.warning("Prelaunch visual_ocr_evidence failed: %s", exc)
            failed_batch_slots.update(slot.slot for slot in image_slots)
    for slot in image_slots:
        extracted = extracted_by_slot.get(slot.slot)
        if extracted and extracted.get("ocr_text"):
            positions.append(await _build_position(slot, context, extracted))
            continue
        positions.append(await _build_position(slot, context, extracted, batch_failed=slot.slot in failed_batch_slots))
    if not positions:
        positions = [{
            "position_id": "materials",
            "position_name": "图片素材",
            "position_type": "image",
            "uploaded": False,
            "ocr_status": "pending",
            "status": "缺失",
            "issue": "暂无图片素材。",
            "impact": None,
            "recommendation": "待录入图片素材。",
            "modification_example": None,
            "final_score": None,
            "usable_status": "待录入",
            "impact_metrics": [],
            "evidence": None,
        }]

    recognized = [item for item in positions if item.get("ocr_status") == "success"]
    pending = [item for item in positions if item.get("ocr_status") != "success"]
    admission_result = "谨慎上架" if recognized and pending else "可以上架" if recognized else "暂不建议上架"
    reason_items = []
    failed_count = len([item for item in positions if item.get("ocr_status") == "failed"])
    pending_count = len([item for item in positions if item.get("ocr_status") == "pending"])
    if failed_count:
        reason_items.append(f"{failed_count}张图片识别失败")
    if pending_count:
        reason_items.append(f"{pending_count}张图片待识别")
    for item in positions:
        if item.get("ocr_status") == "success" and item.get("status") != "通过":
            issue = str(item.get("issue") or "").strip()
            if issue:
                reason_items.append(f"{item.get('position_name')}: {issue}")
        if len(reason_items) >= 4:
            break
    reason_text = "；".join(reason_items) if reason_items else "暂无"
    conclusion = f"已识别{len(recognized)}张图片，待识别{len(pending)}张图片。不建议上架原因：{reason_text}。"
    image_fields = _image_fields(req)
    full_report = {
        "input_snapshot": req.model_dump(),
        "image_fields": image_fields,
        "admission_result": admission_result,
        "conclusion": conclusion,
        "position_diagnoses_json": positions,
        "next_action": "完成分析",
    }

    svc = Prelaunch_test_resultsService(db)
    record = await svc.create({
        "title": req.product_name[:500],
        "keywords": "",
        "bullet_points": "\n".join([req.bullet_1 or "", req.bullet_2 or "", req.bullet_3 or "", req.bullet_4 or "", req.bullet_5 or ""]),
        "a_plus_desc": "",
        "overall_score": 0,
        "score_title_keywords": 0,
        "score_main_image": 0,
        "score_a_plus": 0,
        "score_bullet_points": 0,
        "overall_summary": admission_result,
        "cosmo_alignment": "",
        "rufus_alignment": "",
        "full_report": json.dumps(full_report, ensure_ascii=False),
        "has_images": 3 if any(slot.slot.startswith("aplus") for slot in req.image_slots) else 1 if req.image_slots else 0,
        "created_at": datetime.now(timezone.utc),
    }, user_id=str(current_user.id))

    return _response_from_record(record)


@router.get("/history")
async def list_prelaunch_checks(
    page: int = 1,
    page_size: int = 20,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = Prelaunch_test_resultsService(db)
    scope_user_ids = await get_user_scope_ids(current_user, db)
    rows, total = await svc.list_by_user(scope_user_ids, skip=(page - 1) * page_size, limit=page_size)
    return {"items": [_response_from_record(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/{check_id}")
async def get_prelaunch_check(
    check_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = Prelaunch_test_resultsService(db)
    scope_user_ids = await get_user_scope_ids(current_user, db)
    record = await svc.get_by_id(check_id, user_id=scope_user_ids)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    return _response_from_record(record)
