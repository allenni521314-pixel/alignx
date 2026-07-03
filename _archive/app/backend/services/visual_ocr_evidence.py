from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

from schemas.aihub import ChatMessage, ContentPartImage, ContentPartText, GenTxtRequest, ImageUrl
from services.aihub import AIHubService


def clean_ocr_text(value: Any, *, max_lines: int = 120, max_chars: int = 6000) -> str:
    lines: list[str] = []
    for line in re.split(r"[\r\n]+", str(value or "")):
        cleaned = re.sub(r"\s+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines[:max_lines])[:max_chars].strip()


def _parse_json_payload(value: str) -> dict[str, Any]:
    text = (value or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start_obj = text.find("{")
        end_obj = text.rfind("}")
        start_arr = text.find("[")
        end_arr = text.rfind("]")
        if start_obj >= 0 and end_obj > start_obj:
            parsed = json.loads(text[start_obj : end_obj + 1])
        elif start_arr >= 0 and end_arr > start_arr:
            parsed = json.loads(text[start_arr : end_arr + 1])
        else:
            raise

    if isinstance(parsed, list):
        return {"items": parsed}
    if isinstance(parsed, dict):
        items = parsed.get("items")
        if isinstance(items, list):
            return parsed
        return {"items": [parsed]}
    return {"items": []}


def _image_url(item: dict[str, Any]) -> str:
    url = str(item.get("url") or item.get("base64") or "").strip()
    if not url:
        return ""
    if url.startswith(("http://", "https://", "data:image/")):
        return url
    return f"data:image/jpeg;base64,{url}"


def _normalise_item(raw: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    ocr_text = clean_ocr_text(raw.get("ocr_text") or raw.get("image_text"))
    status = str(raw.get("ocr_status") or "").strip().lower()
    if status not in {"success", "failed", "pending"}:
        status = "success" if ocr_text else "pending"

    return {
        "slot": str(raw.get("slot") or fallback.get("slot") or fallback.get("position_id") or "").strip(),
        "position_id": str(raw.get("position_id") or fallback.get("position_id") or fallback.get("slot") or "").strip(),
        "position_name": str(raw.get("position_name") or fallback.get("position_name") or "").strip(),
        "image_group": str(raw.get("image_group") or fallback.get("image_group") or "").strip(),
        "order": raw.get("order") if raw.get("order") is not None else fallback.get("order"),
        "target": str(raw.get("target") or fallback.get("target") or "").strip(),
        "ocr_text": ocr_text,
        "summary": clean_ocr_text(raw.get("summary"), max_lines=8, max_chars=700),
        "recommendation": clean_ocr_text(raw.get("recommendation"), max_lines=5, max_chars=500),
        "image_expression": clean_ocr_text(raw.get("image_expression"), max_lines=8, max_chars=700),
        "copy_fit": clean_ocr_text(raw.get("copy_fit"), max_lines=5, max_chars=500),
        "buyer_language_note": clean_ocr_text(raw.get("buyer_language_note"), max_lines=5, max_chars=500),
        "ocr_status": status,
    }


async def _call_visual_batch(
    service: AIHubService,
    items: list[dict[str, Any]],
    *,
    context: str,
    prompt_mode: str,
) -> dict[str, Any]:
    meta = [
        {k: v for k, v in item.items() if k not in {"url", "base64"}}
        for item in items
    ]
    prompt = (
        "你是AlignX visual_ocr_evidence步骤。只读取图片事实，不做最终评分。"
        "逐张识别图片可见文字、产品/场景/证明信息，并基于对应图位目标给出一句简短总结和一句优化意见。"
        "不能补充图片里没有的信息。无法读取时对应字段返回空字符串，ocr_status返回pending。"
        "只返回JSON对象，不要Markdown。格式："
        '{"items":[{"slot":"","position_id":"","position_name":"","image_group":"","order":0,'
        '"target":"","ocr_text":"","summary":"","recommendation":"","image_expression":"",'
        '"copy_fit":"","buyer_language_note":"","ocr_status":"success|pending|failed"}]}'
        f"\n图位信息：{json.dumps(meta, ensure_ascii=False)}"
        f"\n上下文：{context or '暂无'}"
    )
    if prompt_mode == "listing":
        prompt += "\n用于Listing诊断证据链，输出只作为OCR/图片事实证据。"
    else:
        prompt += "\n用于上架准入，输出只作为逐图位检查依据。"

    content: list[Any] = [ContentPartText(type="text", text=prompt)]
    for item in items:
        image = _image_url(item)
        if not image:
            continue
        content.append(
            ContentPartText(
                type="text",
                text=(
                    f"slot={item.get('slot') or ''}; "
                    f"position_id={item.get('position_id') or ''}; "
                    f"position_name={item.get('position_name') or ''}; "
                    f"target={item.get('target') or '暂无'}"
                ),
            )
        )
        content.append(ContentPartImage(type="image_url", image_url=ImageUrl(url=image)))

    response = await service.gentxt(
        GenTxtRequest(
            messages=[ChatMessage(role="user", content=content)],
            model="AI_VISION_MODEL",
            temperature=0,
            max_tokens=int(os.getenv("VISION_OCR_MAX_TOKENS", "9000")),
        )
    )
    payload = _parse_json_payload(response.content or "")
    parsed_items = payload.get("items") if isinstance(payload.get("items"), list) else []

    by_key: dict[str, dict[str, Any]] = {}
    normalised: list[dict[str, Any]] = []
    for raw in parsed_items:
        if not isinstance(raw, dict):
            continue
        lookup = str(raw.get("slot") or raw.get("position_id") or "").strip()
        fallback = next(
            (
                item
                for item in items
                if lookup
                and lookup
                in {
                    str(item.get("slot") or ""),
                    str(item.get("position_id") or ""),
                    str(item.get("position_name") or ""),
                }
            ),
            items[len(normalised)] if len(normalised) < len(items) else {},
        )
        item = _normalise_item(raw, fallback)
        key = item["slot"] or item["position_id"] or str(item.get("order") or "")
        if key:
            by_key[key] = item
        normalised.append(item)

    return {
        "items": normalised,
        "by_key": by_key,
        "raw": response.content or "",
        "usage": response.usage or {},
        "model": response.model,
    }


async def extract_visual_ocr_evidence(
    items: list[dict[str, Any]],
    *,
    context: str = "",
    prompt_mode: str = "listing",
) -> dict[str, Any]:
    valid_items = [item for item in items if _image_url(item)]
    result: dict[str, Any] = {"items": [], "by_key": {}, "raw": "", "usage": [], "model": ""}
    if not valid_items:
        return result

    batch_size = max(1, int(os.getenv("VISION_OCR_BATCH_SIZE", "4")))
    interval = float(os.getenv("VISION_OCR_INTERVAL_SECONDS", "0.15"))
    service = AIHubService()
    errors: list[str] = []

    async def merge(batch_result: dict[str, Any]) -> None:
        result["items"].extend(batch_result.get("items", []))
        result["by_key"].update(batch_result.get("by_key", {}))
        if batch_result.get("raw"):
            result["raw"] = (str(result.get("raw") or "") + "\n" + str(batch_result["raw"]))[:4000]
        if batch_result.get("usage"):
            result["usage"].append(batch_result["usage"])
        if batch_result.get("model"):
            result["model"] = batch_result["model"]

    for start in range(0, len(valid_items), batch_size):
        batch = valid_items[start : start + batch_size]
        try:
            await merge(await _call_visual_batch(service, batch, context=context, prompt_mode=prompt_mode))
        except Exception:
            if len(batch) == 1:
                errors.append(str(batch[0].get("slot") or batch[0].get("position_id") or "image"))
            else:
                for item in batch:
                    try:
                        await merge(await _call_visual_batch(service, [item], context=context, prompt_mode=prompt_mode))
                    except Exception:
                        errors.append(str(item.get("slot") or item.get("position_id") or "image"))
        if start + batch_size < len(valid_items) and interval > 0:
            await asyncio.sleep(interval)

    seen = {
        item.get("slot") or item.get("position_id") or str(item.get("order") or "")
        for item in result["items"]
    }
    for item in valid_items:
        key = str(item.get("slot") or item.get("position_id") or item.get("order") or "")
        if key and key not in seen:
            fallback = _normalise_item({"ocr_status": "failed" if key in errors else "pending"}, item)
            result["items"].append(fallback)
            result["by_key"][key] = fallback

    return result

