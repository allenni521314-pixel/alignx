"""Pre-launch Check — listing material admission assessment."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import PrelaunchCheckRequest, PrelaunchCheckResponse, PaginatedResponse
from app.services.prelaunch_check import analyze_prelaunch, list_checks, get_check

router = APIRouter(prefix="/api/v1/prelaunch-check", tags=["prelaunch-check"])


@router.post("/analyze", response_model=PrelaunchCheckResponse)
async def analyze_prelaunch_endpoint(
    req: PrelaunchCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await analyze_prelaunch(req, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=PaginatedResponse)
async def list_prelaunch_checks(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    return await list_checks(page, page_size, db)


@router.get("/{check_id}", response_model=PrelaunchCheckResponse)
async def get_prelaunch_check(
    check_id: str,
    db: AsyncSession = Depends(get_db),
):
    check = await get_check(check_id, db)
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    return check
