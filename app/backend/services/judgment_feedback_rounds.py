import logging
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
