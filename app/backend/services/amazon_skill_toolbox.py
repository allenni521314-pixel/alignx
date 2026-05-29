"""
Amazon skill toolbox adapters for AlignX.

These helpers intentionally do not replace the COSMO/8D+2 judgment layer.
They convert selected Amazon-Skills playbooks into downstream execution hints
that can be attached to existing ASIN, Listing, ad validation, and execution
modules.
"""

from __future__ import annotations

import re
from typing import Any


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if item)
    if isinstance(value, dict):
        return "\n".join(str(v) for v in value.values() if v)
    return str(value)


def _word_count(value: Any) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", _text(value)))


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _keyword_pool(product_data: dict[str, Any], fallback_keywords: Any = None) -> list[str]:
    raw = fallback_keywords or product_data.get("main_keywords") or []
    if isinstance(raw, str):
        raw = re.split(r"[,;\n]+", raw)
    result: list[str] = []
    seen: set[str] = set()
    for item in raw if isinstance(raw, list) else []:
        kw = str(item or "").strip().lower()
        if not kw or re.search(r"[\u4e00-\u9fff]", kw):
            continue
        kw = re.sub(r"[^a-z0-9\s+&/-]", " ", kw)
        kw = re.sub(r"\s+", " ", kw).strip(" -/&")
        if kw and kw not in seen:
            result.append(kw)
            seen.add(kw)
        if len(result) >= 12:
            break
    return result


def build_listing_toolbox(product_data: dict[str, Any], scores: dict[str, Any] | None = None) -> dict[str, Any]:
    """Selected listing rules from amazon-listing-optimization/images/A+/backend-keywords."""
    scores = scores or {}
    title = product_data.get("title") or ""
    bullets = _as_list(product_data.get("bullet_points"))
    image_count = int(float(str(product_data.get("image_count") or len(_as_list(product_data.get("image_urls"))) or 0).replace(",", "") or 0))
    has_aplus = bool(product_data.get("has_a_plus") or product_data.get("aplus_content") or product_data.get("a_plus_content"))
    keywords = _keyword_pool(product_data)

    issues: list[dict[str, str]] = []
    actions: list[dict[str, str]] = []

    if _word_count(title) < 8:
        issues.append({"module": "title", "issue": "标题商品身份承载不足", "maps_to": "product_identity"})
        actions.append({"module": "title", "action": "按 Brand + Core Product + Key Attribute + Use Case 重组标题。"})
    if len(bullets) < 4:
        issues.append({"module": "bullets", "issue": "五点购买理由不足", "maps_to": "functionality/risk_elimination"})
        actions.append({"module": "bullets", "action": "五点分别承接功能、效果、场景、信任、售后/风险消除。"})
    if image_count < 6:
        issues.append({"module": "images", "issue": "图库证据链偏短", "maps_to": "scenario/risk_elimination"})
        actions.append({"module": "images", "action": "补齐主图点击、卖点、场景、尺寸、对比、安全/材质、使用步骤。"})
    if not has_aplus:
        issues.append({"module": "a_plus", "issue": "A+信任闭环缺失", "maps_to": "emotional/differentiation"})
        actions.append({"module": "a_plus", "action": "用A+补品牌、技术原理、对比表、场景教育和售后信任。"})
    if scores.get("risk_elimination", 100) < 65:
        issues.append({"module": "risk", "issue": "风险消除维度偏弱", "maps_to": "risk_elimination"})
        actions.append({"module": "reviews/images", "action": "把尺寸、材质、兼容性、耐用性和售后承诺放进图片/五点/A+证据链。"})

    return {
        "source_skills": [
            "amazon-listing-optimization",
            "amazon-listing-images",
            "amazon-a-plus-content",
            "amazon-backend-keywords",
        ],
        "role": "下游Listing执行工具箱，不改写COSMO/8D+2主评分。",
        "issues": issues[:6],
        "actions": actions[:8],
        "keyword_coverage_hint": {
            "candidate_keywords": keywords[:10],
            "rule": "前台已覆盖词不要重复塞后台；后台Search Terms优先放次级词、同义词、长尾关系词和状态触发词。",
        },
    }


