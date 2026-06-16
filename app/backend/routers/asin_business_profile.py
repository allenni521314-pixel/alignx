from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user, get_user_scope_ids
from schemas.asin_business_profile import (
    AiDecisionTraceCreate,
    AiDecisionTraceListResponse,
    AsinModuleViewResponse,
    AsinProfileListResponse,
    AsinProfileResponse,
    AsinProfileUpsert,
    DailySnapshotCreate,
    DailySnapshotListResponse,
    DailySnapshotResponse,
    DemoImportResponse,
    ExecutionLogCreate,
    ExecutionLogListResponse,
    MetricDictionaryResponse,
    ReportUploadCreate,
    ValidationTaskCreate,
    ValidationTaskResponse,
)
from schemas.auth import UserResponse
from services.asin_business_profile import (
    DEFAULT_STORE_ID,
    AsinBusinessProfileService,
    normalize_asin,
    normalize_marketplace,
)

router = APIRouter(prefix="/api/v1/asin-business-profiles", tags=["asin-business-profiles"])


@router.get("/metrics", response_model=list[MetricDictionaryResponse])
async def list_metric_dictionary(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    return await service.list_metrics()


@router.post("/reports")
async def create_report_upload(
    data: ReportUploadCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    report = await service.create_report_upload(seller_id=str(current_user.id), data=data.model_dump())
    return {
        "report_id": report.report_id,
        "parse_status": report.parse_status,
        "created_at": report.created_at,
    }


@router.post("/snapshots", response_model=DailySnapshotResponse, status_code=201)
async def upsert_daily_snapshot(
    data: DailySnapshotCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    try:
        return await service.upsert_daily_snapshot(seller_id=str(current_user.id), data=data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/snapshots", response_model=DailySnapshotListResponse)
async def list_daily_snapshots(
    asin: str = "",
    store_id: str = "",
    marketplace: str = "",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    return await service.list_daily_snapshots(
        seller_id=str(current_user.id),
        asin=asin or None,
        store_id=store_id or None,
        marketplace=marketplace or None,
        skip=skip,
        limit=limit,
    )


@router.post("/validations", response_model=ValidationTaskResponse, status_code=201)
async def create_validation_task(
    data: ValidationTaskCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    try:
        return await service.create_validation_task(seller_id=str(current_user.id), data=data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/validations")
async def list_validation_tasks(
    asin: str = "",
    store_id: str = "",
    marketplace: str = "",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    return await service.list_validation_tasks(
        seller_id=str(current_user.id),
        asin=asin or None,
        store_id=store_id or None,
        marketplace=marketplace or None,
        skip=skip,
        limit=limit,
    )


@router.get("/execution-logs", response_model=ExecutionLogListResponse)
async def list_execution_logs(
    asin: str = "",
    validation_id: str = "",
    store_id: str = "",
    marketplace: str = "",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    return await service.list_execution_logs(
        seller_id=str(current_user.id),
        asin=asin or None,
        validation_id=validation_id or None,
        store_id=store_id or None,
        marketplace=marketplace or None,
        skip=skip,
        limit=limit,
    )


@router.post("/execution-logs", status_code=201)
async def create_execution_log(
    data: ExecutionLogCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    try:
        log = await service.create_execution_log(seller_id=str(current_user.id), data=data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "execution_id": log.execution_id,
        "validation_id": log.validation_id,
        "asin": log.asin,
        "created_at": log.created_at,
    }


@router.get("/ai-decision-traces", response_model=AiDecisionTraceListResponse)
async def list_ai_decision_traces(
    asin: str = "",
    decision_type: str = "",
    related_validation_id: str = "",
    store_id: str = "",
    marketplace: str = "",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    return await service.list_ai_decision_traces(
        seller_id=str(current_user.id),
        asin=asin or None,
        decision_type=decision_type or None,
        related_validation_id=related_validation_id or None,
        store_id=store_id or None,
        marketplace=marketplace or None,
        skip=skip,
        limit=limit,
    )


@router.post("/ai-decision-traces", status_code=201)
async def create_ai_decision_trace(
    data: AiDecisionTraceCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    try:
        trace = await service.create_ai_decision_trace(seller_id=str(current_user.id), data=data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "decision_id": trace.decision_id,
        "decision_type": trace.decision_type,
        "asin": trace.asin,
        "created_at": trace.created_at,
    }


@router.post("/demo/import-from-listing-diagnosis", response_model=DemoImportResponse)
async def import_demo_from_listing_history(
    store_id: str = DEFAULT_STORE_ID,
    marketplace: str = "",
    limit: int = Query(20, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    scope_user_ids = await get_user_scope_ids(current_user, db)
    return await service.import_demo_from_listing_history(
        seller_id=str(current_user.id),
        source_seller_ids=scope_user_ids,
        store_id=store_id or DEFAULT_STORE_ID,
        marketplace=marketplace or None,
        limit=limit,
    )


@router.delete("/demo")
async def clear_demo_data(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    deleted = await service.clear_demo_data(seller_id=str(current_user.id))
    return {"deleted": deleted}


@router.get("/views/{view_type}", response_model=AsinModuleViewResponse)
async def get_module_view(
    view_type: str,
    asin: str = "",
    store_id: str = DEFAULT_STORE_ID,
    marketplace: str = "US",
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed = {
        "yesterday-report",
        "today-decision",
        "listing-diagnosis",
        "traffic-strategy",
        "execution-records",
        "effect-validation",
    }
    if view_type not in allowed:
        raise HTTPException(status_code=404, detail="暂无")
    service = AsinBusinessProfileService(db)
    return await service.get_module_view(
        seller_id=str(current_user.id),
        view_type=view_type,
        asin=asin or None,
        store_id=store_id or DEFAULT_STORE_ID,
        marketplace=marketplace or "US",
    )


@router.get("", response_model=AsinProfileListResponse)
async def list_profiles(
    store_id: str = "",
    marketplace: str = "",
    is_demo: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    return await service.list_profiles(
        seller_id=str(current_user.id),
        store_id=store_id or None,
        marketplace=marketplace or None,
        is_demo=is_demo,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=AsinProfileResponse, status_code=201)
async def upsert_profile(
    data: AsinProfileUpsert,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    try:
        return await service.upsert_profile(seller_id=str(current_user.id), data=data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{marketplace}/{asin}", response_model=AsinProfileResponse)
async def get_profile(
    marketplace: str,
    asin: str,
    store_id: str = DEFAULT_STORE_ID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AsinBusinessProfileService(db)
    profile = await service.get_profile(
        seller_id=str(current_user.id),
        store_id=store_id or DEFAULT_STORE_ID,
        marketplace=normalize_marketplace(marketplace),
        asin=normalize_asin(asin),
    )
    if not profile:
        raise HTTPException(status_code=404, detail="暂无")
    return profile
