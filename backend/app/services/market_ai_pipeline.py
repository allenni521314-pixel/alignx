from __future__ import annotations

"""Market opportunity pipeline: keyword capture -> AI reasoning."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prompts import MARKET_OPPORTUNITY_SYSTEM, build_market_prompt
from app.core.scraperapi import ScraperAPIProvider
from app.models import CaptureJob
from app.services.access import require_user_id
from app.services.ai_calls import complete_json_with_log


@dataclass
class MarketAiPipelineResult:
    keyword: str
    marketplace: str
    captured_fields: dict[str, Any]
    ai_result: dict[str, Any] | None = None
    capture_job_id: str | None = None
    capture_status: str = "pending"
    capture_error: str | None = None
    ai_error: str | None = None

    def evidence_payload(self) -> dict[str, Any]:
        return {
            "capture_job_id": self.capture_job_id,
            "capture_status": self.capture_status,
            "capture_error": self.capture_error,
        }


async def run_market_ai_pipeline(
    *,
    keyword: str,
    marketplace: str,
    db: AsyncSession,
    user_id: str | None,
) -> MarketAiPipelineResult:
    uid = require_user_id(user_id)
    result = MarketAiPipelineResult(keyword=keyword, marketplace=marketplace, captured_fields={})
    capture = CaptureJob(
        user_id=uid,
        input_type="keyword",
        input_value=keyword,
        marketplace=marketplace,
        provider="scraperapi",
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(capture)
    await db.flush()
    result.capture_job_id = capture.id

    provider = ScraperAPIProvider()
    capture_result = await provider.capture_top20_by_keyword(keyword, marketplace)
    capture.status = capture_result.capture_status
    capture.finished_at = datetime.utcnow()
    capture.error_message = capture_result.error_message
    await db.flush()

    result.capture_status = capture_result.capture_status
    result.capture_error = capture_result.error_message
    result.captured_fields = capture_result.extracted_fields or {}
    if capture_result.capture_status == "failed" or not result.captured_fields.get("results"):
        return result

    try:
        prompt = build_market_prompt(keyword, marketplace, result.captured_fields)
        result.ai_result = await complete_json_with_log(
            db=db,
            user_id=uid,
            module_name="market_opportunity",
            prompt_version="market_opportunity:v1",
            prompt=prompt,
            system=MARKET_OPPORTUNITY_SYSTEM,
            input_payload={
                "keyword": keyword,
                "marketplace": marketplace,
                "captured_fields": result.captured_fields,
                "pipeline": result.evidence_payload(),
            },
        )
    except Exception as exc:
        result.ai_error = str(exc)
    return result
