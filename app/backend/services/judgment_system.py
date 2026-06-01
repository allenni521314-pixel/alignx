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

    version = "judgment-system-v1"

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
                    "CTR提升: 平台识别和首屏表达更容易被识别",
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

        return {
            "version": self.version,
            "scope": "listing",
            "overall_judgment_score": overall_score,
            "alignment_scores": alignment_scores,
            "sections": {
                "review_semantics": review_semantics,
                "cosmo_semantics": cosmo_semantics,
                "causal_judgment": causal,
                "precision_confidence": precision,
                "ad_validation": ad_validation,
            },
            "data_integrity": precision["data_integrity"],
            "diagnosis_confidence": precision["confidence_by_alignment"],
            "legacy_bridge": {
                "causal_scores": causal["dimension_scores"],
                "causal_diagnosis": causal["raw"],
                "data_integrity": precision["data_integrity"],
                "diagnosis_confidence": precision["confidence_by_alignment"],
                "ad_validation_plan": ad_validation,
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
        data["ad_validation_plan"] = sections.get("ad_validation", {})
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
