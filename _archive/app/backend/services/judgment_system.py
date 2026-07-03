"""
Unified AlignX judgment system backend.

This is the algorithm foundation that consolidates four previously separate
capabilities:
1. review semantic demand judgment
2. COSMO / Rufus semantic judgment
3. causal conversion judgment
4. precision and confidence judgment

Routers and product modules should consume slices of this unified result instead
of re-implementing their own confidence, alignment, or causal summaries.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from services.causal_diagnosis import CausalDiagnosisService
from services.human_nature_model import build_human_nature_graph
from services.precision_confidence import assess_listing_diagnosis_input

logger = logging.getLogger(__name__)


COSMO_SCORE_KEYS = [
    "function_expression",
    "scenario_expression",
    "identity_fit",
    "psychology_benefit",
    "risk_elimination",
    "product_identity",
    "compatibility",
    "subjective_properties",
    "differentiation",
    "market_trend",
]

USER_INTENT_DIMENSIONS = [
    "function_expression",
    "scenario_expression",
    "identity_fit",
    "psychology_benefit",
    "risk_elimination",
    "subjective_properties",
]

PLATFORM_MATCHING_DIMENSIONS = [
    "product_identity",
    "compatibility",
    "scenario_expression",
    "function_expression",
    "market_trend",
]

LISTING_CONVERSION_DIMENSIONS = [
    "function_expression",
    "scenario_expression",
    "risk_elimination",
    "differentiation",
    "subjective_properties",
]

ADVERTISING_VALIDATION_DIMENSIONS = [
    "function_expression",
    "scenario_expression",
    "product_identity",
    "compatibility",
    "differentiation",
    "market_trend",
]

REVIEW_DEMAND_KEYS = [
    "core_category",
    "function",
    "scenario",
    "audience",
    "pain_point",
    "long_tail",
]

AD_VALIDATION_KEYWORD_MAP = {
    "core_category": ["{term}", "{term} amazon", "best {term}"],
    "function": ["{term}", "{term} solution", "{term} for home"],
    "scenario": ["{term}", "{term} for {scenario}", "{term} use case"],
    "audience": ["{term} for {audience}", "{audience} {term}"],
    "pain_point": ["{term} remover", "{term} solution", "{term} fix"],
    "long_tail": ["{term}", "{term} alternative", "{term} reviews"],
}


def _keyword_type(keyword: str) -> str:
    kw = keyword.lower()
    state_terms = ("odor", "smell", "ammonia", "pain", "relief", "anxiety", "safe", "comfort", "leak", "tracking", "mess", "stress", "sleep", "noise", "spill", "dust")
    relation_terms = ("for ", "with ", "without ", "under ", "near ", "compatible", "replacement", "indoor", "outdoor", "apartment", "bedroom", "travel", "kids", "women", "men", "cats", "dogs", "office")
    if any(term in kw for term in state_terms):
        return "state_trigger"
    if any(term in kw for term in relation_terms):
        return "relationship"
    return "attribute"


def _clean_ad_keyword(value: Any) -> str:
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
    replacements = {
        "odour": "odor",
        "colour": "color",
        "flavour": "flavor",
        "favourite": "favorite",
        "organiser": "organizer",
        "travelling": "traveling",
        "jewellery": "jewelry",
    }
    for british, american in replacements.items():
        text = re.sub(rf"\b{british}\b", american, text)
    text = re.sub(r"[^a-z0-9 +&/\\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_/")
    normalized = " ".join(text.split()[:8])
    return normalized if re.search(r"[a-z]", normalized) else ""


def _avg(values: list[float]) -> float:
    clean = [float(v) for v in values if isinstance(v, (int, float))]
    if not clean:
        return 0.0
    return round(sum(clean) / len(clean), 2)


def _score_band(score: float) -> str:
    if score >= 80:
        return "强"
    if score >= 65:
        return "可用"
    if score >= 50:
        return "偏弱"
    return "弱"


def _decision_confidence(score: float, precision_score: float) -> int:
    return int(max(30, min(92, round(score * 0.75 + precision_score * 0.25))))


def _dimension_score(scores: dict[str, Any], keys: list[str]) -> float:
    return _avg([scores.get(key, 0) for key in keys])


def _parse_metric(value: Any) -> int:
    if value is None:
        return 0
    match = re.search(r"\d+", str(value).replace(",", ""))
    return int(match.group(0)) if match else 0


def _has_price(value: Any) -> bool:
    text = str(value or "").strip()
    if not text or text in {"-", "—", "N/A", "n/a", "NA", "待确认", "未提供", "未知"}:
        return False
    return bool(re.search(r"\d", text))


def _bullet_count(value: Any) -> int:
    return len([item for item in re.split(r"[\n;；]+", str(value or "")) if item.strip()])


def _is_new_launch(listing: Any, data: dict[str, Any] | None = None) -> bool:
    data = data or {}
    diagnosis_mode = str(data.get("diagnosis_mode") or "").strip().lower()
    if diagnosis_mode in {"new_launch", "new_launch_readiness", "prelaunch", "prelaunch_readiness"}:
        return True
    if diagnosis_mode in {"mature_listing", "listing_conversion", "listing_conversion_readiness"}:
        return False
    cap_meta = data.get("market_reality_caps") if isinstance(data.get("market_reality_caps"), dict) else {}
    if cap_meta.get("is_new_launch") is True:
        return True
    no_price = not _has_price(getattr(listing, "price", ""))
    no_reviews = _parse_metric(getattr(listing, "review_count", None)) == 0
    no_sales = _parse_metric(getattr(listing, "bsr_rank", None)) == 0
    return no_price and no_reviews and no_sales


def _new_launch_core_gaps(listing: Any, scores: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    if len(str(getattr(listing, "title", "") or "").strip()) < 50:
        gaps.append("标题身份不足")
    if _bullet_count(getattr(listing, "bullet_points", "")) < 3:
        gaps.append("五点购买理由不足")
    image_count = _parse_metric(getattr(listing, "image_count", None))
    has_visual_signal = bool(
        image_count > 0
        or str(getattr(listing, "main_image_description", "") or "").strip()
        or getattr(listing, "has_a_plus", False)
        or getattr(listing, "has_video", False)
    )
    if not has_visual_signal:
        gaps.append("主图/副图证据不足")
    if float(scores.get("scenario_expression") or 0) < 60:
        gaps.append("场景问题词不足")
    if float(scores.get("risk_elimination") or 0) < 55:
        gaps.append("基础风险消除不足")
    return gaps


def _count_nested_keywords(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    total = 0
    for items in value.values():
        if isinstance(items, list):
            total += len([item for item in items if str(item).strip()])
    return total


def _collect_ad_keyword_items(diagnosis_data: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    ad_keywords = diagnosis_data.get("ad_keywords") or {}
    items: list[dict[str, Any]] = []
    if not isinstance(ad_keywords, dict):
        return items
    for group in ("high_conversion", "long_tail", "traffic"):
        for raw in ad_keywords.get(group) or []:
            if isinstance(raw, dict):
                keyword = _clean_ad_keyword(raw.get("keyword"))
                keyword_type = raw.get("keyword_type") or _keyword_type(keyword)
                priority = raw.get("priority") or ("P0" if keyword_type != "attribute" else "P2")
            else:
                keyword = _clean_ad_keyword(raw)
                keyword_type = _keyword_type(keyword)
                priority = "P0" if keyword_type != "attribute" else "P2"
            if not keyword:
                continue
            items.append({
                "keyword": keyword,
                "keyword_type": keyword_type if keyword_type in {"state_trigger", "relationship", "attribute"} else _keyword_type(keyword),
                "priority": priority,
                "source": "listing_diagnosis_ad_keywords",
            })
            if len(items) >= limit:
                return items
    return items


def _flatten_missing_terms(review_semantics: dict[str, Any], limit: int = 8) -> list[dict[str, str]]:
    terms: list[dict[str, str]] = []
    for item in review_semantics.get("demand_items", []) or []:
        dimension = item.get("dimension", "demand")
        for raw in item.get("missing", []) or []:
            term = str(raw).strip()
            if term:
                terms.append({"dimension": dimension, "term": term})
            if len(terms) >= limit:
                return terms
    return terms


class JudgmentSystemService:
    """Single backend orchestration layer for all judgment signals."""

    version = "judgment-system-v4"

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db

    def build_review_semantics(self, diagnosis_data: dict[str, Any]) -> dict[str, Any]:
        """Normalize review-demand signals from keyword coverage and diagnosis output.

        This does not pretend to be raw review mining when reviews are absent. It
        marks the source and confidence separately so downstream UI can avoid
        overclaiming.
        """
        keyword_coverage = diagnosis_data.get("keyword_coverage") or {}
        covered = keyword_coverage.get("covered_categories") or {}
        missing = keyword_coverage.get("missing_categories") or {}
        covered_count = _count_nested_keywords(covered)
        missing_count = _count_nested_keywords(missing)
        coverage_score = keyword_coverage.get("coverage_score")
        if not isinstance(coverage_score, (int, float)):
            denom = max(covered_count + missing_count, 1)
            coverage_score = round(covered_count * 100 / denom, 2)

        demand_items = []
        for key in REVIEW_DEMAND_KEYS:
            demand_items.append({
                "dimension": key,
                "covered": covered.get(key, []),
                "missing": missing.get(key, []),
                "covered_count": len(covered.get(key, []) or []),
                "missing_count": len(missing.get(key, []) or []),
            })

        return {
            "name": "review_semantic_demand",
            "source": "keyword_coverage_normalized",
            "score": round(float(coverage_score or 0), 2),
            "covered_count": covered_count,
            "missing_count": missing_count,
            "demand_items": demand_items,
            "summary": keyword_coverage.get("coverage_summary", ""),
        }

    def build_cosmo_semantics(self, diagnosis_data: dict[str, Any]) -> dict[str, Any]:
        """Normalize COSMO semantics from Listing diagnosis scores/elements."""
        scores = diagnosis_data.get("scores") or {}
        analysis = diagnosis_data.get("analysis") or {}
        elements = diagnosis_data.get("elements") or {}
        dimension_scores = {
            key: round(float(scores.get(key, 0) or 0), 2)
            for key in COSMO_SCORE_KEYS
        }
        return {
            "name": "cosmo_semantic_alignment",
            "source": "listing_8d_2d_normalized",
            "score": _avg(list(dimension_scores.values())),
            "dimension_scores": dimension_scores,
            "dimension_analysis": {key: analysis.get(key, "") for key in COSMO_SCORE_KEYS},
            "element_alignment": elements,
        }

    async def build_causal_judgment(
        self,
        *,
        title: str,
        bullets: str,
        description: str,
        asin: str | None = None,
        marketplace: str = "US",
        user_id: str = "",
        listing_diagnosis_id: int | None = None,
        existing_causal_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run or normalize causal judgment through the shared causal service."""
        if existing_causal_result:
            causal_result = existing_causal_result
        elif self.db is not None:
            try:
                causal_result = await asyncio.wait_for(
                    CausalDiagnosisService(self.db).diagnose_listing_causality(
                        title=title or "",
                        bullets=bullets or "",
                        description=description or "",
                        listing_diagnosis_id=listing_diagnosis_id,
                        asin=asin,
                        marketplace=marketplace or "US",
                        user_id=user_id,
                    ),
                    timeout=55,
                )
            except Exception as exc:
                logger.warning(f"Causal judgment timed out or failed; using conservative fallback: {exc}")
                causal_result = {
                    "scores": {
                        "state_gap_coverage": 45,
                        "mechanism_clarity": 45,
                        "side_effect_transparency": 40,
                        "keyword_validation_readiness": 35,
                        "overall": 42,
                    },
                    "summary": "因果判断超时，已使用保守兜底；建议稍后重跑完整因果分析。",
                    "keyword_causality": {
                        "framework": "rufus_cosmo_causal_keywords",
                        "priority_order": ["state_trigger", "relationship", "attribute"],
                        "readiness_score": 35,
                        "priority_keywords": [],
                        "summary": "因果关键词层暂未完整生成。",
                    },
                }
        else:
            causal_result = {}

        scores = causal_result.get("scores") or {}
        return {
            "name": "causal_conversion_alignment",
            "source": "causal_diagnosis_service",
            "score": round(float(scores.get("overall", 0) or 0), 2),
            "dimension_scores": {
                "state_gap_coverage": round(float(scores.get("state_gap_coverage", 0) or 0), 2),
                "mechanism_clarity": round(float(scores.get("mechanism_clarity", 0) or 0), 2),
                "side_effect_transparency": round(float(scores.get("side_effect_transparency", 0) or 0), 2),
                "keyword_validation_readiness": round(float(scores.get("keyword_validation_readiness", 0) or 0), 2),
            },
            "raw": causal_result,
        }

    def build_precision_judgment(self, listing: Any, context: dict[str, Any] | None = None) -> dict[str, Any]:
        precision = assess_listing_diagnosis_input(listing, context or {})
        return {
            "name": "precision_confidence",
            "source": "deterministic_input_rules",
            "score": precision.get("score", 0),
            "level": precision.get("level", "low"),
            "label": precision.get("label", "低"),
            "data_integrity": precision,
            "confidence_by_alignment": precision.get("conclusion_confidence", {}),
        }

    def build_human_nature_layer(self, listing: Any, diagnosis_data: dict[str, Any]) -> dict[str, Any]:
        source = {
            "title": getattr(listing, "title", "") or diagnosis_data.get("title", ""),
            "keywords": diagnosis_data.get("keywords") or diagnosis_data.get("backend_keywords") or "",
            "bullet_points": getattr(listing, "bullet_points", "") or diagnosis_data.get("bullet_points", ""),
            "description": getattr(listing, "description", "") or diagnosis_data.get("description", ""),
            "a_plus_content": getattr(listing, "a_plus_content", "") or diagnosis_data.get("a_plus_content", ""),
            "category": getattr(listing, "category", "") or diagnosis_data.get("category", ""),
            "brand": getattr(listing, "brand", "") or diagnosis_data.get("brand", ""),
        }
        return build_human_nature_graph(source)

    def build_rule_based_causal_judgment(self, listing: Any, diagnosis_data: dict[str, Any]) -> dict[str, Any]:
        """Build causal conversion judgment from scraped fields and 10-dimension diagnosis output without a second AI call.

        Listing diagnosis already contains product semantics, keyword coverage, ad keywords and
        input completeness. This deterministic layer keeps the foreground request fast and turns
        the first diagnosis into verifiable causal hypotheses.
        """
        scores = diagnosis_data.get("scores") or {}
        coverage = diagnosis_data.get("keyword_coverage") or {}
        covered = coverage.get("covered_categories") or {}
        missing = coverage.get("missing_categories") or {}
        priority_keywords = _collect_ad_keyword_items(diagnosis_data)
        state_or_relation = [item for item in priority_keywords if item["keyword_type"] in {"state_trigger", "relationship"}]

        semantic_base = _avg([
            scores.get("scenario_expression", 0),
            scores.get("psychology_benefit", 0),
            scores.get("risk_elimination", 0),
            scores.get("product_identity", 0),
            scores.get("compatibility", 0),
        ])
        state_gap_coverage = min(85, max(35, semantic_base + (8 if state_or_relation else -8)))
        mechanism_clarity = min(85, max(35, _avg([
            scores.get("function_expression", 0),
            scores.get("risk_elimination", 0),
            scores.get("subjective_properties", 0),
        ])))
        side_effect_transparency = min(80, max(30, _avg([
            scores.get("risk_elimination", 0),
            72 if getattr(listing, "review_count", None) else 45,
            68 if getattr(listing, "price", None) else 42,
        ])))
        readiness = min(88, max(30, (coverage.get("coverage_score") or 45) + (10 if state_or_relation else -5)))
        overall = _avg([state_gap_coverage, mechanism_clarity, side_effect_transparency, readiness])

        missing_terms = _flatten_missing_terms({"demand_items": [
            {"dimension": key, "missing": value} for key, value in missing.items()
        ]})
        raw = {
            "scores": {
                "state_gap_coverage": round(state_gap_coverage, 2),
                "mechanism_clarity": round(mechanism_clarity, 2),
                "side_effect_transparency": round(side_effect_transparency, 2),
                "keyword_validation_readiness": round(readiness, 2),
                "overall": round(overall, 2),
            },
            "summary": "后台标准基于抓取字段、10维诊断、关键词覆盖和广告关键词直接生成因果判断，未阻塞等待第二轮AI。",
            "keyword_causality": {
                "framework": "rufus_cosmo_causal_keywords",
                "priority_order": ["state_trigger", "relationship", "attribute"],
                "readiness_score": round(readiness, 2),
                "priority_keywords": priority_keywords,
                "summary": "广告验证优先使用关系词和状态触发词；属性词只做基础品类覆盖。",
            },
            "state_gaps": {
                "covered_gaps": [
                    {"dimension": key, "terms": values}
                    for key, values in covered.items()
                    if values
                ],
                "missing_gaps": [
                    {
                        "gap_name": item["term"],
                        "dimension": item["dimension"],
                        "keyword_type": _keyword_type(item["term"]),
                    }
                    for item in missing_terms
                ],
            },
            "source": "deterministic_backend_judgment",
        }
        return {
            "name": "causal_conversion_alignment",
            "source": "deterministic_backend_judgment",
            "score": round(overall, 2),
            "dimension_scores": {
                "state_gap_coverage": round(state_gap_coverage, 2),
                "mechanism_clarity": round(mechanism_clarity, 2),
                "side_effect_transparency": round(side_effect_transparency, 2),
                "keyword_validation_readiness": round(readiness, 2),
            },
            "raw": raw,
        }

    def build_ad_validation_plan(
        self,
        *,
        review_semantics: dict[str, Any],
        cosmo_semantics: dict[str, Any],
        causal: dict[str, Any],
        precision: dict[str, Any],
    ) -> dict[str, Any]:
        """Turn diagnosis conclusions into small-budget ad validation actions."""
        missing_terms = _flatten_missing_terms(review_semantics)
        raw_causal = causal.get("raw") or {}
        causal_suggestions = (
            raw_causal.get("causal_mechanisms", {}).get("improvement_suggestions", [])
            or raw_causal.get("side_effects", {}).get("improvement_suggestions", [])
            or []
        )
        causal_keyword_items = (
            raw_causal.get("keyword_causality", {}).get("priority_keywords", [])
            if isinstance(raw_causal.get("keyword_causality"), dict)
            else []
        )

        validation_items = []
        for idx, item in enumerate(causal_keyword_items[:5], 1):
            keyword = _clean_ad_keyword(item.get("keyword") if isinstance(item, dict) else item)
            if not keyword:
                continue
            keyword_type = item.get("keyword_type") if isinstance(item, dict) else _keyword_type(keyword)
            if keyword_type not in {"state_trigger", "relationship", "attribute"}:
                keyword_type = _keyword_type(keyword)
            validation_items.append({
                "id": f"ad-test-causal-keyword-{idx}",
                "hypothesis": f"用「{keyword}」验证Listing是否承接了用户状态或使用关系",
                "diagnosis_issue": f"优先验证关键词待验证: {keyword}",
                "suggested_listing_action": "先在标题、五点或图片文案中补强同一状态/关系表达，再用广告验证。",
                "keyword_type": keyword_type,
                "ad_action": {
                    "test_type": "causal_keyword_validation",
                    "campaign_note": "优先单独小预算测试关系词和状态触发词；属性词只做基础覆盖，不作为核心胜负判断。",
                    "keywords": [keyword],
                    "match_types": ["phrase", "exact"],
                },
                "success_metrics": ["CTR", "CVR", "CPC", "ACOS", "search_term_precision"],
                "decision_rules": [
                    "CTR提升: Amazon识别和首屏表达更容易被识别",
                    "CVR提升: 状态承诺和详情页承接成立",
                    "CTR升CVR不升: 关键词切口成立，但价格、评价或机制证据不足",
                    "CTR不升: 状态触发词或关系词仍未击中真实搜索意图",
                ],
            })

        for idx, item in enumerate(missing_terms[:5], 1):
            term = item["term"]
            dimension = item["dimension"]
            templates = AD_VALIDATION_KEYWORD_MAP.get(dimension, ["{term}"])
            keywords = [
                _clean_ad_keyword(tpl.format(term=term, scenario=term, audience=term).strip())
                for tpl in templates[:3]
            ]
            keywords = [keyword for keyword in keywords if keyword]
            if not keywords:
                continue
            validation_items.append({
                "id": f"ad-test-{idx}",
                "hypothesis": f"Listing补强「{term}」后，对应搜索词点击和转化应提升",
                "diagnosis_issue": f"{dimension}需求未充分覆盖: {term}",
                "suggested_listing_action": f"在标题/五点/图片文案中补充「{term}」的清晰表达",
                "keyword_type": _keyword_type(keywords[0]),
                "ad_action": {
                    "test_type": "single_theme_keyword_test",
                    "campaign_note": "建议单独小预算验证，避免混入原有广告组噪声",
                    "keywords": keywords,
                    "match_types": ["phrase", "exact"],
                },
                "success_metrics": ["CTR", "CVR", "CPC", "ACOS", "search_term_precision"],
                "decision_rules": [
                    "CTR提升: 点击表达更准",
                    "CVR提升: 详情页承接更准",
                    "CTR提升但CVR不升: 主图/标题吸引有效，但价格、评价或详情页信任不足",
                    "CTR不升: 关键词选择或首屏表达仍需调整",
                ],
            })

        if not validation_items and causal_suggestions:
            validation_items.append({
                "id": "ad-test-causal-1",
                "hypothesis": "因果承诺表达补强后，广告点击后的转化效率应提升",
                "diagnosis_issue": "因果链条表达不足",
                "suggested_listing_action": str(causal_suggestions[0]),
                "ad_action": {
                    "test_type": "before_after_listing_test",
                    "campaign_note": "保持原广告预算和关键词稳定，对比修改前后7天数据",
                    "keywords": [],
                    "match_types": [],
                },
                "success_metrics": ["CVR", "ACOS", "orders", "unit_session_percentage"],
                "decision_rules": [
                    "CVR提升且ACOS下降: 判断成立",
                    "CVR不变: 表达优化未形成转化因果，需要回到评论需求或价格信任层复核",
                ],
            })

        return {
            "name": "ad_validation_feedback_loop",
            "source": "judgment_system_generated",
            "stage": "ad_validation",
            "status": "planned",
            "confidence_level": precision.get("level", "low"),
            "validation_items": validation_items,
            "feedback_record_fields": [
                "diagnosis_issue",
                "judgment_basis",
                "suggested_action",
                "executed_at",
                "before_snapshot",
                "after_snapshot",
                "ad_result",
                "hit_status",
                "miss_reason",
                "next_iteration",
            ],
            "round_policy": "每一次Listing修改和广告验证都保存为独立optimization_round，用结果校准下一轮判断。",
            "summary": "诊断结论先作为假设，进入广告验证；验证结果回流后再判断是否命中。",
            "reverse_listing_branches": self.build_ad_reverse_listing_branches(),
        }

    def build_ad_reverse_listing_branches(self) -> list[dict[str, Any]]:
        """Rules for using ad validation metrics to reverse-check Listing modules.

        The main chain decides whether a diagnosis should enter ad validation.
        These branches decide which Listing module should be changed when the
        validation result is not healthy enough.
        """
        return [
            {
                "branch": "impression_health",
                "metric_focus": ["impressions", "search_term_precision"],
                "trigger": "曝光不足或搜索词明显发散",
                "listing_module": ["title", "search_terms", "bullets"],
                "reason": "平台没有稳定识别产品身份、对象词、场景词或问题词。",
                "modify_action": "补清产品身份、适用对象、使用场景和问题词；冷门词降级观察，类目错配词直接排除。",
                "do_not_misjudge": "低曝光不一定是Listing差，也可能是词太冷、预算不足或竞价不足。",
            },
            {
                "branch": "click_health",
                "metric_focus": ["CTR", "CPC"],
                "trigger": "曝光足够但CTR低",
                "listing_module": ["main_image", "title", "price_rating"],
                "reason": "用户看见广告但没有形成点击理由。",
                "modify_action": "主图表达产品结果和差异；标题承接搜索意图；同时标记价格、评分、评论数是否弱于竞品。",
                "do_not_misjudge": "如果词意图过泛，先降级或否词，不直接改Listing。",
            },
            {
                "branch": "conversion_health",
                "metric_focus": ["CVR", "orders", "add_to_cart"],
                "trigger": "CTR成立但CVR低",
                "listing_module": ["secondary_images", "bullets", "a_plus", "reviews"],
                "reason": "用户点进来后，详情页没有证明广告承诺、使用边界或信任证据。",
                "modify_action": "副图补场景和效果证据；五点补购买理由和边界；A+补机制/对比/FAQ；评论反向验证失败时降低承诺强度。",
                "do_not_misjudge": "如果关键词和产品真实不匹配，停止投放，不把流量错配误判成承接问题。",
            },
            {
                "branch": "roi_health",
                "metric_focus": ["ACOS", "ROAS", "CPC", "margin"],
                "trigger": "有转化但ACOS高或ROAS低",
                "listing_module": ["ad_structure", "price", "offer", "listing_trust"],
                "reason": "词能卖但利润模型或广告结构不健康。",
                "modify_action": "CPC高但CVR正常时调竞价和匹配；CVR低时回查详情页；毛利低时回查价格/优惠/成本；泛词烧钱时收窄词组并加否词。",
                "do_not_misjudge": "ROI差不一定要改Listing，先分清CPC、价格毛利、词泛化和承接问题。",
            },
            {
                "branch": "learning_feedback",
                "metric_focus": ["hit_status", "miss_reason", "next_iteration"],
                "trigger": "完成一轮广告验证",
                "listing_module": ["keyword_library", "title", "images", "bullets", "a_plus", "negative_keywords"],
                "reason": "把命中词、未命中原因和下一轮动作写回系统，避免下一轮重复误判。",
                "modify_action": "高ROI词进入核心词库和Listing承接；低效泛词进入否词或降级；承接不足词进入对应模块修改。",
                "do_not_misjudge": "没有hit_status、miss_reason和下一轮动作的结果，不进入学习记忆。",
            },
        ]

    @staticmethod
    def build_ad_validation_gate(diagnosis_data: dict[str, Any], listing: Any) -> dict[str, Any]:
        """Final gate that decides whether Listing is ready for ad validation.

        This runs after the market-reality caps and canonical 10D scoring so the
        gate uses the final seller-facing score, not an optimistic pre-cap score.
        Mature listings need a stronger conversion score. New launches can enter
        only small-budget validation once their core Listing evidence is complete.
        """
        scores = diagnosis_data.get("scores") if isinstance(diagnosis_data.get("scores"), dict) else {}
        listing_conversion_score = _dimension_score(scores, LISTING_CONVERSION_DIMENSIONS)
        new_launch = _is_new_launch(listing, diagnosis_data)
        threshold = 72 if new_launch else 80
        core_gaps = _new_launch_core_gaps(listing, scores) if new_launch else []
        passed = listing_conversion_score >= threshold and not core_gaps
        if new_launch:
            status = "新品可小预算验证" if passed else "新品先补承接"
            budget_policy = "只允许小预算精准词/场景问题词验证，不允许放量。"
            action = "进入首轮小预算广告验证。" if passed else "先补齐新品核心承接字段，再进入小预算验证。"
            risk = "新品缺少评论、BSR和销量，广告只能验证点击与转化是否成立，不能当作放量依据。"
        else:
            status = "成熟品可进入验证" if passed else "成熟品先优化承接"
            budget_policy = "承接达标后才进入广告验证；未达标不生成放量建议。"
            action = "进入广告验证。" if passed else "先把Listing承接优化到80分以上，再投广告验证。"
            risk = "承接不足时投广告会污染数据，无法区分关键词问题、产品问题还是页面没接住。"

        reasons = [
            f"Listing承接分 {round(listing_conversion_score)} / {threshold}",
            "新品按可验证标准判断" if new_launch else "成熟品按80分广告验证门槛判断",
        ]
        reasons.extend(core_gaps)

        return {
            "gate": "listing_ad_validation_readiness",
            "product_stage": "new_launch" if new_launch else "mature_listing",
            "threshold": threshold,
            "listing_conversion_score": round(listing_conversion_score, 2),
            "allowed_validation": passed,
            "status": status,
            "budget_policy": budget_policy,
            "required_action": action,
            "risk_warning": risk,
            "blocking_reasons": core_gaps,
            "basis": reasons,
        }

    @staticmethod
    def apply_ad_validation_gate_to_outputs(
        diagnosis_data: dict[str, Any],
        listing: Any,
    ) -> dict[str, Any]:
        gate = JudgmentSystemService.build_ad_validation_gate(diagnosis_data, listing)
        outputs = diagnosis_data.get("decision_outputs")
        if not isinstance(outputs, list):
            return gate

        for item in outputs:
            if not isinstance(item, dict) or item.get("domain") != "advertising_validation":
                continue
            item["validation_gate"] = gate
            item["current_judgment"] = gate["status"]
            item["judgment_basis"] = gate["basis"]
            item["recommended_action"] = gate["required_action"]
            item["risk_warning"] = gate["risk_warning"]
            item["next_check"] = gate["budget_policy"]
            item["score"] = gate["listing_conversion_score"]
            item["score_band"] = "可验证" if gate["allowed_validation"] else "未达标"
            item["seller_facing_output"] = {
                "title": "广告验证判断",
                "judgment": gate["status"],
                "basis": f"Listing承接分 {round(float(gate.get('listing_conversion_score') or 0))} / {gate.get('threshold')}",
                "action": gate["required_action"],
                "risk": gate["risk_warning"],
                "confidence": round(float(gate.get("listing_conversion_score") or 0)),
                "score_band": item["score_band"],
            }
            break
        return gate

    def build_decision_outputs(
        self,
        *,
        human_nature: dict[str, Any],
        review_semantics: dict[str, Any],
        cosmo_semantics: dict[str, Any],
        causal: dict[str, Any],
        precision: dict[str, Any],
        ad_validation: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Build V4 decision outputs.

        DecisionOutput sits after the Human Nature Root Layer, two rulers,
        10D judgment, causal judgment and validation plan. It is the
        user-facing decision expression, not the reasoning standard itself.
        """
        dimension_scores = cosmo_semantics.get("dimension_scores") or {}
        review_score = float(review_semantics.get("score") or 0)
        platform_score = float(cosmo_semantics.get("score") or 0)
        causal_score = float(causal.get("score") or 0)
        precision_score = float(precision.get("score") or 0)
        validation_items = ad_validation.get("validation_items", []) if isinstance(ad_validation, dict) else []
        readiness = float((causal.get("raw") or {}).get("keyword_causality", {}).get("readiness_score") or 0)
        human_nodes = human_nature.get("level_2", {}).get("active_nodes", [])
        motivations = human_nature.get("level_3", {}).get("items", [])
        needs = human_nature.get("level_4", {}).get("items", [])
        scenarios = human_nature.get("level_5", {}).get("items", [])
        solutions = human_nature.get("level_6", {}).get("items", [])

        user_intent_score = _avg([review_score, _dimension_score(dimension_scores, USER_INTENT_DIMENSIONS)])
        platform_matching_score = _avg([platform_score, _dimension_score(dimension_scores, PLATFORM_MATCHING_DIMENSIONS)])
        listing_conversion_score = _avg([causal_score, _dimension_score(dimension_scores, LISTING_CONVERSION_DIMENSIONS)])
        advertising_validation_score = _avg([readiness or causal_score, _dimension_score(dimension_scores, ADVERTISING_VALIDATION_DIMENSIONS)])
        allocation_score = _avg([user_intent_score, platform_matching_score, listing_conversion_score, advertising_validation_score])
        learning_score = _avg([precision_score, 80 if validation_items else 45])

        def seller_output(domain: str, score: float, judgment: str, action: str, risk: str, basis: list[str]) -> dict[str, Any]:
            band = _score_band(score)
            by_domain = {
                "user_intent": {
                    "title": "买家购买判断",
                    "judgment": "购买理由清楚" if score >= 80 else "购买理由还不够清楚" if score >= 60 else "买家为什么买还没讲清楚",
                    "basis": "当前证据用于判断买家是否有清楚的购买理由。",
                    "action": "先补清目标买家、使用场景和最大顾虑，再进入下一步验证。",
                    "risk": "购买理由不清楚时，后续关键词和广告容易跑偏。",
                },
                "platform_matching": {
                    "title": "Amazon识别判断",
                    "judgment": "Amazon识别较清楚" if score >= 80 else "Amazon识别还不稳定" if score >= 60 else "Amazon可能识别不准这个产品",
                    "basis": "标题、五点或后台词里的产品身份和场景信息会影响Amazon匹配。",
                    "action": "补齐产品身份、类目锚点、属性词、关系词和场景问题词。",
                    "risk": "识别不准会带来低曝光、错匹配和更高点击成本。",
                },
                "listing_conversion": {
                    "title": "Listing承接判断",
                    "judgment": "页面承接较好" if score >= 80 else "页面承接还要优化" if score >= 60 else "页面没有接住流量",
                    "basis": "标题、图片、五点或A+是否证明购买理由，会影响点击后的转化。",
                    "action": "先改最影响转化的承接模块，再做小预算验证。",
                    "risk": "只改表述不补证据，可能点击提升但转化不升。",
                },
                "advertising_validation": {
                    "title": "广告验证判断",
                    "judgment": judgment,
                    "basis": "当前数据用于判断是否适合进入广告验证。",
                    "action": action,
                    "risk": risk,
                },
                "capital_allocation": {
                    "title": "投入优先级",
                    "judgment": "可以优先投入高置信改动" if score >= 65 else "先补证据，再投入资源",
                    "basis": f"当前综合置信度为{round(score)}分。",
                    "action": "预算、时间和人力先投向最能验证核心判断的动作。",
                    "risk": "证据不足时加大投入，会把错误判断变成沉没成本。",
                },
                "learning_feedback": {
                    "title": "复盘结论",
                    "judgment": "等待验证结果回流" if validation_items else "暂时缺少可复盘样本",
                    "basis": "当前还没有足够结果判断这次动作是否命中。",
                    "action": "验证后记录命中、未命中、样本不足和下一轮动作。",
                    "risk": "没有归因的结果进入复盘，会让下一轮判断变偏。",
                },
            }
            item = by_domain.get(domain, {})
            return {
                "title": item.get("title", "运营判断"),
                "judgment": item.get("judgment", judgment),
                "basis": item.get("basis", ""),
                "action": item.get("action", action),
                "risk": item.get("risk", risk),
                "confidence": round(_decision_confidence(score, precision_score)),
                "score_band": band,
            }

        def output(
            *,
            domain: str,
            name: str,
            core_question: str,
            score: float,
            judgment: str,
            basis: list[str],
            action: str,
            risk: str,
            impact: str,
            next_check: str,
            failure_pattern: str,
        ) -> dict[str, Any]:
            clean_basis = [item for item in basis if item]
            return {
                "domain": domain,
                "domain_name": name,
                "core_question": core_question,
                "current_judgment": judgment,
                "judgment_basis": clean_basis,
                "confidence_score": _decision_confidence(score, precision_score),
                "recommended_action": action,
                "risk_warning": risk,
                "expected_impact": impact,
                "next_check": next_check,
                "score": round(score, 2),
                "score_band": _score_band(score),
                "failure_pattern": failure_pattern,
                "seller_facing_output": seller_output(domain, score, judgment, action, risk, clean_basis),
                "human_nature_layer": {
                    "levels": human_nature.get("levels", []),
                    "root": human_nature.get("level_0", {}),
                    "human_nodes": human_nodes,
                    "motivations": motivations,
                    "needs": needs,
                    "scenarios": scenarios,
                    "solutions": solutions,
                },
            }

        outputs = [
            output(
                domain="user_intent",
                name="用户意图决策",
                core_question="用户为什么买？",
                score=user_intent_score,
                judgment=f"购买动机{_score_band(user_intent_score)}",
                basis=[
                    f"人性节点：{' / '.join(human_nodes[:4])}" if human_nodes else "",
                    f"动机：{' / '.join(motivations[:3])}" if motivations else "",
                    f"需求：{' / '.join(needs[:3])}" if needs else "",
                    f"用户需求对齐 {round(review_score)} 分",
                    f"场景/人群/心理/风险维度均分 {round(_dimension_score(dimension_scores, USER_INTENT_DIMENSIONS))} 分",
                    review_semantics.get("summary", ""),
                ],
                action="先确认目标人群、购买场景和最大顾虑；低分项不进入大预算广告。",
                risk="用户意图不清时，关键词和广告会把流量带偏。",
                impact="减少无效选品和错误卖点投入。",
                next_check="检查人群、场景、痛点、风险是否能被标题/图片/五点证明。",
                failure_pattern="FP-UI001 意图不清导致后续判断漂移",
            ),
            output(
                domain="platform_matching",
                name="平台匹配决策",
                core_question="Amazon是否能够正确理解商品？",
                score=platform_matching_score,
                judgment=f"平台理解{_score_band(platform_matching_score)}",
                basis=[
                    f"场景根因：{' / '.join(scenarios[:3])}" if scenarios else "",
                    f"平台识别对齐 {round(platform_score)} 分",
                    f"产品身份/兼容/场景/趋势均分 {round(_dimension_score(dimension_scores, PLATFORM_MATCHING_DIMENSIONS))} 分",
                ],
                action="补齐产品身份、类目锚点、属性、关系词和场景问题词。",
                risk="平台识别不清会造成低曝光、错匹配和高CPC。",
                impact="提升搜索词精准度和广告匹配质量。",
                next_check="优先检查标题、Search Terms、五点是否包含身份词、关系词和问题词。",
                failure_pattern="FP-PM001 平台无法稳定识别产品语义池",
            ),
            output(
                domain="listing_conversion",
                name="Listing承接决策",
                core_question="页面是否接住流量？",
                score=listing_conversion_score,
                judgment=f"转化承接{_score_band(listing_conversion_score)}",
                basis=[
                    f"解决方案层：{' / '.join(solutions[:3])}" if solutions else "",
                    f"因果转化对齐 {round(causal_score)} 分",
                    f"功能/场景/风险/差异/主观属性均分 {round(_dimension_score(dimension_scores, LISTING_CONVERSION_DIMENSIONS))} 分",
                ],
                action="优先修改承接断点最大的模块，再进入小预算验证。",
                risk="只改文案不补证据，会出现CTR提升但CVR不升。",
                impact="提升点击后的CVR，降低无效点击和ACOS。",
                next_check="按标题、主图、副图、五点、A+、评论逐项检查承诺是否被证明。",
                failure_pattern="FP-LC001 点击成立但详情页承接不足",
            ),
            output(
                domain="advertising_validation",
                name="广告验证决策",
                core_question="广告是否验证前面判断？",
                score=advertising_validation_score,
                judgment="可进入小预算验证" if validation_items else "暂不建议验证",
                basis=[
                    f"验证从动机链路开始：{' / '.join(motivations[:3])}" if motivations else "",
                    f"关键词验证就绪 {round(readiness or causal_score)} 分",
                    f"已生成 {len(validation_items)} 组验证假设",
                ],
                action="只验证P0关系词和状态触发词；未绑定假设ID的数据不进入学习。",
                risk="广告不能当获客工具直接放量，否则会把诊断误差放大成预算损失。",
                impact="用曝光、点击、转化、ROI反向证明前面的判断。",
                next_check="按Impression、CTR、CVR、ACOS、ROI判断平台、用户、Listing和商业模型是否成立。",
                failure_pattern="FP-AD001 广告未绑定假设导致无法归因",
            ),
            output(
                domain="capital_allocation",
                name="资本配置决策",
                core_question="资源应该投向哪里？",
                score=allocation_score,
                judgment="优先投向高置信改动" if allocation_score >= 65 else "先补判断再投资源",
                basis=[
                    f"资源优先投向已被动机和场景共同支撑的动作",
                    f"用户意图 {round(user_intent_score)} 分",
                    f"平台匹配 {round(platform_matching_score)} 分",
                    f"Listing承接 {round(listing_conversion_score)} 分",
                    f"广告验证 {round(advertising_validation_score)} 分",
                ],
                action="预算先投能验证核心判断的关键词组和P0 Listing改动，不平均分配。",
                risk="在低置信环节投入预算，会把错误判断固化为沉没成本。",
                impact="把预算、时间、人力集中到最高胜率的动作上。",
                next_check="比较各决策域置信度，低于65分的域先补证据，高于80分的域才允许加码。",
                failure_pattern="FP-CA001 资源平均投入导致优先级失真",
            ),
            output(
                domain="learning_feedback",
                name="回流学习决策",
                core_question="这次结果是否应该进入系统认知？",
                score=learning_score,
                judgment="等待验证回流" if validation_items else "缺少可学习样本",
                basis=[
                    "学习对象是动机、需求、场景、解决方案、表达、行为和结果之间的因果关系",
                    f"数据完整性 {round(precision_score)} 分",
                    "已有广告验证假设" if validation_items else "尚未形成广告验证样本",
                ],
                action="只有带hit_status、miss_reason和next_iteration的结果才能进入规则记忆。",
                risk="样本不足或未归因数据进入记忆，会让系统越学越偏。",
                impact="沉淀人性动机、需求、场景、解决方案、表达、行为和结果之间的因果关系。",
                next_check="验证后标记命中、未命中、样本不足、误判或权重修正。",
                failure_pattern="FP-LF001 无归因回流污染学习记忆",
            ),
        ]
        return outputs

    async def judge_listing(
        self,
        *,
        listing: Any,
        diagnosis_data: dict[str, Any],
        user_id: str,
        context: dict[str, Any] | None = None,
        asin: str | None = None,
        listing_diagnosis_id: int | None = None,
        run_causal: bool = True,
        existing_causal_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a unified backend judgment object for Listing workflows."""
        human_nature = self.build_human_nature_layer(listing, diagnosis_data)
        review_semantics = self.build_review_semantics(diagnosis_data)
        cosmo_semantics = self.build_cosmo_semantics(diagnosis_data)
        precision = self.build_precision_judgment(listing, context)

        if run_causal:
            causal = await self.build_causal_judgment(
                title=getattr(listing, "title", "") or "",
                bullets=getattr(listing, "bullet_points", "") or "",
                description=getattr(listing, "description", "") or "",
                asin=asin or getattr(listing, "asin", None),
                marketplace=getattr(listing, "marketplace", "US") or "US",
                user_id=user_id,
                listing_diagnosis_id=listing_diagnosis_id,
                existing_causal_result=existing_causal_result,
            )
        else:
            causal = self.build_rule_based_causal_judgment(listing, diagnosis_data)

        alignment_scores = {
            "review_demand_alignment": review_semantics["score"],
            "platform_semantic_alignment": cosmo_semantics["score"],
            "causal_conversion_alignment": causal["score"],
        }
        overall_score = round(
            alignment_scores["review_demand_alignment"] * 0.30
            + alignment_scores["platform_semantic_alignment"] * 0.35
            + alignment_scores["causal_conversion_alignment"] * 0.35,
            2,
        )
        ad_validation = self.build_ad_validation_plan(
            review_semantics=review_semantics,
            cosmo_semantics=cosmo_semantics,
            causal=causal,
            precision=precision,
        )
        decision_outputs = self.build_decision_outputs(
            human_nature=human_nature,
            review_semantics=review_semantics,
            cosmo_semantics=cosmo_semantics,
            causal=causal,
            precision=precision,
            ad_validation=ad_validation,
        )

        return {
            "version": self.version,
            "scope": "listing",
            "overall_judgment_score": overall_score,
            "alignment_scores": alignment_scores,
            "sections": {
                "human_nature": human_nature,
                "review_semantics": review_semantics,
                "cosmo_semantics": cosmo_semantics,
                "causal_judgment": causal,
                "precision_confidence": precision,
                "ad_validation": ad_validation,
                "decision_outputs": decision_outputs,
            },
            "human_nature_graph": human_nature,
            "data_integrity": precision["data_integrity"],
            "diagnosis_confidence": precision["confidence_by_alignment"],
            "legacy_bridge": {
                "causal_scores": causal["dimension_scores"],
                "causal_diagnosis": causal["raw"],
                "data_integrity": precision["data_integrity"],
                "diagnosis_confidence": precision["confidence_by_alignment"],
                "ad_validation_plan": ad_validation,
                "decision_outputs": decision_outputs,
                "human_nature_graph": human_nature,
            },
        }

    @staticmethod
    def apply_to_legacy_listing_diagnosis(
        diagnosis_data: dict[str, Any],
        judgment: dict[str, Any],
    ) -> dict[str, Any]:
        """Attach unified judgment while keeping old API fields stable."""
        data = dict(diagnosis_data)
        sections = judgment.get("sections", {})
        causal = sections.get("causal_judgment", {})
        causal_scores = causal.get("dimension_scores", {})

        scores = dict(data.get("scores") or {})
        scores["causal_state_gap_coverage"] = causal_scores.get("state_gap_coverage", 0)
        scores["causal_mechanism_clarity"] = causal_scores.get("mechanism_clarity", 0)
        scores["causal_side_effect_transparency"] = causal_scores.get("side_effect_transparency", 0)
        data["scores"] = scores

        data["causal_diagnosis"] = causal.get("raw", {})
        data["judgment_system"] = judgment
        data["human_nature_graph"] = sections.get("human_nature", judgment.get("human_nature_graph", {}))
        data["ad_validation_plan"] = sections.get("ad_validation", {})
        data["decision_outputs"] = sections.get("decision_outputs", [])
        data["data_integrity"] = judgment.get("data_integrity", {})
        data["diagnosis_confidence"] = judgment.get("diagnosis_confidence", {})

        suggestions = dict(data.get("suggestions") or {})
        raw_causal = causal.get("raw", {})
        causal_suggestions: list[str] = []
        for gap in raw_causal.get("state_gaps", {}).get("missing_gaps", []) or []:
            causal_suggestions.append(f"补充「{gap.get('gap_name')}」的场景描述和解决方案")
        causal_suggestions.extend(raw_causal.get("causal_mechanisms", {}).get("improvement_suggestions", []) or [])
        causal_suggestions.extend(raw_causal.get("side_effects", {}).get("improvement_suggestions", []) or [])
        if causal_suggestions:
            suggestions["causal_optimization"] = causal_suggestions
        ad_validation = sections.get("ad_validation", {})
        validation_items = ad_validation.get("validation_items", []) if isinstance(ad_validation, dict) else []
        if validation_items:
            suggestions["ad_validation"] = [
                item.get("hypothesis", "") for item in validation_items if item.get("hypothesis")
            ]
        data["suggestions"] = suggestions

        return data
