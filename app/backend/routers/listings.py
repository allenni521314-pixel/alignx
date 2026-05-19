import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.listings import ListingsService
from dependencies.auth import get_current_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/listings", tags=["listings"])


# ---------- Pydantic Schemas ----------
class ListingsData(BaseModel):
    """Entity data schema (for create/update)"""
    asin: str
    title: str
    cosmo_score: float = None
    current_rank: int = None
    sessions_30d: int = None
    conversion_rate: float = None
    status: str = None
    created_at: Optional[datetime] = None


class ListingsUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    asin: Optional[str] = None
    title: Optional[str] = None
    cosmo_score: Optional[float] = None
    current_rank: Optional[int] = None
    sessions_30d: Optional[int] = None
    conversion_rate: Optional[float] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None


class ListingsResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    asin: str
    title: str
    cosmo_score: Optional[float] = None
    current_rank: Optional[int] = None
    sessions_30d: Optional[int] = None
    conversion_rate: Optional[float] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ListingsListResponse(BaseModel):
    """List response schema"""
    items: List[ListingsResponse]
    total: int
    skip: int
    limit: int


class ListingsBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[ListingsData]


class ListingsBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: ListingsUpdateData


class ListingsBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[ListingsBatchUpdateItem]


class ListingsBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=ListingsListResponse)
async def query_listingss(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query listingss with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying listingss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = ListingsService(db)
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
        logger.debug(f"Found {result['total']} listingss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying listingss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=ListingsListResponse)
async def query_listingss_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    db: AsyncSession = Depends(get_db),
):
    # Query listingss with filtering, sorting, and pagination without user limitation
    logger.debug(f"Querying listingss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = ListingsService(db)
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
        logger.debug(f"Found {result['total']} listingss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying listingss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=ListingsResponse)
async def get_listings(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single listings by ID (user can only see their own records)"""
    logger.debug(f"Fetching listings with id: {id}, fields={fields}")
    
    service = ListingsService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Listings with id {id} not found")
            raise HTTPException(status_code=404, detail="Listings not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching listings {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=ListingsResponse, status_code=201)
async def create_listings(
    data: ListingsData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new listings"""
    logger.debug(f"Creating new listings with data: {data}")
    
    service = ListingsService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create listings")
        
        logger.info(f"Listings created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating listings: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating listings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[ListingsResponse], status_code=201)
async def create_listingss_batch(
    request: ListingsBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple listingss in a single request"""
    logger.debug(f"Batch creating {len(request.items)} listingss")
    
    service = ListingsService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} listingss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[ListingsResponse])
async def update_listingss_batch(
    request: ListingsBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple listingss in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} listingss")
    
    service = ListingsService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} listingss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=ListingsResponse)
async def update_listings(
    id: int,
    data: ListingsUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing listings (requires ownership)"""
    logger.debug(f"Updating listings {id} with data: {data}")

    service = ListingsService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Listings with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Listings not found")
        
        logger.info(f"Listings {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating listings {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating listings {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_listingss_batch(
    request: ListingsBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple listingss by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} listingss")
    
    service = ListingsService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} listingss successfully")
        return {"message": f"Successfully deleted {deleted_count} listingss", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_listings(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single listings by ID (requires ownership)"""
    logger.debug(f"Deleting listings with id: {id}")
    
    service = ListingsService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"Listings with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Listings not found")
        
        logger.info(f"Listings {id} deleted successfully")
        return {"message": "Listings deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting listings {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")