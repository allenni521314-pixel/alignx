from __future__ import annotations
"""Image OCR — extract text from listing images using Qwen Vision."""

import base64
import httpx
import os
from app.config import get_settings

settings = get_settings()

QWEN_KEY = settings.qwen_api_key
if not QWEN_KEY:
    _qwen_key_file = os.path.join(os.path.dirname(__file__), "..", "..", ".qwen_key")
    if os.path.exists(_qwen_key_file):
        try:
            with open(_qwen_key_file) as f:
                QWEN_KEY = f.read().strip()
        except Exception:
            pass

QWEN_BASE = settings.qwen_base_url

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


async def _call_qwen_vision(image_b64: str, prompt: str, max_tokens: int = 200) -> str:
    """Call Qwen Vision API."""
    if not QWEN_KEY:
        return ""
    timeout = httpx.Timeout(30.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        resp = await client.post(
            f"{QWEN_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {QWEN_KEY}"},
            json={
                "model": "qwen-vl-max",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
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
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
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
        return []

    results = []
    for item in items[:7]:
        try:
            b64 = item.get("url", "").split(",", 1)[-1]
            slot = item.get("slot", "")
            prompt = _build_listing_image_ocr_prompt(slot=slot, product_context=product_context)
            text = await _call_qwen_vision(b64, prompt, max_tokens=800)
            if text:
                results.append({"slot": slot, "text": text})
        except Exception:
            continue
    return results
