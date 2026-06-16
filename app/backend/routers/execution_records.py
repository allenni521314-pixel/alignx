import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user, get_user_scope_ids
from schemas.auth import UserResponse
from services.execution_records import ExecutionRecordService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/execution_records", tags=["execution_records"])


class ExecutionRecordData(BaseModel):
    execution_id: Optional[str] = None
    record_type: str
    issue: Optional[str] = None
    reason: Optional[str] = None
    confidence: Optional[str] = None
    suggested_action: Optional[str] = None
    execution_content: Optional[str] = None
    execution_time: Optional[str] = None
    execution_target: Optional[str] = None
    executor: Optional[str] = None
    validation_status: str = "待执行"
    validation_cycle: Optional[str] = None
    result: Optional[str] = "待录入"


class ExecutionRecordUpdateData(BaseModel):
    record_type: Optional[str] = None
    issue: Optional[str] = None
    reason: Optional[str] = None
    confidence: Optional[str] = None
    suggested_action: Optional[str] = None
    execution_content: Optional[str] = None
    execution_time: Optional[str] = None
    execution_target: Optional[str] = None
    executor: Optional[str] = None
    validation_status: Optional[str] = None
    validation_cycle: Optional[str] = None
    result: Optional[str] = None


class ExecutionRecordResponse(BaseModel):
    id: int
    user_id: str
    execution_id: str
    record_type: str
    issue: Optional[str] = None
    reason: Optional[str] = None
    confidence: Optional[str] = None
    suggested_action: Optional[str] = None
    execution_content: Optional[str] = None
    execution_time: Optional[str] = None
    execution_target: Optional[str] = None
    executor: Optional[str] = None
    validation_status: str
    validation_cycle: Optional[str] = None
    result: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExecutionRecordListResponse(BaseModel):
    items: List[ExecutionRecordResponse]
    total: int
    skip: int
    limit: int


@router.get("", response_model=ExecutionRecordListResponse)
async def query_execution_records(
    query: str = Query(None),
    sort: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=2000),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ExecutionRecordService(db)
    try:
        query_dict = json.loads(query) if query else None
        scope_user_ids = await get_user_scope_ids(current_user, db)
        return await service.get_list(skip=skip, limit=limit, query_dict=query_dict, sort=sort, user_id=scope_user_ids)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid query JSON format")
    except Exception as e:
        logger.error("Error querying execution_records: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=ExecutionRecordResponse, status_code=201)
async def create_execution_record(
    data: ExecutionRecordData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ExecutionRecordService(db)
    payload = data.model_dump()
    if not payload.get("execution_id"):
        payload["execution_id"] = f"AUTO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    try:
        return await service.create(payload, user_id=str(current_user.id))
    except Exception as e:
        logger.error("Error creating execution_record: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/{id}", response_model=ExecutionRecordResponse)
async def update_execution_record(
    id: int,
    data: ExecutionRecordUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ExecutionRecordService(db)
    scope_user_ids = await get_user_scope_ids(current_user, db)
    update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
    result = await service.update(id, update_dict, user_id=scope_user_ids)
    if not result:
        raise HTTPException(status_code=404, detail="Execution record not found")
    return result


@router.delete("/{id}")
async def delete_execution_record(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ExecutionRecordService(db)
    scope_user_ids = await get_user_scope_ids(current_user, db)
    success = await service.delete(id, user_id=scope_user_ids)
    if not success:
        raise HTTPException(status_code=404, detail="Execution record not found")
    return {"message": "Execution record deleted successfully", "id": id}
