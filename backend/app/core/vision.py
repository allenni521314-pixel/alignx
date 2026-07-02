import base64
import httpx
import logging
import os
import re
from typing import Optional, Dict, List, Any
from app.config import get_settings

settings = get_settings()
_logger = logging.getLogger(__name__)

QWEN_KEY = settings.qwen_api_key
if not QWEN_KEY:
    _qwen_key_file = os.path.join(os.path.dirname(__file__), "..", "..", ".qwen_key")
    if os.path.exists(_qwen_key_file):
        try:
            with open(_qwen_key_file) as f:
                QWEN_KEY = f.read().strip()
        except Exception:
            pass

_logger.debug("QWEN_KEY loaded: %s chars", len(QWEN_KEY) if QWEN_KEY else 0)

QWEN_BASE = settings.qwen_base_url
QWEN_MODEL = settings.qwen_model

LISTING_IMAGE_OCR_PROMPT = """识别这张图片上的所有可见文案，逐字提取。要求：保留原文语言、大小写、数字、符号；按从上到下从左到右顺序；看不清标[看不清]。如果没有可见文案，写"可见文案：暂无"。然后简要描述图片内容（产品、场景、配件等）。"""

def _image_data_url(image_data: str) -> str:
    image_data = (image_data or "").strip()
    if image_data.startswith("data:image/"):
        return image_data
    if "," in image_data and image_data.split(",", 1)[0].startswith("data:"):
        image_data = image_data.split(",", 1)[1].strip()

    mime = "image/jpeg"
    if image_data.startswith("iVBOR"):
        mime = "image/png"
    elif image_data.startswith("R0lG"):
        mime = "image/gif"
    elif image_data.startswith("UklGR"):
        mime = "image/webp"
    return f"data:{mime};base64,{image_data}"


def _build_listing_image_ocr_prompt(slot: str = "", product_context: str = "") -> str:
    context = product_context.strip()[:1500] if product_context else "暂无"
    return f"""{LISTING_IMAGE_OCR_PROMPT}
图片位置：{slot or '未设置'}
已知产品信息：{context}"""

async def _call_qwen_vision(image_b64: str, prompt: str, max_tokens: int = 200) -> str:
    if not QWEN_KEY:
        return ""
    timeout = httpx.Timeout(30.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        resp = await client.post(
            f"{QWEN_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {QWEN_KEY}"},
            json={
                "model": QWEN_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": _image_data_url(image_b64)}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if "choices" not in data:
            raise RuntimeError(str(data)[:500])
        return data["choices"][0]["message"]["content"].strip()


async def extract_text_from_images(image_urls: list, product_context: str = "", slots_by_url: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    if not image_urls or not QWEN_KEY:
        return {}
    results = {}
    errors = []  # type: list[str]
    timeout = httpx.Timeout(30.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        for url in image_urls[:7]:
            try:
                img_resp = await client.get(url)
                img_resp.raise_for_status()
                img_b64 = base64.b64encode(img_resp.content).decode()
                slot = slots_by_url.get(url, "") if slots_by_url else ""
                text = await _call_qwen_vision(img_b64, _build_listing_image_ocr_prompt(slot=slot, product_context=product_context), max_tokens=800)
                if text: results[url] = text
            except Exception as exc:
                errors.append(f"{url}: {exc!r}")
                if len(errors) >= 3 and not results: break
                continue
    if not results and errors: raise RuntimeError("; ".join(errors[:3]))
    return results


async def extract_text_from_image_url(url: str) -> str:
    results = await extract_text_from_images([url])
    return results.get(url, "")


async def extract_text_from_base64_list(items: list, product_context: str = "") -> list:
    """OCR uploaded images and retry missing slots one by one."""
    if not items or not QWEN_KEY:
        if not QWEN_KEY:
            _logger.warning("Qwen API key not configured — OCR skipped")
        return []
    if not items:
        return []

    BATCH_SIZE = 3

    async def _process_batch(batch: list) -> list:
        content_parts = []
        for item in batch:
            image_data = item.get("url", "")
            slot = item.get("slot", "")
            content_parts.append({"type": "image_url", "image_url": {"url": _image_data_url(image_data)}})
            content_parts.append({"type": "text", "text": f"[图片位置: {slot}]"})

        batch_prompt = f"""逐一识别以下 {len(batch)} 张图片的可见文案。
对每张图片按「图片位置」标注，逐字提取所有可见文字。如果没有可见文案，写"可见文案：暂无"。
已知产品信息：{product_context[:500] if product_context else '暂无'}

输出格式（每个位置一段）：
[img2]
可见文案：...
"""
        content_parts.append({"type": "text", "text": batch_prompt})

        try:
            timeout = httpx.Timeout(60.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                resp = await client.post(
                    f"{QWEN_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {QWEN_KEY}"},
                    json={
                        "model": QWEN_MODEL,
                        "messages": [{"role": "user", "content": content_parts}],
                        "max_tokens": 2048,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                if "choices" not in data:
                    raise RuntimeError(str(data)[:500])
                raw_text = data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            _logger.warning("Batch OCR failed: %s", exc)
            return []

        return _parse_batch_ocr(raw_text, batch)

    batches = [items[i:i+BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    all_results = []
    for batch in batches:
        all_results.extend(await _process_batch(batch))

    found_slots = {str(item.get("slot", "")).strip() for item in all_results if item.get("slot")}
    missing_items = [
        item for item in items
        if str(item.get("slot", "")).strip() and str(item.get("slot", "")).strip() not in found_slots
    ]
    for item in missing_items:
        result = await _process_single_item(item, product_context=product_context)
        if result:
            all_results.append(result)

    return all_results


async def _process_single_item(item: dict, product_context: str = "") -> Optional[dict]:
    slot = str(item.get("slot", "")).strip()
    image_data = item.get("url", "")
    if not slot or not image_data:
        return None
    try:
        text = await _call_qwen_vision(
            image_data,
            _build_listing_image_ocr_prompt(slot=slot, product_context=product_context),
            max_tokens=1200,
        )
    except Exception as exc:
        _logger.warning("Single OCR failed for slot %s: %s", slot, exc)
        return None
    text = (text or "").strip()
    if not text:
        return None
    return {"slot": slot, "text": text}


def _parse_batch_ocr(raw_text: str, batch: list) -> list[dict]:
    """Parse OCR output without requiring one exact marker format."""
    results: list[dict] = []
    if not raw_text:
        return results

    slots = [str(item.get("slot", "")).strip() for item in batch if item.get("slot")]
    for slot in slots:
        patterns = [
            rf"\[{re.escape(slot)}\]\s*(.*?)(?=\n\s*\[[^\]]+\]\s*|\Z)",
            rf"(?:图片位置|位置)\s*[:：]\s*{re.escape(slot)}\s*(.*?)(?=\n\s*(?:图片位置|位置)\s*[:：]\s*|\Z)",
        ]
        text = ""
        for pattern in patterns:
            match = re.search(pattern, raw_text, re.DOTALL | re.IGNORECASE)
            if match:
                text = match.group(1).strip()
                break
        if text:
            results.append({"slot": slot, "text": text})

    if not results and len(slots) == 1:
        results.append({"slot": slots[0], "text": raw_text.strip()})

    return results
