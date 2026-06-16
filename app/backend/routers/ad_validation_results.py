import json
import logging
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user, get_user_scope_ids
from schemas.auth import UserResponse
from services.ad_validation_results import AdValidationResultService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/ad_validation_results", tags=["ad_validation_results"])


class MetricChange(BaseModel):
    name: str
    before: Optional[str] = None
    after: Optional[str] = None
    change: Optional[str] = None


class AdValidationResultData(BaseModel):
    product_id: Optional[int] = None
    asin: Optional[str] = None
    verification_id: Optional[str] = None
    execution_id: Optional[str] = None
    original_issue: Optional[str] = None
    original_hypothesis: Optional[str] = None
    execution_action: Optional[str] = None
    validation_period: Optional[str] = None
    metrics_change: List[MetricChange] = []
    conclusion: str = "需继续观察"
    reason_explanation: Optional[str] = None
    next_suggestion: Optional[str] = None
    suggested_action: Optional[str] = None


class AdValidationResultUpdateData(BaseModel):
    product_id: Optional[int] = None
    asin: Optional[str] = None
    execution_id: Optional[str] = None
    original_issue: Optional[str] = None
    original_hypothesis: Optional[str] = None
    execution_action: Optional[str] = None
    validation_period: Optional[str] = None
    metrics_change: Optional[List[MetricChange]] = None
    conclusion: Optional[str] = None
    reason_explanation: Optional[str] = None
    next_suggestion: Optional[str] = None
    suggested_action: Optional[str] = None


class AdValidationResultResponse(BaseModel):
    id: int
    user_id: str
    product_id: Optional[int] = None
    asin: Optional[str] = None
    verification_id: str
    execution_id: Optional[str] = None
    original_issue: Optional[str] = None
    original_hypothesis: Optional[str] = None
    execution_action: Optional[str] = None
    validation_period: Optional[str] = None
    metrics_change: List[dict[str, Any]]
    conclusion: str
    reason_explanation: Optional[str] = None
    next_suggestion: Optional[str] = None
    suggested_action: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        data = {
            "id": obj.id,
            "user_id": obj.user_id,
            "product_id": obj.product_id,
            "asin": obj.asin,
            "verification_id": obj.verification_id,
            "execution_id": obj.execution_id,
            "original_issue": obj.original_issue,
            "original_hypothesis": obj.original_hypothesis,
            "execution_action": obj.execution_action,
            "validation_period": obj.validation_period,
            "metrics_change": json.loads(obj.metrics_change or "[]"),
            "conclusion": obj.conclusion,
            "reason_explanation": obj.reason_explanation,
            "next_suggestion": obj.next_suggestion,
            "suggested_action": obj.suggested_action,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }
        return super().model_validate(data, *args, **kwargs)


class AdValidationResultListResponse(BaseModel):
    items: List[AdValidationResultResponse]
    total: int
    skip: int
    limit: int


def _payload(data: AdValidationResultData | AdValidationResultUpdateData) -> dict[str, Any]:
    payload = data.model_dump()
    if "metrics_change" in payload and payload["metrics_change"] is not None:
        payload["metrics_change"] = json.dumps(payload["metrics_change"], ensure_ascii=False)
    return payload


@router.get("", response_model=AdValidationResultListResponse)
async def query_ad_validation_results(
    query: str = Query(None),
    sort: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=2000),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AdValidationResultService(db)
    try:
        query_dict = json.loads(query) if query else None
        scope_user_ids = await get_user_scope_ids(current_user, db)
        return await service.get_list(skip=skip, limit=limit, query_dict=query_dict, sort=sort, user_id=scope_user_ids)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid query JSON format")
    except Exception as e:
        logger.error("Error querying ad_validation_results: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=AdValidationResultResponse, status_code=201)
async def create_ad_validation_result(
    data: AdValidationResultData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AdValidationResultService(db)
    payload = _payload(data)
    if not payload.get("verification_id"):
        payload["verification_id"] = f"VERIFY-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    try:
        return await service.create(payload, user_id=str(current_user.id))
    except Exception as e:
        logger.error("Error creating ad_validation_result: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/{id}", response_model=AdValidationResultResponse)
async def update_ad_validation_result(
    id: int,
    data: AdValidationResultUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AdValidationResultService(db)
    scope_user_ids = await get_user_scope_ids(current_user, db)
    update_dict = {k: v for k, v in _payload(data).items() if v is not None}
    result = await service.update(id, update_dict, user_id=scope_user_ids)
    if not result:
        raise HTTPException(status_code=404, detail="Ad validation result not found")
    return result


@router.delete("/{id}")
async def delete_ad_validation_result(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AdValidationResultService(db)
    scope_user_ids = await get_user_scope_ids(current_user, db)
    success = await service.delete(id, user_id=scope_user_ids)
    if not success:
        raise HTTPException(status_code=404, detail="Ad validation result not found")
    return {"message": "Ad validation result deleted successfully", "id": id}