def build_ppc_toolbox(product_data: dict[str, Any], scores: dict[str, Any] | None = None) -> dict[str, Any]:
    """Selected PPC rules from amazon-ppc-campaign/negative-keywords/ad strategy."""
    scores = scores or {}
    keywords = _keyword_pool(product_data)
    exact = keywords[:5]
    broad = keywords[5:10] or keywords[:5]
    problems: list[dict[str, str]] = []
    if scores.get("product_identity", 100) < 65:
        problems.append({"issue": "商品身份分偏低，Exact广告可能拿不到准流量", "validation": "先小预算测核心身份词CTR和CVR。"})
    if scores.get("risk_elimination", 100) < 65:
        problems.append({"issue": "风险消除偏弱，点击后转化承接可能不足", "validation": "观察高CTR低CVR词，回流副图/五点/A+。"})

    return {
        "source_skills": ["amazon-ppc-campaign", "amazon-negative-keywords", "amazon-advertising-strategy"],
        "role": "把主诊断结论转成广告验证，不作为独立判断体系。",
        "campaign_blueprint": [
            {"campaign": "Auto Discovery", "purpose": "发现真实search term，验证平台把商品放进哪个语义池。"},
            {"campaign": "Manual Exact", "keywords": exact, "purpose": "验证核心身份词是否能高相关曝光和转化。"},
            {"campaign": "Manual Broad", "keywords": broad, "purpose": "探索场景词、属性词、长尾任务词。"},
            {"campaign": "Product Targeting", "purpose": "用竞品ASIN页面验证差异化切入点。"},
        ],
        "negative_seed": ["free", "cheap", "used", "diy", "review", "reddit", "manual", "replacement parts"],
        "feedback_rules": [
            {"signal": "高CTR低CVR", "meaning": "标题/主图吸引点击，但副图、五点、A+、价格或评论承接不足。"},
            {"signal": "低CTR高CVR", "meaning": "页面承接强，但标题/主图没有把对的人吸进来。"},
            {"signal": "高CPC低订单", "meaning": "词太宽、竞争太强或Listing证据链不够。"},
            {"signal": "低曝光高CVR", "meaning": "语义池太窄，需要扩相邻任务词/场景词。"},
        ],
        "diagnosis_warnings": problems,
    }


def build_review_toolbox(product_data: dict[str, Any]) -> dict[str, Any]:
    """Selected review rules from amazon-review-analyzer/return-reduction."""
    low_reviews = _as_list(product_data.get("low_star_reviews"))
    themes: list[str] = []
    review_text = _text(low_reviews).lower()
    for label, pattern in [
        ("durability", r"break|broken|stopped working|durable|quality"),
        ("size_fit", r"size|small|large|fit|dimension"),
        ("battery_power", r"battery|charge|power"),
        ("material_safety", r"smell|odor|material|safe|bpa"),
        ("shipping_packaging", r"package|shipping|arrived|box"),
    ]:
        if re.search(pattern, review_text):
            themes.append(label)

    return {
        "source_skills": ["amazon-review-analyzer", "amazon-return-reduction", "amazon-review-strategy"],
        "role": "评论只作为证据链和复盘材料，不替代主评分。",
        "low_star_theme_candidates": themes[:6],
        "actions": [
            "把竞品低星痛点转成我方图片/五点/A+必须回答的问题。",
            "好评支撑的卖点才允许进入广告承诺；未被评论验证的强承诺降级为测试假设。",
            "退货/差评主题要回流到风险消除维度和副图证据链。",
        ],
    }


