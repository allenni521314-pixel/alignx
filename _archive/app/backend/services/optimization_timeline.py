import logging
from typing import Optional, Dict, Any, List

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.optimization_timeline import OptimizationTimeline

logger = logging.getLogger(__name__)


class Optimization_timelineService:
    """Service layer for OptimizationTimeline operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: Dict[str, Any], user_id: Optional[str] = None) -> Optional[OptimizationTimeline]:
        try:
            if user_id:
                data['user_id'] = user_id
            obj = OptimizationTimeline(**data)
            self.db.add(obj)
            await self.db.commit()
            await self.db.refresh(obj)
            logger.info(f"Created optimization_timeline with id: {obj.id}")
            return obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating optimization_timeline: {str(e)}")
            raise

    async def get_by_id(self, obj_id: int, user_id: Optional[str | list[str]] = None) -> Optional[OptimizationTimeline]:
        try:
            query = select(OptimizationTimeline).where(OptimizationTimeline.id == obj_id)
            if isinstance(user_id, list):
                query = query.where(OptimizationTimeline.user_id.in_(user_id))
            elif user_id:
                query = query.where(OptimizationTimeline.user_id == user_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching optimization_timeline {obj_id}: {str(e)}")
            raise

    async def get_list(
        self,
        skip: int = 0,
        limit: int = 200,
        user_id: Optional[str | list[str]] = None,
        sort: Optional[str] = None,
        query_filter: Optional[Dict[str, Any]] = None,
    ) -> tuple[List[OptimizationTimeline], int]:
        try:
            query = select(OptimizationTimeline)
            count_query = select(func.count()).select_from(OptimizationTimeline)

            if isinstance(user_id, list):
                query = query.where(OptimizationTimeline.user_id.in_(user_id))
                count_query = count_query.where(OptimizationTimeline.user_id.in_(user_id))
            elif user_id:
                query = query.where(OptimizationTimeline.user_id == user_id)
                count_query = count_query.where(OptimizationTimeline.user_id == user_id)

            if query_filter:
                for key, value in query_filter.items():
                    if hasattr(OptimizationTimeline, key):
                        query = query.where(getattr(OptimizationTimeline, key) == value)
                        count_query = count_query.where(getattr(OptimizationTimeline, key) == value)

            if sort:
                if sort.startswith("-"):
                    col_name = sort[1:]
                    if hasattr(OptimizationTimeline, col_name):
                        query = query.order_by(desc(getattr(OptimizationTimeline, col_name)))
                else:
                    if hasattr(OptimizationTimeline, sort):
                        query = query.order_by(getattr(OptimizationTimeline, sort))
            else:
                query = query.order_by(desc(OptimizationTimeline.id))

            count_result = await self.db.execute(count_query)
            total = count_result.scalar() or 0

            query = query.offset(skip).limit(limit)
            result = await self.db.execute(query)
            items = list(result.scalars().all())

            return items, total
        except Exception as e:
            logger.error(f"Error listing optimization_timeline: {str(e)}")
            raise

    async def delete(self, obj_id: int, user_id: Optional[str | list[str]] = None) -> bool:
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            if not obj:
                return False
            await self.db.delete(obj)
            await self.db.commit()
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting optimization_timeline {obj_id}: {str(e)}")
            raise
