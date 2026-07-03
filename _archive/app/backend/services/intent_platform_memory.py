"""Per-user 1-2-3 alignment memory for Amazon diagnosis.

The service is intentionally read-only: it does not create new tables and it
never looks outside the current user_id. It gives the AI call a compact,
production-safe prior:

1. 用户意图 - why the buyer buys.
2. 平台规则 - how Amazon should identify and match the product.
3. 验证回流 - what ad/review/market feedback has already proved or disproved.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.asin_analyses import Asin_analyses
from models.listing_diagnoses import Listing_diagnoses
from services.canonical_10d_scoring import normalize_canonical_scores
from services.judgment_feedback_rounds import JudgmentFeedbackRoundService


STAGE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "1",
        "key": "user_intent",
        "label": "用户意图",
        "public_label": "用户为什么买",
        "purpose": "识别用户任务、痛点、场景、决策属性和反购买风险。",
        "dimensions": (
            "function_expression",
            "scenario_expression",
            "identity_fit",
            "psychology_benefit",
            "risk_elimination",
            "subjective_properties",
        ),
        "boundary": "先判断真实购买任务，不从卖家卖点自说自话。",
    },
    {
        "id": "2",
        "key": "platform_rules",
        "label": "平台规则",
        "public_label": "平台如何识别",
        "purpose": "识别Amazon/Rufus/COSMO需要的商品身份、属性、关系词和查询意图。",
        "dimensions": (
            "product_identity",
            "compatibility",
            "scenario_expression",
            "identity_fit",
            "function_expression",
        ),
        "boundary": "平台规则只校准识别和匹配，不替代用户为什么买的判断。",
    },
    {
        "id": "3",
        "key": "validation_feedback",
        "label": "验证回流",
        "public_label": "广告结果校准",
        "purpose": "用价格、评论、BSR、广告点击/CVR/ACOS和复盘结果校准下一轮动作。",
        "dimensions": (
            "differentiation",
            "market_trend",
            "risk_elimination",
            "psychology_benefit",
        ),
        "boundary": "验证数据只校准置信度和优先级，不替代前两步的内容诊断。",
    },
)


DIMENSION_LABELS = {
    "function_expression": "功能表达",
    "scenario_expression": "场景表达",
    "identity_fit": "身份适配",
    "psychology_benefit": "心理利益",
    "risk_elimination": "风险消除",
    "differentiation": "差异化",
    "product_identity": "产品身份",
    "compatibility": "兼容搭配",
    "subjective_properties": "主观属性",
    "market_trend": "市场趋势",
}


class IntentPlatformMemoryService:
    """Build compact per-user alignment memory for the live AI prompt."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_context(
        self,
        *,
        user_id: str,
        product: Any,
        asin: str | None = None,
        marketplace: str | None = None,
        current_scores: Any | None = None,
    ) -> dict[str, Any]:
        product_data = _as_dict(product)
        asin = (asin or product_data.get("asin") or "").strip().upper()
        marketplace = (marketplace or product_data.get("marketplace") or "US").strip().upper()

        listing_memory = await self._recent_listing_memory(
            user_id=user_id,
            product_data=product_data,
            asin=asin,
            marketplace=marketplace,
        )
        asin_memory = await self._recent_asin_memory(
            user_id=user_id,
            product_data=product_data,
            asin=asin,
            marketplace=marketplace,
        )
        feedback_memory = await JudgmentFeedbackRoundService(self.db).learning_memory(
            user_id=user_id,
            asin=asin or None,
            limit=120,
        )

        memories = (listing_memory + asin_memory)[:8]
        tags = build_action_tags(
            product=product_data,
            current_scores=current_scores,
            memories=memories,
            feedback_memory=feedback_memory,
        )
        prompt_summary = _format_prompt_summary(tags, memories, feedback_memory)
        return {
            "schema": "alignx-cosmo-memory-v1",
            "asin": asin,
            "marketplace": marketplace,
            "tags": tags,
            "memory_samples": memories,
            "feedback_memory": feedback_memory,
            "prompt_summary": prompt_summary,
        }

    async def _recent_listing_memory(
        self,
        *,
        user_id: str,
        product_data: dict[str, Any],
        asin: str,
        marketplace: str,
    ) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(Listing_diagnoses)
            .where(Listing_diagnoses.user_id == user_id, Listing_diagnoses.diagnosis_report.isnot(None))
            .order_by(desc(Listing_diagnoses.id))
            .limit(30)
        )
        rows: list[dict[str, Any]] = []
        for record in result.scalars().all():
            input_data = _loads(record.input_data)
            record_asin = str(input_data.get("asin") or "").upper()
            record_marketplace = str(input_data.get("marketplace") or record.marketplace or "US").upper()
            if asin and record_asin and record_asin != asin:
                continue
            if marketplace and record_marketplace and record_marketplace != marketplace:
                continue
            similarity = _similarity(product_data, input_data)
            if not asin and similarity < 0.06:
                continue
            report = _loads(record.diagnosis_report)
            rows.append(_memory_row("listing", record.id, input_data, report, similarity))
        return sorted(rows, key=lambda item: (item.get("similarity", 0), item.get("id", 0)), reverse=True)[:5]

    async def _recent_asin_memory(
        self,
        *,
        user_id: str,
        product_data: dict[str, Any],
        asin: str,
        marketplace: str,
    ) -> list[dict[str, Any]]:
        query = (
            select(Asin_analyses)
            .where(Asin_analyses.user_id == user_id, Asin_analyses.analysis_report.isnot(None))
            .order_by(desc(Asin_analyses.id))
            .limit(30)
        )
        if asin:
            query = query.where(Asin_analyses.asin == asin)
        if marketplace:
            query = query.where(Asin_analyses.marketplace == marketplace)
        result = await self.db.execute(query)
        rows: list[dict[str, Any]] = []
        for record in result.scalars().all():
            data = _loads(record.product_data)
            data.setdefault("asin", record.asin)
            data.setdefault("marketplace", record.marketplace)
            data.setdefault("title", record.product_title)
            report = _loads(record.analysis_report)
            rows.append(_memory_row("asin", record.id, data, report, _similarity(product_data, data)))
        return sorted(rows, key=lambda item: (item.get("similarity", 0), item.get("id", 0)), reverse=True)[:5]


