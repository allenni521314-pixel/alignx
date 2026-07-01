from __future__ import annotations
"""Internal admin API — proposition library, ASIN profiles, closed-loop audit."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user_id
from app.core.rules_registry import get_rules, update_rule_items
from app.services.access import require_admin_user
from app.services.asin_operation_tree import build_closed_loop_audit, build_orphan_audit, list_operation_profiles
from app.services.proposition_library import (
    ensure_proposition_library,
    list_proposition_categories,
    list_propositions as list_proposition_items,
    proposition_library_status,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/buyer-lang-translate")
async def buyer_lang_translate(
    input_data: dict,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_current_user_id),
):
    require_admin_user(user_id)
    from app.services.buyer_lang import translate_seller_to_buyer
    try:
        result = await translate_seller_to_buyer(input_data, db, user_id)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════
# Platform Rules Library
# ═══════════════════════════════════════════

@router.get("/rules")
async def list_rules(user_id: str | None = Depends(get_current_user_id)):
    require_admin_user(user_id)
    return get_rules()


@router.put("/rules/{rule_id}")
async def update_rules(rule_id: str, items: list[str], user_id: str | None = Depends(get_current_user_id)):
    require_admin_user(user_id)
    if not update_rule_items(rule_id, items):
        raise HTTPException(404, "Rule not found")
    return {"success": True}


# ═══════════════════════════════════════════
# Proposition Library
# ═══════════════════════════════════════════

@router.get("/propositions")
async def list_propositions(db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    require_admin_user(user_id)
    return await list_proposition_items(db)


@router.get("/proposition-categories")
async def list_proposition_category_items(db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    require_admin_user(user_id)
    return await list_proposition_categories(db)


@router.post("/propositions/ensure")
async def ensure_propositions(db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    require_admin_user(user_id)
    result = await ensure_proposition_library(db)
    await db.commit()
    return result


@router.get("/propositions/status")
async def get_proposition_status(db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    require_admin_user(user_id)
    return await proposition_library_status(db)


# ═══════════════════════════════════════════
# ASIN Profiles
# ═══════════════════════════════════════════

@router.get("/asin-profiles")
async def list_asin_profiles(db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    require_admin_user(user_id)
    return await list_operation_profiles(db)


# ═══════════════════════════════════════════
# Closed-Loop Audit
# ═══════════════════════════════════════════

@router.get("/audit")
async def audit_loop(asin: str = "", db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    require_admin_user(user_id)
    return await build_closed_loop_audit(db, asin=asin)


@router.get("/audit/orphans")
async def audit_orphans(asin: str = "", db: AsyncSession = Depends(get_db), user_id: str | None = Depends(get_current_user_id)):
    require_admin_user(user_id)
    return await build_orphan_audit(db, asin=asin)
