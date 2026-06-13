"""Unified AI model caller for backend services."""

from __future__ import annotations

import json
import os
from typing import Any, Literal, Optional

import httpx
from pydantic import BaseModel, Field


class UnifiedAIStatus(BaseModel):
    provider: str
    text_configured: bool
    vision_configured: bool
    text_base_url: str
    vision_base_url: str
    default_model: str
    light_model: str
    reasoning_model: str
    deep_model: str
    vision_model: str
    api_mode: str


class UnifiedChatRequest(BaseModel):
    messages: list[dict[str, Any]] = Field(default_factory=list)
    model: str = "AI_DEFAULT_MODEL"
    temperature: Optional[float] = 0.2
    max_tokens: Optional[int] = 1024
    response_format: Literal["text", "json"] = "text"


class UnifiedChatResponse(BaseModel):
    content: str
    provider: str
    model: str
    endpoint: str
    usage: Optional[dict[str, Any]] = None


class UnifiedAIClient:
    """Resolve model aliases, provider keys, and compatible endpoints in one place."""

    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER", "openai-compatible")
        self.provider_lower = self.provider.lower()
        self.text_base_url = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("APP_AI_BASE_URL")
            or "https://api.openai.com/v1"
        ).strip().rstrip("/")
        self.vision_base_url = (
            os.getenv("VISION_BASE_URL")
            or os.getenv("QWEN_BASE_URL")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        ).strip().rstrip("/")
        self.default_model = (
            os.getenv("AI_DEFAULT_MODEL")
            or os.getenv("APP_AI_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "gpt-4.1-mini"
        )
        self.light_model = os.getenv("AI_LIGHT_MODEL") or self.default_model
        self.reasoning_model = os.getenv("AI_REASONING_MODEL") or os.getenv("AI_STANDARD_MODEL") or self.default_model
        self.deep_model = os.getenv("AI_DEEP_MODEL") or self.reasoning_model
        self.vision_model = os.getenv("AI_VISION_MODEL") or os.getenv("VISION_MODEL") or "qwen3-vl-plus"
        self.api_mode = os.getenv("AI_API_MODE", "auto").lower()
        self.request_timeout = float(os.getenv("AI_REQUEST_TIMEOUT", "180"))
        self.vision_timeout = float(os.getenv("VISION_REQUEST_TIMEOUT", os.getenv("AI_REQUEST_TIMEOUT", "180")))
        self.text_api_key = self._resolve_text_api_key()
        self.vision_api_key = self._resolve_vision_api_key()

    def _is_dashscope_text(self) -> bool:
        return self.provider_lower in {"qwen", "dashscope"} or "dashscope.aliyuncs.com" in self.text_base_url

    def _resolve_text_api_key(self) -> str:
        if self._is_dashscope_text():
            return (
                os.getenv("VISION_API_KEY")
                or os.getenv("DASHSCOPE_API_KEY")
                or os.getenv("QWEN_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or os.getenv("APP_AI_KEY")
                or ""
            ).strip()
        return (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("APP_AI_KEY")
            or os.getenv("DASHSCOPE_API_KEY")
            or os.getenv("QWEN_API_KEY")
            or os.getenv("VISION_API_KEY")
            or ""
        ).strip()

    def _resolve_vision_api_key(self) -> str:
        return (
            os.getenv("VISION_API_KEY")
            or os.getenv("QWEN_API_KEY")
            or os.getenv("DASHSCOPE_API_KEY")
            or self.text_api_key
            or ""
        ).strip()

    def status(self) -> UnifiedAIStatus:
        return UnifiedAIStatus(
            provider=self.provider,
            text_configured=bool(self.text_api_key and self.text_base_url),
            vision_configured=bool(self.vision_api_key and self.vision_base_url),
            text_base_url=self.text_base_url,
            vision_base_url=self.vision_base_url,
            default_model=self.default_model,
            light_model=self.light_model,
            reasoning_model=self.reasoning_model,
            deep_model=self.deep_model,
            vision_model=self.vision_model,
            api_mode=self.api_mode,
        )

    def resolve_model(self, requested_model: str | None) -> str:
        if not requested_model or requested_model == "AI_DEFAULT_MODEL":
            return self.default_model
        if requested_model == "AI_LIGHT_MODEL":
            return self.light_model
        if requested_model == "AI_REASONING_MODEL":
            return self.reasoning_model
        if requested_model == "AI_DEEP_MODEL":
            return self.deep_model
        if requested_model == "AI_VISION_MODEL":
            return self.vision_model
        return requested_model

    def is_vision_model(self, requested_model: str | None) -> bool:
        resolved = self.resolve_model(requested_model)
        return requested_model == "AI_VISION_MODEL" or resolved == self.vision_model

    def endpoint_for_model(self, requested_model: str | None) -> tuple[str, str, str, float]:
        if self.is_vision_model(requested_model):
            return self.vision_base_url, self.vision_api_key, "vision", self.vision_timeout
        return self.text_base_url, self.text_api_key, self.provider, self.request_timeout

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = "AI_DEFAULT_MODEL",
        temperature: Optional[float] = 0.2,
        max_tokens: Optional[int] = 1024,
        response_format_json: bool = False,
    ) -> UnifiedChatResponse:
        resolved_model = self.resolve_model(model)
        base_url, api_key, provider, timeout = self.endpoint_for_model(model)
        if not base_url or not api_key:
            raise RuntimeError("AI model is not configured")

        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        is_dashscope_vision = self.is_vision_model(model) and "dashscope.aliyuncs.com" in base_url
        if response_format_json and not is_dashscope_vision:
            payload["response_format"] = {"type": "json_object"}
        if "dashscope.aliyuncs.com" in base_url:
            payload["enable_thinking"] = False

        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"].get("content") or ""
        if response_format_json:
            content = content or "{}"
            json.loads(content)
        return UnifiedChatResponse(
            content=content,
            provider=provider,
            model=resolved_model,
            endpoint=endpoint,
            usage=data.get("usage"),
        )
