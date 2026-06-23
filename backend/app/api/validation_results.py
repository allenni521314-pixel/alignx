"""Validation Results API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ValidationResultCreate, ValidationResultResponse, PaginatedResponse
from app.services.validation import create_result, list_results

router = APIRouter(prefix="/api/v1/validation-results", tags=["validation-results"])


@router.post("", response_model=ValidationResultResponse, status_code=201)
async def create(req: ValidationResultCreate, db: AsyncSession = Depends(get_db)):
    return await create_result(req, db)


@router.get("", response_model=PaginatedResponse)
async def list_all(
    asin: str | None = Query(None),
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    return await list_results(asin, page, page_size, db)
