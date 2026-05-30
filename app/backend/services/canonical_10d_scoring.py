"""Shared Amazon/COSMO-style 10D scoring normalizer.

The public UI can call the same dimensions "10维诊断" everywhere, while
competitor analysis and own-listing diagnosis keep their own action language.
This module keeps the underlying score aliases, market caps, and evidence
gates identical for the same ASIN/listing evidence.
"""

from __future__ import annotations

import re
from typing import Any


CANONICAL_SCORE_KEYS: tuple[str, ...] = (
    "function_expression",
    "scenario_expression",
    "identity_fit",
    "psychology_benefit",
    "risk_elimination",
    "differentiation",
    "product_identity",
    "compatibility",
    "subjective_properties",
    "market_trend",
)

ASIN_TO_CANONICAL_SCORE_KEY: dict[str, str] = {
    "functionality": "function_expression",
    "scenario": "scenario_expression",
    "user_profile": "identity_fit",
    "emotional": "psychology_benefit",
    "risk_elimination": "risk_elimination",
    "differentiation": "differentiation",
    "product_identity": "product_identity",
    "compatibility": "compatibility",
    "subjective_properties": "subjective_properties",
    "market_trend": "market_trend",
}

CANONICAL_TO_ASIN_SCORE_KEY: dict[str, str] = {
    canonical: asin for asin, canonical in ASIN_TO_CANONICAL_SCORE_KEY.items()
}

CANONICAL_DB_SCORE_KEY: dict[str, str] = {
    "function_expression": "score_function_expression",
    "scenario_expression": "score_scenario_expression",
    "identity_fit": "score_identity_fit",
    "psychology_benefit": "score_psychology_benefit",
    "risk_elimination": "score_risk_elimination",
    "differentiation": "score_differentiation",
    "product_identity": "score_product_identity",
    "compatibility": "score_compatibility",
    "subjective_properties": "score_subjective_properties",
    "market_trend": "score_market_trend",
}

ASIN_DB_SCORE_KEY: dict[str, str] = {
    "functionality": "score_functionality",
    "scenario": "score_scenario",
    "user_profile": "score_user_profile",
    "emotional": "score_emotional",
    "risk_elimination": "score_risk_elimination",
    "differentiation": "score_differentiation",
    "product_identity": "score_product_identity",
    "compatibility": "score_compatibility",
    "subjective_properties": "score_subjective_properties",
    "market_trend": "score_market_trend",
}


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            return {}
    if hasattr(value, "dict"):
        try:
            return value.dict()
        except Exception:
            return {}
    return {}


def _clamp_score(value: Any) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if not number or number < 0:
        return 0
    return int(round(max(0, min(100, number))))


def _first_score(raw: dict[str, Any], aliases: list[str]) -> int:
    for alias in aliases:
        if alias in raw:
            score = _clamp_score(raw.get(alias))
            if score > 0:
                return score
    return 0


def _parse_metric_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))
    match = re.search(r"\d+", str(value).replace(",", ""))
    return int(match.group(0)) if match else 0


def _has_required_price(value: Any) -> bool:
    text = str(value or "").strip()
    if not text or text in {"-", "—", "N/A", "n/a", "NA", "待确认", "未提供", "未知"}:
        return False
    return bool(re.search(r"\d", text))


def _count_bullets(value: Any) -> int:
    if isinstance(value, list):
        return len([item for item in value if str(item or "").strip()])
    if isinstance(value, str):
        return len([item for item in re.split(r"[\n;；]+", value) if item.strip()])
    return 0


