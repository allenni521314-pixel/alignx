import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.asin_analyses import Asin_analysesService
from dependencies.auth import get_current_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/asin_analyses", tags=["asin_analyses"])


# ---------- Pydantic Schemas ----------
class Asin_analysesData(BaseModel):
    """Entity data schema (for create/update)"""
    asin: str
    marketplace: str = None
    product_title: str = None
    product_data: str = None
    score_functionality: float = None
    score_emotional: float = None
    score_scenario: float = None
    score_user_profile: float = None
    score_differentiation: float = None
    score_market_trend: float = None
    analysis_report: str = None
    created_at: Optional[datetime] = None


class Asin_analysesUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    asin: Optional[str] = None
    marketplace: Optional[str] = None
    product_title: Optional[str] = None
    product_data: Optional[str] = None
    score_functionality: Optional[float] = None
    score_emotional: Optional[float] = None
    score_scenario: Optional[float] = None
    score_user_profile: Optional[float] = None
    score_differentiation: Optional[float] = None
    score_market_trend: Optional[float] = None
    analysis_report: Optional[str] = None
    created_at: Optional[datetime] = None


class Asin_analysesResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    asin: str
    marketplace: Optional[str] = None
    product_title: Optional[str] = None
    product_data: Optional[str] = None
    score_functionality: Optional[float] = None
    score_emotional: Optional[float] = None
    score_scenario: Optional[float] = None
    score_user_profile: Optional[float] = None
    score_differentiation: Optional[float] = None
    score_market_trend: Optional[float] = None
    analysis_report: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Asin_analysesListResponse(BaseModel):
    """List response schema"""
    items: List[Asin_analysesResponse]
    total: int
    skip: int
    limit: int


class Asin_analysesBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[Asin_analysesData]


class Asin_analysesBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: Asin_analysesUpdateData


class Asin_analysesBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[Asin_analysesBatchUpdateItem]


class Asin_analysesBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=Asin_analysesListResponse)
async def query_asin_analysess(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query asin_analysess with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying asin_analysess: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = Asin_analysesService(db)
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
        logger.debug(f"Found {result['total']} asin_analysess")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying asin_analysess: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=Asin_analysesListResponse)
async def query_asin_analysess_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    db: AsyncSession = Depends(get_db),
):
    # Query asin_analysess with filtering, sorting, and pagination without user limitation
    logger.debug(f"Querying asin_analysess: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = Asin_analysesService(db)
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
        logger.debug(f"Found {result['total']} asin_analysess")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying asin_analysess: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=Asin_analysesResponse)
async def get_asin_analyses(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single asin_analyses by ID (user can only see their own records)"""
    logger.debug(f"Fetching asin_analyses with id: {id}, fields={fields}")
    
    service = Asin_analysesService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Asin_analyses with id {id} not found")
            raise HTTPException(status_code=404, detail="Asin_analyses not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching asin_analyses {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=Asin_analysesResponse, status_code=201)
async def create_asin_analyses(
    data: Asin_analysesData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new asin_analyses"""
    logger.debug(f"Creating new asin_analyses with data: {data}")
    
    service = Asin_analysesService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create asin_analyses")
        
        logger.info(f"Asin_analyses created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating asin_analyses: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating asin_analyses: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[Asin_analysesResponse], status_code=201)
async def create_asin_analysess_batch(
    request: Asin_analysesBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple asin_analysess in a single request"""
    logger.debug(f"Batch creating {len(request.items)} asin_analysess")
    
    service = Asin_analysesService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} asin_analysess successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[Asin_analysesResponse])
async def update_asin_analysess_batch(
    request: Asin_analysesBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple asin_analysess in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} asin_analysess")
    
    service = Asin_analysesService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} asin_analysess successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=Asin_analysesResponse)
async def update_asin_analyses(
    id: int,
    data: Asin_analysesUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing asin_analyses (requires ownership)"""
    logger.debug(f"Updating asin_analyses {id} with data: {data}")

    service = Asin_analysesService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Asin_analyses with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Asin_analyses not found")
        
        logger.info(f"Asin_analyses {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating asin_analyses {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating asin_analyses {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_asin_analysess_batch(
    request: Asin_analysesBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple asin_analysess by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} asin_analysess")
    
    service = Asin_analysesService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} asin_analysess successfully")
        return {"message": f"Successfully deleted {deleted_count} asin_analysess", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_asin_analyses(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single asin_analyses by ID (requires ownership)"""
    logger.debug(f"Deleting asin_analyses with id: {id}")
    
    service = Asin_analysesService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"Asin_analyses with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Asin_analyses not found")
        
        logger.info(f"Asin_analyses {id} deleted successfully")
        return {"message": "Asin_analyses deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting asin_analyses {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")