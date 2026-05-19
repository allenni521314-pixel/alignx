import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.sales_metrics import Sales_metricsService
from dependencies.auth import get_current_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/sales_metrics", tags=["sales_metrics"])


# ---------- Pydantic Schemas ----------
class Sales_metricsData(BaseModel):
    """Entity data schema (for create/update)"""
    date: date
    revenue: float
    orders: int
    acos: float = None
    profit_margin: float = None
    sessions: int = None
    conversion_rate: float = None


class Sales_metricsUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    date: Optional[date] = None
    revenue: Optional[float] = None
    orders: Optional[int] = None
    acos: Optional[float] = None
    profit_margin: Optional[float] = None
    sessions: Optional[int] = None
    conversion_rate: Optional[float] = None


class Sales_metricsResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    date: date
    revenue: float
    orders: int
    acos: Optional[float] = None
    profit_margin: Optional[float] = None
    sessions: Optional[int] = None
    conversion_rate: Optional[float] = None

    class Config:
        from_attributes = True


class Sales_metricsListResponse(BaseModel):
    """List response schema"""
    items: List[Sales_metricsResponse]
    total: int
    skip: int
    limit: int


class Sales_metricsBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[Sales_metricsData]


class Sales_metricsBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: Sales_metricsUpdateData


class Sales_metricsBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[Sales_metricsBatchUpdateItem]


class Sales_metricsBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=Sales_metricsListResponse)
async def query_sales_metricss(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query sales_metricss with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying sales_metricss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = Sales_metricsService(db)
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
        logger.debug(f"Found {result['total']} sales_metricss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying sales_metricss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=Sales_metricsListResponse)
async def query_sales_metricss_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    db: AsyncSession = Depends(get_db),
):
    # Query sales_metricss with filtering, sorting, and pagination without user limitation
    logger.debug(f"Querying sales_metricss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = Sales_metricsService(db)
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
        logger.debug(f"Found {result['total']} sales_metricss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying sales_metricss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=Sales_metricsResponse)
async def get_sales_metrics(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single sales_metrics by ID (user can only see their own records)"""
    logger.debug(f"Fetching sales_metrics with id: {id}, fields={fields}")
    
    service = Sales_metricsService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Sales_metrics with id {id} not found")
            raise HTTPException(status_code=404, detail="Sales_metrics not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching sales_metrics {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=Sales_metricsResponse, status_code=201)
async def create_sales_metrics(
    data: Sales_metricsData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new sales_metrics"""
    logger.debug(f"Creating new sales_metrics with data: {data}")
    
    service = Sales_metricsService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create sales_metrics")
        
        logger.info(f"Sales_metrics created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating sales_metrics: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating sales_metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[Sales_metricsResponse], status_code=201)
async def create_sales_metricss_batch(
    request: Sales_metricsBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple sales_metricss in a single request"""
    logger.debug(f"Batch creating {len(request.items)} sales_metricss")
    
    service = Sales_metricsService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} sales_metricss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[Sales_metricsResponse])
async def update_sales_metricss_batch(
    request: Sales_metricsBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple sales_metricss in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} sales_metricss")
    
    service = Sales_metricsService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} sales_metricss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=Sales_metricsResponse)
async def update_sales_metrics(
    id: int,
    data: Sales_metricsUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing sales_metrics (requires ownership)"""
    logger.debug(f"Updating sales_metrics {id} with data: {data}")

    service = Sales_metricsService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Sales_metrics with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Sales_metrics not found")
        
        logger.info(f"Sales_metrics {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating sales_metrics {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating sales_metrics {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_sales_metricss_batch(
    request: Sales_metricsBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple sales_metricss by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} sales_metricss")
    
    service = Sales_metricsService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} sales_metricss successfully")
        return {"message": f"Successfully deleted {deleted_count} sales_metricss", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_sales_metrics(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single sales_metrics by ID (requires ownership)"""
    logger.debug(f"Deleting sales_metrics with id: {id}")
    
    service = Sales_metricsService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"Sales_metrics with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Sales_metrics not found")
        
        logger.info(f"Sales_metrics {id} deleted successfully")
        return {"message": "Sales_metrics deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting sales_metrics {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")