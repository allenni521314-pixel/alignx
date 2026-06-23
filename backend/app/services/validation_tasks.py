"""Validation task service."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import ValidationTask
from app.schemas import ValidationTaskCreate, ValidationTaskUpdate, ValidationTaskResponse


async def create_task(req: ValidationTaskCreate, db: AsyncSession) -> ValidationTaskResponse:
    task = ValidationTask(
        user_id="default",
        asin=req.asin,
        proposition_code=req.proposition_code,
        proposition_name=req.proposition_name,
        source_module=req.source_module,
        source_record_id=req.source_record_id,
        hypothesis_text=req.hypothesis_text,
        evidence_snapshot=req.evidence_snapshot,
        controlled_variable=req.controlled_variable,
        forbidden_simultaneous_changes=req.forbidden_simultaneous_changes,
        validation_period=req.validation_period,
        success_criteria=req.success_criteria,
        failure_criteria=req.failure_criteria,
    )
    db.add(task)
    await db.flush()
    return ValidationTaskResponse.model_validate(task, from_attributes=True)


async def list_tasks(asin: str | None, page: int, page_size: int, db: AsyncSession) -> dict:
    offset = (page - 1) * page_size
    q = select(ValidationTask).order_by(desc(ValidationTask.created_at))
    if asin:
        q = q.where(ValidationTask.asin == asin)
    q = q.offset(offset).limit(page_size)
    result = await db.execute(q)
    items = [ValidationTaskResponse.model_validate(r, from_attributes=True) for r in result.scalars().all()]
    count_q = select(ValidationTask)
    if asin:
        count_q = count_q.where(ValidationTask.asin == asin)
    total = len((await db.execute(count_q)).scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_task(task_id: str, db: AsyncSession) -> ValidationTaskResponse | None:
    result = await db.execute(select(ValidationTask).where(ValidationTask.id == task_id))
    task = result.scalar_one_or_none()
    return ValidationTaskResponse.model_validate(task, from_attributes=True) if task else None


async def update_task(task_id: str, req: ValidationTaskUpdate, db: AsyncSession) -> ValidationTaskResponse | None:
    result = await db.execute(select(ValidationTask).where(ValidationTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        return None
    if req.execution_status is not None:
        task.execution_status = req.execution_status
    if req.result_status is not None:
        task.result_status = req.result_status
    if req.next_action is not None:
        task.next_action = req.next_action
    await db.flush()
    return ValidationTaskResponse.model_validate(task, from_attributes=True)
