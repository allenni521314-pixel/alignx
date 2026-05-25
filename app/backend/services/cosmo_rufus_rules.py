"""Rule-based COSMO/Rufus diagnostic layer.

This module turns public-source COSMO/Rufus thinking into deterministic backend
rules. It does not claim access to Amazon internal ranking systems.
"""

from __future__ import annotations

import re
from typing import Any


RELATION_DIMENSIONS = ("is_a", "used_for", "used_in", "used_on", "used_with", "capable_of")

SCENARIO_TERMS = {
    "home": ["home", "house", "apartment", "bedroom", "bathroom", "kitchen", "closet"],
    "outdoor": ["outdoor", "camping", "beach", "pool", "travel", "hiking", "rv"],
    "pet": ["cat", "dog", "pet", "litter", "urine", "ammonia"],
    "gift": ["gift", "birthday", "christmas", "mom", "dad", "kids", "teen"],
}

PAIN_TERMS = [
    "odor",
    "smell",
    "ammonia",
    "mess",
    "leak",
    "noise",
    "pain",
    "safe",
    "filter",
    "maintenance",
    "clean",
    "compatible",
    "waterproof",
    "durable",
]

FUNCTION_TERMS = [
    "remove",
    "reduce",
    "control",
    "clean",
    "protect",
    "charge",
    "play",
    "filter",
    "deodorize",
    "purify",
    "organize",
    "store",
]


def build_cosmo_rufus_analysis(listing: Any, diagnosis_data: dict[str, Any]) -> dict[str, Any]:
    text = _listing_text(listing, diagnosis_data)
    title = str(getattr(listing, "title", "") or "")
    category = str(getattr(listing, "category", "") or "")
    keyword_coverage = diagnosis_data.get("keyword_coverage") or {}
    suggestions = diagnosis_data.get("suggestions") or {}
    ad_keywords = diagnosis_data.get("ad_keywords") or {}

    product_identity = _product_identity(title, category)
    relation_map = _relation_map(text, product_identity, category, keyword_coverage)
    buyer_questions = _buyer_questions(text, relation_map)
    gaps = _relation_gaps(relation_map, buyer_questions)
    hypotheses = _hypotheses(gaps, suggestions, ad_keywords)
    scores = _scores(relation_map, buyer_questions, hypotheses)

    return {
        "version": "amazon-cosmo-rufus-rules-v1",
        "source_boundary": "public_source_inference_not_internal_amazon_algorithm",
        "product_identity": product_identity,
        "relation_map": relation_map,
        "buyer_questions": buyer_questions,
        "relation_gaps": gaps,
        "validation_hypotheses": hypotheses,
        "scores": scores,
        "verdict": _verdict(scores, gaps),
        "safe_language": [
            "平台理解准备度",
            "买家问题覆盖",
            "关系图谱完整度",
            "可验证广告假设",
        ],
    }


