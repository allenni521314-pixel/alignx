"""Conversion Diagnosis — in-sale ASIN listing conversion bottleneck analysis."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ConversionDiagnosisRequest, ConversionDiagnosisResponse, PaginatedResponse

router = APIRouter(prefix="/api/v1/conversion-diagnosis", tags=["conversion-diagnosis"])


@router.post("/analyze", response_model=ConversionDiagnosisResponse)
async def diagnose_conversion(
    req: ConversionDiagnosisRequest,
    db: AsyncSession = Depends(get_db),
):
    """Input in-sale ASIN → position-by-position conversion diagnosis with ad metric mapping."""
    pass


@router.get("/history", response_model=PaginatedResponse)
async def list_conversion_diagnoses(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List historical conversion diagnoses."""
    pass


@router.get("/{diagnosis_id}", response_model=ConversionDiagnosisResponse)
async def get_conversion_diagnosis(
    diagnosis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single conversion diagnosis by ID."""
    pass
