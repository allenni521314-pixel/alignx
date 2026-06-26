from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.database import get_db
from app.schemas import ReportUploadConfirmRequest, ReportUploadStagingRequest, ReportUploadStagingResponse, PaginatedResponse
from app.services.report_uploads import confirm_staging_record, list_staging_records, stage_report_upload

router = APIRouter(prefix="/api/v1/report-uploads", tags=["report-uploads"])


@router.post("/staging", response_model=ReportUploadStagingResponse, status_code=201)
async def create_staging(
    req: ReportUploadStagingRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await stage_report_upload(req, db, user_id=user_id)


@router.get("/staging", response_model=PaginatedResponse)
async def list_staging(
    status: str | None = Query(None),
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await list_staging_records(status, page, page_size, db, user_id=user_id)


@router.post("/staging/{record_id}/confirm")
async def confirm_staging(
    record_id: str,
    req: ReportUploadConfirmRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        execution_record_id = await confirm_staging_record(record_id, req.validation_task_id, db, user_id=user_id)
        return {"execution_record_id": execution_record_id}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
