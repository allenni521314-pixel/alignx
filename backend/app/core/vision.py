import asyncio
import base64
import httpx
import logging
import os
import re
from typing import Optional
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

LISTING_IMAGE_OCR_PROMPT = """识别这张图片上的所有可见文案，逐字提取。要求：保留原文语言、大小写、数字、符号；按从上到下从左到右顺序；看不清标[看不清]。如果没有可见文案，写"可见文案：暂无"。然后简要描述图片内容（产品、场景、配件等）。"""

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
                "model": "Qwen/Qwen2.5-VL-72B-Instruct",
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


async def extract_text_from_images(image_urls: list[str], product_context: str = "", slots_by_url: Optional[dict[str, str]] = None) -> dict[str, str]:
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


async def extract_text_from_base64_list(items: list[dict], product_context: str = "") -> list[dict]:
    """Batch OCR: process images in batches of 4, batches run concurrently."""
    if not items or not QWEN_KEY:
        if not QWEN_KEY:
            _logger.warning("Qwen API key not configured — OCR skipped")
        return []
    if not items:
        return []

    BATCH_SIZE = 4

    async def _process_batch(batch: list[dict]) -> list[dict]:
        content_parts: list[dict] = []
        for item in batch:
            image_data = item.get("url", "")
            slot = item.get("slot", "")
            content_parts.append({"type": "image_url", "image_url": {"url": image_data}})
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
                        "model": "Qwen/Qwen2.5-VL-72B-Instruct",
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

        import re
        results: list[dict] = []
        for item in batch:
            slot = item.get("slot", "")
            pattern = rf"\[{re.escape(slot)}\](.*?)(?=\[|$)"
            match = re.search(pattern, raw_text, re.DOTALL)
            text = match.group(1).strip() if match else ""
            if text:
                results.append({"slot": slot, "text": text})
        return results

    batches = [items[i:i+BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    all_results = await asyncio.gather(*[_process_batch(b) for b in batches])
    return [r for batch in all_results for r in batch]
