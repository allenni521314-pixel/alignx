import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.optimization_timeline import Optimization_timelineService
from dependencies.auth import get_current_user
from schemas.auth import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/optimization_timeline", tags=["optimization_timeline"])


class Optimization_timelineData(BaseModel):
    product_id: int
    step_name: str
    action_timestamp: Optional[str] = None
    listing_score: Optional[int] = 0
    score_details: Optional[str] = "{}"
    optimization_round: Optional[int] = 1


class Optimization_timelineResponse(BaseModel):
    id: int
    product_id: int
    step_name: str
    action_timestamp: Optional[str] = None
    listing_score: Optional[int] = 0
    score_details: Optional[str] = "{}"
    optimization_round: Optional[int] = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Optimization_timelineListResponse(BaseModel):
    items: List[Optimization_timelineResponse]
    total: int
    skip: int
    limit: int


@router.post("", response_model=Optimization_timelineResponse)
async def create_optimization_timeline(
    data: Optimization_timelineData,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    service = Optimization_timelineService(db)
    obj = await service.create(data.model_dump(exclude_unset=True))
    if not obj:
        raise HTTPException(status_code=500, detail="Failed to create optimization_timeline")
    return obj


@router.get("", response_model=Optimization_timelineListResponse)
async def list_optimization_timeline(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    sort: Optional[str] = Query(None),
    product_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    service = Optimization_timelineService(db)
    query_filter = {}
    if product_id is not None:
        query_filter["product_id"] = product_id
    items, total = await service.get_list(
        skip=skip, limit=limit, sort=sort, query_filter=query_filter if query_filter else None
    )
    return Optimization_timelineListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{item_id}", response_model=Optimization_timelineResponse)
async def get_optimization_timeline(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    service = Optimization_timelineService(db)
    obj = await service.get_by_id(item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="optimization_timeline not found")
    return obj


@router.delete("/{item_id}")
async def delete_optimization_timeline(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    service = Optimization_timelineService(db)
    success = await service.delete(item_id)
    if not success:
        raise HTTPException(status_code=404, detail="optimization_timeline not found")
    return {"message": "Deleted successfully"}
