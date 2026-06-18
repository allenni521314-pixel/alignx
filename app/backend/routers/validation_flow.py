from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from schemas.asin_business_profile import (
    EffectValidationRunRequest,
    EffectValidationRunResponse,
    ExecutionLogCreate,
    ExecutionLogListResponse,
    ValidationTaskCreate,
    ValidationTaskResponse,
)
from schemas.auth import UserResponse
from services.asin_business_profile import AsinBusinessProfileService


validation_router = APIRouter(prefix="/api/validation-tasks", tags=["validation-tasks"])
execution_router = APIRouter(prefix="/api/execution-logs", tags=["execution-logs"])
effect_router = APIRouter(prefix="/api/effect-validation", tags=["effect-validation"])


@validation_router.post("", response_model=ValidationTaskResponse, status_code=201)
async def create_validation_task(
    data: ValidationTaskCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    try:
        return await service.create_validation_task(seller_id=str(current_user.id), data=data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@execution_router.get("", response_model=ExecutionLogListResponse)
async def list_execution_logs(
    asin: str = "",
    validation_id: str = "",
    store_id: str = "",
    marketplace: str = "",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    return await service.list_execution_logs(
        seller_id=str(current_user.id),
        asin=asin or None,
        validation_id=validation_id or None,
        store_id=store_id or None,
        marketplace=marketplace or None,
        skip=skip,
        limit=limit,
    )


@execution_router.post("", status_code=201)
async def create_execution_log(
    data: ExecutionLogCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    try:
        log = await service.create_execution_log(seller_id=str(current_user.id), data=data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"execution_id": log.execution_id, "validation_id": log.validation_id, "asin": log.asin}


@effect_router.post("/run", response_model=EffectValidationRunResponse)
async def run_effect_validation(
    data: EffectValidationRunRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    try:
        return await service.run_effect_validation(
            seller_id=str(current_user.id),
            validation_id=data.validation_id,
            result_start_date=data.result_start_date,
            result_end_date=data.result_end_date,
            minimum_sample_ready=data.minimum_sample_ready,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="暂无")


router = [validation_router, execution_router, effect_router]
