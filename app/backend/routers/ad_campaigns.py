import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.ad_campaigns import Ad_campaignsService
from dependencies.auth import get_current_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/ad_campaigns", tags=["ad_campaigns"])


# ---------- Pydantic Schemas ----------
class Ad_campaignsData(BaseModel):
    """Entity data schema (for create/update)"""
    campaign_name: str
    campaign_type: str = None
    daily_budget: float = None
    spend: float = None
    sales: float = None
    acos: float = None
    impressions: int = None
    clicks: int = None
    ctr: float = None
    status: str = None
    created_at: Optional[datetime] = None


class Ad_campaignsUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    campaign_name: Optional[str] = None
    campaign_type: Optional[str] = None
    daily_budget: Optional[float] = None
    spend: Optional[float] = None
    sales: Optional[float] = None
    acos: Optional[float] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    ctr: Optional[float] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None


class Ad_campaignsResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    campaign_name: str
    campaign_type: Optional[str] = None
    daily_budget: Optional[float] = None
    spend: Optional[float] = None
    sales: Optional[float] = None
    acos: Optional[float] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    ctr: Optional[float] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Ad_campaignsListResponse(BaseModel):
    """List response schema"""
    items: List[Ad_campaignsResponse]
    total: int
    skip: int
    limit: int


class Ad_campaignsBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[Ad_campaignsData]


class Ad_campaignsBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: Ad_campaignsUpdateData


class Ad_campaignsBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[Ad_campaignsBatchUpdateItem]


class Ad_campaignsBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=Ad_campaignsListResponse)
async def query_ad_campaignss(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query ad_campaignss with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying ad_campaignss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = Ad_campaignsService(db)
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
        logger.debug(f"Found {result['total']} ad_campaignss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying ad_campaignss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=Ad_campaignsListResponse)
async def query_ad_campaignss_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    db: AsyncSession = Depends(get_db),
):
    # Query ad_campaignss with filtering, sorting, and pagination without user limitation
    logger.debug(f"Querying ad_campaignss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = Ad_campaignsService(db)
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
            sort=sort
        )
        logger.debug(f"Found {result['total']} ad_campaignss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying ad_campaignss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=Ad_campaignsResponse)
async def get_ad_campaigns(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single ad_campaigns by ID (user can only see their own records)"""
    logger.debug(f"Fetching ad_campaigns with id: {id}, fields={fields}")
    
    service = Ad_campaignsService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Ad_campaigns with id {id} not found")
            raise HTTPException(status_code=404, detail="Ad_campaigns not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ad_campaigns {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=Ad_campaignsResponse, status_code=201)
async def create_ad_campaigns(
    data: Ad_campaignsData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new ad_campaigns"""
    logger.debug(f"Creating new ad_campaigns with data: {data}")
    
    service = Ad_campaignsService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create ad_campaigns")
        
        logger.info(f"Ad_campaigns created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating ad_campaigns: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating ad_campaigns: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[Ad_campaignsResponse], status_code=201)
async def create_ad_campaignss_batch(
    request: Ad_campaignsBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple ad_campaignss in a single request"""
    logger.debug(f"Batch creating {len(request.items)} ad_campaignss")
    
    service = Ad_campaignsService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} ad_campaignss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[Ad_campaignsResponse])
async def update_ad_campaignss_batch(
    request: Ad_campaignsBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple ad_campaignss in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} ad_campaignss")
    
    service = Ad_campaignsService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} ad_campaignss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=Ad_campaignsResponse)
async def update_ad_campaigns(
    id: int,
    data: Ad_campaignsUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing ad_campaigns (requires ownership)"""
    logger.debug(f"Updating ad_campaigns {id} with data: {data}")

    service = Ad_campaignsService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Ad_campaigns with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Ad_campaigns not found")
        
        logger.info(f"Ad_campaigns {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating ad_campaigns {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating ad_campaigns {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_ad_campaignss_batch(
    request: Ad_campaignsBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple ad_campaignss by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} ad_campaignss")
    
    service = Ad_campaignsService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} ad_campaignss successfully")
        return {"message": f"Successfully deleted {deleted_count} ad_campaignss", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_ad_campaigns(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single ad_campaigns by ID (requires ownership)"""
    logger.debug(f"Deleting ad_campaigns with id: {id}")
    
    service = Ad_campaignsService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"Ad_campaigns with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Ad_campaigns not found")
        
        logger.info(f"Ad_campaigns {id} deleted successfully")
        return {"message": "Ad_campaigns deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting ad_campaigns {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")