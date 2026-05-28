import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from core.database import db_manager, get_db
from dependencies.auth import get_current_user, get_user_scope_ids
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from models.diagnosis_tasks import DiagnosisTask
from pydantic import BaseModel, Field
from schemas.auth import UserResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from routers.asin_analysis import AnalyzeAsinRequest, _analyze_single_asin
from routers.listing_diagnosis import (
    DiagnoseRequest,
    _diagnose_single,
    _fallback_listing_diagnosis,
    _has_required_price,
    _normalize_diagnosis_result,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/diagnosis-tasks", tags=["diagnosis-tasks"])


class DiagnosisTaskResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    progress_percent: float = 0
    title: str = ""
    asin: str = ""
    marketplace: str = ""
    result_payload: dict[str, Any] | None = None
    error_message: str = ""
    source_record_table: str = ""
    source_record_id: str = ""
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str | None = None


class DiagnosisTaskListResponse(BaseModel):
    items: list[DiagnosisTaskResponse] = Field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _public_task(task: DiagnosisTask) -> DiagnosisTaskResponse:
    return DiagnosisTaskResponse(
        task_id=task.task_id,
        task_type=task.task_type,
        status=task.status,
        progress_percent=float(task.progress_percent or 0),
        title=task.title or "",
        asin=task.asin or "",
        marketplace=task.marketplace or "",
        result_payload=task.result_payload if isinstance(task.result_payload, dict) else None,
        error_message=task.error_message or "",
        source_record_table=task.source_record_table or "",
        source_record_id=task.source_record_id or "",
        created_at=task.created_at.isoformat() if task.created_at else None,
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
    )


async def _set_task_status(
    db: AsyncSession,
    task_id: str,
    status: str,
    progress: float,
    *,
    result: dict[str, Any] | None = None,
    error: str = "",
    source_record_table: str = "",
    source_record_id: str | int | None = None,
) -> None:
    row = (
        await db.execute(select(DiagnosisTask).where(DiagnosisTask.task_id == task_id))
    ).scalar_one_or_none()
    if not row:
        return
    row.status = status
    row.progress_percent = progress
    row.updated_at = _now()
    if status == "running" and not row.started_at:
        row.started_at = _now()
    if status in {"completed", "failed"}:
        row.completed_at = _now()
    if result is not None:
        row.result_payload = jsonable_encoder(result)
    if error:
        row.error_message = error[:2000]
    if source_record_table:
        row.source_record_table = source_record_table
    if source_record_id is not None:
        row.source_record_id = str(source_record_id)
    await db.commit()


async def _run_listing_task(task_id: str, user_id: str, payload: dict[str, Any]) -> None:
    if not db_manager.async_session_maker:
        await db_manager.ensure_initialized()
    async with db_manager.async_session_maker() as db:
        request: DiagnoseRequest | None = None
        try:
            await _set_task_status(db, task_id, "running", 12)
            request = DiagnoseRequest.model_validate(payload)
            if not _has_required_price(request.listing.price):
                raise HTTPException(
                    status_code=400,
                    detail="缺少价格，不能生成正式诊断报告。请补充价格或价格区间后再诊断。",
                )
            result = await _diagnose_single(
                listing=request.listing,
                user_id=user_id,
                db=db,
                save=True,
                precision_context=request.precision_context,
            )
            normalized = _normalize_diagnosis_result(result, request.listing)
            await _set_task_status(
                db,
                task_id,
                "completed",
                100,
                result=normalized,
                source_record_table="listing_diagnoses",
                source_record_id=normalized.get("id"),
            )
        except HTTPException as exc:
            logger.warning("Listing diagnosis task rejected: %s", task_id)
            await _set_task_status(db, task_id, "failed", 100, error=str(exc.detail))
        except Exception as exc:
            logger.exception("Listing diagnosis task failed: %s", task_id)
            if request is not None:
                fallback = _fallback_listing_diagnosis(
                    request.listing,
                    reason=f"后台诊断任务异常，已返回保守兜底结果。错误：{str(exc)[:300]}",
                )
                normalized = _normalize_diagnosis_result(fallback, request.listing)
                normalized.setdefault("trace", {})
                normalized["trace"]["task_recovered_from_error"] = str(exc)[:500]
                await _set_task_status(
                    db,
                    task_id,
                    "completed",
                    100,
                    result=normalized,
                    source_record_table="listing_diagnoses",
                )
                return
            await _set_task_status(db, task_id, "failed", 100, error=str(exc))


async def _run_asin_task(task_id: str, user_id: str, payload: dict[str, Any]) -> None:
    if not db_manager.async_session_maker:
        await db_manager.ensure_initialized()
    async with db_manager.async_session_maker() as db:
        try:
            await _set_task_status(db, task_id, "running", 10)
            request = AnalyzeAsinRequest.model_validate(payload)
            result = await _analyze_single_asin(
                asin=request.asin.strip().upper(),
                marketplace=request.marketplace,
                user_id=user_id,
                db=db,
            )
            encoded = jsonable_encoder(result)
            await _set_task_status(
                db,
                task_id,
                "completed",
                100,
                result=encoded,
                source_record_table="asin_analyses",
                source_record_id=encoded.get("id"),
            )
        except Exception as exc:
            logger.exception("ASIN analysis task failed: %s", task_id)
            await _set_task_status(db, task_id, "failed", 100, error=str(exc))


@router.post("/listing", response_model=DiagnosisTaskResponse)
async def create_listing_task(
    request: DiagnoseRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    listing = request.listing
    if not listing.title and not listing.bullet_points:
        raise HTTPException(status_code=400, detail="请至少输入标题或五点描述")
    if not _has_required_price(listing.price):
        raise HTTPException(status_code=400, detail="缺少价格，不能生成正式诊断报告。请补充价格或价格区间后再诊断。")
    task_id = f"lst_{uuid4().hex}"
    payload = request.model_dump()
    task = DiagnosisTask(
        task_id=task_id,
        user_id=str(current_user.id),
        task_type="listing_diagnosis",
        status="pending",
        progress_percent=0,
        title=(listing.title or "")[:500],
        asin=listing.asin or "",
        marketplace=listing.marketplace or "US",
        input_payload=jsonable_encoder(payload),
        source_record_table="listing_diagnoses",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    background_tasks.add_task(_run_listing_task, task_id, str(current_user.id), payload)
    return _public_task(task)


@router.post("/asin", response_model=DiagnosisTaskResponse)
async def create_asin_task(
    request: AnalyzeAsinRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asin = request.asin.strip().upper()
    if not asin or len(asin) != 10:
        raise HTTPException(status_code=400, detail="请输入有效的10位ASIN")
    task_id = f"asn_{uuid4().hex}"
    payload = request.model_dump()
    task = DiagnosisTask(
        task_id=task_id,
        user_id=str(current_user.id),
        task_type="asin_analysis",
        status="pending",
        progress_percent=0,
        title=asin,
        asin=asin,
        marketplace=request.marketplace or "US",
        input_payload=jsonable_encoder(payload),
        source_record_table="asin_analyses",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    background_tasks.add_task(_run_asin_task, task_id, str(current_user.id), payload)
    return _public_task(task)


@router.get("", response_model=DiagnosisTaskListResponse)
async def list_tasks(
    status: str | None = None,
    task_type: str | None = None,
    limit: int = 20,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope_user_ids = await get_user_scope_ids(current_user, db)
    stmt = select(DiagnosisTask).where(DiagnosisTask.user_id.in_(scope_user_ids))
    if status:
        stmt = stmt.where(DiagnosisTask.status == status)
    if task_type:
        stmt = stmt.where(DiagnosisTask.task_type == task_type)
    stmt = stmt.order_by(desc(DiagnosisTask.created_at)).limit(max(1, min(limit, 100)))
    rows = (await db.execute(stmt)).scalars().all()
    return DiagnosisTaskListResponse(items=[_public_task(row) for row in rows])


@router.get("/{task_id}", response_model=DiagnosisTaskResponse)
async def get_task(
    task_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope_user_ids = await get_user_scope_ids(current_user, db)
    task = (
        await db.execute(
            select(DiagnosisTask).where(
                DiagnosisTask.task_id == task_id,
                DiagnosisTask.user_id.in_(scope_user_ids),
            )
        )
    ).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="诊断任务不存在")
    return _public_task(task)
