from __future__ import annotations
"""Execution records + validation results + ASIN profiles — service stubs."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import ExecutionRecord, ValidationResult, AsinOperationProfile, ValidationTask, Proposition
from app.config import get_settings
from app.schemas import (
    ExecutionRecordCreate, ExecutionRecordResponse,
    ValidationResultCreate, ValidationResultResponse,
    AsinOperationProfileResponse,
)
from app.services.audit_logs import record_audit_log
from app.services.access import TenantScope, ensure_asin_record, require_user_id, user_scoped


async def create_execution(req: ExecutionRecordCreate, db: AsyncSession, user_id: str | None = None) -> ExecutionRecordResponse:
    uid = require_user_id(user_id)
    if not req.validation_task_id:
        raise ValueError("Validation task is required")
    task = await TenantScope.require(db, uid).validation_task(req.validation_task_id)
    if not task:
        raise ValueError("Validation task not found")
    if req.asin != task.asin:
        raise ValueError("ASIN does not match validation task")

    limit = get_settings().validation_budget_limit
    if limit > 0 and req.cost_amount is not None and req.cost_amount > limit:
        raise ValueError(f"预算超过上限：{req.cost_amount} > {limit}")
    rec = ExecutionRecord(**req.model_dump(), user_id=task.user_id)
    db.add(rec)
    await db.flush()
    await record_audit_log(
        db=db,
        user_id=task.user_id,
        module_name="execution_records",
        action="execution_record.create",
        entity_type="execution_record",
        entity_id=rec.id,
        asin=rec.asin,
        before=None,
        after={
            "validation_task_id": rec.validation_task_id,
            "action_summary": rec.action_summary,
            "cost_amount": rec.cost_amount,
            "cost_type": rec.cost_type,
        },
    )
    return ExecutionRecordResponse.model_validate(rec, from_attributes=True)


async def list_executions(asin: str | None, task_id: str | None, page: int, page_size: int, db: AsyncSession, user_id: str | None = None) -> dict:
    uid = require_user_id(user_id)
    offset = (page - 1) * page_size
    q = user_scoped(select(ExecutionRecord), ExecutionRecord, uid)
    q = q.order_by(desc(ExecutionRecord.created_at))
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
    uid = require_user_id(user_id)
    task = await TenantScope.require(db, uid).validation_task(req.validation_task_id)
    if not task:
        raise ValueError("Validation task not found")
    if req.asin != task.asin:
        raise ValueError("ASIN does not match validation task")

    rec = ValidationResult(**req.model_dump(), user_id=task.user_id)
    db.add(rec)
    await db.flush()

    # Update linked validation task
    task.execution_status = "completed"
    task.result_status = req.final_result_status
    await db.flush()

    # Rebuild ASIN profile
    profile = await sync_profile(req.asin, db, user_id=task.user_id)

    # ── 3/4/5: Auto-attribution + next-step + scale-up signal ──
    status = req.final_result_status or ""
    prop = None
    if task:
        prop_q = select(Proposition).where(Proposition.proposition_code == task.proposition_code)
        prop = (await db.execute(prop_q)).scalar_one_or_none()

    # Auto-generate attribution if not provided
    attribution = req.attribution_conclusion
    if not attribution:
        if status == "effective":
            attribution = _attr_effective(task, prop)
        elif status == "ineffective":
            attribution = _attr_ineffective(task, prop, req)
        elif status == "interfered":
            attribution = "受干扰"
        elif status == "insufficient_data":
            attribution = "数据不足"

    if attribution and not req.attribution_conclusion:
        rec.attribution_conclusion = attribution
        await db.flush()

    # Generate next step
    label = _next_step_label(status)
    detail = _next_step(status, task, prop, profile)
    if detail:
        rec.notes = (rec.notes or "") + ("\n" if rec.notes else "") + detail
        await db.flush()

    # Scale-up signal: if 3+ effective on this ASIN, flag persisted profile.
    if profile.effective_count >= 3:
        profile_row = (
            await db.execute(
                select(AsinOperationProfile).where(
                    AsinOperationProfile.user_id == task.user_id,
                    AsinOperationProfile.asin == req.asin,
                    AsinOperationProfile.marketplace == "amazon.com",
                )
            )
        ).scalar_one_or_none()
        if profile_row:
            profile_success = list(profile_row.successful_propositions_json or [])
            if not any(s.get("scale_up") for s in profile_success):
                for s in profile_success:
                    s["scale_up"] = True
                profile_row.successful_propositions_json = profile_success
                await db.flush()

    resp = ValidationResultResponse.model_validate(rec, from_attributes=True)
    resp.next_step = label
    return resp


async def list_results(asin: str | None, page: int, page_size: int, db: AsyncSession, user_id: str | None = None) -> dict:
    uid = require_user_id(user_id)
    offset = (page - 1) * page_size
    q = user_scoped(select(ValidationResult), ValidationResult, uid)
    q = q.order_by(desc(ValidationResult.created_at))
    if asin:
        q = q.where(ValidationResult.asin == asin)
    q = q.offset(offset).limit(page_size)
    result = await db.execute(q)
    items = [ValidationResultResponse.model_validate(r, from_attributes=True) for r in result.scalars().all()]
    return {"items": items, "total": len(items), "page": page, "page_size": page_size}


# ── ASIN Profiles ──────────────────────────────────

async def list_profiles(page: int, page_size: int, db: AsyncSession, user_id: str | None = None) -> dict:
    uid = require_user_id(user_id)
    offset = (page - 1) * page_size
    q = user_scoped(select(AsinOperationProfile), AsinOperationProfile, uid)
    q = q.order_by(desc(AsinOperationProfile.updated_at)).offset(offset).limit(page_size)
    result = await db.execute(q)
    items = [AsinOperationProfileResponse.model_validate(r, from_attributes=True) for r in result.scalars().all()]
    count_q = user_scoped(select(AsinOperationProfile), AsinOperationProfile, uid)
    total = len((await db.execute(count_q)).scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_profile(asin: str, db: AsyncSession, user_id: str | None = None, marketplace: str = "amazon.com") -> AsinOperationProfileResponse | None:
    uid = require_user_id(user_id)
    q = user_scoped(select(AsinOperationProfile), AsinOperationProfile, uid)
    result = await db.execute(q.where(AsinOperationProfile.asin == asin, AsinOperationProfile.marketplace == marketplace))
    profile = result.scalar_one_or_none()
    return AsinOperationProfileResponse.model_validate(profile, from_attributes=True) if profile else None


async def sync_profile(asin: str, db: AsyncSession, user_id: str | None = None, marketplace: str = "amazon.com") -> AsinOperationProfileResponse:
    """Rebuild ASIN profile from validation history + latest diagnosis."""
    from app.models import ConversionDiagnosis

    uid = require_user_id(user_id)
    await ensure_asin_record(db, user_id=uid, asin=asin, marketplace=marketplace)

    # Count validation results
    vq = user_scoped(select(ValidationResult), ValidationResult, uid)
    vq = vq.where(ValidationResult.asin == asin)
    results = (await db.execute(vq)).scalars().all()

    effective = sum(1 for r in results if r.final_result_status == "effective")
    ineffective = sum(1 for r in results if r.final_result_status == "ineffective")
    interfered = sum(1 for r in results if r.final_result_status == "interfered")
    insufficient = sum(1 for r in results if r.final_result_status == "insufficient_data")

    # Latest diagnosis
    dq = user_scoped(select(ConversionDiagnosis), ConversionDiagnosis, uid)
    dq = dq.where(
        ConversionDiagnosis.asin == asin
    ).order_by(desc(ConversionDiagnosis.created_at)).limit(1)
    latest_diag = (await db.execute(dq)).scalar_one_or_none()

    # ── Build successful / failed / repeated-failure proposition lists ──
    from collections import defaultdict
    prop_stats: dict[str, dict] = defaultdict(lambda: {"effective": 0, "ineffective": 0, "interfered": 0, "dates": []})
    tasks_q = user_scoped(select(ValidationTask), ValidationTask, uid)
    tasks_q = tasks_q.where(ValidationTask.asin == asin)
    all_tasks = (await db.execute(tasks_q)).scalars().all()
    task_map = {t.id: t for t in all_tasks}
    prop_q = select(Proposition)
    all_props = (await db.execute(prop_q)).scalars().all()
    prop_name_map = {p.proposition_code: p.name for p in all_props if p.proposition_code}

    for r in results:
        t = task_map.get(r.validation_task_id)
        if not t:
            continue
        code = t.proposition_code
        status = r.final_result_status or "insufficient_data"
        if status in ("effective", "ineffective", "interfered"):
            prop_stats[code][status] += 1
            prop_stats[code]["dates"].append(r.created_at.strftime("%m-%d") if r.created_at else "")

    successful = []
    failed = []
    repeated_failures = []
    for code, stats in prop_stats.items():
        entry = {
            "code": code,
            "name": prop_name_map.get(code, code),
            "count": stats["effective"] + stats["ineffective"] + stats["interfered"],
            "effective": stats["effective"],
            "ineffective": stats["ineffective"],
            "interfered": stats["interfered"],
            "last_date": sorted(stats["dates"])[-1] if stats["dates"] else None,
        }
        if stats["effective"] > 0:
            successful.append(entry)
        if stats["ineffective"] > 0:
            failed.append(entry)
            if stats["ineffective"] >= 2:
                repeated_failures.append(entry)

    # Build learning summary
    learning_parts = []
    if effective > 0:
        learning_parts.append(f"{effective}次有效验证")
    if ineffective > 0:
        learning_parts.append(f"{ineffective}次无效验证")

    # Upsert
    existing = await db.execute(
        select(AsinOperationProfile).where(
            AsinOperationProfile.user_id == uid,
            AsinOperationProfile.asin == asin,
            AsinOperationProfile.marketplace == marketplace,
        )
    )
    profile = existing.scalar_one_or_none()

    if not profile:
        profile = AsinOperationProfile(
            asin=asin,
            marketplace=marketplace,
            user_id=uid,
            total_validation_count=len(results),
            effective_count=effective, ineffective_count=ineffective,
            interfered_count=interfered, insufficient_data_count=insufficient,
            current_main_problem=latest_diag.biggest_breakpoint if latest_diag else None,
            next_recommended_proposition=latest_diag.priority_action if latest_diag else None,
            asin_learning_summary="；".join(learning_parts) if learning_parts else None,
            successful_propositions_json=successful if successful else None,
            failed_propositions_json=failed if failed else None,
            repeated_failure_patterns_json=repeated_failures if repeated_failures else None,
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
        profile.successful_propositions_json = successful if successful else None
        profile.failed_propositions_json = failed if failed else None
        profile.repeated_failure_patterns_json = repeated_failures if repeated_failures else None

    await db.flush()
    return AsinOperationProfileResponse.model_validate(profile, from_attributes=True)


# ── 3/4/5 helpers: attribution + next-step ──────────────────

def _attr_effective(task, prop) -> str:
    """Auto-attribution for effective results."""
    what = "验证"
    if task:
        if task.controlled_variable:
            what = f"「{task.controlled_variable}」"
        if task.hypothesis_text:
            what = f"「{task.hypothesis_text[:40]}」"
    return f"{what}有效"


def _attr_ineffective(task, prop, req) -> str:
    """Auto-attribution for ineffective results."""
    variable = task.controlled_variable if task and task.controlled_variable else "验证"
    hypothesis = task.hypothesis_text[:60] if task and task.hypothesis_text else ""

    parts = [f"「{variable}」无效"]
    if hypothesis:
        parts.append(f"假设「{hypothesis}」无效")
    if prop and prop.next_proposition_if_failed:
        parts.append(f"下一命题：{prop.next_proposition_if_failed}")
    return "。".join(parts)


def _next_step(status: str, task, prop, profile) -> str | None:
    """Generate next-step action in natural language."""
    if status == "effective":
        return "下一步：加大投入"
    elif status == "ineffective":
        if prop and prop.next_proposition_if_failed:
            return f"下一步：{prop.next_proposition_if_failed}"
        return "下一步：换方向"
    elif status == "interfered":
        return "下一步：重新验证"
    elif status == "insufficient_data":
        return "下一步：继续观察"
    return None


def _next_step_label(status: str) -> str:
    """Short label for frontend display."""
    mapping = {
        "effective": "加大投入",
        "ineffective": "换方向",
        "interfered": "重新验证",
        "insufficient_data": "继续观察",
    }
    return mapping.get(status, "")
