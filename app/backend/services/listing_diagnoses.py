import logging
from typing import Optional, Dict, Any, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.listing_diagnoses import Listing_diagnoses

logger = logging.getLogger(__name__)


# ------------------ Service Layer ------------------
class Listing_diagnosesService:
    """Service layer for Listing_diagnoses operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: Dict[str, Any], user_id: Optional[str] = None) -> Optional[Listing_diagnoses]:
        """Create a new listing_diagnoses"""
        try:
            if user_id:
                data['user_id'] = user_id
            obj = Listing_diagnoses(**data)
            self.db.add(obj)
            await self.db.commit()
            await self.db.refresh(obj)
            logger.info(f"Created listing_diagnoses with id: {obj.id}")
            return obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating listing_diagnoses: {str(e)}")
            raise

    async def check_ownership(self, obj_id: int, user_id: str) -> bool:
        """Check if user owns this record"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            return obj is not None
        except Exception as e:
            logger.error(f"Error checking ownership for listing_diagnoses {obj_id}: {str(e)}")
            return False

    async def get_by_id(self, obj_id: int, user_id: Optional[str | list[str]] = None) -> Optional[Listing_diagnoses]:
        """Get listing_diagnoses by ID (user can only see their own records)"""
        try:
            query = select(Listing_diagnoses).where(Listing_diagnoses.id == obj_id)
            if isinstance(user_id, list):
                query = query.where(Listing_diagnoses.user_id.in_(user_id))
            elif user_id:
                query = query.where(Listing_diagnoses.user_id == user_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching listing_diagnoses {obj_id}: {str(e)}")
            raise

    async def get_list(
        self, 
        skip: int = 0, 
        limit: int = 20, 
        user_id: Optional[str | list[str]] = None,
        query_dict: Optional[Dict[str, Any]] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get paginated list of listing_diagnosess (user can only see their own records)"""
        try:
            query = select(Listing_diagnoses)
            count_query = select(func.count(Listing_diagnoses.id))
            
            if isinstance(user_id, list):
                query = query.where(Listing_diagnoses.user_id.in_(user_id))
                count_query = count_query.where(Listing_diagnoses.user_id.in_(user_id))
            elif user_id:
                query = query.where(Listing_diagnoses.user_id == user_id)
                count_query = count_query.where(Listing_diagnoses.user_id == user_id)
            
            if query_dict:
                for field, value in query_dict.items():
                    if hasattr(Listing_diagnoses, field):
                        query = query.where(getattr(Listing_diagnoses, field) == value)
                        count_query = count_query.where(getattr(Listing_diagnoses, field) == value)
            
            count_result = await self.db.execute(count_query)
            total = count_result.scalar()

            if sort:
                if sort.startswith('-'):
                    field_name = sort[1:]
                    if hasattr(Listing_diagnoses, field_name):
                        query = query.order_by(getattr(Listing_diagnoses, field_name).desc())
                else:
                    if hasattr(Listing_diagnoses, sort):
                        query = query.order_by(getattr(Listing_diagnoses, sort))
            else:
                query = query.order_by(Listing_diagnoses.id.desc())

            result = await self.db.execute(query.offset(skip).limit(limit))
            items = result.scalars().all()

            return {
                "items": items,
                "total": total,
                "skip": skip,
                "limit": limit,
            }
        except Exception as e:
            logger.error(f"Error fetching listing_diagnoses list: {str(e)}")
            raise

    async def update(self, obj_id: int, update_data: Dict[str, Any], user_id: Optional[str | list[str]] = None) -> Optional[Listing_diagnoses]:
        """Update listing_diagnoses (requires ownership)"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            if not obj:
                logger.warning(f"Listing_diagnoses {obj_id} not found for update")
                return None
            for key, value in update_data.items():
                if hasattr(obj, key) and key != 'user_id':
                    setattr(obj, key, value)

            await self.db.commit()
            await self.db.refresh(obj)
            logger.info(f"Updated listing_diagnoses {obj_id}")
            return obj
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating listing_diagnoses {obj_id}: {str(e)}")
            raise

    async def delete(self, obj_id: int, user_id: Optional[str | list[str]] = None) -> bool:
        """Delete listing_diagnoses (requires ownership)"""
        try:
            obj = await self.get_by_id(obj_id, user_id=user_id)
            if not obj:
                logger.warning(f"Listing_diagnoses {obj_id} not found for deletion")
                return False
            await self.db.delete(obj)
            await self.db.commit()
            logger.info(f"Deleted listing_diagnoses {obj_id}")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting listing_diagnoses {obj_id}: {str(e)}")
            raise

    async def get_by_field(self, field_name: str, field_value: Any) -> Optional[Listing_diagnoses]:
        """Get listing_diagnoses by any field"""
        try:
            if not hasattr(Listing_diagnoses, field_name):
                raise ValueError(f"Field {field_name} does not exist on Listing_diagnoses")
            result = await self.db.execute(
                select(Listing_diagnoses).where(getattr(Listing_diagnoses, field_name) == field_value)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching listing_diagnoses by {field_name}: {str(e)}")
            raise

    async def list_by_field(
        self, field_name: str, field_value: Any, skip: int = 0, limit: int = 20
    ) -> List[Listing_diagnoses]:
        """Get list of listing_diagnosess filtered by field"""
        try:
            if not hasattr(Listing_diagnoses, field_name):
                raise ValueError(f"Field {field_name} does not exist on Listing_diagnoses")
            result = await self.db.execute(
                select(Listing_diagnoses)
                .where(getattr(Listing_diagnoses, field_name) == field_value)
                .offset(skip)
                .limit(limit)
                .order_by(Listing_diagnoses.id.desc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching listing_diagnosess by {field_name}: {str(e)}")
            raise
