from __future__ import annotations
"""AlignX V1 — API router aggregation."""

from fastapi import APIRouter

from app.api.market_opportunity import router as market_opportunity_router
from app.api.competitor_analysis import router as competitor_analysis_router
from app.api.prelaunch_check import router as prelaunch_check_router
from app.api.conversion_diagnosis import router as conversion_diagnosis_router
from app.api.validation_tasks import router as validation_tasks_router
from app.api.execution_records import router as execution_records_router
from app.api.validation_results import router as validation_results_router
from app.api.asin_profiles import router as asin_profiles_router
from app.api.reports import router as reports_router
from app.api.lifecycle import router as lifecycle_router
from app.api.report_uploads import router as report_uploads_router
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(admin_router)

api_router.include_router(market_opportunity_router)
api_router.include_router(competitor_analysis_router)
api_router.include_router(prelaunch_check_router)
api_router.include_router(conversion_diagnosis_router)
api_router.include_router(validation_tasks_router)
api_router.include_router(execution_records_router)
api_router.include_router(validation_results_router)
api_router.include_router(asin_profiles_router)
api_router.include_router(reports_router)
api_router.include_router(lifecycle_router)
api_router.include_router(report_uploads_router)
