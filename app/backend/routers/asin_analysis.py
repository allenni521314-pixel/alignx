"""
ASIN Product Analysis Router.
Provides AI-powered product analysis and 10-dimension scoring.
Uses web scraping to get real product data. No AI estimation fallback — precision is the core value.
Optimized: single AI call for both product enrichment + scoring.
"""

import json
import logging
import copy
import re
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
from services.amazon_scraper import scrape_amazon_product
from services.amazon_skill_toolbox import (
    build_review_intent_assets,
    build_toolbox_enhancements,
    normalize_review_samples,
)
from services.asin_analyses import Asin_analysesService
from services.canonical_10d_scoring import (
    canonical_to_asin_scores,
    product_evidence_similarity,
)
from services.cosmo_operator_agent import CosmoOperatorAgent
from services.human_nature_model import human_nature_prompt_block

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/asin-analysis", tags=["asin-analysis"])


_US_SPELLING_REPLACEMENTS = {
    "colour": "color",
    "colours": "colors",
    "flavour": "flavor",
    "flavours": "flavors",
    "favourite": "favorite",
    "odour": "odor",
    "odours": "odors",
    "behaviour": "behavior",
    "traveller": "traveler",
    "travelling": "traveling",
    "organiser": "organizer",
    "organisers": "organizers",
    "centre": "center",
    "centres": "centers",
}


def _normalize_us_keyword(value) -> str:
    """Keep only original English Amazon keywords, not Chinese or translated fallbacks."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    if re.search(r"[\u4e00-\u9fff]", text):
        return ""
    text = re.sub(r"[^a-z0-9\s+&/-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -/&")
    if not text:
        return ""
    words = []
    for word in text.split():
        words.append(_US_SPELLING_REPLACEMENTS.get(word, word))
    normalized = " ".join(words)
    if len(normalized.split()) > 8:
        normalized = " ".join(normalized.split()[:8])
    return normalized if re.search(r"[a-z]", normalized) else ""


def _normalize_us_keyword_list(values, limit: int = 10) -> list[str]:
    if isinstance(values, str):
        values = re.split(r"[,;\n]+", values)
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        keyword = _normalize_us_keyword(value)
        if keyword and keyword not in seen:
            result.append(keyword)
            seen.add(keyword)
        if len(result) >= limit:
            break
    return result


def _is_english_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text.strip()) and not re.search(r"[\u4e00-\u9fff]", text) and re.search(r"[A-Za-z]", text) is not None


def _derive_us_keywords_from_real_text(product_data: dict, limit: int = 10) -> list[str]:
    """Derive Amazon-style keywords from scraped text without exposing Chinese UI text."""
    chunks: list[str] = []
    for key in ["title", "category", "bsr_category"]:
        value = product_data.get(key)
        if value:
            chunks.append(str(value))
    for bp in product_data.get("bullet_points") or []:
        if bp:
            chunks.append(str(bp))
    text = " ".join(chunks).lower()
    if not text:
        return []

    candidates: list[str] = []
    def has(pattern: str) -> bool:
        return re.search(pattern, text, flags=re.I) is not None

    if has(r"\b(bluetooth|speaker|boombox|audio)\b"):
        candidates += ["portable bluetooth speaker", "wireless speaker"]
        if has(r"\b(waterproof|ipx|beach|pool|shower|outdoor|camping)\b"):
            candidates += ["waterproof bluetooth speaker", "speaker for beach trips", "outdoor waterproof speaker"]
        if has(r"\b(fm|radio)\b"):
            candidates.append("bluetooth speaker with fm radio")
        if has(r"\b(clip|strap|lanyard|carry)\b"):
            candidates.append("portable speaker with carrying strap")
    if has(r"\b(cat|litter|odor|ammonia)\b"):
        candidates += ["cat litter box odor control", "litter box for apartment cats", "ammonia odor control"]
    if has(r"\b(power bank|portable charger|battery pack|mah)\b"):
        candidates += ["portable phone power bank", "power bank for travel", "compact charger for purse"]
    if has(r"(手机壳|保护壳|iphone|magsafe|phone case|\bcase\b)"):
        candidates += ["iphone case", "magsafe iphone case", "protective iphone case"]
        if has(r"(透明|clear|translucent)"):
            candidates.append("clear iphone case")
        if has(r"(防摔|shock|drop|military|protection|protective)"):
            candidates.append("shockproof iphone case")
        if has(r"(磁吸|magnetic|magsafe)"):
            candidates.append("magnetic phone case")
        if has(r"(防指纹|fingerprint)"):
            candidates.append("anti fingerprint phone case")
    if has(r"\b(bamboo|boxer|underwear|trunks)\b"):
        candidates += ["men's bamboo boxer briefs", "breathable boxer briefs for men", "moisture wicking underwear for men"]
    if has(r"\b(gift|mom|dad|women|men|teen|kids)\b"):
        candidates += ["gift for mom", "gift for men", "gift for teens"]

    # Add conservative title phrase only when it is English.
    words = re.sub(r"[^a-z0-9\s]", " ", text).split()
    stop = {"the", "and", "with", "for", "from", "this", "that", "your", "you", "are", "new", "pink", "white", "black"}
    words = [w for w in words if len(w) > 2 and w not in stop]
    if len(words) >= 3:
        candidates.append(" ".join(words[:4]))

    return _normalize_us_keyword_list(candidates, limit)


def _clean_original_english_keywords(values: Any, product_data: dict, limit: int = 10) -> list[str]:
    keywords = _normalize_us_keyword_list(values, limit)
    keywords = [kw for kw in keywords if _is_english_text(kw)]
    if keywords:
        return keywords[:limit]
    return _derive_us_keywords_from_real_text(product_data, limit)


def _keywords_from_module_text(values: Any, category: str = "", limit: int = 8) -> list[str]:
    """Extract module-specific keyword candidates from localized or English Amazon text."""
    if isinstance(values, str):
        chunks = [values]
    elif isinstance(values, list):
        chunks = []
        for item in values:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                chunks.extend(str(item.get(key) or "") for key in ("title", "body", "text"))
    elif isinstance(values, dict):
        chunks = [str(values.get(key) or "") for key in ("title", "body", "text", "summary")]
    else:
        chunks = []

    usable_chunks = [chunk for chunk in chunks if str(chunk or "").strip()]
    if not usable_chunks:
        return []
    data = {
        "title": usable_chunks[0],
        "category": category or "",
        "bullet_points": usable_chunks[1:],
    }
    return _derive_us_keywords_from_real_text(data, limit)


def _build_listing_breakdown(product_data: dict, scoring_data: dict) -> dict:
    keywords = _clean_original_english_keywords(product_data.get("main_keywords"), product_data, 12)
    title = product_data.get("title") or ""
    bullets = product_data.get("bullet_points") or []
    aplus = product_data.get("aplus_content") or ""
    category = product_data.get("category") or product_data.get("bsr_category") or ""
    image_urls = product_data.get("image_urls") or []
    aplus_image_urls = product_data.get("aplus_image_urls") or []
    low_reviews = product_data.get("low_star_reviews") or []
    used_keywords: set[str] = set()

    def take_module_keywords(candidates: list[str], limit: int = 5) -> list[str]:
        result: list[str] = []
        for keyword in _normalize_us_keyword_list(candidates, limit * 3):
            if keyword in used_keywords:
                continue
            result.append(keyword)
            used_keywords.add(keyword)
            if len(result) >= limit:
                break
        return result

    title_keywords = take_module_keywords(
        _keywords_from_module_text(title, category, 10) + keywords,
        5,
    )
    bullet_keywords = take_module_keywords(
        _keywords_from_module_text(bullets, category, 10),
        6,
    )
    aplus_keywords = take_module_keywords(
        _keywords_from_module_text(aplus, category, 10),
        5,
    )
    review_keywords = take_module_keywords(
        _keywords_from_module_text(low_reviews, category, 10),
        5,
    )

    def module(
        key: str,
        name: str,
        raw: Any,
        structure: list[str],
        strengths: list[str],
        weaknesses: list[str],
        intents: list[str],
        actions: list[str],
        avoid: list[str],
        module_keywords: list[str] | None = None,
    ) -> dict:
        return {
            "key": key,
            "name": name,
            "summary": strengths[0] if strengths else "已按竞品Listing证据完成拆解。",
            "raw_content": raw,
            "structure_breakdown": structure,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "covered_user_intents": intents,
            "keywords": (module_keywords or [])[:8],
            "borrowable_actions": actions,
            "do_not_copy": avoid,
        }

    title_words = len(re.findall(r"[A-Za-z0-9]+", title))
    bullet_count = len(bullets)
    image_count = int(float(str(product_data.get("image_count") or 0).replace(",", "") or 0))
    has_aplus = bool(product_data.get("has_a_plus"))
    has_video = bool(product_data.get("has_video"))
    rating_histogram = product_data.get("rating_histogram") or {}
    seller_type = str(product_data.get("seller_type") or "")
    platform_bound = bool(product_data.get("platform_ecosystem") or "平台生态" in seller_type or "Amazon自营" in seller_type)
    platform_avoid = ["该竞品可能依赖Amazon自有生态或官方流量，不建议按普通第三方产品直接模仿。"] if platform_bound else []

    return {
        "modules": [
            module(
                "title",
                "标题结构分析",
                title,
                ["标题按“品牌/身份词 → 核心品类词 → 关键属性 → 规格数量 → 适用对象或场景”的顺序承接搜索识别。"],
                ["标题能让平台识别产品身份。" if title_words >= 8 else "标题较短，核心身份可识别但承载信息有限。"],
                (["若标题缺少关系词或状态触发词，广告验证词承接会偏弱。"] + (["平台自营标题可能有品牌流量加成，不能只看标题结构。"] if platform_bound else [])),
                ["识别产品身份", "确认核心品类", "理解关键属性", "判断适用对象/场景"],
                ["提炼竞品标题中的品类词、关系词和状态触发词，迁移为我方标题候选结构。"],
                ["不要照抄竞品品牌词、夸张词或与我方产品无关的规格。"] + platform_avoid,
                title_keywords,
            ),
            module(
                "bullets",
                "五点卖点分析",
                bullets,
                [f"已识别 {bullet_count} 条五点，需检查是否按功能、效果、场景、信任、售后/风险消除的顺序讲清购买理由。"],
                ["五点覆盖了多个购买理由。" if bullet_count >= 4 else "五点数量不足，仍可观察其核心承诺。"],
                ["需要验证每条五点是否只讲一个购买理由，避免堆参数。"],
                ["确认功能效果", "降低购买犹豫", "理解使用场景", "建立信任", "消除售后/风险顾虑"],
                ["借鉴竞品五点的购买理由顺序：功能、效果、场景、信任、售后。"],
                ["不要复制没有证据支撑的最高级承诺。"] + platform_avoid,
                bullet_keywords,
            ),
            module(
                "main_image",
                "主图点击力分析",
                image_urls[:1],
                ["主图只负责点击和快速识别：白底真实商品、主体清晰、无干扰文字，并让用户一眼知道卖什么。"],
                ["抓取到主图，可进入视觉模型逐图判断。" if image_urls else "当前只抓到图片数量，需接视觉模型读取主图内容。"],
                ["主图点击力最终要结合CTR验证。"],
                ["快速识别产品类型", "降低点击前理解成本"],
                ["借鉴竞品主图的主体角度、清晰度和差异点呈现方式。"],
                ["不要模仿违规文字、水印、夸张道具或与实物不一致的场景。"],
                [],
            ),
            module(
                "secondary_images",
                "副图信息结构分析",
                image_urls[1:8],
                [f"识别到 {image_count} 张图库图片，副图应按卖点、场景、尺寸结构、对比证据、信任证明和使用步骤依次承接转化。"],
                ["图库数量较完整，具备承接转化的素材基础。" if image_count >= 6 else "图库数量偏少，转化信息可能不完整。"],
                ["需要视觉模型判断每张副图是否承担唯一信息任务。"],
                ["功能理解", "场景想象", "风险消除"],
                ["按7张图逻辑拆竞品：主图点击，2图卖点，3图场景，4图尺寸，5图对比，6图信任，7图步骤。"],
                ["不要把同一套图文重复堆到所有位置。"],
                [],
            ),
            module(
                "a_plus",
                "A+内容结构分析",
                {"text": aplus, "images": aplus_image_urls},
                ["A+负责更深的信任闭环：品牌故事、技术/材质原理、场景教育、差异化证明和对比表不要与前台图片重复。"],
                ["存在A+内容，可支撑品牌信任和深度说明。" if has_aplus else "未抓取到A+内容，信任闭环不足。"],
                ["A+需要避免重复Listing图库，需要承担更深的信任与教育。"],
                ["品牌信任", "购买风险消除", "差异化理解"],
                ["借鉴竞品A+的信息层级，不直接复制图文。"],
                ["不要把前台五点原样搬进A+，A+应讲原理、证据和信任。"],
                aplus_keywords,
            ),
            module(
                "video_brand",
                "视频/品牌内容分析",
                "有视频" if has_video else "未检测到视频",
                ["视频按使用方法、动态效果、结果证明、品牌信任的顺序，让用户看到功能如何真实发生。"],
                ["有视频素材，可提升使用理解。" if has_video else "未检测到视频，竞品动态证明较弱。"],
                ["视频是否有效仍需看点击和转化数据验证。"],
                ["使用方法", "效果证明", "品牌信任"],
                ["若竞品没有视频，我方可用短视频补强动态使用证据。"],
                ["不要做纯氛围视频，必须让用户看到功能和使用结果。"],
                [],
            ),
            module(
                "review_validation",
                "评论反向验证",
                low_reviews,
                ["评论反向验证按评分分布、3星以下差评、未满足需求、可攻击弱点的顺序提炼机会。"],
                ["已抓取评分分布，可用于判断差评比例。" if rating_histogram else "评分分布暂未抓取完整。"],
                ["低分评论越完整，越能反推真实痛点。"],
                ["质量风险", "使用阻碍", "售后疑虑"],
                ["把3星以下评论转成我方必须规避的承诺、图片和五点检查项。"],
                ["不要只看好评卖点，竞品真正的机会往往在低分评论。"],
                review_keywords,
            ),
        ],
        "rating_histogram": rating_histogram,
        "low_star_reviews": low_reviews,
        "image_urls": image_urls,
        "aplus_image_urls": aplus_image_urls,
    }


class AnalyzeAsinRequest(BaseModel):
    asin: str
    marketplace: str = "US"
    force_refresh: bool = False


class AnalyzeAsinResponse(BaseModel):
    asin: str
    marketplace: str
    product_title: str
    product_data: dict
    scores: dict
    analysis_report: dict
    amazon_compliance: dict = {}
    data_source: str = "unknown"
    id: Optional[int] = None


def _image_signals_from_product_data(product_data: dict) -> dict:
    return {
        "main_image": {
            "text_detected": bool(product_data.get("main_image_text_detected")),
            "badge_detected": bool(product_data.get("main_image_badge_detected")),
            "watermark_detected": bool(product_data.get("main_image_watermark_detected")),
            "logo_overlay_detected": bool(product_data.get("main_image_logo_overlay_detected")),
            "non_white_background": bool(product_data.get("main_image_non_white_background")),
        },
        "secondary_images": product_data.get("secondary_image_analysis") or {},
        "image_count": product_data.get("image_count") or len(product_data.get("image_urls") or []),
    }


async def _evaluate_asin_compliance(product_data: dict, marketplace: str, db: AsyncSession) -> dict:
    rules = await load_active_rules(db)
    bullets = product_data.get("bullet_points") or []
    description = product_data.get("description") or product_data.get("description_summary") or ""
    a_plus_text = product_data.get("aplus_content") or product_data.get("a_plus_content") or ""
    claims = "\n".join(
        str(part)
        for part in [
            product_data.get("title") or "",
            "\n".join(str(bp) for bp in bullets) if isinstance(bullets, list) else bullets,
            description,
            a_plus_text,
        ]
        if part
    )
    payload = {
        "marketplace": marketplace or "US",
        "product_type": product_data.get("category") or product_data.get("product_type") or "",
        "title": product_data.get("title") or "",
        "bullets": bullets,
        "description": description,
        "a_plus_text": a_plus_text,
        "image_analysis": _image_signals_from_product_data(product_data),
        "claims": claims,
        "attributes": product_data.get("product_details") or {},
    }
    return evaluate_amazon_compliance(payload, rules)


async def _get_cached_asin_analysis(
    asin: str,
    marketplace: str,
    db: AsyncSession,
    user_id: str | list[str],
) -> AnalyzeAsinResponse | None:
    """Return the latest saved ASIN analysis so the same ASIN does not receive drifting scores."""
    from sqlalchemy import select
    from models.asin_analyses import Asin_analyses

    user_filter = Asin_analyses.user_id.in_(user_id) if isinstance(user_id, list) else Asin_analyses.user_id == user_id
    result = await db.execute(
        select(Asin_analyses)
        .where(Asin_analyses.asin == asin, Asin_analyses.marketplace == marketplace)
        .where(user_filter)
        .where(Asin_analyses.product_title.isnot(None), Asin_analyses.analysis_report.isnot(None))
        .order_by(Asin_analyses.id.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()
    if not record:
        return None
    return await _analysis_record_to_response(record, marketplace, db, user_id)


async def _analysis_record_to_response(
    record: Any,
    marketplace: str,
    db: AsyncSession,
    user_id: str | list[str],
) -> AnalyzeAsinResponse | None:
    """Build the full API response from a saved ASIN analysis record."""
    try:
        product_data = json.loads(record.product_data or "{}")
    except Exception:
        product_data = {}
    try:
        analysis_report = json.loads(record.analysis_report or "{}")
    except Exception:
        analysis_report = {}
    scores = {
        "functionality": record.score_functionality or 0,
        "emotional": record.score_emotional or 0,
        "scenario": record.score_scenario or 0,
        "user_profile": record.score_user_profile or 0,
        "product_identity": record.score_product_identity or 0,
        "compatibility": record.score_compatibility or 0,
        "subjective_properties": record.score_subjective_properties or 0,
        "differentiation": record.score_differentiation or 0,
        "market_trend": record.score_market_trend or 0,
        "risk_elimination": record.score_risk_elimination or 0,
    }
    product_data["main_keywords"] = _clean_original_english_keywords(product_data.get("main_keywords"), product_data, 10)
    aligned = CosmoOperatorAgent.align_scores(
        analysis_report.get("canonical_10d_scores") or analysis_report.get("scores") or scores,
        product_data,
    )
    scores = aligned["asin_scores"]
    if not _has_positive_scores(scores):
        return None
    analysis_report["scores"] = aligned["scores"]
    analysis_report["canonical_10d_scores"] = aligned["canonical_scores"]
    analysis_report["score_basis"] = "amazon_skill_10d_canonical"
    analysis_report["market_reality_caps"] = aligned["market_reality_caps"]
    shared_snapshot = await _find_shared_listing_score_snapshot(record.asin, marketplace, product_data, db, user_id)
    if shared_snapshot:
        scores = shared_snapshot["asin_scores"]
        _apply_shared_listing_snapshot(analysis_report, shared_snapshot)
    if not analysis_report.get("listing_breakdown"):
        analysis_report["listing_breakdown"] = _build_listing_breakdown(product_data, analysis_report)
    analysis_report["toolbox_enhancements"] = analysis_report.get("toolbox_enhancements") or build_toolbox_enhancements(
        product_data=product_data,
        scores=analysis_report["scores"],
        context="competitor",
    )
    data_source = str(product_data.get("_data_source") or analysis_report.get("data_source") or "cached_analysis")
    amazon_compliance = analysis_report.get("amazon_compliance") or {}
    return AnalyzeAsinResponse(
        asin=record.asin,
        marketplace=record.marketplace or marketplace,
        product_title=record.product_title or product_data.get("title", ""),
        product_data=product_data,
        scores=scores,
        analysis_report=analysis_report,
        amazon_compliance=amazon_compliance,
        data_source=data_source,
        id=record.id,
    )


def _apply_shared_listing_snapshot(scoring_data: dict, shared_snapshot: dict) -> None:
    """Apply the saved Listing 10D judgment as the canonical source for the same ASIN."""
    scoring_data["scores"] = shared_snapshot["score_aliases"]
    scoring_data["canonical_10d_scores"] = shared_snapshot["canonical_scores"]
    scoring_data["score_basis"] = "amazon_skill_10d_canonical_shared_listing_snapshot"
    scoring_data["shared_score_source"] = {
        "type": shared_snapshot["source"],
        "id": shared_snapshot["source_id"],
        "similarity": shared_snapshot["similarity"],
    }
    scoring_data["market_reality_caps"] = shared_snapshot["market_reality_caps"]

    shared_analysis = shared_snapshot.get("analysis")
    if isinstance(shared_analysis, dict) and shared_analysis:
        existing_analysis = scoring_data.get("analysis") if isinstance(scoring_data.get("analysis"), dict) else {}
        merged_analysis = dict(existing_analysis)
        for key, value in shared_analysis.items():
            if value not in (None, "", [], {}):
                merged_analysis[key] = value
        if merged_analysis:
            scoring_data["analysis"] = merged_analysis


async def _find_shared_listing_score_snapshot(
    asin: str,
    marketplace: str,
    product_data: dict,
    db: AsyncSession,
    user_id: str | list[str],
) -> dict | None:
    """Reuse the latest saved Listing 10D judgment for the same ASIN/user/marketplace."""
    asin = (asin or "").strip().upper()
    if not asin:
        return None
    from sqlalchemy import select
    from models.listing_diagnoses import Listing_diagnoses

    user_filter = Listing_diagnoses.user_id.in_(user_id) if isinstance(user_id, list) else Listing_diagnoses.user_id == user_id
    result = await db.execute(
        select(Listing_diagnoses)
        .where(Listing_diagnoses.marketplace == marketplace)
        .where(user_filter)
        .where(Listing_diagnoses.input_data.isnot(None), Listing_diagnoses.diagnosis_report.isnot(None))
        .order_by(Listing_diagnoses.id.desc())
        .limit(30)
    )
    for record in result.scalars().all():
        try:
            input_data = json.loads(record.input_data or "{}")
            diagnosis_report = json.loads(record.diagnosis_report or "{}")
        except Exception:
            continue
        input_asin = str(input_data.get("asin") or "").strip().upper()
        if input_asin and input_asin != asin:
            continue
        if not input_asin:
            continue
        similarity = product_evidence_similarity(product_data, input_data)
        raw_scores = diagnosis_report.get("canonical_10d_scores") or diagnosis_report.get("scores") or {
            "function_expression": record.score_function_expression or 0,
            "scenario_expression": record.score_scenario_expression or 0,
            "identity_fit": record.score_identity_fit or 0,
            "psychology_benefit": record.score_psychology_benefit or 0,
            "risk_elimination": record.score_risk_elimination or 0,
            "product_identity": record.score_product_identity or 0,
            "compatibility": record.score_compatibility or 0,
            "subjective_properties": record.score_subjective_properties or 0,
            "differentiation": record.score_differentiation or 0,
            "market_trend": record.score_market_trend or 0,
        }
        aligned = CosmoOperatorAgent.align_scores(raw_scores, input_data)
        canonical_scores = aligned["canonical_scores"]
        if not any(canonical_scores.values()):
            continue
        asin_scores = canonical_to_asin_scores(canonical_scores)
        return {
            "source": "listing_diagnosis",
            "source_id": record.id,
            "canonical_scores": canonical_scores,
            "asin_scores": asin_scores,
            "score_aliases": {**asin_scores, **canonical_scores},
            "market_reality_caps": diagnosis_report.get("market_reality_caps") or aligned["market_reality_caps"],
            "similarity": similarity,
            "analysis": diagnosis_report.get("analysis") if isinstance(diagnosis_report.get("analysis"), dict) else {},
        }
    return None


class ParseHtmlAnalyzeRequest(BaseModel):
    """Request to parse raw HTML from a trusted capture source and run full analysis."""
    asin: str
    marketplace: str = "US"
    html: str
    source: str = "server_proxy_fetch"
    captured_title: str = ""
    captured_price: str = ""
    captured_rating: str = ""
    captured_review_count: str = ""
    captured_bsr_rank: str = ""
    captured_image_count: str = ""
    captured_bullets: list[str] = Field(default_factory=list)
    captured_reviews: list[dict[str, Any]] = Field(default_factory=list)


class ParseHtmlAnalyzeResponse(BaseModel):
    success: bool
    asin: str
    product_title: str = ""
    product_data: dict = {}
    scores: dict = {}
    analysis_report: dict = {}
    amazon_compliance: dict = {}
    data_source: str = "server_proxy_fetch"
    capture_quality: dict = {}
    error: str = ""
    id: Optional[int] = None


class ProxyFetchRequest(BaseModel):
    """Request to fetch Amazon HTML via our backend (no public CORS proxies)."""
    asin: str
    marketplace: str = "US"


class ProxyFetchResponse(BaseModel):
    success: bool
    html: str = ""
    error: str = ""


class CompareAsinsRequest(BaseModel):
    my_asin: str
    competitor_asins: List[str]
    marketplace: str = "US"


class CompareAsinsResponse(BaseModel):
    my_product: AnalyzeAsinResponse
    competitors: List[AnalyzeAsinResponse]
    comparison: dict


# ---- Combined Prompt (single AI call for enrichment + scoring) ---- #

COMBINED_ANALYSIS_WITH_CONTEXT_PROMPT = """你是AlignX的10维诊断系统专家，同时也是专业的亚马逊产品分析师。

