"""
Deterministic precision and confidence scoring for AlignX diagnostics.

This module intentionally does not call an AI model. It turns input completeness
and sample-size rules into explainable confidence signals for every diagnosis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CheckRule:
    key: str
    label: str
    weight: int
    passed: bool
    severity: str
    reason: str
    recommendation: str


def _text_len(value: Any) -> int:
    return len(str(value or "").strip())


def _parse_number(value: Any) -> float:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[\d,.]+", str(value))
    if not match:
        return 0
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return 0


def _level(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _cn_level(level: str) -> str:
    return {"high": "高", "medium": "中", "low": "低"}.get(level, "低")


def _rule(
    key: str,
    label: str,
    weight: int,
    passed: bool,
    severity: str,
    reason: str,
    recommendation: str,
) -> CheckRule:
    return CheckRule(key, label, weight, passed, severity, reason, recommendation)


def assess_listing_diagnosis_input(listing: Any, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Score whether the available data can support a precise Listing diagnosis.

    The output is designed for both API consumers and UI display:
    - overall score and confidence level
    - per-source completeness
    - failed checks with reasons and recommendations
    - per-diagnosis confidence for the 3 AlignX alignment dimensions
    """

    context = context or {}
    title_len = _text_len(getattr(listing, "title", ""))
    bullet_len = _text_len(getattr(listing, "bullet_points", ""))
    desc_len = _text_len(getattr(listing, "description", ""))
    aplus_len = _text_len(getattr(listing, "a_plus_content", ""))
    image_len = _text_len(getattr(listing, "main_image_description", ""))
    category_len = _text_len(getattr(listing, "category", ""))
    price_len = _text_len(getattr(listing, "price", ""))
    keyword_len = _text_len(getattr(listing, "backend_keywords", ""))

    review_count = _parse_number(getattr(listing, "review_count", None) or context.get("review_count"))
    rating = _parse_number(getattr(listing, "rating", None) or context.get("rating"))
    bsr_rank = _parse_number(getattr(listing, "bsr_rank", None) or context.get("bsr_rank"))
    image_count = _parse_number(getattr(listing, "image_count", None) or context.get("image_count"))
    has_a_plus = bool(getattr(listing, "has_a_plus", False) or context.get("has_a_plus"))
    has_video = bool(getattr(listing, "has_video", False) or context.get("has_video"))
    top_competitor_count = int(_parse_number(context.get("top_competitor_count")))
    ad_clicks = _parse_number(context.get("ad_clicks"))
    ad_orders = _parse_number(context.get("ad_orders"))

    checks = [
        _rule(
            "title",
            "标题",
            12,
            title_len >= 50,
            "high",
            "标题长度和信息量足够支撑基础语义判断。" if title_len >= 50 else "标题过短，平台语义和点击相关性判断容易漂移。",
            "补充核心品类词、关键功能、适配对象或核心场景。",
        ),
        _rule(
            "bullets",
            "五点描述",
            14,
            bullet_len >= 250,
            "high",
            "五点描述信息较完整。" if bullet_len >= 250 else "五点描述信息不足，痛点承接和因果链判断置信度下降。",
            "补齐功能机制、场景、风险规避、信任证明和差异化。",
        ),
        _rule(
            "category",
            "类目路径",
            8,
            category_len > 0,
            "medium",
            "已有类目路径，可判断品类语义一致性。" if category_len else "缺少类目路径，平台语义对齐判断会变弱。",
            "补充Amazon类目路径或目标叶子类目。",
        ),
        _rule(
            "price",
            "价格",
            7,
            price_len > 0,
            "medium",
            "已有价格，可辅助判断承诺强度和价格带匹配。" if price_len else "缺少价格，无法判断价格是否匹配卖点承诺。",
            "补充当前售价、Coupon和目标价格带。",
        ),
        _rule(
            "images",
            "图片/A+素材",
            11,
            image_len > 0 or image_count > 0 or has_a_plus or has_video,
            "high",
            "已有图片或A+素材信号，可支撑图文一致性判断。" if (image_len > 0 or image_count > 0 or has_a_plus or has_video) else "缺少图片/A+输入，COSMO图文匹配只能低置信估计。",
            "补充主图、副图、A+和视频信息，至少提供图片数量或图片描述。",
        ),
        _rule(
            "backend_keywords",
            "搜索关键词",
            7,
            keyword_len > 0,
            "medium",
            "已有后台关键词，可判断关键词覆盖。" if keyword_len else "缺少后台关键词，搜索覆盖判断不完整。",
            "补充后台Search Terms、核心词和长尾词。",
        ),
        _rule(
            "review_sample",
            "评论样本量",
            15,
            review_count >= 50,
            "high",
            f"评论数约 {int(review_count)}，可支撑评论需求判断。" if review_count >= 50 else f"评论数约 {int(review_count)}，低于50条，评论需求判断置信度降低。",
            "补充Review/Q&A原文；评论不足时只作为假设，不作为强结论。",
        ),
        _rule(
            "rating",
            "评分",
            6,
            rating > 0,
            "low",
            "已有评分，可辅助信任判断。" if rating > 0 else "缺少评分，信任承接判断不完整。",
            "补充评分、星级分布和差评占比。",
        ),
        _rule(
            "competitors",
            "Top竞品",
            12,
            top_competitor_count >= 5,
            "high",
            f"已有 {top_competitor_count} 个竞品，可做同尺比较。" if top_competitor_count >= 5 else f"竞品数量为 {top_competitor_count}，不足以稳定判断市场标准。",
            "补齐Top10竞品ASIN、评分、评论数、价格带和核心卖点。",
        ),
        _rule(
            "ad_validation",
            "广告验证样本",
            8,
            ad_clicks >= 100 and ad_orders >= 10,
            "high",
            f"广告点击 {int(ad_clicks)}、订单 {int(ad_orders)}，可支撑转化验证。" if (ad_clicks >= 100 and ad_orders >= 10) else "广告点击低于100或订单低于10，转化因果结论仍是待验证假设。",
            "用小预算单独测试核心关键词，点击>=100且订单>=10后再提升结论置信度。",
        ),
    ]

    max_score = sum(c.weight for c in checks)
    earned = sum(c.weight for c in checks if c.passed)
    score = round(earned * 100 / max(max_score, 1))
    level = _level(score)

    failed = [c for c in checks if not c.passed]
    source_coverage = {
        "listing": round(sum(c.weight for c in checks[:6] if c.passed) * 100 / sum(c.weight for c in checks[:6])),
        "review": 100 if review_count >= 50 else (50 if review_count > 0 else 0),
        "competitor": min(100, round(top_competitor_count * 10)),
        "advertising": 100 if ad_clicks >= 100 and ad_orders >= 10 else (50 if ad_clicks > 0 else 0),
    }

    review_alignment_score = round((source_coverage["listing"] * 0.35) + (source_coverage["review"] * 0.65))
    semantic_alignment_score = round((source_coverage["listing"] * 0.75) + ((100 if image_len > 0 or image_count > 0 or has_a_plus else 0) * 0.25))
    causal_alignment_score = round((source_coverage["listing"] * 0.35) + (source_coverage["competitor"] * 0.25) + (source_coverage["advertising"] * 0.40))

    conclusion_confidence = {
        "review_alignment": {
            "score": review_alignment_score,
            "level": _level(review_alignment_score),
            "label": _cn_level(_level(review_alignment_score)),
            "reason": "由Listing完整度和评论样本量共同决定。",
        },
        "platform_semantic_alignment": {
            "score": semantic_alignment_score,
            "level": _level(semantic_alignment_score),
            "label": _cn_level(_level(semantic_alignment_score)),
            "reason": "由文本、类目、关键词、图片/A+输入共同决定。",
        },
        "causal_conversion_alignment": {
            "score": causal_alignment_score,
            "level": _level(causal_alignment_score),
            "label": _cn_level(_level(causal_alignment_score)),
            "reason": "由Listing完整度、竞品样本和广告验证样本共同决定。",
        },
    }

    return {
        "score": score,
        "level": level,
        "label": _cn_level(level),
        "summary": f"数据完整性{score}/100，当前诊断置信度为{_cn_level(level)}。每条结论应按置信度使用，低置信项优先补数据或做广告验证。",
        "source_coverage": source_coverage,
        "checks": [c.__dict__ for c in checks],
        "failed_checks": [c.__dict__ for c in failed],
        "missing_fields": [c.label for c in failed],
        "recommendations": [c.recommendation for c in failed[:5]],
        "conclusion_confidence": conclusion_confidence,
        "raw_inputs": {
            "review_count": int(review_count),
            "rating": rating,
            "bsr_rank": int(bsr_rank),
            "image_count": int(image_count),
            "top_competitor_count": top_competitor_count,
            "ad_clicks": int(ad_clicks),
            "ad_orders": int(ad_orders),
        },
    }
