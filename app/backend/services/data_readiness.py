"""Hard data-readiness gates for Amazon decision workflows.

The goal is to keep low-integrity or AI-estimated data out of formal analysis,
ad strategy, and workflow memory.
"""

from __future__ import annotations

import re
from typing import Any


HIGH_TRUST_SOURCES = {
    "browser_proxy",
    "user_chrome_extension",
    "user_chrome_apple_events",
    "local_browser_agent",
    "manual_verified_html",
    "sp_api",
}

MEDIUM_TRUST_SOURCES = {
    "amazon_scrape",
    "amazon_scrape_httpx",
    "amazon_scrape_browser",
    "server_scrape",
    "scraped",
    "manual",
    "manual_listing",
    "cached_analysis",
}

LOW_TRUST_SOURCES = {
    "ai",
    "ai_search",
    "ai_empty",
    "ai_estimated",
    "ai_estimated_low_confidence",
    "insufficient_real_data",
    "scrape_failed",
    "scrape_timeout",
    "rule_fallback",
    "saved_history_snapshot",
    "incomplete_saved_snapshot",
}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _has_text(value: Any, min_len: int = 2) -> bool:
    return len(_clean_text(value)) >= min_len


def _has_number(value: Any) -> bool:
    return bool(re.search(r"\d", _clean_text(value)))


def _count_items(value: Any) -> int:
    if isinstance(value, list):
        return len([item for item in value if _has_text(item)])
    if isinstance(value, str):
        lines = [line.strip(" -*\t") for line in re.split(r"[\n;]+", value) if line.strip(" -*\t")]
        if len(lines) > 1:
            return len(lines)
        return 1 if len(value.strip()) >= 40 else 0
    return 0


def _source_trust(source: str) -> str:
    normalized = (source or "").strip().lower()
    if normalized in HIGH_TRUST_SOURCES:
        return "high"
    if normalized in LOW_TRUST_SOURCES or normalized.startswith("ai_"):
        return "low"
    if normalized in MEDIUM_TRUST_SOURCES or "scrape" in normalized:
        return "medium"
    return "medium" if normalized else "low"


def _safe_int(value: Any) -> int:
    match = re.search(r"\d+", _clean_text(value).replace(",", ""))
    return int(match.group(0)) if match else 0


def _grade(score: int, source_trust: str, formal_allowed: bool) -> str:
    if source_trust == "low" or score < 45:
        return "D"
    if not formal_allowed or score < 65:
        return "C"
    if score >= 85 and source_trust == "high":
        return "A"
    return "B"


def assess_asin_product_data(product_data: dict | None, source: str | None = None) -> dict:
    data = product_data or {}
    data_source = source or data.get("_data_source") or data.get("data_source") or ""
    trust = _source_trust(str(data_source))

    passed: list[str] = []
    missing: list[str] = []

    def check(key: str, ok: bool, weight: int) -> int:
        (passed if ok else missing).append(key)
        return weight if ok else 0

    bullet_count = _count_items(data.get("bullet_points"))
    image_count = _count_items(data.get("image_urls")) or _safe_int(data.get("image_count"))
    low_review_count = _count_items(data.get("low_star_reviews"))
    rating_histogram = data.get("rating_histogram") if isinstance(data.get("rating_histogram"), dict) else {}

    title_ok = _has_text(data.get("title") or data.get("product_title"), 8)
    asin_ok = _has_text(data.get("asin"), 8)
    bullets_ok = bullet_count >= 3
    price_ok = _has_number(data.get("price"))
    rating_or_reviews_ok = _has_number(data.get("rating")) or _has_number(data.get("review_count"))
    images_ok = image_count >= 1
    category_ok = _has_text(data.get("category") or data.get("bsr_category"), 3)
    brand_ok = _has_text(data.get("brand"), 2)
    demand_signal_ok = _has_number(data.get("bsr_rank")) or _has_number(data.get("bought_count"))
    review_evidence_ok = low_review_count >= 3 or bool(rating_histogram)

    score = 0
    score += check("asin", asin_ok, 6)
    score += check("title", title_ok, 18)
    score += check("bullet_points>=3", bullets_ok, 16)
    score += check("price", price_ok, 12)
    score += check("rating_or_review_count", rating_or_reviews_ok, 12)
    score += check("image_evidence", images_ok, 12)
    score += check("category", category_ok, 8)
    score += check("brand", brand_ok, 5)
    score += check("demand_signal", demand_signal_ok, 4)
    score += check("review_evidence", review_evidence_ok, 7)

    if trust == "low":
        score = min(score, 35)

    formal_required = ["title", "bullet_points>=3", "price", "rating_or_review_count", "image_evidence"]
    strategy_required = formal_required + ["review_evidence"]
    formal_allowed = trust != "low" and all(field not in missing for field in formal_required)
    ad_strategy_allowed = formal_allowed and "review_evidence" not in missing
    save_allowed = formal_allowed and trust in {"high", "medium"}

    warnings: list[str] = []
    if trust == "low":
        warnings.append("数据来源为低可信来源，只能用于提示用户补抓，不能进入正式评分、广告策略或记忆库。")
    if trust == "medium":
        warnings.append("服务端抓取可能受地区、登录态、反爬和页面变体影响，关键决策前建议用用户本地浏览器代理复核。")
    if not formal_allowed:
        warnings.append("核心页面字段不完整，系统已阻止正式分析口径。")
    if formal_allowed and not ad_strategy_allowed:
        warnings.append("缺少低星评论或评分分布，广告策略只能做方向提示，不能直接生成投放动作。")

    return {
        "grade": _grade(score, trust, formal_allowed),
        "score": score,
        "formal_analysis_allowed": formal_allowed,
        "ad_strategy_allowed": ad_strategy_allowed,
        "save_to_memory_allowed": save_allowed,
        "source": data_source or "unknown",
        "source_trust": trust,
        "passed_fields": passed,
        "missing_fields": missing,
        "warnings": warnings,
        "required_for_formal": formal_required,
        "required_for_strategy": strategy_required,
    }


def assess_listing_input(listing: Any, source: str | None = None, context: dict | None = None) -> dict:
    ctx = context or {}
    data = {
        "asin": getattr(listing, "asin", ""),
        "title": getattr(listing, "title", ""),
        "bullet_points": getattr(listing, "bullet_points", ""),
        "price": getattr(listing, "price", ""),
        "brand": getattr(listing, "brand", ""),
        "category": getattr(listing, "category", ""),
        "rating": getattr(listing, "rating", ""),
        "review_count": getattr(listing, "review_count", ""),
        "bsr_rank": getattr(listing, "bsr_rank", ""),
        "image_count": getattr(listing, "image_count", ""),
        "low_star_reviews": ctx.get("low_star_reviews") or ctx.get("review_samples") or [],
        "rating_histogram": ctx.get("rating_histogram") or {},
    }
    resolved_source = source or ctx.get("source") or ctx.get("data_source") or "manual_listing"
    return assess_asin_product_data(data, str(resolved_source))
