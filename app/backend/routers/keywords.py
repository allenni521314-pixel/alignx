import json
import logging
from typing import List, Optional


from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.keywords import KeywordsService
from dependencies.auth import get_current_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/keywords", tags=["keywords"])


# ---------- Pydantic Schemas ----------
class KeywordsData(BaseModel):
    """Entity data schema (for create/update)"""
    keyword: str
    match_type: str = None
    search_volume: int = None
    bid: float = None
    suggested_bid: float = None
    acos: float = None
    conversions: int = None
    relevance_score: float = None
    campaign_id: int = None


class KeywordsUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    keyword: Optional[str] = None
    match_type: Optional[str] = None
    search_volume: Optional[int] = None
    bid: Optional[float] = None
    suggested_bid: Optional[float] = None
    acos: Optional[float] = None
    conversions: Optional[int] = None
    relevance_score: Optional[float] = None
    campaign_id: Optional[int] = None


class KeywordsResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    keyword: str
    match_type: Optional[str] = None
    search_volume: Optional[int] = None
    bid: Optional[float] = None
    suggested_bid: Optional[float] = None
    acos: Optional[float] = None
    conversions: Optional[int] = None
    relevance_score: Optional[float] = None
    campaign_id: Optional[int] = None

    class Config:
        from_attributes = True


class KeywordsListResponse(BaseModel):
    """List response schema"""
    items: List[KeywordsResponse]
    total: int
    skip: int
    limit: int


class KeywordsBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[KeywordsData]


class KeywordsBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: KeywordsUpdateData


class KeywordsBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[KeywordsBatchUpdateItem]


class KeywordsBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=KeywordsListResponse)
async def query_keywordss(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query keywordss with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying keywordss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = KeywordsService(db)
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
        logger.debug(f"Found {result['total']} keywordss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying keywordss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=KeywordsListResponse)
async def query_keywordss_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Query keywordss with filtering, sorting, and pagination current user only
    logger.debug(f"Querying keywordss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = KeywordsService(db)
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
        logger.debug(f"Found {result['total']} keywordss")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying keywordss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=KeywordsResponse)
async def get_keywords(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single keywords by ID (user can only see their own records)"""
    logger.debug(f"Fetching keywords with id: {id}, fields={fields}")
    
    service = KeywordsService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Keywords with id {id} not found")
            raise HTTPException(status_code=404, detail="Keywords not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching keywords {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=KeywordsResponse, status_code=201)
async def create_keywords(
    data: KeywordsData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new keywords"""
    logger.debug(f"Creating new keywords with data: {data}")
    
    service = KeywordsService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create keywords")
        
        logger.info(f"Keywords created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating keywords: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating keywords: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[KeywordsResponse], status_code=201)
async def create_keywordss_batch(
    request: KeywordsBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple keywordss in a single request"""
    logger.debug(f"Batch creating {len(request.items)} keywordss")
    
    service = KeywordsService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} keywordss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[KeywordsResponse])
async def update_keywordss_batch(
    request: KeywordsBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple keywordss in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} keywordss")
    
    service = KeywordsService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} keywordss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=KeywordsResponse)
async def update_keywords(
    id: int,
    data: KeywordsUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing keywords (requires ownership)"""
    logger.debug(f"Updating keywords {id} with data: {data}")

    service = KeywordsService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Keywords with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Keywords not found")
        
        logger.info(f"Keywords {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating keywords {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating keywords {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_keywordss_batch(
    request: KeywordsBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple keywordss by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} keywordss")
    
    service = KeywordsService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} keywordss successfully")
        return {"message": f"Successfully deleted {deleted_count} keywordss", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_keywords(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single keywords by ID (requires ownership)"""
    logger.debug(f"Deleting keywords with id: {id}")
    
    service = KeywordsService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"Keywords with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Keywords not found")
        
        logger.info(f"Keywords {id} deleted successfully")
        return {"message": "Keywords deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting keywords {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")