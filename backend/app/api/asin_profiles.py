from __future__ import annotations
"""ASIN Operation Profiles API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import AsinOperationProfileResponse, PaginatedResponse
from app.services.validation import list_profiles, get_profile, sync_profile

router = APIRouter(prefix="/api/v1/asin-profiles", tags=["asin-profiles"])


@router.get("", response_model=PaginatedResponse)
async def list_all(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    return await list_profiles(page, page_size, db)


@router.get("/{asin}", response_model=AsinOperationProfileResponse)
async def get(asin: str, db: AsyncSession = Depends(get_db)):
    profile = await get_profile(asin, db)
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile


@router.post("/sync", response_model=AsinOperationProfileResponse)
async def sync(
    asin: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    return await sync_profile(asin, db)
