from __future__ import annotations
"""Image OCR — extract text from listing images using Qwen Vision."""

import base64
import httpx
import os
from app.config import get_settings

settings = get_settings()

QWEN_KEY = None
_qwen_key_file = os.path.join(os.path.dirname(__file__), "..", ".qwen_key")
if os.path.exists(_qwen_key_file):
    try:
        with open(_qwen_key_file) as f:
            QWEN_KEY = f.read().strip()
    except Exception:
        pass

QWEN_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"


async def _call_qwen_vision(image_b64: str, prompt: str, max_tokens: int = 200) -> str:
    """Call Qwen Vision API."""
    if not QWEN_KEY:
        return ""
    async with httpx.AsyncClient(timeout=30.0) as client:
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
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    return ""


async def extract_text_from_images(image_urls: list[str]) -> dict[str, str]:
    """Download images and use Qwen Vision to extract text from each."""
    if not image_urls or not QWEN_KEY:
        return {}

    results = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for url in image_urls[:4]:
            try:
                img_resp = await client.get(url)
                img_resp.raise_for_status()
                img_b64 = base64.b64encode(img_resp.content).decode()
                text = await _call_qwen_vision(
                    img_b64,
                    "Extract ALL visible text from this Amazon product image. List every word, label, specification, and callout. Be thorough.",
                    max_tokens=300,
                )
                if text:
                    results[url] = text
            except Exception:
                continue
    return results


async def extract_text_from_image_url(url: str) -> str:
    """Extract text from a single image URL."""
    results = await extract_text_from_images([url])
    return results.get(url, "")


async def extract_text_from_base64_list(items: list[dict]) -> list[dict]:
    """Extract text and content description from images using Qwen Vision.

    Returns: [{"slot": "img3", "text": "...", "content_type": "usage_scenario", "mismatch": false}, ...]
    """
    if not items or not QWEN_KEY:
        return []

    results = []
    for item in items[:5]:
        try:
            b64 = item.get("url", "").split(",", 1)[-1]
            slot = item.get("slot", "")
            # Position-specific prompts
            prompts = {
                "main": "Describe this Amazon main image: is it pure white background? Is there text/logo/watermark? What is shown?",
                "img2": "Describe this image: what key features are highlighted? Are there icons and short text labels?",
                "img3": "Is this a real usage scenario photo or a product-only shot? Describe the environment and how the product is used.",
                "img4": "Does this image show size comparison with a reference object? Are dimensions clearly labeled?",
                "img5": "Describe the close-up details or usage steps shown. Are features clearly visible?",
                "img6": "What certifications, warranty info, or package contents are shown? Is this a trust-building image?",
                "img7": "Is this a lifestyle/atmosphere image? Describe the mood and setting.",
            }
            prompt = prompts.get(slot, "Describe this image: what is shown, any visible text, and what type of content it contains.")
            text = await _call_qwen_vision(b64, prompt, max_tokens=200)
            if text:
                results.append({"slot": slot, "text": text})
        except Exception:
            continue
    return results
