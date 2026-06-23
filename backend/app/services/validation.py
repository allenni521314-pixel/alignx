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

async def create_execution(req: ExecutionRecordCreate, db: AsyncSession) -> ExecutionRecordResponse:
    rec = ExecutionRecord(**req.model_dump())
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

async def create_result(req: ValidationResultCreate, db: AsyncSession) -> ValidationResultResponse:
    res = ValidationResult(**req.model_dump())
    db.add(res)
    await db.flush()
    return ValidationResultResponse.model_validate(res, from_attributes=True)


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

async def list_profiles(page: int, page_size: int, db: AsyncSession) -> dict:
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
    """Rebuild ASIN profile from validation history."""
    # Count validation results
    vq = select(ValidationResult).where(ValidationResult.asin == asin)
    results = (await db.execute(vq)).scalars().all()

    effective = sum(1 for r in results if r.final_result_status == "effective")
    ineffective = sum(1 for r in results if r.final_result_status == "ineffective")
    interfered = sum(1 for r in results if r.final_result_status == "interfered")
    insufficient = sum(1 for r in results if r.final_result_status == "insufficient_data")

    # Upsert
    existing = await db.execute(select(AsinOperationProfile).where(AsinOperationProfile.asin == asin))
    profile = existing.scalar_one_or_none()

    if not profile:
        profile = AsinOperationProfile(
            user_id="default",
            asin=asin,
            total_validation_count=len(results),
            effective_count=effective,
            ineffective_count=ineffective,
            interfered_count=interfered,
            insufficient_data_count=insufficient,
        )
        db.add(profile)
    else:
        profile.total_validation_count = len(results)
        profile.effective_count = effective
        profile.ineffective_count = ineffective
        profile.interfered_count = interfered
        profile.insufficient_data_count = insufficient

    await db.flush()
    return AsinOperationProfileResponse.model_validate(profile, from_attributes=True)
