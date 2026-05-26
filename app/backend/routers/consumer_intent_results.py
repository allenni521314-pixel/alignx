import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.consumer_intent_results import Consumer_intent_resultsService
from dependencies.auth import get_current_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/consumer_intent_results", tags=["consumer_intent_results"])


# ---------- Pydantic Schemas ----------
class Consumer_intent_resultsData(BaseModel):
    """Entity data schema (for create/update)"""
    keyword: str
    categories: str = None
    summary: str = None
    total_keywords: int = None
    high_freq_count: int = None
    created_at: Optional[datetime] = None


class Consumer_intent_resultsUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    keyword: Optional[str] = None
    categories: Optional[str] = None
    summary: Optional[str] = None
    total_keywords: Optional[int] = None
    high_freq_count: Optional[int] = None
    created_at: Optional[datetime] = None


class Consumer_intent_resultsResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    keyword: str
    categories: Optional[str] = None
    summary: Optional[str] = None
    total_keywords: Optional[int] = None
    high_freq_count: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Consumer_intent_resultsListResponse(BaseModel):
    """List response schema"""
    items: List[Consumer_intent_resultsResponse]
    total: int
    skip: int
    limit: int


class Consumer_intent_resultsBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[Consumer_intent_resultsData]


class Consumer_intent_resultsBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: Consumer_intent_resultsUpdateData


class Consumer_intent_resultsBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[Consumer_intent_resultsBatchUpdateItem]


class Consumer_intent_resultsBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=Consumer_intent_resultsListResponse)
async def query_consumer_intent_resultss(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query consumer_intent_resultss with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying consumer_intent_resultss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = Consumer_intent_resultsService(db)
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
        logger.debug(f"Found {result['total']} consumer_intent_resultss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying consumer_intent_resultss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=Consumer_intent_resultsListResponse)
async def query_consumer_intent_resultss_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Query consumer_intent_resultss with filtering, sorting, and pagination current user only
    logger.debug(f"Querying consumer_intent_resultss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = Consumer_intent_resultsService(db)
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
        logger.debug(f"Found {result['total']} consumer_intent_resultss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying consumer_intent_resultss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=Consumer_intent_resultsResponse)
async def get_consumer_intent_results(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single consumer_intent_results by ID (user can only see their own records)"""
    logger.debug(f"Fetching consumer_intent_results with id: {id}, fields={fields}")
    
    service = Consumer_intent_resultsService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Consumer_intent_results with id {id} not found")
            raise HTTPException(status_code=404, detail="Consumer_intent_results not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching consumer_intent_results {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=Consumer_intent_resultsResponse, status_code=201)
async def create_consumer_intent_results(
    data: Consumer_intent_resultsData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new consumer_intent_results"""
    logger.debug(f"Creating new consumer_intent_results with data: {data}")
    
    service = Consumer_intent_resultsService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create consumer_intent_results")
        
        logger.info(f"Consumer_intent_results created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating consumer_intent_results: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating consumer_intent_results: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[Consumer_intent_resultsResponse], status_code=201)
async def create_consumer_intent_resultss_batch(
    request: Consumer_intent_resultsBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple consumer_intent_resultss in a single request"""
    logger.debug(f"Batch creating {len(request.items)} consumer_intent_resultss")
    
    service = Consumer_intent_resultsService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} consumer_intent_resultss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[Consumer_intent_resultsResponse])
async def update_consumer_intent_resultss_batch(
    request: Consumer_intent_resultsBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple consumer_intent_resultss in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} consumer_intent_resultss")
    
    service = Consumer_intent_resultsService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} consumer_intent_resultss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=Consumer_intent_resultsResponse)
async def update_consumer_intent_results(
    id: int,
    data: Consumer_intent_resultsUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing consumer_intent_results (requires ownership)"""
    logger.debug(f"Updating consumer_intent_results {id} with data: {data}")

    service = Consumer_intent_resultsService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Consumer_intent_results with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Consumer_intent_results not found")
        
        logger.info(f"Consumer_intent_results {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating consumer_intent_results {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating consumer_intent_results {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_consumer_intent_resultss_batch(
    request: Consumer_intent_resultsBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple consumer_intent_resultss by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} consumer_intent_resultss")
    
    service = Consumer_intent_resultsService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} consumer_intent_resultss successfully")
        return {"message": f"Successfully deleted {deleted_count} consumer_intent_resultss", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_consumer_intent_results(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single consumer_intent_results by ID (requires ownership)"""
    logger.debug(f"Deleting consumer_intent_results with id: {id}")
    
    service = Consumer_intent_resultsService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"Consumer_intent_results with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Consumer_intent_results not found")
        
        logger.info(f"Consumer_intent_results {id} deleted successfully")
        return {"message": "Consumer_intent_results deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting consumer_intent_results {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")