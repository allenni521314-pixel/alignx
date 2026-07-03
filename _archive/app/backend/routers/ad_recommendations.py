import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.ad_recommendations import Ad_recommendationsService
from dependencies.auth import get_current_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/ad_recommendations", tags=["ad_recommendations"])


# ---------- Pydantic Schemas ----------
class Ad_recommendationsData(BaseModel):
    """Entity data schema (for create/update)"""
    product_id: int
    recommendation_type: str
    content: str = None
    created_at: Optional[datetime] = None


class Ad_recommendationsUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    product_id: Optional[int] = None
    recommendation_type: Optional[str] = None
    content: Optional[str] = None
    created_at: Optional[datetime] = None


class Ad_recommendationsResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    product_id: int
    recommendation_type: str
    content: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Ad_recommendationsListResponse(BaseModel):
    """List response schema"""
    items: List[Ad_recommendationsResponse]
    total: int
    skip: int
    limit: int


class Ad_recommendationsBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[Ad_recommendationsData]


class Ad_recommendationsBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: Ad_recommendationsUpdateData


class Ad_recommendationsBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[Ad_recommendationsBatchUpdateItem]


class Ad_recommendationsBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=Ad_recommendationsListResponse)
async def query_ad_recommendationss(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query ad_recommendationss with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying ad_recommendationss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = Ad_recommendationsService(db)
    try:
        # Parse query JSON if provided
        query_dict = None
        if query:
            try:
                query_dict = json.loads(query)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid query JSON format")
        
        result = await service.get_list(
            skip=skip, 
            limit=limit,
            query_dict=query_dict,
            sort=sort,
            user_id=str(current_user.id),
        )
        logger.debug(f"Found {result['total']} ad_recommendationss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying ad_recommendationss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=Ad_recommendationsListResponse)
async def query_ad_recommendationss_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Query ad_recommendationss with filtering, sorting, and pagination current user only
    logger.debug(f"Querying ad_recommendationss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = Ad_recommendationsService(db)
    try:
        # Parse query JSON if provided
        query_dict = None
        if query:
            try:
                query_dict = json.loads(query)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid query JSON format")

        result = await service.get_list(
            skip=skip,
            limit=limit,
            query_dict=query_dict,
            sort=sort,
            user_id=str(current_user.id)
        )
        logger.debug(f"Found {result['total']} ad_recommendationss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying ad_recommendationss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=Ad_recommendationsResponse)
async def get_ad_recommendations(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single ad_recommendations by ID (user can only see their own records)"""
    logger.debug(f"Fetching ad_recommendations with id: {id}, fields={fields}")
    
    service = Ad_recommendationsService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Ad_recommendations with id {id} not found")
            raise HTTPException(status_code=404, detail="Ad_recommendations not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ad_recommendations {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=Ad_recommendationsResponse, status_code=201)
async def create_ad_recommendations(
    data: Ad_recommendationsData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new ad_recommendations"""
    logger.debug(f"Creating new ad_recommendations with data: {data}")
    
    service = Ad_recommendationsService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create ad_recommendations")
        
        logger.info(f"Ad_recommendations created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating ad_recommendations: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating ad_recommendations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[Ad_recommendationsResponse], status_code=201)
async def create_ad_recommendationss_batch(
    request: Ad_recommendationsBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple ad_recommendationss in a single request"""
    logger.debug(f"Batch creating {len(request.items)} ad_recommendationss")
    
    service = Ad_recommendationsService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} ad_recommendationss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[Ad_recommendationsResponse])
async def update_ad_recommendationss_batch(
    request: Ad_recommendationsBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple ad_recommendationss in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} ad_recommendationss")
    
    service = Ad_recommendationsService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} ad_recommendationss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=Ad_recommendationsResponse)
async def update_ad_recommendations(
    id: int,
    data: Ad_recommendationsUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing ad_recommendations (requires ownership)"""
    logger.debug(f"Updating ad_recommendations {id} with data: {data}")

    service = Ad_recommendationsService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Ad_recommendations with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Ad_recommendations not found")
        
        logger.info(f"Ad_recommendations {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating ad_recommendations {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating ad_recommendations {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_ad_recommendationss_batch(
    request: Ad_recommendationsBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple ad_recommendationss by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} ad_recommendationss")
    
    service = Ad_recommendationsService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} ad_recommendationss successfully")
        return {"message": f"Successfully deleted {deleted_count} ad_recommendationss", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_ad_recommendations(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single ad_recommendations by ID (requires ownership)"""
    logger.debug(f"Deleting ad_recommendations with id: {id}")
    
    service = Ad_recommendationsService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"Ad_recommendations with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Ad_recommendations not found")
        
        logger.info(f"Ad_recommendations {id} deleted successfully")
        return {"message": "Ad_recommendations deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting ad_recommendations {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")