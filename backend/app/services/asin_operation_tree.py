from __future__ import annotations

"""ASIN operation tree and closed-loop audit service."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AsinOperationProfile, ExecutionRecord, Proposition, ValidationResult, ValidationTask


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
    return result
