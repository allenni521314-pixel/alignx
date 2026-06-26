from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai import AI
from app.models import AiCallLog
from app.services.access import require_user_id


async def complete_json_with_log(
    *,
    db: AsyncSession,
    user_id: str | None,
    module_name: str,
    prompt_version: str,
    prompt: str,
    system: str | None,
    input_payload: dict[str, Any],
    asin: str | None = None,
    store_id: str | None = None,
    model: str | None = None,
    max_tokens: int = 8192,
) -> dict:
    uid = require_user_id(user_id)
    ai = AI()
    model_name = model or "deepseek-chat"
    log = AiCallLog(
        user_id=uid,
        store_id=store_id,
        asin=asin,
        module_name=module_name,
        model_name=model_name,
        model_provider=ai.provider_name,
        prompt_version=prompt_version,
        input_payload={
            **input_payload,
            "prompt": prompt,
            "system": system,
        },
    )
    db.add(log)
    await db.flush()

    response = None
    try:
        response = await ai.complete(
            prompt=prompt,
            system=system,
            model=model,
            temperature=0.1,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.raw)
        log.model_name = response.model
        log.model_provider = response.provider
        log.output_raw = response.raw
        log.output_parsed = parsed
        log.token_usage = response.tokens_used
        await db.flush()
        return parsed
    except Exception as exc:
        if response is not None:
            log.model_name = response.model
            log.model_provider = response.provider
            log.output_raw = response.raw
            log.token_usage = response.tokens_used
        log.error_message = str(exc)
        await db.flush()
        raise
