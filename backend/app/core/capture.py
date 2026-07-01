from __future__ import annotations
"""Capture provider abstraction — ScraperAPI / manual.

Protocol: every provider implements these three methods and returns a unified CaptureResult.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class CaptureResult:
    """Unified capture output regardless of provider."""

    raw_response: dict | None = None
    raw_html: str | None = None
    screenshot: bytes | None = None

    extracted_fields: dict = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)

    capture_status: str = "pending"  # success | partial | failed
    capture_provider: str = ""
    data_completeness_score: float = 0.0
    error_message: str | None = None


class CaptureProvider(Protocol):
    """Interface that every Amazon capture provider must satisfy."""

    async def capture_product_by_asin(
        self, asin: str, marketplace: str
    ) -> CaptureResult: ...

    async def capture_product_by_url(
        self, url: str, marketplace: str
    ) -> CaptureResult: ...

    async def capture_top20_by_keyword(
        self, keyword: str, marketplace: str
    ) -> CaptureResult: ...


# Minimum fields required for a partial diagnosis
MIN_DIAGNOSIS_FIELDS = [
    "title",
    "main_image",
    "bullet_points",
]
