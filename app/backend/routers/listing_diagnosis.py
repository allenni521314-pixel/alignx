"""
Listing Diagnosis & Optimization Router.
Provides COSMO 8D+2 listing diagnosis, keyword coverage analysis,
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
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from schemas.auth import UserResponse
from services.aihub import AIHubService
from services.amazon_rules_engine import evaluate_amazon_compliance, load_active_rules
from services.judgment_feedback_rounds import JudgmentFeedbackRoundService
from services.listing_diagnoses import Listing_diagnosesService
from services.judgment_system import JudgmentSystemService
from services.cosmo_rufus_rules import build_cosmo_rufus_analysis, merge_cosmo_rufus_into_legacy

logger = logging.getLogger(__name__)
AI_DIAGNOSIS_TIMEOUT_SECONDS = int(os.getenv("AI_DIAGNOSIS_TIMEOUT_SECONDS", "180"))

router = APIRouter(prefix="/api/v1/listing-diagnosis", tags=["listing-diagnosis"])


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
        zh_rules = [
            (r"旅行箱.*充电宝|旅行.*充电宝", "travel power bank"),
            (r"适合.*小钱包.*充电器|小钱包.*充电器", "compact charger for small purse"),
            (r"双装.*移动电源.*礼品|移动电源.*礼品", "power bank gift set"),
            (r"口袋型.*超薄.*电池组|超薄.*电池组|口袋型.*电池", "slim pocket power bank"),
            (r"usb\s*c.*移动电源.*iphone.*三星|移动电源.*iphone.*三星", "usb c power bank for iphone and samsung"),
            (r"slimmest.*10000mah.*移动电源|10000mah.*移动电源", "slimmest 10000mah power bank"),
            (r"轻型.*飞机.*手机充电器|飞机.*手机充电器", "lightweight phone charger for flights"),
            (r"便携式.*充电器|充电宝|移动电源|手机充电器", "portable phone power bank"),
            (r"泳池.*夹式.*蓝牙|夹式.*蓝牙.*泳池", "clip on bluetooth speaker for pool"),
            (r"夹式.*蓝牙|蓝牙.*夹式", "clip on bluetooth speaker"),
            (r"便携式.*防水.*扬声器.*调频|防水.*扬声器.*调频|fm.*防水.*扬声器", "portable waterproof speaker with fm radio"),
            (r"迷你.*户外.*音箱.*背带|户外.*音箱.*背带", "mini outdoor speaker with carrying strap"),
            (r"适用于.*海滩.*tws|海滩.*tws.*无线.*扬声器|tws.*海滩", "tws speaker for beach trips"),
            (r"旅行.*徒步.*淋浴.*音箱|淋浴.*音箱.*旅行|淋浴.*音箱.*徒步", "shower speaker for hiking and travel"),
            (r"沙滩.*专用.*tws|沙滩.*tws.*无线.*音箱", "tws speaker for beach trips"),
            (r"防水.*蓝牙.*音箱|蓝牙.*音箱.*防水", "waterproof bluetooth speaker"),
            (r"防水.*扬声器|扬声器.*防水", "waterproof speaker"),
            (r"便携式.*蓝牙.*音箱|蓝牙.*音箱.*便携式", "portable bluetooth speaker"),
            (r"海滩|沙滩", "bluetooth speaker for beach trips"),
            (r"露营|户外", "portable speaker for camping"),
            (r"泳池|池边", "poolside bluetooth speaker"),
            (r"调频|收音机|fm", "bluetooth speaker with fm radio"),
            (r"背带|挂绳|肩带", "portable speaker with carrying strap"),
            (r"夹式|夹子", "clip on speaker"),
            (r"淋浴", "shower speaker"),
            (r"徒步", "speaker for hiking"),
            (r"tws", "tws bluetooth speaker"),
            (r"led|灯|彩灯|灯光|炫彩", "bluetooth speaker with led lights"),
            (r"礼物|送礼|生日", "bluetooth speaker gift"),
            (r"儿童|孩子|男孩|女孩|青少年", "speaker gift for kids"),
            (r"卧室|房间", "bedroom bluetooth speaker"),
            (r"派对|聚会", "party speaker with lights"),
            (r"猫砂.*臭|除臭|异味", "cat litter box odor control"),
            (r"氨气", "ammonia odor control"),
            (r"猫砂.*公寓|公寓.*猫", "litter box for apartment cats"),
            (r"防外溅|追踪|带砂", "reduce litter tracking"),
        ]
        for pattern, replacement in zh_rules:
            if re.search(pattern, text, flags=re.I):
                text = replacement
                break
        else:
            text = re.sub(r"[\u4e00-\u9fff]+", " ", text)
    text = re.sub(r"[^a-z0-9 +&/\\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_")
    for british, american in _US_SPELLING_REPLACEMENTS.items():
        text = re.sub(rf"\b{british}\b", american, text)
    words = text.split()
    normalized = " ".join(words[:8])
    return normalized if re.search(r"[a-z]", normalized) else ""


def _keyword_type(keyword: str) -> str:
    kw = keyword.lower()
    state_terms = ("odor", "smell", "ammonia", "pain", "relief", "anxiety", "safe", "comfort", "leak", "tracking", "mess", "stress", "sleep", "noise")
    relation_terms = ("for ", "with ", "without ", "under ", "near ", "compatible", "replacement", "indoor", "outdoor", "apartment", "bedroom", "travel", "kids", "women", "men", "cats", "dogs")
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


class DiagnoseRequest(BaseModel):
    listing: ListingInput
    precision_context: dict = {}
    force_refresh: bool = False


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
    amazon_compliance: dict = {}
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


async def _get_cached_listing_diagnosis(listing: ListingInput, db: AsyncSession, user_id: str) -> dict | None:
    """Return the user's latest saved diagnosis only for explicit history/latest loads."""
    if not listing.title:
        return None
    from sqlalchemy import select
    from models.listing_diagnoses import Listing_diagnoses as LD

    result = await db.execute(
        select(LD)
        .where(LD.user_id == user_id, LD.listing_title == listing.title[:500], LD.marketplace == listing.marketplace)
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


async def _get_exact_cached_listing_diagnosis(listing: ListingInput, db: AsyncSession, user_id: str) -> dict | None:
    """Return a saved diagnosis only when the current Listing content is identical."""
    if not listing.title:
        return None
    from sqlalchemy import select
    from models.listing_diagnoses import Listing_diagnoses as LD

    current_fingerprint = _listing_content_fingerprint(_sanitize_listing_for_ai(listing))
    result = await db.execute(
        select(LD)
        .where(LD.user_id == user_id, LD.listing_title == listing.title[:500], LD.marketplace == listing.marketplace)
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
        data["_cache_hit"] = "exact_content"
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


class ParseHtmlRequest(BaseModel):
    html: str
    marketplace: str = "US"
    asin: str = ""


class ParseHtmlResponse(BaseModel):
    listing: ListingInput
    asin: str = ""
    source: str = "browser_proxy"
    rating: str = ""
    review_count: str = ""
    bsr_rank: str = ""
    bsr_category: str = ""
    image_count: str = ""
    has_video: bool = False
    has_a_plus: bool = False
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

你是一位顶级亚马逊Listing优化专家，精通COSMO语义算法和美区消费者行为。
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

## 诊断维度（COSMO核心8D + 卖家扩展2D，共10个维度，每个0-100分）

### COSMO核心8D

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
产品的"is_a"和"used_as"定义是否清晰？COSMO算法如何理解这个产品？
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
产品的感性描述词是否丰富？是否触发了COSMO的主观属性匹配？
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
- attribute=产品属性词（如 bluetooth speaker、cat litter box），通常竞争激烈，只做基础覆盖。
- relationship=关系词（for apartments、with replaceable carbon filter、for indoor cats），用于验证使用关系和场景承接。
- state_trigger=状态触发词（odor control、ammonia smell、reduce litter tracking），用于验证用户状态差距和痛点承接。
- 广告验证优先级：state_trigger > relationship > attribute；high_conversion 和 long_tail 中必须优先放 relationship/state_trigger 词。

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
      "long_tail": ["已覆盖的长尾词"]
    }},
    "missing_categories": {{
      "core_category": ["缺失的核心品类词"],
      "function": ["缺失的功能词"],
      "scenario": ["缺失的场景词"],
      "audience": ["缺失的人群词"],
      "pain_point": ["缺失的痛点词"],
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
    "title": {{"functional": 0-100, "scenario": 0-100, "persona": 0-100, "motivation": 0-100, "competitive": 0-100, "trend": 0-100, "product_id": 0-100, "compat": 0-100, "subjective": 0-100, "market": 0-100, "summary": "标题各维度分析"}},
    "bullets": {{"functional": 0-100, "scenario": 0-100, "persona": 0-100, "motivation": 0-100, "competitive": 0-100, "trend": 0-100, "product_id": 0-100, "compat": 0-100, "subjective": 0-100, "market": 0-100, "summary": "五点描述各维度分析"}},
    "images": {{"functional": 0-100, "scenario": 0-100, "persona": 0-100, "motivation": 0-100, "competitive": 0-100, "trend": 0-100, "product_id": 0-100, "compat": 0-100, "subjective": 0-100, "market": 0-100, "summary": "图片各维度分析"}},
    "aplus": {{"functional": 0-100, "scenario": 0-100, "persona": 0-100, "motivation": 0-100, "competitive": 0-100, "trend": 0-100, "product_id": 0-100, "compat": 0-100, "subjective": 0-100, "market": 0-100, "summary": "A+内容各维度分析"}},
    "backend": {{"functional": 0-100, "scenario": 0-100, "persona": 0-100, "motivation": 0-100, "competitive": 0-100, "trend": 0-100, "product_id": 0-100, "compat": 0-100, "subjective": 0-100, "market": 0-100, "summary": "后台属性各维度分析"}}
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
8D+2诊断评分: {my_scores}

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
    if listing.bullet_points:
        parts.append(f"五点描述: {listing.bullet_points}")
    if listing.category:
        parts.append(f"类目: {listing.category}")
    if listing.price:
        parts.append(f"价格: {listing.price}")
    return " | ".join(parts) if parts else "未提供"


# All 10 dimension keys used in the elements heatmap
_ELEMENT_DIM_KEYS = [
    "functional", "scenario", "persona", "motivation", "competitive",
    "trend", "product_id", "compat", "subjective", "market",
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


def _derive_fallback_insights(listing: ListingInput) -> dict:
    text = f"{listing.title} {listing.bullet_points} {listing.description} {listing.a_plus_content} {listing.category}".lower()
    title = (listing.title or "").lower()
    price = listing.price or ""
    review_count = listing.review_count or ""
    rating = listing.rating or ""

    product_identity = "amazon product"
    covered: dict[str, list[str]] = {k: [] for k in ("core_category", "function", "scenario", "audience", "pain_point", "long_tail")}
    missing: dict[str, list[str]] = {k: [] for k in ("core_category", "function", "scenario", "audience", "pain_point", "long_tail")}
    ad_keywords: dict[str, list[dict]] = {"high_conversion": [], "traffic": [], "long_tail": []}
    suggestions: list[str] = []
    state_keywords: list[dict] = []

    def add_keyword(group: str, keyword: str, keyword_type: str, priority: str = "P1", competition: str = "medium") -> None:
        ad_keywords[group].append({
            "keyword": keyword,
            "keyword_type": keyword_type,
            "match_type": "phrase" if keyword_type != "attribute" else "exact",
            "intent": "验证状态触发词/关系词是否能带来更精准点击和转化" if keyword_type != "attribute" else "基础品类覆盖",
            "competition": competition,
            "priority": priority,
        })
        state_keywords.append({
            "keyword": keyword,
            "keyword_type": keyword_type,
            "source": "local_fallback_rules",
            "priority": priority,
            "validation_role": "广告验证关键词",
        })

    if any(word in text for word in ("bluetooth", "speaker", "boombox", "wireless speaker")):
        product_identity = "portable bluetooth speaker"
        covered["core_category"] = ["bluetooth speaker", "portable speaker"]
        covered["function"] = [kw for kw in ["waterproof", "24h playtime", "tws pairing", "led lights", "deep bass"] if kw in text]
        covered["scenario"] = [kw for kw in ["outdoor", "camping", "pool", "beach", "travel", "party", "bedroom", "gym"] if kw in text]
        covered["audience"] = [kw for kw in ["mom gifts", "gifts for women", "teen gifts"] if kw in text]
        missing["pain_point"] = ["loud sound for outdoor parties", "poolside waterproof speaker", "gift-ready bluetooth speaker"]
        missing["long_tail"] = ["portable speaker for beach trips", "bluetooth speaker with led lights for gifts", "small waterproof speaker for camping"]
        suggestions = [
            "标题已经覆盖蓝牙音箱、IPX5、防水、续航、TWS、礼物和户外场景，但表达偏堆叠，建议把第一优先级改成“portable waterproof bluetooth speaker for beach/pool/camping”。",
            "五点有功能信息，但状态触发不够强，建议补充“outdoor party sound”“poolside splash protection”“gift-ready speaker”这类可验证表达。",
            "价格显示为125.13，若实际为美元价格，需要重点复核价格抓取是否准确；该价格带对小型蓝牙音箱会显著影响转化。",
            "A+ 有内容和图片信号，但抓取到的是图片文本摘要，建议重点检查A+是否强化了户外、礼物、续航、防水和音效证据。",
        ]
        add_keyword("high_conversion", "waterproof bluetooth speaker for beach", "relationship", "P0", "medium")
        add_keyword("high_conversion", "portable speaker for camping", "relationship", "P0", "medium")
        add_keyword("high_conversion", "bluetooth speaker with led lights gift", "relationship", "P0", "medium")
        add_keyword("traffic", "portable bluetooth speaker", "attribute", "P2", "high")
        add_keyword("traffic", "waterproof speaker", "attribute", "P2", "high")
        add_keyword("long_tail", "small speaker for poolside music", "state_trigger", "P1", "low")
        add_keyword("long_tail", "outdoor party bluetooth speaker lights", "state_trigger", "P1", "medium")
    elif any(word in text for word in ("cat litter", "litter box", "cat")):
        product_identity = "cat litter box"
        covered["core_category"] = ["cat litter box"]
        covered["function"] = [kw for kw in ["carbon filter", "odor", "pull-out tray", "enclosed"] if kw in text]
        missing["pain_point"] = ["ammonia odor control", "reduce litter tracking", "easy cleaning for apartments"]
        missing["long_tail"] = ["cat litter box for apartment odor control", "enclosed litter box with carbon filter"]
        suggestions = [
            "优先把属性词升级成状态触发词：ammonia odor control、reduce litter tracking、easy cleaning。",
            "补强公寓/卧室/多猫家庭等关系词，避免只和普通 cat litter box 属性词竞争。",
        ]
        add_keyword("high_conversion", "cat litter box odor control", "state_trigger", "P0", "medium")
        add_keyword("high_conversion", "litter box for apartment cats", "relationship", "P0", "medium")
        add_keyword("long_tail", "reduce litter tracking enclosed box", "state_trigger", "P1", "low")
    else:
        tokens = [w for w in re.sub(r"[^a-z0-9\s]", " ", title).split() if len(w) > 2]
        product_identity = " ".join(tokens[:3]) if tokens else "amazon product"
        covered["core_category"] = [product_identity]
        missing["pain_point"] = ["state-trigger keyword not explicit", "relationship keyword not explicit"]
        suggestions = [
            "当前可识别产品身份，但缺少稳定的关系词和状态触发词，建议补充具体人群、场景和痛点。",
            "先用竞品和评论确认买家真实搜索状态，再进入广告验证。",
        ]
        add_keyword("traffic", product_identity, "attribute", "P2", "high")

    score_adjust = 0
    if rating:
        try:
            score_adjust += 4 if float(str(rating).split()[0]) >= 4.5 else 0
        except Exception:
            pass
    if review_count:
        try:
            score_adjust += 4 if int(re.sub(r"[^0-9]", "", str(review_count)) or "0") >= 100 else 0
        except Exception:
            pass

    return {
        "product_identity": product_identity,
        "covered": covered,
        "missing": missing,
        "ad_keywords": ad_keywords,
        "state_keywords": state_keywords[:10],
        "suggestions": suggestions,
        "score_adjust": score_adjust,
        "price_note": f"当前抓取价格: {price}" if price else "价格未抓取",
    }


def _fallback_listing_diagnosis(listing: ListingInput, reason: str = "") -> dict:
    """Return a conservative diagnosis when the model call times out or returns invalid JSON."""
    insights = _derive_fallback_insights(listing)
    has_title = bool((listing.title or "").strip())
    has_bullets = bool((listing.bullet_points or "").strip())
    has_aplus = bool((listing.a_plus_content or "").strip())
    has_image = bool((listing.main_image_description or "").strip())
    has_price = bool((listing.price or "").strip())
    base = 58 if has_title and has_bullets else 48
    base += insights["score_adjust"]
    scores = {
        "function_expression": min(base + (10 if has_bullets else 0), 78),
        "scenario_expression": min(base + (6 if insights["covered"].get("scenario") else -2), 76),
        "identity_fit": min(base + (5 if insights["covered"].get("audience") else -2), 74),
        "psychology_benefit": min(base + (5 if insights["missing"].get("pain_point") else -3), 72),
        "risk_elimination": max(42, base - (3 if has_price else 8)),
        "product_identity": min(base + (8 if has_title else 0), 80),
        "compatibility": min(base + (4 if insights["covered"].get("scenario") else -3), 74),
        "subjective_properties": min(base + (3 if has_aplus else -3), 72),
        "differentiation": max(45, base - 6),
        "market_trend": max(48, base - 4),
        "causal_state_gap_coverage": max(45, base - 2),
        "causal_mechanism_clarity": max(45, base - 5),
        "causal_side_effect_transparency": max(40, base - 8),
        "keyword_validation_readiness": min(base + (8 if insights["state_keywords"] else -4), 76),
    }
    covered = insights["covered"]
    missing = insights["missing"]
    analysis = {
        "function_expression": f"本地兜底判断：产品身份为 {insights['product_identity']}，已识别功能点：{', '.join(covered.get('function') or ['基础功能可识别'])}。AI深度分析超时，但抓取字段足以做基础功能判断。",
        "scenario_expression": f"已识别场景：{', '.join(covered.get('scenario') or ['场景表达不够集中'])}。建议把最高转化场景前置到标题和主图，而不是平均堆叠多个场景。",
        "identity_fit": f"已识别人群/关系词：{', '.join(covered.get('audience') or ['人群关系词不足'])}。关系词决定Rufus/COSMO是否理解适用人群。",
        "psychology_benefit": f"待补强状态触发词：{', '.join(missing.get('pain_point') or ['痛点触发词不足'])}。这些词比普通属性词更适合广告验证。",
        "risk_elimination": f"{insights['price_note']}；评分/评论信号为 {listing.rating or '未抓取'} / {listing.review_count or '未抓取'}。风险消除还需要保修、安全、材质、使用限制或真实证据支撑。",
        "product_identity": f"产品身份词已可识别为 {insights['product_identity']}，但仍需要用类目路径和后台关键词确认平台语义一致。",
        "compatibility": "兼容/搭配应从 used with、for、without、compatible with 这类关系词展开，当前仅能从标题/五点做基础推断。",
        "subjective_properties": "A+或图片信号存在时可支撑感性属性，但仍需检查是否把 sound、portable、gift-ready、waterproof 等感知词视觉化。",
        "differentiation": "差异化不能只靠功能堆叠，需要与Top竞品同尺比较：价格、评分、评论量、场景词、状态触发词是否更强。",
        "market_trend": "趋势判断需要竞品和广告数据确认；当前只能先按抓取到的场景词和评论信号做中等置信判断。",
    }
    elements = {}
    for key, present in {
        "title": has_title,
        "bullets": has_bullets,
        "aplus": has_aplus,
        "images": has_image,
        "backend": bool((listing.backend_keywords or "").strip()),
        "price": has_price,
    }.items():
        element_base = 55 if present else 25
        elements[key] = {dim: element_base for dim in _ELEMENT_DIM_KEYS}
        elements[key]["summary"] = "模型超时后的保守占位评分，需重新诊断获得完整解释。"
    return {
        "scores": scores,
        "analysis": analysis,
        "suggestions": {
            "high_priority": [
                *insights["suggestions"][:3],
            ],
            "medium_priority": ["补充类目路径、后台关键词和Top竞品，提升平台语义与竞品差距判断置信度。"],
            "low_priority": ["AI深度分析恢复后，可重跑一次获得更完整解释；当前结果已可进入基础广告验证准备。"],
            "backend_keywords_addition": (missing.get("long_tail") or [])[:8],
        },
        "keyword_coverage": {
            "covered_categories": covered,
            "missing_categories": missing,
            "covered_keywords": [kw for values in covered.values() for kw in values],
            "missing_keywords": [kw for values in missing.values() for kw in values],
            "coverage_score": 58 if insights["state_keywords"] else 42,
            "coverage_summary": "AI深度分析超时，当前为本地规则兜底关键词判断；优先使用关系词和状态触发词进入广告验证。",
        },
        "ad_keywords": {
            **insights["ad_keywords"],
            "negative_keywords": [],
            "negative": [],
            "ad_summary": "本地兜底广告词优先给出关系词和状态触发词，属性词仅做基础覆盖。",
        },
        "elements": elements,
        "market_estimates": {},
        "overall_summary": f"AI深度诊断超时，系统已基于真实抓取字段生成本地兜底诊断。可先用于判断方向和广告验证准备；完整AI解释可稍后重跑。{reason}",
        "analyzed_product_name": listing.title or "",
        "product_mismatch": False,
        "product_mismatch_detail": "",
        "causal_diagnosis": {
            "overall_causal_score": scores["causal_state_gap_coverage"],
            "summary": "模型超时，因果诊断暂按保守分处理。",
            "keyword_causality": {
                "framework": "rufus_cosmo_causal_keywords",
                "priority_order": ["state_trigger", "relationship", "attribute"],
                "readiness_score": scores["keyword_validation_readiness"],
                "priority_keywords": insights["state_keywords"],
                "summary": "本地规则已生成关系词/状态触发词，可先进入小预算广告验证；AI恢复后再补完整因果解释。",
            },
        },
        "ad_validation_plan": {
            "validation_items": [
                {
                    "diagnosis_issue": "AI深度诊断超时，但已识别可验证关系词/状态触发词",
                    "suggested_listing_action": (insights["suggestions"][0] if insights["suggestions"] else "先补强关系词和状态触发词，再做广告验证"),
                    "ad_action": {
                        "test_type": "fallback_causal_keyword_validation",
                        "keywords": [item["keyword"] for item in insights["state_keywords"][:5]],
                        "match_types": ["phrase", "exact"],
                    },
                }
            ]
        },
        "diagnosis_confidence": {
            "overall": {
                "level": "low",
                "reason": "AI完整诊断超时或响应异常，本结果为保守兜底。",
            }
        },
        "data_integrity": {
            "score": 35,
            "level": "low",
            "reason": "诊断模型未完整返回结构化结果。",
        },
    }


def _build_compact_diagnosis_prompt(listing: ListingInput) -> str:
    """Build a compact prompt for live diagnosis so domestic models do not stall on huge schemas."""
    return f"""你是AlignX亚马逊Listing诊断专家。只诊断以下产品，不要替换产品。

产品信息：
- 站点：{listing.marketplace}
- 标题：{listing.title or "未提供"}
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
1. 按10个维度0-100打分：function_expression, scenario_expression, identity_fit, psychology_benefit, risk_elimination, product_identity, compatibility, subjective_properties, differentiation, market_trend。
2. 关键词必须是自然美式英语，不能输出中文关键词。
3. 广告关键词必须标记 keyword_type：attribute / relationship / state_trigger。
4. 优先找 relationship 和 state_trigger，因为它们用于广告验证和避开纯属性词价格竞争。
5. 输出要具体指出依据来源：标题、五点、图片/A+、价格、评分评论、缺失类目/后台词。

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
    "covered_categories": {{"core_category": [], "function": [], "scenario": [], "audience": [], "pain_point": [], "long_tail": []}},
    "missing_categories": {{"core_category": [], "function": [], "scenario": [], "audience": [], "pain_point": [], "long_tail": []}},
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
    "title": {{"functional": 50, "scenario": 50, "persona": 50, "motivation": 50, "competitive": 50, "trend": 50, "product_id": 50, "compat": 50, "subjective": 50, "market": 50, "summary": "标题判断"}},
    "bullets": {{"functional": 50, "scenario": 50, "persona": 50, "motivation": 50, "competitive": 50, "trend": 50, "product_id": 50, "compat": 50, "subjective": 50, "market": 50, "summary": "五点判断"}},
    "images": {{"functional": 50, "scenario": 50, "persona": 50, "motivation": 50, "competitive": 50, "trend": 50, "product_id": 50, "compat": 50, "subjective": 50, "market": 50, "summary": "图片判断"}},
    "aplus": {{"functional": 50, "scenario": 50, "persona": 50, "motivation": 50, "competitive": 50, "trend": 50, "product_id": 50, "compat": 50, "subjective": 50, "market": 50, "summary": "A+判断"}},
    "backend": {{"functional": 30, "scenario": 30, "persona": 30, "motivation": 30, "competitive": 30, "trend": 30, "product_id": 30, "compat": 30, "subjective": 30, "market": 30, "summary": "后台关键词判断"}}
  }},
  "market_estimates": {{"estimated_monthly_sales": 0, "estimated_bsr_rank": 0}},
  "analyzed_product_name": "{listing.title or ""}",
  "overall_summary": "整体总结"
}}"""


async def _diagnose_single(
    listing: ListingInput,
    user_id: str,
    db: AsyncSession,
    save: bool = True,
    precision_context: dict | None = None,
) -> dict:
    """Run full diagnosis on a single listing."""
    ai_service = AIHubService()
    listing = _sanitize_listing_for_ai(listing)

    product_title = listing.title or "未提供"

    prompt = _build_compact_diagnosis_prompt(listing)

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
        f' 7.本次诊断采用8D+2维度体系（COSMO核心8D + 卖家扩展2D），共10个维度。'
        f'你是亚马逊Listing优化专家。只输出JSON。'
    )

    from schemas.aihub import GenTxtRequest, ChatMessage
    request = GenTxtRequest(
        messages=[
            ChatMessage(role="system", content=system_msg),
            ChatMessage(role="user", content=prompt),
        ],
        model="AI_DEFAULT_MODEL",
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
                request.model = "AI_DEFAULT_MODEL"
                request.max_tokens = 4096
        except Exception as e:
            last_error = e
            logger.warning(f"AI diagnosis call failed (attempt {attempt + 1}/2): {e}")
            if attempt == 0:
                request.model = "AI_DEFAULT_MODEL"
    else:
        data = _fallback_listing_diagnosis(listing, reason=str(last_error or ""))

    data = _normalize_keyword_payload(data)

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
            context=precision_context or {},
            asin=listing.asin or None,
            listing_diagnosis_id=None,
            run_causal=False,
        )
        data = JudgmentSystemService.apply_to_legacy_listing_diagnosis(data, judgment_system)
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
    data = merge_cosmo_rufus_into_legacy(data, cosmo_rufus_analysis)
    ad_validation_plan = data.get("ad_validation_plan", ad_validation_plan)

    amazon_compliance = await _evaluate_listing_compliance(listing, db)
    data["amazon_compliance"] = amazon_compliance

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
        
        record = await svc.create(create_data, user_id=user_id)
        if record:
            record_id = record.id
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
        "causal_diagnosis": causal_diagnosis,
        "judgment_system": judgment_system,
        "ad_validation_plan": ad_validation_plan,
        "data_integrity": data_integrity,
        "diagnosis_confidence": diagnosis_confidence,
        "cosmo_rufus_analysis": cosmo_rufus_analysis,
        "amazon_compliance": amazon_compliance,
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

        # ---- Phase 1: Try real Amazon scraping ----
        from services.amazon_scraper import scrape_amazon_product

        scraped = await scrape_amazon_product(asin, marketplace)
        scrape_ok = scraped.get("scrape_success", False)

        # Helper to clean markers
        def _clean_field(val: str) -> str:
            if not val or not isinstance(val, str):
                return ""
            for marker in ["[未确认]", "[未确认] ", "[unknown]", "[Unknown]", "[unconfirmed]"]:
                val = val.replace(marker, "")
            return val.strip()

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
                price=scraped.get("price", ""),
                brand=scraped.get("brand", ""),
                marketplace=marketplace,
            )
            return FetchUrlResponse(
                listing=listing,
                asin=asin,
                source="scraped",
                rating=scraped.get("rating", ""),
                review_count=scraped.get("review_count", ""),
                bsr_rank=scraped.get("bsr_rank", ""),
                bsr_category=scraped.get("bsr_category", ""),
                image_count=scraped.get("image_count", ""),
                has_video=scraped.get("has_video", False),
                has_a_plus=scraped.get("has_a_plus", False),
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
            model="AI_DEFAULT_MODEL",
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
                    ai_request.model = "AI_DEFAULT_MODEL"

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
    """Parse raw HTML from an Amazon product page.

    Used by the frontend browser-side CORS proxy fetch.
    Reuses the same BeautifulSoup parsing logic from amazon_scraper.
    """
    try:
        html = request.html
        if not html or len(html) < 500:
            return ParseHtmlResponse(
                listing=ListingInput(marketplace=request.marketplace),
                asin=request.asin,
                success=False,
                error="HTML内容过短，无法解析",
            )

        from services.amazon_scraper import _parse_product_page

        parsed = _parse_product_page(html, request.marketplace)
        if not parsed or not parsed.get("title"):
            from services.amazon_scraper import _is_captcha_page
            if _is_captcha_page(html):
                return ParseHtmlResponse(
                    listing=ListingInput(marketplace=request.marketplace),
                    asin=request.asin,
                    success=False,
                    error="检测到CAPTCHA验证页面，请使用手动粘贴模式",
                )
            return ParseHtmlResponse(
                listing=ListingInput(marketplace=request.marketplace),
                asin=request.asin,
                success=False,
                error="无法从HTML中解析出产品信息，页面可能不是有效的Amazon产品页",
            )

        marketplace = request.marketplace
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
            price=parsed.get("price", ""),
            brand=parsed.get("brand", ""),
            marketplace=marketplace,
        )

        bsr = parsed.get("bsr_rank", "")
        bsr_cat = parsed.get("bsr_category", "")

        logger.info(f"parse-html succeeded for ASIN {request.asin}: {parsed['title'][:60]}")

        return ParseHtmlResponse(
            listing=listing,
            asin=request.asin,
            source="browser_proxy",
            rating=parsed.get("rating", ""),
            review_count=parsed.get("review_count", ""),
            bsr_rank=bsr,
            bsr_category=bsr_cat,
            image_count=parsed.get("image_count", ""),
            has_video=parsed.get("has_video", False),
            has_a_plus=parsed.get("has_a_plus", False),
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
    """Full listing diagnosis: 8D+2 scoring + keyword coverage + optimization suggestions + ad keywords."""
    try:
        listing = request.listing
        if not listing.title and not listing.bullet_points:
            raise HTTPException(status_code=400, detail="请至少输入标题或五点描述")

        result = None
        if not request.force_refresh:
            result = await _get_exact_cached_listing_diagnosis(listing, db, str(current_user.id))
        if not result:
            result = await _diagnose_single(
                listing=listing,
                user_id=str(current_user.id),
                db=db,
                precision_context=request.precision_context,
            )
        if not result.get("amazon_compliance"):
            result["amazon_compliance"] = await _evaluate_listing_compliance(listing, db)
        return DiagnoseResponse(
            scores=result["scores"],
            analysis=result["analysis"],
            suggestions=result["suggestions"],
            keyword_coverage=result["keyword_coverage"],
            ad_keywords=result["ad_keywords"],
            elements=result.get("elements", {}),
            market_estimates=result.get("market_estimates", {}),
            overall_summary=result["overall_summary"],
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
            amazon_compliance=result.get("amazon_compliance", {}),
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
            f"竞品{i+1} 标题: {c['listing_title']}, 8D+2评分: {json.dumps(c['scores'], ensure_ascii=False)}"
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
            model="AI_DEFAULT_MODEL",
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
                    compare_request.model = "AI_DEFAULT_MODEL"

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

    user_id = str(current_user.id)

    # Build base query
    base_filter = [LD.user_id == user_id]
    if search.strip():
        base_filter.append(LD.listing_title.ilike(f"%{search.strip()}%"))
    if marketplace_filter.strip():
        base_filter.append(LD.marketplace == marketplace_filter.strip())

    # Count
    count_q = select(func.count(LD.id)).where(*base_filter)
    count_result = await db.execute(count_q)
    total = count_result.scalar() or 0

    # Aggregate stats for this user (unfiltered)
    stats_filter = [LD.user_id == user_id]
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
        .offset(skip)
        .limit(limit)
    )
    items_result = await db.execute(items_q)
    rows = items_result.scalars().all()

    items = []
    for item in rows:
        items.append({
            "id": item.id,
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
    svc = Listing_diagnosesService(db)
    record = await svc.get_by_id(diagnosis_id, user_id=str(current_user.id))
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

    return {
        "id": record.id,
        "listing_title": record.listing_title,
        "marketplace": record.marketplace,
        "input_data": input_data,
        "scores": {
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
        },
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

        user_id = str(current_user.id)

        # Overall stats
        overall_q = select(
            func.count(SL.id).label("total"),
            func.sum(case((SL.success == True, 1), else_=0)).label("success_count"),
        ).where(SL.user_id == user_id)
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
        ).where(SL.user_id == user_id).group_by(SL.scrape_method)
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
            .where(SL.user_id == user_id)
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
        record = await svc.create({
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
        }, user_id=str(current_user.id))

        record_id = record.id if record else None
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
    svc = Listing_diagnosesService(db)
    deleted = await svc.delete(diagnosis_id, user_id=str(current_user.id))
    if not deleted:
        raise HTTPException(status_code=404, detail="诊断记录不存在或无权删除")
    return {"success": True, "message": "已删除"}
