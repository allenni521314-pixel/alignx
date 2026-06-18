import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from models.asin_business_profile import AiDecisionTrace, AsinDailySnapshot, ValidationTask
from schemas.asin_business_profile import (
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


@effect_router.post("/run")
async def run_effect_validation(
    validation_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ValidationTask).where(
            ValidationTask.validation_id == validation_id,
            ValidationTask.seller_id == str(current_user.id),
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="暂无")

    metric = (task.target_metric or "").lower()
    column_map = {
        "sessions": AsinDailySnapshot.sessions,
        "clicks": AsinDailySnapshot.clicks,
        "orders": AsinDailySnapshot.orders,
        "sales": AsinDailySnapshot.total_sales,
        "total_sales": AsinDailySnapshot.total_sales,
        "ctr": AsinDailySnapshot.ctr,
        "cvr": AsinDailySnapshot.cvr,
        "acos": AsinDailySnapshot.acos,
        "tacos": AsinDailySnapshot.tacos,
        "ad_spend": AsinDailySnapshot.ad_spend,
        "ad_sales": AsinDailySnapshot.ad_sales,
    }
    metric_column = column_map.get(metric)
    if metric_column is None:
        task.status = "Inconclusive"
        task.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"validation_id": task.validation_id, "status": task.status}

    baseline_value = await _period_average(db, task, metric_column, task.baseline_start_date, task.baseline_end_date)
    result_value = await _period_average(db, task, metric_column, task.test_start_date, task.test_end_date)
    task.baseline_value = baseline_value
    task.result_value = result_value
    if baseline_value in (None, 0) or result_value is None:
        task.status = "Inconclusive"
    else:
        task.improvement_rate = round((result_value - baseline_value) / baseline_value, 6)
        if task.target_value is not None and result_value >= task.target_value:
            task.status = "Success"
        elif result_value < baseline_value:
            task.status = "Failed"
        else:
            task.status = "Inconclusive"
    task.updated_at = datetime.now(timezone.utc)

    db.add(
        AiDecisionTrace(
            decision_id=f"effect_{uuid.uuid4().hex}",
            seller_id=task.seller_id,
            store_id=task.store_id,
            marketplace=task.marketplace,
            asin=task.asin,
            related_validation_id=task.validation_id,
            decision_type="Effect Validation",
            conclusion=task.status,
            evidence_metrics="{}",
            reasoning_summary=task.target_metric,
            confidence_score=task.confidence_score,
            recommended_action=task.action_plan,
        )
    )
    await db.commit()
    return {
        "validation_id": task.validation_id,
        "status": task.status,
        "baseline_value": task.baseline_value,
        "result_value": task.result_value,
        "improvement_rate": task.improvement_rate,
    }


async def _period_average(db: AsyncSession, task: ValidationTask, metric_column, start_date, end_date):
    if not start_date or not end_date:
        return None
    result = await db.execute(
        select(func.avg(metric_column)).where(
            AsinDailySnapshot.seller_id == task.seller_id,
            AsinDailySnapshot.store_id == task.store_id,
            AsinDailySnapshot.marketplace == task.marketplace,
            AsinDailySnapshot.asin == task.asin,
            AsinDailySnapshot.date >= start_date,
            AsinDailySnapshot.date <= end_date,
        )
    )
    value = result.scalar()
    return float(value) if value is not None else None


router = [validation_router, execution_router, effect_router]
