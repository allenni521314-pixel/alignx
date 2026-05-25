"""
Unified Judgment System Router.

This is a backend foundation API for internal AlignX modules. It is not intended
to become a first-level frontend navigation item. Business pages should call it
or consume its output through their own workflows.
"""

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from schemas.auth import UserResponse
from services.judgment_feedback_rounds import JudgmentFeedbackRoundService
from services.judgment_system import JudgmentSystemService

router = APIRouter(prefix="/api/v1/judgment-system", tags=["judgment-system"])


class JudgmentListingInput(BaseModel):
    title: str = ""
    bullet_points: str = ""
    description: str = ""
    a_plus_content: str = ""
    backend_keywords: str = ""
    main_image_description: str = ""
    category: str = ""
    price: str = ""
    brand: str = ""
    marketplace: str = "US"
    asin: str = ""
    rating: str = ""
    review_count: str = ""
    bsr_rank: str = ""
    image_count: str = ""
    has_video: bool = False
    has_a_plus: bool = False


class UnifiedJudgmentRequest(BaseModel):
    listing: JudgmentListingInput
    diagnosis_data: dict[str, Any] = {}
    precision_context: dict[str, Any] = {}
    run_causal: bool = True


class UnifiedJudgmentResponse(BaseModel):
    version: str
    scope: str
    overall_judgment_score: float
    alignment_scores: dict[str, float]
    sections: dict[str, Any]
    data_integrity: dict[str, Any]
    diagnosis_confidence: dict[str, Any]
    legacy_bridge: dict[str, Any]


class JudgmentFeedbackRoundInput(BaseModel):
    asin: str = ""
    marketplace: str = "US"
    listing_diagnosis_id: Optional[int] = None
    product_id: Optional[int] = None
    optimization_round: Optional[int] = None
    stage: str = "ad_validation"
    status: str = "planned"
    diagnosis_issue: str = ""
    judgment_basis: str = ""
    suggested_action: str = ""
    ad_validation_plan: dict[str, Any] = {}
    before_snapshot: dict[str, Any] = {}
    after_snapshot: dict[str, Any] = {}
    ad_result: dict[str, Any] = {}
    hit_status: str = ""
    miss_reason: str = ""
    next_iteration: str = ""
    confidence_before: Optional[float] = None
    confidence_after: Optional[float] = None
    executed_at: Optional[datetime] = None


class JudgmentFeedbackRoundUpdate(BaseModel):
    stage: Optional[str] = None
    status: Optional[str] = None
    diagnosis_issue: Optional[str] = None
    judgment_basis: Optional[str] = None
    suggested_action: Optional[str] = None
    ad_validation_plan: Optional[dict[str, Any]] = None
    before_snapshot: Optional[dict[str, Any]] = None
    after_snapshot: Optional[dict[str, Any]] = None
    ad_result: Optional[dict[str, Any]] = None
    hit_status: Optional[str] = None
    miss_reason: Optional[str] = None
    next_iteration: Optional[str] = None
    confidence_before: Optional[float] = None
    confidence_after: Optional[float] = None
    executed_at: Optional[datetime] = None


def _json_dumps(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def _json_loads(value: str | None) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}


def _feedback_round_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "asin": row.asin,
        "marketplace": row.marketplace,
        "listing_diagnosis_id": row.listing_diagnosis_id,
        "product_id": row.product_id,
        "optimization_round": row.optimization_round,
        "stage": row.stage,
        "status": row.status,
        "diagnosis_issue": row.diagnosis_issue,
        "judgment_basis": row.judgment_basis,
        "suggested_action": row.suggested_action,
        "ad_validation_plan": _json_loads(row.ad_validation_plan),
        "before_snapshot": _json_loads(row.before_snapshot),
        "after_snapshot": _json_loads(row.after_snapshot),
        "ad_result": _json_loads(row.ad_result),
        "hit_status": row.hit_status,
        "miss_reason": row.miss_reason,
        "next_iteration": row.next_iteration,
        "confidence_before": row.confidence_before,
        "confidence_after": row.confidence_after,
        "executed_at": row.executed_at.isoformat() if row.executed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _feedback_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = dict(data)
    for key in ("ad_validation_plan", "before_snapshot", "after_snapshot", "ad_result"):
        if key in payload:
            payload[key] = _json_dumps(payload[key])
    if payload.get("asin"):
        payload["asin"] = str(payload["asin"]).strip().upper()
    return payload


@router.post("/listing", response_model=UnifiedJudgmentResponse)
async def judge_listing(
    request: UnifiedJudgmentRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run the unified backend judgment layer for a Listing.

    Consolidates:
    - review semantic demand
    - COSMO semantic alignment
    - causal conversion judgment
    - precision/confidence scoring
    """
    if not request.listing.title and not request.listing.bullet_points:
        raise HTTPException(status_code=400, detail="请至少输入标题或五点描述")

    service = JudgmentSystemService(db)
    result = await service.judge_listing(
        listing=request.listing,
        diagnosis_data=request.diagnosis_data,
        user_id=str(current_user.id),
        context=request.precision_context,
        asin=request.listing.asin or None,
        run_causal=request.run_causal,
    )
    return result


@router.post("/listing/feedback-rounds")
async def create_feedback_round(
    request: JudgmentFeedbackRoundInput,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save one Listing optimization/ad-validation feedback round."""
    service = JudgmentFeedbackRoundService(db)
    data = request.model_dump(exclude_unset=True)
    row = await service.create(_feedback_payload(data), user_id=str(current_user.id))
    return _feedback_round_to_dict(row)


@router.get("/listing/feedback-rounds")
async def list_feedback_rounds(
    asin: str = "",
    listing_diagnosis_id: Optional[int] = None,
    product_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Read saved judgment feedback rounds for a Listing/ASIN/product."""
    service = JudgmentFeedbackRoundService(db)
    items, total = await service.list(
        user_id=str(current_user.id),
        asin=asin.strip().upper() or None,
        listing_diagnosis_id=listing_diagnosis_id,
        product_id=product_id,
        skip=skip,
        limit=limit,
    )
    return {"items": [_feedback_round_to_dict(item) for item in items], "total": total, "skip": skip, "limit": limit}


@router.get("/listing/learning-memory")
async def get_learning_memory(
    asin: str = "",
    product_id: Optional[int] = None,
    limit: int = 200,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate historical feedback rounds into reusable judgment memory."""
    service = JudgmentFeedbackRoundService(db)
    return await service.learning_memory(
        user_id=str(current_user.id),
        asin=asin.strip().upper() or None,
        product_id=product_id,
        limit=limit,
    )


@router.patch("/listing/feedback-rounds/{round_id}")
async def update_feedback_round(
    round_id: int,
    request: JudgmentFeedbackRoundUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update execution/ad result/next-iteration fields for a saved feedback round."""
    service = JudgmentFeedbackRoundService(db)
    row = await service.update(
        round_id,
        _feedback_payload(request.model_dump(exclude_unset=True)),
        user_id=str(current_user.id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="反馈记录不存在")
    return _feedback_round_to_dict(row)