## 已抓取的真实产品数据
ASIN: {asin}
站点: Amazon {marketplace}
{scraped_context}

## 任务
请完成以下两项任务，合并为一个JSON返回：

### 任务1：产品数据补充
基于以上真实数据，补充缺失的字段（如预估月销量、月收入等）。已有真实数据直接使用，不要修改。
真实字段硬性约束：标题、品牌、类目、价格、评分、评论数、BSR、上架时间、五点、A+文本必须以抓取数据为准；不要翻译、不要改写、不要自行估算覆盖真实字段。

### 任务2：人性根层 × 用户需求 × 平台识别 × 10维诊断
本任务不是把10个维度当作平铺同级指标简单平均。必须先判断竞品/ASIN背后的趋利/避害、人性节点、动机、需求、场景和解决方案，再判断为什么被用户选择、为什么被Amazon匹配，最后用10维诊断做反向检查。

**人性根层标准**
- Level 0：趋利（Gain）/ 避害（Loss）。
- Level 1：生存 / 繁衍 / 资源 / 探索。
- Level 2：13个人性节点。
- Level 3：动机。
- Level 4：需求。
- Level 5：场景。
- Level 6：解决方案。
- Level 7：表达。
- Level 8：行为。
- Level 9：结果。
- 禁止从关键词开始推理；关键词只能是Level 7表达或广告验证资产。

**用户需求标准**
- 任务对象清晰度：用户是谁，要完成什么任务，想得到什么结果。
- 购买触发强度：用户为什么现在需要它，痛点/损失/效率/安心感是否明确。
- 使用场景约束：地点、人群、搭配、时间、限制和不适用边界是否清楚。
- 决策属性优先级：用户买前最先确认的尺寸、材质、效果、安全、兼容、价格或信任证据。
- 反购买风险：为什么不买、退货、差评或产生错误期待。

**平台识别标准**
- 类目身份锚定：Amazon能否识别产品类型、子类目、核心对象。
- 查询意图匹配：核心词、场景词、问题词、属性词是否与用户任务对应。
- 结构化属性完整度：尺寸、材质、数量、规格、兼容性、变体是否可抽取。
- 关系图谱完整度：for whom、used for、used with、in scenario、solves 是否清楚。
- 证据可回答性：标题、图片、五点、A+、评论是否能回答用户和平台购物助手的问题。

每个analysis字段必须输出：人性根层映射、用户需求映射、平台识别映射、真实证据、强点/漏洞、我方动作（借鉴/避开/攻击/差异化）和广告验证假设。后台判断必须按1人性根层、2用户意图、3平台规则、4验证回流的顺序执行，但不要把内部流程原文暴露给前台卖家。

从以下10个维度进行评分（每个维度0-100分）并给出详细分析：

**基础承接维度：**
1. 功能性(functionality): 产品功能是否完善、是否满足核心需求
2. 情感性(emotional): 品牌故事、情感连接、用户体验感受
3. 场景性(scenario): 使用场景是否明确、场景覆盖是否全面
4. 用户画像(user_profile): 目标用户是否清晰、是否精准定位
5. 产品身份(product_identity): is_a/used_as定义是否清晰，品类归属是否准确
6. 兼容搭配(compatibility): used_with关系是否明确，配件/搭配场景覆盖
7. 感性属性(subjective_properties): 感性描述词是否丰富，能否触发感官联想
8. 差异化(differentiation): 与竞品差异点、独特卖点(USP)

**卖家扩展2D维度：**
9. 市场趋势(market_trend): 市场增长趋势、品类热度、竞争程度
10. 风险消除(risk_elimination): 是否有效消除购买顾虑

### 关键词硬性规则
- main_keywords 必须是自然美式英语 Amazon 搜索词，不允许中文、不允许直译腔。
- main_keywords 只能来自真实抓取到的英文标题、五点、类目、A+或评论语义；如果原始字段是中文或不确定，返回空数组，不要翻译、不要补中文词。
- 关键词必须符合平台可识别结构：产品身份词 + 使用关系词 + 场景状态词。
- 不要只输出 product attribute words（如 material、size、color），必须优先包含 relationship words 与 state-trigger words。
- relationship words 示例：for apartment cats, with odor filter, under desk speaker, for mom gifts, compatible with xxx。
- state-trigger words 示例：ammonia odor control, litter tracking mess, outdoor party sound, sleep noise relief。
- 属性词只做基础覆盖；关系词和状态触发词用于广告验证与转化假设。

请以JSON格式返回（确保返回有效的JSON）：
{{
  "product_data": {{
    "title": "产品标题（使用真实标题）",
    "brand": "品牌名",
    "category": "产品类目",
    "price": "价格",
    "price_currency": "货币代码",
    "rating": "评分（1-5）",
    "review_count": "评论数量",
    "date_first_available": "上架时间/Date First Available（直接使用真实抓取字段，不要改）",
    "bsr_rank": "BSR排名",
    "bsr_category": "BSR所在类目",
    "bullet_points": ["卖点1", "卖点2", "卖点3", "卖点4", "卖点5"],
    "description_summary": "产品描述摘要",
    "main_keywords": ["amazon us keyword 1", "relationship keyword 2", "state trigger keyword 3", "long tail keyword 4", "product identity keyword 5"],
    "seller_type": "FBA/FBM/Amazon自营",
    "amazon_bought_count": "亚马逊前台显示的官方购买人数（如 '1K+ bought in past month'，直接使用抓取数据，不要修改）",
    "estimated_monthly_sales": "BSR预估月销量（基于BSR排名算法估算的数字，仅作参考）",
    "estimated_monthly_revenue": "预估月收入（美元，数字）",
    "listing_quality_notes": "Listing质量简评",
    "image_count": "主图数量",
    "has_video": true/false,
    "has_a_plus": true/false,
    "rating_histogram": {{"5_star": "79%", "4_star": "10%", "3_star": "5%", "2_star": "2%", "1_star": "4%"}},
    "low_star_reviews": [{{"rating": 2, "title": "review title", "body": "full review body", "date": "review date", "verified": true}}],
    "variation_count": "变体数量",
    "data_confidence": "high/medium/low",
    "data_notes": "数据来源说明"
  }},
  "scores": {{
    "functionality": 分数,
    "emotional": 分数,
    "scenario": 分数,
    "user_profile": 分数,
    "product_identity": 分数,
    "compatibility": 分数,
    "subjective_properties": 分数,
    "differentiation": 分数,
    "market_trend": 分数,
    "risk_elimination": 分数
  }},
  "analysis": {{
    "functionality": "功能性分析详情...",
    "emotional": "情感性分析详情...",
    "scenario": "场景性分析详情...",
    "user_profile": "用户画像分析详情...",
    "product_identity": "产品身份分析详情...",
    "compatibility": "兼容搭配分析详情...",
    "subjective_properties": "感性属性分析详情...",
    "differentiation": "差异化分析详情...",
    "market_trend": "市场趋势分析详情...",
    "risk_elimination": "风险消除分析详情..."
  }},
  "overall_summary": "总体评价摘要...",
  "improvement_suggestions": ["建议1", "建议2", "建议3"]
}}

只返回JSON，不要返回其他内容。"""


AI_FALLBACK_ANALYSIS_PROMPT = """你是AlignX亚马逊ASIN分析专家。

当前系统无法通过本地浏览器页面采集或服务器抓取获得该ASIN的完整页面数据。
请基于用户提供的ASIN、站点和你可推断的公开常识，生成一个低置信度的结构化分析结果。

重要规则：
1. 不要伪装成真实抓取数据。
2. 不确定字段必须留空或标记“待确认”。
3. data_confidence 必须为 low。
4. data_notes 必须说明“AI兜底估算，需以本地浏览器页面采集、服务器抓取或人工核实为准”。
5. 仍需给出可用于初步测试的10维诊断评分，但分数要保守；analysis必须说明低置信度和待补证据。

ASIN: {asin}
站点: Amazon {marketplace}

请只返回JSON：
{{
  "product_data": {{
    "title": "待确认",
    "brand": "待确认",
    "category": "待确认",
    "price": "",
    "rating": "",
    "review_count": "",
    "bsr_rank": "",
    "bsr_category": "",
    "bullet_points": [],
    "description_summary": "待确认",
    "main_keywords": [],
    "seller_type": "待确认",
    "amazon_bought_count": "",
    "estimated_monthly_sales": "",
    "estimated_monthly_revenue": "",
    "listing_quality_notes": "AI兜底估算，需核实",
    "image_count": "",
    "has_video": false,
    "has_a_plus": false,
    "variation_count": "",
    "data_confidence": "low",
    "data_notes": "AI兜底估算，需以本地浏览器页面采集、服务器抓取或人工核实为准"
  }},
  "scores": {{
    "functionality": 50,
    "emotional": 50,
    "scenario": 50,
    "user_profile": 50,
    "product_identity": 50,
    "compatibility": 50,
    "subjective_properties": 50,
    "differentiation": 50,
    "market_trend": 50,
    "risk_elimination": 50
  }},
  "analysis": {{
    "functionality": "分析详情",
    "emotional": "分析详情",
    "scenario": "分析详情",
    "user_profile": "分析详情",
    "product_identity": "分析详情",
    "compatibility": "分析详情",
    "subjective_properties": "分析详情",
    "differentiation": "分析详情",
    "market_trend": "分析详情",
    "risk_elimination": "分析详情"
  }},
  "overall_summary": "低置信度初步判断",
  "improvement_suggestions": ["建议用户手动粘贴Amazon页面内容后重新分析"]
}}"""


COMPARISON_PROMPT = """你是AlignX的竞品对比分析专家。请对比以下产品的10维诊断数据，生成对比分析报告。

