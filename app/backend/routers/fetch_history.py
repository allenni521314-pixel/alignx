import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.fetch_history import Fetch_historyService
from dependencies.auth import get_current_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/fetch_history", tags=["fetch_history"])


# ---------- Pydantic Schemas ----------
class Fetch_historyData(BaseModel):
    """Entity data schema (for create/update)"""
    asin: str
    marketplace: str
    status: str
    data_snapshot: str = None
    error_message: str = None
    created_at: Optional[datetime] = None


class Fetch_historyUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    asin: Optional[str] = None
    marketplace: Optional[str] = None
    status: Optional[str] = None
    data_snapshot: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


class Fetch_historyResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    asin: str
    marketplace: str
    status: str
    data_snapshot: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Fetch_historyListResponse(BaseModel):
    """List response schema"""
    items: List[Fetch_historyResponse]
    total: int
    skip: int
    limit: int


class Fetch_historyBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[Fetch_historyData]


class Fetch_historyBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: Fetch_historyUpdateData


class Fetch_historyBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[Fetch_historyBatchUpdateItem]


class Fetch_historyBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=Fetch_historyListResponse)
async def query_fetch_historys(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query fetch_historys with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying fetch_historys: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = Fetch_historyService(db)
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
        logger.debug(f"Found {result['total']} fetch_historys")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying fetch_historys: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=Fetch_historyListResponse)
async def query_fetch_historys_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    db: AsyncSession = Depends(get_db),
):
    # Query fetch_historys with filtering, sorting, and pagination without user limitation
    logger.debug(f"Querying fetch_historys: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = Fetch_historyService(db)
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
        logger.debug(f"Found {result['total']} fetch_historys")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying fetch_historys: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=Fetch_historyResponse)
async def get_fetch_history(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single fetch_history by ID (user can only see their own records)"""
    logger.debug(f"Fetching fetch_history with id: {id}, fields={fields}")
    
    service = Fetch_historyService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Fetch_history with id {id} not found")
            raise HTTPException(status_code=404, detail="Fetch_history not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching fetch_history {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=Fetch_historyResponse, status_code=201)
async def create_fetch_history(
    data: Fetch_historyData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new fetch_history"""
    logger.debug(f"Creating new fetch_history with data: {data}")
    
    service = Fetch_historyService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create fetch_history")
        
        logger.info(f"Fetch_history created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating fetch_history: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating fetch_history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[Fetch_historyResponse], status_code=201)
async def create_fetch_historys_batch(
    request: Fetch_historyBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple fetch_historys in a single request"""
    logger.debug(f"Batch creating {len(request.items)} fetch_historys")
    
    service = Fetch_historyService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} fetch_historys successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[Fetch_historyResponse])
async def update_fetch_historys_batch(
    request: Fetch_historyBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple fetch_historys in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} fetch_historys")
    
    service = Fetch_historyService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} fetch_historys successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=Fetch_historyResponse)
async def update_fetch_history(
    id: int,
    data: Fetch_historyUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing fetch_history (requires ownership)"""
    logger.debug(f"Updating fetch_history {id} with data: {data}")

    service = Fetch_historyService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Fetch_history with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Fetch_history not found")
        
        logger.info(f"Fetch_history {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating fetch_history {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating fetch_history {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_fetch_historys_batch(
    request: Fetch_historyBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple fetch_historys by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} fetch_historys")
    
    service = Fetch_historyService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} fetch_historys successfully")
        return {"message": f"Successfully deleted {deleted_count} fetch_historys", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_fetch_history(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single fetch_history by ID (requires ownership)"""
    logger.debug(f"Deleting fetch_history with id: {id}")
    
    service = Fetch_historyService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"Fetch_history with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Fetch_history not found")
        
        logger.info(f"Fetch_history {id} deleted successfully")
        return {"message": "Fetch_history deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting fetch_history {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")