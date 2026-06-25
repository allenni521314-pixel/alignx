from __future__ import annotations
"""Internal admin API — proposition library, ASIN profiles, closed-loop audit."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import AsinOperationProfile, Proposition, ValidationTask, ExecutionRecord, ValidationResult
from app.api.deps import get_current_user_id
from app.core.rules_registry import get_rules, update_rule_items

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/buyer-lang-translate")
async def buyer_lang_translate(
    input_data: dict,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_current_user_id),
):
    if user_id != "__admin__":
        raise HTTPException(403, "Admin only")
    from app.services.buyer_lang import translate_seller_to_buyer
    try:
        result = await translate_seller_to_buyer(input_data)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════
# Platform Rules Library
# ═══════════════════════════════════════════

@router.get("/rules")
async def list_rules(user_id: str | None = Depends(get_current_user_id)):
    if user_id != "__admin__":
        raise HTTPException(403, "Admin only")
    return get_rules()


@router.put("/rules/{rule_id}")
async def update_rules(rule_id: str, items: list[str], user_id: str | None = Depends(get_current_user_id)):
    if user_id != "__admin__":
        raise HTTPException(403, "Admin only")
    if not update_rule_items(rule_id, items):
        raise HTTPException(404, "Rule not found")
    return {"success": True}


# ═══════════════════════════════════════════
# Proposition Library
# ═══════════════════════════════════════════

@router.get("/propositions")
async def list_propositions(db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    if user_id != "__admin__":
        raise HTTPException(403, "Admin only")
    q = select(Proposition).order_by(Proposition.code)
    r = await db.execute(q)
    return [{"id": p.id, "code": p.code, "title": p.title, "description": p.description,
             "category": p.category, "hypothesis_template": p.hypothesis_template,
             "validation_method": p.validation_method} for p in r.scalars().all()]


# ═══════════════════════════════════════════
# ASIN Profiles
# ═══════════════════════════════════════════

@router.get("/asin-profiles")
async def list_asin_profiles(db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    if user_id != "__admin__":
        raise HTTPException(403, "Admin only")
    q = select(AsinOperationProfile).order_by(AsinOperationProfile.updated_at.desc()).limit(50)
    r = await db.execute(q)
    return [{"asin": p.asin, "product_title": p.product_title, "lifecycle_stage": p.lifecycle_stage,
             "total_validation_count": p.total_validation_count, "effective_count": p.effective_count,
             "ineffective_count": p.ineffective_count, "current_main_problem": p.current_main_problem,
             "next_recommended_proposition": p.next_recommended_proposition,
             "updated_at": str(p.updated_at)} for p in r.scalars().all()]


# ═══════════════════════════════════════════
# Closed-Loop Audit
# ═══════════════════════════════════════════

@router.get("/audit")
async def audit_loop(asin: str = "", db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    if user_id != "__admin__":
        raise HTTPException(403, "Admin only")

    result = {"asin": asin, "stages": {}}

    # Stage 1: Propositions matched
    q = select(func.count(Proposition.id))
    result["stages"]["propositions_total"] = (await db.execute(q)).scalar()

    # Stage 2: Validation tasks
    q = select(ValidationTask).where(ValidationTask.asin == asin) if asin else select(ValidationTask)
    tasks = (await db.execute(q.order_by(ValidationTask.created_at.desc()).limit(20))).scalars().all()
    result["stages"]["tasks"] = [{"id": t.id, "asin": t.asin, "proposition_code": t.proposition_code,
                                   "hypothesis_text": t.hypothesis_text, "execution_status": t.execution_status,
                                   "result_status": t.result_status} for t in tasks]

    # Stage 3: Execution records
    q = select(ExecutionRecord).where(ExecutionRecord.asin == asin) if asin else select(ExecutionRecord)
    execs = (await db.execute(q.order_by(ExecutionRecord.executed_at.desc()).limit(20))).scalars().all()
    result["stages"]["executions"] = [{"id": e.id, "asin": e.asin, "action_summary": e.action_summary,
                                        "cost_amount": e.cost_amount, "executed_at": str(e.executed_at)} for e in execs]

    # Stage 4: Validation results
    q = select(ValidationResult).where(ValidationResult.asin == asin) if asin else select(ValidationResult)
    vrs = (await db.execute(q.order_by(ValidationResult.created_at.desc()).limit(20))).scalars().all()
    result["stages"]["results"] = [{"id": v.id, "asin": v.asin, "final_result_status": v.final_result_status,
                                     "attribution_conclusion": v.attribution_conclusion} for v in vrs]

    # Stage 5: ASIN profile (final state)
    if asin:
        q = select(AsinOperationProfile).where(AsinOperationProfile.asin == asin)
        profile = (await db.execute(q)).scalar().first()
        if profile:
            result["stages"]["profile"] = {"asin": profile.asin, "effective_count": profile.effective_count,
                                            "ineffective_count": profile.ineffective_count,
                                            "current_main_problem": profile.current_main_problem}

    # Loop completeness check
    result["loop_health"] = {
        "has_propositions": result["stages"]["propositions_total"] > 0,
        "has_tasks": len(result["stages"]["tasks"]) > 0,
        "has_executions": len(result["stages"]["executions"]) > 0,
        "has_results": len(result["stages"]["results"]) > 0,
        "profile_synced": "profile" in result["stages"],
        "loop_complete": len(result["stages"]["tasks"]) > 0 and len(result["stages"]["results"]) > 0,
    }

    return result
