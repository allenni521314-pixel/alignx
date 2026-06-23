"""Pre-launch Check — listing material admission assessment."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import PrelaunchCheckRequest, PrelaunchCheckResponse, PaginatedResponse

router = APIRouter(prefix="/api/v1/prelaunch-check", tags=["prelaunch-check"])


@router.post("/analyze", response_model=PrelaunchCheckResponse)
async def analyze_prelaunch(
    req: PrelaunchCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    """Upload listing materials → AI position-by-position admission diagnosis."""
    pass


@router.get("/history", response_model=PaginatedResponse)
async def list_prelaunch_checks(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List historical pre-launch checks."""
    pass


@router.get("/{check_id}", response_model=PrelaunchCheckResponse)
async def get_prelaunch_check(
    check_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single pre-launch check by ID."""
    pass
