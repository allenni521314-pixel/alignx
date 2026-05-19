import logging
from typing import Optional, Dict, Any, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.asin_analyses import Asin_analyses

logger = logging.getLogger(__name__)


# ------------------ Service Layer ------------------
class Asin_analysesService:
    """Service layer for Asin_analyses operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: Dict[str, Any], user_id: Optional[str] = None) -> Optional[Asin_analyses]:
        """Create a new asin_analyses"""
        try:
            if user_id:
                data['user_id'] = user_id
            obj = Asin_analyses(**data)
            self.db.add(obj)
            await self.db.commit()
            await self.db.refresh(obj)
            logger.info(f"Created asin_analyses with id: {obj.id}")
            return obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating asin_analyses: {str(e)}")
            raise

    async def check_ownership(self, obj_id: int, user_id: str) -> bool:
        """Check if user owns this record"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            return obj is not None
        except Exception as e:
            logger.error(f"Error checking ownership for asin_analyses {obj_id}: {str(e)}")
            return False

    async def get_by_id(self, obj_id: int, user_id: Optional[str] = None) -> Optional[Asin_analyses]:
        """Get asin_analyses by ID (user can only see their own records)"""
        try:
            query = select(Asin_analyses).where(Asin_analyses.id == obj_id)
            if user_id:
                query = query.where(Asin_analyses.user_id == user_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching asin_analyses {obj_id}: {str(e)}")
            raise

    async def get_list(
        self, 
        skip: int = 0, 
        limit: int = 20, 
        user_id: Optional[str] = None,
        query_dict: Optional[Dict[str, Any]] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get paginated list of asin_analysess (user can only see their own records)"""
        try:
            query = select(Asin_analyses)
            count_query = select(func.count(Asin_analyses.id))
            
            if user_id:
                query = query.where(Asin_analyses.user_id == user_id)
                count_query = count_query.where(Asin_analyses.user_id == user_id)
            
            if query_dict:
                for field, value in query_dict.items():
                    if hasattr(Asin_analyses, field):
                        query = query.where(getattr(Asin_analyses, field) == value)
                        count_query = count_query.where(getattr(Asin_analyses, field) == value)
            
            count_result = await self.db.execute(count_query)
            total = count_result.scalar()

            if sort:
                if sort.startswith('-'):
                    field_name = sort[1:]
                    if hasattr(Asin_analyses, field_name):
                        query = query.order_by(getattr(Asin_analyses, field_name).desc())
                else:
                    if hasattr(Asin_analyses, sort):
                        query = query.order_by(getattr(Asin_analyses, sort))
            else:
                query = query.order_by(Asin_analyses.id.desc())

            result = await self.db.execute(query.offset(skip).limit(limit))
            items = result.scalars().all()

            return {
                "items": items,
                "total": total,
                "skip": skip,
                "limit": limit,
            }
        except Exception as e:
            logger.error(f"Error fetching asin_analyses list: {str(e)}")
            raise

    async def update(self, obj_id: int, update_data: Dict[str, Any], user_id: Optional[str] = None) -> Optional[Asin_analyses]:
        """Update asin_analyses (requires ownership)"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            if not obj:
                logger.warning(f"Asin_analyses {obj_id} not found for update")
                return None
            for key, value in update_data.items():
                if hasattr(obj, key) and key != 'user_id':
                    setattr(obj, key, value)

            await self.db.commit()
            await self.db.refresh(obj)
            logger.info(f"Updated asin_analyses {obj_id}")
            return obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating asin_analyses {obj_id}: {str(e)}")
            raise

    async def delete(self, obj_id: int, user_id: Optional[str] = None) -> bool:
        """Delete asin_analyses (requires ownership)"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            if not obj:
                logger.warning(f"Asin_analyses {obj_id} not found for deletion")
                return False
            await self.db.delete(obj)
            await self.db.commit()
            logger.info(f"Deleted asin_analyses {obj_id}")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting asin_analyses {obj_id}: {str(e)}")
            raise

    async def get_by_field(self, field_name: str, field_value: Any) -> Optional[Asin_analyses]:
        """Get asin_analyses by any field"""
        try:
            if not hasattr(Asin_analyses, field_name):
                raise ValueError(f"Field {field_name} does not exist on Asin_analyses")
            result = await self.db.execute(
                select(Asin_analyses).where(getattr(Asin_analyses, field_name) == field_value)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching asin_analyses by {field_name}: {str(e)}")
            raise

    async def list_by_field(
        self, field_name: str, field_value: Any, skip: int = 0, limit: int = 20
    ) -> List[Asin_analyses]:
        """Get list of asin_analysess filtered by field"""
        try:
            if not hasattr(Asin_analyses, field_name):
                raise ValueError(f"Field {field_name} does not exist on Asin_analyses")
            result = await self.db.execute(
                select(Asin_analyses)
                .where(getattr(Asin_analyses, field_name) == field_value)
                .offset(skip)
                .limit(limit)
                .order_by(Asin_analyses.id.desc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching asin_analysess by {field_name}: {str(e)}")
            raise