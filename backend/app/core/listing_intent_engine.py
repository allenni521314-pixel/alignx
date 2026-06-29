from __future__ import annotations

"""Listing intent rules used by AlignX runtime.

This module converts observable listing text into a product mind-value point.
It is not a Codex skill dependency; it is application logic executed by AlignX.
"""

from typing import Any


PET_SMALL_SPACE_KEYWORDS = [
    "pet",
    "cat",
    "dog",
    "litter",
    "odor",
    "odour",
    "deodor",
    "small space",
    "small spaces",
    "no ozone",
    "no filters",
    "no refills",
]

TECHNICAL_TERMS = ["photocatalyst", "uvc", "uv-c", "voc sensor", "voc", "sensor"]


def listing_text(materials: dict[str, Any]) -> str:
    values: list[str] = [
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
    version = "listing_intent:v1"

    def analyze(self, materials: dict[str, Any]) -> dict[str, Any]:
        text = listing_text(materials).lower()
        if self._is_pet_small_space_odor_product(text):
            return self._pet_small_space_odor_intent(text)
        return {
            "version": self.version,
            "intent_type": "unknown",
            "product_identity_zh": "待录入",
            "product_identity_en": "待录入",
            "technical_terms": [term for term in TECHNICAL_TERMS if term in text],
            "title_suggestion": "",
            "item_highlight_suggestion": "",
            "bullet_suggestions": [],
        }

    def _is_pet_small_space_odor_product(self, text: str) -> bool:
        return (
            ("odor" in text or "odour" in text or "deodor" in text)
            and any(term in text for term in ["pet", "cat", "dog", "litter"])
        )

    def _pet_small_space_odor_intent(self, text: str) -> dict[str, Any]:
        title = "Gleeda Pet Odor Eliminator for Small Spaces, No Ozone, No Filters"
        highlight = "Freshens litter box areas and small pet spaces without ozone, filters or fragrance refills"
        return {
            "version": self.version,
            "intent_type": "pet_small_space_odor_eliminator",
            "product_identity_zh": "宠物小空间除臭器",
            "product_identity_en": "Pet Small-Space Odor Eliminator",
            "core_search_terms": [
                "pet odor eliminator",
                "litter box odor eliminator",
                "cat litter odor eliminator",
            ],
            "primary_use_cases": [
                "litter box areas",
                "small pet spaces",
                "bathrooms",
                "closets",
                "shoe cabinets",
            ],
            "differentiators": ["no ozone", "no filters", "no refills", "no fragrance refills"],
            "technical_terms": [term for term in TECHNICAL_TERMS if term in text],
            "technical_terms_placement": "A+6 Technical Specs",
            "title_suggestion": title,
            "title_suggestion_character_count": len(title),
            "item_highlight_suggestion": highlight,
            "item_highlight_suggestion_character_count": len(highlight),
            "bullet_suggestions": [
                "Made for litter box areas and small pet spaces where everyday pet odors tend to build up.",
                "No ozone design, with no room-clearing ozone routine before daily use.",
                "No filters or fragrance refills to replace, so upkeep stays simple.",
                "USB powered wall-mount design helps keep the device placed near odor-prone spots.",
                "Best for bathrooms, closets, shoe cabinets and pet areas that need steady small-space odor control.",
            ],
            "demoted_terms_reason": "Photocatalyst, UVC and VOC sensor are technical support terms, not the core buyer value point.",
        }
