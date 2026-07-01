from __future__ import annotations

"""Listing AI pipeline: capture -> OCR -> reasoning."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.listing_images import ensure_snapshot_image_texts
from app.core.prompts import (
    COMPETITOR_SYSTEM,
    CONVERSION_SYSTEM,
    build_competitor_prompt,
    build_conversion_prompt,
)
from app.core.scraperapi import ScraperAPIProvider
from app.models import CaptureJob, ListingSnapshot
from app.services.access import TenantScope
from app.services.ai_calls import complete_json_with_log


def extract_asin(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    direct = re.fullmatch(r"[A-Z0-9]{10}", text.upper())
    if direct:
        return direct.group(0)
    match = re.search(r"/(?:dp|gp/product|product-reviews)/([A-Z0-9]{10})(?:[/?#]|$)", text, re.I)
    return match.group(1).upper() if match else None


@dataclass
class ListingAiPipelineResult:
    asin: str
    marketplace: str
    listing_data: dict[str, Any] | None = None
    ai_result: dict[str, Any] | None = None
    capture_job_id: str | None = None
    listing_snapshot_id: str | None = None
    capture_status: str = "pending"
    ocr_status: str = "pending"
    capture_error: str | None = None
    ocr_error: str | None = None
    ai_error: str | None = None

    def evidence_payload(self) -> dict[str, Any]:
        return {
            "capture_job_id": self.capture_job_id,
            "listing_snapshot_id": self.listing_snapshot_id,
            "capture_status": self.capture_status,
            "ocr_status": self.ocr_status,
            "capture_error": self.capture_error,
            "ocr_error": self.ocr_error,
        }


class ListingAiPipeline:
    def __init__(
        self,
        db: AsyncSession,
        user_id: str | None,
        asin: str,
        marketplace: str,
        product_url: str | None = None,
    ) -> None:
        self.db = db
        self.scope = TenantScope.require(db, user_id)
        self.user_id = self.scope.user_id
        self.asin = asin
        self.marketplace = marketplace
        self.product_url = product_url

    async def run_conversion_diagnosis(self) -> ListingAiPipelineResult:
        return await self.run_listing_reasoning(
            module_name="conversion_diagnosis",
            prompt_version="conversion_diagnosis:v1",
            prompt_builder=lambda listing_data: build_conversion_prompt(self.asin, listing_data),
            system=CONVERSION_SYSTEM,
        )

    async def run_competitor_analysis(self) -> ListingAiPipelineResult:
        return await self.run_listing_reasoning(
            module_name="competitor_analysis",
            prompt_version="competitor_analysis:v1",
            prompt_builder=lambda listing_data: build_competitor_prompt(self.asin, listing_data),
            system=COMPETITOR_SYSTEM,
        )

    async def run_listing_reasoning(
        self,
        *,
        module_name: str,
        prompt_version: str,
        prompt_builder: Callable[[dict[str, Any]], str],
        system: str,
    ) -> ListingAiPipelineResult:
        result = ListingAiPipelineResult(asin=self.asin, marketplace=self.marketplace)
        await self.prepare_listing(result)
        if not result.listing_data:
            return result

        try:
            prompt = prompt_builder(result.listing_data)
            result.ai_result = await complete_json_with_log(
                db=self.db,
                user_id=self.user_id,
                asin=self.asin,
                module_name=module_name,
                prompt_version=prompt_version,
                prompt=prompt,
                system=system,
                input_payload={
                    "asin": self.asin,
                    "marketplace": self.marketplace,
                    "product_url": self.product_url,
                    "listing_data": result.listing_data,
                    "pipeline": result.evidence_payload(),
                },
                analysis_mode="listing_reasoning",
                trust_meta=result.evidence_payload(),
                ai_trace={
                    "capture_job_id": result.capture_job_id,
                    "listing_snapshot_id": result.listing_snapshot_id,
                    "capture_status": result.capture_status,
                    "ocr_status": result.ocr_status,
                },
            )
        except Exception as exc:
            result.ai_error = str(exc)
        return result

    async def prepare_listing(self, result: ListingAiPipelineResult | None = None) -> ListingAiPipelineResult:
        if result is None:
            result = ListingAiPipelineResult(asin=self.asin, marketplace=self.marketplace)
        snapshot, capture_job = await self._latest_owned_snapshot()
        if snapshot:
            result.capture_status = "snapshot"
            result.capture_job_id = capture_job.id if capture_job else None
            result.listing_snapshot_id = snapshot.id
            result.ocr_status = await self._ensure_ocr(snapshot, result)
            result.listing_data = self._snapshot_to_listing_data(snapshot)
        else:
            snapshot = await self._capture_snapshot(result)
            if snapshot:
                result.listing_snapshot_id = snapshot.id
                result.ocr_status = await self._ensure_ocr(snapshot, result)
                result.listing_data = self._snapshot_to_listing_data(snapshot)
        return result

    async def _latest_owned_snapshot(self) -> tuple[ListingSnapshot | None, CaptureJob | None]:
        return await self.scope.latest_listing_snapshot(self.asin, self.marketplace)

    async def _capture_snapshot(self, result: ListingAiPipelineResult) -> ListingSnapshot | None:
        capture = CaptureJob(
            user_id=self.user_id,
            input_type="product_url" if self.product_url else "asin",
            input_value=self.product_url or self.asin,
            marketplace=self.marketplace,
            provider="scraperapi",
            status="running",
            started_at=datetime.utcnow(),
        )
        self.db.add(capture)
        await self.db.flush()
        result.capture_job_id = capture.id

        provider = ScraperAPIProvider()
        capture_result = await (
            provider.capture_product_by_url(self.product_url, self.marketplace)
            if self.product_url
            else provider.capture_product_by_asin(self.asin, self.marketplace)
        )
        capture.status = capture_result.capture_status
        capture.finished_at = datetime.utcnow()
        fields = capture_result.extracted_fields or {}
        capture.error_message = capture_result.error_message or fields.get("ocr_error")
        result.capture_status = capture_result.capture_status
        result.capture_error = capture.error_message
        await self.db.flush()

        if capture_result.capture_status == "failed":
            return None

        snapshot = ListingSnapshot(
            capture_job_id=capture.id,
            asin=self.asin,
            marketplace=self.marketplace,
            title=fields.get("title"),
            price=fields.get("price"),
            price_value=fields.get("price_value"),
            rating=fields.get("rating"),
            review_count=fields.get("review_count"),
            main_image=fields.get("main_image"),
            image_urls=fields.get("image_urls"),
            bullet_points=fields.get("bullet_points"),
            aplus_content=fields.get("aplus_content"),
            product_details=fields.get("product_details"),
            ocr_image_texts=fields.get("ocr_image_texts"),
            parse_status=capture_result.capture_status,
            missing_fields=capture_result.missing_fields,
            field_completeness_score=capture_result.data_completeness_score,
        )
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def _ensure_ocr(self, snapshot: ListingSnapshot, result: ListingAiPipelineResult) -> str:
        current = snapshot.ocr_image_texts
        if isinstance(current, dict) and current:
            return "success"
        try:
            image_texts = await ensure_snapshot_image_texts(snapshot, self.db)
            return "success" if image_texts else "skipped"
        except Exception as exc:
            result.ocr_error = str(exc)
            return "failed"

    def _snapshot_to_listing_data(self, snapshot: ListingSnapshot) -> dict[str, Any]:
        return {
            "title": snapshot.title,
            "price": snapshot.price,
            "rating": snapshot.rating,
            "review_count": snapshot.review_count,
            "bullet_points": snapshot.bullet_points,
            "main_image": snapshot.main_image,
            "image_urls": snapshot.image_urls,
            "aplus_content": snapshot.aplus_content,
            "product_details": snapshot.product_details,
            "ocr_image_texts": snapshot.ocr_image_texts,
        }


async def run_conversion_listing_ai_pipeline(
    *,
    asin: str,
    marketplace: str,
    db: AsyncSession,
    user_id: str | None,
    product_url: str | None = None,
) -> ListingAiPipelineResult:
    pipeline = ListingAiPipeline(
        db=db,
        user_id=user_id,
        asin=asin,
        marketplace=marketplace,
        product_url=product_url,
    )
    return await pipeline.run_conversion_diagnosis()


async def run_competitor_listing_ai_pipeline(
    *,
    asin: str,
    marketplace: str,
    db: AsyncSession,
    user_id: str | None,
    product_url: str | None = None,
) -> ListingAiPipelineResult:
    pipeline = ListingAiPipeline(
        db=db,
        user_id=user_id,
        asin=asin,
        marketplace=marketplace,
        product_url=product_url,
    )
    return await pipeline.run_competitor_analysis()


async def run_listing_ai_reasoning(
    *,
    asin: str,
    marketplace: str,
    db: AsyncSession,
    user_id: str | None,
    product_url: str | None,
    module_name: str,
    prompt_version: str,
    prompt_builder: Callable[[dict[str, Any]], str],
    system: str,
) -> ListingAiPipelineResult:
    pipeline = ListingAiPipeline(
        db=db,
        user_id=user_id,
        asin=asin,
        marketplace=marketplace,
        product_url=product_url,
    )
    return await pipeline.run_listing_reasoning(
        module_name=module_name,
        prompt_version=prompt_version,
        prompt_builder=prompt_builder,
        system=system,
    )
