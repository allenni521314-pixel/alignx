import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.cosmo_results import Cosmo_resultsService
from dependencies.auth import get_current_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/cosmo_results", tags=["cosmo_results"])


# ---------- Pydantic Schemas ----------
class Cosmo_resultsData(BaseModel):
    """Entity data schema (for create/update)"""
    product_id: int
    model_name: str
    optimized_title: str = None
    optimized_bullets: str = None
    optimized_keywords: str = None
    analysis_reason: str = None
    created_at: Optional[datetime] = None


class Cosmo_resultsUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    product_id: Optional[int] = None
    model_name: Optional[str] = None
    optimized_title: Optional[str] = None
    optimized_bullets: Optional[str] = None
    optimized_keywords: Optional[str] = None
    analysis_reason: Optional[str] = None
    created_at: Optional[datetime] = None


class Cosmo_resultsResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    product_id: int
    model_name: str
    optimized_title: Optional[str] = None
    optimized_bullets: Optional[str] = None
    optimized_keywords: Optional[str] = None
    analysis_reason: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Cosmo_resultsListResponse(BaseModel):
    """List response schema"""
    items: List[Cosmo_resultsResponse]
    total: int
    skip: int
    limit: int


class Cosmo_resultsBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[Cosmo_resultsData]


class Cosmo_resultsBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: Cosmo_resultsUpdateData


class Cosmo_resultsBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[Cosmo_resultsBatchUpdateItem]


class Cosmo_resultsBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=Cosmo_resultsListResponse)
async def query_cosmo_resultss(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query cosmo_resultss with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying cosmo_resultss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = Cosmo_resultsService(db)
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
        logger.debug(f"Found {result['total']} cosmo_resultss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying cosmo_resultss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=Cosmo_resultsListResponse)
async def query_cosmo_resultss_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    db: AsyncSession = Depends(get_db),
):
    # Query cosmo_resultss with filtering, sorting, and pagination without user limitation
    logger.debug(f"Querying cosmo_resultss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = Cosmo_resultsService(db)
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
        logger.debug(f"Found {result['total']} cosmo_resultss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying cosmo_resultss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=Cosmo_resultsResponse)
async def get_cosmo_results(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single cosmo_results by ID (user can only see their own records)"""
    logger.debug(f"Fetching cosmo_results with id: {id}, fields={fields}")
    
    service = Cosmo_resultsService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Cosmo_results with id {id} not found")
            raise HTTPException(status_code=404, detail="Cosmo_results not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching cosmo_results {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=Cosmo_resultsResponse, status_code=201)
async def create_cosmo_results(
    data: Cosmo_resultsData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new cosmo_results"""
    logger.debug(f"Creating new cosmo_results with data: {data}")
    
    service = Cosmo_resultsService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create cosmo_results")
        
        logger.info(f"Cosmo_results created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating cosmo_results: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating cosmo_results: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[Cosmo_resultsResponse], status_code=201)
async def create_cosmo_resultss_batch(
    request: Cosmo_resultsBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple cosmo_resultss in a single request"""
    logger.debug(f"Batch creating {len(request.items)} cosmo_resultss")
    
    service = Cosmo_resultsService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} cosmo_resultss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[Cosmo_resultsResponse])
async def update_cosmo_resultss_batch(
    request: Cosmo_resultsBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple cosmo_resultss in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} cosmo_resultss")
    
    service = Cosmo_resultsService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} cosmo_resultss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=Cosmo_resultsResponse)
async def update_cosmo_results(
    id: int,
    data: Cosmo_resultsUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing cosmo_results (requires ownership)"""
    logger.debug(f"Updating cosmo_results {id} with data: {data}")

    service = Cosmo_resultsService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Cosmo_results with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Cosmo_results not found")
        
        logger.info(f"Cosmo_results {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating cosmo_results {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating cosmo_results {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_cosmo_resultss_batch(
    request: Cosmo_resultsBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple cosmo_resultss by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} cosmo_resultss")
    
    service = Cosmo_resultsService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} cosmo_resultss successfully")
        return {"message": f"Successfully deleted {deleted_count} cosmo_resultss", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_cosmo_results(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single cosmo_results by ID (requires ownership)"""
    logger.debug(f"Deleting cosmo_results with id: {id}")
    
    service = Cosmo_resultsService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"Cosmo_results with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Cosmo_results not found")
        
        logger.info(f"Cosmo_results {id} deleted successfully")
        return {"message": "Cosmo_results deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting cosmo_results {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")