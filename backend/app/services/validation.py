from __future__ import annotations
"""Execution records + validation results + ASIN profiles — service stubs."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import ExecutionRecord, ValidationResult, AsinOperationProfile
from app.schemas import (
    ExecutionRecordCreate, ExecutionRecordResponse,
    ValidationResultCreate, ValidationResultResponse,
    AsinOperationProfileResponse,
)


# ── Execution Records ──────────────────────────────

from app.constants import DEFAULT_USER_ID


async def create_execution(req: ExecutionRecordCreate, db: AsyncSession, user_id: str | None = None) -> ExecutionRecordResponse:
    uid = user_id or DEFAULT_USER_ID
    rec = ExecutionRecord(**req.model_dump(), user_id=uid)
    db.add(rec)
    await db.flush()
    return ExecutionRecordResponse.model_validate(rec, from_attributes=True)


async def list_executions(asin: str | None, task_id: str | None, page: int, page_size: int, db: AsyncSession) -> dict:
    offset = (page - 1) * page_size
    q = select(ExecutionRecord).order_by(desc(ExecutionRecord.created_at))
    if asin:
        q = q.where(ExecutionRecord.asin == asin)
    if task_id:
        q = q.where(ExecutionRecord.validation_task_id == task_id)
    q = q.offset(offset).limit(page_size)
    result = await db.execute(q)
    items = [ExecutionRecordResponse.model_validate(r, from_attributes=True) for r in result.scalars().all()]
    return {"items": items, "total": len(items), "page": page, "page_size": page_size}


# ── Validation Results ─────────────────────────────

async def create_result(req: ValidationResultCreate, db: AsyncSession, user_id: str | None = None) -> ValidationResultResponse:
    uid = user_id or DEFAULT_USER_ID
    rec = ValidationResult(**req.model_dump(), user_id=uid)
    db.add(rec)
    await db.flush()

    # Update linked validation task
    task_result = await db.execute(select(ValidationTask).where(ValidationTask.id == req.validation_task_id))
    task = task_result.scalar_one_or_none()
    if task:
        task.execution_status = "completed"
        task.result_status = req.final_result_status
        await db.flush()

    # Rebuild ASIN profile
    await sync_profile(req.asin, db)

    return ValidationResultResponse.model_validate(rec, from_attributes=True)


async def list_results(asin: str | None, page: int, page_size: int, db: AsyncSession) -> dict:
    offset = (page - 1) * page_size
    q = select(ValidationResult).order_by(desc(ValidationResult.created_at))
    if asin:
        q = q.where(ValidationResult.asin == asin)
    q = q.offset(offset).limit(page_size)
    result = await db.execute(q)
    items = [ValidationResultResponse.model_validate(r, from_attributes=True) for r in result.scalars().all()]
    return {"items": items, "total": len(items), "page": page, "page_size": page_size}


# ── ASIN Profiles ──────────────────────────────────

async def list_profiles(page: int, page_size: int, db: AsyncSession, user_id: str | None = None) -> dict:
    offset = (page - 1) * page_size
    q = select(AsinOperationProfile).order_by(desc(AsinOperationProfile.updated_at)).offset(offset).limit(page_size)
    result = await db.execute(q)
    items = [AsinOperationProfileResponse.model_validate(r, from_attributes=True) for r in result.scalars().all()]
    count_q = select(AsinOperationProfile)
    total = len((await db.execute(count_q)).scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_profile(asin: str, db: AsyncSession) -> AsinOperationProfileResponse | None:
    result = await db.execute(select(AsinOperationProfile).where(AsinOperationProfile.asin == asin))
    profile = result.scalar_one_or_none()
    return AsinOperationProfileResponse.model_validate(profile, from_attributes=True) if profile else None


async def sync_profile(asin: str, db: AsyncSession) -> AsinOperationProfileResponse:
    """Rebuild ASIN profile from validation history + latest diagnosis."""
    from app.models import ConversionDiagnosis

    # Count validation results
    vq = select(ValidationResult).where(ValidationResult.asin == asin)
    results = (await db.execute(vq)).scalars().all()

    effective = sum(1 for r in results if r.final_result_status == "effective")
    ineffective = sum(1 for r in results if r.final_result_status == "ineffective")
    interfered = sum(1 for r in results if r.final_result_status == "interfered")
    insufficient = sum(1 for r in results if r.final_result_status == "insufficient_data")

    # Latest diagnosis
    dq = select(ConversionDiagnosis).where(
        ConversionDiagnosis.asin == asin
    ).order_by(desc(ConversionDiagnosis.created_at)).limit(1)
    latest_diag = (await db.execute(dq)).scalar_one_or_none()

    # Build learning summary
    learning_parts = []
    if effective > 0:
        learning_parts.append(f"{effective}次有效验证")
    if ineffective > 0:
        learning_parts.append(f"{ineffective}次无效验证")

    # Upsert
    existing = await db.execute(select(AsinOperationProfile).where(AsinOperationProfile.asin == asin))
    profile = existing.scalar_one_or_none()

    if not profile:
        profile = AsinOperationProfile(
            asin=asin,
            total_validation_count=len(results),
            effective_count=effective, ineffective_count=ineffective,
            interfered_count=interfered, insufficient_data_count=insufficient,
            current_main_problem=latest_diag.biggest_breakpoint if latest_diag else None,
            next_recommended_proposition=latest_diag.priority_action if latest_diag else None,
            asin_learning_summary="；".join(learning_parts) if learning_parts else None,
        )
        db.add(profile)
    else:
        profile.total_validation_count = len(results)
        profile.effective_count = effective
        profile.ineffective_count = ineffective
        profile.interfered_count = interfered
        profile.insufficient_data_count = insufficient
        if latest_diag:
            profile.current_main_problem = latest_diag.biggest_breakpoint
            profile.next_recommended_proposition = latest_diag.priority_action
        profile.asin_learning_summary = "；".join(learning_parts) if learning_parts else None

    await db.flush()
    return AsinOperationProfileResponse.model_validate(profile, from_attributes=True)
