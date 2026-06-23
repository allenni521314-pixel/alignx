"""Validation Tasks — proposition-driven hypothesis validation."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    ValidationTaskCreate,
    ValidationTaskUpdate,
    ValidationTaskResponse,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/v1/validation-tasks", tags=["validation-tasks"])


@router.post("", response_model=ValidationTaskResponse, status_code=201)
async def create_validation_task(
    req: ValidationTaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new validation task from a matched proposition."""
    pass


@router.get("", response_model=PaginatedResponse)
async def list_validation_tasks(
    asin: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List validation tasks, optionally filtered by ASIN."""
    pass


@router.get("/{task_id}", response_model=ValidationTaskResponse)
async def get_validation_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single validation task by ID."""
    pass


@router.patch("/{task_id}", response_model=ValidationTaskResponse)
async def update_validation_task(
    task_id: str,
    req: ValidationTaskUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update validation task status."""
    pass
