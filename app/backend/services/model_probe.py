"""Runtime probes for configured AI providers.

These probes intentionally use tiny prompts/payloads and return only sanitized
status data. They prove that a configured model is callable without exposing
provider secrets.
"""

from __future__ import annotations

import base64
import os
import time
from typing import Any

import httpx
from openai import AsyncOpenAI
from schemas.aihub import ChatMessage, ContentPartImage, ContentPartText, GenTxtRequest, ImageUrl
from services.aihub import AIHubService

ONE_PIXEL_PNG = base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?"
    b"\x00\x05\xfe\x02\xfeA\xe2#\xb5\x00\x00\x00\x00IEND\xaeB`\x82"
).decode("ascii")


def _sanitize_error(exc: Exception) -> str:
    text = str(exc)
    for key_name in ("OPENAI_API_KEY", "APP_AI_KEY", "VISION_API_KEY", "QWEN_API_KEY", "SILICONFLOW_API_KEY"):
        secret = os.getenv(key_name)
        if secret:
            text = text.replace(secret, "***")
    if len(text) > 260:
        text = text[:257] + "..."
    return text


async def _timed_probe(name: str, provider: str, model: str, runner) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        detail = await runner()
        return {
            "name": name,
            "provider": provider,
            "model": model,
            "ok": True,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "detail": detail or "ok",
        }
    except Exception as exc:
        return {
            "name": name,
            "provider": provider,
            "model": model,
            "ok": False,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "error": _sanitize_error(exc),
        }


async def probe_ai_models() -> dict[str, Any]:
    service = AIHubService()

    text_model = service.reasoning_model
    deep_model = service.deep_model
    vision_model = service.vision_model
    embedding_model = (os.getenv("AI_EMBEDDING_MODEL") or os.getenv("EMBEDDING_MODEL") or "").strip()
    rerank_model = (os.getenv("RERANK_MODEL") or os.getenv("AI_RERANK_MODEL") or "").strip()
    siliconflow_key = (os.getenv("SILICONFLOW_API_KEY") or "").strip()

    async def probe_text_reasoning() -> str:
        response = await service.gentxt(
            GenTxtRequest(
                messages=[ChatMessage(role="user", content='只返回JSON: {"ok":true}')],
                model="AI_REASONING_MODEL",
                temperature=0,
                max_tokens=40,
            )
        )
        return f"content_len={len(response.content or '')}"

    async def probe_text_deep() -> str:
        response = await service.gentxt(
            GenTxtRequest(
                messages=[ChatMessage(role="user", content='只返回JSON: {"deep":true}')],
                model="AI_DEEP_MODEL",
                temperature=0,
                max_tokens=40,
            )
        )
        return f"content_len={len(response.content or '')}"

    async def probe_vision() -> str:
        response = await service.gentxt(
            GenTxtRequest(
                messages=[
                    ChatMessage(
                        role="user",
                        content=[
                            ContentPartText(type="text", text='OCR测试：这是一张1像素图片。只返回JSON: {"image_seen":true}'),
                            ContentPartImage(
                                type="image_url",
                                image_url=ImageUrl(url=f"data:image/png;base64,{ONE_PIXEL_PNG}"),
                            ),
                        ],
                    )
                ],
                model="AI_VISION_MODEL",
                temperature=0,
                max_tokens=80,
            )
        )
        return f"content_len={len(response.content or '')}"

    async def probe_embedding() -> str:
        api_key = (os.getenv("EMBEDDING_API_KEY") or siliconflow_key).strip()
        base_url = (os.getenv("EMBEDDING_BASE_URL") or os.getenv("SILICONFLOW_BASE_URL") or "").strip().rstrip("/")
        if not embedding_model or not api_key or not base_url:
            raise RuntimeError("Embedding model/base_url/api_key not configured")
        client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=30, http_client=httpx.AsyncClient(trust_env=False))
        response = await client.embeddings.create(model=embedding_model, input=["AlignX semantic probe"])
        dim = len(response.data[0].embedding) if response.data else 0
        return f"dimension={dim}"

    async def probe_rerank() -> str:
        api_key = (os.getenv("RERANK_API_KEY") or siliconflow_key).strip()
        base_url = (os.getenv("RERANK_BASE_URL") or os.getenv("SILICONFLOW_BASE_URL") or "").strip().rstrip("/")
        if not rerank_model or not api_key or not base_url:
            raise RuntimeError("Rerank model/base_url/api_key not configured")
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.post(
                f"{base_url}/rerank",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": rerank_model,
                    "query": "cat litter odor control",
                    "documents": ["cat litter box deodorizer", "wireless phone case"],
                    "top_n": 2,
                },
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results") or []
        return f"results={len(results)}"

    probes = [
        await _timed_probe("DeepSeek标准推理", os.getenv("AI_PROVIDER", "openai-compatible"), text_model, probe_text_reasoning),
        await _timed_probe("DeepSeek深度诊断", os.getenv("AI_PROVIDER", "openai-compatible"), deep_model, probe_text_deep),
        await _timed_probe("Qwen图片/OCR视觉", os.getenv("VISION_PROVIDER") or "qwen", vision_model, probe_vision),
        await _timed_probe("SiliconFlow语义向量", "SiliconFlow", embedding_model or "未配置", probe_embedding),
        await _timed_probe("SiliconFlow语义精排", "SiliconFlow", rerank_model or "未配置", probe_rerank),
    ]
    return {
        "ok": all(item["ok"] for item in probes),
        "checked_at": int(time.time()),
        "probes": probes,
    }