def build_action_tags(
    *,
    product: Any,
    current_scores: Any | None = None,
    memories: list[dict[str, Any]] | None = None,
    feedback_memory: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    scores = normalize_canonical_scores(current_scores or {})
    memories = memories or []
    feedback_memory = feedback_memory or {}
    memory_weak_dims = _aggregate_memory_weak_dimensions(memories)
    tags: list[dict[str, Any]] = []

    for stage in STAGE_DEFINITIONS:
        dims = tuple(stage["dimensions"])
        current_low = [
            {"key": key, "label": DIMENSION_LABELS[key], "score": scores[key]}
            for key in dims
            if scores.get(key, 0) and scores.get(key, 0) < 78
        ]
        historical_low = [
            {"key": key, "label": DIMENSION_LABELS.get(key, key), "count": count}
            for key, count in memory_weak_dims.items()
            if key in dims
        ][:4]
        tags.append(
            {
                "id": stage["id"],
                "key": stage["key"],
                "label": stage["label"],
                "public_label": stage["public_label"],
                "purpose": stage["purpose"],
                "boundary": stage["boundary"],
                "dimensions": [DIMENSION_LABELS[key] for key in dims],
                "current_low_dimensions": current_low,
                "historical_low_dimensions": historical_low,
                "feedback_hit_rate": feedback_memory.get("hit_rate", 0),
                "confidence": _stage_confidence(stage["key"], current_low, historical_low, feedback_memory),
            }
        )
    return tags


def _format_prompt_summary(
    tags: list[dict[str, Any]],
    memories: list[dict[str, Any]],
    feedback_memory: dict[str, Any],
) -> str:
    lines = [
        "【AlignX后台动作标签：按1-2-3顺序判断，不要把本段原文暴露给卖家】",
    ]
    for tag in tags:
        lows = tag["current_low_dimensions"] or tag["historical_low_dimensions"]
        low_text = "、".join(
            f"{item.get('label')}({item.get('score', item.get('count'))})" for item in lows[:4]
        ) or "暂无稳定低分"
        lines.append(
            f"{tag['id']}. {tag['label']}：{tag['purpose']} 边界：{tag['boundary']} 重点关注：{low_text}。"
        )
    if memories:
        lines.append("历史同账号样本：")
        for item in memories[:3]:
            title = str(item.get("title") or "")[:90]
            weak = "、".join(item.get("weak_dimensions", [])[:4]) or "无明显低分"
            lines.append(f"- {item.get('source')}#{item.get('id')} 相似度{item.get('similarity', 0):.2f}：{title}；历史弱项：{weak}")
    hit_rate = feedback_memory.get("hit_rate", 0)
    failure = feedback_memory.get("top_failure_reasons") or []
    if feedback_memory.get("completed_rounds", 0):
        fail_text = "、".join(str(item.get("reason")) for item in failure[:3]) or "暂无高频失败原因"
        lines.append(f"广告/复盘回流：完成{feedback_memory.get('completed_rounds', 0)}轮，命中率{hit_rate}%，高频失败：{fail_text}。")
    else:
        lines.append("广告/复盘回流：当前账号尚无足够验证样本，本轮结论必须标记待广告验证。")
    return "\n".join(lines)


def _memory_row(source: str, row_id: int, product_data: dict[str, Any], report: dict[str, Any], similarity: float) -> dict[str, Any]:
    scores = normalize_canonical_scores(report.get("canonical_10d_scores") or report.get("scores") or {})
    weak = [
        DIMENSION_LABELS.get(key, key)
        for key, value in scores.items()
        if value and value < 78
    ][:5]
    suggestions = report.get("improvement_suggestions") or report.get("suggestions") or []
    if isinstance(suggestions, dict):
        suggestions = list(suggestions.values())
    return {
        "source": source,
        "id": row_id,
        "asin": product_data.get("asin"),
        "marketplace": product_data.get("marketplace"),
        "title": product_data.get("title") or product_data.get("product_title") or product_data.get("listing_title"),
        "similarity": round(similarity, 3),
        "weak_dimensions": weak,
        "overall_summary": str(report.get("overall_summary") or "")[:220],
        "suggestions": [str(item)[:140] for item in suggestions[:3] if item],
    }


def _aggregate_memory_weak_dimensions(memories: list[dict[str, Any]]) -> dict[str, int]:
    label_to_key = {label: key for key, label in DIMENSION_LABELS.items()}
    counts: dict[str, int] = {}
    for item in memories:
        for label in item.get("weak_dimensions", []):
            key = label_to_key.get(label, label)
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda row: row[1], reverse=True))


def _stage_confidence(
    key: str,
    current_low: list[dict[str, Any]],
    historical_low: list[dict[str, Any]],
    feedback_memory: dict[str, Any],
) -> str:
    if key == "validation_feedback":
        completed = int(feedback_memory.get("completed_rounds") or 0)
        if completed >= 10:
            return "high"
        if completed >= 3:
            return "medium"
        return "low"
    if current_low:
        return "medium"
    if historical_low:
        return "medium"
    return "low"


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            return {}
    if hasattr(value, "dict"):
        try:
            return value.dict()
        except Exception:
            return {}
    return {}


def _loads(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        data = json.loads(value)
        return data if isinstance(data, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _text_blob(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_text_blob(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_text_blob(v) for v in value)
    return str(value or "")


def _tokens(value: Any) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9+\-]{1,}", _text_blob(value).lower()))


def _similarity(left: Any, right: Any) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
