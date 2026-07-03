from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from schemas.asin_business_profile import (
    AsinProfileDetailResponse,
    IntentDecisionListResponse,
    IntentDecisionResponse,
    IntentDecisionRunRequest,
)
from schemas.auth import UserResponse
from services.asin_business_profile import DEFAULT_STORE_ID, AsinBusinessProfileService


router = APIRouter(prefix="/api/asins", tags=["asin-intent-engine"])


@router.post("/{asin}/intent-decisions/run", response_model=IntentDecisionResponse)
async def run_intent_decision(
    asin: str,
    data: IntentDecisionRunRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    try:
        return await service.run_intent_decision(seller_id=str(current_user.id), asin=asin, data=data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{asin}/intent-decisions", response_model=IntentDecisionListResponse)
async def list_intent_decisions(
    asin: str,
    store_id: str = DEFAULT_STORE_ID,
    marketplace: str = "US",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    return await service.list_intent_decisions(
        seller_id=str(current_user.id),
        asin=asin,
        store_id=store_id or DEFAULT_STORE_ID,
        marketplace=marketplace or "US",
        skip=skip,
        limit=limit,
    )


@router.get("/{asin}/profile", response_model=AsinProfileDetailResponse)
async def get_asin_profile(
    asin: str,
    store_id: str = DEFAULT_STORE_ID,
    marketplace: str = "US",
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    return await service.get_asin_profile_detail(
        seller_id=str(current_user.id),
        asin=asin,
        store_id=store_id or DEFAULT_STORE_ID,
        marketplace=marketplace or "US",
    )
