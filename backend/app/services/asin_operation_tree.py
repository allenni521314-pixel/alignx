from __future__ import annotations

"""ASIN operation tree and closed-loop audit service."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AiCallLog,
    AsinOperationProfile,
    CaptureJob,
    ConversionDiagnosis,
    ExecutionRecord,
    ListingSnapshot,
    Proposition,
    ValidationResult,
    ValidationTask,
)


async def list_operation_profiles(db: AsyncSession, limit: int = 50) -> list[dict]:
    q = select(AsinOperationProfile).order_by(AsinOperationProfile.updated_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "asin": row.asin,
            "marketplace": row.marketplace,
            "product_title": row.product_title,
            "lifecycle_stage": row.lifecycle_stage,
            "total_validation_count": row.total_validation_count,
            "effective_count": row.effective_count,
            "ineffective_count": row.ineffective_count,
            "interfered_count": row.interfered_count,
            "insufficient_data_count": row.insufficient_data_count,
            "current_main_problem": row.current_main_problem,
            "next_recommended_proposition": row.next_recommended_proposition,
            "updated_at": str(row.updated_at),
        }
        for row in rows
    ]


async def build_closed_loop_audit(db: AsyncSession, asin: str = "") -> dict:
    result = {"asin": asin, "stages": {}}

    result["stages"]["propositions_total"] = (await db.execute(select(func.count(Proposition.id)))).scalar()

    tasks_q = select(ValidationTask)
    if asin:
        tasks_q = tasks_q.where(ValidationTask.asin == asin)
    tasks = (await db.execute(tasks_q.order_by(ValidationTask.created_at.desc()).limit(20))).scalars().all()
    result["stages"]["tasks"] = [
        {
            "id": task.id,
            "asin": task.asin,
            "proposition_code": task.proposition_code,
            "hypothesis_text": task.hypothesis_text,
            "execution_status": task.execution_status,
            "result_status": task.result_status,
        }
        for task in tasks
    ]

    executions_q = select(ExecutionRecord)
    if asin:
        executions_q = executions_q.where(ExecutionRecord.asin == asin)
    executions = (await db.execute(executions_q.order_by(ExecutionRecord.executed_at.desc()).limit(20))).scalars().all()
    result["stages"]["executions"] = [
        {
            "id": item.id,
            "asin": item.asin,
            "action_summary": item.action_summary,
            "cost_amount": item.cost_amount,
            "executed_at": str(item.executed_at),
        }
        for item in executions
    ]

    results_q = select(ValidationResult)
    if asin:
        results_q = results_q.where(ValidationResult.asin == asin)
    validation_results = (await db.execute(results_q.order_by(ValidationResult.created_at.desc()).limit(20))).scalars().all()
    result["stages"]["results"] = [
        {
            "id": item.id,
            "asin": item.asin,
            "final_result_status": item.final_result_status,
            "attribution_conclusion": item.attribution_conclusion,
        }
        for item in validation_results
    ]

    if asin:
        profile = (
            await db.execute(
                select(AsinOperationProfile).where(AsinOperationProfile.asin == asin)
            )
        ).scalar_one_or_none()
        if profile:
            result["stages"]["profile"] = {
                "asin": profile.asin,
                "marketplace": profile.marketplace,
                "effective_count": profile.effective_count,
                "ineffective_count": profile.ineffective_count,
                "current_main_problem": profile.current_main_problem,
            }

    result["loop_health"] = {
        "has_propositions": result["stages"]["propositions_total"] > 0,
        "has_tasks": len(result["stages"]["tasks"]) > 0,
        "has_executions": len(result["stages"]["executions"]) > 0,
        "has_results": len(result["stages"]["results"]) > 0,
        "profile_synced": "profile" in result["stages"],
        "loop_complete": len(result["stages"]["tasks"]) > 0 and len(result["stages"]["results"]) > 0,
    }
    result["orphan_check"] = await build_orphan_audit(db, asin=asin)
    return result


async def build_orphan_audit(db: AsyncSession, asin: str = "") -> dict:
    checks = {
        "listing_snapshots_without_capture_job": await _listing_snapshots_without_capture_job(db, asin),
        "conversion_diagnoses_without_validation_task": await _conversion_diagnoses_without_validation_task(db, asin),
        "execution_records_without_validation_task": await _execution_records_without_validation_task(db, asin),
        "validation_results_without_validation_task": await _validation_results_without_validation_task(db, asin),
        "validation_tasks_without_asin_profile": await _validation_tasks_without_asin_profile(db, asin),
        "ai_calls_without_trace": await _ai_calls_without_trace(db, asin),
    }
    total = sum(item["count"] for item in checks.values())
    return {
        "asin": asin,
        "total": total,
        "status": "pass" if total == 0 else "fail",
        "checks": checks,
    }


async def _listing_snapshots_without_capture_job(db: AsyncSession, asin: str) -> dict:
    q = (
        select(ListingSnapshot.id, ListingSnapshot.asin, ListingSnapshot.capture_job_id)
        .outerjoin(CaptureJob, ListingSnapshot.capture_job_id == CaptureJob.id)
        .where(CaptureJob.id.is_(None))
    )
    if asin:
        q = q.where(ListingSnapshot.asin == asin)
    rows = (await db.execute(q.limit(50))).all()
    return _audit_item(rows, ["id", "asin", "capture_job_id"])


async def _conversion_diagnoses_without_validation_task(db: AsyncSession, asin: str) -> dict:
    q = (
        select(ConversionDiagnosis.id, ConversionDiagnosis.asin, ConversionDiagnosis.created_at)
        .outerjoin(
            ValidationTask,
            (ValidationTask.source_module == "conversion_diagnosis")
            & (ValidationTask.source_record_id == ConversionDiagnosis.id),
        )
        .where(ValidationTask.id.is_(None))
    )
    if asin:
        q = q.where(ConversionDiagnosis.asin == asin)
    rows = (await db.execute(q.limit(50))).all()
    return _audit_item(rows, ["id", "asin", "created_at"])


async def _execution_records_without_validation_task(db: AsyncSession, asin: str) -> dict:
    q = (
        select(ExecutionRecord.id, ExecutionRecord.asin, ExecutionRecord.validation_task_id)
        .outerjoin(ValidationTask, ExecutionRecord.validation_task_id == ValidationTask.id)
        .where(ValidationTask.id.is_(None))
    )
    if asin:
        q = q.where(ExecutionRecord.asin == asin)
    rows = (await db.execute(q.limit(50))).all()
    return _audit_item(rows, ["id", "asin", "validation_task_id"])


async def _validation_results_without_validation_task(db: AsyncSession, asin: str) -> dict:
    q = (
        select(ValidationResult.id, ValidationResult.asin, ValidationResult.validation_task_id)
        .outerjoin(ValidationTask, ValidationResult.validation_task_id == ValidationTask.id)
        .where(ValidationTask.id.is_(None))
    )
    if asin:
        q = q.where(ValidationResult.asin == asin)
    rows = (await db.execute(q.limit(50))).all()
    return _audit_item(rows, ["id", "asin", "validation_task_id"])


async def _validation_tasks_without_asin_profile(db: AsyncSession, asin: str) -> dict:
    q = (
        select(ValidationTask.id, ValidationTask.asin, ValidationTask.proposition_code)
        .outerjoin(
            AsinOperationProfile,
            (AsinOperationProfile.user_id == ValidationTask.user_id)
            & (AsinOperationProfile.asin == ValidationTask.asin),
        )
        .where(AsinOperationProfile.id.is_(None))
    )
    if asin:
        q = q.where(ValidationTask.asin == asin)
    rows = (await db.execute(q.limit(50))).all()
    return _audit_item(rows, ["id", "asin", "proposition_code"])


async def _ai_calls_without_trace(db: AsyncSession, asin: str) -> dict:
    q = select(AiCallLog.id, AiCallLog.asin, AiCallLog.module_name).where(
        (AiCallLog.input_payload.is_(None)) | (AiCallLog.ai_trace.is_(None))
    )
    if asin:
        q = q.where(AiCallLog.asin == asin)
    rows = (await db.execute(q.limit(50))).all()
    return _audit_item(rows, ["id", "asin", "module_name"])


def _audit_item(rows, keys: list[str]) -> dict:
    samples = []
    for row in rows:
        values = tuple(row)
        samples.append({
            key: str(values[index]) if values[index] is not None else None
            for index, key in enumerate(keys)
        })
    return {"count": len(samples), "samples": samples}
