import logging
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ad_validation_results import AdValidationResult

logger = logging.getLogger(__name__)


class AdValidationResultService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict[str, Any], user_id: str) -> AdValidationResult:
        obj = AdValidationResult(**data, user_id=user_id)
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, obj_id: int, user_id: Optional[str | list[str]] = None) -> Optional[AdValidationResult]:
        query = select(AdValidationResult).where(AdValidationResult.id == obj_id)
        if isinstance(user_id, list):
            query = query.where(AdValidationResult.user_id.in_(user_id))
        elif user_id:
            query = query.where(AdValidationResult.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_list(
        self,
        skip: int = 0,
        limit: int = 20,
        user_id: Optional[str | list[str]] = None,
        query_dict: Optional[dict[str, Any]] = None,
        sort: Optional[str] = None,
    ) -> dict[str, Any]:
        query = select(AdValidationResult)
        count_query = select(func.count(AdValidationResult.id))

        if isinstance(user_id, list):
            query = query.where(AdValidationResult.user_id.in_(user_id))
            count_query = count_query.where(AdValidationResult.user_id.in_(user_id))
        elif user_id:
            query = query.where(AdValidationResult.user_id == user_id)
            count_query = count_query.where(AdValidationResult.user_id == user_id)

        if query_dict:
            for field, value in query_dict.items():
                if hasattr(AdValidationResult, field):
                    query = query.where(getattr(AdValidationResult, field) == value)
                    count_query = count_query.where(getattr(AdValidationResult, field) == value)

        total = (await self.db.execute(count_query)).scalar()

        if sort:
            field_name = sort[1:] if sort.startswith("-") else sort
            if hasattr(AdValidationResult, field_name):
                field = getattr(AdValidationResult, field_name)
                query = query.order_by(field.desc() if sort.startswith("-") else field)
        else:
            query = query.order_by(AdValidationResult.id.desc())

        result = await self.db.execute(query.offset(skip).limit(limit))
        return {"items": result.scalars().all(), "total": total, "skip": skip, "limit": limit}

    async def update(
        self,
        obj_id: int,
        update_data: dict[str, Any],
        user_id: Optional[str | list[str]] = None,
    ) -> Optional[AdValidationResult]:
        obj = await self.get_by_id(obj_id, user_id=user_id)
        if not obj:
            return None
        for key, value in update_data.items():
            if hasattr(obj, key) and key != "user_id":
                setattr(obj, key, value)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj_id: int, user_id: Optional[str | list[str]] = None) -> bool:
        obj = await self.get_by_id(obj_id, user_id=user_id)
        if not obj:
            return False
        await self.db.delete(obj)
        await self.db.commit()
        return True
