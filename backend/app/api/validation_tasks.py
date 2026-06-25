from __future__ import annotations
"""Validation Tasks — proposition-driven hypothesis validation."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ValidationTaskCreate, ValidationTaskUpdate, ValidationTaskResponse, PaginatedResponse
from app.services.validation_tasks import create_task, list_tasks, get_task, update_task
from app.api.deps import get_current_user_id

router = APIRouter(prefix="/api/v1/validation-tasks", tags=["validation-tasks"])


@router.post("/", response_model=ValidationTaskResponse)
async def create(
    req: ValidationTaskCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_current_user_id),
):
    return await create_task(req, db, user_id=user_id)

@router.get("", response_model=PaginatedResponse)
async def list_all(
    asin: str | None = Query(None),
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    return await list_tasks(asin, page, page_size, db)


@router.get("/{task_id}", response_model=ValidationTaskResponse)
async def get(task_id: str, db: AsyncSession = Depends(get_db)):
    t = await get_task(task_id, db)
    if not t:
        raise HTTPException(404, "Task not found")
    return t


@router.patch("/{task_id}", response_model=ValidationTaskResponse)
async def update(task_id: str, req: ValidationTaskUpdate, db: AsyncSession = Depends(get_db)):
    t = await update_task(task_id, req, db)
    if not t:
        raise HTTPException(404, "Task not found")
    return t