def _text_blob(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_text_blob(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_text_blob(item) for item in value.values())
    return str(value or "")


def _tokens(value: Any) -> set[str]:
    text = _text_blob(value).lower()
    return set(re.findall(r"[a-z0-9][a-z0-9+\-]{1,}", text))


def _jaccard(left: Any, right: Any) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _field(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", "-", "—"):
            return value
    return ""


def product_evidence_similarity(left: Any, right: Any) -> dict[str, float]:
    """Compare whether two product payloads describe the same Listing evidence.

    This is intentionally conservative: the same ASIN can have a rewritten
    listing, and that should receive a fresh diagnosis instead of inheriting an
    old score snapshot.
    """
    left_data = _as_dict(left)
    right_data = _as_dict(right)
    title_similarity = _jaccard(
        _field(left_data, "title", "product_title", "listing_title"),
        _field(right_data, "title", "product_title", "listing_title"),
    )
    bullet_similarity = _jaccard(
        _field(left_data, "bullet_points", "bullets"),
        _field(right_data, "bullet_points", "bullets"),
    )
    has_both_bullets = _count_bullets(_field(left_data, "bullet_points", "bullets")) > 0 and _count_bullets(
        _field(right_data, "bullet_points", "bullets")
    ) > 0
    if has_both_bullets:
        score = title_similarity * 0.55 + bullet_similarity * 0.45
    else:
        score = title_similarity
    return {
        "score": round(score, 4),
        "title_similarity": round(title_similarity, 4),
        "bullet_similarity": round(bullet_similarity, 4),
    }


def normalize_canonical_scores(scores: Any) -> dict[str, int]:
    """Normalize either legacy ASIN scores or listing scores into canonical 10D."""
    raw = _as_dict(scores)
    nested = _as_dict(raw.get("scores"))
    source = {**nested, **raw}
    canonical: dict[str, int] = {}
    for key in CANONICAL_SCORE_KEYS:
        asin_key = CANONICAL_TO_ASIN_SCORE_KEY.get(key, "")
        aliases = [
            key,
            CANONICAL_DB_SCORE_KEY.get(key, ""),
            asin_key,
            ASIN_DB_SCORE_KEY.get(asin_key, ""),
        ]
        canonical[key] = _first_score(source, [alias for alias in aliases if alias])
    return canonical


def canonical_to_asin_scores(canonical_scores: Any) -> dict[str, int]:
    canonical = normalize_canonical_scores(canonical_scores)
    return {
        asin_key: canonical.get(canonical_key, 0)
        for canonical_key, asin_key in CANONICAL_TO_ASIN_SCORE_KEY.items()
    }


def _cap_score_map(scores: dict[str, int], caps: dict[str, int], reasons: list[str]) -> None:
    for key, cap in caps.items():
        current = scores.get(key)
        if isinstance(current, (int, float)) and current > cap:
            scores[key] = int(cap)
    reasons[:] = [reason for reason in reasons if reason]


def _product_context(product_data: Any) -> dict[str, Any]:
    data = _as_dict(product_data)
    return {
        "price": data.get("price"),
        "review_count": data.get("review_count"),
        "bsr_rank": data.get("bsr_rank") or data.get("sales_rank"),
        "bullet_points": data.get("bullet_points") or data.get("bullets"),
        "backend_keywords": data.get("backend_keywords") or data.get("search_terms") or data.get("search_keywords"),
    }


def apply_market_reality_caps(
    canonical_scores: Any,
    product_data: Any,
) -> tuple[dict[str, int], dict[str, Any]]:
    """Apply the same evidence caps to ASIN, competitor, and own-listing views."""
    scores = normalize_canonical_scores(canonical_scores)
    if not any(scores.values()):
        return scores, {"applied": False, "reasons": []}

    ctx = _product_context(product_data)
    review_count = _parse_metric_int(ctx.get("review_count"))
    bsr_rank = _parse_metric_int(ctx.get("bsr_rank"))
    bullet_count = _count_bullets(ctx.get("bullet_points"))
    has_backend = bool(str(ctx.get("backend_keywords") or "").strip())
    has_price = _has_required_price(ctx.get("price"))
    is_new_launch = (not has_price) and review_count == 0 and bsr_rank == 0
    reasons: list[str] = []

    if is_new_launch:
        _cap_score_map(
            scores,
            {
                "risk_elimination": 68,
                "psychology_benefit": 72,
                "differentiation": 74,
                "market_trend": 62,
            },
            reasons,
        )
        reasons.append("新品上架：无价格、无评论、无BSR/销售记录，只判断Listing承接，不按成熟销量模型放大。")

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
        reasons.append("价格缺失：可以做承接预检，但不能判断价格承接和广告承受力。")

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
        reasons.append("缺少评论数：不能证明信任承接和市场趋势。")

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
        reasons.append("缺少BSR：不能直接证明自然销量和市场趋势。")

    if not has_backend:
        _cap_score_map(scores, {"compatibility": 82, "product_identity": 86, "market_trend": 78}, reasons)
        reasons.append("后台Search Terms未提供，平台语义对齐不能按满链路确认。")

    meta = {
        "applied": bool(reasons),
        "review_count": review_count,
        "bsr_rank": bsr_rank,
        "bullet_count": bullet_count,
        "has_price": has_price,
        "is_new_launch": is_new_launch,
        "has_backend_keywords": has_backend,
        "reasons": reasons,
        "score_basis": "amazon_skill_10d_canonical",
    }
    return scores, meta


def align_amazon_skill_scores(scores: Any, product_data: Any) -> dict[str, Any]:
    """Return canonical, legacy-ASIN, and combined aliases after shared caps."""
    canonical_before_caps = normalize_canonical_scores(scores)
    canonical_scores, cap_meta = apply_market_reality_caps(canonical_before_caps, product_data)
    asin_scores = canonical_to_asin_scores(canonical_scores)
    return {
        "canonical_scores": canonical_scores,
        "asin_scores": asin_scores,
        "scores": {**asin_scores, **canonical_scores},
        "market_reality_caps": cap_meta,
    }
