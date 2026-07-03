from __future__ import annotations

from typing import Any


AMAZON_TITLE_RULE_VERSION = "2026-07-27"
AMAZON_TITLE_MAX_CHARS = 75
AMAZON_ITEM_HIGHLIGHTS_MAX_CHARS = 125


def _status(value: str, limit: int) -> str:
    text = (value or "").strip()
    if not text:
        return "待录入"
    return "通过" if len(text) <= limit else "需修改"


def build_listing_title_rule(title: str = "", item_highlights: str = "") -> dict[str, Any]:
    current_title = (title or "").strip()
    highlights = (item_highlights or "").strip()
    return {
        "current_title": current_title,
        "optimized_title": current_title if len(current_title) <= AMAZON_TITLE_MAX_CHARS else "",
        "title_char_count": len(current_title),
        "title_max_chars": AMAZON_TITLE_MAX_CHARS,
        "item_highlights": highlights,
        "item_highlights_char_count": len(highlights),
        "item_highlights_max_chars": AMAZON_ITEM_HIGHLIGHTS_MAX_CHARS,
        "title_compliance_status": _status(current_title, AMAZON_TITLE_MAX_CHARS),
        "highlights_status": _status(highlights, AMAZON_ITEM_HIGHLIGHTS_MAX_CHARS),
        "amazon_title_rule_version": AMAZON_TITLE_RULE_VERSION,
        "effective_date": AMAZON_TITLE_RULE_VERSION,
    }
