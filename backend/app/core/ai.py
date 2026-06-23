from __future__ import annotations
"""AI Provider — DeepSeek / OpenAI / Anthropic unified interface."""

import json
import httpx
from app.config import get_settings
from app.core.ai_orchestration import AIProvider, AIResponse

settings = get_settings()

# Provider configs
PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
    },
}


class AI:
    """Unified AI provider using OpenAI-compatible chat completions API."""

    def __init__(self, provider: str | None = None) -> None:
        provider = provider or settings.ai_provider or "deepseek"
        cfg = PROVIDERS.get(provider, PROVIDERS["deepseek"])
        self.base_url = cfg["base_url"]
        self.api_key = settings.deepseek_api_key or ""
        self.provider_name = provider

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> AIResponse:
        """Call chat completions API."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": model or "deepseek-chat",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            body["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=body,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        tokens = data.get("usage", {}).get("total_tokens", 0)

        return AIResponse(
            raw=content,
            provider=self.provider_name,
            model=body["model"],
            tokens_used=tokens,
        )

    async def complete_json(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
    ) -> dict:
        """Call and parse JSON response."""
        response = await self.complete(
            prompt=prompt,
            system=system,
            model=model,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        return json.loads(response.raw)
