import logging
from typing import Optional, Dict, Any, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.cosmo_results import Cosmo_results

logger = logging.getLogger(__name__)


# ------------------ Service Layer ------------------
class Cosmo_resultsService:
    """Service layer for Cosmo_results operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: Dict[str, Any], user_id: Optional[str] = None) -> Optional[Cosmo_results]:
        """Create a new cosmo_results"""
        try:
            if user_id:
                data['user_id'] = user_id
            obj = Cosmo_results(**data)
            self.db.add(obj)
            await self.db.commit()
            await self.db.refresh(obj)
            logger.info(f"Created cosmo_results with id: {obj.id}")
            return obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating cosmo_results: {str(e)}")
            raise

    async def check_ownership(self, obj_id: int, user_id: str) -> bool:
        """Check if user owns this record"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            return obj is not None
        except Exception as e:
            logger.error(f"Error checking ownership for cosmo_results {obj_id}: {str(e)}")
            return False

    async def get_by_id(self, obj_id: int, user_id: Optional[str] = None) -> Optional[Cosmo_results]:
        """Get cosmo_results by ID (user can only see their own records)"""
        try:
            query = select(Cosmo_results).where(Cosmo_results.id == obj_id)
            if user_id:
                query = query.where(Cosmo_results.user_id == user_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching cosmo_results {obj_id}: {str(e)}")
            raise

    async def get_list(
        self, 
        skip: int = 0, 
        limit: int = 20, 
        user_id: Optional[str] = None,
        query_dict: Optional[Dict[str, Any]] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get paginated list of cosmo_resultss (user can only see their own records)"""
        try:
            query = select(Cosmo_results)
            count_query = select(func.count(Cosmo_results.id))
            
            if user_id:
                query = query.where(Cosmo_results.user_id == user_id)
                count_query = count_query.where(Cosmo_results.user_id == user_id)
            
            if query_dict:
                for field, value in query_dict.items():
                    if hasattr(Cosmo_results, field):
                        query = query.where(getattr(Cosmo_results, field) == value)
                        count_query = count_query.where(getattr(Cosmo_results, field) == value)
            
            count_result = await self.db.execute(count_query)
            total = count_result.scalar()

            if sort:
                if sort.startswith('-'):
                    field_name = sort[1:]
                    if hasattr(Cosmo_results, field_name):
                        query = query.order_by(getattr(Cosmo_results, field_name).desc())
                else:
                    if hasattr(Cosmo_results, sort):
                        query = query.order_by(getattr(Cosmo_results, sort))
            else:
                query = query.order_by(Cosmo_results.id.desc())

            result = await self.db.execute(query.offset(skip).limit(limit))
            items = result.scalars().all()

            return {
                "items": items,
                "total": total,
                "skip": skip,
                "limit": limit,
            }
        except Exception as e:
            logger.error(f"Error fetching cosmo_results list: {str(e)}")
            raise

    async def update(self, obj_id: int, update_data: Dict[str, Any], user_id: Optional[str] = None) -> Optional[Cosmo_results]:
        """Update cosmo_results (requires ownership)"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            if not obj:
                logger.warning(f"Cosmo_results {obj_id} not found for update")
                return None
            for key, value in update_data.items():
                if hasattr(obj, key) and key != 'user_id':
                    setattr(obj, key, value)

            await self.db.commit()
            await self.db.refresh(obj)
            logger.info(f"Updated cosmo_results {obj_id}")
            return obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating cosmo_results {obj_id}: {str(e)}")
            raise

    async def delete(self, obj_id: int, user_id: Optional[str] = None) -> bool:
        """Delete cosmo_results (requires ownership)"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            if not obj:
                logger.warning(f"Cosmo_results {obj_id} not found for deletion")
                return False
            await self.db.delete(obj)
            await self.db.commit()
            logger.info(f"Deleted cosmo_results {obj_id}")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting cosmo_results {obj_id}: {str(e)}")
            raise

    async def get_by_field(self, field_name: str, field_value: Any) -> Optional[Cosmo_results]:
        """Get cosmo_results by any field"""
        try:
            if not hasattr(Cosmo_results, field_name):
                raise ValueError(f"Field {field_name} does not exist on Cosmo_results")
            result = await self.db.execute(
                select(Cosmo_results).where(getattr(Cosmo_results, field_name) == field_value)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching cosmo_results by {field_name}: {str(e)}")
            raise

    async def list_by_field(
        self, field_name: str, field_value: Any, skip: int = 0, limit: int = 20
    ) -> List[Cosmo_results]:
        """Get list of cosmo_resultss filtered by field"""
        try:
            if not hasattr(Cosmo_results, field_name):
                raise ValueError(f"Field {field_name} does not exist on Cosmo_results")
            result = await self.db.execute(
                select(Cosmo_results)
                .where(getattr(Cosmo_results, field_name) == field_value)
                .offset(skip)
                .limit(limit)
                .order_by(Cosmo_results.id.desc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching cosmo_resultss by {field_name}: {str(e)}")
            raise