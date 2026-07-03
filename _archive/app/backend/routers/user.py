import json
from datetime import datetime, timezone
from typing import Optional

from core.database import get_db
from dependencies.auth import get_current_user, get_user_scope_ids
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from models.action_snapshots import ActionSnapshot
from models.ad_campaigns import Ad_campaigns
from models.ad_data import Ad_data
from models.ad_recommendations import Ad_recommendations
from models.asin_analyses import Asin_analyses
from models.asin_keyword_sales_validation import (
    AsinKeywordIntentScore,
    AsinKeywordRankSnapshot,
    AsinKeywordSalesValidationReport,
)
from models.batch_causal_tasks import BatchCausalTask
from models.causal_ab_comparison import CausalABComparison
from models.auth import User
from models.diagnosis_tasks import DiagnosisTask
from models.competitor_insights import Competitor_insights
from models.consumer_intent_results import Consumer_intent_results
from models.cosmo_results import Cosmo_results
from models.fetch_history import Fetch_history
from models.health_reports import Health_reports
from models.human_state_body import HumanStateBody
from models.judgment_feedback_rounds import JudgmentFeedbackRound
from models.keywords import Keywords
from models.listing_diagnoses import Listing_diagnoses
from models.listings import Listings
from models.optimization_timeline import OptimizationTimeline
from models.prelaunch_test_results import Prelaunch_test_results
from models.products import Products
from models.review_causal_validation import ReviewCausalValidation
from models.sales_metrics import Sales_metrics
from models.scrape_logs import Scrape_logs
from pydantic import BaseModel
from schemas.auth import UserResponse
from sqlalchemy import func, inspect, select
from services.user import UserService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/users", tags=["users"])


USER_DATA_TABLES = [
    ("products", Products),
    ("asin_analyses", Asin_analyses),
    ("listing_diagnoses", Listing_diagnoses),
    ("prelaunch_test_results", Prelaunch_test_results),
    ("action_snapshots", ActionSnapshot),
    ("asin_keyword_rank_snapshots", AsinKeywordRankSnapshot),
    ("asin_keyword_sales_validation_reports", AsinKeywordSalesValidationReport),
    ("asin_keyword_intent_scores", AsinKeywordIntentScore),
    ("listings", Listings),
    ("keywords", Keywords),
    ("ad_campaigns", Ad_campaigns),
    ("ad_data", Ad_data),
    ("ad_recommendations", Ad_recommendations),
    ("sales_metrics", Sales_metrics),
    ("health_reports", Health_reports),
    ("fetch_history", Fetch_history),
    ("cosmo_results", Cosmo_results),
    ("competitor_insights", Competitor_insights),
    ("consumer_intent_results", Consumer_intent_results),
    ("judgment_feedback_rounds", JudgmentFeedbackRound),
    ("causal_ab_comparisons", CausalABComparison),
    ("review_causal_validations", ReviewCausalValidation),
    ("batch_causal_tasks", BatchCausalTask),
    ("diagnosis_tasks", DiagnosisTask),
    ("human_state_bodies", HumanStateBody),
    ("scrape_logs", Scrape_logs),
    ("optimization_timeline", OptimizationTimeline),
]


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None


class DataDeletionRequest(BaseModel):
    reason: Optional[str] = None


def _serialize_model_row(row) -> dict:
    mapper = inspect(row.__class__)
    return {column.key: getattr(row, column.key) for column in mapper.columns}


async def _count_for_scope(db: AsyncSession, model, scope_ids: list[str]) -> int:
    if not hasattr(model, "user_id"):
        return 0
    result = await db.execute(select(func.count(model.id)).where(model.user_id.in_(scope_ids)))
    return int(result.scalar() or 0)


@router.get("/profile", response_model=UserResponse)
async def get_profile(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    profile = await UserService.get_user_profile(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
    return profile


@router.get("/account-status")
async def get_account_status(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return publish-ready account, plan, and usage status for the current email tenant."""
    scope_ids = await get_user_scope_ids(current_user, db)
    counts = {table_name: await _count_for_scope(db, model, scope_ids) for table_name, model in USER_DATA_TABLES}
    is_super_admin = current_user.role == "super_admin"
    plan = "enterprise" if is_super_admin else "trial"

    return {
        "account": {
            "id": current_user.id,
            "email": current_user.email,
            "role": current_user.role,
            "tenant_scope": "same_email",
            "scope_user_ids": scope_ids,
        },
        "plan": {
            "id": plan,
            "name": "企业版 / 超级管理员" if is_super_admin else "免费试用版",
            "status": "paid_active" if is_super_admin else "trial",
            "expires_at": "长期有效" if is_super_admin else None,
        },
        "usage": {
            "asin_analysis": {"used": counts.get("asin_analyses", 0), "total": "unlimited" if is_super_admin else 1},
            "listing_diagnosis": {
                "used": counts.get("listing_diagnoses", 0) + counts.get("prelaunch_test_results", 0),
                "total": "unlimited" if is_super_admin else 1,
            },
            "ad_validation": {"used": counts.get("ad_data", 0), "total": "unlimited" if is_super_admin else 0},
            "snapshots": {"used": counts.get("action_snapshots", 0), "total": "unlimited"},
        },
        "data_counts": counts,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/data-export")
async def export_my_data(
    limit_per_table: int = 1000,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export current email tenant data as JSON.

    This endpoint is intentionally scoped by normalized email aliases, so a
    user who logs in again with the same email can still export historical
    rows that were attached to an older auth id during beta.
    """
    limit = max(1, min(limit_per_table, 5000))
    scope_ids = await get_user_scope_ids(current_user, db)
    tables = {}
    for table_name, model in USER_DATA_TABLES:
        if not hasattr(model, "user_id"):
            continue
        query = select(model).where(model.user_id.in_(scope_ids)).order_by(model.id.desc()).limit(limit)
        rows = (await db.execute(query)).scalars().all()
        total = await _count_for_scope(db, model, scope_ids)
        tables[table_name] = {
            "total": total,
            "exported": len(rows),
            "truncated": total > len(rows),
            "rows": [_serialize_model_row(row) for row in rows],
        }

    return jsonable_encoder(
        {
            "export_version": "alignx-user-data-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "account": {
                "id": current_user.id,
                "email": current_user.email,
                "role": current_user.role,
                "tenant_scope": "same_email",
                "scope_user_ids": scope_ids,
            },
            "tables": tables,
        }
    )


@router.post("/data-deletion-request", status_code=status.HTTP_202_ACCEPTED)
async def request_data_deletion(
    payload: DataDeletionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a data deletion request without immediately deleting beta data."""
    scope_ids = await get_user_scope_ids(current_user, db)
    snapshot = ActionSnapshot(
        user_id=str(current_user.id),
        module_key="account_data",
        module_name="账号数据",
        action_key="data_deletion_request",
        action_name="用户数据删除申请",
        input_snapshot=json.dumps(
            {
                "email": current_user.email,
                "scope_user_ids": scope_ids,
                "reason": payload.reason or "",
            },
            ensure_ascii=False,
        ),
        output_snapshot=json.dumps(
            {
                "status": "pending_manual_review",
                "policy": "beta_requires_manual_review_before_physical_delete",
            },
            ensure_ascii=False,
        ),
        data_source="user_request",
        confidence="high",
        ai_called=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return {
        "status": "pending_manual_review",
        "request_id": snapshot.id,
        "message": "删除申请已记录。内测阶段为避免误删，需超级管理员复核后执行物理删除。",
    }


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update current user profile"""
    profile = await UserService.update_user_profile(db, current_user.id, profile_data.name)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
    return profile
