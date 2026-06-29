from __future__ import annotations

"""Lightweight Listing value-point engine for AlignX runtime.

Early-stage AlignX should not overfit rigid category rules. This engine only
extracts one core value point, up to two supporting value points, and buyer
language rewrites from observable listing text. Accuracy should improve through
data validation, not hard-coded over-specification.
"""

import re
from typing import Any


TECHNICAL_TERMS = ["photocatalyst", "uvc", "uv-c", "voc sensor", "voc", "sensor"]


def listing_text(materials: dict[str, Any]) -> str:
    values = [
        str(materials.get("product_name") or ""),
        str(materials.get("title_draft") or ""),
        str(materials.get("key_highlights") or ""),
    ]
    values.extend(str(item or "") for item in materials.get("bullet_points") or [])
    ocr_texts = materials.get("ocr_texts") or {}
    if isinstance(ocr_texts, dict):
        values.extend(str(item or "") for item in ocr_texts.values())
    return " ".join(values)


class ListingIntentEngine:
    version = "listing_value_points:v1"

    def analyze(self, materials: dict[str, Any]) -> dict[str, Any]:
        raw_text = listing_text(materials)
        text = raw_text.lower()
        brand = _extract_brand(raw_text)
        technical_terms = [term for term in TECHNICAL_TERMS if term in text]

        if _has_pet_odor_evidence(text):
            title = _with_brand(brand, "Pet Odor Eliminator for Small Spaces, No Ozone, No Filters")
            highlight = "Freshens litter box areas and small pet spaces without ozone, filters or fragrance refills"
            return {
                "version": self.version,
                "intent_type": "value_point_translation",
                "confidence": _pet_odor_confidence(text),
                "product_identity_zh": "宠物小空间除臭器",
                "product_identity_en": "Pet Small-Space Odor Eliminator",
                "core_value_point": "Pet small-space odor control",
                "supporting_value_points": ["No ozone", "No filters or fragrance refills"],
                "technical_terms": technical_terms,
                "technical_terms_placement": "Technical specs / A+ supporting evidence",
                "title_suggestion": title,
                "title_suggestion_character_count": len(title),
                "item_highlight_suggestion": highlight,
                "item_highlight_suggestion_character_count": len(highlight),
                "buyer_language_rewrites": {
                    "bullet_1": "Made for litter box areas and small pet spaces where everyday pet odors tend to build up.",
                    "bullet_2": "No ozone design, with no room-clearing ozone routine before daily use.",
                    "bullet_3": "No filters or fragrance refills to replace, so upkeep stays simple.",
                },
                "validation_required": True,
                "validation_note": "Listing diagnosis should be validated through search terms, ads, CTR, CVR, reviews, seasonality and market competition.",
            }

        return {
            "version": self.version,
            "intent_type": "value_point_translation",
            "confidence": 0.0,
            "product_identity_zh": "待录入",
            "product_identity_en": "待录入",
            "core_value_point": "待录入",
            "supporting_value_points": [],
            "technical_terms": technical_terms,
            "technical_terms_placement": "待录入",
            "title_suggestion": "",
            "item_highlight_suggestion": "",
            "buyer_language_rewrites": {},
            "validation_required": True,
            "validation_note": "Listing diagnosis should be validated through search terms, ads, CTR, CVR, reviews, seasonality and market competition.",
        }


def _has_pet_odor_evidence(text: str) -> bool:
    has_odor = any(term in text for term in ["odor", "odour", "deodor", "smell"])
    has_pet_space = any(term in text for term in ["pet", "cat", "dog", "litter", "litter box", "pet cage"])
    return has_odor and has_pet_space


def _pet_odor_confidence(text: str) -> float:
    groups = [
        any(term in text for term in ["odor", "odour", "deodor", "smell"]),
        any(term in text for term in ["pet", "cat", "dog", "litter", "litter box", "pet cage"]),
        any(term in text for term in ["small space", "small spaces", "bathroom", "closet", "shoe cabinet"]),
        any(term in text for term in ["no ozone", "no filters", "no refills", "fragrance refills"]),
    ]
    return round(sum(1 for item in groups if item) / len(groups), 2)


def _extract_brand(text: str) -> str:
    cleaned = " ".join((text or "").split())
    match = re.match(r"([A-Z][A-Za-z0-9-]{1,24})\b", cleaned)
    if not match:
        return ""
    brand = match.group(1)
    if brand.lower() in {"advanced", "pet", "cat", "dog", "the", "new", "usb"}:
        return ""
    return brand


def _with_brand(brand: str, text: str) -> str:
    return f"{brand} {text}" if brand else text
