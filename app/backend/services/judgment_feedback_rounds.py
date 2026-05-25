import logging
import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.judgment_feedback_rounds import JudgmentFeedbackRound

logger = logging.getLogger(__name__)


class JudgmentFeedbackRoundService:
    """Persistence for every judgment -> ad validation -> feedback iteration."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def next_round(
        self,
        *,
        user_id: str,
        asin: str | None = None,
        listing_diagnosis_id: int | None = None,
        product_id: int | None = None,
    ) -> int:
        query = select(func.max(JudgmentFeedbackRound.optimization_round)).where(
            JudgmentFeedbackRound.user_id == user_id
        )
        if asin:
            query = query.where(JudgmentFeedbackRound.asin == asin)
        if listing_diagnosis_id:
            query = query.where(JudgmentFeedbackRound.listing_diagnosis_id == listing_diagnosis_id)
        if product_id:
            query = query.where(JudgmentFeedbackRound.product_id == product_id)
        result = await self.db.execute(query)
        current = result.scalar() or 0
        return int(current) + 1

    async def create(self, data: dict[str, Any], user_id: str) -> JudgmentFeedbackRound:
        payload = dict(data)
        payload["user_id"] = user_id
        payload.setdefault("optimization_round", await self.next_round(
            user_id=user_id,
            asin=payload.get("asin"),
            listing_diagnosis_id=payload.get("listing_diagnosis_id"),
            product_id=payload.get("product_id"),
        ))
        obj = JudgmentFeedbackRound(**payload)
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        logger.info("Created judgment feedback round id=%s", obj.id)
        return obj

    async def update(self, obj_id: int, data: dict[str, Any], user_id: str) -> Optional[JudgmentFeedbackRound]:
        query = select(JudgmentFeedbackRound).where(
            JudgmentFeedbackRound.id == obj_id,
            JudgmentFeedbackRound.user_id == user_id,
        )
        result = await self.db.execute(query)
        obj = result.scalar_one_or_none()
        if not obj:
            return None

        for key, value in data.items():
            if hasattr(obj, key) and key not in {"id", "user_id", "created_at"}:
                setattr(obj, key, value)
        obj.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def list(
        self,
        *,
        user_id: str,
        asin: str | None = None,
        listing_diagnosis_id: int | None = None,
        product_id: int | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> tuple[list[JudgmentFeedbackRound], int]:
        base = select(JudgmentFeedbackRound).where(JudgmentFeedbackRound.user_id == user_id)
        count = select(func.count(JudgmentFeedbackRound.id)).where(JudgmentFeedbackRound.user_id == user_id)
        for field, value in {
            "asin": asin,
            "listing_diagnosis_id": listing_diagnosis_id,
            "product_id": product_id,
        }.items():
            if value is not None and value != "":
                base = base.where(getattr(JudgmentFeedbackRound, field) == value)
                count = count.where(getattr(JudgmentFeedbackRound, field) == value)

        total_result = await self.db.execute(count)
        total = total_result.scalar() or 0
        result = await self.db.execute(
            base.order_by(desc(JudgmentFeedbackRound.optimization_round), desc(JudgmentFeedbackRound.id))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), int(total)

    async def learning_memory(
        self,
        *,
        user_id: str,
        asin: str | None = None,
        product_id: int | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        """Aggregate saved feedback rounds into reusable decision memory."""
        items, total = await self.list(
            user_id=user_id,
            asin=asin,
            product_id=product_id,
            limit=limit,
            skip=0,
        )

        completed = [
            item for item in items if (item.hit_status or "").strip() in {"已命中", "命中", "未命中", "部分命中"}
        ]
        hits = [item for item in completed if (item.hit_status or "").strip() in {"已命中", "命中"}]
        misses = [item for item in completed if (item.hit_status or "").strip() == "未命中"]

        failure_counts: dict[str, int] = {}
        action_counts: dict[str, int] = {}
        reusable_learnings: list[dict[str, Any]] = []

        for item in completed:
            reason = (item.miss_reason or "").strip() or "none"
            if reason != "none":
                failure_counts[reason] = failure_counts.get(reason, 0) + 1

            action = (item.suggested_action or "").strip()
            if action:
                action_counts[action] = action_counts.get(action, 0) + 1

            ad_result = _loads(item.ad_result)
            if (item.hit_status or "").strip() in {"已命中", "命中"}:
                reusable_learnings.append(
                    {
                        "round_id": item.id,
                        "optimization_round": item.optimization_round,
                        "diagnosis_issue": item.diagnosis_issue,
                        "suggested_action": item.suggested_action,
                        "ad_result": ad_result,
                        "confidence_gain": round((item.confidence_after or 0) - (item.confidence_before or 0), 2),
                    }
                )

        top_failure_reasons = sorted(
            [{"reason": key, "count": value} for key, value in failure_counts.items()],
            key=lambda row: row["count"],
            reverse=True,
        )[:5]
        top_actions = sorted(
            [{"action": key, "count": value} for key, value in action_counts.items()],
            key=lambda row: row["count"],
            reverse=True,
        )[:5]
        hit_rate = round(len(hits) * 100 / len(completed), 1) if completed else 0

        return {
            "scope": "product" if product_id or asin else "account",
            "total_rounds": total,
            "completed_rounds": len(completed),
            "hit_rounds": len(hits),
            "miss_rounds": len(misses),
            "hit_rate": hit_rate,
            "top_failure_reasons": top_failure_reasons,
            "top_actions": top_actions,
            "reusable_learnings": reusable_learnings[:5],
            "confidence": "高" if len(completed) >= 10 else "中" if len(completed) >= 3 else "低",
            "next_memory_action": (
                "优先复用已命中动作，并对高频失败原因单独建假设验证。"
                if completed
                else "先完成至少1轮带hit_status和miss_reason的复盘，才能形成记忆。"
            ),
        }


def _loads(value: str | None) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
