import logging
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.action_snapshots import ActionSnapshot

logger = logging.getLogger(__name__)


class ActionSnapshotsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: Dict[str, Any], user_id: Optional[str] = None) -> ActionSnapshot:
        if user_id:
            data["user_id"] = user_id
        obj = ActionSnapshot(**data)
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def list(
        self,
        user_id: Optional[str | list[str]] = None,
        module_key: str = "",
        action_key: str = "",
        product_id: Optional[int] = None,
        asin: str = "",
        skip: int = 0,
        limit: int = 50,
    ):
        query = select(ActionSnapshot)
        count_query = select(func.count()).select_from(ActionSnapshot)

        if user_id:
            if isinstance(user_id, list):
                query = query.where(ActionSnapshot.user_id.in_(user_id))
                count_query = count_query.where(ActionSnapshot.user_id.in_(user_id))
            else:
                query = query.where(ActionSnapshot.user_id == user_id)
                count_query = count_query.where(ActionSnapshot.user_id == user_id)
        if module_key:
            query = query.where(ActionSnapshot.module_key == module_key)
            count_query = count_query.where(ActionSnapshot.module_key == module_key)
        if action_key:
            query = query.where(ActionSnapshot.action_key == action_key)
            count_query = count_query.where(ActionSnapshot.action_key == action_key)
        if product_id is not None:
            query = query.where(ActionSnapshot.product_id == product_id)
            count_query = count_query.where(ActionSnapshot.product_id == product_id)
        if asin:
            query = query.where(ActionSnapshot.asin == asin)
            count_query = count_query.where(ActionSnapshot.asin == asin)

        total_res = await self.db.execute(count_query)
        total = total_res.scalar() or 0
        rows = await self.db.execute(query.order_by(desc(ActionSnapshot.id)).offset(skip).limit(limit))
        return list(rows.scalars().all()), total

    async def get(self, snapshot_id: int, user_id: Optional[str | Sequence[str]] = None) -> Optional[ActionSnapshot]:
        query = select(ActionSnapshot).where(ActionSnapshot.id == snapshot_id)
        if isinstance(user_id, list):
            query = query.where(ActionSnapshot.user_id.in_(user_id))
        elif user_id:
            query = query.where(ActionSnapshot.user_id == user_id)
        res = await self.db.execute(query)
        return res.scalar_one_or_none()
