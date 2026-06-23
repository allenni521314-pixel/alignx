"""Execution Records API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ExecutionRecordCreate, ExecutionRecordResponse, PaginatedResponse
from app.services.validation import create_execution, list_executions

router = APIRouter(prefix="/api/v1/execution-records", tags=["execution-records"])


@router.post("", response_model=ExecutionRecordResponse, status_code=201)
async def create(req: ExecutionRecordCreate, db: AsyncSession = Depends(get_db)):
    return await create_execution(req, db)


@router.get("", response_model=PaginatedResponse)
async def list_all(
    asin: str | None = Query(None),
    validation_task_id: str | None = Query(None),
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    return await list_executions(asin, validation_task_id, page, page_size, db)
