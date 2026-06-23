from __future__ import annotations
"""Image OCR — extract text from listing images using DeepSeek Vision."""

import base64
import httpx
from app.config import get_settings

settings = get_settings()


async def extract_text_from_images(image_urls: list[str]) -> dict[str, str]:
    """Download images and use DeepSeek Vision to extract text from each.

    Returns: {url: extracted_text}
    """
    if not image_urls or not settings.deepseek_api_key:
        return {}

    results = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for url in image_urls[:6]:  # Limit to 6 images to avoid timeout
            try:
                # Download image
                img_resp = await client.get(url)
                img_resp.raise_for_status()
                img_b64 = base64.b64encode(img_resp.content).decode()

                # Call DeepSeek Vision
                resp = await client.post(
                    f"{settings.deepseek_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [{
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                                },
                                {
                                    "type": "text",
                                    "text": "Extract ALL visible text from this Amazon product image. List every word, label, specification, and callout you can see. Be thorough — include small text, icons labels, badges, and numbers. Return ONLY the extracted text, no commentary.",
                                },
                            ],
                        }],
                        "max_tokens": 500,
                    },
                )
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                if text:
                    results[url] = text
            except Exception:
                continue

    return results


async def extract_text_from_image_url(url: str) -> str:
    """Extract text from a single image URL."""
    results = await extract_text_from_images([url])
    return results.get(url, "")
