from __future__ import annotations
"""Image OCR — extract text from listing images using Qwen Vision."""

import base64
from io import BytesIO

import httpx
import logging
import os
from PIL import Image, ImageOps

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

QWEN_BASE = settings.qwen_base_url.rstrip("/")
QWEN_MODEL = settings.qwen_model

LISTING_IMAGE_OCR_PROMPT = """识别这张 Amazon Listing 图片。
优先任务：逐字提取图片上的所有可见文案。
要求：
1. 保留原文语言、大小写、数字、单位、符号、百分比和换行层级。
2. 不要翻译、不要改写、不要总结图片文案。
3. 文案按从上到下、从左到右的顺序列出；看不清的部分标为[看不清]。
4. 如果图片没有可见文案，写“可见文案：暂无”。
5. 文案之后再补“图片内容：”，简要说明产品、场景、配件、尺寸、认证或安装信息。
6. 根据已知产品信息判断图片中的产品、场景、配件、尺寸、认证或安装信息是否与产品吻合；依据不足时写“无法判断”，不要猜测。
输出格式：
可见文案：
- ...
图片内容：
...
产品场景吻合度：
- 结论：吻合 | 不吻合 | 无法判断
- 依据：...
- 错配点：暂无 | ..."""


def _build_listing_image_ocr_prompt(slot: str = "", product_context: str = "") -> str:
    context = product_context.strip()[:1500] if product_context else "暂无"
    return f"""{LISTING_IMAGE_OCR_PROMPT}
图片位置：{slot or '未设置'}
已知产品信息：
{context}"""


def _compress_image_data_url(image_data: str, *, max_side: int = 1600, quality: int = 84) -> str:
    """Normalize uploaded/captured images before OCR to reduce model failures."""
    value = (image_data or "").strip()
    if not value:
        return ""
    raw_b64 = value.split(",", 1)[-1] if value.startswith("data:image/") else value
    try:
        raw = base64.b64decode(raw_b64, validate=False)
        with Image.open(BytesIO(raw)) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode in ("RGBA", "LA"):
                    background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
                    img = background
                else:
                    img = img.convert("RGB")
            else:
                img = img.convert("RGB")
            img.thumbnail((max_side, max_side))
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception as exc:
        _logger.warning("Image compression skipped before OCR: %s", str(exc) or type(exc).__name__)
        if value.startswith("data:image/"):
            return value
        return f"data:image/jpeg;base64,{value}"


async def _call_qwen_vision(image_data: str, prompt: str, max_tokens: int = 200) -> str:
    """Call Qwen Vision API."""
    if not QWEN_KEY:
        return ""
    image_url = _compress_image_data_url(image_data)
    timeout = httpx.Timeout(30.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=True) as client:
        resp = await client.post(
            f"{QWEN_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {QWEN_KEY}"},
            json={
                "model": QWEN_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                "max_tokens": max_tokens,
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Qwen OCR HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if "choices" not in data:
            raise RuntimeError(str(data)[:500])
        return data["choices"][0]["message"]["content"].strip()
    return ""


async def extract_text_from_images(
    image_urls: list[str],
    product_context: str = "",
    slots_by_url: dict[str, str] | None = None,
) -> dict[str, str]:
    """Download images and use Qwen Vision to extract text and image content from each."""
    if not image_urls or not QWEN_KEY:
        return {}

    results = {}
    errors: list[str] = []
    timeout = httpx.Timeout(30.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=True) as client:
        for url in image_urls[:7]:
            try:
                img_resp = await client.get(url)
                img_resp.raise_for_status()
                img_b64 = base64.b64encode(img_resp.content).decode()
                slot = slots_by_url.get(url, "") if slots_by_url else ""
                text = await _call_qwen_vision(
                    img_b64,
                    _build_listing_image_ocr_prompt(slot=slot, product_context=product_context),
                    max_tokens=800,
                )
                if text:
                    results[url] = text
            except Exception as exc:
                errors.append(f"{url}: {exc!r}")
                if len(errors) >= 3 and not results:
                    break
                continue
    if not results and errors:
        raise RuntimeError("; ".join(errors[:3]))
    return results


async def extract_text_from_image_url(url: str) -> str:
    """Extract text from a single image URL."""
    results = await extract_text_from_images([url])
    return results.get(url, "")


async def extract_text_from_base64_list(items: list[dict], product_context: str = "") -> list[dict]:
    """Extract text and content description from images using Qwen Vision.

    Returns: [{"slot": "img3", "text": "...", "content_type": "usage_scenario", "mismatch": false}, ...]
    """
    if not items or not QWEN_KEY:
        if not QWEN_KEY:
            _logger.warning("Qwen API key not configured — OCR skipped")
        return []

    results = []
    errors: list[str] = []
    for item in items[:7]:
        try:
            image_data = item.get("url", "")
            slot = item.get("slot", "")
            prompt = _build_listing_image_ocr_prompt(slot=slot, product_context=product_context)
            text = await _call_qwen_vision(image_data, prompt, max_tokens=800)
            if text:
                results.append({"slot": slot, "text": text})
        except Exception as exc:
            errors.append(f"{item.get('slot', '?')}: {type(exc).__name__}: {str(exc) or '[no message]'}")
            _logger.warning("OCR failed for slot=%s: type=%s msg=%s", item.get("slot", "?"), type(exc).__name__, str(exc) or "[no message]")
            continue
    if not results and errors:
        raise RuntimeError("; ".join(errors[:3]))
    return results
