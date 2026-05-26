import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.products import ProductsService
from dependencies.auth import get_current_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/products", tags=["products"])


# ---------- Pydantic Schemas ----------
class ProductsData(BaseModel):
    """Entity data schema (for create/update)"""
    asin: str
    title: str
    bullet_points: str = None
    a_plus_content: str = None
    search_keywords: str = None
    price: float = None
    review_count: int = None
    rating: float = None
    category: str = None
    lifecycle_stage: str = None
    optimization_round: int = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProductsUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    asin: Optional[str] = None
    title: Optional[str] = None
    bullet_points: Optional[str] = None
    a_plus_content: Optional[str] = None
    search_keywords: Optional[str] = None
    price: Optional[float] = None
    review_count: Optional[int] = None
    rating: Optional[float] = None
    category: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    optimization_round: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProductsResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    asin: str
    title: str
    bullet_points: Optional[str] = None
    a_plus_content: Optional[str] = None
    search_keywords: Optional[str] = None
    price: Optional[float] = None
    review_count: Optional[int] = None
    rating: Optional[float] = None
    category: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    optimization_round: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProductsListResponse(BaseModel):
    """List response schema"""
    items: List[ProductsResponse]
    total: int
    skip: int
    limit: int


class ProductsBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[ProductsData]


class ProductsBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: ProductsUpdateData


class ProductsBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[ProductsBatchUpdateItem]


class ProductsBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=ProductsListResponse)
async def query_productss(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query productss with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying productss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = ProductsService(db)
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
        logger.debug(f"Found {result['total']} productss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying productss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=ProductsListResponse)
async def query_productss_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Query productss with filtering, sorting, and pagination current user only
    logger.debug(f"Querying productss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = ProductsService(db)
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
        logger.debug(f"Found {result['total']} productss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying productss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=ProductsResponse)
async def get_products(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single products by ID (user can only see their own records)"""
    logger.debug(f"Fetching products with id: {id}, fields={fields}")
    
    service = ProductsService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Products with id {id} not found")
            raise HTTPException(status_code=404, detail="Products not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching products {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=ProductsResponse, status_code=201)
async def create_products(
    data: ProductsData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new products"""
    logger.debug(f"Creating new products with data: {data}")
    
    service = ProductsService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create products")
        
        logger.info(f"Products created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating products: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating products: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[ProductsResponse], status_code=201)
async def create_productss_batch(
    request: ProductsBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple productss in a single request"""
    logger.debug(f"Batch creating {len(request.items)} productss")
    
    service = ProductsService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} productss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[ProductsResponse])
async def update_productss_batch(
    request: ProductsBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple productss in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} productss")
    
    service = ProductsService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} productss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=ProductsResponse)
async def update_products(
    id: int,
    data: ProductsUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing products (requires ownership)"""
    logger.debug(f"Updating products {id} with data: {data}")

    service = ProductsService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Products with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Products not found")
        
        logger.info(f"Products {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating products {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating products {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_productss_batch(
    request: ProductsBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple productss by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} productss")
    
    service = ProductsService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} productss successfully")
        return {"message": f"Successfully deleted {deleted_count} productss", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_products(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single products by ID (requires ownership)"""
    logger.debug(f"Deleting products with id: {id}")
    
    service = ProductsService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"Products with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Products not found")
        
        logger.info(f"Products {id} deleted successfully")
        return {"message": "Products deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting products {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")