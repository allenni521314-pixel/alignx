"""
Listing Diagnosis & Optimization Router.
Provides COSMO 10-dimension listing diagnosis, keyword coverage analysis,
optimization suggestions, competitor comparison, and ad ROI keyword recommendations.

Dimension system:
  COSMO Core 8D:
    1. function_expression  — 功能表达清晰度
    2. scenario_expression  — 场景表达具体度
    3. identity_fit         — 身份认同适配度
    4. psychology_benefit   — 心理收益唤起度
    5. risk_elimination     — 风险消除有效度
    6. product_identity     — 产品身份 (is_a / used_as)
    7. compatibility        — 兼容搭配 (used_with)
    8. subjective_properties— 主观属性 (感性描述词)
  Seller Extension 2D:
    9. differentiation      — 竞品差异化
   10. market_trend         — 市场趋势
"""

import json
import logging
import re
import asyncio
import os
import hashlib
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user, get_user_scope_ids
from schemas.auth import UserResponse
from services.aihub import AIHubService
from services.amazon_rules_engine import evaluate_amazon_compliance, load_active_rules
from services.amazon_skill_toolbox import (
    build_review_intent_assets,
    build_toolbox_enhancements,
    merge_toolbox_into_ad_validation_plan,
    normalize_review_samples,
)
from services.ai_gateway import AIGatewayService
from services.buyer_language_translation import (
    build_buyer_language_messages,
    build_buyer_language_payload,
    empty_buyer_language_translation,
    normalize_buyer_language_translation,
)
from services.judgment_feedback_rounds import JudgmentFeedbackRoundService
from services.listing_diagnoses import Listing_diagnosesService
from services.judgment_system import JudgmentSystemService
from services.listing_title_rules import build_listing_title_rule
from services.listing_position_cross_judgment import build_listing_position_diagnosis
from services.core_engine_adapter import CoreEngineBusinessAdapter
from services.cosmo_rufus_rules import build_cosmo_rufus_analysis, merge_cosmo_rufus_into_legacy
from services.cosmo_vector_mapping import evaluate_cosmo_vector_mapping_async
from services.canonical_10d_scoring import product_evidence_similarity
from services.human_nature_model import build_human_nature_graph, human_nature_prompt_block
from services.cosmo_operator_agent import CosmoOperatorAgent
from services.scrapeless_amazon_capture import scrape_amazon_product_via_scrapeless
from services.asin_business_profile import AsinBusinessProfileService

logger = logging.getLogger(__name__)
AI_DIAGNOSIS_TIMEOUT_SECONDS = int(os.getenv("AI_DIAGNOSIS_TIMEOUT_SECONDS", "300"))

router = APIRouter(prefix="/api/v1/listing-diagnosis", tags=["listing-diagnosis"])


async def _sync_asin_profile_from_listing_record(db: AsyncSession, user_id: str, record: Any) -> None:
    if not record:
        return
    try:
        await AsinBusinessProfileService(db).upsert_profile_from_listing_diagnosis_record(
            seller_id=user_id,
            row=record,
        )
    except Exception as exc:
        logger.error(f"Sync ASIN profile from listing diagnosis failed: {exc}", exc_info=True)


def _stable_score_offset(*parts: str) -> int:
    """Return a deterministic small offset so fallback element scores never drift between runs."""
    key = "|".join(str(part) for part in parts)
    return (sum(ord(ch) for ch in key) % 16) - 5


_US_SPELLING_REPLACEMENTS = {
    "odour": "odor",
    "colour": "color",
    "flavour": "flavor",
    "favourite": "favorite",
    "organiser": "organizer",
    "organisation": "organization",
    "travelling": "traveling",
    "jewellery": "jewelry",
}


def _normalize_us_keyword(value) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if re.search(r"[\u4e00-\u9fff]", text):
        return ""
    text = re.sub(r"[^a-z0-9 +&/\\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_")
    for british, american in _US_SPELLING_REPLACEMENTS.items():
        text = re.sub(rf"\b{british}\b", american, text)
    words = text.split()
    normalized = " ".join(words[:8])
    return normalized if re.search(r"[a-z]", normalized) else ""


def _keyword_type(keyword: str) -> str:
    kw = keyword.lower()
    state_terms = ("odor", "smell", "ammonia", "pain", "relief", "anxiety", "safe", "comfort", "leak", "tracking", "mess", "stress", "sleep", "noise", "clog", "jam", "blockage", "spill", "overflow", "fresh", "portion")
    relation_terms = ("for ", "with ", "without ", "under ", "near ", "compatible", "replacement", "indoor", "outdoor", "apartment", "bedroom", "travel", "kids", "women", "men", "cats", "dogs", "large breed", "vacation", "weekend")
    if any(term in kw for term in state_terms):
        return "state_trigger"
    if any(term in kw for term in relation_terms):
        return "relationship"
    return "attribute"


def _normalize_keyword_payload(data: dict) -> dict:
    def normalize_list(values, limit=10):
        result = []
        seen = set()
        for raw in values or []:
            kw = _normalize_us_keyword(raw)
            if kw and kw not in seen:
                seen.add(kw)
                result.append(kw)
            if len(result) >= limit:
                break
        return result

    suggestions = data.get("suggestions") or {}
    if isinstance(suggestions, dict):
        suggestions["backend_keywords_addition"] = normalize_list(suggestions.get("backend_keywords_addition"), 10)
        data["suggestions"] = suggestions

    for side in ("covered_categories", "missing_categories"):
        categories = (data.get("keyword_coverage") or {}).get(side) or {}
        if isinstance(categories, dict):
            for key, values in categories.items():
                categories[key] = normalize_list(values, 12)

    ad_keywords = data.get("ad_keywords") or {}
    if isinstance(ad_keywords, dict):
        for group in ("high_conversion", "traffic", "long_tail"):
            items = []
            for item in ad_keywords.get(group) or []:
                if isinstance(item, dict):
                    kw = _normalize_us_keyword(item.get("keyword"))
                    if kw:
                        item["keyword"] = kw
                        item["keyword_type"] = item.get("keyword_type") or _keyword_type(kw)
                        items.append(item)
            ad_keywords[group] = items
        ad_keywords["negative"] = normalize_list(ad_keywords.get("negative"), 12)
        data["ad_keywords"] = ad_keywords
    return data


# ---------- Request / Response Models ----------

class ListingInput(BaseModel):
    title: str = ""
    item_highlights: str = ""
    bullet_points: str = ""
    description: str = ""
    a_plus_content: str = ""
    backend_keywords: str = ""
    main_image_description: str = ""
    category: str = ""
    price: str = ""
    brand: str = ""
    marketplace: str = "US"
    asin: str = ""
    rating: str = ""
    review_count: str = ""
    bsr_rank: str = ""
    image_count: str = ""
    has_video: bool = False
    has_a_plus: bool = False
    image_urls: List[str] = Field(default_factory=list)
    main_image_texts: List[str] = Field(default_factory=list)
    aplus_image_count: str = ""
    aplus_image_urls: List[str] = Field(default_factory=list)
    a_plus_image_texts: List[str] = Field(default_factory=list)


def _ensure_scenario_problem_keywords(data: dict, listing: ListingInput) -> dict:
    """Keep model output as-is; do not inject local legacy keyword rules."""
    return data


class DiagnoseRequest(BaseModel):
    listing: ListingInput
    precision_context: dict = Field(default_factory=dict)
    force_refresh: bool = False
    diagnosis_mode: str = "listing_conversion_readiness"


def _has_required_price(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text or text in {"-", "—", "N/A", "n/a", "NA", "待确认", "未提供", "未知"}:
        return False
    return bool(re.search(r"\d", text))


def _is_new_launch_listing(listing: ListingInput) -> bool:
    no_reviews = _parse_metric_int(listing.review_count) == 0
    no_sales = _parse_metric_int(listing.bsr_rank) == 0
    return no_reviews and no_sales


def _is_new_launch_mode(value: str | None) -> bool:
    return str(value or "").strip().lower() in {
        "new_launch",
        "new_launch_readiness",
        "prelaunch",
        "prelaunch_readiness",
    }


def _is_mature_listing_mode(value: str | None) -> bool:
    return str(value or "").strip().lower() in {
        "mature_listing",
        "listing_conversion",
        "listing_conversion_readiness",
    }


class DiagnoseResponse(BaseModel):
    scores: dict
    analysis: dict
    suggestions: dict
    keyword_coverage: dict
    ad_keywords: dict
    elements: dict = {}
    market_estimates: dict = {}
    overall_summary: str
    analyzed_product_name: str = ""
    product_mismatch: bool = False
    product_mismatch_detail: str = ""
    id: Optional[int] = None
    # ========== 新增：因果诊断字段 ==========
    causal_diagnosis: dict = {}  # 完整的因果诊断报告
    causal_scores: dict = {}     # 因果三维度得分
    # =========================================
    # ========== 新增：精准度/置信度字段 ==========
    judgment_system: dict = {}
    data_integrity: dict = {}
    diagnosis_confidence: dict = {}
    ad_validation_plan: dict = {}
    buyer_language_translation: dict = {}
    opc_v5_execution: dict = {}
    listing_health_analysis: dict = {}
    listing_position_diagnosis: dict = {}
    amazon_compliance: dict = {}
    toolbox_enhancements: dict = {}
    trace: dict = {}
    # =========================================


def _image_signals_from_listing(listing: ListingInput) -> dict:
    description = (listing.main_image_description or "").lower()
    return {
        "main_image": {
            "text_detected": any(token in description for token in ["文字", "text", "copy", "文案"]),
            "badge_detected": any(token in description for token in ["徽章", "badge", "认证标", "icon"]),
            "watermark_detected": any(token in description for token in ["水印", "watermark"]),
            "logo_overlay_detected": any(token in description for token in ["logo overlay", "额外logo", "贴标"]),
            "non_white_background": any(token in description for token in ["非白底", "场景图", "lifestyle", "background"]),
        },
        "raw_description": listing.main_image_description or "",
    }


async def _evaluate_listing_compliance(listing: ListingInput, db: AsyncSession) -> dict:
    rules = await load_active_rules(db)
    claims = "\n".join(
        part
        for part in [
            listing.title,
            listing.bullet_points,
            listing.description,
            listing.a_plus_content,
            listing.backend_keywords,
        ]
        if part
    )
    payload = {
        "marketplace": listing.marketplace or "US",
        "product_type": listing.category or "",
        "title": listing.title or "",
        "bullets": listing.bullet_points or "",
        "description": listing.description or "",
        "a_plus_text": listing.a_plus_content or "",
        "image_analysis": _image_signals_from_listing(listing),
        "claims": claims,
        "attributes": {},
    }
    return evaluate_amazon_compliance(payload, rules)


def _extract_visual_ocr_texts(evidence_chain: dict[str, Any] | None) -> list[str]:
    visual = (evidence_chain or {}).get("visual_ocr") if isinstance(evidence_chain, dict) else {}
    structured_texts = []
    if isinstance(visual, dict):
        for key in ("main_image_texts", "a_plus_image_texts"):
            values = visual.get(key)
            if isinstance(values, list):
                structured_texts.extend(str(item).strip() for item in values if str(item or "").strip())
    if structured_texts:
        return structured_texts[:12]

    summary = visual.get("summary") if isinstance(visual, dict) else ""
    texts: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            text = re.sub(r"\s+", " ", value.strip())
            if text and text not in texts:
                texts.append(text)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key).lower()
                if any(token in key_text for token in ("text", "ocr", "copy", "badge", "claim", "wording")):
                    walk(item)
                elif isinstance(item, (dict, list)):
                    walk(item)

    if isinstance(summary, str) and summary.strip():
        try:
            walk(json.loads(summary))
        except Exception:
            walk(summary)
    return texts[:12]


def _clean_visual_ocr_text(value: Any, max_chars: int = 360) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value).strip())
    if not text or text.lower() in {"none", "null", "n/a", "na", "暂无", "未提供", "没有", "无"}:
        return ""
    return text[:max_chars]


