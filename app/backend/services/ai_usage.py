import logging
import os
from datetime import datetime, timezone
from typing import Any

from core.database import db_manager
from models.ai_usage_logs import AIUsageLog
from sqlalchemy import func, select

logger = logging.getLogger(__name__)


DEFAULT_PRICE_CNY_PER_1M: dict[str, tuple[float, float]] = {
    # Conservative cache-miss estimates converted from official USD rates at 7.2 CNY/USD.
    # Override with AI_PRICE_<MODEL>_INPUT/OUTPUT_CNY_PER_1M when provider bills in CNY or prices change.
    "deepseek-v4-flash": (1.008, 2.016),
    "deepseek-v4-pro": (3.132, 6.264),
    "qwen2.5-vl-72b-instruct": (16.5168, 49.5432),
    "BAAI/bge-m3": (0.0, 0.0),
    "BAAI/bge-reranker-v2-m3": (0.0, 0.0),
}


def _env_price_key(model: str, side: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in model.upper()).strip("_")
    return f"AI_PRICE_{safe}_{side}_CNY_PER_1M"


def get_model_price_cny(model: str) -> tuple[float, float]:
    default_input, default_output = DEFAULT_PRICE_CNY_PER_1M.get(model, (0.0, 0.0))
    input_price = os.getenv(_env_price_key(model, "INPUT"))
    output_price = os.getenv(_env_price_key(model, "OUTPUT"))
    try:
        resolved_input = float(input_price) if input_price not in (None, "") else default_input
    except ValueError:
        resolved_input = default_input
    try:
        resolved_output = float(output_price) if output_price not in (None, "") else default_output
    except ValueError:
        resolved_output = default_output
    return resolved_input, resolved_output


def normalize_usage(usage: dict[str, Any] | None) -> tuple[int, int, int]:
    if not usage:
        return 0, 0, 0
    prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or prompt_tokens + completion_tokens)
    return prompt_tokens, completion_tokens, total_tokens


def estimate_cost_cny(model: str, usage: dict[str, Any] | None) -> tuple[float, float, float]:
    prompt_tokens, completion_tokens, _ = normalize_usage(usage)
    input_price, output_price = get_model_price_cny(model)
    cost = (prompt_tokens / 1_000_000 * input_price) + (completion_tokens / 1_000_000 * output_price)
    return round(cost, 6), input_price, output_price


async def record_ai_usage(
    *,
    provider: str,
    model: str,
    module: str,
    endpoint: str,
    usage: dict[str, Any] | None,
    user_id: str | None = None,
) -> None:
    if not db_manager.async_session_maker:
        return

    prompt_tokens, completion_tokens, total_tokens = normalize_usage(usage)
    if total_tokens <= 0:
        return

    cost, input_price, output_price = estimate_cost_cny(model, usage)
    try:
        async with db_manager.async_session_maker() as session:
            session.add(
                AIUsageLog(
                    provider=provider,
                    model=model,
                    module=module,
                    endpoint=endpoint,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    estimated_cost_cny=cost,
                    input_cost_per_1m_cny=input_price,
                    output_cost_per_1m_cny=output_price,
                    user_id=user_id,
                )
            )
            await session.commit()
    except Exception:
        logger.exception("Failed to record AI usage")


async def get_ai_usage_summary(days: int = 7) -> dict[str, Any]:
    if not db_manager.async_session_maker:
        return {"days": days, "total_tokens": 0, "estimated_cost_cny": 0.0, "by_model": []}

    since = datetime.now(timezone.utc).replace(tzinfo=None)
    if days > 0:
        from datetime import timedelta

        since = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None)

    async with db_manager.async_session_maker() as session:
        filters = [AIUsageLog.created_at >= since] if days > 0 else []
        total_row = (
            await session.execute(
                select(
                    func.coalesce(func.sum(AIUsageLog.prompt_tokens), 0),
                    func.coalesce(func.sum(AIUsageLog.completion_tokens), 0),
                    func.coalesce(func.sum(AIUsageLog.total_tokens), 0),
                    func.coalesce(func.sum(AIUsageLog.estimated_cost_cny), 0.0),
                    func.count(AIUsageLog.id),
                ).where(*filters)
            )
        ).one()
        model_rows = (
            await session.execute(
                select(
                    AIUsageLog.provider,
                    AIUsageLog.model,
                    AIUsageLog.module,
                    func.coalesce(func.sum(AIUsageLog.prompt_tokens), 0),
                    func.coalesce(func.sum(AIUsageLog.completion_tokens), 0),
                    func.coalesce(func.sum(AIUsageLog.total_tokens), 0),
                    func.coalesce(func.sum(AIUsageLog.estimated_cost_cny), 0.0),
                    func.count(AIUsageLog.id),
                )
                .where(*filters)
                .group_by(AIUsageLog.provider, AIUsageLog.model, AIUsageLog.module)
                .order_by(func.coalesce(func.sum(AIUsageLog.estimated_cost_cny), 0.0).desc())
            )
        ).all()

    return {
        "days": days,
        "prompt_tokens": int(total_row[0] or 0),
        "completion_tokens": int(total_row[1] or 0),
        "total_tokens": int(total_row[2] or 0),
        "estimated_cost_cny": round(float(total_row[3] or 0.0), 6),
        "calls": int(total_row[4] or 0),
        "by_model": [
            {
                "provider": row[0],
                "model": row[1],
                "module": row[2],
                "prompt_tokens": int(row[3] or 0),
                "completion_tokens": int(row[4] or 0),
                "total_tokens": int(row[5] or 0),
                "estimated_cost_cny": round(float(row[6] or 0.0), 6),
                "calls": int(row[7] or 0),
            }
            for row in model_rows
        ],
    }
