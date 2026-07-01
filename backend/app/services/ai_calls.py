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
    analysis_mode: str | None = None,
    trust_meta: dict[str, Any] | None = None,
    ai_trace: dict[str, Any] | None = None,
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
        analysis_mode=analysis_mode,
        input_payload={
            **input_payload,
            "prompt": prompt,
            "system": system,
        },
        trust_meta=trust_meta,
        ai_trace={
            **(ai_trace or {}),
            "module_name": module_name,
            "prompt_version": prompt_version,
            "analysis_mode": analysis_mode,
        },
    )
    db.add(log)
    await db.flush()
    trace = dict(log.ai_trace or {})
    trace["ai_call_id"] = log.ai_call_id
    log.ai_trace = trace

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
        log.confidence_score = _extract_confidence(parsed)
        log.risk_flags = _extract_risk_flags(parsed)
        log.token_usage = response.tokens_used
        log.ai_trace = {
            **(log.ai_trace or {}),
            "status": "success",
            "has_output": True,
        }
        await db.flush()
        return parsed
    except Exception as exc:
        if response is not None:
            log.model_name = response.model
            log.model_provider = response.provider
            log.output_raw = response.raw
            log.token_usage = response.tokens_used
        log.error_message = str(exc)
        log.ai_trace = {
            **(log.ai_trace or {}),
            "status": "failed",
            "has_output": bool(log.output_raw),
        }
        await db.flush()
        raise


def _extract_confidence(parsed: dict[str, Any]) -> float | None:
    value = parsed.get("confidence")
    if value is None:
        value = parsed.get("confidence_score")
    if value is None:
        value = parsed.get("overall_health_score")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_risk_flags(parsed: dict[str, Any]) -> list[str] | None:
    flags = parsed.get("risk_flags")
    if isinstance(flags, list):
        return [str(item) for item in flags]
    rule_check = parsed.get("rule_check")
    if isinstance(rule_check, dict):
        blocked = rule_check.get("blocked_reasons")
        warnings = rule_check.get("warnings")
        values: list[str] = []
        if isinstance(blocked, list):
            values.extend(str(item) for item in blocked)
        if isinstance(warnings, list):
            values.extend(str(item) for item in warnings)
        return values or None
    return None
