"""ASIN Operation Profiles — cumulative validation history per ASIN."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import AsinOperationProfileResponse, PaginatedResponse

router = APIRouter(prefix="/api/v1/asin-profiles", tags=["asin-profiles"])


@router.get("", response_model=PaginatedResponse)
async def list_asin_profiles(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List all ASIN operation profiles."""
    pass


@router.get("/{asin}", response_model=AsinOperationProfileResponse)
async def get_asin_profile(
    asin: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single ASIN operation profile."""
    pass


@router.post("/sync", response_model=AsinOperationProfileResponse)
async def sync_asin_profile(
    asin: str,
    db: AsyncSession = Depends(get_db),
):
    """Sync/recalculate ASIN operation profile from validation & execution history."""
    pass
