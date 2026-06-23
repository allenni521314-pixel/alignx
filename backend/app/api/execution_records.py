"""Execution Records — log actions, costs, and changes per validation task."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ExecutionRecordCreate, ExecutionRecordResponse, PaginatedResponse

router = APIRouter(prefix="/api/v1/execution-records", tags=["execution-records"])


@router.post("", response_model=ExecutionRecordResponse, status_code=201)
async def create_execution_record(
    req: ExecutionRecordCreate,
    db: AsyncSession = Depends(get_db),
):
    """Log an execution action — what was changed, cost, evidence."""
    pass


@router.get("", response_model=PaginatedResponse)
async def list_execution_records(
    asin: str | None = Query(None),
    validation_task_id: str | None = Query(None),
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List execution records, filterable by ASIN or validation_task_id."""
    pass
