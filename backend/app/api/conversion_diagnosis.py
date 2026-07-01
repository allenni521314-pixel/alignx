from __future__ import annotations
"""Conversion Diagnosis — in-sale ASIN listing conversion bottleneck analysis."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ConversionDiagnosisRequest, ConversionDiagnosisResponse, PaginatedResponse
from app.services.conversion_diagnosis import diagnose, list_diagnoses, get_diagnosis
from app.api.deps import get_current_user_id

router = APIRouter(prefix="/api/v1/conversion-diagnosis", tags=["conversion-diagnosis"])


@router.post("/analyze", response_model=ConversionDiagnosisResponse)
async def diagnose_endpoint(
    req: ConversionDiagnosisRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_current_user_id),
):
    try:
        return await diagnose(req, db, user_id=user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=PaginatedResponse)
async def list_conversion_diagnoses(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await list_diagnoses(page, page_size, db, user_id=user_id)


@router.get("/{diagnosis_id}", response_model=ConversionDiagnosisResponse)
async def get_conversion_diagnosis(
    diagnosis_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    diagnosis = await get_diagnosis(diagnosis_id, db, user_id=user_id)
    if not diagnosis:
        raise HTTPException(status_code=404, detail="Diagnosis not found")
    return diagnosis


@router.post("/multi-source")
async def multi_source_diagnosis(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_current_user_id),
):
    """Run 5-dimension diagnosis using ad data + listing + TOP20."""
    from app.core.multi_source_diagnosis import MultiSourceDiagnosisEngine

    engine = MultiSourceDiagnosisEngine()
    result = engine.diagnose(
        asin=payload.get("asin", ""),
        marketplace=payload.get("marketplace", "amazon.com"),
        ad_metrics=payload.get("ad_metrics"),
        listing_data=payload.get("listing_data"),
        ai_result=payload.get("ai_result"),
        top20_context=payload.get("top20_context"),
    )
    return result
