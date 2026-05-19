import logging
from typing import Optional, Dict, Any, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.competitor_insights import Competitor_insights

logger = logging.getLogger(__name__)


# ------------------ Service Layer ------------------
class Competitor_insightsService:
    """Service layer for Competitor_insights operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: Dict[str, Any], user_id: Optional[str] = None) -> Optional[Competitor_insights]:
        """Create a new competitor_insights"""
        try:
            if user_id:
                data['user_id'] = user_id
            obj = Competitor_insights(**data)
            self.db.add(obj)
            await self.db.commit()
            await self.db.refresh(obj)
            logger.info(f"Created competitor_insights with id: {obj.id}")
            return obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating competitor_insights: {str(e)}")
            raise

    async def check_ownership(self, obj_id: int, user_id: str) -> bool:
        """Check if user owns this record"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            return obj is not None
        except Exception as e:
            logger.error(f"Error checking ownership for competitor_insights {obj_id}: {str(e)}")
            return False

    async def get_by_id(self, obj_id: int, user_id: Optional[str] = None) -> Optional[Competitor_insights]:
        """Get competitor_insights by ID (user can only see their own records)"""
        try:
            query = select(Competitor_insights).where(Competitor_insights.id == obj_id)
            if user_id:
                query = query.where(Competitor_insights.user_id == user_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching competitor_insights {obj_id}: {str(e)}")
            raise

    async def get_list(
        self, 
        skip: int = 0, 
        limit: int = 20, 
        user_id: Optional[str] = None,
        query_dict: Optional[Dict[str, Any]] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get paginated list of competitor_insightss (user can only see their own records)"""
        try:
            query = select(Competitor_insights)
            count_query = select(func.count(Competitor_insights.id))
            
            if user_id:
                query = query.where(Competitor_insights.user_id == user_id)
                count_query = count_query.where(Competitor_insights.user_id == user_id)
            
            if query_dict:
                for field, value in query_dict.items():
                    if hasattr(Competitor_insights, field):
                        query = query.where(getattr(Competitor_insights, field) == value)
                        count_query = count_query.where(getattr(Competitor_insights, field) == value)
            
            count_result = await self.db.execute(count_query)
            total = count_result.scalar()

            if sort:
                if sort.startswith('-'):
                    field_name = sort[1:]
                    if hasattr(Competitor_insights, field_name):
                        query = query.order_by(getattr(Competitor_insights, field_name).desc())
                else:
                    if hasattr(Competitor_insights, sort):
                        query = query.order_by(getattr(Competitor_insights, sort))
            else:
                query = query.order_by(Competitor_insights.id.desc())

            result = await self.db.execute(query.offset(skip).limit(limit))
            items = result.scalars().all()

            return {
                "items": items,
                "total": total,
                "skip": skip,
                "limit": limit,
            }
        except Exception as e:
            logger.error(f"Error fetching competitor_insights list: {str(e)}")
            raise

    async def update(self, obj_id: int, update_data: Dict[str, Any], user_id: Optional[str] = None) -> Optional[Competitor_insights]:
        """Update competitor_insights (requires ownership)"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            if not obj:
                logger.warning(f"Competitor_insights {obj_id} not found for update")
                return None
            for key, value in update_data.items():
                if hasattr(obj, key) and key != 'user_id':
                    setattr(obj, key, value)

            await self.db.commit()
            await self.db.refresh(obj)
            logger.info(f"Updated competitor_insights {obj_id}")
            return obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating competitor_insights {obj_id}: {str(e)}")
            raise

    async def delete(self, obj_id: int, user_id: Optional[str] = None) -> bool:
        """Delete competitor_insights (requires ownership)"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            if not obj:
                logger.warning(f"Competitor_insights {obj_id} not found for deletion")
                return False
            await self.db.delete(obj)
            await self.db.commit()
            logger.info(f"Deleted competitor_insights {obj_id}")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting competitor_insights {obj_id}: {str(e)}")
            raise

    async def get_by_field(self, field_name: str, field_value: Any) -> Optional[Competitor_insights]:
        """Get competitor_insights by any field"""
        try:
            if not hasattr(Competitor_insights, field_name):
                raise ValueError(f"Field {field_name} does not exist on Competitor_insights")
            result = await self.db.execute(
                select(Competitor_insights).where(getattr(Competitor_insights, field_name) == field_value)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching competitor_insights by {field_name}: {str(e)}")
            raise

    async def list_by_field(
        self, field_name: str, field_value: Any, skip: int = 0, limit: int = 20
    ) -> List[Competitor_insights]:
        """Get list of competitor_insightss filtered by field"""
        try:
            if not hasattr(Competitor_insights, field_name):
                raise ValueError(f"Field {field_name} does not exist on Competitor_insights")
            result = await self.db.execute(
                select(Competitor_insights)
                .where(getattr(Competitor_insights, field_name) == field_value)
                .offset(skip)
                .limit(limit)
                .order_by(Competitor_insights.id.desc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching competitor_insightss by {field_name}: {str(e)}")
            raise