def _visual_item_text(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for label, key in [
        ("图片文案", "image_text"),
        ("图片表达", "image_expression"),
        ("图文错位", "copy_fit"),
        ("买家语言", "buyer_language_note"),
    ]:
        text = _clean_visual_ocr_text(item.get(key), 220)
        if text:
            parts.append(f"{label}：{text}")
    return "；".join(parts)[:520]


def _empty_text_slots(count: int) -> list[str]:
    return ["" for _ in range(max(0, min(count, 9)))]


def _parse_visual_ocr_by_position(content: str, main_count: int, aplus_count: int) -> dict[str, Any]:
    result = {
        "items": [],
        "main_image_texts": _empty_text_slots(main_count),
        "a_plus_image_texts": _empty_text_slots(aplus_count),
    }
    if not content or not content.strip():
        return result

    try:
        parsed = _extract_json(content)
    except Exception:
        return result

    items = parsed.get("items") if isinstance(parsed, dict) else []
    if not isinstance(items, list):
        return result

    normalized_items: list[dict[str, Any]] = []
    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        position_id = _clean_visual_ocr_text(raw_item.get("position_id"), 40)
        image_group = _clean_visual_ocr_text(raw_item.get("image_group"), 40).lower()
        order_raw = raw_item.get("order")
        try:
            order = int(order_raw)
        except Exception:
            order = 0
        item = {
            "position_id": position_id,
            "image_group": image_group,
            "order": order,
            "image_text": _clean_visual_ocr_text(raw_item.get("image_text"), 320),
            "image_expression": _clean_visual_ocr_text(raw_item.get("image_expression"), 320),
            "copy_fit": _clean_visual_ocr_text(raw_item.get("copy_fit"), 240),
            "buyer_language_note": _clean_visual_ocr_text(raw_item.get("buyer_language_note"), 240),
        }
        normalized_items.append(item)
        item_text = _visual_item_text(item)
        if not item_text:
            continue

        if position_id == "主图" or (image_group == "listing" and order == 1):
            if result["main_image_texts"]:
                result["main_image_texts"][0] = item_text
            continue
        secondary_match = re.search(r"副图\s*(\d+)", position_id)
        if secondary_match:
            idx = int(secondary_match.group(1))
            if 1 <= idx < len(result["main_image_texts"]):
                result["main_image_texts"][idx] = item_text
            continue
        if image_group == "listing" and order > 1:
            idx = order - 1
            if 0 <= idx < len(result["main_image_texts"]):
                result["main_image_texts"][idx] = item_text
            continue

        aplus_match = re.search(r"A\+\s*图\s*(\d+)", position_id, re.I)
        if aplus_match:
            idx = int(aplus_match.group(1)) - 1
            if 0 <= idx < len(result["a_plus_image_texts"]):
                result["a_plus_image_texts"][idx] = item_text
            continue
        if image_group in {"aplus", "a_plus", "a+"} and order > 0:
            idx = order - 1
            if 0 <= idx < len(result["a_plus_image_texts"]):
                result["a_plus_image_texts"][idx] = item_text

    result["items"] = normalized_items
    return result


def _merge_visual_ocr_into_listing(listing: ListingInput, evidence_chain: dict[str, Any] | None) -> ListingInput:
    visual = (evidence_chain or {}).get("visual_ocr") if isinstance(evidence_chain, dict) else {}
    if not isinstance(visual, dict):
        return listing
    main_texts = visual.get("main_image_texts") if isinstance(visual.get("main_image_texts"), list) else []
    aplus_texts = visual.get("a_plus_image_texts") if isinstance(visual.get("a_plus_image_texts"), list) else []
    if not main_texts and not aplus_texts:
        return listing

    def merge_slots(existing: list[str], extracted: list[str], count: int) -> list[str]:
        slot_count = max(len(existing or []), len(extracted or []), min(count, 9))
        merged = []
        for idx in range(slot_count):
            current = existing[idx] if idx < len(existing or []) else ""
            ocr_text = extracted[idx] if idx < len(extracted or []) else ""
            merged.append(_clean_visual_ocr_text(current, 520) or _clean_visual_ocr_text(ocr_text, 520))
        return merged

    return listing.model_copy(update={
        "main_image_texts": merge_slots(
            listing.main_image_texts or [],
            main_texts,
            len(listing.image_urls or []),
        ),
        "a_plus_image_texts": merge_slots(
            listing.a_plus_image_texts or [],
            aplus_texts,
            len(listing.aplus_image_urls or []),
        ),
    })


def _buyer_language_payload_from_listing(listing: ListingInput, evidence_chain: dict[str, Any] | None = None) -> dict[str, Any]:
    source = {
        "title": listing.title,
        "bullet_points": listing.bullet_points,
        "description": listing.description,
        "a_plus_content": listing.a_plus_content,
        "category": listing.category,
        "brand": listing.brand,
        "keywords": listing.backend_keywords,
    }
    visual_texts = _extract_visual_ocr_texts(evidence_chain)
    payload = build_buyer_language_payload(
        title=listing.title,
        bullet_points=listing.bullet_points,
        a_plus_desc=listing.a_plus_content,
        keywords=listing.backend_keywords,
        main_image_texts=[
            *([listing.main_image_description] if listing.main_image_description else []),
            *(listing.main_image_texts or []),
            *visual_texts,
        ],
        a_plus_image_texts=[
            *(listing.a_plus_image_texts or []),
            *([listing.a_plus_content] if listing.a_plus_content else []),
        ],
    )
    payload["human_nature_graph"] = build_human_nature_graph(source)
    return payload


def _position_payload_from_listing(listing: ListingInput) -> dict[str, Any]:
    return {
        "title": listing.title,
        "item_highlights": listing.item_highlights,
        "bullet_points": listing.bullet_points,
        "a_plus_content": listing.a_plus_content,
        "main_image_description": listing.main_image_description,
        "image_count": listing.image_count,
        "image_urls": listing.image_urls or [],
        "main_image_texts": listing.main_image_texts or [],
        "aplus_image_count": listing.aplus_image_count,
        "aplus_image_urls": listing.aplus_image_urls or [],
        "a_plus_image_texts": listing.a_plus_image_texts or [],
        "has_a_plus": listing.has_a_plus,
    }


async def _build_listing_buyer_language_translation(
    listing: ListingInput,
    evidence_chain: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _buyer_language_payload_from_listing(listing, evidence_chain)
    fallback = empty_buyer_language_translation(payload)
    gateway = AIGatewayService()
    try:
        if not gateway.status().configured:
            return fallback
        model = gateway.select_model("light")
        content, _usage = await asyncio.wait_for(
            gateway._create_chat_completion(model, build_buyer_language_messages(payload)),
            timeout=45,
        )
        result = normalize_buyer_language_translation(json.loads(content or "{}"), payload)
        result["ai_called"] = True
        result["ai_model"] = model
        return result
    except Exception as exc:
        logger.warning("Listing buyer language translation failed, using fallback: %s", exc)
        return fallback


def _user_filter(column, user_id: str | list[str]):
    return column.in_(user_id) if isinstance(user_id, list) else column == user_id


async def _get_cached_listing_diagnosis(listing: ListingInput, db: AsyncSession, user_id: str | list[str]) -> dict | None:
    """Return the user's latest saved diagnosis only for explicit history/latest loads."""
    if not listing.title:
        return None
    from sqlalchemy import select
    from models.listing_diagnoses import Listing_diagnoses as LD

    result = await db.execute(
        select(LD)
        .where(_user_filter(LD.user_id, user_id), LD.listing_title == listing.title[:500], LD.marketplace == listing.marketplace)
        .where(LD.diagnosis_report.isnot(None), LD.score_function_expression > 0)
        .order_by(LD.id.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()
    if not record:
        return None
    try:
        data = json.loads(record.diagnosis_report or "{}")
    except Exception:
        return None
    scores = dict(data.get("scores") or {})
    scores.update({
        "function_expression": record.score_function_expression or scores.get("function_expression", 0),
        "scenario_expression": record.score_scenario_expression or scores.get("scenario_expression", 0),
        "identity_fit": record.score_identity_fit or scores.get("identity_fit", 0),
        "psychology_benefit": record.score_psychology_benefit or scores.get("psychology_benefit", 0),
        "risk_elimination": record.score_risk_elimination or scores.get("risk_elimination", 0),
        "product_identity": record.score_product_identity or scores.get("product_identity", 0),
        "compatibility": record.score_compatibility or scores.get("compatibility", 0),
        "subjective_properties": record.score_subjective_properties or scores.get("subjective_properties", 0),
        "differentiation": record.score_differentiation or scores.get("differentiation", 0),
        "market_trend": record.score_market_trend or scores.get("market_trend", 0),
        "causal_state_gap_coverage": record.score_causal_state_gap_coverage or scores.get("causal_state_gap_coverage", 0),
        "causal_mechanism_clarity": record.score_causal_mechanism_clarity or scores.get("causal_mechanism_clarity", 0),
        "causal_side_effect_transparency": record.score_causal_side_effect_transparency or scores.get("causal_side_effect_transparency", 0),
    })
    data["scores"] = scores
    data["id"] = record.id
    return data


async def _get_exact_cached_listing_diagnosis(
    listing: ListingInput,
    db: AsyncSession,
    user_id: str | list[str],
    diagnosis_mode: str = "listing_conversion_readiness",
) -> dict | None:
    """Return a saved diagnosis only when the current Listing content is identical."""
    if not listing.title:
        return None
    from sqlalchemy import select
    from models.listing_diagnoses import Listing_diagnoses as LD

    current_fingerprint = _listing_content_fingerprint(_sanitize_listing_for_ai(listing))
    result = await db.execute(
        select(LD)
        .where(_user_filter(LD.user_id, user_id), LD.listing_title == listing.title[:500], LD.marketplace == listing.marketplace)
        .where(LD.diagnosis_report.isnot(None), LD.input_data.isnot(None), LD.score_function_expression > 0)
        .order_by(LD.id.desc())
        .limit(20)
    )
    for record in result.scalars().all():
        try:
            saved_input = json.loads(record.input_data or "{}")
            saved_listing = ListingInput(**saved_input)
        except Exception:
            continue
        if _listing_content_fingerprint(_sanitize_listing_for_ai(saved_listing)) != current_fingerprint:
            continue
        try:
            data = json.loads(record.diagnosis_report or "{}")
        except Exception:
            return None
        saved_mode = str(data.get("diagnosis_mode") or "listing_conversion_readiness")
        requested_mode = str(diagnosis_mode or "listing_conversion_readiness")
        if saved_mode != requested_mode:
            continue
        scores = dict(data.get("scores") or {})
        scores.update({
            "function_expression": record.score_function_expression or scores.get("function_expression", 0),
            "scenario_expression": record.score_scenario_expression or scores.get("scenario_expression", 0),
            "identity_fit": record.score_identity_fit or scores.get("identity_fit", 0),
            "psychology_benefit": record.score_psychology_benefit or scores.get("psychology_benefit", 0),
            "risk_elimination": record.score_risk_elimination or scores.get("risk_elimination", 0),
            "product_identity": record.score_product_identity or scores.get("product_identity", 0),
            "compatibility": record.score_compatibility or scores.get("compatibility", 0),
            "subjective_properties": record.score_subjective_properties or scores.get("subjective_properties", 0),
            "differentiation": record.score_differentiation or scores.get("differentiation", 0),
            "market_trend": record.score_market_trend or scores.get("market_trend", 0),
            "causal_state_gap_coverage": record.score_causal_state_gap_coverage or scores.get("causal_state_gap_coverage", 0),
            "causal_mechanism_clarity": record.score_causal_mechanism_clarity or scores.get("causal_mechanism_clarity", 0),
            "causal_side_effect_transparency": record.score_causal_side_effect_transparency or scores.get("causal_side_effect_transparency", 0),
        })
        data["scores"] = scores
        data["id"] = record.id
        data.setdefault(
            "diagnosis_meta",
            {
                "schema_version": "legacy-or-imported",
                "content_fingerprint": current_fingerprint,
                "content_fingerprint_short": current_fingerprint[:8],
                "cache_policy": "exact_content_only",
            },
        )
        data["_cache_hit"] = "exact_content"
        data["_ai_called"] = False
        return data
    return None


class CompareRequest(BaseModel):
    my_listing: ListingInput
    competitor_listings: List[ListingInput]


class CompareResponse(BaseModel):
    my_diagnosis: dict
    competitor_diagnoses: List[dict]
    comparison: dict


# ---------- URL Fetch Models ----------

class FetchUrlRequest(BaseModel):
    url: str
    marketplace: str = "US"


class FetchUrlResponse(BaseModel):
    listing: ListingInput
    asin: str = ""
    source: str = "ai"
    # Scraped metadata fields
    rating: str = ""
    review_count: str = ""
    bsr_rank: str = ""
    bsr_category: str = ""
    image_count: str = ""
    has_video: bool = False
    has_a_plus: bool = False
    aplus_image_count: str = ""


class ParseHtmlRequest(BaseModel):
    html: str
    marketplace: str = "US"
    asin: str = ""
    source: str = "external_amazon_product"
    captured_title: str = ""
    captured_price: str = ""
    captured_rating: str = ""
    captured_review_count: str = ""
    captured_bsr_rank: str = ""
    captured_image_count: str = ""
    captured_bullets: List[str] = Field(default_factory=list)
    captured_reviews: List[dict[str, Any]] = Field(default_factory=list)


class ParseHtmlResponse(BaseModel):
    listing: ListingInput
    asin: str = ""
    source: str = "external_amazon_product"
    rating: str = ""
    review_count: str = ""
    bsr_rank: str = ""
    bsr_category: str = ""
    image_count: str = ""
    has_video: bool = False
    has_a_plus: bool = False
    aplus_image_count: str = ""
    capture_quality: dict = {}
    review_intent_assets: dict = Field(default_factory=dict)
    review_samples: List[dict[str, Any]] = Field(default_factory=list)
    success: bool = False
    error: str = ""


# ---------- URL Fetch Helpers ----------

import re

FETCH_LISTING_PROMPT = """你是一位资深的Amazon产品数据分析专家。你的任务是搜索一个特定ASIN的真实产品信息。

## 目标ASIN信息
- ASIN: {asin}
- 站点: Amazon {marketplace}
- 产品页面URL: https://www.amazon.{domain}/dp/{asin}

## 搜索指令（必须严格遵守）

### 第一步：搜索该ASIN的真实产品
请搜索以下查询（按优先级）：
1. 搜索 "amazon.{domain}/dp/{asin}" 获取该产品页面信息
2. 搜索 "Amazon {asin}" 获取该ASIN对应的产品
3. 搜索 "site:amazon.{domain} {asin}" 限定在Amazon域名内搜索

### 第二步：验证ASIN匹配（关键！）
找到产品后，你必须验证：
- 搜索结果中的ASIN是否确实是 "{asin}"
- 如果搜索结果中没有明确提到ASIN "{asin}"，则confidence必须设为"low"
- 如果你找到的是一个不同的产品/ASIN，不要返回那个产品的数据

### 第三步：填写数据
- 只填写你从搜索结果中确认属于ASIN "{asin}" 的数据
- 无法确定的字段返回空字符串 ""
- 绝对不要编造数据，不要猜测
- 不要在任何字段中添加"[未确认]"、"[unknown]"等标记

## 重要警告
⚠️ 如果你无法确认找到的产品就是ASIN "{asin}"，请将所有字段设为空字符串，confidence设为"low"。
⚠️ 宁可返回空数据，也不要返回错误产品的数据。返回错误产品比返回空数据更糟糕。
⚠️ 不同的ASIN对应完全不同的产品，不要混淆。

请以JSON格式返回（确保返回有效的JSON）：
{{
  "asin_verified": "{asin}",
  "title": "产品完整标题（必须是ASIN {asin}对应的产品，无法确定则返回空字符串）",
  "bullet_points": "五点描述，每条用换行符分隔",
  "description": "产品描述",
  "a_plus_content": "A+内容描述（如果有的话）",
  "backend_keywords": "可能的后台关键词",
  "main_image_description": "主图内容描述",
  "category": "产品类目",
  "price": "价格（如 $29.99）",
  "brand": "品牌名",
  "rating": "评分（如 4.5）",
  "review_count": "评论数（如 1234）",
  "bsr_rank": "BSR排名（如 5678）",
  "bsr_category": "BSR所在类目",
  "confidence": "high/medium/low - 你对以上数据确实属于ASIN {asin}的自信程度。如果你不确定找到的产品是否是这个ASIN，必须设为low",
  "verification_note": "简要说明你是如何确认这个产品对应ASIN {asin}的"
}}

只返回JSON，不要返回其他内容。"""

MARKETPLACE_DOMAINS = {
    "US": "com", "JP": "co.jp", "DE": "de", "UK": "co.uk",
    "FR": "fr", "IT": "it", "ES": "es", "CA": "ca",
    "AU": "com.au", "IN": "in", "MX": "com.mx", "BR": "com.br",
    "SG": "sg", "AE": "ae", "SA": "sa", "NL": "nl", "PL": "pl", "SE": "se",
}


def _extract_asin(url: str) -> str:
    """Extract ASIN from Amazon URL."""
    patterns = [
        r'/dp/([A-Z0-9]{10})',
        r'/gp/product/([A-Z0-9]{10})',
        r'/product/([A-Z0-9]{10})',
        r'/ASIN/([A-Z0-9]{10})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    bare = re.search(r'\b([A-Z0-9]{10})\b', url)
    if bare:
        candidate = bare.group(1)
        if candidate.startswith('B0'):
            return candidate
    return ""


def _detect_marketplace(url: str) -> str:
    """Detect marketplace from URL domain."""
    domain_map = {
        "amazon.com": "US",
        "amazon.co.jp": "JP",
        "amazon.de": "DE",
        "amazon.co.uk": "UK",
        "amazon.fr": "FR",
        "amazon.it": "IT",
        "amazon.es": "ES",
        "amazon.ca": "CA",
        "amazon.com.au": "AU",
        "amazon.in": "IN",
        "amazon.com.mx": "MX",
        "amazon.com.br": "BR",
        "amazon.sg": "SG",
        "amazon.ae": "AE",
        "amazon.sa": "SA",
        "amazon.nl": "NL",
        "amazon.pl": "PL",
        "amazon.se": "SE",
    }
    url_lower = url.lower()
    for domain, mp in domain_map.items():
        if domain in url_lower:
            return mp
    return "US"


# ---------- AI Prompts ----------

DIAGNOSIS_PROMPT = """【最高优先级指令】你正在诊断的产品是: "{title}"。所有分析必须围绕这个产品，禁止分析其他任何产品。

你是一位顶级亚马逊Listing优化专家，精通平台语义识别和美区消费者行为。
请对以下Amazon Listing进行全面诊断分析。

⚠️ 绝对禁止猜测或替换产品信息！你必须且只能分析以下提供的产品。
产品名称是: "{title}"
如果你的分析中出现了与"{title}"不同的产品，说明你犯了严重错误，请立即纠正。

## Listing信息（你必须分析的产品）
站点: Amazon {marketplace}
标题: {title}
五点描述: {bullet_points}
产品描述/A+内容: {description} {a_plus_content}
后台关键词: {backend_keywords}
主图描述: {main_image_description}
类目: {category}
价格: {price}
品牌: {brand}

## 判断模式：人性根层 × 用户需求 × 平台识别 × 10维诊断

本次不是把10个维度当作平铺同级指标简单平均。必须先从“人性根层”推导购买动机，再进入“用户需求”和“平台识别”两套标准判断，最后把10维诊断作为反向检查视角。注意：最终输出面向卖家，不要暴露内部方法论名称；输出字段值中禁止出现“人性根层、趋利、避害、Level、13个人性节点、后台判断、内部方法论”等后台链路词。

### 人性根层标准
判断用户是在趋利还是避害，再从进化层和13个人性节点推导购买动机。
- Level 0：Seek Gain / Avoid Loss。
- Level 1：Survival / Reproduction / Resource / Exploration。
- Level 2：生存、安全、健康、爱、归属、尊严、权力、自由、扩张、好奇、娱乐、懒惰、恐惧。
- 推理链路：Level 0 → Level 1 → Level 2 → 动机 → 需求 → 场景 → Solution → 表达 → 行为 → 结果。
- 禁止从关键词开始推理，关键词只能是动机链路后的表达和验证资产。

### 用户需求标准
判断用户真实要完成什么任务、为什么现在要买、在什么场景使用、依据什么属性决策、担心什么风险。
- 任务对象清晰度：谁要完成什么任务，想得到什么结果？
- 购买触发强度：用户为什么现在需要解决？
- 使用场景约束：人群、地点、搭配、时间和限制是否清楚？
- 决策属性优先级：尺寸、材质、兼容、效果、安全、信任证据哪个先影响购买？
- 反购买风险：为什么会不买、退货或差评？

### 平台识别标准
判断Amazon是否能把该商品放进正确的搜索、广告、推荐和购物助手语义池。
- 类目身份锚定：平台能否识别它是什么商品、属于哪个子类目？
- 查询意图匹配：它应该匹配哪些核心词、场景词、问题词和属性词？
- 结构化属性完整度：尺寸、材质、数量、规格、兼容性、变体是否可抽取？
- 关系图谱完整度：for whom、used for、used with、in scenario、solves 是否清楚？
- 证据可回答性：标题、图片、五点、A+、评论能否回答用户和平台购物助手的问题？
- 推荐语义可抓取性：能否从产品属性主动推理出“谁 + 在什么场景 + 遇到什么问题 + 需要什么结果”的场景问题词，供平台搜索、推荐和广告验证理解。

### 10维诊断动作顺序
必须按以下顺序做后台判断：
1. 人性驱动力：先判断趋利/避害、13个动机节点和动机强度。
2. 用户意图：再判断用户任务、购买触发、场景、决策属性和反购买风险。
3. 平台规则：再判断Amazon能否识别商品身份、查询意图、结构化属性和关系图谱。
4. 验证回流：最后用价格、评论、BSR、关键词和广告数据校准置信度与动作。

每个analysis字段必须说明：人性动机映射、用户需求映射、平台识别映射、当前证据、扣分原因、问题类型（对齐/缺失/错位/断链/误导）、影响指标（CTR/CVR/CPC/ACOS/退货/差评）、动作。禁止在analysis里直接写内部方法论名称。

## 诊断维度（共10个维度，每个0-100分）

### 基础承接维度

#### 1. 功能表达清晰度 (function_expression)
这个产品到底解决什么问题？功能描述是否清晰、具体、可量化？
- 核心功能是否在标题前半段明确表达
- 五点描述是否将技术参数转化为用户利益
- 功能卖点是否有具体数据支撑（如充电速度、容量、尺寸）

#### 2. 场景表达具体度 (scenario_expression)
用户在什么情况下需要它？使用场景是否明确、具体、有画面感？
    - 是否覆盖了核心使用场景（家用、办公、旅行、户外等）
    - 场景描述是否具体到空间和时间（如"nightstand charging"而非"home use"）
    - 是否有季节性/事件性场景覆盖
    - 是否覆盖多场景问题词：同一产品在不同场景下解决的具体问题，例如 vacation feeding、anti clog kibble、odor control for apartments

#### 3. 身份认同适配度 (identity_fit)
它更适合谁？目标用户画像是否清晰？
- 是否明确了目标人群（年龄、职业、生活方式）
- 是否有礼物场景词覆盖（gift for dad, stocking stuffer等）
- 是否匹配了用户的自我认同（minimalist, tech enthusiast等）

#### 4. 心理收益唤起度 (psychology_benefit)
买它后感觉是什么？是否唤起了情感共鸣？
- 是否触发了焦虑缓解（如"never worry about dead phone"）
- 是否有时间效率诉求（save time, faster, smarter）
- 是否有自我奖励/升级感（upgrade, premium, sleek）
- 是否有安心感/掌控感表达

#### 5. 风险消除有效度 (risk_elimination)
用户担心什么？是否有效消除了购买顾虑？
- 是否有安全认证提及（UL, FCC, CE等）
- 是否有兼容性确认（具体设备型号列表）
- 是否有价值对比（vs OEM pricing）
- 是否有保障承诺（warranty, guarantee, return policy）
- 是否有社会证明（bestseller, reviews, ratings）

#### 6. 产品身份 (product_identity) 🆕
产品的"is_a"和"used_as"定义是否清晰？平台如何理解这个产品？
- 产品品类词(is_a)是否在标题中明确出现（如"wireless charger"、"phone stand"）
- 是否有多个used_as场景定义（如"desk organizer"同时也是"phone holder"）
- 品类词是否覆盖了用户可能搜索的所有同义词和变体
- 产品身份是否与实际功能一致，避免品类错配

#### 7. 兼容搭配 (compatibility) 🆕
产品的"used_with"关系是否完整？搭配使用的设备/场景是否明确？
- 是否列出了兼容的具体设备型号（如"Compatible with iPhone 15/14/13, Samsung Galaxy S24"）
- 是否提及了搭配使用的配件或场景（如"works with MagSafe cases"）
- 兼容性信息是否在标题、五点描述和后台关键词中充分覆盖
- 是否有不兼容的设备说明（减少退货风险）

#### 8. 主观属性 (subjective_properties) 🆕
产品的感性描述词是否丰富？是否触发了平台的主观属性匹配？
- 是否使用了感官描述词（soft, lightweight, sleek, compact, sturdy等）
- 是否有品质感知词（premium, professional-grade, military-grade等）
- 是否有美学/设计描述（modern design, minimalist, elegant等）
- 主观属性词是否与目标用户的偏好匹配
- 是否在标题和五点中自然融入了足够的主观属性词

### 卖家扩展2D

#### 9. 竞品差异化 (differentiation)
为什么不是买别人？独特卖点是否成立？
- 是否有明确的USP（独特卖点）
- 是否与竞品形成了可感知的差异
- 差异化是否在标题和首张图中就能体现
- 是否有技术/设计/品牌层面的壁垒

#### 10. 市场趋势 (market_trend) 🆕
产品是否顺应市场趋势？是否有增长潜力？
- 是否使用了当前热门/趋势关键词（如"2024 upgraded"、"AI-powered"等）
- 是否覆盖了季节性/节日性搜索词
- 产品定位是否符合品类发展方向
- 是否有新兴需求的关键词覆盖（如环保、可持续等）

## 输出要求
关键词硬性规则：
- 所有 keyword_coverage、ad_keywords、backend_keywords_addition 必须输出自然美式英语搜索词，不允许中文、不允许直译腔。
- 每个广告关键词必须增加 keyword_type 字段，值只能是 attribute / relationship / state_trigger。
- attribute=产品属性词，通常竞争激烈，只做基础覆盖。
- relationship=关系词，用于验证使用关系和场景承接。
- state_trigger=状态触发词，用于验证用户状态差距和痛点承接。
- 广告验证优先级：state_trigger > relationship > attribute；high_conversion 和 long_tail 中必须优先放 relationship/state_trigger 词。
- 必须单独识别多场景问题词：不是只列场景，也不是只列痛点，而是“使用场景 + 具体问题/结果”的自然美式英语搜索词。它们优先进入 missing_categories.scenario_problem 和 ad_keywords.long_tail/high_conversion。
- 必须主动最大化推理场景问题词：根据容量、尺寸、材质、兼容对象、使用时长、适用人群、风险承诺和图片场景，生成不少于6个候选场景问题词；已被Listing明确承接的放入 covered_categories.scenario_problem，未承接但有商业价值的放入 missing_categories.scenario_problem。禁止只复述标题原词。
- 运营建议必须提醒卖家：在标题、五点、图片文案、A+和后台词里自然承接高价值场景问题词，可以提升平台对商品意图的理解和推荐匹配概率，减少无效广告测试；不要承诺不投广告也一定获得推荐。

请以JSON格式返回（确保返回有效的JSON）：
{{
  "scores": {{
    "function_expression": 分数,
    "scenario_expression": 分数,
    "identity_fit": 分数,
    "psychology_benefit": 分数,
    "risk_elimination": 分数,
    "product_identity": 分数,
    "compatibility": 分数,
    "subjective_properties": 分数,
    "differentiation": 分数,
    "market_trend": 分数
  }},
  "analysis": {{
    "function_expression": "详细分析（2-3句话，指出具体问题和亮点）",
    "scenario_expression": "详细分析",
    "identity_fit": "详细分析",
    "psychology_benefit": "详细分析",
    "risk_elimination": "详细分析",
    "product_identity": "详细分析",
    "compatibility": "详细分析",
    "subjective_properties": "详细分析",
    "differentiation": "详细分析",
    "market_trend": "详细分析"
  }},
  "suggestions": {{
    "title_rewrite": "优化后的标题建议（完整标题）",
    "bullet_points_optimization": ["优化后的五点描述1", "优化后的五点描述2", "优化后的五点描述3", "优化后的五点描述4", "优化后的五点描述5"],
    "backend_keywords_addition": ["建议补充的后台关键词1", "建议补充的后台关键词2", "...最多10个"],
    "image_suggestions": ["主图优化建议", "副图1建议", "副图2建议"],
    "a_plus_suggestions": "A+内容优化方向建议"
  }},
  "keyword_coverage": {{
    "covered_categories": {{
      "core_category": ["已覆盖的核心品类词"],
      "function": ["已覆盖的功能词"],
      "scenario": ["已覆盖的场景词"],
      "audience": ["已覆盖的人群词"],
      "pain_point": ["已覆盖的痛点词"],
      "scenario_problem": ["已覆盖的场景问题词"],
      "long_tail": ["已覆盖的长尾词"]
    }},
    "missing_categories": {{
      "core_category": ["缺失的核心品类词"],
      "function": ["缺失的功能词"],
      "scenario": ["缺失的场景词"],
      "audience": ["缺失的人群词"],
      "pain_point": ["缺失的痛点词"],
      "scenario_problem": ["缺失的场景问题词"],
      "long_tail": ["缺失的长尾需求词"]
    }},
    "coverage_score": 覆盖率分数(0-100),
    "coverage_summary": "关键词覆盖情况总结"
  }},
  "ad_keywords": {{
    "high_conversion": [
      {{"keyword": "American English keyword", "keyword_type": "state_trigger/relationship/attribute", "match_type": "exact/phrase/broad", "intent": "购买意图描述", "competition": "high/medium/low", "priority": "P0/P1/P2"}}
    ],
    "traffic": [
      {{"keyword": "American English keyword", "keyword_type": "state_trigger/relationship/attribute", "match_type": "exact/phrase/broad", "intent": "搜索意图描述", "competition": "high/medium/low", "priority": "P0/P1/P2"}}
    ],
    "long_tail": [
      {{"keyword": "American English keyword", "keyword_type": "state_trigger/relationship/attribute", "match_type": "exact/phrase", "intent": "精准意图描述", "competition": "low/medium", "priority": "P1/P2"}}
    ],
    "negative": ["建议否定关键词1", "建议否定关键词2"],
    "ad_summary": "广告关键词策略总结"
  }},
  "elements": {{
    "title": {{"function_expression": 0-100, "scenario_expression": 0-100, "identity_fit": 0-100, "psychology_benefit": 0-100, "risk_elimination": 0-100, "product_identity": 0-100, "compatibility": 0-100, "subjective_properties": 0-100, "differentiation": 0-100, "market_trend": 0-100, "summary": "标题对10维诊断各维度的责任归因"}},
    "bullets": {{"function_expression": 0-100, "scenario_expression": 0-100, "identity_fit": 0-100, "psychology_benefit": 0-100, "risk_elimination": 0-100, "product_identity": 0-100, "compatibility": 0-100, "subjective_properties": 0-100, "differentiation": 0-100, "market_trend": 0-100, "summary": "五点描述对10维诊断各维度的责任归因"}},
    "images": {{"function_expression": 0-100, "scenario_expression": 0-100, "identity_fit": 0-100, "psychology_benefit": 0-100, "risk_elimination": 0-100, "product_identity": 0-100, "compatibility": 0-100, "subjective_properties": 0-100, "differentiation": 0-100, "market_trend": 0-100, "summary": "图片对10维诊断各维度的责任归因"}},
    "aplus": {{"function_expression": 0-100, "scenario_expression": 0-100, "identity_fit": 0-100, "psychology_benefit": 0-100, "risk_elimination": 0-100, "product_identity": 0-100, "compatibility": 0-100, "subjective_properties": 0-100, "differentiation": 0-100, "market_trend": 0-100, "summary": "A+内容对10维诊断各维度的责任归因"}},
    "backend": {{"function_expression": 0-100, "scenario_expression": 0-100, "identity_fit": 0-100, "psychology_benefit": 0-100, "risk_elimination": 0-100, "product_identity": 0-100, "compatibility": 0-100, "subjective_properties": 0-100, "differentiation": 0-100, "market_trend": 0-100, "summary": "后台属性对10维诊断各维度的责任归因"}}
  }},

⚠️ 关于elements中各要素的评分规则（极其重要，必须遵守）：
- 每个要素（title, bullets, images, aplus, backend）的每个维度分数必须是合理的非零值。
- **绝对禁止所有维度都给0分！** 即使某个要素的信息有限，你也必须根据已有信息进行合理推断和评估。
- 对于"aplus"（A+内容）：如果输入中标注了"A+内容已检测"或类似表述，说明该产品确实拥有A+内容。你必须：
  1. 根据产品类型、标题、五点描述等已有信息，推断A+内容可能的质量水平
  2. 给出合理的非零评分（通常有A+内容的产品，各维度至少应在30-60分范围）
  3. 在summary中说明"A+内容已检测到但未获取详细内容，评分基于产品特征推断"
- 对于"images"（图片）：如果有图片数量信息（如"共7张产品图片"），根据图片数量和产品类型推断评分
- 对于"backend"（后台属性）：即使后台关键词未提供，也应根据标题和五点描述中的关键词覆盖情况给出推断评分
- 评分参考标准：有该要素且质量好=70-100，有该要素但信息有限=30-60，完全没有该要素=10-25
  "market_estimates": {{
    "estimated_monthly_sales": 数字(根据评论数和类目估算月销量),
    "estimated_bsr_rank": 数字(根据销量和类目估算BSR排名)
  }},
  "analyzed_product_name": "你实际分析的产品名称（必须与'{title}'一致）",
  "overall_summary": "Listing整体诊断总结（3-5句话，概括核心问题和优化方向）"
}}

再次提醒：你正在分析的产品是 "{title}"。确保所有分析内容都关于这个产品，不要分析其他任何产品。
只返回JSON，不要返回其他内容。"""


COMPARE_PROMPT = """你是一位顶级亚马逊Listing竞品对比分析专家。
请对比以下Listing的诊断数据，生成对比分析报告。

## 我的Listing
标题: {my_title}
10维诊断评分: {my_scores}

## 竞品Listing列表
{competitor_info}

请以JSON格式返回对比分析（确保返回有效的JSON）：
{{
  "strengths": ["我的Listing优势1", "优势2", "优势3"],
  "weaknesses": ["我的Listing劣势1", "劣势2", "劣势3"],
  "opportunities": ["优化机会1", "优化机会2"],
  "threats": ["竞争威胁1", "竞争威胁2"],
  "dimension_comparison": {{
    "function_expression": "功能表达维度对比分析...",
    "scenario_expression": "场景表达维度对比分析...",
    "identity_fit": "身份认同维度对比分析...",
    "psychology_benefit": "心理收益维度对比分析...",
    "risk_elimination": "风险消除维度对比分析...",
    "product_identity": "产品身份维度对比分析...",
    "compatibility": "兼容搭配维度对比分析...",
    "subjective_properties": "主观属性维度对比分析...",
    "differentiation": "竞品差异化维度对比分析...",
    "market_trend": "市场趋势维度对比分析..."
  }},
  "keyword_gaps": ["我的Listing缺失但竞品覆盖的关键词1", "关键词2", "..."],
  "action_plan": ["优化行动1", "优化行动2", "优化行动3", "优化行动4"]
}}

只返回JSON，不要返回其他内容。"""


def _extract_json(text: str) -> dict:
    """Extract JSON from AI response text, handling markdown code blocks and truncated responses."""
    if not text or not text.strip():
        raise ValueError("Empty AI response")

    text = text.strip()

    # Remove markdown code blocks (```json ... ``` or ``` ... ```)
    if text.startswith("```"):
        lines = text.split("\n")
        # Skip first line (```json or ```)
        lines = lines[1:]
        # Remove trailing ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Also handle case where ``` appears at the end without newline
    if text.endswith("```"):
        text = text[:-3].strip()

    # Attempt 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: Find JSON object boundaries
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in AI response: {text[:200]}")

    end = text.rfind("}") + 1
    if end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    # Attempt 3: Handle truncated JSON - try to repair it
    json_text = text[start:]
    repaired = _repair_truncated_json(json_text)
    if repaired is not None:
        return repaired

    raise ValueError(f"Failed to parse AI response as JSON (possibly truncated): {text[:300]}")


def _repair_truncated_json(text: str) -> dict | None:
    """Attempt to repair truncated JSON by closing unclosed brackets and strings."""
    if not text.startswith("{"):
        return None

    # Strategy 1: Try closing unclosed structures
    for trim_len in range(0, min(500, len(text)), 1):
        candidate = text if trim_len == 0 else text[:-trim_len]

        # Count open/close brackets
        open_braces = candidate.count("{") - candidate.count("}")
        open_brackets = candidate.count("[") - candidate.count("]")

        # Check if we're inside a string (odd number of unescaped quotes)
        in_string = False
        i = len(candidate) - 1
        while i >= 0:
            if candidate[i] == '"' and (i == 0 or candidate[i-1] != '\\'):
                in_string = not in_string
                break
            i -= 1

        # Build closing sequence
        suffix = ""
        if in_string:
            suffix += '"'

        trimmed = candidate + suffix
        trimmed += "]" * max(0, open_brackets - (1 if in_string and suffix else 0))
        trimmed += "}" * max(0, open_braces)

        try:
            result = json.loads(trimmed)
            if isinstance(result, dict):
                logger.info(f"Successfully repaired truncated JSON (trimmed {trim_len} chars)")
                return result
        except json.JSONDecodeError:
            continue

    # Strategy 2: More aggressive - find the last complete key-value pair
    lines = text.split("\n")
    for end_line in range(len(lines) - 1, 0, -1):
        partial = "\n".join(lines[:end_line])
        open_braces = partial.count("{") - partial.count("}")
        open_brackets = partial.count("[") - partial.count("]")

        if open_braces <= 0 and open_brackets <= 0:
            continue

        partial = partial.rstrip().rstrip(",")

        suffix = "]" * max(0, open_brackets) + "}" * max(0, open_braces)
        try:
            result = json.loads(partial + suffix)
            if isinstance(result, dict):
                logger.info(f"Repaired truncated JSON by trimming to line {end_line}/{len(lines)}")
                return result
        except json.JSONDecodeError:
            continue

    return None


def _build_listing_text(listing: ListingInput) -> str:
    """Build a text representation of listing for display."""
    parts = []
    if listing.title:
        parts.append(f"标题: {listing.title}")
    if listing.item_highlights:
        parts.append(f"商品亮点: {listing.item_highlights}")
    if listing.bullet_points:
        parts.append(f"五点描述: {listing.bullet_points}")
    if listing.category:
        parts.append(f"类目: {listing.category}")
    if listing.price:
        parts.append(f"价格: {listing.price}")
    return " | ".join(parts) if parts else "未提供"


# All 10 diagnosis dimension keys used in the module attribution heatmap
_ELEMENT_DIM_KEYS = [
    "function_expression", "scenario_expression", "identity_fit", "psychology_benefit", "risk_elimination",
    "product_identity", "compatibility", "subjective_properties", "differentiation", "market_trend",
]


def _clean_listing_text(value: str, *, max_chars: int, keep_image_signal: bool = False) -> str:
    """Clean scraped Amazon text before sending it to the model."""
    text = str(value or "")
    text = text.replace("\x00", " ")
    text = re.sub(r"[\uFFFC\uFE0F]", " ", text)
    image_mentions = len(re.findall(r"(?:图片|image|img)\s*[:：]", text, flags=re.I))
    text = re.sub(r"\[?\s*(?:🖼️\s*)?(?:图片|image|img)\s*[:：][^\]\n]{0,120}\]?", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    if keep_image_signal and image_mentions:
        text = f"A+ content detected; image/text modules detected: {min(image_mentions, 30)}. {text}"
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "..."
    return text


def _sanitize_listing_for_ai(listing: ListingInput) -> ListingInput:
    """Limit noisy scrape fields so diagnosis is stable and fast."""
    return listing.model_copy(update={
        "title": _clean_listing_text(listing.title, max_chars=300),
        "bullet_points": _clean_listing_text(listing.bullet_points, max_chars=2600),
        "description": _clean_listing_text(listing.description, max_chars=1200),
        "a_plus_content": _clean_listing_text(listing.a_plus_content, max_chars=900, keep_image_signal=True),
        "backend_keywords": _clean_listing_text(listing.backend_keywords, max_chars=500),
        "main_image_description": _clean_listing_text(listing.main_image_description, max_chars=500, keep_image_signal=True),
        "category": _clean_listing_text(listing.category, max_chars=160),
        "price": _clean_listing_text(listing.price, max_chars=80),
        "brand": _clean_listing_text(listing.brand, max_chars=120),
    })


def _listing_content_fingerprint(listing: ListingInput) -> str:
    """Stable fingerprint for fields that should trigger a new diagnosis when changed."""
    payload = {
        "asin": (listing.asin or "").strip().upper(),
        "marketplace": (listing.marketplace or "").strip().upper(),
        "title": _clean_listing_text(listing.title, max_chars=500),
        "bullet_points": _clean_listing_text(listing.bullet_points, max_chars=3000),
        "description": _clean_listing_text(listing.description, max_chars=1400),
        "a_plus_content": _clean_listing_text(listing.a_plus_content, max_chars=1000, keep_image_signal=True),
        "backend_keywords": _clean_listing_text(listing.backend_keywords, max_chars=600),
        "main_image_description": _clean_listing_text(listing.main_image_description, max_chars=600, keep_image_signal=True),
        "category": _clean_listing_text(listing.category, max_chars=180),
        "price": str(listing.price or "").strip(),
        "rating": str(listing.rating or "").strip(),
        "review_count": str(listing.review_count or "").strip(),
        "bsr_rank": str(listing.bsr_rank or "").strip(),
        "image_count": str(listing.image_count or "").strip(),
        "aplus_image_count": str(listing.aplus_image_count or "").strip(),
        "has_video": bool(listing.has_video),
        "has_a_plus": bool(listing.has_a_plus),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _element_baseline_for_listing(listing: ListingInput, element_key: str) -> int:
    if element_key == "title":
        return 58 if listing.title else 18
    if element_key == "bullets":
        return 58 if listing.bullet_points else 18
    if element_key == "images":
        return 52 if (listing.main_image_description or listing.image_count or listing.has_video) else 20
    if element_key == "aplus":
        return 48 if (listing.a_plus_content or listing.has_a_plus) else 18
    if element_key == "backend":
        return 42 if listing.backend_keywords else 20
    return 25


def _ensure_element_scores(data: dict, listing: ListingInput) -> dict:
    """Ensure heatmap elements are always present and non-zero for display stability."""
    elements = data.get("elements") if isinstance(data.get("elements"), dict) else {}
    labels = {
        "title": "标题",
        "bullets": "五点描述",
        "images": "图片",
        "aplus": "A+内容",
        "backend": "后台属性",
    }
    for el_key in ("title", "bullets", "images", "aplus", "backend"):
        el_data = elements.get(el_key)
        if not isinstance(el_data, dict):
            el_data = {}
            elements[el_key] = el_data
        all_zero = all(float(el_data.get(dk, 0) or 0) <= 0 for dk in _ELEMENT_DIM_KEYS)
        if all_zero:
            baseline = _element_baseline_for_listing(listing, el_key)
            for dk in _ELEMENT_DIM_KEYS:
                el_data[dk] = max(float(el_data.get(dk, 0) or 0), baseline + _stable_score_offset(el_key, dk))
            if not el_data.get("summary"):
                el_data["summary"] = f"{labels[el_key]}评分由系统基于当前Listing内容稳定推断；AI未返回完整热力图时用于防止展示为空。"
    data["elements"] = elements
    return data


def _normalize_diagnosis_result(result: dict, listing: ListingInput) -> dict:
    """Fill required response fields when an AI/cached result is partial."""
    data = dict(result or {})
    data["scores"] = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    data["analysis"] = data.get("analysis") if isinstance(data.get("analysis"), dict) else {}
    data["suggestions"] = data.get("suggestions") if isinstance(data.get("suggestions"), dict) else {}
    data["keyword_coverage"] = data.get("keyword_coverage") if isinstance(data.get("keyword_coverage"), dict) else {}
    data["ad_keywords"] = data.get("ad_keywords") if isinstance(data.get("ad_keywords"), dict) else {}
    data["market_estimates"] = data.get("market_estimates") if isinstance(data.get("market_estimates"), dict) else {}
    data = _normalize_keyword_payload(data)
    data["diagnosis_mode"] = data.get("diagnosis_mode") or "listing_conversion_readiness"
    data = _ensure_scenario_problem_keywords(data, listing)
    data = _ensure_element_scores(data, listing)
    if not data.get("overall_summary"):
        weak_dims = [
            key for key, value in data["scores"].items()
            if isinstance(value, (int, float)) and value < 80
        ][:3]
        weak_text = "、".join(weak_dims) if weak_dims else "核心维度"
        data["overall_summary"] = f"系统已完成Listing诊断归一化。当前需优先检查{weak_text}，并结合模块归因图定位标题、五点、图片、A+或后台词的责任。"
    if not data.get("analyzed_product_name"):
        data["analyzed_product_name"] = listing.title or ""
    data["listing_title_rule"] = build_listing_title_rule(listing.title, listing.item_highlights)
    if not isinstance(data.get("buyer_language_translation"), dict):
        data["buyer_language_translation"] = empty_buyer_language_translation(_buyer_language_payload_from_listing(listing))
    data = _apply_market_reality_caps(data, listing)
    data = _align_listing_scores_with_canonical(data, listing)
    data["listing_health_analysis"] = _build_listing_health_analysis(data, listing)
    return data


def _numeric_score(value: Any) -> float:
    try:
        return max(0, min(100, float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _avg_scores(values: list[Any]) -> float:
    numbers = [_numeric_score(value) for value in values if value is not None]
    return round(sum(numbers) / len(numbers), 2) if numbers else 0


_LISTING_HEALTH_DIMS = [
    {
        "key": "buyer_clarity",
        "label": "买家看懂度",
        "max": 10,
        "legacy": ["product_identity", "function_expression"],
        "positions": ["标题", "主图"],
    },
    {
        "key": "demand_expression",
        "label": "需求表达",
        "max": 8,
        "legacy": ["function_expression", "scenario_expression"],
        "positions": ["标题", "主图", "副图1"],
    },
    {
        "key": "benefit_expression",
        "label": "收益表达",
        "max": 8,
        "legacy": ["psychology_benefit", "function_expression"],
        "positions": ["副图2", "A+"],
    },
    {
        "key": "scenario_expression",
        "label": "场景表达",
        "max": 8,
        "legacy": ["scenario_expression", "compatibility"],
        "positions": ["副图6", "A+05"],
    },
    {
        "key": "differentiation_expression",
        "label": "差异化表达",
        "max": 10,
        "legacy": ["differentiation"],
        "positions": ["副图3", "A+03"],
    },
    {
        "key": "trust_expression",
        "label": "信任表达",
        "max": 8,
        "legacy": ["risk_elimination", "market_trend"],
        "positions": ["副图4", "A+06", "Review", "QA"],
    },
    {
        "key": "risk_elimination",
        "label": "风险消除",
        "max": 8,
        "legacy": ["risk_elimination", "compatibility"],
        "positions": ["副图5", "A+04", "QA"],
    },
    {
        "key": "purchase_driver",
        "label": "购买驱动力",
        "max": 8,
        "legacy": ["psychology_benefit", "market_trend"],
        "positions": ["主图", "副图7", "Coupon", "Deal"],
    },
    {
        "key": "price_acceptance",
        "label": "价格承接",
        "max": 8,
        "legacy": ["market_trend", "risk_elimination"],
        "positions": ["全Listing"],
    },
    {
        "key": "visual_acceptance",
        "label": "视觉承接",
        "max": 8,
        "legacy": ["subjective_properties", "psychology_benefit"],
        "positions": ["主图", "副图", "A+", "视频"],
    },
    {
        "key": "traffic_acceptance",
        "label": "流量承接",
        "max": 8,
        "legacy": ["product_identity", "scenario_expression"],
        "positions": ["CTR", "CVR", "关键词匹配", "页面承接"],
    },
    {
        "key": "ad_acceptance",
        "label": "广告承接",
        "max": 8,
        "legacy": ["function_expression", "risk_elimination", "differentiation"],
        "positions": ["整体承接能力", "整体转化能力", "整体竞争力"],
    },
]


_LISTING_POSITION_META = [
    ("标题", "卖什么"),
    ("主图", "卖什么"),
    ("副图1", "解决什么问题"),
    ("副图2", "买完得到什么"),
    ("副图3", "为什么买你"),
    ("副图4", "是否相信"),
    ("副图5", "是否敢买"),
    ("副图6", "在哪里/什么时候/谁使用"),
    ("副图7", "购买驱动力"),
    ("A+01", "暂无"),
    ("A+02", "暂无"),
    ("A+03", "为什么买你"),
    ("A+04", "是否敢买"),
    ("A+05", "在哪里/什么时候/谁使用"),
    ("A+06", "是否相信"),
    ("A+07", "暂无"),
    ("Review", "是否相信"),
    ("QA", "是否敢买"),
]


def _safe_text(value: Any) -> str:
    if value is None:
        return "暂无"
    if isinstance(value, str):
        return value.strip() or "暂无"
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        text = "；".join(_safe_text(item) for item in value if _safe_text(item) != "暂无")
        return text or "暂无"
    if isinstance(value, dict):
        parts = []
        for item in value.values():
            text = _safe_text(item)
            if text != "暂无":
                parts.append(text)
        return "；".join(parts) or "暂无"
    return "暂无"


def _element_average(elements: dict, element_key: str) -> float:
    item = elements.get(element_key) if isinstance(elements, dict) else {}
    if not isinstance(item, dict):
        return 0
    return _avg_scores([item.get(key) for key in _ELEMENT_DIM_KEYS])


def _position_score(elements: dict, position: str) -> float:
    if position == "标题":
        return _element_average(elements, "title")
    if position in {"主图", "副图", "副图1", "副图2", "副图3", "副图4", "副图5", "副图6", "副图7", "视频"}:
        return _element_average(elements, "images")
    if position.startswith("A+") or position == "A+":
        return _element_average(elements, "aplus")
    if position == "全Listing":
        return _avg_scores([
            _element_average(elements, "title"),
            _element_average(elements, "bullets"),
            _element_average(elements, "images"),
            _element_average(elements, "aplus"),
            _element_average(elements, "backend"),
        ])
    return 0


_POSITION_DIMENSION_MAP: dict[str, list[str]] = {
    "title": ["product_identity", "function_expression", "scenario_expression", "compatibility"],
    "highlights": ["differentiation", "psychology_benefit", "function_expression", "subjective_properties"],
    "bullets": ["function_expression", "psychology_benefit", "risk_elimination", "differentiation", "compatibility"],
    "main_image": ["product_identity", "differentiation", "subjective_properties"],
    "secondary_1": ["function_expression", "differentiation", "psychology_benefit"],
    "secondary_2": ["scenario_expression", "identity_fit"],
    "secondary_3": ["compatibility", "function_expression", "risk_elimination"],
    "secondary_4": ["differentiation", "product_identity", "subjective_properties"],
    "secondary_5": ["risk_elimination", "psychology_benefit"],
    "secondary_6": ["compatibility", "risk_elimination", "function_expression"],
    "aplus_1": ["psychology_benefit", "risk_elimination"],
    "aplus_2": ["function_expression", "product_identity"],
    "aplus_3": ["scenario_expression", "identity_fit"],
    "aplus_4": ["psychology_benefit", "subjective_properties", "risk_elimination"],
    "aplus_5": ["differentiation", "product_identity"],
    "aplus_6": ["compatibility", "risk_elimination"],
    "aplus_7": ["risk_elimination", "psychology_benefit"],
    "aplus_8": ["function_expression", "compatibility", "risk_elimination"],
    "aplus_9": ["risk_elimination", "psychology_benefit"],
}


def _clamp_score(value: Any) -> int:
    try:
        number = round(float(value or 0))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, number))


def _avg_dimension_scores(scores: dict, keys: list[str]) -> int:
    values = [_clamp_score(scores.get(key)) for key in keys if _clamp_score(scores.get(key)) > 0]
    return _clamp_score(sum(values) / len(values)) if values else 0


def _parse_count(value: Any) -> int:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else 0


def _actual_listing_image_count(listing: ListingInput) -> int:
    return min(9, max(len(listing.image_urls or []), _parse_count(listing.image_count)))


def _actual_aplus_image_count(listing: ListingInput) -> int:
    text_count = re.search(r"A\+图片数[:：]\s*(\d+)", listing.a_plus_content or "", re.I)
    return max(
        len(listing.aplus_image_urls or []),
        _parse_count(listing.aplus_image_count),
        int(text_count.group(1)) if text_count else 0,
    )


def _split_bullets_for_position(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"\n+", value or "") if item.strip()]


def _position_content_exists(listing: ListingInput, module: str, index: int = 0) -> bool:
    if module == "title":
        return bool((listing.title or "").strip())
    if module == "highlights":
        return bool((listing.item_highlights or "").strip())
    if module == "bullets":
        return bool(_split_bullets_for_position(listing.bullet_points))
    if module == "main_image":
        return bool((listing.image_urls or [None])[0] if listing.image_urls else listing.main_image_description)
    if module == "secondary_images":
        return bool(len(listing.image_urls or []) > index)
    if module == "a_plus":
        return bool(len(listing.aplus_image_urls or []) >= index or listing.a_plus_content)
    return False


def _position_source_facts(listing: ListingInput, module: str, index: int = 0) -> dict[str, Any]:
    if module == "title":
        return {
            "source": "amazon_listing_data",
            "field": "title",
            "content_present": bool((listing.title or "").strip()),
            "text": listing.title or "暂无",
        }
    if module == "highlights":
        return {
            "source": "amazon_listing_data",
            "field": "item_highlights",
            "content_present": bool((listing.item_highlights or "").strip()),
            "text": listing.item_highlights or "暂无",
        }
    if module == "bullets":
        bullet_items = _split_bullets_for_position(listing.bullet_points)
        return {
            "source": "amazon_listing_data",
            "field": "bullet_points",
            "content_present": bool(bullet_items),
            "bullet_count": len(bullet_items),
            "text": listing.bullet_points or "暂无",
        }
    if module == "main_image":
        url = (listing.image_urls or [""])[0] if listing.image_urls else ""
        return {
            "source": "amazon_listing_data",
            "field": "image_urls[0]",
            "content_present": bool(url or listing.main_image_description),
            "image_url": url or "暂无",
            "text": listing.main_image_description or "暂无",
        }
    if module == "secondary_images":
        url = listing.image_urls[index] if len(listing.image_urls or []) > index else ""
        return {
            "source": "amazon_listing_data",
            "field": f"image_urls[{index}]",
            "content_present": bool(url),
            "image_url": url or "暂无",
        }
    if module == "a_plus":
        image_index = max(0, index - 1)
        url = listing.aplus_image_urls[image_index] if len(listing.aplus_image_urls or []) > image_index else ""
        return {
            "source": "amazon_listing_data",
            "field": f"aplus_image_urls[{image_index}]",
            "content_present": bool(url or listing.a_plus_content),
            "image_url": url or "暂无",
            "text": listing.a_plus_content or "暂无",
        }
    return {"source": "amazon_listing_data", "content_present": False}


def _violation_penalty(amazon_compliance: dict, module: str) -> int:
    module_keys = {
        "title": ["title", "标题"],
        "highlights": ["highlight", "亮点"],
        "bullets": ["bullet", "五点", "描述"],
        "main_image": ["image", "main_image", "主图", "图片"],
        "secondary_images": ["image", "secondary", "副图", "图片"],
        "a_plus": ["a+", "aplus", "a_plus", "A+"],
    }.get(module, [])
    violations = amazon_compliance.get("violations") if isinstance(amazon_compliance, dict) else []
    risk = 0
    for violation in violations or []:
        if not isinstance(violation, dict):
            continue
        text = f"{violation.get('module', '')} {violation.get('rule_type', '')} {violation.get('category', '')}".lower()
        if any(str(key).lower() in text for key in module_keys):
            risk = max(risk, _clamp_score(violation.get("risk_score")))
    return min(40, risk)


def _amazon_position_rule_score(listing: ListingInput, data: dict, module: str, index: int = 0) -> int:
    if not _position_content_exists(listing, module, index):
        return 0
    rule = data.get("listing_title_rule") if isinstance(data.get("listing_title_rule"), dict) else {}
    score = 85
    if module == "title":
        score = 100 if rule.get("title_compliance_status") in {None, "", "compliant"} else 70
        if _clamp_score(rule.get("title_char_count")) > _clamp_score(rule.get("title_max_chars") or 75):
            score = min(score, 70)
    elif module == "highlights":
        score = 100 if rule.get("highlights_status") in {None, "", "compliant"} else 70
        if _clamp_score(rule.get("item_highlights_char_count")) > _clamp_score(rule.get("item_highlights_max_chars") or 125):
            score = min(score, 70)
    elif module == "bullets":
        count = len(_split_bullets_for_position(listing.bullet_points))
        score = 90 if count >= 5 else 70 if count > 0 else 0
    return _clamp_score(score - _violation_penalty(data.get("amazon_compliance") or {}, module))


def _buyer_language_has_text(value: Any) -> bool:
    if isinstance(value, list):
        return any(_buyer_language_has_text(item) for item in value)
    text = str(value or "").strip()
    return bool(text and text not in {"暂无", "待录入"})


def _buyer_language_position_score(data: dict, module: str, listing: ListingInput, index: int = 0) -> int:
    if not _position_content_exists(listing, module, index):
        return 0
    translation = data.get("buyer_language_translation") if isinstance(data.get("buyer_language_translation"), dict) else {}
    buyer_language = translation.get("buyer_language") if isinstance(translation.get("buyer_language"), dict) else {}
    graph = translation.get("human_nature_graph") or data.get("human_nature_graph") or (data.get("judgment_system") or {}).get("human_nature_graph")
    has_graph = isinstance(graph, dict) and bool(graph)
    if module == "title":
        has_translation = _buyer_language_has_text(buyer_language.get("title"))
    elif module in {"highlights", "bullets"}:
        has_translation = _buyer_language_has_text(buyer_language.get("bullet_points"))
    elif module == "a_plus":
        has_translation = _buyer_language_has_text(buyer_language.get("a_plus_desc")) or _buyer_language_has_text(buyer_language.get("image_texts"))
    else:
        has_translation = _buyer_language_has_text(buyer_language.get("image_texts"))
    if has_graph and has_translation:
        return 100
    if has_graph or has_translation:
        return 70
    return 0


def _position_ad_validation(data: dict, module: str) -> dict:
    plan = data.get("ad_validation_plan") if isinstance(data.get("ad_validation_plan"), dict) else {}
    items = plan.get("validation_items") if isinstance(plan.get("validation_items"), list) else []
    module_index = {"title": 0, "highlights": 0, "main_image": 1, "secondary_images": 2, "bullets": 3, "a_plus": 4}.get(module, 0)
    item = items[module_index] if module_index < len(items) and isinstance(items[module_index], dict) else {}
    keywords = item.get("ad_test_keywords") or item.get("validation_keywords") or item.get("keywords") or (item.get("ad_action") or {}).get("keywords") or []
    if not keywords:
        collected_keywords: list[str] = []
        _collect_keywords((data.get("ad_keywords") or {}).get("high_conversion"), collected_keywords)
        _collect_keywords((data.get("ad_keywords") or {}).get("traffic"), collected_keywords)
        _collect_keywords((data.get("ad_keywords") or {}).get("long_tail"), collected_keywords)
        _collect_keywords((data.get("suggestions") or {}).get("backend_keywords_addition"), collected_keywords)
        coverage = data.get("keyword_coverage") if isinstance(data.get("keyword_coverage"), dict) else {}
        missing = coverage.get("missing_categories") if isinstance(coverage.get("missing_categories"), dict) else {}
        for values in missing.values():
            _collect_keywords(values, collected_keywords)
        keywords = collected_keywords[:8]
    hypothesis = _safe_text(item.get("hypothesis"))
    if re.search(r"Listing补强|对应搜索词点击|对应搜索词.*转化|点击和转化应提升|验证Listing是否承接", hypothesis):
        hypothesis = "暂无"
    return {
        "hypothesis": hypothesis,
        "keywords": keywords,
        "metrics": ["CTR", "CVR", "CPC", "ACOS"] if keywords else [],
    }


def _keyword_text(value: Any) -> str:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value.strip().lower())
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("keyword", "term", "phrase", "query", "text", "value"):
            text = _keyword_text(value.get(key))
            if text:
                return text
    return ""


def _collect_keywords(value: Any, out: list[str]) -> None:
    if not value:
        return
    if isinstance(value, list):
        for item in value:
            _collect_keywords(item, out)
        return
    text = _keyword_text(value)
    if text and text not in out:
        out.append(text)


def _position_problem_from_scores(scores: dict[str, int]) -> str:
    return "暂无"


def _build_listing_position_diagnosis(data: dict, listing: ListingInput) -> dict:
    scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    alignment = (data.get("judgment_system") or {}).get("alignment_scores") if isinstance(data.get("judgment_system"), dict) else {}
    platform_score = _clamp_score((alignment or {}).get("platform_semantic_alignment"))

    def row(label: str, module: str, key: str, focus: str, index: int = 0) -> dict:
        dimension_keys = _POSITION_DIMENSION_MAP.get(key) or _POSITION_DIMENSION_MAP.get(module) or []
        mapped_score = _avg_dimension_scores(scores, dimension_keys)
        cosmo_score = _clamp_score(mapped_score * 0.7 + platform_score * 0.3) if platform_score and mapped_score else mapped_score
        cross_scores = {
            "amazon_rule_score": _amazon_position_rule_score(listing, data, module, index),
            "cosmo_alignment_score": cosmo_score,
            "buyer_language_score": _buyer_language_position_score(data, module, listing, index),
        }
        final_score = min(cross_scores.values()) if cross_scores else 0
        return {
            "id": f"{module}-{index}",
            "label": label,
            "module": module,
            "position_key": key,
            "index": index,
            "focus": focus,
            "source_facts": _position_source_facts(listing, module, index),
            **cross_scores,
            "final_score": final_score,
            "status": "合格" if final_score >= 80 else "待优化",
            "dimension_keys": dimension_keys,
            "problem": _position_problem_from_scores(cross_scores),
            "optimization_suggestion": "暂无",
            "ad_validation": _position_ad_validation(data, module),
        }

    positions = [
        row("标题", "title", "title", "title"),
        row("亮点差异化", "highlights", "highlights", "item-highlights"),
        row("5点描述", "bullets", "bullets", "bullets"),
    ]
    image_count = _actual_listing_image_count(listing)
    if image_count > 0:
        positions.append(row("主图", "main_image", "main_image", "main-images", 0))
        for image_index in range(1, image_count):
            positions.append(row(f"副图{image_index}", "secondary_images", f"secondary_{image_index}", "main-images", image_index))
    for aplus_index in range(1, min(_actual_aplus_image_count(listing), 9) + 1):
        positions.append(row(f"A+图{aplus_index}", "a_plus", f"aplus_{aplus_index}", "aplus-images", aplus_index))

    return {
        "basis": "amazon_rule_cosmo_buyer_language_position_cross",
        "threshold": 80,
        "positions": positions,
    }


def _build_listing_health_analysis(data: dict, listing: ListingInput) -> dict:
    existing = data.get("listing_health_analysis")
    if isinstance(existing, dict) and existing.get("dimensions"):
        return existing

    scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    analysis = data.get("analysis") if isinstance(data.get("analysis"), dict) else {}
    suggestions = data.get("suggestions") if isinstance(data.get("suggestions"), dict) else {}
    elements = data.get("elements") if isinstance(data.get("elements"), dict) else {}

    dimensions = []
    for item in _LISTING_HEALTH_DIMS:
        legacy_score = _avg_scores([scores.get(key) for key in item["legacy"]])
        score = round((legacy_score / 100) * item["max"], 1)
        evidence_texts = [_safe_text(analysis.get(key)) for key in item["legacy"]]
        evidence = "；".join(text for text in evidence_texts if text != "暂无") or "暂无"
        position_scores = [
            {"position": position, "score": round(_position_score(elements, position), 1) or "暂无"}
            for position in item["positions"]
        ]
        dimensions.append(
            {
                "key": item["key"],
                "label": item["label"],
                "max_score": item["max"],
                "score": score,
                "problem_position": "、".join(item["positions"]),
                "analysis": evidence,
                "optimization_suggestion": _safe_text(suggestions.get("title_rewrite") if item["key"] in {"buyer_clarity", "demand_expression"} else suggestions.get("a_plus_suggestions") or suggestions.get("image_suggestions")),
                "position_scores": position_scores,
            }
        )

    total_score = round(sum(float(item.get("score") or 0) for item in dimensions), 1)
    weak_dimensions = sorted(dimensions, key=lambda item: float(item.get("score") or 0))[:5]

    problem_sources = []
    for item in weak_dimensions:
        sources = item.get("position_scores") or []
        problem_sources.append(
            {
                "dimension": item["label"],
                "score": item["score"],
                "problem_sources": sources,
                "reason": item.get("analysis") or "暂无",
                "suggestion": item.get("optimization_suggestion") or "暂无",
            }
        )

    position_scores = []
    for position, responsibility in _LISTING_POSITION_META:
        raw_score = _position_score(elements, position)
        issue = "暂无"
        recommendation = "暂无"
        if position == "标题":
            issue = _safe_text(analysis.get("product_identity") or analysis.get("function_expression"))
            recommendation = _safe_text(suggestions.get("title_rewrite"))
        elif position.startswith("副图") or position == "主图":
            issue = _safe_text(analysis.get("psychology_benefit") or analysis.get("scenario_expression"))
            recommendation = _safe_text(suggestions.get("image_suggestions"))
        elif position.startswith("A+"):
            issue = _safe_text(analysis.get("differentiation") or analysis.get("risk_elimination"))
            recommendation = _safe_text(suggestions.get("a_plus_suggestions"))
        elif position in {"Review", "QA"}:
            issue = _safe_text(analysis.get("risk_elimination"))
        position_scores.append(
            {
                "position": position,
                "responsibility": responsibility,
                "score": round(raw_score, 1) if raw_score else "暂无",
                "problem": issue,
                "optimization_suggestion": recommendation,
            }
        )

    priority_labels = [
        ("TOP1", "影响转化率最大"),
        ("TOP2", "影响点击率最大"),
        ("TOP3", "影响广告效果最大"),
        ("TOP4", "影响价格承接最大"),
        ("TOP5", "影响购买决策最大"),
    ]
    priority_issues = []
    for index, (rank, impact) in enumerate(priority_labels):
        weak = weak_dimensions[index] if index < len(weak_dimensions) else {}
        priority_issues.append(
            {
                "rank": rank,
                "impact": impact,
                "dimension": weak.get("label") or "暂无",
                "position": weak.get("problem_position") or "暂无",
                "problem": weak.get("analysis") or "暂无",
                "action": weak.get("optimization_suggestion") or "暂无",
            }
        )

    dimension_score_map = {item["label"]: item["score"] for item in dimensions}
    biggest = weak_dimensions[0] if weak_dimensions else {}
    final_conclusion = {
        "current_biggest_problem": biggest.get("label") or "暂无",
        "problem_image": next((p for p in (biggest.get("problem_position") or "").split("、") if "图" in p), "暂无"),
        "problem_aplus_module": next((p for p in (biggest.get("problem_position") or "").split("、") if p.startswith("A+")), "暂无"),
        "conversion_reason": biggest.get("analysis") or "暂无",
        "expected_ctr_decline": "暂无",
        "expected_cvr_decline": "暂无",
        "expected_ad_efficiency_decline": "暂无",
        "immediate_modification": biggest.get("optimization_suggestion") or "暂无",
        "priority": "★★★★★" if total_score < 70 else "★★★★",
        "expected_benefits": ["提升点击率", "提升转化率", "降低广告浪费"],
    }

    return {
        "total_score": total_score,
        "dimensions": dimensions,
        "problem_sources": problem_sources,
        "position_scores": position_scores,
        "priority_issues": priority_issues,
        "business_conclusion": {
            "listing_health": total_score,
            **dimension_score_map,
            "综合评分": total_score,
        },
        "final_conclusion": final_conclusion,
    }


async def _build_listing_opc_v5_execution(
    data: dict,
    listing: ListingInput,
    user_id: str,
    db: AsyncSession,
    source_record_id: int | None = None,
) -> dict:
    scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    integrity = data.get("data_integrity") if isinstance(data.get("data_integrity"), dict) else {}
    source_coverage = integrity.get("source_coverage") if isinstance(integrity.get("source_coverage"), dict) else {}
    diagnosis_confidence = data.get("diagnosis_confidence") if isinstance(data.get("diagnosis_confidence"), dict) else {}
    causal_confidence = diagnosis_confidence.get("causal_conversion_alignment") if isinstance(diagnosis_confidence.get("causal_conversion_alignment"), dict) else {}
    causal = data.get("causal_diagnosis") if isinstance(data.get("causal_diagnosis"), dict) else {}
    keyword_causality = causal.get("keyword_causality") if isinstance(causal.get("keyword_causality"), dict) else {}
    has_ad_evidence = _numeric_score(source_coverage.get("advertising")) > 0

    listing_score = _avg_scores(
        [
            scores.get("function_expression"),
            scores.get("scenario_expression"),
            scores.get("psychology_benefit"),
            scores.get("risk_elimination"),
            scores.get("product_identity"),
            scores.get("compatibility"),
        ]
    )
    evidence_metrics = {}
    if has_ad_evidence:
        evidence_metrics = {
            "转化": _numeric_score(causal_confidence.get("score")),
            "ROI": _numeric_score(keyword_causality.get("readiness_score")),
        }
    source_id = str(source_record_id or listing.asin or listing.title or "")
    return await CoreEngineBusinessAdapter(db, user_id).evaluate_cycle(
        source_type="listing_diagnosis",
        source_id=source_id,
        opportunity_id=listing.asin or source_id or "待录入",
        opportunity_score=listing_score,
        risk_score=max(0, 100 - listing_score),
        information_gain=_numeric_score(source_coverage.get("advertising")) if has_ad_evidence else 0,
        evidence_count=1 if has_ad_evidence else 0,
        evidence_quality=_numeric_score(integrity.get("score")) if has_ad_evidence else 0,
        sample_size=30 if has_ad_evidence else 0,
        conversion_signal=_numeric_score(causal_confidence.get("score")) if has_ad_evidence else 0,
        consistency=_numeric_score(keyword_causality.get("readiness_score")) if has_ad_evidence else 0,
        statistical_confidence=_numeric_score(integrity.get("score")) if has_ad_evidence else 0,
        metrics=evidence_metrics,
    )


def _parse_metric_int(value: str | int | float | None) -> int:
    if value is None:
        return 0
    match = re.search(r"\d+", str(value).replace(",", ""))
    return int(match.group(0)) if match else 0


def _count_listing_bullets(value: str | None) -> int:
    if not value:
        return 0
    return len([item for item in re.split(r"[\n;；]+", value) if item.strip()])


def _cap_score_map(scores: dict, caps: dict[str, int], reasons: list[str]) -> None:
    for key, cap in caps.items():
        current = scores.get(key)
        if isinstance(current, (int, float)) and current > cap:
            scores[key] = cap
    reasons[:] = [reason for reason in reasons if reason]


def _apply_market_reality_caps(data: dict, listing: ListingInput) -> dict:
    """Keep content scores from drifting into market-proof claims.

    Local browser capture improves evidence completeness, but the 10-dimension score is
    a sell-through hypothesis. It must be capped by review, BSR, bullet quality
    and backend/ad validation evidence so a complete page is not mistaken for a
    proven high-conversion listing.
    """
    cap_meta = data.get("market_reality_caps")
    if isinstance(cap_meta, dict) and cap_meta.get("applied"):
        return data

    scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    if not scores:
        return data

    review_count = _parse_metric_int(listing.review_count)
    bsr_rank = _parse_metric_int(listing.bsr_rank)
    bullet_count = _count_listing_bullets(listing.bullet_points)
    has_backend = bool((listing.backend_keywords or "").strip())
    has_price = _has_required_price(listing.price)
    diagnosis_mode = str(data.get("diagnosis_mode") or "").strip().lower()
    is_new_launch = _is_new_launch_mode(diagnosis_mode) or (
        not _is_mature_listing_mode(diagnosis_mode) and _is_new_launch_listing(listing)
    )
    reasons: list[str] = []

    if is_new_launch:
        _cap_score_map(
            scores,
            {
                "risk_elimination": 68,
                "psychology_benefit": 72,
                "differentiation": 74,
                "market_trend": 62,
                "causal_state_gap_coverage": 78,
                "keyword_validation_readiness": 76,
            },
            reasons,
        )
        reasons.append("无价格、无评论、无BSR/销售记录，系统定位为新品上架承接诊断，不按成熟销量模型判断。")

    if bullet_count < 3:
        _cap_score_map(
            scores,
            {
                "function_expression": 70,
                "scenario_expression": 68,
                "psychology_benefit": 68,
                "risk_elimination": 70,
                "differentiation": 68,
            },
            reasons,
        )
        reasons.append(f"五点仅识别 {bullet_count}/5，不能按完整购买理由给高分。")
    elif bullet_count < 5:
        _cap_score_map(scores, {"psychology_benefit": 78, "risk_elimination": 78, "differentiation": 76}, reasons)
        reasons.append(f"五点仅识别 {bullet_count}/5，转化承接仍需补齐。")

    if not has_price:
        _cap_score_map(
            scores,
            {
                "risk_elimination": 74,
                "differentiation": 76,
                "market_trend": 68,
                "psychology_benefit": 78,
            },
            reasons,
        )
        reasons.append("价格缺失不阻断新品承接诊断，但不能判断价格承接和广告承受力。")

    if 0 < review_count < 100:
        _cap_score_map(
            scores,
            {
                "psychology_benefit": 78,
                "risk_elimination": 76,
                "differentiation": 76,
                "market_trend": 74,
            },
            reasons,
        )
        reasons.append(f"评论数 {review_count} 低于100，信任和趋势不能按成熟大卖家评分。")
    elif review_count == 0:
        _cap_score_map(scores, {"psychology_benefit": 72, "risk_elimination": 70, "market_trend": 68}, reasons)
        reasons.append("缺少评论数，不能证明信任承接和市场趋势。")

    if bsr_rank > 10000:
        _cap_score_map(
            scores,
            {
                "market_trend": 72,
                "differentiation": 74,
                "scenario_expression": 82,
                "psychology_benefit": 78,
            },
            reasons,
        )
        reasons.append(f"BSR #{bsr_rank} 不属于强势销量段，市场趋势和差异化需保守。")
    elif bsr_rank == 0:
        _cap_score_map(scores, {"market_trend": 72, "differentiation": 76}, reasons)
        reasons.append("缺少BSR，不能直接证明自然销量和市场趋势。")

    if not has_backend:
        _cap_score_map(scores, {"compatibility": 82, "product_identity": 86, "market_trend": 78}, reasons)
        reasons.append("后台Search Terms未提供，平台语义对齐不能按满链路确认。")

    if reasons:
        data["scores"] = scores
        data["market_reality_caps"] = {
            "applied": True,
            "review_count": review_count,
            "bsr_rank": bsr_rank,
            "bullet_count": bullet_count,
            "has_price": has_price,
            "is_new_launch": is_new_launch,
            "has_backend_keywords": has_backend,
            "reasons": reasons,
        }
        confidence = data.get("diagnosis_confidence") if isinstance(data.get("diagnosis_confidence"), dict) else {}
        overall_conf = confidence.get("overall") if isinstance(confidence.get("overall"), dict) else {}
        if not has_price or review_count == 0 or bsr_rank == 0:
            confidence["overall"] = {
                **overall_conf,
                "level": "medium" if bullet_count >= 3 and not is_new_launch else "low",
                "reason": "新品上架承接诊断已生成；市场证据缺失，需用首轮小预算广告验证。" if is_new_launch else "Listing承接诊断已生成；价格/评论/BSR等市场证据缺失，市场验证置信度降低。",
            }
            data["diagnosis_confidence"] = confidence
            data["data_integrity"] = {
                **(data.get("data_integrity") if isinstance(data.get("data_integrity"), dict) else {}),
                "level": "low" if is_new_launch else "medium",
                "reason": "新品上架：承接字段可诊断，但无市场验证证据，不能当作成熟销量判断。" if is_new_launch else "承接字段可诊断；市场证据不足，不能当作成熟销量验证。",
            }
        prefix = ("新品上架承接闸门已校准评分：" if is_new_launch else "市场现实闸门已校准评分：") + "；".join(reasons[:3])
        data["overall_summary"] = f"{prefix}。{data.get('overall_summary', '')}".strip()
    return data


def _align_listing_scores_with_canonical(data: dict, listing: ListingInput) -> dict:
    """Use the same Amazon/COSMO 10D basis as ASIN and competitor diagnosis."""
    scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    if not scores:
        return data
    product_context = listing.model_dump()
    if data.get("diagnosis_mode"):
        product_context["diagnosis_mode"] = data.get("diagnosis_mode")
    aligned = CosmoOperatorAgent.align_scores(scores, product_context)
    data["scores"] = aligned["canonical_scores"]
    data["canonical_10d_scores"] = aligned["canonical_scores"]
    data["score_aliases"] = aligned["scores"]
    data["score_basis"] = "amazon_skill_10d_canonical"
    data["market_reality_caps"] = aligned["market_reality_caps"]
    return data


async def _find_shared_asin_score_snapshot(
    listing: ListingInput,
    db: AsyncSession,
    user_id: str,
    diagnosis_mode: str = "listing_conversion_readiness",
) -> dict | None:
    """Reuse the same 10D score base when the ASIN and captured evidence match."""
    asin = (listing.asin or "").strip().upper()
    if not asin:
        return None
    from sqlalchemy import select
    from models.asin_analyses import Asin_analyses

    result = await db.execute(
        select(Asin_analyses)
        .where(Asin_analyses.user_id == user_id, Asin_analyses.asin == asin, Asin_analyses.marketplace == listing.marketplace)
        .where(Asin_analyses.analysis_report.isnot(None), Asin_analyses.product_data.isnot(None))
        .order_by(Asin_analyses.id.desc())
        .limit(10)
    )
    for record in result.scalars().all():
        try:
            product_data = json.loads(record.product_data or "{}")
            analysis_report = json.loads(record.analysis_report or "{}")
        except Exception:
            continue
        product_data.setdefault("title", record.product_title or "")
        similarity = product_evidence_similarity(listing.model_dump(), product_data)
        if similarity.get("score", 0) < 0.62:
            continue
        product_context = {**product_data, **listing.model_dump(), "diagnosis_mode": diagnosis_mode}
        aligned = CosmoOperatorAgent.align_scores(
            analysis_report.get("canonical_10d_scores") or analysis_report.get("scores"),
            product_context,
        )
        if not any(aligned["canonical_scores"].values()):
            continue
        return {
            "source": "asin_analysis",
            "source_id": record.id,
            "canonical_scores": aligned["canonical_scores"],
            "score_aliases": aligned["scores"],
            "market_reality_caps": aligned["market_reality_caps"],
            "similarity": similarity,
        }
    return None


async def _apply_shared_asin_score_snapshot(
    data: dict,
    listing: ListingInput,
    db: AsyncSession,
    user_id: str,
) -> dict:
    snapshot = await _find_shared_asin_score_snapshot(
        listing,
        db,
        user_id,
        str(data.get("diagnosis_mode") or "listing_conversion_readiness"),
    )
    if not snapshot:
        return data
    data["scores"] = snapshot["canonical_scores"]
    data["canonical_10d_scores"] = snapshot["canonical_scores"]
    data["score_aliases"] = snapshot["score_aliases"]
    data["score_basis"] = "amazon_skill_10d_canonical_shared_asin_snapshot"
    data["shared_score_source"] = {
        "type": snapshot["source"],
        "id": snapshot["source_id"],
        "similarity": snapshot["similarity"],
    }
    data["market_reality_caps"] = snapshot["market_reality_caps"]
    return data


def _derive_fallback_insights(listing: ListingInput) -> dict:
    return {
        "product_identity": "",
        "covered": {k: [] for k in ("core_category", "function", "scenario", "audience", "pain_point", "scenario_problem", "long_tail")},
        "missing": {k: [] for k in ("core_category", "function", "scenario", "audience", "pain_point", "scenario_problem", "long_tail")},
        "ad_keywords": {"high_conversion": [], "traffic": [], "long_tail": []},
        "state_keywords": [],
        "suggestions": [],
        "score_adjust": 0,
        "price_note": "暂无",
    }


def _fallback_listing_diagnosis(listing: ListingInput, reason: str = "") -> dict:
    """Return an empty diagnosis when the model call fails."""
    scores = {key: 0 for key in _DIMENSION_KEYS}
    analysis = {key: "暂无" for key in _DIMENSION_KEYS}
    elements = {
        key: {**{dim: 0 for dim in _ELEMENT_DIM_KEYS}, "summary": "暂无"}
        for key in ("title", "bullets", "aplus", "images", "backend", "price")
    }
    return {
        "scores": scores,
        "analysis": analysis,
        "suggestions": {
            "high_priority": [
                "暂无",
            ],
            "medium_priority": [],
            "low_priority": [],
            "backend_keywords_addition": [],
        },
        "keyword_coverage": {
            "covered_categories": {},
            "missing_categories": {},
            "covered_keywords": [],
            "missing_keywords": [],
            "coverage_score": 0,
            "coverage_summary": "暂无",
        },
        "ad_keywords": {
            "high_conversion": [],
            "traffic": [],
            "long_tail": [],
            "negative_keywords": [],
            "negative": [],
            "ad_summary": "暂无",
        },
        "elements": elements,
        "market_estimates": {},
        "overall_summary": "暂无" if not reason else f"暂无：{reason}",
        "analyzed_product_name": listing.title or "",
        "product_mismatch": False,
        "product_mismatch_detail": "",
        "causal_diagnosis": {
            "overall_causal_score": 0,
            "summary": "暂无",
            "keyword_causality": {
                "framework": "暂无",
                "priority_order": [],
                "readiness_score": 0,
                "priority_keywords": [],
                "summary": "暂无",
            },
        },
        "ad_validation_plan": {
            "validation_items": []
        },
        "diagnosis_confidence": {
            "overall": {
                "level": "暂无",
                "reason": "暂无",
            }
        },
        "data_integrity": {
            "score": 0,
            "level": "暂无",
            "reason": "暂无",
        },
    }


def _build_compact_diagnosis_prompt(listing: ListingInput) -> str:
    """Build a compact prompt for live diagnosis so domestic models do not stall on huge schemas."""
    return f"""你是AlignX亚马逊Listing诊断专家。只诊断以下产品，不要替换产品。

产品信息：
- 站点：{listing.marketplace}
- 标题：{listing.title or "未提供"}
- 商品亮点：{listing.item_highlights or "未提供"}
- 五点：{listing.bullet_points or "未提供"}
- 描述：{listing.description or "未提供"}
- A+摘要：{listing.a_plus_content or "未提供"}
- 后台关键词：{listing.backend_keywords or "未提供"}
- 主图/图片：{listing.main_image_description or "未提供"}
- 类目：{listing.category or "未提供"}
- 价格：{listing.price or "未提供"}
- 品牌：{listing.brand or "未提供"}
- 评分/评论数：{listing.rating or "未提供"} / {listing.review_count or "未提供"}

判断标准：
1. 主要目标是判断Listing承接能力：标题、五点、图片/A+、后台词是否能承接广告点击和自然搜索意图。
2. 关键词必须是自然美式英语，不能输出中文关键词。
3. 广告关键词必须标记 keyword_type：attribute / relationship / state_trigger。
4. 优先找 relationship 和 state_trigger，因为它们用于广告验证和避开纯属性词价格竞争；不能只给属性词。
5. relationship 必须来自平台关系锚点：used_for_function / used_for_event / used_for_activity / used_when / used_where / used_with / used_for_audience / used_by。
6. state_trigger 必须来自平台状态锚点：cause_positive / cause_negative / compared_to / requires，例如 odor control, reduce mess, low noise, safe for cats, no ozone, easy maintenance。
7. 必须主动最大化推理场景问题词：从容量、尺寸、材质、兼容对象、使用时长、适用人群、风险承诺和图片场景，反推“谁 + 场景 + 问题/结果”的自然美式英语搜索词；不少于6个候选，放入 keyword_coverage 的 scenario_problem，并优先进入 high_conversion/long_tail。
8. 场景问题词要能被平台理解为购物意图，例如 large dog feeder for vacation、anti clog feeder for large kibble、odor control litter box for apartments。禁止只复述标题原词。
9. 运营建议必须提醒卖家：把高价值场景问题词自然写进标题、五点、图片文案、A+和后台词，可以提升平台对商品意图的理解和推荐匹配概率，减少无效广告测试；不要承诺不投广告也一定获得推荐。
10. 新品或自有产品可能缺少价格、评论、BSR或库存信号；如果同时无价格、无评论、无销售/BSR记录，定位为“新品上架承接诊断”，这些字段缺失不能阻止Listing承接诊断，但必须降低市场验证、风险消除、广告承受力和趋势判断的置信度。
11. 不得编造价格、评论数、BSR、销量或库存；缺失时只评价内容承接，并明确写“市场证据不足/需要广告验证”。
12. 输出要具体指出依据来源：标题、五点、图片/A+、价格、评分评论、缺失类目/后台词。
13. 后台规则只是兜底和一致性校验；真实模型证据链优先。

只返回有效JSON，结构如下：
{{
  "scores": {{
    "function_expression": 0,
    "scenario_expression": 0,
    "identity_fit": 0,
    "psychology_benefit": 0,
    "risk_elimination": 0,
    "product_identity": 0,
    "compatibility": 0,
    "subjective_properties": 0,
    "differentiation": 0,
    "market_trend": 0
  }},
  "analysis": {{
    "function_expression": "具体分析",
    "scenario_expression": "具体分析",
    "identity_fit": "具体分析",
    "psychology_benefit": "具体分析",
    "risk_elimination": "具体分析",
    "product_identity": "具体分析",
    "compatibility": "具体分析",
    "subjective_properties": "具体分析",
    "differentiation": "具体分析",
    "market_trend": "具体分析"
  }},
  "suggestions": {{
    "title_rewrite": "标题建议",
    "bullet_points_optimization": ["五点建议1", "五点建议2", "五点建议3", "五点建议4", "五点建议5"],
    "backend_keywords_addition": ["american keyword"],
    "image_suggestions": ["图片建议"],
    "a_plus_suggestions": "A+建议"
  }},
  "keyword_coverage": {{
    "covered_categories": {{"core_category": [], "function": [], "scenario": [], "audience": [], "pain_point": [], "scenario_problem": [], "long_tail": []}},
    "missing_categories": {{"core_category": [], "function": [], "scenario": [], "audience": [], "pain_point": [], "scenario_problem": [], "long_tail": []}},
    "coverage_score": 0,
    "coverage_summary": "总结"
  }},
  "ad_keywords": {{
    "high_conversion": [{{"keyword": "american keyword", "keyword_type": "state_trigger", "match_type": "phrase", "intent": "意图", "competition": "low", "priority": "P0"}}],
    "traffic": [],
    "long_tail": [],
    "negative": [],
    "ad_summary": "广告验证策略"
  }},
  "elements": {{
    "title": {{"function_expression": 50, "scenario_expression": 50, "identity_fit": 50, "psychology_benefit": 50, "risk_elimination": 50, "product_identity": 50, "compatibility": 50, "subjective_properties": 50, "differentiation": 50, "market_trend": 50, "summary": "标题判断"}},
    "bullets": {{"function_expression": 50, "scenario_expression": 50, "identity_fit": 50, "psychology_benefit": 50, "risk_elimination": 50, "product_identity": 50, "compatibility": 50, "subjective_properties": 50, "differentiation": 50, "market_trend": 50, "summary": "五点判断"}},
    "images": {{"function_expression": 50, "scenario_expression": 50, "identity_fit": 50, "psychology_benefit": 50, "risk_elimination": 50, "product_identity": 50, "compatibility": 50, "subjective_properties": 50, "differentiation": 50, "market_trend": 50, "summary": "图片判断"}},
    "aplus": {{"function_expression": 50, "scenario_expression": 50, "identity_fit": 50, "psychology_benefit": 50, "risk_elimination": 50, "product_identity": 50, "compatibility": 50, "subjective_properties": 50, "differentiation": 50, "market_trend": 50, "summary": "A+判断"}},
    "backend": {{"function_expression": 30, "scenario_expression": 30, "identity_fit": 30, "psychology_benefit": 30, "risk_elimination": 30, "product_identity": 30, "compatibility": 30, "subjective_properties": 30, "differentiation": 30, "market_trend": 30, "summary": "后台关键词判断"}}
  }},
  "listing_health_analysis": {{
    "total_score": 0,
    "dimensions": [
      {{"key": "buyer_clarity", "label": "买家看懂度", "max_score": 10, "score": 0, "problem_position": "标题/主图", "analysis": "为什么买家3秒内是否看懂卖什么", "optimization_suggestion": "具体修改哪里"}},
      {{"key": "demand_expression", "label": "需求表达", "max_score": 8, "score": 0, "problem_position": "标题/主图/副图1", "analysis": "是否表达解决什么问题", "optimization_suggestion": "具体修改哪里"}},
      {{"key": "benefit_expression", "label": "收益表达", "max_score": 8, "score": 0, "problem_position": "副图2/A+", "analysis": "是否表达买完得到什么", "optimization_suggestion": "具体修改哪里"}},
      {{"key": "scenario_expression", "label": "场景表达", "max_score": 8, "score": 0, "problem_position": "副图6/A+05", "analysis": "是否表达在哪里、什么时候、谁使用", "optimization_suggestion": "具体修改哪里"}},
      {{"key": "differentiation_expression", "label": "差异化表达", "max_score": 10, "score": 0, "problem_position": "副图3/A+03", "analysis": "为什么买你不买别人", "optimization_suggestion": "具体修改哪里"}},
      {{"key": "trust_expression", "label": "信任表达", "max_score": 8, "score": 0, "problem_position": "副图4/A+06/Review/QA", "analysis": "买家是否相信页面承诺", "optimization_suggestion": "具体修改哪里"}},
      {{"key": "risk_elimination", "label": "风险消除", "max_score": 8, "score": 0, "problem_position": "副图5/A+04/QA", "analysis": "安全、效果、耐用、售后风险是否消除", "optimization_suggestion": "具体修改哪里"}},
      {{"key": "purchase_driver", "label": "购买驱动力", "max_score": 8, "score": 0, "problem_position": "主图/副图7/Coupon/Deal", "analysis": "为什么现在买", "optimization_suggestion": "具体修改哪里"}},
      {{"key": "price_acceptance", "label": "价格承接", "max_score": 8, "score": 0, "problem_position": "全Listing", "analysis": "页面表达是否支撑当前售价", "optimization_suggestion": "具体修改哪里"}},
      {{"key": "visual_acceptance", "label": "视觉承接", "max_score": 8, "score": 0, "problem_position": "主图/副图/A+/视频", "analysis": "图片是否承担销售工作", "optimization_suggestion": "具体修改哪里"}},
      {{"key": "traffic_acceptance", "label": "流量承接", "max_score": 8, "score": 0, "problem_position": "CTR/CVR/关键词匹配/页面承接", "analysis": "点击进来后能接住多少", "optimization_suggestion": "具体修改哪里"}},
      {{"key": "ad_acceptance", "label": "广告承接", "max_score": 8, "score": 0, "problem_position": "整体承接能力/整体转化能力/整体竞争力", "analysis": "是否具备放大广告条件", "optimization_suggestion": "继续放量/保持/暂停放量/先优化Listing"}}
    ],
    "problem_sources": [{{"dimension": "差异化表达", "score": 0, "problem_sources": [{{"position": "副图3", "score": 0}}, {{"position": "A+03", "score": 0}}], "reason": "原因", "suggestion": "建议"}}],
    "position_scores": [{{"position": "标题", "responsibility": "卖什么", "score": 0, "problem": "存在问题", "optimization_suggestion": "优化建议"}}],
    "priority_issues": [{{"rank": "TOP1", "impact": "影响转化率最大", "dimension": "维度", "position": "具体位置", "problem": "问题", "action": "动作"}}],
    "business_conclusion": {{"Listing健康度": 0, "综合评分": 0}},
    "final_conclusion": {{"current_biggest_problem": "当前最大问题", "problem_image": "具体哪张图", "problem_aplus_module": "具体哪个A+模块", "conversion_reason": "为什么影响转化", "expected_ctr_decline": "暂无", "expected_cvr_decline": "暂无", "expected_ad_efficiency_decline": "暂无", "immediate_modification": "立即修改", "priority": "★★★★★", "expected_benefits": ["提升点击率", "提升转化率", "降低广告浪费"]}}
  }},
  "market_estimates": {{"estimated_monthly_sales": 0, "estimated_bsr_rank": 0}},
  "analyzed_product_name": "{listing.title or ""}",
  "overall_summary": "整体总结"
}}"""


def _listing_semantic_text(listing: ListingInput) -> str:
    return "\n".join(
        part
        for part in [
            f"Title: {listing.title}",
            f"Bullets: {listing.bullet_points}",
            f"Description: {listing.description}",
            f"A+: {listing.a_plus_content}",
            f"Backend keywords: {listing.backend_keywords}",
            f"Main image description: {listing.main_image_description}",
            f"Category: {listing.category}",
            f"Brand: {listing.brand}",
            f"Price: {listing.price}",
            f"Rating reviews BSR: {listing.rating} {listing.review_count} {listing.bsr_rank}",
        ]
        if part and part.strip()
    )[:12000]


async def _run_visual_ocr_batch(
    ai_service: AIHubService,
    listing: ListingInput,
    image_items: list[dict[str, Any]],
    main_count: int,
    aplus_count: int,
) -> dict[str, Any]:
    from schemas.aihub import (
        ChatMessage,
        ContentPartImage,
        ContentPartText,
        GenTxtRequest,
        ImageUrl,
    )

    prompt = (
        "你是AlignX视觉/OCR证据提取器。只提取事实，不做最终评分，不改写Listing。"
        "请严格按图片输入顺序逐张识别图片内文字和可见表达，判断图片表达与图片文案是否错位，以及文案是否是买家容易理解的语言。"
        "不能做最终评分，不能凭空补图中不存在的信息。"
        "只返回JSON，格式："
        '{"items":[{"position_id":"主图","image_group":"listing","order":1,"image_text":"图片内可见文字，保持原文；没有则空字符串","image_expression":"图片实际表达的产品/场景/人群/利益点","copy_fit":"只写图文是否一致的事实；未知则空字符串","buyer_language_note":"只写图片文案是否买家易懂的事实；未知则空字符串"}]}'
        f"\n图片顺序：{json.dumps([{k: v for k, v in item.items() if k != 'url'} for item in image_items], ensure_ascii=False)}"
        f"\nListing标题：{listing.title}"
        f"\n五点描述：{listing.bullet_points[:1000] if listing.bullet_points else '未提供'}"
        f"\n主图描述：{listing.main_image_description or '未提供'}"
        f"\n已有图片文字：{json.dumps({'main_image_texts': listing.main_image_texts or [], 'a_plus_image_texts': listing.a_plus_image_texts or []}, ensure_ascii=False)[:1200]}"
        f"\nA+摘要：{listing.a_plus_content[:700] if listing.a_plus_content else '未提供'}"
    )
    content = [ContentPartText(type="text", text=prompt)]
    for item in image_items:
        content.append(ContentPartImage(type="image_url", image_url=ImageUrl(url=item["url"])))
    response = await asyncio.wait_for(
        ai_service.gentxt(
            GenTxtRequest(
                messages=[ChatMessage(role="user", content=content)],
                model="AI_VISION_MODEL",
                temperature=0,
                max_tokens=1400,
            )
        ),
        timeout=min(AI_DIAGNOSIS_TIMEOUT_SECONDS, 75),
    )
    parsed = _parse_visual_ocr_by_position(response.content or "", main_count=main_count, aplus_count=aplus_count)
    parsed["summary"] = (response.content or "")[:1400]
    parsed["usage"] = response.usage or {}
    parsed["model"] = response.model
    return parsed


async def _build_listing_evidence_chain(listing: ListingInput, ai_service: AIHubService) -> dict:
    """Run mandatory platform evidence enhancement for every Listing diagnosis.

    Hosted embedding/rerank/vision models are the primary evidence path. Local
    platform rules are only fallback and consistency checks.
    """
    semantic_text = _listing_semantic_text(listing)
    evidence: dict = {
        "required": True,
        "priority": "hosted_models_primary_rules_fallback",
        "semantic_vector": {},
        "visual_ocr": {},
        "model_chain": ["BAAI/bge-m3", "BAAI/bge-reranker-v2-m3", "qwen2.5-vl-72b-instruct"],
        "task_boundaries": {
            "AI_EMBEDDING_MODEL": "只做平台语义召回：把标题、五点、A+、后台词映射到isA、used_for_function、used_where、used_with、cause_positive、cause_negative等关系/状态锚点；不做最终评分。",
            "RERANK_MODEL": "只做证据精排：过滤低相关关系锚点和历史语义证据，优先保留relationship与state_trigger；不生成Listing建议。",
            "AI_VISION_MODEL": "只做图片/OCR事实提取：识别主图、副图、A+图里的产品、场景、文字、徽章、认证、风险承诺和合规风险；不做最终评分。",
            "AI_DEEP_MODEL": "只做综合诊断：必须引用向量、精排、OCR事实和抓取字段，先按用户需求与平台识别判断，再用10维诊断反向检查承接、关系词、状态词和广告验证假设。输出面向卖家，不暴露内部方法论名称。",
            "rules": "后台规则只做兜底和一致性校验，不能覆盖真实模型证据。",
        },
        "cosmo_reference": {
            "relationship_anchors": ["used_for_function", "used_for_event", "used_for_activity", "used_when", "used_where", "used_with", "used_for_audience", "used_by"],
            "state_anchors": ["cause_positive", "cause_negative", "compared_to", "requires"],
            "keyword_priority": ["state_trigger", "relationship", "attribute"],
        },
    }

    try:
        vector_track = await evaluate_cosmo_vector_mapping_async(
            semantic_text,
            category_anchor_texts=[
                listing.category or "",
                listing.title or "",
                listing.backend_keywords or "",
            ],
        )
        evidence["semantic_vector"] = {
            "ok": True,
            "embedding_model": vector_track.get("embedding_model", ""),
            "rerank_model": vector_track.get("rerank_model", ""),
            "top_relation": vector_track.get("top_relation", ""),
            "top_confidence": vector_track.get("top_confidence", 0),
            "activated_relations": vector_track.get("activated_relations", [])[:5],
            "fallback_to_prompt_track": vector_track.get("fallback_to_prompt_track", False),
        }
    except Exception as exc:
        logger.warning("Listing semantic vector evidence failed: %s", exc)
        evidence["semantic_vector"] = {"ok": False, "error": "semantic_vector_failed"}

    image_items: list[dict[str, Any]] = []
    for idx, url in enumerate((listing.image_urls or [])[:9]):
        if isinstance(url, str) and url.startswith(("http://", "https://", "data:image/")):
            image_items.append({
                "position_id": "主图" if idx == 0 else f"副图{idx}",
                "image_group": "listing",
                "order": idx + 1,
                "url": url,
            })
    for idx, url in enumerate((listing.aplus_image_urls or [])[:9]):
        if isinstance(url, str) and url.startswith(("http://", "https://", "data:image/")):
            image_items.append({
                "position_id": f"A+图{idx + 1}",
                "image_group": "aplus",
                "order": idx + 1,
                "url": url,
            })
    image_items = image_items[:18]
    image_urls = [item["url"] for item in image_items]
    try:
        main_count = len((listing.image_urls or [])[:9])
        aplus_count = len((listing.aplus_image_urls or [])[:9])
        parsed_visual = {
            "items": [],
            "main_image_texts": _empty_text_slots(main_count),
            "a_plus_image_texts": _empty_text_slots(aplus_count),
        }
        summaries: list[str] = []
        usages: list[dict[str, Any]] = []
        vision_model = ""
        batch_errors: list[str] = []
        batch_size = 6

        def merge_batch_result(batch_result: dict[str, Any]) -> None:
            nonlocal vision_model
            parsed_visual["items"].extend(batch_result.get("items", []))
            for key in ("main_image_texts", "a_plus_image_texts"):
                target = parsed_visual.get(key) or []
                source = batch_result.get(key) or []
                for idx, text in enumerate(source):
                    if idx < len(target) and text and not target[idx]:
                        target[idx] = text
            if batch_result.get("summary"):
                summaries.append(str(batch_result.get("summary"))[:900])
            if isinstance(batch_result.get("usage"), dict):
                usages.append(batch_result["usage"])
            vision_model = str(batch_result.get("model") or vision_model)

        for start in range(0, len(image_items), batch_size):
            batch = image_items[start:start + batch_size]
            try:
                batch_result = await _run_visual_ocr_batch(
                    ai_service=ai_service,
                    listing=listing,
                    image_items=batch,
                    main_count=main_count,
                    aplus_count=aplus_count,
                )
                merge_batch_result(batch_result)
            except Exception as batch_exc:
                logger.warning("Listing visual/OCR batch failed: %s", batch_exc)
                retry_success = False
                if len(batch) > 1:
                    for single_item in batch:
                        try:
                            single_result = await _run_visual_ocr_batch(
                                ai_service=ai_service,
                                listing=listing,
                                image_items=[single_item],
                                main_count=main_count,
                                aplus_count=aplus_count,
                            )
                            merge_batch_result(single_result)
                            retry_success = True
                        except Exception as single_exc:
                            logger.warning("Listing visual/OCR single image failed: %s", single_exc)
                if not retry_success:
                    batch_errors.append("visual_ocr_batch_failed")

        if image_items and not parsed_visual["items"] and batch_errors:
            raise RuntimeError("visual_ocr_failed")

        evidence["visual_ocr"] = {
            "ok": True,
            "model": vision_model,
            "image_count": len(image_urls),
            "input_mode": "image_urls" if image_urls else "description_only",
            "summary": "\n".join(summaries)[:2400],
            "items": parsed_visual.get("items", []),
            "main_image_texts": parsed_visual.get("main_image_texts", []),
            "a_plus_image_texts": parsed_visual.get("a_plus_image_texts", []),
            "usage": usages[:4],
            "batch_errors": batch_errors[:3],
        }
    except Exception as exc:
        logger.warning("Listing visual/OCR evidence failed: %s", exc)
        evidence["visual_ocr"] = {
            "ok": False,
            "image_count": len(image_urls),
            "input_mode": "image_urls" if image_urls else "description_only",
            "error": "visual_ocr_failed",
        }

    return evidence


async def _diagnose_single(
    listing: ListingInput,
    user_id: str,
    db: AsyncSession,
    save: bool = True,
    precision_context: dict | None = None,
    diagnosis_mode: str = "listing_conversion_readiness",
) -> dict:
    """Run full diagnosis on a single listing."""
    ai_service = AIHubService()
    listing = _sanitize_listing_for_ai(listing)
    precision_context = dict(precision_context or {})
    diagnosis_mode = str(diagnosis_mode or precision_context.get("diagnosis_mode") or "listing_conversion_readiness")
    precision_context["diagnosis_mode"] = diagnosis_mode
    review_samples = normalize_review_samples(
        precision_context.get("review_samples") or precision_context.get("captured_reviews"),
        limit=40,
    )
    review_intent_assets = (
        precision_context.get("review_intent_assets")
        if isinstance(precision_context.get("review_intent_assets"), dict)
        else {}
    )
    if review_samples and not review_intent_assets:
        review_intent_assets = build_review_intent_assets({
            "title": listing.title,
            "bullet_points": [item.strip() for item in re.split(r"\n+", listing.bullet_points or "") if item.strip()],
            "review_samples": review_samples,
        })
    if review_samples:
        precision_context["review_samples"] = review_samples
        precision_context["review_intent_assets"] = review_intent_assets

    product_title = listing.title or "未提供"
    evidence_chain = await _build_listing_evidence_chain(listing, ai_service)
    listing = _merge_visual_ocr_into_listing(listing, evidence_chain)
    buyer_language_translation = await _build_listing_buyer_language_translation(listing, evidence_chain)
    precision_context["buyer_language_translation"] = buyer_language_translation
    operator_agent = CosmoOperatorAgent(db)
    alignment_context: dict = {}
    try:
        alignment_context = await operator_agent.build_context(
            user_id=user_id,
            workflow="listing_diagnosis",
            product=listing.model_dump(),
            asin=listing.asin or None,
            marketplace=listing.marketplace,
        )
    except Exception as e:
        logger.warning(f"123 alignment memory unavailable for listing diagnosis: {e}")

    prompt = (
        human_nature_prompt_block({
            "title": listing.title,
            "bullet_points": listing.bullet_points,
            "description": listing.description,
            "a_plus_content": listing.a_plus_content,
            "category": listing.category,
            "brand": listing.brand,
            "keywords": getattr(listing, "backend_keywords", ""),
        })
        + "\n\n"
        + _build_compact_diagnosis_prompt(listing)
        + "\n\n【强制证据链】以下证据来自平台识别主链路，必须优先使用；后台规则只可作为兜底或一致性校验，不能替代主判断：\n"
        + json.dumps(evidence_chain, ensure_ascii=False)[:6000]
        + "\n\n【买家语言转译层】以下内容是本次上架准入和承接决策共用的买家语言翻译层。必须先用它判断Listing是否还是卖家思维，再做10维评分、模块归因和广告验证。不要把内部字段名暴露给卖家：\n"
        + json.dumps(buyer_language_translation, ensure_ascii=False)[:3600]
    )
    if review_intent_assets:
        prompt += (
            "\n\n【评论证据】以下内容来自页面评论样本，只用于识别买家真实购买理由、抱怨和风险，不得编造评论不存在的结论：\n"
            + json.dumps(review_intent_assets, ensure_ascii=False)[:2400]
        )
    if alignment_context.get("prompt_summary"):
        prompt += "\n\n" + str(alignment_context["prompt_summary"])[:3500]

    # Determine A+ content status for system message hint
    a_plus_hint = ""
    a_plus_val = listing.a_plus_content or ""
    if "已检测" in a_plus_val or "detected" in a_plus_val.lower() or a_plus_val.strip():
        a_plus_hint = (
            f' 5.该产品有A+内容（已净化摘要: {a_plus_val[:450]}），在elements.aplus中必须给出合理的非零评分（各维度至少30分以上），'
            f'根据产品类型和其他listing信息推断A+内容质量。绝对不能给0分！'
        )

    system_msg = (
        f'【最高优先级指令】你正在分析的产品是: "{product_title}"。'
        f'规则：1.所有分析必须围绕"{product_title}" '
        f'2.禁止分析其他任何产品 '
        f'3.基于标题关键词推断产品特性 '
        f'4.在JSON中"analyzed_product_name"字段填入你实际分析的产品名称。'
        f'{a_plus_hint}'
        f' 6.elements中每个要素的每个维度评分都必须是合理的非零值，绝对禁止全部给0分。'
        f' 7.本次诊断采用“1人性根层 → 2用户意图 → 3平台规则 → 4验证回流 → 10维诊断”的后台动作顺序；禁止把10项当作平铺平均分。输出面向卖家，禁止暴露内部方法论名称。'
        f' 8.判断优先级：语义召回和证据精排 > 图片识别事实 > AI综合判断；后台规则只做兜底和一致性校验。'
        f' 9.必须先检查卖家语言是否被买家看懂：卖家参数/技术/营销表达需要转成买家会搜索、会点击、会相信的语言，再映射到标题、五点、图片、A+和Search Terms。'
        f'你是亚马逊Listing优化专家。只输出JSON。'
    )

    from schemas.aihub import GenTxtRequest, ChatMessage
    request = GenTxtRequest(
        messages=[
            ChatMessage(role="system", content=system_msg),
            ChatMessage(role="user", content=prompt),
        ],
        model="AI_DEEP_MODEL",
        temperature=0,
        max_tokens=4096,
    )

    # Try up to 2 times - if first attempt produces truncated/unparseable JSON, retry
    last_error = None
    for attempt in range(2):
        try:
            response = await asyncio.wait_for(ai_service.gentxt(request), timeout=AI_DIAGNOSIS_TIMEOUT_SECONDS)
            data = _extract_json(response.content)
            break
        except asyncio.TimeoutError as e:
            last_error = e
            logger.warning(
                "AI diagnosis timed out after %ss; using fallback diagnosis",
                AI_DIAGNOSIS_TIMEOUT_SECONDS,
            )
            data = _fallback_listing_diagnosis(
                listing,
                reason=f"AI diagnosis timed out after {AI_DIAGNOSIS_TIMEOUT_SECONDS}s",
            )
            break
        except ValueError as e:
            last_error = e
            logger.warning(f"AI response parse failed (attempt {attempt + 1}/2): {e}")
            if attempt == 0:
                request.model = "AI_DEEP_MODEL"
                request.max_tokens = 4096
        except Exception as e:
            last_error = e
            logger.warning(f"AI diagnosis call failed (attempt {attempt + 1}/2): {e}")
            if attempt == 0:
                request.model = "AI_DEEP_MODEL"
    else:
        data = _fallback_listing_diagnosis(listing, reason=str(last_error or ""))

    data = _normalize_keyword_payload(data)
    data["buyer_language_translation"] = buyer_language_translation

    # Validate product name match
    analyzed_name = data.get("analyzed_product_name", "")
    if analyzed_name and product_title != "未提供":
        input_lower = product_title.lower()
        analyzed_lower = analyzed_name.lower()
        input_words = [w for w in input_lower.split() if len(w) >= 2]
        analyzed_words = [w for w in analyzed_lower.split() if len(w) >= 2]
        if input_words:
            common = [w for w in input_words if any(aw in w or w in aw for aw in analyzed_words)]
            match_ratio = len(common) / len(input_words)
            if match_ratio < 0.15:
                logger.warning(
                    f"Product mismatch detected! Input: '{product_title}', "
                    f"AI analyzed: '{analyzed_name}', match_ratio: {match_ratio:.2f}"
                )
                data["product_mismatch"] = True
                data["product_mismatch_detail"] = (
                    f"AI分析的产品「{analyzed_name}」与输入产品「{product_title}」不匹配"
                )

    data = _ensure_element_scores(data, listing)

    record_id = None

    # ========== 统一判断系统 ==========
    # 评论语义、COSMO语义、因果判断、精准度体系统一在后台判断层输出；
    # Listing诊断只消费统一结果，避免四套能力重复计算/重复定义。
    judgment_system = {}
    try:
        judgment_service = JudgmentSystemService(db)
        judgment_system = await judgment_service.judge_listing(
            listing=listing,
            diagnosis_data=data,
            user_id=user_id,
            context=precision_context,
            asin=listing.asin or None,
            listing_diagnosis_id=None,
            run_causal=False,
        )
        data = JudgmentSystemService.apply_to_legacy_listing_diagnosis(data, judgment_system)
        data["diagnosis_mode"] = diagnosis_mode
    except Exception as e:
        logger.error(f"Unified judgment system failed, continuing with base diagnosis: {e}")
        judgment_system = {}

    scores = data.get("scores", {})
    legacy_bridge = judgment_system.get("legacy_bridge", {}) if isinstance(judgment_system, dict) else {}
    data_integrity = legacy_bridge.get("data_integrity", {})
    diagnosis_confidence = legacy_bridge.get("diagnosis_confidence", {})
    causal_diagnosis = legacy_bridge.get("causal_diagnosis", data.get("causal_diagnosis", {}))
    ad_validation_plan = legacy_bridge.get("ad_validation_plan", data.get("ad_validation_plan", {}))
    # ========== 统一判断系统结束 ==========
    cosmo_rufus_analysis = build_cosmo_rufus_analysis(listing, data)
    cosmo_rufus_analysis["evidence_chain"] = evidence_chain
    cosmo_rufus_analysis["rule_track_role"] = "fallback_consistency_check_only"
    data = merge_cosmo_rufus_into_legacy(data, cosmo_rufus_analysis)
    data = _apply_market_reality_caps(data, listing)
    data = _align_listing_scores_with_canonical(data, listing)
    data = await _apply_shared_asin_score_snapshot(data, listing, db, user_id)
    scores = data.get("scores", {})
    ad_validation_plan = data.get("ad_validation_plan", ad_validation_plan)
    data = operator_agent.attach_result_metadata(
        data,
        alignment_context,
        product=listing.model_dump(),
        scores=scores,
    )

    amazon_compliance = await _evaluate_listing_compliance(listing, db)
    data["amazon_compliance"] = amazon_compliance
    toolbox_product_data = {
        "asin": listing.asin,
        "title": listing.title,
        "category": listing.category,
        "price": listing.price,
        "rating": listing.rating,
        "review_count": listing.review_count,
        "bullet_points": [item.strip() for item in re.split(r"\n+", listing.bullet_points or "") if item.strip()],
        "description_summary": listing.description,
        "aplus_content": listing.a_plus_content,
        "has_a_plus": listing.has_a_plus or bool(listing.a_plus_content),
        "has_video": listing.has_video,
        "image_count": listing.image_count,
        "main_keywords": (data.get("ad_keywords") or {}).get("high_intent_keywords")
            or (data.get("keyword_coverage") or {}).get("covered_keywords")
            or listing.backend_keywords,
        "review_samples": review_samples,
        "review_intent_assets": review_intent_assets,
    }
    toolbox_enhancements = build_toolbox_enhancements(
        product_data=toolbox_product_data,
        scores=scores,
        context="listing",
    )
    data["toolbox_enhancements"] = toolbox_enhancements
    ad_validation_plan = merge_toolbox_into_ad_validation_plan(ad_validation_plan, toolbox_enhancements)
    data["ad_validation_plan"] = ad_validation_plan
    data["diagnosis_mode"] = diagnosis_mode
    data["buyer_language_translation"] = buyer_language_translation
    data["listing_position_diagnosis"] = build_listing_position_diagnosis(data, _position_payload_from_listing(listing))
    data["ad_validation_readiness_gate"] = JudgmentSystemService.apply_ad_validation_gate_to_outputs(data, listing)
    data["opc_v5_execution"] = await _build_listing_opc_v5_execution(data, listing, user_id, db)
    sanitized_listing = _sanitize_listing_for_ai(listing)
    content_fingerprint = _listing_content_fingerprint(sanitized_listing)
    data["diagnosis_meta"] = {
        "schema_version": "listing-diagnosis-v3",
        "rules_version": "cosmo-rufus-8d2-v2",
        "content_fingerprint": content_fingerprint,
        "content_fingerprint_short": content_fingerprint[:8],
        "cache_policy": "exact_content_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    data["diagnosis_mode"] = diagnosis_mode

    if save:
        svc = Listing_diagnosesService(db)
        # 准备创建数据，包含新增的因果维度字段
        create_data = {
            "listing_title": (listing.title or "")[:500],
            "marketplace": listing.marketplace,
            "input_data": json.dumps(listing.model_dump(), ensure_ascii=False),
            "score_function_expression": scores.get("function_expression", 0),
            "score_scenario_expression": scores.get("scenario_expression", 0),
            "score_identity_fit": scores.get("identity_fit", 0),
            "score_psychology_benefit": scores.get("psychology_benefit", 0),
            "score_risk_elimination": scores.get("risk_elimination", 0),
            "score_product_identity": scores.get("product_identity", 0),
            "score_compatibility": scores.get("compatibility", 0),
            "score_subjective_properties": scores.get("subjective_properties", 0),
            "score_differentiation": scores.get("differentiation", 0),
            "score_market_trend": scores.get("market_trend", 0),
            # ========== 新增：因果维度字段 ==========
            "score_causal_state_gap_coverage": scores.get("causal_state_gap_coverage", 0),
            "score_causal_mechanism_clarity": scores.get("causal_mechanism_clarity", 0),
            "score_causal_side_effect_transparency": scores.get("causal_side_effect_transparency", 0),
            "causal_diagnosis_report": json.dumps(causal_diagnosis or {}, ensure_ascii=False),
            # ==========================================
            "diagnosis_report": json.dumps(data, ensure_ascii=False),
            "keyword_report": json.dumps(data.get("keyword_coverage", {}), ensure_ascii=False),
            "created_at": datetime.now(timezone.utc),
        }
        
        record = await svc.create_or_update_by_asin(
            create_data,
            asin=listing.asin,
            marketplace=listing.marketplace,
            user_id=user_id,
        )
        if record:
            record_id = record.id
            await _sync_asin_profile_from_listing_record(db, user_id, record)
            try:
                validation_items = ad_validation_plan.get("validation_items", []) if isinstance(ad_validation_plan, dict) else []
                first_validation = validation_items[0] if validation_items else {}
                await JudgmentFeedbackRoundService(db).create(
                    {
                        "asin": listing.asin or None,
                        "marketplace": listing.marketplace,
                        "listing_diagnosis_id": record_id,
                        "optimization_round": 1,
                        "stage": "ad_validation",
                        "status": "planned",
                        "diagnosis_issue": first_validation.get("diagnosis_issue", "Listing诊断完成，待广告验证"),
                        "judgment_basis": json.dumps(
                            {
                                "alignment_scores": judgment_system.get("alignment_scores", {}),
                                "diagnosis_confidence": diagnosis_confidence,
                                "data_integrity": data_integrity,
                                "cosmo_rufus_analysis": cosmo_rufus_analysis,
                            },
                            ensure_ascii=False,
                        ),
                        "suggested_action": first_validation.get("suggested_listing_action", ""),
                        "ad_validation_plan": json.dumps(ad_validation_plan or {}, ensure_ascii=False),
                        "before_snapshot": json.dumps(
                            {
                                "listing": listing.model_dump(),
                                "scores": scores,
                                "overall_summary": data.get("overall_summary", ""),
                            },
                            ensure_ascii=False,
                        ),
                        "confidence_before": float(data_integrity.get("score", 0) or 0),
                    },
                    user_id=user_id,
                )
            except Exception as e:
                logger.warning(f"Failed to create initial feedback round: {e}")

    return {
        "listing_title": listing.title or "",
        "listing": listing.model_dump(),
        "marketplace": listing.marketplace,
        "scores": scores,
        "analysis": data.get("analysis", {}),
        "suggestions": data.get("suggestions", {}),
        "keyword_coverage": data.get("keyword_coverage", {}),
        "ad_keywords": data.get("ad_keywords", {}),
        "elements": data.get("elements", {}),
        "market_estimates": data.get("market_estimates", {}),
        "overall_summary": data.get("overall_summary", ""),
        "analyzed_product_name": data.get("analyzed_product_name", ""),
        "product_mismatch": data.get("product_mismatch", False),
        "product_mismatch_detail": data.get("product_mismatch_detail", ""),
        "id": record_id,
        "_ai_called": True,
        "_cache_hit": "",
        "causal_diagnosis": causal_diagnosis,
        "judgment_system": judgment_system,
        "ad_validation_plan": ad_validation_plan,
        "buyer_language_translation": buyer_language_translation,
        "listing_health_analysis": data.get("listing_health_analysis", {}),
        "listing_position_diagnosis": data.get("listing_position_diagnosis", {}),
        "opc_v5_execution": data.get("opc_v5_execution", {}),
        "data_integrity": data_integrity,
        "diagnosis_confidence": diagnosis_confidence,
        "decision_outputs": data.get("decision_outputs", []),
        "ad_validation_readiness_gate": data.get("ad_validation_readiness_gate", {}),
        "cosmo_rufus_analysis": cosmo_rufus_analysis,
        "amazon_compliance": amazon_compliance,
        "toolbox_enhancements": toolbox_enhancements,
        "trace": {
            "model_chain": evidence_chain.get("model_chain", []),
            "cosmo_rufus_evidence_chain": evidence_chain,
            "rule_track_role": "fallback_consistency_check_only",
        },
    }


# ---------- API Endpoints ----------

@router.post("/fetch-url", response_model=FetchUrlResponse)
async def fetch_listing_from_url(
    request: FetchUrlRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Fetch listing information from an Amazon product URL.

    Strategy: Try real web scraping first, fall back to AI estimation if scraping fails.
    """
    try:
        url = request.url.strip()
        if not url:
            raise HTTPException(status_code=400, detail="请输入Amazon产品链接")

        asin = _extract_asin(url)
        if not asin:
            raise HTTPException(status_code=400, detail="无法从链接中提取ASIN，请检查链接格式")

        marketplace = _detect_marketplace(url) or request.marketplace

        # ---- Phase 1: Public deployment delegates Amazon capture to external Amazon capture ----
        scraped = await scrape_amazon_product_via_scrapeless(asin, marketplace)
        scrape_ok = scraped.get("scrape_success", False)

        # Helper to clean markers
        def _clean_field(val: str) -> str:
            if not val or not isinstance(val, str):
                return ""
            for marker in ["[未确认]", "[未确认] ", "[unknown]", "[Unknown]", "[unconfirmed]"]:
                val = val.replace(marker, "")
            return val.strip()

        def _listing_text_value(val: Any) -> str:
            if val is None:
                return ""
            if isinstance(val, str):
                return val.strip()
            return str(val).strip()

        if scrape_ok and scraped.get("title"):
            logger.info(f"Scrape succeeded for {asin}: {scraped['title'][:60]}")
            aplus_text = scraped.get("aplus_content", "")
            if scraped.get("has_a_plus"):
                if aplus_text and len(aplus_text) > 20:
                    aplus_text = f"A+内容已检测，详细内容: {aplus_text}"
                else:
                    aplus_text = "A+内容已检测（详细内容未能提取，请根据产品类型推断A+内容质量）"
            listing = ListingInput(
                title=scraped.get("title", ""),
                bullet_points="\n".join(scraped.get("bullet_points", [])),
                description="",
                a_plus_content=aplus_text,
                backend_keywords="",
                main_image_description=f"共{scraped.get('image_count', '?')}张产品图片" + (", 含视频" if scraped.get("has_video") else ""),
                category=scraped.get("category", ""),
                price=_listing_text_value(scraped.get("price", "")),
                brand=scraped.get("brand", ""),
                marketplace=marketplace,
                image_urls=scraped.get("image_urls", []) or [],
                main_image_texts=scraped.get("main_image_texts", []) or [],
                aplus_image_count=str(scraped.get("aplus_image_count", "") or ""),
                aplus_image_urls=scraped.get("aplus_image_urls", []) or [],
                a_plus_image_texts=scraped.get("a_plus_image_texts", []) or [],
            )
            return FetchUrlResponse(
                listing=listing,
                asin=asin,
                source=scraped.get("data_source") or "scraped",
                rating=_listing_text_value(scraped.get("rating", "")),
                review_count=_listing_text_value(scraped.get("review_count", "")),
                bsr_rank=_listing_text_value(scraped.get("bsr_rank", "")),
                bsr_category=scraped.get("bsr_category", ""),
                image_count=str(scraped.get("image_count", "") or ""),
                has_video=scraped.get("has_video", False),
                has_a_plus=scraped.get("has_a_plus", False),
                aplus_image_count=str(scraped.get("aplus_image_count", "") or ""),
            )

        # ---- Phase 2: Scraping failed, fall back to AI search ----
        scrape_reason = scraped.get("data_source", "unknown")
        logger.info(f"Scrape failed for {asin} (reason: {scrape_reason}), falling back to AI search")

        domain = MARKETPLACE_DOMAINS.get(marketplace, "com")
        ai_service = AIHubService()
        prompt = FETCH_LISTING_PROMPT.format(asin=asin, marketplace=marketplace, domain=domain)

        from schemas.aihub import GenTxtRequest, ChatMessage
        ai_request = GenTxtRequest(
            messages=[
                ChatMessage(
                    role="system",
                    content=(
                        f"你是Amazon产品数据搜索专家。你的唯一任务是搜索ASIN {asin}在Amazon {marketplace}站点的真实产品信息。"
                        f"\n\n关键规则："
                        f"\n1. 你必须搜索的是ASIN: {asin}，产品页面URL: https://www.amazon.{domain}/dp/{asin}"
                        f"\n2. 只返回你确认属于ASIN {asin}的产品数据，不要返回其他ASIN的数据"
                        f"\n3. 如果搜索结果中找不到ASIN {asin}对应的产品，返回空字段而不是猜测"
                        f"\n4. 宁可返回空数据也不要返回错误产品的数据"
                        f"\n5. 无法确定的字段返回空字符串"
                        f"\n6. 只输出JSON，不要输出其他内容"
                    ),
                ),
                ChatMessage(role="user", content=prompt),
            ],
            model="AI_REASONING_MODEL",
            temperature=0.2,
            max_tokens=8192,
        )

        # Try up to 2 times for URL fetch AI
        data = None
        for attempt in range(2):
            try:
                response = await ai_service.gentxt(ai_request)
                data = _extract_json(response.content)
                break
            except ValueError as e:
                logger.warning(f"Fetch URL AI JSON parse failed (attempt {attempt + 1}/2): {e}")
                if attempt == 0:
                    ai_request.model = "AI_REASONING_MODEL"

        if data is None:
            data = {
                "title": "", "bullet_points": "", "description": "",
                "a_plus_content": "", "backend_keywords": "",
                "main_image_description": "", "category": "",
                "price": "", "brand": "", "rating": "", "review_count": "",
                "bsr_rank": "", "bsr_category": "", "confidence": "low",
                "verification_note": "AI响应解析失败",
            }

        listing = ListingInput(
            title=_clean_field(data.get("title", "")),
            bullet_points=_clean_field(data.get("bullet_points", "")),
            description=_clean_field(data.get("description", "")),
            a_plus_content=_clean_field(data.get("a_plus_content", "")),
            backend_keywords=_clean_field(data.get("backend_keywords", "")),
            main_image_description=_clean_field(data.get("main_image_description", "")),
            category=_clean_field(data.get("category", "")),
            price=_clean_field(data.get("price", "")),
            brand=_clean_field(data.get("brand", "")),
            marketplace=marketplace,
        )

        ai_rating = _clean_field(data.get("rating", ""))
        ai_review_count = _clean_field(data.get("review_count", ""))
        ai_bsr_rank = _clean_field(data.get("bsr_rank", ""))
        ai_bsr_category = _clean_field(data.get("bsr_category", ""))
        ai_confidence = _clean_field(data.get("confidence", "low"))

        if not listing.title:
            source = "ai_empty"
        elif ai_confidence in ("high", "medium") and listing.title:
            source = "ai_search"
        else:
            source = "ai_estimated"

        return FetchUrlResponse(
            listing=listing,
            asin=asin,
            source=source,
            rating=ai_rating,
            review_count=ai_review_count,
            bsr_rank=ai_bsr_rank,
            bsr_category=ai_bsr_category,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Fetch URL error: {e}")
        raise HTTPException(status_code=500, detail=f"抓取失败: {str(e)}")
    except Exception as e:
        logger.error(f"Fetch URL error: {e}")
        raise HTTPException(status_code=500, detail=f"抓取失败: {str(e)}")


@router.post("/parse-html", response_model=ParseHtmlResponse)
async def parse_html_content(
    request: ParseHtmlRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Legacy HTML parsing endpoint; Amazon capture is delegated to external Amazon capture."""
    try:
        asin = request.asin.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{10}", asin):
            return ParseHtmlResponse(
                listing=ListingInput(marketplace=request.marketplace),
                asin=asin,
                success=False,
                error="请输入有效的10位ASIN",
            )

        parsed = await scrape_amazon_product_via_scrapeless(asin, request.marketplace)
        if not parsed.get("scrape_success"):
            return ParseHtmlResponse(
                listing=ListingInput(marketplace=request.marketplace),
                asin=asin,
                success=False,
                error=str(parsed.get("error") or "外部采集失败"),
            )

        marketplace = request.marketplace
        review_samples = normalize_review_samples(parsed.get("review_samples") or [], limit=40)
        review_intent_assets = {}
        if review_samples:
            review_intent_assets = build_review_intent_assets({
                **parsed,
                "review_samples": review_samples,
            })

        aplus_text_parsed = parsed.get("aplus_content", "")
        if parsed.get("has_a_plus"):
            if aplus_text_parsed and len(aplus_text_parsed) > 20:
                aplus_text_parsed = f"A+内容已检测，详细内容: {aplus_text_parsed}"
            else:
                aplus_text_parsed = "A+内容已检测（详细内容未能提取，请根据产品类型推断A+内容质量）"
        listing = ListingInput(
            title=parsed.get("title", ""),
            bullet_points="\n".join(parsed.get("bullet_points", [])),
            description="",
            a_plus_content=aplus_text_parsed,
            backend_keywords="",
            main_image_description=f"共{parsed.get('image_count', '?')}张产品图片" + (", 含视频" if parsed.get("has_video") else ""),
            category=parsed.get("category", ""),
            price=str(parsed.get("price", "") or ""),
            brand=parsed.get("brand", ""),
            marketplace=marketplace,
            asin=request.asin.strip().upper() if request.asin else parsed.get("asin", ""),
            rating=str(parsed.get("rating", "") or ""),
            review_count=str(parsed.get("review_count", "") or ""),
            bsr_rank=str(parsed.get("bsr_rank", "") or ""),
            image_count=str(parsed.get("image_count", "") or ""),
            has_video=bool(parsed.get("has_video", False)),
            has_a_plus=bool(parsed.get("has_a_plus", False)),
            aplus_image_count=str(parsed.get("aplus_image_count", "") or ""),
            image_urls=parsed.get("image_urls", []) or [],
            main_image_texts=parsed.get("main_image_texts", []) or [],
            aplus_image_urls=parsed.get("aplus_image_urls", []) or [],
            a_plus_image_texts=parsed.get("a_plus_image_texts", []) or [],
        )

        bsr = parsed.get("bsr_rank", "")
        bsr_cat = parsed.get("bsr_category", "")
        source = parsed.get("data_source") or "external_amazon_product"
        quality = parsed.get("capture_quality") if isinstance(parsed.get("capture_quality"), dict) else {}

        logger.info("parse-html delegated to external Amazon capture for ASIN %s: %s", asin, parsed.get("title", "")[:60])

        return ParseHtmlResponse(
            listing=listing,
            asin=asin,
            source=source,
            rating=parsed.get("rating", ""),
            review_count=parsed.get("review_count", ""),
            bsr_rank=bsr,
            bsr_category=bsr_cat,
            image_count=str(parsed.get("image_count", "") or ""),
            has_video=parsed.get("has_video", False),
            has_a_plus=parsed.get("has_a_plus", False),
            aplus_image_count=str(parsed.get("aplus_image_count", "") or ""),
            capture_quality=quality,
            review_intent_assets=review_intent_assets,
            review_samples=review_samples,
            success=True,
        )

    except Exception as e:
        logger.error(f"parse-html error: {e}")
        return ParseHtmlResponse(
            listing=ListingInput(marketplace=request.marketplace),
            asin=request.asin,
            success=False,
            error=f"解析失败: {str(e)}",
        )


@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose_listing(
    request: DiagnoseRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full listing diagnosis: 10-dimension scoring + keyword coverage + optimization suggestions + ad keywords."""
    try:
        listing = request.listing
        if not listing.title and not listing.bullet_points:
            raise HTTPException(status_code=400, detail="请至少输入标题或五点描述")

        result = await _diagnose_single(
            listing=listing,
            user_id=str(current_user.id),
            db=db,
            precision_context=request.precision_context,
            diagnosis_mode=request.diagnosis_mode,
        )
        result = _normalize_diagnosis_result({**result, "diagnosis_mode": request.diagnosis_mode}, listing)
        content_fingerprint = _listing_content_fingerprint(_sanitize_listing_for_ai(listing))
        trace = {
            "diagnosis_id": result.get("id"),
            "cache_hit": result.get("_cache_hit") or "",
            "ai_called": bool(result.get("_ai_called", not result.get("_cache_hit"))),
            "diagnosis_meta": result.get("diagnosis_meta", {}),
            "content_fingerprint": content_fingerprint,
            "content_fingerprint_short": content_fingerprint[:8],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "frontend_version": "module-attribution-v2",
        }
        if not result.get("amazon_compliance"):
            result["amazon_compliance"] = await _evaluate_listing_compliance(listing, db)
        if not result.get("opc_v5_execution"):
            result["opc_v5_execution"] = await _build_listing_opc_v5_execution(result, listing, str(current_user.id), db, result.get("id"))
        return DiagnoseResponse(
            scores=result.get("scores", {}),
            analysis=result.get("analysis", {}),
            suggestions=result.get("suggestions", {}),
            keyword_coverage=result.get("keyword_coverage", {}),
            ad_keywords=result.get("ad_keywords", {}),
            elements=result.get("elements", {}),
            market_estimates=result.get("market_estimates", {}),
            overall_summary=result.get("overall_summary", ""),
            analyzed_product_name=result.get("analyzed_product_name", ""),
            product_mismatch=result.get("product_mismatch", False),
            product_mismatch_detail=result.get("product_mismatch_detail", ""),
            id=result.get("id"),
            # ========== 新增：因果诊断返回 ==========
            causal_diagnosis=result.get("causal_diagnosis", {}),
            causal_scores={
                "state_gap_coverage": result.get("scores", {}).get("causal_state_gap_coverage", 0),
                "mechanism_clarity": result.get("scores", {}).get("causal_mechanism_clarity", 0),
                "side_effect_transparency": result.get("scores", {}).get("causal_side_effect_transparency", 0),
                "overall_causal_score": result.get("causal_diagnosis", {}).get("overall_causal_score", 0)
            },
            # =========================================
            # ========== 新增：精准度/置信度返回 ==========
            judgment_system=result.get("judgment_system", {}),
            data_integrity=result.get("data_integrity", {}),
            diagnosis_confidence=result.get("diagnosis_confidence", {}),
            ad_validation_plan=result.get("ad_validation_plan", {}),
            buyer_language_translation=result.get("buyer_language_translation", {}),
            listing_health_analysis=result.get("listing_health_analysis", {}),
            listing_position_diagnosis=result.get("listing_position_diagnosis", {}),
            opc_v5_execution=result.get("opc_v5_execution", {}),
            amazon_compliance=result.get("amazon_compliance", {}),
            trace=trace,
            # =========================================
        )
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Diagnosis error: {e}")
        raise HTTPException(status_code=500, detail=f"AI分析失败: {str(e)}")
    except Exception as e:
        logger.error(f"Diagnosis error: {e}")
        raise HTTPException(status_code=500, detail=f"诊断失败: {str(e)}")


@router.post("/compare", response_model=CompareResponse)
async def compare_listings(
    request: CompareRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compare my listing with competitor listings."""
    try:
        if not request.my_listing.title and not request.my_listing.bullet_points:
            raise HTTPException(status_code=400, detail="请输入我的Listing信息")
        if not request.competitor_listings:
            raise HTTPException(status_code=400, detail="请至少输入一个竞品Listing")
        if len(request.competitor_listings) > 3:
            raise HTTPException(status_code=400, detail="最多支持3个竞品对比")

        user_id = str(current_user.id)

        # Diagnose my listing
        my_result = await _diagnose_single(request.my_listing, user_id, db)

        # Diagnose competitors
        comp_results = []
        for comp_listing in request.competitor_listings:
            if comp_listing.title or comp_listing.bullet_points:
                comp_result = await _diagnose_single(comp_listing, user_id, db, save=False)
                comp_results.append(comp_result)

        # Generate comparison
        ai_service = AIHubService()
        competitor_info = "\n".join([
            f"竞品{i+1} 标题: {c['listing_title']}, 10维诊断: {json.dumps(c['scores'], ensure_ascii=False)}"
            for i, c in enumerate(comp_results)
        ])

        compare_prompt = COMPARE_PROMPT.format(
            my_title=my_result["listing_title"],
            my_scores=json.dumps(my_result["scores"], ensure_ascii=False),
            competitor_info=competitor_info,
        )

        from schemas.aihub import GenTxtRequest, ChatMessage
        compare_request = GenTxtRequest(
            messages=[ChatMessage(role="user", content=compare_prompt)],
            model="AI_REASONING_MODEL",
            temperature=0,
            max_tokens=8192,
        )

        comparison_data = None
        for attempt in range(2):
            try:
                compare_response = await ai_service.gentxt(compare_request)
                comparison_data = _extract_json(compare_response.content)
                break
            except ValueError as e:
                logger.warning(f"Compare JSON parse failed (attempt {attempt + 1}/2): {e}")
                if attempt == 0:
                    compare_request.model = "AI_REASONING_MODEL"

        if comparison_data is None:
            comparison_data = {
                "strengths": ["对比分析暂时无法完成，请重试"],
                "weaknesses": [],
                "opportunities": [],
                "threats": [],
                "dimension_comparison": {},
                "keyword_gaps": [],
                "action_plan": ["请重新运行对比分析"],
            }

        return CompareResponse(
            my_diagnosis=my_result,
            competitor_diagnoses=comp_results,
            comparison=comparison_data,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comparison error: {e}")
        raise HTTPException(status_code=500, detail=f"对比分析失败: {str(e)}")


@router.get("/history")
async def get_diagnosis_history(
    skip: int = 0,
    limit: int = 20,
    search: str = "",
    marketplace_filter: str = "",
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's diagnosis history with optional search and marketplace filter."""
    from sqlalchemy import select, func, or_
    from models.listing_diagnoses import Listing_diagnoses as LD

    scope_user_ids = await get_user_scope_ids(current_user, db)

    # Build base query
    base_filter = [LD.user_id.in_(scope_user_ids)]
    if search.strip():
        base_filter.append(LD.listing_title.ilike(f"%{search.strip()}%"))
    if marketplace_filter.strip():
        base_filter.append(LD.marketplace == marketplace_filter.strip())

    # Count
    count_q = select(func.count(LD.id)).where(*base_filter)
    count_result = await db.execute(count_q)
    total = count_result.scalar() or 0

    # Aggregate stats for this user (unfiltered)
    stats_filter = [LD.user_id.in_(scope_user_ids)]
    stats_q = select(
        func.count(LD.id).label("total_count"),
        func.avg(LD.score_function_expression).label("avg_func"),
        func.avg(LD.score_scenario_expression).label("avg_scen"),
        func.avg(LD.score_identity_fit).label("avg_iden"),
        func.avg(LD.score_psychology_benefit).label("avg_psyc"),
        func.avg(LD.score_risk_elimination).label("avg_risk"),
        func.avg(LD.score_product_identity).label("avg_prod_id"),
        func.avg(LD.score_compatibility).label("avg_compat"),
        func.avg(LD.score_subjective_properties).label("avg_subj"),
        func.avg(LD.score_differentiation).label("avg_diff"),
        func.avg(LD.score_market_trend).label("avg_trend"),
        func.max(
            (LD.score_function_expression + LD.score_scenario_expression +
             LD.score_identity_fit + LD.score_psychology_benefit +
             LD.score_risk_elimination + LD.score_product_identity +
             LD.score_compatibility + LD.score_subjective_properties +
             LD.score_differentiation + LD.score_market_trend) / 10
        ).label("max_avg"),
        func.min(
            (LD.score_function_expression + LD.score_scenario_expression +
             LD.score_identity_fit + LD.score_psychology_benefit +
             LD.score_risk_elimination + LD.score_product_identity +
             LD.score_compatibility + LD.score_subjective_properties +
             LD.score_differentiation + LD.score_market_trend) / 10
        ).label("min_avg"),
    ).where(*stats_filter)
    stats_result = await db.execute(stats_q)
    stats_row = stats_result.one_or_none()

    stats = {}
    if stats_row:
        overall_avg = 0
        dim_avgs = {}
        for dim_name, col_name in [
            ("function_expression", "avg_func"),
            ("scenario_expression", "avg_scen"),
            ("identity_fit", "avg_iden"),
            ("psychology_benefit", "avg_psyc"),
            ("risk_elimination", "avg_risk"),
            ("product_identity", "avg_prod_id"),
            ("compatibility", "avg_compat"),
            ("subjective_properties", "avg_subj"),
            ("differentiation", "avg_diff"),
            ("market_trend", "avg_trend"),
        ]:
            val = getattr(stats_row, col_name, None)
            dim_avgs[dim_name] = round(float(val), 1) if val else 0
        vals = [v for v in dim_avgs.values() if v > 0]
        overall_avg = round(sum(vals) / len(vals), 1) if vals else 0
        stats = {
            "total_count": getattr(stats_row, "total_count", 0) or 0,
            "overall_avg": overall_avg,
            "dimension_avgs": dim_avgs,
            "max_avg": round(float(getattr(stats_row, "max_avg", 0) or 0), 1),
            "min_avg": round(float(getattr(stats_row, "min_avg", 0) or 0), 1),
        }

    # Items
    items_q = (
        select(LD)
        .where(*base_filter)
        .order_by(LD.id.desc())
    )
    items_result = await db.execute(items_q)
    rows = items_result.scalars().all()

    deduped_rows = []
    seen_asins = set()
    for row in rows:
        asin = Listing_diagnosesService._record_asin(row)
        if asin:
            key = (asin, row.marketplace or "")
            if key in seen_asins:
                continue
            seen_asins.add(key)
        deduped_rows.append((row, asin))

    total = len(deduped_rows)
    if stats:
        stats["total_count"] = total

    items = []
    for item, asin in deduped_rows[skip: skip + limit]:
        items.append({
            "id": item.id,
            "asin": asin,
            "listing_title": item.listing_title,
            "marketplace": item.marketplace,
            "scores": {
                "function_expression": item.score_function_expression,
                "scenario_expression": item.score_scenario_expression,
                "identity_fit": item.score_identity_fit,
                "psychology_benefit": item.score_psychology_benefit,
                "risk_elimination": item.score_risk_elimination,
                "product_identity": item.score_product_identity,
                "compatibility": item.score_compatibility,
                "subjective_properties": item.score_subjective_properties,
                "differentiation": item.score_differentiation,
                "market_trend": item.score_market_trend,
            },
            "created_at": item.created_at.isoformat() if item.created_at else None,
        })

    return {"items": items, "total": total, "stats": stats}


@router.get("/history/{diagnosis_id}")
async def get_diagnosis_detail(
    diagnosis_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full diagnosis detail by ID."""
    scope_user_ids = await get_user_scope_ids(current_user, db)
    svc = Listing_diagnosesService(db)
    record = await svc.get_by_id(diagnosis_id, user_id=scope_user_ids)
    if not record:
        raise HTTPException(status_code=404, detail="诊断记录不存在")

    diagnosis_report = {}
    keyword_report = {}
    input_data = {}
    try:
        if record.diagnosis_report:
            diagnosis_report = json.loads(record.diagnosis_report)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        if record.keyword_report:
            keyword_report = json.loads(record.keyword_report)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        if record.input_data:
            input_data = json.loads(record.input_data)
    except (json.JSONDecodeError, TypeError):
        pass

    scores = {
        "function_expression": record.score_function_expression,
        "scenario_expression": record.score_scenario_expression,
        "identity_fit": record.score_identity_fit,
        "psychology_benefit": record.score_psychology_benefit,
        "risk_elimination": record.score_risk_elimination,
        "product_identity": record.score_product_identity,
        "compatibility": record.score_compatibility,
        "subjective_properties": record.score_subjective_properties,
        "differentiation": record.score_differentiation,
        "market_trend": record.score_market_trend,
    }
    if input_data:
        try:
            saved_listing = ListingInput(**input_data)
            diagnosis_report = _normalize_diagnosis_result({**diagnosis_report, "scores": scores}, saved_listing)
            scores = diagnosis_report.get("scores", scores)
        except Exception:
            pass

    return {
        "id": record.id,
        "listing_title": record.listing_title,
        "marketplace": record.marketplace,
        "input_data": input_data,
        "scores": scores,
        "diagnosis_report": diagnosis_report,
        "keyword_report": keyword_report,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


# ---------- Scrape Log Models ----------

class ScrapeLogRequest(BaseModel):
    asin: str
    marketplace: str = "US"
    scrape_method: str  # cors_proxy, server_scrape, manual_paste, ai_search
    success: bool
    data_source: str = ""  # scraped, browser_proxy, ai_search, ai_estimated, manual, failed
    error_message: str = ""


class ScrapeStatsResponse(BaseModel):
    total_attempts: int = 0
    total_success: int = 0
    success_rate: float = 0.0
    method_stats: dict = {}  # { method: { total, success, rate } }
    recent_logs: list = []


# ---------- Scrape Log Endpoints ----------

@router.post("/scrape-log")
async def log_scrape_attempt(
    request: ScrapeLogRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record a scrape attempt result."""
    try:
        from services.scrape_logs import Scrape_logsService
        svc = Scrape_logsService(db)
        record = await svc.create({
            "asin": request.asin,
            "marketplace": request.marketplace,
            "scrape_method": request.scrape_method,
            "success": request.success,
            "data_source": request.data_source,
            "error_message": request.error_message,
            "created_at": datetime.now(timezone.utc),
        }, user_id=str(current_user.id))
        return {"success": True, "id": record.id if record else None}
    except Exception as e:
        logger.error(f"Error logging scrape attempt: {e}")
        return {"success": False, "message": str(e)}


@router.get("/scrape-stats", response_model=ScrapeStatsResponse)
async def get_scrape_stats(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get scrape statistics for the current user."""
    try:
        from sqlalchemy import select, func, case, cast, Float
        from models.scrape_logs import Scrape_logs as SL

        scope_user_ids = await get_user_scope_ids(current_user, db)

        # Overall stats
        overall_q = select(
            func.count(SL.id).label("total"),
            func.sum(case((SL.success == True, 1), else_=0)).label("success_count"),
        ).where(SL.user_id.in_(scope_user_ids))
        overall_result = await db.execute(overall_q)
        overall_row = overall_result.one_or_none()

        total_attempts = int(overall_row.total or 0) if overall_row else 0
        total_success = int(overall_row.success_count or 0) if overall_row else 0
        success_rate = round((total_success / total_attempts * 100), 1) if total_attempts > 0 else 0.0

        # Per-method stats
        method_q = select(
            SL.scrape_method,
            func.count(SL.id).label("total"),
            func.sum(case((SL.success == True, 1), else_=0)).label("success_count"),
        ).where(SL.user_id.in_(scope_user_ids)).group_by(SL.scrape_method)
        method_result = await db.execute(method_q)
        method_rows = method_result.all()

        method_stats = {}
        for row in method_rows:
            m_total = int(row.total or 0)
            m_success = int(row.success_count or 0)
            m_rate = round((m_success / m_total * 100), 1) if m_total > 0 else 0.0
            method_stats[row.scrape_method] = {
                "total": m_total,
                "success": m_success,
                "rate": m_rate,
            }

        # Recent logs (last 10)
        recent_q = (
            select(SL)
            .where(SL.user_id.in_(scope_user_ids))
            .order_by(SL.id.desc())
            .limit(10)
        )
        recent_result = await db.execute(recent_q)
        recent_rows = recent_result.scalars().all()

        recent_logs = []
        for log in recent_rows:
            recent_logs.append({
                "id": log.id,
                "asin": log.asin,
                "marketplace": log.marketplace,
                "scrape_method": log.scrape_method,
                "success": log.success,
                "data_source": log.data_source,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            })

        return ScrapeStatsResponse(
            total_attempts=total_attempts,
            total_success=total_success,
            success_rate=success_rate,
            method_stats=method_stats,
            recent_logs=recent_logs,
        )
    except Exception as e:
        logger.error(f"Error getting scrape stats: {e}")
        return ScrapeStatsResponse()


class SaveFetchedRequest(BaseModel):
    listing: ListingInput
    source: str = ""
    asin: str = ""
    rating: str = ""
    review_count: str = ""
    bsr_rank: str = ""


@router.post("/save-fetched")
async def save_fetched_listing(
    request: SaveFetchedRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a fetched listing immediately to the database (before diagnosis)."""
    try:
        listing = request.listing
        if not listing.title:
            return {"success": False, "message": "No title to save"}

        svc = Listing_diagnosesService(db)
        record = await svc.create_or_update_by_asin({
            "listing_title": (listing.title or "")[:500],
            "marketplace": listing.marketplace or "US",
            "input_data": json.dumps(listing.model_dump(), ensure_ascii=False),
            "score_function_expression": 0,
            "score_scenario_expression": 0,
            "score_identity_fit": 0,
            "score_psychology_benefit": 0,
            "score_risk_elimination": 0,
            "score_product_identity": 0,
            "score_compatibility": 0,
            "score_subjective_properties": 0,
            "score_differentiation": 0,
            "score_market_trend": 0,
            "diagnosis_report": json.dumps({
                "status": "fetched",
                "source": request.source,
                "asin": request.asin,
                "rating": request.rating,
                "review_count": request.review_count,
                "bsr_rank": request.bsr_rank,
            }, ensure_ascii=False),
            "keyword_report": "{}",
            "created_at": datetime.now(timezone.utc),
        }, asin=request.asin or listing.asin, marketplace=listing.marketplace or "US", user_id=str(current_user.id))

        record_id = record.id if record else None
        await _sync_asin_profile_from_listing_record(db, str(current_user.id), record)
        logger.info(f"Saved fetched listing '{listing.title[:60]}' with id={record_id}")
        return {"success": True, "id": record_id}
    except Exception as e:
        logger.error(f"Save fetched listing error: {e}")
        return {"success": False, "message": str(e)}


@router.delete("/history/{diagnosis_id}")
async def delete_diagnosis_record(
    diagnosis_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a diagnosis record by ID."""
    scope_user_ids = await get_user_scope_ids(current_user, db)
    svc = Listing_diagnosesService(db)
    deleted = await svc.delete(diagnosis_id, user_id=scope_user_ids)
    if not deleted:
        raise HTTPException(status_code=404, detail="诊断记录不存在或无权删除")
    return {"success": True, "message": "已删除"}
