from __future__ import annotations
"""Conversion Diagnosis — in-sale ASIN listing conversion bottleneck analysis."""

import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ConversionDiagnosisRequest, ConversionDiagnosisResponse, PaginatedResponse
from app.services.conversion_diagnosis import diagnose, list_diagnoses, get_diagnosis
from app.api.deps import get_current_user_id
from app.core.scraperapi import ScraperAPIProvider
from app.core.multi_source_diagnosis import MultiSourceDiagnosisEngine
from app.models import CaptureJob

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


# ── Multi-Source Diagnosis with Auto-Fetch ──────────────────────────

@router.post("/multi-source")
async def multi_source_diagnosis(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_current_user_id),
):
    """Run 5-dimension diagnosis with auto-fetched data sources.

    Minimal request: {"asin": "B0XXX", "marketplace": "amazon.com"}
    Auto-fetches listing (ScraperAPI), ad_metrics (DB), top20 (DB).
    Falls back to manually supplied data if auto-fetch fails.
    """
    asin = (payload.get("asin") or "").strip()
    marketplace = payload.get("marketplace", "amazon.com")
    manual_ad = payload.get("ad_metrics")
    manual_listing = payload.get("listing_data")
    manual_ai = payload.get("ai_result")
    manual_top20 = payload.get("top20_context")

    if not asin:
        return {
            "error": "missing_asin",
            "message": "请提供 ASIN",
        }

    # ── Run all three auto-fetch operations concurrently ──
    listing_result, ad_result, top20_result = await asyncio.gather(
        _fetch_listing_from_scraper(asin, marketplace),
        _fetch_ad_metrics_from_db(asin, user_id, db),
        _fetch_top20_from_db(asin, user_id, db),
        return_exceptions=True,
    )

    # ── Unpack results (exceptions become None) ──
    listing_data = listing_result if isinstance(listing_result, dict) else None
    ad_metrics = ad_result if isinstance(ad_result, dict) else None
    top20_context = top20_result if isinstance(top20_result, dict) else None

    # ── Build data_sources provenance ──
    data_sources = {
        "listing": "scraped" if listing_data else ("manual" if manual_listing else "missing"),
        "ad_metrics": "database" if ad_metrics else ("manual" if manual_ad else "missing"),
        "top20": "database" if top20_context else ("manual" if manual_top20 else "missing"),
    }

    # ── Fall back to manual data if auto-fetch returned nothing ──
    listing_data = listing_data or manual_listing
    ad_metrics = ad_metrics or manual_ad
    top20_context = top20_context or manual_top20

    # ── If all three sources are missing, return early ──
    if not listing_data and not ad_metrics and not top20_context:
        return {
            "error": "insufficient_data",
            "message": "无法获取诊断所需数据，请先上传广告报表或手动输入Listing信息",
            "data_sources": data_sources,
        }

    # ── Run diagnosis ──
    engine = MultiSourceDiagnosisEngine()
    result = engine.diagnose(
        asin=asin,
        marketplace=marketplace,
        ad_metrics=ad_metrics,
        listing_data=listing_data,
        ai_result=manual_ai,
        top20_context=top20_context,
    )
    result["data_sources"] = data_sources
    return result


# ── Auto-fetch helpers ──────────────────────────────────────────────

async def _fetch_listing_from_scraper(asin: str, marketplace: str) -> dict | None:
    """Scrape listing data from Amazon via ScraperAPI. 5-second timeout."""
    try:
        async with asyncio.timeout(5):
            scraper = ScraperAPIProvider()
            capture = await scraper.capture_product_by_asin(asin, marketplace)
        if capture.capture_status == "failed" or not capture.extracted_fields:
            return None
        return dict(capture.extracted_fields)
    except (asyncio.TimeoutError, Exception):
        return None


async def _fetch_ad_metrics_from_db(asin: str, user_id: str | None, db: AsyncSession) -> dict | None:
    """Aggregate 30-day ad metrics from ad_data table (legacy model)."""
    try:
        from app.backend.models.ad_data import Ad_data  # type: ignore[import-untyped]

        cutoff = datetime.utcnow() - timedelta(days=30)
        stmt = select(
            func.sum(Ad_data.impressions),
            func.sum(Ad_data.clicks),
            func.sum(Ad_data.orders),
            func.sum(Ad_data.spend),
            func.sum(Ad_data.sales),
        ).where(
            Ad_data.user_id == (user_id or ""),
            Ad_data.date >= cutoff,
        )
        result = await db.execute(stmt)
        row = result.first()
        if not row or row[0] is None:
            return None

        impressions, clicks, orders, spend, sales = row
        ctr = round(clicks / impressions, 4) if impressions else None
        cvr = round(orders / clicks, 4) if clicks else None
        acos = round(spend / sales, 4) if sales else None

        return {
            "impressions": impressions,
            "clicks": clicks,
            "orders": orders,
            "spend": spend,
            "sales": sales,
            "ctr": ctr,
            "cvr": cvr,
            "acos": acos,
        }
    except Exception:
        return None


async def _fetch_top20_from_db(asin: str, user_id: str | None, db: AsyncSession) -> dict | None:
    """Extract avg_price, bsr_trend from historical CaptureJob records for this ASIN."""
    try:
        stmt = (
            select(CaptureJob)
            .where(
                CaptureJob.user_id == (user_id or ""),
                CaptureJob.input_value.contains(asin),
                CaptureJob.status == "success",
            )
            .order_by(desc(CaptureJob.finished_at))
            .limit(3)
        )
        result = await db.execute(stmt)
        jobs = result.scalars().all()

        prices: list[float] = []
        bsr_values: list[int] = []
        keywords: list[str] = []

        for job in jobs:
            fields = job.extracted_fields or {}
            if isinstance(fields, dict):
                results_list = fields.get("results")
                if isinstance(results_list, list):
                    for item in results_list:
                        if isinstance(item, dict):
                            if item.get("asin") == asin and item.get("price"):
                                try:
                                    prices.append(float(str(item["price"]).replace("$", "").replace(",", "")))
                                except (ValueError, TypeError):
                                    pass
                            kw = item.get("keyword")
                            if kw and kw not in keywords:
                                keywords.append(str(kw))

        if not prices and not keywords:
            return None

        avg_price = round(sum(prices) / len(prices), 2) if prices else None
        return {
            "avg_price": avg_price,
            "top20_sample_count": len(prices),
            "bsr_trend": "stable",
            "keywords": keywords[:10],
        }
    except Exception:
        return None