def build_competitor_toolbox(product_data: dict[str, Any], scores: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "source_skills": ["amazon-competitor-analysis", "amazon-competitor-monitoring", "amazon-keyword-research"],
        "role": "竞品工具箱只提炼可测试机会，不照搬竞品。",
        "semantic_gap_questions": [
            "竞品标题是否比我方更清楚表达商品身份？",
            "竞品图片是否证明了一个我方没有证明的用户任务？",
            "竞品差评是否暴露我方可攻击的风险点？",
            "竞品A+是否承担了品牌信任或技术解释，而不是重复前台图片？",
        ],
        "borrow_as_hypothesis": [
            "借鉴词序，不借品牌词。",
            "借鉴证据链结构，不复制图文。",
            "借鉴差评切口，必须用广告小预算验证。",
        ],
        "keyword_pool": _keyword_pool(product_data),
    }


def build_execution_toolbox(ad_result: dict[str, Any] | None = None) -> dict[str, Any]:
    ad_result = ad_result or {}
    return {
        "source_skills": ["amazon-ppc-campaign", "amazon-negative-keywords", "amazon-profit-analyzer"],
        "role": "执行复盘工具箱用于解释广告结果并回流主判断。",
        "review_cadence": ["第7天看CTR/CPC/点击质量", "第14天看CVR/ACoS/订单", "第30天决定放量、否词或重写Listing"],
        "required_metrics": ["impressions", "clicks", "ctr", "cpc", "orders", "cvr", "acos", "spend", "sales"],
        "action_rules": [
            "20+点击无订单：先检查词意图和页面承接，再决定否词或降bid。",
            "ACoS高于目标10%以上：降bid或切长尾词，不直接扩大预算。",
            "低曝光高转化：扩相邻任务词和场景词。",
            "高花费零订单：加入否词候选并回看图片/五点/A+承接。",
        ],
        "observed_input": {k: ad_result.get(k) for k in ("ctr", "cpc", "orders", "cvr", "acos", "spend", "sales") if k in ad_result},
    }


def build_toolbox_enhancements(
    product_data: dict[str, Any] | None = None,
    scores: dict[str, Any] | None = None,
    context: str = "asin",
    ad_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    product_data = product_data or {}
    scores = scores or {}
    enabled = {
        "asin": ["competitor", "listing", "ppc", "review"],
        "competitor": ["competitor", "listing", "ppc", "review"],
        "listing": ["listing", "ppc", "review"],
        "prelaunch": ["listing", "ppc"],
        "ad_validation": ["ppc", "execution"],
        "execution": ["execution"],
    }.get(context, ["listing", "ppc"])

    result: dict[str, Any] = {
        "principle": "工具箱按需调用；AlignX COSMO/8D+2仍是主判断结构。",
        "context": context,
    }
    if "competitor" in enabled:
        result["competitor"] = build_competitor_toolbox(product_data, scores)
    if "listing" in enabled:
        result["listing"] = build_listing_toolbox(product_data, scores)
    if "ppc" in enabled:
        result["ppc"] = build_ppc_toolbox(product_data, scores)
    if "review" in enabled:
        result["review"] = build_review_toolbox(product_data)
    if "execution" in enabled:
        result["execution"] = build_execution_toolbox(ad_result)
    return result


def merge_toolbox_into_ad_validation_plan(plan: dict[str, Any] | None, toolbox: dict[str, Any]) -> dict[str, Any]:
    plan = dict(plan or {})
    ppc = toolbox.get("ppc") if isinstance(toolbox, dict) else None
    if not isinstance(ppc, dict):
        return plan
    plan.setdefault("toolbox_source", "amazon-ppc-campaign")
    plan.setdefault("toolbox_principle", "广告计划只验证主诊断假设，不改写主判断。")
    if not plan.get("campaign_blueprint"):
        plan["campaign_blueprint"] = ppc.get("campaign_blueprint", [])
    if not plan.get("negative_seed"):
        plan["negative_seed"] = ppc.get("negative_seed", [])
    if not plan.get("feedback_rules"):
        plan["feedback_rules"] = ppc.get("feedback_rules", [])
    return plan
