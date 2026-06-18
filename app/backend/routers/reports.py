from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from schemas.asin_business_profile import (
    ReportParseSummary,
    ReportUploadResponse,
    StagingRowListResponse,
    StagingRowResolveRequest,
    StagingRowResolveResponse,
)
from schemas.auth import UserResponse
from services.asin_business_profile import DEFAULT_STORE_ID, normalize_marketplace
from services.report_import import ReportImportService


reports_router = APIRouter(prefix="/api/reports", tags=["reports"])
reports_v1_router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


async def _upload_report(
    *,
    store_id: str,
    marketplace: str,
    report_type: str,
    date_range_start: Optional[date],
    date_range_end: Optional[date],
    file: UploadFile,
    current_user: UserResponse,
    db: AsyncSession,
) -> ReportUploadResponse:
    service = ReportImportService(db)
    content = await file.read()
    try:
        report = await service.create_upload(
            seller_id=str(current_user.id),
            store_id=store_id or DEFAULT_STORE_ID,
            marketplace=normalize_marketplace(marketplace),
            report_type=report_type,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            original_filename=file.filename or "report",
            content=content,
            uploaded_by=str(current_user.id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return report


async def _parse_report(
    *,
    report_id: str,
    current_user: UserResponse,
    db: AsyncSession,
) -> ReportParseSummary:
    service = ReportImportService(db)
    try:
        return await service.parse_report(seller_id=str(current_user.id), report_id=report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


async def _list_staging_rows(
    *,
    report_id: str,
    match_status: str,
    skip: int,
    limit: int,
    current_user: UserResponse,
    db: AsyncSession,
) -> StagingRowListResponse:
    service = ReportImportService(db)
    return await service.list_staging_rows(
        seller_id=str(current_user.id),
        report_id=report_id or None,
        match_status=match_status or None,
        skip=skip,
        limit=limit,
    )


async def _resolve_staging_rows(
    *,
    data: StagingRowResolveRequest,
    current_user: UserResponse,
    db: AsyncSession,
) -> StagingRowResolveResponse:
    service = ReportImportService(db)
    try:
        return await service.resolve_staging_rows(
            seller_id=str(current_user.id),
            report_id=data.report_id,
            action=data.action,
            asin=data.asin,
            staging_row_ids=data.staging_row_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


async def _match_summary(
    *,
    report_id: str,
    current_user: UserResponse,
    db: AsyncSession,
) -> ReportParseSummary:
    service = ReportImportService(db)
    try:
        return await service.get_match_summary(seller_id=str(current_user.id), report_id=report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


for item_router in (reports_router, reports_v1_router):

    @item_router.post("/upload", response_model=ReportUploadResponse)
    async def upload_report(
        store_id: str = Form(DEFAULT_STORE_ID),
        marketplace: str = Form("US"),
        report_type: str = Form(...),
        date_range_start: Optional[date] = Form(None),
        date_range_end: Optional[date] = Form(None),
        file: UploadFile = File(...),
        current_user: UserResponse = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await _upload_report(
            store_id=store_id,
            marketplace=marketplace,
            report_type=report_type,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            file=file,
            current_user=current_user,
            db=db,
        )

    @item_router.post("/{report_id}/parse", response_model=ReportParseSummary)
    async def parse_report(
        report_id: str,
        current_user: UserResponse = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await _parse_report(report_id=report_id, current_user=current_user, db=db)

    @item_router.get("/staging", response_model=StagingRowListResponse)
    async def list_staging_rows(
        report_id: str = "",
        match_status: str = "",
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=500),
        current_user: UserResponse = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await _list_staging_rows(
            report_id=report_id,
            match_status=match_status,
            skip=skip,
            limit=limit,
            current_user=current_user,
            db=db,
        )

    @item_router.post("/staging/resolve", response_model=StagingRowResolveResponse)
    async def resolve_staging_rows(
        data: StagingRowResolveRequest,
        current_user: UserResponse = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await _resolve_staging_rows(data=data, current_user=current_user, db=db)

    @item_router.get("/{report_id}/match-summary", response_model=ReportParseSummary)
    async def get_report_match_summary(
        report_id: str,
        current_user: UserResponse = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await _match_summary(report_id=report_id, current_user=current_user, db=db)

    @item_router.get("/{report_id}/unmatched-rows", response_model=StagingRowListResponse)
    async def get_unmatched_rows(
        report_id: str,
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=500),
        current_user: UserResponse = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        unresolved = await _list_staging_rows(
            report_id=report_id,
            match_status="Unresolved",
            skip=skip,
            limit=limit,
            current_user=current_user,
            db=db,
        )
        return unresolved

    @item_router.post("/{report_id}/resolve-asin-mapping", response_model=StagingRowResolveResponse)
    async def resolve_asin_mapping(
        report_id: str,
        data: StagingRowResolveRequest,
        current_user: UserResponse = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        payload = data.model_copy(update={"report_id": report_id})
        return await _resolve_staging_rows(data=payload, current_user=current_user, db=db)

    @item_router.post("/{report_id}/commit-resolved-rows", response_model=ReportParseSummary)
    async def commit_resolved_rows(
        report_id: str,
        current_user: UserResponse = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        return await _match_summary(report_id=report_id, current_user=current_user, db=db)


router = [reports_router, reports_v1_router]
