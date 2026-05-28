from __future__ import annotations

from typing import Any


CORE_FIELDS = {
    "title": "标题",
    "price": "价格",
    "rating": "评分",
    "review_count": "评论数",
    "bullet_points": "五点描述",
    "image_urls": "主图/图片",
}

STRATEGY_FIELDS = {
    "bsr_rank": "BSR排名",
    "low_star_reviews": "低星评论",
    "rating_histogram": "评分分布",
    "aplus_content": "A+内容",
    "availability": "库存/可售状态",
}

SOURCE_CONFIDENCE = {
    "local_browser_capture": "high",
    "server_proxy_fetch": "medium",
    "amazon_scrape": "medium",
    "scraped": "medium",
    "manual_paste": "medium",
    "ai_estimated": "low",
    "ai_estimated_low_confidence": "low",
}


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def capture_quality(parsed: dict[str, Any], source: str = "server_proxy_fetch") -> dict[str, Any]:
    missing_core = [label for key, label in CORE_FIELDS.items() if not _present(parsed.get(key))]
    missing_strategy = [label for key, label in STRATEGY_FIELDS.items() if not _present(parsed.get(key))]
    core_score = round((len(CORE_FIELDS) - len(missing_core)) / len(CORE_FIELDS) * 100)
    strategy_score = round((len(STRATEGY_FIELDS) - len(missing_strategy)) / len(STRATEGY_FIELDS) * 100)
    completeness = round(core_score * 0.7 + strategy_score * 0.3)
    source_confidence = SOURCE_CONFIDENCE.get(source, "medium")
    allow_formal_diagnosis = not missing_core and bool(parsed.get("title"))
    allow_strategy_diagnosis = allow_formal_diagnosis and strategy_score >= 60

    if not allow_formal_diagnosis:
        level = "low"
    elif source_confidence == "high" and completeness >= 80:
        level = "high"
    else:
        level = "medium"

    return {
        "source": source,
        "source_confidence": source_confidence,
        "completeness": completeness,
        "core_score": core_score,
        "strategy_score": strategy_score,
        "missing_core": missing_core,
        "missing_strategy": missing_strategy,
        "allow_formal_diagnosis": allow_formal_diagnosis,
        "allow_strategy_diagnosis": allow_strategy_diagnosis,
        "confidence_level": level,
        "rule": "AI只解释已抓取证据；缺失字段不得自动猜测。",
    }