我的产品：
ASIN: {my_asin}
标题: {my_title}
10维诊断: {my_scores}

竞品列表：
{competitor_info}

请以JSON格式返回对比分析（确保返回有效的JSON）：
{{
  "strengths": ["我的产品优势1", "优势2", "优势3"],
  "weaknesses": ["我的产品劣势1", "劣势2", "劣势3"],
  "opportunities": ["机会点1", "机会点2"],
  "threats": ["威胁1", "威胁2"],
  "dimension_comparison": {{
    "functionality": "功能性维度对比分析...",
    "emotional": "情感性维度对比分析...",
    "scenario": "场景性维度对比分析...",
    "user_profile": "用户画像维度对比分析...",
    "product_identity": "产品身份维度对比分析...",
    "compatibility": "兼容搭配维度对比分析...",
    "subjective_properties": "感性属性维度对比分析...",
    "differentiation": "差异化维度对比分析...",
    "market_trend": "市场趋势维度对比分析...",
    "risk_elimination": "风险消除维度对比分析..."
  }},
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
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

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

    # Strategy 1: Try closing unclosed structures by trimming from end
    for trim_len in range(0, min(500, len(text)), 1):
        candidate = text if trim_len == 0 else text[:-trim_len]

        open_braces = candidate.count("{") - candidate.count("}")
        open_brackets = candidate.count("[") - candidate.count("]")

        in_string = False
        i = len(candidate) - 1
        while i >= 0:
            if candidate[i] == '"' and (i == 0 or candidate[i-1] != '\\'):
                in_string = not in_string
                break
            i -= 1

        suffix = ""
        if in_string:
            suffix += '"'

        trimmed = candidate + suffix
        trimmed += "]" * max(0, open_brackets)
        trimmed += "}" * max(0, open_braces)

        try:
            result = json.loads(trimmed)
            if isinstance(result, dict):
                logger.info(f"Successfully repaired truncated JSON (trimmed {trim_len} chars)")
                return result
        except json.JSONDecodeError:
            continue

    # Strategy 2: Line-by-line trimming
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


def _format_scraped_context(scraped: dict) -> str:
    """Format scraped data into a readable context string for the AI prompt."""
    lines = []
    if scraped.get("title"):
        lines.append(f"标题: {scraped['title']}")
    if scraped.get("brand"):
        lines.append(f"品牌: {scraped['brand']}")
    if scraped.get("category"):
        lines.append(f"类目: {scraped['category']}")
    if scraped.get("price"):
        currency = scraped.get("price_currency") or "USD"
        lines.append(f"价格: {currency} {scraped['price']}")
    if scraped.get("date_first_available"):
        lines.append(f"上架时间/Date First Available: {scraped['date_first_available']}")
    if scraped.get("rating"):
        lines.append(f"评分: {scraped['rating']}")
    if scraped.get("review_count"):
        lines.append(f"评论数: {scraped['review_count']}")
    if scraped.get("rating_histogram"):
        lines.append(f"评分分布: {json.dumps(scraped['rating_histogram'], ensure_ascii=False)}")
    if scraped.get("bought_count"):
        lines.append(f"亚马逊官方购买人数: {scraped['bought_count']}")
    if scraped.get("bsr_rank"):
        lines.append(f"BSR排名: #{scraped['bsr_rank']}")
    if scraped.get("bsr_category"):
        lines.append(f"BSR类目: {scraped['bsr_category']}")
    if scraped.get("bullet_points"):
        lines.append("五点描述:")
        for i, bp in enumerate(scraped["bullet_points"], 1):
            lines.append(f"  {i}. {bp}")
    if scraped.get("image_count"):
        lines.append(f"图片数量: {scraped['image_count']}")
    if scraped.get("product_details"):
        details = scraped["product_details"]
        detail_lines = [f"{k}: {v}" for k, v in list(details.items())[:12]]
        lines.append("产品详情:\n  " + "\n  ".join(detail_lines))
    if scraped.get("low_star_reviews"):
        lines.append(f"3星及以下评论样本: {len(scraped['low_star_reviews'])}条")
    review_samples = scraped.get("review_samples") or scraped.get("reviews") or []
    if isinstance(review_samples, list) and review_samples:
        lines.append(f"页面评论样本: {len(review_samples)}条")
    review_assets = scraped.get("review_intent_assets") if isinstance(scraped.get("review_intent_assets"), dict) else {}
    review_keywords = review_assets.get("intent_keywords") if isinstance(review_assets, dict) else []
    if isinstance(review_keywords, list) and review_keywords:
        labels = [
            str(item.get("keyword") or "").strip()
            for item in review_keywords
            if isinstance(item, dict) and str(item.get("keyword") or "").strip()
        ][:10]
        if labels:
            lines.append("评论提取的买家意图/抱怨: " + ", ".join(labels))
    lines.append(f"有视频: {'是' if scraped.get('has_video') else '否'}")
    lines.append(f"有A+内容: {'是' if scraped.get('has_a_plus') else '否'}")
    return "\n".join(lines) if lines else "（未能抓取到数据）"


def _as_number(value: Any, default: float = 0) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)", str(value or "").replace(",", ""))
    if not match:
        return default
    try:
        return float(match.group(1))
    except ValueError:
        return default


def _clamp_score(value: float, low: int = 35, high: int = 88) -> int:
    return max(low, min(high, round(value)))


def _has_positive_scores(scores: Any) -> bool:
    """True when a score payload contains at least one usable non-zero dimension."""
    if not isinstance(scores, dict):
        return False
    for value in scores.values():
        try:
            if float(value or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _rule_based_competitor_scoring(asin: str, marketplace: str, scraped_data: dict) -> tuple[dict, dict]:
    """Build a non-AI diagnostic result from real scraped fields when the model fails.

    This prevents the UI from presenting all-50 default scores as if they were an AI judgment.
    The result is intentionally conservative and marked as rule_fallback.
    """
    title = scraped_data.get("title") or f"ASIN {asin} - 待确认"
    bullets = scraped_data.get("bullet_points") or []
    details = scraped_data.get("product_details") or {}
    image_urls = scraped_data.get("image_urls") or []
    aplus_text = scraped_data.get("aplus_content") or ""
    text_blob = " ".join([title, scraped_data.get("category") or "", " ".join(bullets), aplus_text]).lower()

    rating = _as_number(scraped_data.get("rating"))
    review_count = _as_number(scraped_data.get("review_count"))
    image_count = _as_number(scraped_data.get("image_count"), len(image_urls))
    has_video = bool(scraped_data.get("has_video"))
    has_a_plus = bool(scraped_data.get("has_a_plus") or aplus_text)
    has_price = bool(scraped_data.get("price"))
    has_bsr = bool(scraped_data.get("bsr_rank"))
    has_bought = bool(scraped_data.get("bought_count"))
    bullet_count = len(bullets)

    def has(pattern: str) -> bool:
        return re.search(pattern, text_blob, flags=re.I) is not None

    product_identity_signal = 0
    if has(r"(iphone|phone case|手机壳|保护壳|case|power bank|speaker|litter|boxer)"):
        product_identity_signal += 12
    if scraped_data.get("category"):
        product_identity_signal += 8

    compatibility_signal = 0
    if has(r"(compatible|适用于|兼容|magsafe|iphone\s?\d+|iphone|磁吸|magnetic)"):
        compatibility_signal += 20
    if details:
        compatibility_signal += 5

    scenario_signal = 0
    if has(r"(for |with |outdoor|travel|apartment|office|kids|women|men|兼容|适用于|防摔|防震|透明|磁吸)"):
        scenario_signal += 16
    if bullet_count >= 3:
        scenario_signal += 6

    sensory_signal = 0
    if has(r"(clear|translucent|anti-fingerprint|fingerprint|matte|silicone|leather|soft|thin|轻薄|透明|磨砂|防指纹|防震)"):
        sensory_signal += 18

    risk_signal = 0
    if rating >= 4.3:
        risk_signal += 10
    if review_count >= 500:
        risk_signal += 8
    if has(r"(warranty|return|military|drop|shock|protection|防摔|军规|保护)"):
        risk_signal += 10

    scores = {
        "functionality": _clamp_score(50 + bullet_count * 4 + (8 if has_price else 0) + (5 if rating >= 4 else 0)),
        "emotional": _clamp_score(42 + (8 if has_a_plus else 0) + (5 if has_video else 0) + (6 if image_count >= 5 else 0)),
        "scenario": _clamp_score(45 + scenario_signal + (5 if has_bought else 0)),
        "user_profile": _clamp_score(45 + (12 if has(r"(iphone|kids|women|men|cats|travel|office|apartment|适用于)") else 0) + (5 if bullet_count else 0)),
        "product_identity": _clamp_score(45 + product_identity_signal + (4 if has_price else 0)),
        "compatibility": _clamp_score(42 + compatibility_signal),
        "subjective_properties": _clamp_score(42 + sensory_signal + (5 if image_count >= 4 else 0)),
        "differentiation": _clamp_score(42 + (10 if has_a_plus else 0) + (8 if has_video else 0) + (8 if has(r"(magsafe|magnetic|anti-fingerprint|military|军规|防指纹)") else 0)),
        "market_trend": _clamp_score(48 + (10 if has_bought else 0) + (8 if has_bsr else 0) + (8 if review_count >= 1000 else 0)),
        "risk_elimination": _clamp_score(45 + risk_signal + (5 if scraped_data.get("rating_histogram") else 0)),
    }

    product_data = {
        "title": title,
        "brand": scraped_data.get("brand") or "待确认",
        "category": scraped_data.get("category") or "待确认",
        "price": scraped_data.get("price") or "",
        "price_currency": scraped_data.get("price_currency") or "",
        "rating": scraped_data.get("rating") or "",
        "review_count": scraped_data.get("review_count") or "",
        "date_first_available": scraped_data.get("date_first_available") or "",
        "bsr_rank": scraped_data.get("bsr_rank") or "",
        "bsr_category": scraped_data.get("bsr_category") or "",
        "bullet_points": bullets,
        "description_summary": "深度分析暂未完成，当前为基于真实抓取字段生成的保守预检。",
        "main_keywords": _clean_original_english_keywords([], scraped_data, 10),
        "seller_type": scraped_data.get("seller_type") or "待确认",
        "amazon_bought_count": scraped_data.get("bought_count") or "",
        "estimated_monthly_sales": "",
        "estimated_monthly_revenue": "",
        "listing_quality_notes": "已使用标题、价格、评分、评论、图片、五点和A+等字段做保守预检。",
        "image_count": scraped_data.get("image_count") or str(len(image_urls) or ""),
        "has_video": has_video,
        "has_a_plus": has_a_plus,
        "rating_histogram": scraped_data.get("rating_histogram") or {},
        "low_star_reviews": scraped_data.get("low_star_reviews") or [],
        "image_urls": image_urls,
        "product_details": details,
        "data_confidence": "medium" if scraped_data.get("scrape_success") and title else "low",
        "data_notes": "深度分析暂未完成；本次结果为真实抓取字段驱动的保守预检，建议稍后重新生成完整诊断。",
    }

    analysis = {
        "functionality": f"基于五点数量({bullet_count})、价格字段、评分等可核实字段保守判断。",
        "emotional": "基于A+、视频、图片数量等品牌表达资产判断，非AI语义深度分析。",
        "scenario": "基于标题/五点中的使用关系词、适配词和场景词判断。",
        "user_profile": "基于标题中的适用对象、设备型号和场景词判断。",
        "product_identity": "基于标题、类目和核心品类词判断产品身份清晰度。",
        "compatibility": "基于compatible/适用于/MagSafe/iPhone等适配关系信号判断。",
        "subjective_properties": "基于材质、触感、外观、保护属性等感性词判断。",
        "differentiation": "基于A+、视频、MagSafe、防指纹、军规防摔等差异化信号判断。",
        "market_trend": "基于购买人数、BSR、评论规模等市场热度信号判断。",
        "risk_elimination": "基于评分、评论规模、评分分布和防护/售后信号判断。",
    }
    scoring_data = {
        "scores": scores,
        "analysis": analysis,
        "overall_summary": "深度分析暂未完成，当前为保守预检。分数可用于快速排查，但不应作为最终决策。",
        "improvement_suggestions": ["稍后重新生成完整诊断", "优先核实价格、评论数、购买人数和五点/A+内容", "进入单品分析前先确认该ASIN是否为真实目标竞品"],
        "analysis_mode": "rule_fallback",
        "fallback_reason": "深度分析暂未完成，系统使用真实抓取字段做保守预检。",
    }
    return product_data, scoring_data


async def _analyze_single_asin_with_scraped(
    asin: str,
    marketplace: str,
    user_id: str,
    db: AsyncSession,
    scraped_data: dict,
) -> AnalyzeAsinResponse:
    """Analyze a single ASIN using pre-scraped data + ONE AI call (combined enrichment + scoring).

    This is the core analysis pipeline shared by both the direct analyze endpoint
    and the parse-html-analyze endpoint.
    """
    ai_service = AIHubService()

    scrape_success = scraped_data.get("scrape_success", False)
    data_source = scraped_data.get("data_source", "unknown")

    logger.info(f"Analysis for {asin}: scrape_success={scrape_success}, source={data_source}")

    from schemas.aihub import GenTxtRequest, ChatMessage

    if not (scrape_success and scraped_data.get("title")):
        data_source = "ai_estimated_low_confidence"
    elif data_source == "unknown" and scrape_success:
        data_source = "amazon_scrape"

    if data_source == "ai_estimated_low_confidence":
        combined_prompt = AI_FALLBACK_ANALYSIS_PROMPT.format(asin=asin, marketplace=marketplace)
    else:
        scraped_context = _format_scraped_context(scraped_data)
        combined_prompt = COMBINED_ANALYSIS_WITH_CONTEXT_PROMPT.format(
            asin=asin,
            marketplace=marketplace,
            scraped_context=scraped_context,
        )
    operator_agent = CosmoOperatorAgent(db)
    alignment_context: dict = {}
    try:
        memory_product = {**scraped_data, "asin": asin, "marketplace": marketplace}
        alignment_context = await operator_agent.build_context(
            user_id=user_id,
            workflow="asin_selection",
            product=memory_product,
            asin=asin,
            marketplace=marketplace,
        )
        if alignment_context.get("prompt_summary"):
            combined_prompt += "\n\n" + str(alignment_context["prompt_summary"])[:3500]
    except Exception as e:
        logger.warning(f"123 alignment memory unavailable for ASIN analysis {asin}: {e}")

    # Single AI call for both product data enrichment AND scoring
    combined_request = GenTxtRequest(
        messages=[ChatMessage(role="user", content=combined_prompt)],
        model="AI_REASONING_MODEL",
        temperature=0,
        max_tokens=4096,
    )

    combined_data = None
    for attempt in range(2):
        try:
            combined_response = await ai_service.gentxt(combined_request)
            combined_data = _extract_json(combined_response.content)
            break
        except ValueError as e:
            logger.warning(f"Combined analysis JSON parse failed (attempt {attempt + 1}/2): {e}")
            if attempt == 0:
                combined_request.model = "AI_REASONING_MODEL"
        except Exception as e:
            logger.warning(f"Combined analysis AI call failed for {asin} (attempt {attempt + 1}/2): {e}")
            if attempt == 1:
                break

    # Extract product_data and scoring from combined response
    if combined_data is not None:
        product_data = combined_data.get("product_data", {})
        scores = combined_data.get("scores", {})
        scoring_data = {
            "scores": scores,
            "analysis": combined_data.get("analysis", {}),
            "overall_summary": combined_data.get("overall_summary", ""),
            "improvement_suggestions": combined_data.get("improvement_suggestions", []),
        }
    else:
        logger.error(f"All combined analysis attempts failed for {asin}")
        product_data, scoring_data = _rule_based_competitor_scoring(asin, marketplace, scraped_data)
        scores = scoring_data["scores"]

    # Merge scraped data to ensure real data takes priority
    if scrape_success and scraped_data.get("title"):
        if scraped_data.get("title"):
            product_data["title"] = scraped_data["title"]
        if scraped_data.get("brand"):
            product_data["brand"] = scraped_data["brand"]
        if scraped_data.get("category"):
            product_data["category"] = scraped_data["category"]
        if scraped_data.get("price"):
            product_data["price"] = scraped_data["price"]
        if scraped_data.get("price_currency"):
            product_data["price_currency"] = scraped_data["price_currency"]
        if scraped_data.get("rating"):
            product_data["rating"] = scraped_data["rating"]
        if scraped_data.get("review_count"):
            product_data["review_count"] = scraped_data["review_count"]
        if scraped_data.get("date_first_available"):
            product_data["date_first_available"] = scraped_data["date_first_available"]
            product_data["launch_date"] = scraped_data["date_first_available"]
        if scraped_data.get("bsr_rank"):
            product_data["bsr_rank"] = scraped_data["bsr_rank"]
        if scraped_data.get("bsr_category"):
            product_data["bsr_category"] = scraped_data["bsr_category"]
        if scraped_data.get("bullet_points"):
            product_data["bullet_points"] = scraped_data["bullet_points"]
        if scraped_data.get("product_details"):
            product_data["product_details"] = scraped_data["product_details"]
        if scraped_data.get("rating_histogram"):
            product_data["rating_histogram"] = scraped_data["rating_histogram"]
        if scraped_data.get("low_star_reviews"):
            product_data["low_star_reviews"] = scraped_data["low_star_reviews"]
        if scraped_data.get("image_urls"):
            product_data["image_urls"] = scraped_data["image_urls"]
        if scraped_data.get("aplus_content"):
            product_data["aplus_content"] = scraped_data["aplus_content"]
        if scraped_data.get("aplus_image_count"):
            product_data["aplus_image_count"] = scraped_data["aplus_image_count"]
        if scraped_data.get("aplus_image_urls"):
            product_data["aplus_image_urls"] = scraped_data["aplus_image_urls"]
        if scraped_data.get("image_count"):
            product_data["image_count"] = scraped_data["image_count"]
        if scraped_data.get("bought_count"):
            product_data["bought_count"] = scraped_data["bought_count"]
        for key in [
            "seller_type",
            "platform_ecosystem",
            "brand_monopoly_risk",
            "capture_quality",
            "review_samples",
            "reviews",
            "review_intent_assets",
        ]:
            if key in scraped_data:
                product_data[key] = scraped_data[key]
        product_data["has_video"] = scraped_data.get("has_video", False)
        product_data["has_a_plus"] = scraped_data.get("has_a_plus", False)

    product_data["_data_source"] = data_source
    product_data["_scrape_success"] = scrape_success
    if isinstance(product_data.get("capture_quality"), dict):
        product_data["data_confidence"] = product_data["capture_quality"].get("confidence_level", "medium")
    if data_source == "ai_estimated_low_confidence":
        product_data["asin"] = asin
        product_data["data_confidence"] = "low"
        product_data["data_notes"] = "AI兜底估算，需以本地浏览器页面采集、服务器抓取或人工核实为准。"

    product_data["main_keywords"] = _clean_original_english_keywords(product_data.get("main_keywords"), product_data, 10)
    if not _has_positive_scores(scoring_data.get("scores") or scores):
        logger.warning(f"Empty score payload for {asin}; using conservative rule scoring from captured evidence")
        _, fallback_scoring_data = _rule_based_competitor_scoring(asin, marketplace, {**scraped_data, **product_data})
        fallback_scoring_data["fallback_reason"] = "本次未生成完整评分，已根据已抓取页面证据生成保守诊断。"
        if scoring_data.get("overall_summary"):
            fallback_scoring_data["overall_summary"] = scoring_data["overall_summary"]
        if scoring_data.get("improvement_suggestions"):
            fallback_scoring_data["improvement_suggestions"] = scoring_data["improvement_suggestions"]
        scoring_data = fallback_scoring_data
        scores = scoring_data["scores"]

    aligned_scores = CosmoOperatorAgent.align_scores(scoring_data.get("scores") or scores, product_data)
    scores = aligned_scores["asin_scores"]
    scoring_data["scores"] = aligned_scores["scores"]
    scoring_data["canonical_10d_scores"] = aligned_scores["canonical_scores"]
    scoring_data["score_basis"] = "amazon_skill_10d_canonical"
    scoring_data["market_reality_caps"] = aligned_scores["market_reality_caps"]
    if not _has_positive_scores(scores):
        logger.warning(f"Aligned score payload still empty for {asin}; forcing conservative rule scoring")
        _, fallback_scoring_data = _rule_based_competitor_scoring(asin, marketplace, {**scraped_data, **product_data})
        fallback_scoring_data["fallback_reason"] = "本次未生成完整评分，已根据已抓取页面证据生成保守诊断。"
        aligned_scores = CosmoOperatorAgent.align_scores(fallback_scoring_data["scores"], product_data)
        scores = aligned_scores["asin_scores"]
        scoring_data = fallback_scoring_data
        scoring_data["scores"] = aligned_scores["scores"]
        scoring_data["canonical_10d_scores"] = aligned_scores["canonical_scores"]
        scoring_data["score_basis"] = "amazon_skill_10d_canonical_rule_repair"
        scoring_data["market_reality_caps"] = aligned_scores["market_reality_caps"]
    shared_snapshot = await _find_shared_listing_score_snapshot(asin, marketplace, product_data, db, user_id)
    if shared_snapshot:
        scores = shared_snapshot["asin_scores"]
        _apply_shared_listing_snapshot(scoring_data, shared_snapshot)
    scoring_data = operator_agent.attach_result_metadata(
        scoring_data,
        alignment_context,
        product=product_data,
        scores=scoring_data.get("canonical_10d_scores") or scoring_data.get("scores"),
    )
    scoring_data["listing_breakdown"] = _build_listing_breakdown(product_data, scoring_data)
    amazon_compliance = await _evaluate_asin_compliance(product_data, marketplace, db)
    scoring_data["amazon_compliance"] = amazon_compliance
    scoring_data["toolbox_enhancements"] = build_toolbox_enhancements(
        product_data=product_data,
        scores=scoring_data["scores"],
        context="competitor",
    )

    # Save to database
    svc = Asin_analysesService(db)
    record = await svc.create({
        "asin": asin,
        "marketplace": marketplace,
        "product_title": product_data.get("title", ""),
        "product_data": json.dumps(product_data, ensure_ascii=False),
        "score_functionality": scores.get("functionality", 0),
        "score_emotional": scores.get("emotional", 0),
        "score_scenario": scores.get("scenario", 0),
        "score_user_profile": scores.get("user_profile", 0),
        "score_product_identity": scores.get("product_identity", 0),
        "score_compatibility": scores.get("compatibility", 0),
        "score_subjective_properties": scores.get("subjective_properties", 0),
        "score_differentiation": scores.get("differentiation", 0),
        "score_market_trend": scores.get("market_trend", 0),
        "score_risk_elimination": scores.get("risk_elimination", 0),
        "analysis_report": json.dumps(scoring_data, ensure_ascii=False),
        "created_at": datetime.now(timezone.utc),
    }, user_id=user_id)

    return AnalyzeAsinResponse(
        asin=asin,
        marketplace=marketplace,
        product_title=product_data.get("title", ""),
        product_data=product_data,
        scores=scores,
        analysis_report=scoring_data,
        amazon_compliance=amazon_compliance,
        data_source=data_source,
        id=record.id if record else None,
    )


async def _analyze_single_asin(
    asin: str,
    marketplace: str,
    user_id: str,
    db: AsyncSession,
) -> AnalyzeAsinResponse:
    """Analyze a single ASIN through scrape-first, AI fallback-second pipeline."""

    # Step 1: Try to scrape real product data from Amazon
    scraped_data = await scrape_amazon_product(asin, marketplace)

    if not scraped_data.get("scrape_success"):
        logger.warning(f"Scraping failed for {asin}; using low-confidence AI fallback")

    # Step 2: Delegate to the shared analysis pipeline.
    return await _analyze_single_asin_with_scraped(
        asin=asin,
        marketplace=marketplace,
        user_id=user_id,
        db=db,
        scraped_data=scraped_data,
    )


@router.post("/proxy-fetch", response_model=ProxyFetchResponse)
async def proxy_fetch_amazon(
    request: ProxyFetchRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Fetch Amazon product page HTML via our backend server.

    This replaces public CORS proxies — the backend fetches the page
    using the same scraping infrastructure (httpx / curl-cffi) and
    returns raw HTML to the frontend for parse-html-analyze.
    """
    try:
        asin = request.asin.strip().upper()
        if not asin or len(asin) != 10:
            return ProxyFetchResponse(success=False, error="无效的ASIN")

        from services.amazon_scraper import (
            MARKETPLACE_DOMAINS,
            ACCEPT_LANG,
            _DESKTOP_UAS,
            _build_desktop_headers,
            _is_captcha_page,
        )
        import random

        domain = MARKETPLACE_DOMAINS.get(request.marketplace, "www.amazon.com")
        url = f"https://{domain}/dp/{asin}"
        lang = ACCEPT_LANG.get(request.marketplace, "en-US,en;q=0.9")

        html = ""

        # Strategy 1: curl-cffi
        try:
            from curl_cffi.requests import AsyncSession as CurlSession
            impersonate = random.choice(["chrome131", "chrome124", "chrome120", "chrome"])
            async with CurlSession(impersonate=impersonate) as session:
                headers = _build_desktop_headers(lang)
                try:
                    await session.get(f"https://{domain}/", headers=headers, timeout=10)
                except Exception:
                    pass
                import asyncio
                await asyncio.sleep(random.uniform(0.3, 0.8))
                resp = await session.get(url, headers=headers, timeout=20)
                if resp.status_code == 200 and len(resp.text) > 5000:
                    html = resp.text
        except Exception as e:
            logger.info(f"proxy-fetch curl-cffi failed for {asin}: {e}")

        # Strategy 2: httpx fallback
        if not html or len(html) < 5000:
            try:
                import httpx
                ua = random.choice(_DESKTOP_UAS)
                headers = {
                    "User-Agent": ua,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": lang,
                    "Accept-Encoding": "gzip, deflate, br",
                    "Cache-Control": "max-age=0",
                    "Upgrade-Insecure-Requests": "1",
                }
                async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(25.0, connect=10.0)) as client:
                    try:
                        await client.get(f"https://{domain}/", headers=headers)
                    except Exception:
                        pass
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200 and len(resp.text) > 5000:
                        html = resp.text
            except Exception as e:
                logger.info(f"proxy-fetch httpx failed for {asin}: {e}")

        if not html or len(html) < 5000:
            return ProxyFetchResponse(success=False, error="无法获取Amazon页面，请稍后重试")

        if _is_captcha_page(html):
            return ProxyFetchResponse(success=False, error="Amazon返回了验证码页面，请稍后重试")

        return ProxyFetchResponse(success=True, html=html)

    except Exception as e:
        logger.error(f"proxy-fetch error for {request.asin}: {e}")
        return ProxyFetchResponse(success=False, error=str(e))


@router.post("/parse-html-analyze", response_model=ParseHtmlAnalyzeResponse)
async def parse_html_and_analyze(
    request: ParseHtmlAnalyzeRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Parse raw Amazon HTML and run full 10-dimension analysis.

    Source is explicit so local-browser captures and backend proxy fetches
    never get mixed into the same confidence bucket.
    """
    try:
        asin = request.asin.strip().upper()
        if not asin or len(asin) != 10:
            return ParseHtmlAnalyzeResponse(success=False, asin=asin, error="无效的ASIN")

        html = request.html
        if not html or len(html) < 500:
            return ParseHtmlAnalyzeResponse(success=False, asin=asin, error="HTML内容过短")

        from services.amazon_scraper import _parse_product_page, _is_captcha_page, fetch_low_star_reviews
        from services.capture_quality import capture_quality

        if _is_captcha_page(html):
            return ParseHtmlAnalyzeResponse(success=False, asin=asin, error="检测到CAPTCHA验证页面")

        parsed = _parse_product_page(html, request.marketplace)
        if not parsed or not parsed.get("title"):
            return ParseHtmlAnalyzeResponse(success=False, asin=asin, error="无法从HTML中解析出产品信息")
        if request.source == "local_browser_capture":
            captured_bullets = [str(item).strip() for item in (request.captured_bullets or []) if str(item).strip()][:5]
            if request.captured_title.strip() and len(request.captured_title.strip()) > len(str(parsed.get("title", "")).strip()):
                parsed["title"] = request.captured_title.strip()
            if captured_bullets and len(captured_bullets) > len(parsed.get("bullet_points") or []):
                parsed["bullet_points"] = captured_bullets
            if request.captured_price.strip():
                parsed["price"] = request.captured_price.strip()
            if request.captured_rating.strip():
                parsed["rating"] = request.captured_rating.strip()
            if request.captured_review_count.strip():
                parsed["review_count"] = request.captured_review_count.strip()
            if request.captured_bsr_rank.strip() and not parsed.get("bsr_rank"):
                parsed["bsr_rank"] = request.captured_bsr_rank.strip()
            if request.captured_image_count.strip():
                parsed["image_count"] = request.captured_image_count.strip()
        if not parsed.get("low_star_reviews") and request.source != "local_browser_capture":
            parsed["low_star_reviews"] = await fetch_low_star_reviews(asin, request.marketplace)
        review_samples = normalize_review_samples(request.captured_reviews, limit=40)
        if review_samples:
            parsed["review_samples"] = review_samples
            parsed["reviews"] = review_samples
            parsed["review_intent_assets"] = build_review_intent_assets({
                **parsed,
                "review_samples": review_samples,
            })

        logger.info(f"parse-html-analyze: parsed {asin}: {parsed['title'][:60]}")

        domain_map = {
            "US": "www.amazon.com", "UK": "www.amazon.co.uk", "DE": "www.amazon.de",
            "JP": "www.amazon.co.jp", "CA": "www.amazon.ca", "FR": "www.amazon.fr",
            "IT": "www.amazon.it", "ES": "www.amazon.es", "AU": "www.amazon.com.au",
        }
        domain = domain_map.get(request.marketplace, "www.amazon.com")
        source = request.source if request.source in {"local_browser_capture", "server_proxy_fetch"} else "server_proxy_fetch"
        quality = capture_quality(parsed, source)
        scraped_data = {
            "asin": asin,
            "url": f"https://{domain}/dp/{asin}",
            "scrape_success": True,
            "data_source": source,
            "capture_quality": quality,
            **parsed,
        }

        result = await _analyze_single_asin_with_scraped(
            asin=asin,
            marketplace=request.marketplace,
            user_id=str(current_user.id),
            db=db,
            scraped_data=scraped_data,
        )

        return ParseHtmlAnalyzeResponse(
            success=True,
            asin=result.asin,
            product_title=result.product_title,
            product_data=result.product_data,
            scores=result.scores,
            analysis_report=result.analysis_report,
            amazon_compliance=result.amazon_compliance,
            data_source=result.data_source,
            capture_quality=quality,
            id=result.id,
        )
    except Exception as e:
        logger.error(f"parse-html-analyze error for {request.asin}: {e}")
        return ParseHtmlAnalyzeResponse(success=False, asin=request.asin, error=str(e))


@router.post("/analyze", response_model=AnalyzeAsinResponse)
async def analyze_asin(
    request: AnalyzeAsinRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Analyze a single ASIN - get product data and 10-dimension scores."""
    try:
        asin = request.asin.strip().upper()
        if not asin or len(asin) != 10:
            raise HTTPException(status_code=400, detail="请输入有效的10位ASIN")

        if not request.force_refresh:
            scope_user_ids = await get_user_scope_ids(current_user, db)
            cached = await _get_cached_asin_analysis(asin, request.marketplace, db, scope_user_ids)
            if cached:
                if not cached.amazon_compliance:
                    cached.amazon_compliance = await _evaluate_asin_compliance(cached.product_data, cached.marketplace, db)
                    cached.analysis_report["amazon_compliance"] = cached.amazon_compliance
                return cached

        result = await _analyze_single_asin(
            asin=asin,
            marketplace=request.marketplace,
            user_id=str(current_user.id),
            db=db,
        )
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Analysis error for {request.asin}: {e}")
        raise HTTPException(status_code=500, detail=f"AI分析失败: {str(e)}")
    except Exception as e:
        logger.error(f"Analysis error for {request.asin}: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/compare", response_model=CompareAsinsResponse)
async def compare_asins(
    request: CompareAsinsRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compare my ASIN with competitor ASINs using 10-dimension scoring."""
    try:
        my_asin = request.my_asin.strip().upper()
        competitor_asins = [a.strip().upper() for a in request.competitor_asins if a.strip()]

        if not my_asin or len(my_asin) != 10:
            raise HTTPException(status_code=400, detail="请输入有效的10位ASIN")
        if not competitor_asins:
            raise HTTPException(status_code=400, detail="请至少输入一个竞品ASIN")
        if len(competitor_asins) > 5:
            raise HTTPException(status_code=400, detail="最多支持5个竞品ASIN")

        user_id = str(current_user.id)

        # Analyze my product
        my_result = await _analyze_single_asin(my_asin, request.marketplace, user_id, db)

        # Analyze competitors
        competitor_results = []
        for comp_asin in competitor_asins:
            if len(comp_asin) == 10:
                comp_result = await _analyze_single_asin(comp_asin, request.marketplace, user_id, db)
                competitor_results.append(comp_result)

        # Generate comparison report
        ai_service = AIHubService()
        competitor_info = "\n".join([
            f"ASIN: {c.asin}, 标题: {c.product_title}, 10维诊断: {json.dumps(c.scores, ensure_ascii=False)}"
            for c in competitor_results
        ])

        comparison_prompt = COMPARISON_PROMPT.format(
            my_asin=my_result.asin,
            my_title=my_result.product_title,
            my_scores=json.dumps(my_result.scores, ensure_ascii=False),
            competitor_info=competitor_info,
        )

        from schemas.aihub import GenTxtRequest, ChatMessage
        comparison_request = GenTxtRequest(
            messages=[ChatMessage(role="user", content=comparison_prompt)],
            model="AI_REASONING_MODEL",
            temperature=0,
            max_tokens=8192,
        )

        comparison_data = None
        for attempt in range(2):
            try:
                comparison_response = await ai_service.gentxt(comparison_request)
                comparison_data = _extract_json(comparison_response.content)
                break
            except ValueError as e:
                logger.warning(f"Comparison JSON parse failed (attempt {attempt + 1}/2): {e}")
                if attempt == 0:
                    comparison_request.model = "AI_REASONING_MODEL"

        if comparison_data is None:
            comparison_data = {
                "strengths": ["对比分析暂时无法完成，请重试"],
                "weaknesses": [], "opportunities": [], "threats": [],
                "dimension_comparison": {},
                "action_plan": ["请重新运行对比分析"],
            }

        return CompareAsinsResponse(
            my_product=my_result,
            competitors=competitor_results,
            comparison=comparison_data,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comparison error: {e}")
        raise HTTPException(status_code=500, detail=f"对比分析失败: {str(e)}")


@router.get("/history")
async def get_analysis_history(
    skip: int = 0,
    limit: int = 20,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's analysis history."""
    svc = Asin_analysesService(db)
    result = await svc.get_list(skip=skip, limit=limit, user_id=str(current_user.id), sort="-id")

    items = []
    for item in result["items"]:
        items.append({
            "id": item.id,
            "asin": item.asin,
            "marketplace": item.marketplace,
            "product_title": item.product_title,
            "scores": {
                "functionality": item.score_functionality,
                "emotional": item.score_emotional,
                "scenario": item.score_scenario,
                "user_profile": item.score_user_profile,
                "product_identity": item.score_product_identity,
                "compatibility": item.score_compatibility,
                "subjective_properties": item.score_subjective_properties,
                "differentiation": item.score_differentiation,
                "market_trend": item.score_market_trend,
                "risk_elimination": item.score_risk_elimination,
            },
            "created_at": item.created_at.isoformat() if item.created_at else None,
        })

    return {"items": items, "total": result["total"]}


@router.get("/history/by-asin/{asin}", response_model=AnalyzeAsinResponse)
async def get_latest_analysis_history_by_asin(
    asin: str,
    marketplace: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the latest complete saved ASIN diagnosis for this user.

    This intentionally ignores old action snapshots or partial records so the UI
    never renders a stale residual capture as a formal competitor diagnosis.
    """
    from sqlalchemy import select
    from models.asin_analyses import Asin_analyses

    normalized_asin = asin.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{10}", normalized_asin):
        raise HTTPException(status_code=422, detail="ASIN格式不正确")

    query = (
        select(Asin_analyses)
        .where(Asin_analyses.user_id == str(current_user.id))
        .where(Asin_analyses.asin == normalized_asin)
        .where(Asin_analyses.analysis_report.isnot(None))
        .order_by(Asin_analyses.id.desc())
        .limit(20)
    )
    if marketplace:
        query = query.where(Asin_analyses.marketplace == marketplace)

    result = await db.execute(query)
    records = result.scalars().all()
    for record in records:
        try:
            product_data = json.loads(record.product_data or "{}")
        except Exception:
            product_data = {}
        has_core_evidence = bool(
            record.product_title
            and (
                product_data.get("price")
                or product_data.get("rating")
                or product_data.get("review_count")
                or product_data.get("bullet_points")
                or product_data.get("image_urls")
            )
        )
        if not has_core_evidence:
            continue

        response = await _analysis_record_to_response(
            record,
            record.marketplace or marketplace or "US",
            db,
            str(current_user.id),
        )
        if response and _has_positive_scores(response.scores):
            return response

    raise HTTPException(status_code=404, detail="未找到完整历史诊断，请重新分析")


@router.get("/history/{analysis_id}", response_model=AnalyzeAsinResponse)
async def get_analysis_history_detail(
    analysis_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get one saved ASIN analysis with the full diagnosis payload."""
    svc = Asin_analysesService(db)
    record = await svc.get_by_id(analysis_id, user_id=str(current_user.id))
    if not record:
        raise HTTPException(status_code=404, detail="历史诊断不存在")

    response = await _analysis_record_to_response(
        record,
        record.marketplace or "US",
        db,
        str(current_user.id),
    )
    if not response:
        raise HTTPException(status_code=404, detail="历史诊断缺少完整评分，请重新分析")
    return response


# ================================================================== #
#  6-Dimension Product Scoring (6维产品判断打分标准)                      #
# ================================================================== #

class FiveDimensionScoreRequest(BaseModel):
    """Request for 6-dimension product scoring."""
    asin: str
    marketplace: str = "US"
    # Optional: pass existing product data to avoid re-scraping
    product_title: str = ""
    product_data: Optional[dict] = None


class FiveDimensionScoreResponse(BaseModel):
    success: bool
    asin: str
    product_title: str = ""
    total_score: float = 0
    raw_total: float = 0
    qualified: bool = False  # True only when routed to opportunity_pool
    dimension_scores: dict = {}  # {demand: 15, scenario: 12, ..., price_tier: 18}
    price_tier_category: str = "medium"  # high / medium / low - 价格带分类
    price_tier_analysis: dict = {}   # 价格带详细分析
    detail_scores: dict = {}    # Full 24-item breakdown (原20+新增4)
    analysis: dict = {}         # AI analysis per dimension
    suggestions: list = []
    data_completeness: float = 0
    confidence_level: str = "low"
    risk_level: str = "medium"
    decision: str = "not_entered"
    pool_status: str = "not_entered"
    recommended_path: str = ""
    one_sentence_reason: str = ""
    dimensions: list = []
    veto_rules: list = []
    next_actions: list = []
    analysis_mode: str = "rule_fallback"
    ai_called: bool = False
    fallback_reason: Optional[str] = None
    rule_guardrails: dict = {}
    id: Optional[int] = None


FIVE_DIMENSION_PROMPT = """你是AlignX的「6维产品判断打分」专家。请根据以下产品数据，按照6维24项标准进行严格评分。

## 产品数据
ASIN: {asin}
站点: Amazon {marketplace}
{product_context}

## 6维24项评分标准（每项0-5分，每维满分20分，总分120分 → 标准化到100分）

### 一、需求维（demand）- 满分20分
1. **痛点明确度**(pain_clarity): 目标用户的痛点是否清晰可见？是否有明确的"不满"或"未被满足"的需求？(0-5)
2. **使用频率**(usage_frequency): 该产品被使用的频率如何？日用>周用>月用>偶尔用 (0-5)
3. **需求刚性**(demand_rigidity): 是刚需还是可有可无？用户是否"必须"购买？(0-5)
4. **付费理由清晰度**(payment_clarity): 用户为什么愿意付这个价格？价值感知是否清晰？(0-5)

### 二、场景维（scenario）- 满分20分
1. **场景明确度**(scene_clarity): 产品的核心使用场景是否清晰？用户能否立刻想到"在哪里用"？(0-5)
2. **场景触发强度**(scene_trigger): 场景触发购买的力度有多强？是否容易联想到"我需要这个"？(0-5)
3. **场景扩展性**(scene_expansion): 除核心场景外，是否有其他使用场景？场景越多，市场越大 (0-5)
4. **场景可视化表达能力**(scene_visual): Listing图片/视频能否有效展示使用场景？(0-5)

### 三、竞争维（competition）- 满分20分
1. **同质化程度**(homogeneity): 市场上同类产品的相似度（反向计分：同质化越高分越低）(0-5)
2. **差异化锚点**(differentiation_anchor): 产品是否有明确的差异化卖点？USP是否突出？(0-5)
3. **替代难度**(substitution_difficulty): 用户转向竞品的成本/难度有多高？(0-5)
4. **竞品弱点可攻击性**(competitor_weakness): 竞品是否有明显弱点可以被利用？(0-5)

### 四、利润维（profit）- 满分20分
1. **毛利空间**(gross_margin): 产品毛利率是否健康？（>50%=5分, 40-50%=4分, 30-40%=3分, 20-30%=2分, <20%=1分）(0-5)
2. **广告承受力**(ad_tolerance): 在合理ACOS下是否还有利润？广告费用占比是否可控？(0-5)
3. **定价合理性**(pricing_rationality): 定价是否在目标客群的心理价位区间？是否有溢价空间？(0-5)
4. **放大利润空间**(profit_scalability): 是否可以通过捆绑、变体、订阅等方式放大利润？(0-5)

### 五、趋势维（trend）- 满分20分
1. **需求增长趋势**(demand_growth): 该品类/关键词搜索量是上升还是下降？(0-5)
2. **品类生命周期**(category_lifecycle): 品类处于导入期/成长期/成熟期/衰退期？成长期最优 (0-5)
3. **政策合规风险**(compliance_risk): 是否有政策/合规/专利风险？（反向计分：风险越高分越低）(0-5)
4. **技术与供应链趋势**(tech_supply_trend): 技术迭代和供应链是否稳定？是否有利好趋势？(0-5)

### 六、价格带维（price_tier）- 满分20分
**价格带定位判断**: 根据品类价格分布，判断该产品是否匹配目标价格带，并评估价值感知、溢价和价格战风险。

1. **价格带匹配度**(price_band_match): 产品价格是否落在目标用户愿意接受的价格带？(0-5)
2. **价值感知支撑**(value_perception): 图片、A+、评论和卖点是否足以支撑该价格？(0-5)
3. **溢价空间**(premium_potential): 是否能通过品牌、功能、场景或差异化形成溢价？(0-5)
4. **价格风险承受力**(price_risk_resistance): 是否能避免陷入纯价格竞争，广告成本上涨时是否还能承受？(0-5)

## 输出要求
请以JSON格式返回（确保返回有效的JSON）：
{{
  "dimension_scores": {{
    "demand": 需求维总分(0-20),
    "scenario": 场景维总分(0-20),
    "competition": 竞争维总分(0-20),
    "profit": 利润维总分(0-20),
    "trend": 趋势维总分(0-20),
    "price_tier": 价格带维总分(0-20)
  }},
  "price_tier_analysis": {{
    "category": "high | medium | low",  # 价格带分类: 高/中/低
    "confidence": 0-100,  # 价格带判断置信度
    "tier_percentile": 该价格在品类中的百分位（0-100）
  }},
  "detail_scores": {{
    "pain_clarity": 分数(0-5),
    "usage_frequency": 分数(0-5),
    "demand_rigidity": 分数(0-5),
    "payment_clarity": 分数(0-5),
    "scene_clarity": 分数(0-5),
    "scene_trigger": 分数(0-5),
    "scene_expansion": 分数(0-5),
    "scene_visual": 分数(0-5),
    "homogeneity": 分数(0-5),
    "differentiation_anchor": 分数(0-5),
    "substitution_difficulty": 分数(0-5),
    "competitor_weakness": 分数(0-5),
    "gross_margin": 分数(0-5),
    "ad_tolerance": 分数(0-5),
    "pricing_rationality": 分数(0-5),
    "profit_scalability": 分数(0-5),
    "demand_growth": 分数(0-5),
    "category_lifecycle": 分数(0-5),
    "compliance_risk": 分数(0-5),
    "tech_supply_trend": 分数(0-5),
    "price_band_match": 分数(0-5),
    "value_perception": 分数(0-5),
    "premium_potential": 分数(0-5),
    "price_risk_resistance": 分数(0-5)
  }},
  "analysis": {{
    "demand": "需求维分析详情（含每个子项的判断依据）...",
    "scenario": "场景维分析详情...",
    "competition": "竞争维分析详情...",
    "profit": "利润维分析详情...",
    "trend": "趋势维分析详情...",
    "price_tier": "价格带维分析详情（价格带分类依据、该价格带优劣势）..."
  }},
  "overall_summary": "总体评价摘要（含是否建议进入机会池的结论）...",
  "suggestions": ["优化建议1", "优化建议2", "优化建议3"]
}}

只返回JSON，不要返回其他内容。"""

SIX_DIMENSION_AI_PRIMARY_PROMPT = """你是AlignX的ASIN选品主判模型，使用人性根层 × 用户意图 × 平台识别 × 顶级亚马逊运营操盘手的复合判断方式。

你的职责：基于真实抓取证据，对单个ASIN做机会判断主判。规则底座只作为证据提示和硬闸门参考，不允许被规则分数牵着走。

## 关键原则
1. AI负责语义主判：判断商品身份、用户任务、场景、搜索入口、竞争结构、差异化、广告承受力和风险趋势。
2. 不要补空字段：缺价格、缺评论、缺BSR、缺关键词排名时，降低对应维度分数和置信度，不能猜。
3. 广告视角：判断该ASIN后续能不能通过CTR、CVR、CPC、ACOS和关键词订单验证。
4. 分数要保守：证据不足不能给高分；单靠标题好听不能判断能做。

## 产品证据
ASIN: {asin}
站点: Amazon {marketplace}
{product_context}

## 规则底座与硬闸门参考
{rule_context}

## 6维定义
- demand: 需求强度。痛点明确、使用频率、刚性、付费理由。
- search_entry: 搜索入口。核心词容量、长尾机会、自然位可进入性、广告入口承受力。
- competition: 竞争结构。Top20评论门槛、低评论高排名样本、广告位压力、同质化。
- differentiation: 差异化切口。可表达差异点、竞品差评机会、Listing承接、替代难度。
- business: 商业承受力。毛利空间、价格带合理性、广告承受力、套装/变体/复购空间。
- risk_trend: 风险与趋势。政策合规、BSR/关键词趋势、生命周期、新品进入案例。

## 输出JSON
只返回JSON，不要解释，不要Markdown：
{{
  "dimension_scores": {{
    "demand": 0-20,
    "search_entry": 0-20,
    "competition": 0-20,
    "differentiation": 0-20,
    "business": 0-20,
    "risk_trend": 0-20
  }},
  "detail_scores": {{
    "pain_clarity": 0-5,
    "usage_frequency": 0-5,
    "demand_rigidity": 0-5,
    "payment_clarity": 0-5,
    "core_keyword_capacity": 0-5,
    "long_tail_opportunity": 0-5,
    "organic_entry_access": 0-5,
    "ad_entry_tolerance": 0-5,
    "top20_review_barrier": 0-5,
    "low_review_rank_opportunity": 0-5,
    "sponsored_pressure": 0-5,
    "homogeneity": 0-5,
    "differentiation_anchor": 0-5,
    "competitor_weakness": 0-5,
    "listing_expression_fit": 0-5,
    "substitution_difficulty": 0-5,
    "gross_margin": 0-5,
    "price_band_match": 0-5,
    "ad_tolerance": 0-5,
    "profit_scalability": 0-5,
    "compliance_risk": 0-5,
    "demand_growth": 0-5,
    "category_lifecycle": 0-5,
    "new_entry_signal": 0-5
  }},
  "analysis": {{
    "demand": "一句话证据判断",
    "search_entry": "一句话证据判断",
    "competition": "一句话证据判断",
    "differentiation": "一句话证据判断",
    "business": "一句话证据判断",
    "risk_trend": "一句话证据判断"
  }},
  "suggestions": ["下一步动作1", "下一步动作2", "下一步动作3"],
  "one_sentence_reason": "一句话结论，必须说明主要证据和主要风险"
}}"""


def _build_product_context(product_data: dict, product_title: str = "") -> str:
    """Build product context string for the 6D scoring prompt."""
    lines = []
    if product_title:
        lines.append(f"标题: {product_title}")
    if product_data:
        if product_data.get("title") and not product_title:
            lines.append(f"标题: {product_data['title']}")
        if product_data.get("brand"):
            lines.append(f"品牌: {product_data['brand']}")
        if product_data.get("category"):
            lines.append(f"类目: {product_data['category']}")
        if product_data.get("price"):
            lines.append(f"价格: ${product_data['price']}")
        if product_data.get("rating"):
            lines.append(f"评分: {product_data['rating']}")
        if product_data.get("review_count"):
            lines.append(f"评论数: {product_data['review_count']}")
        if product_data.get("bsr_rank"):
            lines.append(f"BSR排名: #{product_data['bsr_rank']}")
        if product_data.get("bullet_points"):
            bps = product_data["bullet_points"]
            if isinstance(bps, list):
                lines.append("五点描述:")
                for i, bp in enumerate(bps, 1):
                    lines.append(f"  {i}. {bp}")
            elif isinstance(bps, str) and bps.strip():
                lines.append(f"五点描述: {bps[:500]}")
        if product_data.get("description_summary"):
            lines.append(f"描述摘要: {product_data['description_summary'][:300]}")
        if product_data.get("main_keywords"):
            kws = product_data["main_keywords"]
            if isinstance(kws, list):
                lines.append(f"关键词: {', '.join(kws[:10])}")
            elif isinstance(kws, str):
                lines.append(f"关键词: {kws[:200]}")
    return "\n".join(lines) if lines else "（无产品数据，请基于ASIN公开信息分析）"


SIX_DIMENSION_SCHEMA = [
    ("demand", "需求强度", [
        ("pain_clarity", "痛点明确度"),
        ("usage_frequency", "使用频率"),
        ("demand_rigidity", "需求刚性"),
        ("payment_clarity", "付费理由清晰度"),
    ]),
    ("search_entry", "搜索入口", [
        ("core_keyword_capacity", "核心关键词容量"),
        ("long_tail_opportunity", "长尾词机会"),
        ("organic_entry_access", "自然排名可进入性"),
        ("ad_entry_tolerance", "广告入口承受力"),
    ]),
    ("competition", "竞争结构", [
        ("top20_review_barrier", "Top20评论门槛"),
        ("low_review_rank_opportunity", "低评论高排名样本"),
        ("sponsored_pressure", "广告位压力"),
        ("homogeneity", "同质化程度"),
    ]),
    ("differentiation", "差异化切口", [
        ("differentiation_anchor", "可表达差异点"),
        ("competitor_weakness", "竞品差评机会"),
        ("listing_expression_fit", "Listing表达承接"),
        ("substitution_difficulty", "替代难度"),
    ]),
    ("business", "商业承受力", [
        ("gross_margin", "毛利空间"),
        ("price_band_match", "价格带合理性"),
        ("ad_tolerance", "广告承受力"),
        ("profit_scalability", "套装/变体/复购空间"),
    ]),
    ("risk_trend", "风险与趋势", [
        ("compliance_risk", "政策合规风险"),
        ("demand_growth", "BSR/关键词趋势"),
        ("category_lifecycle", "类目生命周期"),
        ("new_entry_signal", "新品进入案例"),
    ]),
]

SIX_DIMENSION_HARD_VETO_NAMES = {
    "品牌垄断明显",
    "平台生态强绑定",
    "侵权风险高",
    "不是第三方卖家的合理切入品",
}


def _num_value(value, default: float = 0) -> float:
    if value is None:
        return default
    try:
        text = str(value).replace(",", "")
        found = re.findall(r"\d+(?:\.\d+)?", text)
        return float(found[0]) if found else default
    except Exception:
        return default


def _text_blob(product_data: dict, product_title: str) -> str:
    parts = [product_title or "", str(product_data.get("title") or ""), str(product_data.get("category") or "")]
    bullets = product_data.get("bullet_points")
    if isinstance(bullets, list):
        parts.extend(str(item) for item in bullets)
    else:
        parts.append(str(bullets or ""))
    parts.append(str(product_data.get("description_summary") or ""))
    parts.append(str(product_data.get("search_keywords") or ""))
    parts.append(str(product_data.get("main_keywords") or ""))
    return " ".join(parts).lower()


def _score_item(rule_score: float, evidence: list[str], deductions: list[str], suggestion: str, ai_adjustment: float = 0) -> dict:
    ai_adjustment = max(-1, min(1, round(ai_adjustment, 1)))
    final_score = max(0, min(5, round(rule_score + ai_adjustment, 1)))
    return {
        "rule_score": round(rule_score, 1),
        "ai_adjustment": ai_adjustment,
        "final_score": final_score,
        "evidence": evidence[:4],
        "deduction_reasons": deductions[:4],
        "suggestion": suggestion,
    }


def _data_completeness(product_data: dict) -> tuple[float, str, dict]:
    checks = {
        "title": bool(product_data.get("title")),
        "brand": bool(product_data.get("brand")),
        "category": bool(product_data.get("category")),
        "price": _num_value(product_data.get("price")) > 0,
        "rating": _num_value(product_data.get("rating")) > 0,
        "review_count": _num_value(product_data.get("review_count")) > 0,
        "bsr": _num_value(product_data.get("bsr_rank")) > 0,
        "bullet_points": bool(product_data.get("bullet_points")),
        "images_count": _num_value(product_data.get("image_count")) > 0,
        "a_plus": bool(product_data.get("has_a_plus") or product_data.get("a_plus_content")),
        "video": bool(product_data.get("has_video")),
        "top10_competitors": bool(product_data.get("top10_competitors")),
        "top20_competitors": bool(product_data.get("top20_competitors")),
        "review_pain_points": bool(product_data.get("review_pain_points")),
        "qa_data": bool(product_data.get("qa_data")),
        "keyword_data": bool(product_data.get("keyword_data") or product_data.get("main_keywords") or product_data.get("search_keywords")),
        "cpc_data": bool(product_data.get("cpc_data")),
        "bsr_history": bool(product_data.get("bsr_history")),
        "review_growth_history": bool(product_data.get("review_growth_history")),
    }
    completeness = round(sum(1 for ok in checks.values() if ok) / len(checks), 2)
    confidence = "high" if completeness >= 0.8 else "medium" if completeness >= 0.5 else "low"
    return completeness, confidence, checks


def _coerce_score(value, low: float, high: float, fallback: float, convert_100: bool = False) -> float:
    if value is None:
        return round(fallback, 1)
    try:
        score = float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        score = fallback
    if convert_100 and score > high and score <= 100:
        score = score * high / 100
    return round(max(low, min(high, score)), 1)


def _build_six_dimension_rule_context(engine: dict) -> str:
    dimensions = []
    for item in engine.get("dimensions", []):
        dimensions.append({
            "dimension_key": item.get("dimension_key"),
            "dimension_name": item.get("dimension_name"),
            "rule_score": item.get("final_score"),
        })
    payload = {
        "data_completeness": engine.get("data_completeness"),
        "confidence_level": engine.get("confidence_level"),
        "rule_dimension_scores": dimensions,
        "triggered_vetoes": [
            {
                "rule_name": rule.get("rule_name"),
                "reason": rule.get("reason"),
                "evidence": rule.get("evidence", []),
            }
            for rule in engine.get("veto_rules", [])
            if rule.get("triggered")
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _normalize_six_dimension_ai_result(ai_result: dict, rule_engine: dict) -> dict:
    if not isinstance(ai_result, dict):
        raise ValueError("AI 6维主判返回格式无效")

    raw_dimensions = ai_result.get("dimension_scores") or {}
    raw_details = ai_result.get("detail_scores") or {}
    if not isinstance(raw_dimensions, dict):
        raw_dimensions = {}
    if not isinstance(raw_details, dict):
        raw_details = {}

    dimension_scores: dict[str, float] = {}
    valid_dimension_count = 0
    for dim_key, _dim_name, _items in SIX_DIMENSION_SCHEMA:
        fallback = float((rule_engine.get("dimension_scores") or {}).get(dim_key, 0))
        has_value = raw_dimensions.get(dim_key) is not None
        dimension_scores[dim_key] = _coerce_score(raw_dimensions.get(dim_key), 0, 20, fallback, convert_100=True)
        if has_value:
            valid_dimension_count += 1

    if valid_dimension_count < 4:
        raise ValueError("AI 6维主判缺少关键维度分数")

    fallback_detail = rule_engine.get("detail_scores") or {}
    detail_scores: dict[str, float] = {}
    for _dim_key, _dim_name, items in SIX_DIMENSION_SCHEMA:
        for item_key, _item_name in items:
            fallback = float(fallback_detail.get(item_key, 0))
            detail_scores[item_key] = _coerce_score(raw_details.get(item_key), 0, 5, fallback, convert_100=True)

    analysis = {}
    raw_analysis = ai_result.get("analysis") or {}
    if not isinstance(raw_analysis, dict):
        raw_analysis = {}
    for dim_key, _dim_name, _items in SIX_DIMENSION_SCHEMA:
        analysis[dim_key] = str(raw_analysis.get(dim_key) or (rule_engine.get("analysis") or {}).get(dim_key) or "").strip()

    suggestions = ai_result.get("suggestions")
    if not isinstance(suggestions, list):
        suggestions = rule_engine.get("suggestions") or []
    suggestions = [str(item).strip() for item in suggestions if str(item).strip()][:5]

    return {
        "dimension_scores": dimension_scores,
        "detail_scores": detail_scores,
        "analysis": analysis,
        "suggestions": suggestions,
        "one_sentence_reason": str(ai_result.get("one_sentence_reason") or "").strip(),
    }


def _apply_six_dimension_routing(engine: dict) -> dict:
    total_score = float(engine.get("total_score") or 0)
    dimension_scores = engine.get("dimension_scores") or {}
    confidence_level = str(engine.get("confidence_level") or "low")
    triggered_vetoes = [rule for rule in engine.get("veto_rules", []) if rule.get("triggered")]
    hard_vetoes = [rule for rule in triggered_vetoes if rule.get("rule_name") in SIX_DIMENSION_HARD_VETO_NAMES]
    market_barriers = [rule for rule in triggered_vetoes if rule.get("rule_name") not in SIX_DIMENSION_HARD_VETO_NAMES]
    risk_level = (
        "high"
        if hard_vetoes or total_score < 45
        else "medium"
        if market_barriers or total_score < 75 or confidence_level == "low"
        else "low"
    )

    derivative_signal = (
        total_score >= 55
        and (
            market_barriers
            or float(dimension_scores.get("competition", 0)) < 12
            or float(dimension_scores.get("differentiation", 0)) < 12
        )
        and (float(dimension_scores.get("search_entry", 0)) >= 10 or float(dimension_scores.get("demand", 0)) >= 10)
    )
    if hard_vetoes:
        pool_status = "rejected_pool"
    elif total_score >= 75 and risk_level != "high":
        pool_status = "opportunity_pool"
    elif 65 <= total_score < 75 and risk_level in {"low", "medium"}:
        pool_status = "validation_pool"
    elif derivative_signal:
        pool_status = "derivative_pool"
    elif total_score < 55 or risk_level == "high":
        pool_status = "rejected_pool"
    else:
        pool_status = "not_entered"

    if hard_vetoes:
        decision = "暂缓进入"
    elif pool_status == "opportunity_pool":
        decision = "可进入验证"
    elif pool_status == "validation_pool":
        decision = "小预算验证"
    elif pool_status == "derivative_pool":
        decision = "找细分机会"
    elif total_score >= 60:
        decision = "补证后再评估"
    else:
        decision = "暂不建议进入"

    action_map = {
        "可进入验证": ["生成 Listing 方向", "生成首轮广告验证词", "创建执行跟踪任务"],
        "小预算验证": ["生成最小验证方案", "生成测试关键词", "生成验证指标"],
        "补证后再评估": ["补齐关键证据", "提取竞品差评机会", "重新评估"],
        "找细分机会": ["查找替代机会", "分析配件/周边市场", "重新选择相邻类目"],
        "暂不建议进入": ["查找替代机会", "分析配件/周边市场", "重新选择相邻类目"],
        "暂缓进入": ["查看风险证据", "生成避坑报告", "重新选品"],
    }
    recommended_path = {
        "opportunity_pool": "/listing-launch-check",
        "validation_pool": "/ab-test-comparison",
        "derivative_pool": "/asin-manager",
        "rejected_pool": "/asin-manager",
        "not_entered": "/asin-manager",
    }.get(pool_status, "/asin-manager")
    gate_reason = (
        f"需要先排查：{hard_vetoes[0]['rule_name']}" if hard_vetoes
        else f"进入前需确认：{market_barriers[0]['rule_name']}" if market_barriers
        else "未发现必须先排查的硬伤"
    )
    confidence_label = {"high": "较完整", "medium": "一般", "low": "偏少"}.get(confidence_level, confidence_level)
    risk_label = {"high": "高", "medium": "中", "low": "低"}.get(risk_level, risk_level)
    one_sentence_reason = (
        f"{decision}：总分{round(total_score, 1)}，证据完整度{confidence_label}，主要风险{risk_label}，{gate_reason}。"
    )
    if engine.get("ai_called") and engine.get("ai_reason"):
        one_sentence_reason = f"{one_sentence_reason} 判断依据：{engine['ai_reason']}"

    return {
        "risk_level": risk_level,
        "decision": decision,
        "pool_status": pool_status,
        "qualified": pool_status == "opportunity_pool",
        "recommended_path": recommended_path,
        "one_sentence_reason": one_sentence_reason,
        "suggestions": action_map.get(decision, []),
        "next_actions": action_map.get(decision, []),
        "rule_guardrails": {
            "hard_vetoes": hard_vetoes,
            "market_barriers": market_barriers,
            "triggered_vetoes": triggered_vetoes,
        },
    }


def _merge_ai_primary_six_dimension(rule_engine: dict, ai_result: dict) -> dict:
    normalized = _normalize_six_dimension_ai_result(ai_result, rule_engine)
    engine = copy.deepcopy(rule_engine)
    engine["analysis_mode"] = "ai_primary_rule_guarded"
    engine["ai_called"] = True
    engine["fallback_reason"] = None
    engine["ai_reason"] = normalized.get("one_sentence_reason") or ""
    engine["dimension_scores"] = normalized["dimension_scores"]
    engine["detail_scores"] = normalized["detail_scores"]
    engine["analysis"] = normalized["analysis"]
    engine["suggestions"] = normalized["suggestions"] or engine.get("suggestions", [])

    for dimension in engine.get("dimensions", []):
        dim_key = dimension.get("dimension_key")
        if not dim_key:
            continue
        base_score = float(dimension.get("base_score") or 0)
        final_score = float(engine["dimension_scores"].get(dim_key, base_score))
        dimension["ai_adjustment"] = round(final_score - base_score, 1)
        dimension["final_score"] = round(final_score, 1)
        for item in dimension.get("items", []):
            item_key = item.get("item_key")
            if item_key and item_key in engine["detail_scores"]:
                item_base = float(item.get("rule_score") or 0)
                item_final = float(engine["detail_scores"][item_key])
                item["ai_adjustment"] = round(item_final - item_base, 1)
                item["final_score"] = round(item_final, 1)

    engine["raw_total"] = round(sum(float(value or 0) for value in engine["dimension_scores"].values()), 1)
    engine["total_score"] = round(engine["raw_total"] * 100 / 120, 1)
    engine.update(_apply_six_dimension_routing(engine))
    return engine


async def _run_six_dimension_ai_primary(asin: str, marketplace: str, product_title: str, product_data: dict, rule_engine: dict) -> dict:
    from schemas.aihub import ChatMessage, GenTxtRequest

    product_context = _build_product_context(product_data, product_title)
    human_context = human_nature_prompt_block({
        "title": product_title or product_data.get("title", ""),
        "bullet_points": product_data.get("bullet_points", ""),
        "category": product_data.get("category", ""),
        "brand": product_data.get("brand", ""),
        "keywords": product_data.get("main_keywords", ""),
    })
    prompt = SIX_DIMENSION_AI_PRIMARY_PROMPT.format(
        asin=asin,
        marketplace=marketplace,
        product_context=f"{human_context}\n\n{product_context}",
        rule_context=_build_six_dimension_rule_context(rule_engine),
    )
    ai_service = AIHubService()
    response = await ai_service.gentxt(
        GenTxtRequest(
            messages=[ChatMessage(role="user", content=prompt)],
            model="AI_REASONING_MODEL",
            temperature=0,
            max_tokens=4096,
        )
    )
    return _extract_json_from_text(response.content)


def _build_six_dimension_rule_engine(asin: str, marketplace: str, product_title: str, product_data: dict, ai_result: dict | None = None) -> dict:
    title = product_title or str(product_data.get("title") or "")
    text = _text_blob(product_data, title)
    price = _num_value(product_data.get("price"))
    rating = _num_value(product_data.get("rating"))
    reviews = _num_value(product_data.get("review_count"))
    bsr = _num_value(product_data.get("bsr_rank"))
    image_count = _num_value(product_data.get("image_count"))
    bullets = product_data.get("bullet_points") or []
    bullet_count = len(bullets) if isinstance(bullets, list) else len([x for x in re.split(r"[\n;]+", str(bullets)) if x.strip()])
    has_a_plus = bool(product_data.get("has_a_plus") or product_data.get("a_plus_content") or product_data.get("description_summary"))
    has_video = bool(product_data.get("has_video"))
    completeness, confidence_level, completeness_checks = _data_completeness(product_data)

    pain_terms = ["odor", "smell", "pain", "mess", "tracking", "noise", "leak", "safe", "waterproof", "easy", "portable", "backup", "without"]
    scenario_terms = ["for ", "with ", "travel", "outdoor", "camping", "pool", "beach", "home", "office", "apartment", "gift", "kids", "mom", "cats", "dogs"]
    diff_terms = ["unique", "patented", "exclusive", "new", "upgraded", "compare", "different", "only", "advanced", "sealed", "replaceable"]
    compliance_terms = ["fda", "fcc", "ul", "ce", "prop 65", "battery", "medical", "food", "child", "baby", "chemical", "laser"]
    risk_terms = ["patent", "infringe", "restricted", "certification", "hazard", "recall", "counterfeit"]

    pain_hits = sum(1 for term in pain_terms if term in text)
    scenario_hits = sum(1 for term in scenario_terms if term in text)
    diff_hits = sum(1 for term in diff_terms if term in text)
    compliance_hits = sum(1 for term in compliance_terms if term in text)
    risk_hits = sum(1 for term in risk_terms if term in text)
    keyword_validation = product_data.get("keyword_sales_validation") if isinstance(product_data.get("keyword_sales_validation"), dict) else {}
    validation_opportunity_keywords = keyword_validation.get("opportunity_keywords") or []
    validation_assist = keyword_validation.get("market_validation_assist") if isinstance(keyword_validation.get("market_validation_assist"), dict) else {}
    assist_keywords = validation_assist.get("keyword_expansion") if isinstance(validation_assist, dict) else []
    if isinstance(validation_opportunity_keywords, list) or isinstance(assist_keywords, list):
        validation_keyword_blob = " ".join(
            str(item)
            for item in [*(validation_opportunity_keywords if isinstance(validation_opportunity_keywords, list) else []), *(assist_keywords if isinstance(assist_keywords, list) else [])]
            if item
        )
    else:
        validation_keyword_blob = ""
    keyword_blob = " ".join(
        str(product_data.get(key) or "")
        for key in ("keyword_data", "main_keywords", "search_keywords", "backend_keywords")
    ).lower()
    if validation_keyword_blob:
        keyword_blob = f"{keyword_blob} {validation_keyword_blob.lower()}"
    keyword_count = len({kw for kw in re.split(r"[,;\n]+", keyword_blob) if kw.strip()})
    keyword_rank_snapshots = product_data.get("keyword_rank_snapshots") or keyword_validation.get("rank_snapshots") or []
    if not isinstance(keyword_rank_snapshots, list):
        keyword_rank_snapshots = []
    validation_organic_strength = _num_value(keyword_validation.get("organic_rank_strength"), -1) if keyword_validation else -1
    validation_ad_risk = _num_value(keyword_validation.get("ad_dependency_risk"), -1) if keyword_validation else -1
    validation_score = _num_value(keyword_validation.get("keyword_sales_score"), -1) if keyword_validation else -1
    validation_top20_count = sum(
        1
        for row in keyword_rank_snapshots
        if isinstance(row, dict) and _num_value(row.get("organic_position"), 999) <= 20
    )
    validation_sponsored_count = sum(1 for row in keyword_rank_snapshots if isinstance(row, dict) and row.get("is_sponsored"))
    top20 = product_data.get("top20_competitors") or product_data.get("top40_items") or []
    top20_count = len(top20) if isinstance(top20, list) else 0
    low_review_rank_count = 0
    sponsored_count = 0
    if isinstance(top20, list):
        for index, item in enumerate(top20[:20], start=1):
            if not isinstance(item, dict):
                continue
            item_reviews = _num_value(item.get("review_count") or item.get("reviews") or item.get("reviewCount"))
            if index <= 20 and item_reviews and item_reviews <= 500:
                low_review_rank_count += 1
            if item.get("isSponsored") or item.get("sponsored"):
                sponsored_count += 1
    sponsored_ratio = sponsored_count / top20_count if top20_count else _num_value(product_data.get("sponsored_ratio"), 0)
    if keyword_validation and not top20_count and validation_ad_risk >= 0:
        sponsored_ratio = max(sponsored_ratio, min(0.8, validation_ad_risk / 100))
    organic_entry_score = 4.5 if bsr and bsr <= 3000 and reviews < 10000 else 3.6 if bsr and bsr <= 20000 else 2.4 if bsr else 2.8
    if validation_organic_strength >= 75:
        organic_entry_score = max(organic_entry_score, 4.2)
    elif 0 <= validation_organic_strength < 45:
        organic_entry_score = min(organic_entry_score, 2.7)
    if reviews >= 30000 and bsr and bsr <= 5000:
        organic_entry_score = min(organic_entry_score, 2.2)
    review_barrier_score = 4.4 if reviews < 800 else 3.5 if reviews < 5000 else 2.4 if reviews < 30000 else 1.5
    validation_new_entry_case = bool(validation_top20_count and reviews and reviews <= 800)
    search_entry_evidence = [f"关键词证据 {keyword_count} 组", f"BSR {int(bsr)}" if bsr else "BSR缺失"]
    if validation_organic_strength >= 0:
        search_entry_evidence.append(f"自然流量强度 {round(validation_organic_strength)}")
    organic_access_evidence = [f"BSR {int(bsr)}" if bsr else "BSR缺失", f"评论 {int(reviews)}"]
    if validation_top20_count:
        organic_access_evidence.append(f"核心词Top20自然位 {validation_top20_count} 个")
    ad_pressure_evidence = [f"广告位占比 {round(sponsored_ratio * 100)}%"]
    if validation_sponsored_count:
        ad_pressure_evidence.append(f"核心词广告位命中 {validation_sponsored_count} 个")
    elif validation_ad_risk >= 0:
        ad_pressure_evidence.append(f"广告依赖风险 {round(validation_ad_risk)}%")

    item_map = {
        "pain_clarity": _score_item(min(5, 1.5 + pain_hits * 0.7), [f"痛点词命中 {pain_hits} 个"], [] if pain_hits >= 2 else ["标题/五点未充分暴露用户痛点"], "补充评论痛点和差评问题，确认是否是真需求。"),
        "usage_frequency": _score_item(4.5 if any(x in text for x in ["daily", "everyday", "home", "office", "cat", "charger"]) else 3, ["存在日常/高频使用信号"] if any(x in text for x in ["daily", "everyday", "home", "office", "cat", "charger"]) else [], ["缺少使用频率证据"] if not any(x in text for x in ["daily", "everyday", "home", "office", "cat", "charger"]) else [], "用评论、QA或场景词确认使用频率。"),
        "demand_rigidity": _score_item(4.2 if pain_hits >= 3 else 3 if pain_hits >= 1 else 2, [f"痛点强度 {pain_hits}"], [] if pain_hits else ["刚需证据不足"], "判断用户是否必须解决该问题，而不是可买可不买。"),
        "payment_clarity": _score_item(4.3 if rating >= 4.3 and reviews >= 100 else 3.5 if price > 0 and rating >= 4 else 2.5, [f"价格 {price}", f"评分 {rating}", f"评论 {int(reviews)}"], ["价值支撑不足"] if rating < 4.1 or reviews < 50 else [], "用功能、效果、信任证据支撑付费理由。"),
        "core_keyword_capacity": _score_item(4.4 if keyword_count >= 5 or validation_score >= 75 else 3.6 if keyword_count >= 2 or bsr or validation_top20_count else 2.6, search_entry_evidence, ["核心搜索入口证据不足"] if keyword_count < 2 and not bsr and not validation_top20_count else [], "先确定1-3个核心词，再用Top40排名和广告位验证入口大小。"),
        "long_tail_opportunity": _score_item(4.2 if scenario_hits >= 3 and pain_hits >= 1 else 3.3 if scenario_hits >= 2 or pain_hits >= 2 else 2.4, [f"场景词 {scenario_hits}", f"痛点词 {pain_hits}"], ["缺少长尾场景/属性组合词"] if scenario_hits < 2 else [], "把用途、对象、属性组合成长尾词，优先验证低CPC高CVR入口。"),
        "organic_entry_access": _score_item(organic_entry_score, organic_access_evidence, ["自然位进入难度高"] if organic_entry_score < 3 else [], "看核心词Top40自然位，而不是只看BSR。若头部评论过高，切细分词进入。"),
        "ad_entry_tolerance": _score_item(4 if price >= 40 else 3.2 if price >= 25 else 2.2 if price > 0 else 2.5, [f"价格 {price}"], ["客单价低，广告试错空间小"] if price and price < 25 else [], "用目标毛利和CPC反推可承受ACOS，低客单价优先找自然/长尾入口。"),
        "scene_clarity": _score_item(min(5, 1.5 + scenario_hits * 0.6), [f"场景词命中 {scenario_hits} 个"], [] if scenario_hits >= 2 else ["场景表达不足"], "明确核心使用场景和目标人群。"),
        "scene_trigger": _score_item(4.2 if scenario_hits >= 3 and pain_hits >= 1 else 3 if scenario_hits else 2, [f"场景 {scenario_hits} / 痛点 {pain_hits}"], ["场景不能强触发购买"] if scenario_hits < 2 else [], "用状态触发词表达什么时候会需要它。"),
        "scene_expansion": _score_item(4.2 if scenario_hits >= 4 else 3 if scenario_hits >= 2 else 2, [f"可扩展场景 {scenario_hits}"], ["场景过窄"] if scenario_hits < 2 else [], "补充相邻场景但不要泛化到无关人群。"),
        "scene_visual": _score_item(4.5 if image_count >= 7 or has_video else 3.5 if image_count >= 4 else 2, [f"图片数 {int(image_count)}", f"视频 {has_video}"], ["图片/视频场景证据不足"] if image_count < 7 and not has_video else [], "用图片/视频验证场景是否可视化。"),
        "top20_review_barrier": _score_item(review_barrier_score, [f"当前评论 {int(reviews)}", f"低评论高位样本 {low_review_rank_count} 个"], ["Top20评论门槛偏高"] if review_barrier_score < 3 else [], "不要只看销量第一，要看Top20里有没有低评论也能上位的切口。"),
        "low_review_rank_opportunity": _score_item(4.2 if low_review_rank_count >= 2 or product_data.get("new_seller_case") or validation_new_entry_case else 3 if low_review_rank_count == 1 or validation_top20_count else 2.3, [f"低评论高排名样本 {low_review_rank_count} 个", f"本ASIN核心词Top20 {validation_top20_count} 个"], ["缺少新品/低评论进入案例"] if low_review_rank_count == 0 and not product_data.get("new_seller_case") and not validation_top20_count else [], "抓Top40，找低评论但自然位靠前的ASIN，证明新卖家仍可进入。"),
        "sponsored_pressure": _score_item(4.2 if sponsored_ratio <= 0.15 else 3 if sponsored_ratio <= 0.35 else 2.1, ad_pressure_evidence, ["广告位压力高，可能需要更强预算或更细长尾词"] if sponsored_ratio > 0.35 else [], "核心词广告位过密时，先切属性词/场景词，别正面烧钱。"),
        "homogeneity": _score_item(2.2 if diff_hits == 0 else 3.2 if diff_hits < 2 else 4, [f"差异化信号 {diff_hits}"], ["同质化风险高"] if diff_hits == 0 else [], "对Top竞品做同尺子比较，确认同质化程度。"),
        "differentiation_anchor": _score_item(min(5, 1.8 + diff_hits * 0.8), [f"差异化词命中 {diff_hits} 个"], ["差异化锚点不清晰"] if diff_hits < 2 else [], "找到可以被Listing和广告表达的核心差异。"),
        "listing_expression_fit": _score_item(4.3 if bullet_count >= 5 and image_count >= 6 else 3.3 if bullet_count >= 3 and image_count >= 4 else 2.2, [f"五点 {bullet_count}/5", f"图片 {int(image_count)}"], ["Listing承接不足，差异点无法被图文证明"] if bullet_count < 5 or image_count < 6 else [], "差异化必须能被标题、主图、副图、五点和A+重复证明。"),
        "substitution_difficulty": _score_item(4 if diff_hits >= 3 and reviews >= 100 else 3 if diff_hits else 2, [f"差异化 {diff_hits}", f"评论门槛 {int(reviews)}"], ["用户转向竞品成本低"] if diff_hits < 2 else [], "确认是否有结构、配件、体验或服务门槛。"),
        "competitor_weakness": _score_item(3.5 if product_data.get("review_pain_points") else 2.2, ["已有评论痛点数据"] if product_data.get("review_pain_points") else [], ["缺少竞品差评机会数据"], "抓取竞品差评，找可攻击弱点。"),
        "gross_margin": _score_item(4 if price >= 35 else 3 if price >= 20 else 2, [f"价格 {price}"], ["低价品毛利空间偏窄"] if price and price < 20 else [], "补充采购成本、FBA费和退货率后复算毛利。"),
        "ad_tolerance": _score_item(4 if price >= 40 else 3 if price >= 25 else 2, [f"价格可承受CPC区间 {price}"], ["客单价低，广告承受力弱"] if price and price < 25 else [], "补充CPC数据和目标ACOS测算广告承受力。"),
        "pricing_rationality": _score_item(4.2 if 15 <= price <= 80 else 3 if price > 0 else 1.5, [f"价格 {price}"], ["缺少价格或价格带异常"] if price <= 0 or price > 120 else [], "和Top10价格带对比，确认是否匹配承诺强度。"),
        "profit_scalability": _score_item(4 if any(x in text for x in ["set", "pack", "refill", "replace", "accessory"]) else 2.8, ["存在套装/耗材/配件信号"] if any(x in text for x in ["set", "pack", "refill", "replace", "accessory"]) else [], ["放大利润空间不明确"], "寻找捆绑、变体、配件或复购方案。"),
        "demand_growth": _score_item(3.6 if bsr and bsr < 50000 else 3, [f"BSR {int(bsr)}"] if bsr else [], ["缺少BSR历史/关键词趋势"], "补充BSR历史和关键词搜索趋势。"),
        "category_lifecycle": _score_item(3.5 if reviews < 5000 else 2.8, [f"评论门槛 {int(reviews)}"], ["品类可能成熟，需验证新品进入案例"] if reviews >= 5000 else [], "检查新品是否仍能进入前排。"),
        "compliance_risk": _score_item(2.5 if compliance_hits or risk_hits else 4, [f"合规/风险词 {compliance_hits + risk_hits}"], ["可能涉及认证、侵权或合规风险"] if compliance_hits or risk_hits else [], "确认认证、专利、类目限制和平台政策。"),
        "tech_supply_trend": _score_item(3.6 if any(x in text for x in ["usb", "bluetooth", "wireless", "battery", "led"]) else 3, ["存在技术/供应链关键词"] if any(x in text for x in ["usb", "bluetooth", "wireless", "battery", "led"]) else [], ["缺少供应链稳定性证据"], "确认技术迭代速度和供应链稳定性。"),
        "price_band_match": _score_item(4 if 20 <= price <= 70 else 3 if price > 0 else 1, [f"价格 {price}"], ["价格带可能错配"] if price <= 0 or price > 120 else [], "对比Top20价格分布确认所在价格带。"),
        "value_perception": _score_item(4 if rating >= 4.3 and (has_a_plus or image_count >= 7) else 3, [f"评分 {rating}", f"A+ {has_a_plus}", f"图片 {int(image_count)}"], ["价值感知支撑不足"] if rating < 4.2 else [], "用A+、图片和评论支撑价格价值感。"),
        "premium_potential": _score_item(4 if diff_hits >= 2 and has_a_plus else 2.8, [f"差异化 {diff_hits}", f"A+ {has_a_plus}"], ["溢价证据不足"] if diff_hits < 2 else [], "用品牌信任和差异化证明支撑溢价。"),
        "price_risk_resistance": _score_item(4 if price >= 35 and diff_hits >= 2 else 2.8, [f"价格 {price}", f"差异化 {diff_hits}"], ["容易陷入价格战"] if diff_hits < 2 else [], "验证是否能避开纯价格竞争。"),
        "new_entry_signal": _score_item(4.2 if product_data.get("new_seller_case") or low_review_rank_count >= 2 or validation_new_entry_case else 3 if bsr and bsr < 50000 or validation_top20_count else 2.3, [f"新品/低评论进入证据 {low_review_rank_count} 个", f"本ASIN核心词Top20 {validation_top20_count} 个"], ["缺少新卖家进入证据"] if not product_data.get("new_seller_case") and low_review_rank_count == 0 and not validation_top20_count else [], "用Top40和评论增长确认新品是否仍能进入，而不是只看头部销量。"),
    }

    dimensions = []
    dimension_scores = {}
    detail_scores = {}
    analysis = {}
    ai_adjustments = (ai_result or {}).get("ai_adjustments", {}) if isinstance(ai_result, dict) else {}
    for dim_key, dim_name, items in SIX_DIMENSION_SCHEMA:
        item_rows = []
        base_score = 0.0
        final_score = 0.0
        for item_key, item_name in items:
            row = dict(item_map[item_key])
            requested_adj = 0
            if isinstance(ai_adjustments, dict):
                requested_adj = _num_value(ai_adjustments.get(item_key), 0)
            requested_adj = max(-1, min(1, requested_adj))
            row["ai_adjustment"] = round(requested_adj, 1)
            row["final_score"] = max(0, min(5, round(row["rule_score"] + requested_adj, 1)))
            row["item_key"] = item_key
            row["item_name"] = item_name
            base_score += row["rule_score"]
            final_score += row["final_score"]
            detail_scores[item_key] = row["final_score"]
            item_rows.append(row)
        dim_ai_adjustment = round(final_score - base_score, 1)
        dimension_scores[dim_key] = round(final_score, 1)
        analysis[dim_key] = "；".join([item["suggestion"] for item in item_rows[:2]])
        dimensions.append({
            "dimension_name": dim_name,
            "dimension_key": dim_key,
            "base_score": round(base_score, 1),
            "ai_adjustment": dim_ai_adjustment,
            "final_score": round(final_score, 1),
            "confidence": completeness,
            "items": item_rows,
        })

    raw_total = round(sum(dimension_scores.values()), 1)
    total_score = round(raw_total * 100 / 120, 1)

    seller_type = str(product_data.get("seller_type") or "")
    platform_ecosystem = bool(product_data.get("platform_ecosystem"))
    platform_terms = ["echo show", "echo dot", "echo spot", "echo studio", "alexa", "fire tv", "kindle", "ring video", "blink outdoor"]
    accessory_context = any(x in text for x in ["compatible", "case for", "cover for", "stand for", "mount for", "charger for", "replacement"])
    amazon_owned_or_bound = platform_ecosystem or "平台生态" in seller_type or "Amazon自营" in seller_type
    hard_compliance_context = any(x in text for x in ["medical", "baby", "food", "fda", "ul", "fcc", "battery", "laser", "chemical"])
    has_bundle_or_accessory_margin = any(x in text for x in ["pack", "set", "bundle", "replacement", "accessory", "refill"])
    review_barrier = reviews >= 30000 and bsr and bsr <= 3000 and not product_data.get("new_seller_case")
    low_price_barrier = bool(price and price < 10 and not has_bundle_or_accessory_margin)

    veto_rules = [
        {"rule_name": "品牌垄断明显", "triggered": bool(product_data.get("brand_monopoly_risk")), "reason": "存在明确品牌垄断或品牌强绑定证据。", "evidence": [seller_type]},
        {"rule_name": "平台生态强绑定", "triggered": bool((amazon_owned_or_bound or any(x in text for x in platform_terms)) and not accessory_context), "reason": "该商品依赖Amazon自有生态、系统入口或品牌流量，不应按普通第三方产品直接进入。", "evidence": [title, seller_type]},
        {"rule_name": "侵权风险高", "triggered": risk_hits >= 1 or "patent" in text, "reason": "存在侵权或受限关键词信号。", "evidence": [f"风险词命中 {risk_hits}"]},
        {"rule_name": "认证/合规风险高", "triggered": compliance_hits >= 3 and hard_compliance_context, "reason": "可能需要强认证或合规准入。", "evidence": [f"合规词命中 {compliance_hits}"]},
        {"rule_name": "利润无法覆盖广告成本", "triggered": low_price_barrier, "reason": "低客单价产品广告承受力弱，需要核算套装、配件或供应链成本。", "evidence": [f"价格 {price}"]},
        {"rule_name": "价格带严重错配", "triggered": bool(price and price > 150 and rating < 4.3), "reason": "高价但评分/信任支撑不足。", "evidence": [f"价格 {price}", f"评分 {rating}"]},
        {"rule_name": "履约不可控", "triggered": any(x in text for x in ["fragile", "oversize", "glass", "liquid", "heavy"]), "reason": "可能存在破损、超大件、液体或重货履约风险。", "evidence": [title]},
        {"rule_name": "Review门槛过高且新品无进入案例", "triggered": review_barrier, "reason": "头部样本评论门槛很高，不适合正面复制，需要找细分词、差异款或长尾切口。", "evidence": [f"评论数 {int(reviews)}", f"BSR {int(bsr)}"]},
        {"rule_name": "产品差异化无法通过Listing表达", "triggered": diff_hits == 0 and total_score < 70, "reason": "缺少可表达差异点，容易进入价格竞争。", "evidence": ["差异化信号为0"]},
        {"rule_name": "不是第三方卖家的合理切入品", "triggered": bool(amazon_owned_or_bound and reviews > 1000 and not accessory_context), "reason": "平台自营/生态强绑定且评论门槛较高，普通第三方卖家直接切入风险大。", "evidence": [seller_type, f"评论数 {int(reviews)}"]},
    ]
    triggered_vetoes = [rule for rule in veto_rules if rule["triggered"]]
    hard_vetoes = [rule for rule in triggered_vetoes if rule["rule_name"] in SIX_DIMENSION_HARD_VETO_NAMES]
    market_barriers = [rule for rule in triggered_vetoes if rule["rule_name"] not in SIX_DIMENSION_HARD_VETO_NAMES]
    risk_level = (
        "high"
        if hard_vetoes or total_score < 45
        else "medium"
        if market_barriers or total_score < 75 or confidence_level == "low"
        else "low"
    )

    derivative_signal = (
        total_score >= 55
        and (
            market_barriers
            or dimension_scores.get("competition", 0) < 12
            or dimension_scores.get("differentiation", 0) < 12
        )
        and (dimension_scores.get("search_entry", 0) >= 10 or scenario_hits >= 2 or pain_hits >= 2)
    )
    if hard_vetoes:
        pool_status = "rejected_pool"
    elif total_score >= 75 and risk_level != "high":
        pool_status = "opportunity_pool"
    elif 65 <= total_score < 75 and risk_level in {"low", "medium"}:
        pool_status = "validation_pool"
    elif derivative_signal:
        pool_status = "derivative_pool"
    elif total_score < 55 or risk_level == "high":
        pool_status = "rejected_pool"
    else:
        pool_status = "not_entered"

    if hard_vetoes:
        decision = "暂缓进入"
    elif pool_status == "opportunity_pool":
        decision = "可进入验证"
    elif pool_status == "validation_pool":
        decision = "小预算验证"
    elif pool_status == "derivative_pool":
        decision = "找细分机会"
    elif total_score >= 60:
        decision = "补证后再评估"
    else:
        decision = "暂不建议进入"

    action_map = {
        "可进入验证": ["生成 Listing 方向", "生成首轮广告验证词", "创建执行跟踪任务"],
        "小预算验证": ["生成最小验证方案", "生成测试关键词", "生成验证指标"],
        "补证后再评估": ["补齐关键证据", "提取竞品差评机会", "重新评估"],
        "找细分机会": ["查找替代机会", "分析配件/周边市场", "重新选择相邻类目"],
        "暂不建议进入": ["查找替代机会", "分析配件/周边市场", "重新选择相邻类目"],
        "暂缓进入": ["查看风险证据", "生成避坑报告", "重新选品"],
    }
    recommended_path = {
        "opportunity_pool": "/listing-launch-check",
        "validation_pool": "/ab-test-comparison",
        "derivative_pool": "/asin-manager",
        "rejected_pool": "/asin-manager",
        "not_entered": "/asin-manager",
    }.get(pool_status, "/asin-manager")
    confidence_label = {"high": "较完整", "medium": "一般", "low": "偏少"}.get(confidence_level, confidence_level)
    risk_label = {"high": "高", "medium": "中", "low": "低"}.get(risk_level, risk_level)
    gate_reason = (
        f"需要先排查：{hard_vetoes[0]['rule_name']}" if hard_vetoes
        else f"进入前需确认：{market_barriers[0]['rule_name']}" if market_barriers
        else "未发现必须先排查的硬伤"
    )
    one_sentence_reason = f"{decision}：总分{total_score}，证据完整度{confidence_label}，主要风险{risk_label}，{gate_reason}。"

    return {
        "raw_total": raw_total,
        "total_score": total_score,
        "qualified": pool_status == "opportunity_pool",
        "dimension_scores": dimension_scores,
        "detail_scores": detail_scores,
        "analysis": analysis,
        "suggestions": action_map.get(decision, []),
        "data_completeness": completeness,
        "confidence_level": confidence_level,
        "data_completeness_checks": completeness_checks,
        "risk_level": risk_level,
        "decision": decision,
        "pool_status": pool_status,
        "recommended_path": recommended_path,
        "one_sentence_reason": one_sentence_reason,
        "dimensions": dimensions,
        "veto_rules": veto_rules,
        "next_actions": action_map.get(decision, []),
        "analysis_mode": "rule_fallback",
        "ai_called": False,
        "fallback_reason": None,
        "rule_guardrails": {
            "hard_vetoes": hard_vetoes,
            "market_barriers": market_barriers,
            "triggered_vetoes": triggered_vetoes,
        },
        "price_tier_category": "high" if price >= 70 else "medium" if price >= 20 else "low",
        "price_tier_analysis": {
            "category": "high" if price >= 70 else "medium" if price >= 20 else "low",
            "confidence": round(completeness * 100),
            "tier_percentile": 80 if price >= 70 else 50 if price >= 20 else 20,
        },
    }


@router.post("/five-dimension-score", response_model=FiveDimensionScoreResponse)
async def five_dimension_score(
    request: FiveDimensionScoreRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run 6-Dimension Product Scoring (6维产品级决策引擎).

    The canonical scoring path is now:
    real input data -> AI semantic main judgment -> deterministic rule guardrails
    -> risk veto -> pool routing. If AI is unavailable or returns invalid JSON,
    the deterministic engine is used as a clearly marked fallback.
    """
    try:
        asin = request.asin.strip().upper()
        if not asin:
            raise HTTPException(status_code=400, detail="请输入ASIN")

        # Build product context from provided data or try to get from DB
        product_data = request.product_data or {}
        product_title = request.product_title or ""

        # If no product data provided, try to find from existing analyses or products table
        if not product_data and not product_title:
            svc = Asin_analysesService(db)
            existing = await svc.list_by_field("asin", asin, limit=1)
            if existing:
                latest = existing[0]
                product_title = latest.product_title or ""
                try:
                    product_data = json.loads(latest.product_data) if latest.product_data else {}
                except (json.JSONDecodeError, TypeError):
                    product_data = {}

        rule_engine = _build_six_dimension_rule_engine(
            asin=asin,
            marketplace=request.marketplace,
            product_title=product_title or product_data.get("title", ""),
            product_data=product_data,
            ai_result=None,
        )
        try:
            ai_payload = await _run_six_dimension_ai_primary(
                asin=asin,
                marketplace=request.marketplace,
                product_title=product_title or product_data.get("title", ""),
                product_data=product_data,
                rule_engine=rule_engine,
            )
            engine = _merge_ai_primary_six_dimension(rule_engine, ai_payload)
        except Exception as ai_error:
            logger.warning("6D AI primary judgment failed for %s, using rule fallback: %s", asin, ai_error)
            engine = copy.deepcopy(rule_engine)
            engine["analysis_mode"] = "rule_fallback"
            engine["ai_called"] = False
            engine["fallback_reason"] = str(ai_error)
            engine.update(_apply_six_dimension_routing(engine))

        dimension_scores = engine["dimension_scores"]
        detail_scores = engine["detail_scores"]
        analysis = engine["analysis"]
        suggestions = engine["suggestions"]
        raw_total = engine["raw_total"]
        total_score = engine["total_score"]
        qualified = engine["qualified"]
        price_tier_analysis = engine["price_tier_analysis"]
        price_tier_category = engine["price_tier_category"]
        overall_summary = engine["one_sentence_reason"]

        detail_payload = {
            "dimension_scores": dimension_scores,
            "detail_scores": detail_scores,
            "analysis": analysis,
            "overall_summary": overall_summary,
            "suggestions": suggestions,
            "price_tier_analysis": price_tier_analysis,
            "raw_total": raw_total,
            "data_completeness": engine["data_completeness"],
            "confidence_level": engine["confidence_level"],
            "data_completeness_checks": engine["data_completeness_checks"],
            "risk_level": engine["risk_level"],
            "decision": engine["decision"],
            "pool_status": engine["pool_status"],
            "recommended_path": engine["recommended_path"],
            "one_sentence_reason": engine["one_sentence_reason"],
            "dimensions": engine["dimensions"],
            "veto_rules": engine["veto_rules"],
            "next_actions": engine["next_actions"],
            "analysis_mode": engine.get("analysis_mode", "rule_fallback"),
            "ai_called": engine.get("ai_called", False),
            "fallback_reason": engine.get("fallback_reason"),
            "rule_guardrails": engine.get("rule_guardrails", {}),
        }

        # Save to database
        svc = Asin_analysesService(db)
        record = await svc.create({
            "asin": asin,
            "marketplace": request.marketplace,
            "product_title": product_title or product_data.get("title", ""),
            "product_data": json.dumps(product_data, ensure_ascii=False) if product_data else "",
            "score_5d_total": total_score,
            "score_5d_demand": float(dimension_scores.get("demand", 0)),
            "score_5d_scenario": float(dimension_scores.get("search_entry", 0)),
            "score_5d_competition": float(dimension_scores.get("competition", 0)),
            "score_5d_profit": float(dimension_scores.get("differentiation", 0)),
            "score_5d_trend": float(dimension_scores.get("business", 0)),
            "score_5d_price_tier": float(dimension_scores.get("risk_trend", 0)),
            "price_tier_category": price_tier_category,
            "price_tier_analysis": json.dumps(price_tier_analysis, ensure_ascii=False),
            "score_5d_detail": json.dumps(detail_payload, ensure_ascii=False),
            "qualified": 1 if qualified else 0,
            "analysis_report": json.dumps({
                "type": "6d_decision_engine",
                "overall_summary": overall_summary,
                "suggestions": suggestions,
                "price_tier": price_tier_category,
                "decision": engine["decision"],
                "pool_status": engine["pool_status"],
                "risk_level": engine["risk_level"],
                "confidence_level": engine["confidence_level"],
                "analysis_mode": engine.get("analysis_mode", "rule_fallback"),
                "ai_called": engine.get("ai_called", False),
                "fallback_reason": engine.get("fallback_reason"),
            }, ensure_ascii=False),
            "created_at": datetime.now(timezone.utc),
        }, user_id=str(current_user.id))

        return FiveDimensionScoreResponse(
            success=True,
            asin=asin,
            product_title=product_title or product_data.get("title", ""),
            total_score=total_score,
            raw_total=raw_total,
            qualified=qualified,
            dimension_scores=dimension_scores,
            price_tier_category=price_tier_category,
            price_tier_analysis=price_tier_analysis,
            detail_scores=detail_scores,
            analysis=analysis,
            suggestions=suggestions,
            data_completeness=engine["data_completeness"],
            confidence_level=engine["confidence_level"],
            risk_level=engine["risk_level"],
            decision=engine["decision"],
            pool_status=engine["pool_status"],
            recommended_path=engine["recommended_path"],
            one_sentence_reason=engine["one_sentence_reason"],
            dimensions=engine["dimensions"],
            veto_rules=engine["veto_rules"],
            next_actions=engine["next_actions"],
            analysis_mode=engine.get("analysis_mode", "rule_fallback"),
            ai_called=bool(engine.get("ai_called", False)),
            fallback_reason=engine.get("fallback_reason"),
            rule_guardrails=engine.get("rule_guardrails", {}),
            id=record.id if record else None,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"6D score error for {request.asin}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"6D score error for {request.asin}: {e}")
        raise HTTPException(status_code=500, detail=f"6维评分失败: {str(e)}")


@router.post("/six-dimension-score", response_model=FiveDimensionScoreResponse)
async def six_dimension_score(
    request: FiveDimensionScoreRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Canonical 6D scoring endpoint. The old five-dimension endpoint is kept for compatibility."""
    return await five_dimension_score(request=request, current_user=current_user, db=db)


@router.get("/five-dimension-history")
async def get_five_dimension_history(
    asin: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get 6-dimension scoring history, optionally filtered by ASIN."""
    from sqlalchemy import select, func, and_
    from models.asin_analyses import Asin_analyses

    try:
        scope_user_ids = await get_user_scope_ids(current_user, db)
        base_filter = and_(
            Asin_analyses.user_id.in_(scope_user_ids),
            Asin_analyses.score_5d_total.isnot(None),
        )
        if asin:
            base_filter = and_(base_filter, Asin_analyses.asin == asin.strip().upper())

        count_q = select(func.count(Asin_analyses.id)).where(base_filter)
        count_result = await db.execute(count_q)
        total = count_result.scalar() or 0

        query = (
            select(Asin_analyses)
            .where(base_filter)
            .order_by(Asin_analyses.id.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        rows = result.scalars().all()

        items = []
        for row in rows:
            detail = {}
            if row.score_5d_detail:
                try:
                    detail = json.loads(row.score_5d_detail)
                except (json.JSONDecodeError, TypeError):
                    pass
            stored_product_data = {}
            if row.product_data:
                try:
                    stored_product_data = json.loads(row.product_data)
                except (json.JSONDecodeError, TypeError):
                    stored_product_data = {}
            if row.product_title and not stored_product_data.get("title"):
                stored_product_data["title"] = row.product_title
            fallback_completeness, fallback_confidence, _fallback_checks = _data_completeness(stored_product_data)
            data_completeness = detail.get("data_completeness") or fallback_completeness
            confidence_level = detail.get("confidence_level") or fallback_confidence
            detail_dimensions = detail.get("dimensions", [])
            is_legacy_score = not bool(detail_dimensions) or not bool(detail.get("data_completeness"))
            if isinstance(detail_dimensions, list):
                for dim in detail_dimensions:
                    if isinstance(dim, dict) and dim.get("dimension_key") in {"scenario", "profit", "trend", "price_tier"}:
                        is_legacy_score = True
                    for item in dim.get("items", []) if isinstance(dim, dict) else []:
                        if item.get("item_name") in {"价值支撑", "促销空间", "价格竞争力", "价格带供需结构", "价格带进入门槛", "价格带抗风险能力"}:
                            is_legacy_score = True
            stored_scores = detail.get("dimension_scores") if isinstance(detail, dict) else None
            if not isinstance(stored_scores, dict):
                stored_scores = {
                    "demand": row.score_5d_demand,
                    "search_entry": row.score_5d_scenario,
                    "competition": row.score_5d_competition,
                    "differentiation": row.score_5d_profit,
                    "business": row.score_5d_trend,
                    "risk_trend": getattr(row, "score_5d_price_tier", 0),
                }

            items.append({
                "id": row.id,
                "asin": row.asin,
                "marketplace": row.marketplace,
                "product_title": row.product_title,
                "total_score": row.score_5d_total,
                "raw_total": detail.get("raw_total", 0),
                "qualified": bool(row.qualified),
                "dimension_scores": stored_scores,
                "price_tier_category": getattr(row, "price_tier_category", None),
                "price_tier_analysis": json.loads(row.price_tier_analysis) if getattr(row, "price_tier_analysis", None) else {},
                "detail_scores": detail.get("detail_scores", {}),
                "analysis": detail.get("analysis", {}),
                "suggestions": detail.get("suggestions", []),
                "data_completeness": data_completeness,
                "confidence_level": confidence_level,
                "risk_level": detail.get("risk_level", "medium"),
                "decision": detail.get("decision", "not_entered"),
                "pool_status": detail.get("pool_status", "not_entered"),
                "recommended_path": detail.get("recommended_path", ""),
                "one_sentence_reason": detail.get("one_sentence_reason", detail.get("overall_summary", "")),
                "dimensions": detail.get("dimensions", []),
                "veto_rules": detail.get("veto_rules", []),
                "next_actions": detail.get("next_actions", []),
                "is_legacy_score": is_legacy_score,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })

        return {"items": items, "total": total}
    except Exception as e:
        logger.error(f"6D history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/six-dimension-history")
async def get_six_dimension_history(
    asin: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Canonical 6D scoring history endpoint. The old endpoint remains compatible."""
    return await get_five_dimension_history(
        asin=asin,
        skip=skip,
        limit=limit,
        current_user=current_user,
        db=db,
    )