def merge_cosmo_rufus_into_legacy(data: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    """Attach COSMO/Rufus rules and enrich existing suggestions/ad validation."""
    data = dict(data)
    data["cosmo_rufus_analysis"] = analysis

    suggestions = dict(data.get("suggestions") or {})
    existing = suggestions.get("cosmo_rufus_optimization") or []
    gap_actions = [
        f"补强 {gap['relation']}：{gap['action']}"
        for gap in analysis.get("relation_gaps", [])[:5]
    ]
    suggestions["cosmo_rufus_optimization"] = [*existing, *gap_actions][:8]
    data["suggestions"] = suggestions

    ad_validation_plan = dict(data.get("ad_validation_plan") or {})
    existing_items = ad_validation_plan.get("validation_items") or []
    hypothesis_items = [
        {
            "id": item["hypothesis_id"],
            "hypothesis": item["hypothesis"],
            "diagnosis_issue": item["diagnosis_issue"],
            "cosmo_relation": item["cosmo_relation"],
            "rufus_question": item["rufus_question"],
            "suggested_listing_action": item["listing_action"],
            "ad_action": {
                "test_type": "cosmo_rufus_hypothesis_validation",
                "keywords": item["ad_test_keywords"],
                "match_types": ["phrase", "exact"],
            },
            "success_metrics": item["success_metrics"],
            "decision_rules": item["decision_rules"],
        }
        for item in analysis.get("validation_hypotheses", [])
    ]
    ad_validation_plan["validation_items"] = [*hypothesis_items, *existing_items][:8]
    ad_validation_plan["source"] = "cosmo_rufus_rules_and_judgment_system"
    data["ad_validation_plan"] = ad_validation_plan
    return data


def _listing_text(listing: Any, diagnosis_data: dict[str, Any]) -> str:
    parts = [
        getattr(listing, "title", "") or "",
        getattr(listing, "bullet_points", "") or "",
        getattr(listing, "description", "") or "",
        getattr(listing, "a_plus_content", "") or "",
        getattr(listing, "backend_keywords", "") or "",
        getattr(listing, "main_image_description", "") or "",
        getattr(listing, "category", "") or "",
        str(diagnosis_data.get("overall_summary") or ""),
    ]
    return " ".join(parts).lower()


def _product_identity(title: str, category: str) -> dict[str, str]:
    tokens = [w for w in re.sub(r"[^a-zA-Z0-9\s]", " ", title.lower()).split() if len(w) > 2]
    identity = category or " ".join(tokens[:4]) or "amazon product"
    return {
        "name": title[:180],
        "category": category,
        "inferred_identity": identity,
    }


def _relation_map(text: str, product_identity: dict[str, str], category: str, keyword_coverage: dict[str, Any]) -> dict[str, list[str]]:
    covered = keyword_coverage.get("covered_categories") or {}
    relation_map = {key: [] for key in RELATION_DIMENSIONS}
    relation_map["is_a"] = _unique([product_identity.get("inferred_identity", ""), category, *covered.get("core_category", [])])
    relation_map["used_for"] = _unique([term for term in [*covered.get("pain_point", []), *covered.get("function", [])] if term])
    relation_map["capable_of"] = _unique([term for term in FUNCTION_TERMS if term in text] + covered.get("function", []))
    relation_map["used_in"] = _unique([term for terms in SCENARIO_TERMS.values() for term in terms if term in text] + covered.get("scenario", []))
    relation_map["used_on"] = _unique([term for term in ["pet", "cat", "dog", "skin", "hair", "car", "floor", "countertop"] if term in text])
    relation_map["used_with"] = _unique([term for term in ["filter", "charger", "phone", "litter box", "cookware", "speaker"] if term in text])
    return relation_map


def _buyer_questions(text: str, relation_map: dict[str, list[str]]) -> list[dict[str, str]]:
    candidates = [
        ("discover", "What exactly is this product, and is it the right type for my need?", bool(relation_map["is_a"])),
        ("validate", "Will it solve my specific problem or pain point?", bool(relation_map["used_for"])),
        ("compare", "Where and when should I use it compared with alternatives?", bool(relation_map["used_in"])),
        ("object", "What risks, limits, maintenance, or compatibility issues should I know?", any(term in text for term in ["safe", "compatible", "filter", "maintenance", "clean", "warranty"])),
        ("decide", "Do reviews and detail-page evidence support the promise?", any(term in text for term in ["review", "rating", "customer", "qa", "q&a"])),
    ]
    return [
        {
            "question": question,
            "buyer_stage": stage,
            "current_answer_quality": "strong" if answered else "missing",
            "evidence_needed": "" if answered else _evidence_for_stage(stage),
        }
        for stage, question, answered in candidates
    ]


def _relation_gaps(relation_map: dict[str, list[str]], buyer_questions: list[dict[str, str]]) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    for relation, values in relation_map.items():
        if not values:
            gaps.append(
                {
                    "relation": relation,
                    "gap": "missing_relation_evidence",
                    "action": f"在标题、五点、图片或A+中补充 {relation} 关系证据",
                }
            )
    for item in buyer_questions:
        if item["current_answer_quality"] == "missing":
            gaps.append(
                {
                    "relation": f"rufus_question:{item['buyer_stage']}",
                    "gap": item["question"],
                    "action": item["evidence_needed"],
                }
            )
    return gaps[:8]


def _hypotheses(gaps: list[dict[str, str]], suggestions: dict[str, Any], ad_keywords: dict[str, Any]) -> list[dict[str, Any]]:
    keywords = _ad_keyword_pool(ad_keywords)
    fallback_action = ""
    bullets = suggestions.get("bullet_points_optimization") or []
    if bullets:
        fallback_action = str(bullets[0])
    fallback_action = fallback_action or suggestions.get("title_rewrite") or "补强Listing关系证据和买家问题承接"

    hypotheses = []
    for index, gap in enumerate(gaps[:4], start=1):
        hypotheses.append(
            {
                "hypothesis_id": f"cosmo-rufus-{index}",
                "hypothesis": f"补强 {gap['relation']} 后，对应搜索词点击质量和转化承接应提升",
                "diagnosis_issue": gap["gap"],
                "cosmo_relation": gap["relation"],
                "rufus_question": gap["gap"] if gap["relation"].startswith("rufus_question") else "",
                "listing_action": gap["action"] or fallback_action,
                "ad_test_keywords": keywords[index - 1:index + 2] or keywords[:2],
                "success_metrics": ["CTR", "CVR", "ACOS", "search_term_precision"],
                "decision_rules": [
                    "clicks < 100: 待验证，不能判定失败",
                    "CTR低: 优先检查关键词意图或主图证据",
                    "CTR可接受但CVR低: 优先检查详情页信任承接",
                    "CVR可接受但ACOS高: 检查价格与承诺强度",
                ],
            }
        )
    return hypotheses


def _scores(relation_map: dict[str, list[str]], buyer_questions: list[dict[str, str]], hypotheses: list[dict[str, Any]]) -> dict[str, int]:
    relation_score = round(sum(1 for values in relation_map.values() if values) * 100 / len(RELATION_DIMENSIONS))
    question_score = round(sum(1 for item in buyer_questions if item["current_answer_quality"] == "strong") * 100 / len(buyer_questions))
    validation_score = 80 if hypotheses else 35
    overall = round(relation_score * 0.4 + question_score * 0.4 + validation_score * 0.2)
    return {
        "relationship_graph_completeness": relation_score,
        "buyer_question_coverage": question_score,
        "validation_readiness": validation_score,
        "overall": overall,
    }


def _verdict(scores: dict[str, int], gaps: list[dict[str, str]]) -> str:
    if scores["overall"] >= 80:
        return "COSMO/Rufus关系与买家问题承接较完整，可进入假设级广告验证。"
    if scores["overall"] >= 60:
        return "已有基础语义承接，但仍存在关系或买家问题缺口，建议先补强再验证。"
    return "平台理解和买家问题承接不足，当前广告验证容易产生噪音。"


def _ad_keyword_pool(ad_keywords: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for group in ("high_conversion", "long_tail", "traffic"):
        for item in ad_keywords.get(group) or []:
            if isinstance(item, dict) and item.get("keyword"):
                values.append(str(item["keyword"]))
            elif isinstance(item, str):
                values.append(item)
    return _unique(values)[:8]


def _evidence_for_stage(stage: str) -> str:
    return {
        "discover": "补充清晰品类身份和首屏产品定位",
        "validate": "补充痛点、机制和场景证据",
        "compare": "补充使用场景、适用/不适用边界和替代品差异",
        "object": "补充安全、维护、兼容、耗材、售后等风险解释",
        "decide": "补充评论/Q&A承接、A+证据和真实使用反馈",
    }.get(stage, "补充可验证证据")


def _unique(values: list[Any]) -> list[str]:
    seen = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result
