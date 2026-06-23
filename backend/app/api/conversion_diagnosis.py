"""Conversion Diagnosis — in-sale ASIN listing conversion bottleneck analysis."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ConversionDiagnosisRequest, ConversionDiagnosisResponse, PaginatedResponse
from app.services.conversion_diagnosis import diagnose, list_diagnoses, get_diagnosis

router = APIRouter(prefix="/api/v1/conversion-diagnosis", tags=["conversion-diagnosis"])


@router.post("/analyze", response_model=ConversionDiagnosisResponse)
async def diagnose_conversion(
    req: ConversionDiagnosisRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await diagnose(req, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=PaginatedResponse)
async def list_conversion_diagnoses(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    return await list_diagnoses(page, page_size, db)


@router.get("/{diagnosis_id}", response_model=ConversionDiagnosisResponse)
async def get_conversion_diagnosis(
    diagnosis_id: str,
    db: AsyncSession = Depends(get_db),
):
    diagnosis = await get_diagnosis(diagnosis_id, db)
    if not diagnosis:
        raise HTTPException(status_code=404, detail="Diagnosis not found")
    return diagnosis
