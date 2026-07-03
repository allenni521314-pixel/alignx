import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.competitor_insights import Competitor_insightsService
from dependencies.auth import get_current_user, get_user_scope_ids
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/competitor_insights", tags=["competitor_insights"])


# ---------- Pydantic Schemas ----------
class Competitor_insightsData(BaseModel):
    """Entity data schema (for create/update)"""
    product_id: int
    competitor_asin: str
    strengths: str = None
    weaknesses: str = None
    gaps: str = None
    suggestions: str = None
    radar_scores: str = None
    created_at: Optional[datetime] = None


class Competitor_insightsUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    product_id: Optional[int] = None
    competitor_asin: Optional[str] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    gaps: Optional[str] = None
    suggestions: Optional[str] = None
    radar_scores: Optional[str] = None
    created_at: Optional[datetime] = None


class Competitor_insightsResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    product_id: int
    competitor_asin: str
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    gaps: Optional[str] = None
    suggestions: Optional[str] = None
    radar_scores: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Competitor_insightsListResponse(BaseModel):
    """List response schema"""
    items: List[Competitor_insightsResponse]
    total: int
    skip: int
    limit: int


class Competitor_insightsBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[Competitor_insightsData]


class Competitor_insightsBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: Competitor_insightsUpdateData


class Competitor_insightsBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[Competitor_insightsBatchUpdateItem]


class Competitor_insightsBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=Competitor_insightsListResponse)
async def query_competitor_insightss(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query competitor_insightss with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying competitor_insightss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = Competitor_insightsService(db)
    try:
        # Parse query JSON if provided
        query_dict = None
        if query:
            try:
                query_dict = json.loads(query)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid query JSON format")
        
        scope_user_ids = await get_user_scope_ids(current_user, db)
        result = await service.get_list(
            skip=skip, 
            limit=limit,
            query_dict=query_dict,
            sort=sort,
            user_id=scope_user_ids,
        )
        logger.debug(f"Found {result['total']} competitor_insightss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying competitor_insightss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=Competitor_insightsListResponse)
async def query_competitor_insightss_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Query competitor_insightss with filtering, sorting, and pagination current user only
    logger.debug(f"Querying competitor_insightss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = Competitor_insightsService(db)
    try:
        # Parse query JSON if provided
        query_dict = None
        if query:
            try:
                query_dict = json.loads(query)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid query JSON format")

        scope_user_ids = await get_user_scope_ids(current_user, db)
        result = await service.get_list(
            skip=skip,
            limit=limit,
            query_dict=query_dict,
            sort=sort,
            user_id=scope_user_ids
        )
        logger.debug(f"Found {result['total']} competitor_insightss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying competitor_insightss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=Competitor_insightsResponse)
async def get_competitor_insights(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single competitor_insights by ID (user can only see their own records)"""
    logger.debug(f"Fetching competitor_insights with id: {id}, fields={fields}")
    
    service = Competitor_insightsService(db)
    try:
        scope_user_ids = await get_user_scope_ids(current_user, db)
        result = await service.get_by_id(id, user_id=scope_user_ids)
        if not result:
            logger.warning(f"Competitor_insights with id {id} not found")
            raise HTTPException(status_code=404, detail="Competitor_insights not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching competitor_insights {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=Competitor_insightsResponse, status_code=201)
async def create_competitor_insights(
    data: Competitor_insightsData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new competitor_insights"""
    logger.debug(f"Creating new competitor_insights with data: {data}")
    
    service = Competitor_insightsService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create competitor_insights")
        
        logger.info(f"Competitor_insights created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating competitor_insights: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating competitor_insights: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[Competitor_insightsResponse], status_code=201)
async def create_competitor_insightss_batch(
    request: Competitor_insightsBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple competitor_insightss in a single request"""
    logger.debug(f"Batch creating {len(request.items)} competitor_insightss")
    
    service = Competitor_insightsService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} competitor_insightss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[Competitor_insightsResponse])
async def update_competitor_insightss_batch(
    request: Competitor_insightsBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple competitor_insightss in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} competitor_insightss")
    
    service = Competitor_insightsService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            scope_user_ids = await get_user_scope_ids(current_user, db)
            result = await service.update(item.id, update_dict, user_id=scope_user_ids)
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} competitor_insightss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=Competitor_insightsResponse)
async def update_competitor_insights(
    id: int,
    data: Competitor_insightsUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing competitor_insights (requires ownership)"""
    logger.debug(f"Updating competitor_insights {id} with data: {data}")

    service = Competitor_insightsService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        scope_user_ids = await get_user_scope_ids(current_user, db)
        result = await service.update(id, update_dict, user_id=scope_user_ids)
        if not result:
            logger.warning(f"Competitor_insights with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Competitor_insights not found")
        
        logger.info(f"Competitor_insights {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating competitor_insights {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating competitor_insights {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_competitor_insightss_batch(
    request: Competitor_insightsBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple competitor_insightss by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} competitor_insightss")
    
    service = Competitor_insightsService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            scope_user_ids = await get_user_scope_ids(current_user, db)
            success = await service.delete(item_id, user_id=scope_user_ids)
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} competitor_insightss successfully")
        return {"message": f"Successfully deleted {deleted_count} competitor_insightss", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_competitor_insights(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single competitor_insights by ID (requires ownership)"""
    logger.debug(f"Deleting competitor_insights with id: {id}")
    
    service = Competitor_insightsService(db)
    try:
        scope_user_ids = await get_user_scope_ids(current_user, db)
        success = await service.delete(id, user_id=scope_user_ids)
        if not success:
            logger.warning(f"Competitor_insights with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Competitor_insights not found")
        
        logger.info(f"Competitor_insights {id} deleted successfully")
        return {"message": "Competitor_insights deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting competitor_insights {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
