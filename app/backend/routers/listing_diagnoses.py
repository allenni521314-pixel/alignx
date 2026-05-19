import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.listing_diagnoses import Listing_diagnosesService
from dependencies.auth import get_current_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/listing_diagnoses", tags=["listing_diagnoses"])


# ---------- Pydantic Schemas ----------
class Listing_diagnosesData(BaseModel):
    """Entity data schema (for create/update)"""
    listing_title: str
    marketplace: str = None
    input_data: str = None
    score_function_expression: float = None
    score_scenario_expression: float = None
    score_identity_fit: float = None
    score_psychology_benefit: float = None
    score_risk_elimination: float = None
    score_differentiation: float = None
    diagnosis_report: str = None
    keyword_report: str = None
    created_at: Optional[datetime] = None


class Listing_diagnosesUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    listing_title: Optional[str] = None
    marketplace: Optional[str] = None
    input_data: Optional[str] = None
    score_function_expression: Optional[float] = None
    score_scenario_expression: Optional[float] = None
    score_identity_fit: Optional[float] = None
    score_psychology_benefit: Optional[float] = None
    score_risk_elimination: Optional[float] = None
    score_differentiation: Optional[float] = None
    diagnosis_report: Optional[str] = None
    keyword_report: Optional[str] = None
    created_at: Optional[datetime] = None


class Listing_diagnosesResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    listing_title: str
    marketplace: Optional[str] = None
    input_data: Optional[str] = None
    score_function_expression: Optional[float] = None
    score_scenario_expression: Optional[float] = None
    score_identity_fit: Optional[float] = None
    score_psychology_benefit: Optional[float] = None
    score_risk_elimination: Optional[float] = None
    score_differentiation: Optional[float] = None
    diagnosis_report: Optional[str] = None
    keyword_report: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Listing_diagnosesListResponse(BaseModel):
    """List response schema"""
    items: List[Listing_diagnosesResponse]
    total: int
    skip: int
    limit: int


class Listing_diagnosesBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[Listing_diagnosesData]


class Listing_diagnosesBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: Listing_diagnosesUpdateData


class Listing_diagnosesBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[Listing_diagnosesBatchUpdateItem]


class Listing_diagnosesBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=Listing_diagnosesListResponse)
async def query_listing_diagnosess(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query listing_diagnosess with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying listing_diagnosess: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = Listing_diagnosesService(db)
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
        logger.debug(f"Found {result['total']} listing_diagnosess")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying listing_diagnosess: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=Listing_diagnosesListResponse)
async def query_listing_diagnosess_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    db: AsyncSession = Depends(get_db),
):
    # Query listing_diagnosess with filtering, sorting, and pagination without user limitation
    logger.debug(f"Querying listing_diagnosess: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = Listing_diagnosesService(db)
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
        logger.debug(f"Found {result['total']} listing_diagnosess")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying listing_diagnosess: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=Listing_diagnosesResponse)
async def get_listing_diagnoses(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single listing_diagnoses by ID (user can only see their own records)"""
    logger.debug(f"Fetching listing_diagnoses with id: {id}, fields={fields}")
    
    service = Listing_diagnosesService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Listing_diagnoses with id {id} not found")
            raise HTTPException(status_code=404, detail="Listing_diagnoses not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching listing_diagnoses {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=Listing_diagnosesResponse, status_code=201)
async def create_listing_diagnoses(
    data: Listing_diagnosesData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new listing_diagnoses"""
    logger.debug(f"Creating new listing_diagnoses with data: {data}")
    
    service = Listing_diagnosesService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create listing_diagnoses")
        
        logger.info(f"Listing_diagnoses created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating listing_diagnoses: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating listing_diagnoses: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[Listing_diagnosesResponse], status_code=201)
async def create_listing_diagnosess_batch(
    request: Listing_diagnosesBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple listing_diagnosess in a single request"""
    logger.debug(f"Batch creating {len(request.items)} listing_diagnosess")
    
    service = Listing_diagnosesService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} listing_diagnosess successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[Listing_diagnosesResponse])
async def update_listing_diagnosess_batch(
    request: Listing_diagnosesBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple listing_diagnosess in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} listing_diagnosess")
    
    service = Listing_diagnosesService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} listing_diagnosess successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=Listing_diagnosesResponse)
async def update_listing_diagnoses(
    id: int,
    data: Listing_diagnosesUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing listing_diagnoses (requires ownership)"""
    logger.debug(f"Updating listing_diagnoses {id} with data: {data}")

    service = Listing_diagnosesService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Listing_diagnoses with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Listing_diagnoses not found")
        
        logger.info(f"Listing_diagnoses {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating listing_diagnoses {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating listing_diagnoses {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_listing_diagnosess_batch(
    request: Listing_diagnosesBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple listing_diagnosess by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} listing_diagnosess")
    
    service = Listing_diagnosesService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} listing_diagnosess successfully")
        return {"message": f"Successfully deleted {deleted_count} listing_diagnosess", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_listing_diagnoses(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single listing_diagnoses by ID (requires ownership)"""
    logger.debug(f"Deleting listing_diagnoses with id: {id}")
    
    service = Listing_diagnosesService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"Listing_diagnoses with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Listing_diagnoses not found")
        
        logger.info(f"Listing_diagnoses {id} deleted successfully")
        return {"message": "Listing_diagnoses deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting listing_diagnoses {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")