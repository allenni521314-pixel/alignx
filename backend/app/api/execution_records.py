from __future__ import annotations
"""Execution Records API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ExecutionRecordCreate, ExecutionRecordResponse, PaginatedResponse
from app.services.validation import create_execution, list_executions
from app.api.deps import get_current_user_id

router = APIRouter(prefix="/api/v1/execution-records", tags=["execution-records"])


@router.post("", response_model=ExecutionRecordResponse, status_code=201)
async def create(req: ExecutionRecordCreate, db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    try:
        return await create_execution(req, db, user_id=user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=PaginatedResponse)
async def list_all(
    asin: str | None = Query(None),
    validation_task_id: str | None = Query(None),
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await list_executions(asin, validation_task_id, page, page_size, db, user_id=user_id)
