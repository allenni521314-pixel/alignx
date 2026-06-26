from __future__ import annotations
"""Validation task service."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import ValidationTask
from app.schemas import ValidationTaskCreate, ValidationTaskUpdate, ValidationTaskResponse
from app.services.audit_logs import record_audit_log
from app.services.access import require_user_id, user_scoped


async def create_task(req: ValidationTaskCreate, db: AsyncSession, user_id: str | None = None) -> ValidationTaskResponse:
    uid = require_user_id(user_id)
    evidence_snapshot = req.evidence_snapshot or await _default_evidence_snapshot(req, db, uid)
    task = ValidationTask(
        user_id=uid,
        asin=req.asin,
        proposition_code=req.proposition_code,
        proposition_name=req.proposition_name,
        source_module=req.source_module,
        source_record_id=req.source_record_id,
        hypothesis_text=req.hypothesis_text,
        evidence_snapshot=evidence_snapshot,
        controlled_variable=req.controlled_variable or _default_controlled(req.source_module),
        forbidden_simultaneous_changes=req.forbidden_simultaneous_changes,
        validation_period=req.validation_period or "7天",
        success_criteria=req.success_criteria or _default_success_criteria(req.source_module),
        failure_criteria=req.failure_criteria or "指标无显著变化或反向",
    )
    db.add(task)
    await db.flush()
    # Auto-create or update ASIN profile
    await _ensure_profile(db, req.asin, uid)
    return ValidationTaskResponse.model_validate(task, from_attributes=True)


async def list_tasks(asin: str | None, page: int, page_size: int, db: AsyncSession, user_id: str | None = None) -> dict:
    uid = require_user_id(user_id)
    offset = (page - 1) * page_size
    q = user_scoped(select(ValidationTask), ValidationTask, uid)
    q = q.order_by(desc(ValidationTask.created_at))
    if asin:
        q = q.where(ValidationTask.asin == asin)
    q = q.offset(offset).limit(page_size)
    result = await db.execute(q)
    items = [ValidationTaskResponse.model_validate(r, from_attributes=True) for r in result.scalars().all()]
    count_q = user_scoped(select(ValidationTask), ValidationTask, uid)
    if asin:
        count_q = count_q.where(ValidationTask.asin == asin)
    total = len((await db.execute(count_q)).scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_task(task_id: str, db: AsyncSession, user_id: str | None = None) -> ValidationTaskResponse | None:
    uid = require_user_id(user_id)
    q = user_scoped(select(ValidationTask), ValidationTask, uid)
    result = await db.execute(q.where(ValidationTask.id == task_id))
    task = result.scalar_one_or_none()
    return ValidationTaskResponse.model_validate(task, from_attributes=True) if task else None


async def update_task(task_id: str, req: ValidationTaskUpdate, db: AsyncSession, user_id: str | None = None) -> ValidationTaskResponse | None:
    uid = require_user_id(user_id)
    q = user_scoped(select(ValidationTask), ValidationTask, uid)
    result = await db.execute(q.where(ValidationTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        return None
    before = {
        "execution_status": task.execution_status,
        "result_status": task.result_status,
        "next_action": task.next_action,
    }
    if req.execution_status is not None:
        task.execution_status = req.execution_status
    if req.result_status is not None:
        task.result_status = req.result_status
    if req.next_action is not None:
        task.next_action = req.next_action
    await db.flush()
    after = {
        "execution_status": task.execution_status,
        "result_status": task.result_status,
        "next_action": task.next_action,
    }
    action = (
        "today_decision.start_validation"
        if req.audit_source == "today_decisions" and req.execution_status == "running"
        else "validation_task.update"
    )
    await record_audit_log(
        db=db,
        user_id=task.user_id,
        module_name="today_decisions" if req.audit_source == "today_decisions" else "validation_tasks",
        action=action,
        entity_type="validation_task",
        entity_id=task.id,
        asin=task.asin,
        source_type=req.audit_source,
        before=before,
        after=after,
    )
    return ValidationTaskResponse.model_validate(task, from_attributes=True)


def _default_controlled(source: str | None) -> str | None:
    mapping = {
        "competitor_analysis": "主图/标题/A+内容等Listing元素",
        "conversion_diagnosis": "标题/五点/图片/A+等Listing元素",
        "prelaunch_check": "上架素材（图片/文案）",
        "ad_strategy": "广告竞价/预算/关键词",
    }
    return mapping.get(source or "")


def _default_success_criteria(source: str | None) -> str | None:
    mapping = {
        "competitor_analysis": "CTR相对提升≥0.3%或CVR相对提升≥0.5%",
        "conversion_diagnosis": "CVR相对提升≥0.5%",
        "prelaunch_check": "Listing完整度达标且无合规风险",
        "ad_strategy": "ACoS降低≥5%或Impression提升≥15%",
    }
    return mapping.get(source or "")


async def _default_evidence_snapshot(req: ValidationTaskCreate, db: AsyncSession, user_id: str) -> dict:
    base = {
        "source_module": req.source_module,
        "source_record_id": req.source_record_id,
        "proposition_code": req.proposition_code,
        "proposition_name": req.proposition_name,
        "hypothesis_text": req.hypothesis_text,
    }

    if req.source_record_id and req.source_module == "competitor_analysis":
        from app.models import CompetitorAnalysisReport
        result = await db.execute(
            user_scoped(select(CompetitorAnalysisReport), CompetitorAnalysisReport, user_id)
            .where(CompetitorAnalysisReport.id == req.source_record_id)
        )
        report = result.scalar_one_or_none()
        if report:
            base.update({
                "overall_judgment": report.overall_judgment,
                "main_weaknesses": report.main_weaknesses,
                "attack_points": report.attack_points,
            })

    if req.source_record_id and req.source_module == "conversion_diagnosis":
        from app.models import ConversionDiagnosis
        result = await db.execute(
            user_scoped(select(ConversionDiagnosis), ConversionDiagnosis, user_id)
            .where(ConversionDiagnosis.id == req.source_record_id)
        )
        report = result.scalar_one_or_none()
        if report:
            base.update({
                "overall_conclusion": report.overall_conclusion,
                "biggest_breakpoint": report.biggest_breakpoint,
                "priority_position": report.priority_position,
                "priority_action": report.priority_action,
                "impacted_ad_metrics": report.impacted_ad_metrics,
            })

    if req.source_record_id and req.source_module == "prelaunch_check":
        from app.models import PrelaunchCheck
        result = await db.execute(
            user_scoped(select(PrelaunchCheck), PrelaunchCheck, user_id)
            .where(PrelaunchCheck.id == req.source_record_id)
        )
        report = result.scalar_one_or_none()
        if report:
            base.update({
                "admission_result": report.admission_result,
                "conclusion": report.conclusion,
                "next_action": report.next_action,
            })

    return {key: value for key, value in base.items() if value is not None}


async def _ensure_profile(db: AsyncSession, asin: str, user_id: str):
    """Get or create ASIN operation profile."""
    from sqlalchemy import select as sa_select
    from app.models import AsinOperationProfile
    from app.services.access import ensure_asin_record
    await ensure_asin_record(db, user_id=user_id, asin=asin, marketplace="amazon.com")
    result = await db.execute(
        sa_select(AsinOperationProfile).where(
            AsinOperationProfile.user_id == user_id,
            AsinOperationProfile.asin == asin,
            AsinOperationProfile.marketplace == "amazon.com",
        )
    )
    if not result.scalar_one_or_none():
        profile = AsinOperationProfile(asin=asin, marketplace="amazon.com", user_id=user_id)
        db.add(profile)
        await db.flush()
