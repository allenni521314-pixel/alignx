from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from schemas.asin_business_profile import AsinModuleViewResponse
from schemas.auth import UserResponse
from services.asin_business_profile import DEFAULT_STORE_ID, AsinBusinessProfileService


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/yesterday-report", response_model=AsinModuleViewResponse)
async def get_yesterday_report(
    store_id: str = DEFAULT_STORE_ID,
    marketplace: str = "US",
    date: date | None = None,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    return await service.get_module_view(
        seller_id=str(current_user.id),
        view_type="yesterday-report",
        store_id=store_id or DEFAULT_STORE_ID,
        marketplace=marketplace or "US",
    )


@router.get("/today-decision", response_model=AsinModuleViewResponse)
async def get_today_decision(
    store_id: str = DEFAULT_STORE_ID,
    marketplace: str = "US",
    date: date | None = None,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    return await service.get_module_view(
        seller_id=str(current_user.id),
        view_type="today-decision",
        store_id=store_id or DEFAULT_STORE_ID,
        marketplace=marketplace or "US",
    )
