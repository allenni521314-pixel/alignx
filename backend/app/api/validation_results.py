"""Validation Results — before/after metric comparison and attribution."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ValidationResultCreate, ValidationResultResponse, PaginatedResponse

router = APIRouter(prefix="/api/v1/validation-results", tags=["validation-results"])


@router.post("", response_model=ValidationResultResponse, status_code=201)
async def create_validation_result(
    req: ValidationResultCreate,
    db: AsyncSession = Depends(get_db),
):
    """Submit validation result — baseline vs result metrics, attribution conclusion."""
    pass


@router.get("", response_model=PaginatedResponse)
async def list_validation_results(
    asin: str | None = Query(None),
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List validation results, filterable by ASIN."""
    pass
