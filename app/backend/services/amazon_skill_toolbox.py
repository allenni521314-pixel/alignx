"""
Amazon skill toolbox adapters for AlignX.

The toolbox is an internal orchestration layer. Public UI should receive plain
seller-facing guidance only; skill names, model routing, and internal standards
must stay out of the product surface.
"""

from __future__ import annotations

import re
from typing import Any


AMAZON_SKILL_GROUPS: dict[str, list[str]] = {
    "selection": [
        "amazon-product-research",
        "amazon-niche-finder",
        "amazon-sales-estimator",
        "amazon-trending-products",
        "amazon-seller-analytics",
        "amazon-brand-analytics",
    ],
    "listing": [
        "amazon-listing-optimization",
        "amazon-listing-images",
        "amazon-product-photography",
        "amazon-a-plus-content",
        "amazon-enhanced-brand-content",
        "amazon-backend-keywords",
        "amazon-search-optimization",
        "amazon-storefront-design",
        "amazon-international-listings",
        "amazon-variation-strategy",
        "amazon-product-bundling",
    ],
    "competition": [
        "amazon-competitor-analysis",
        "amazon-competitor-monitoring",
        "amazon-keyword-research",
        "amazon-rank-tracker",
    ],
    "ads": [
        "amazon-ppc-campaign",
        "amazon-advertising-strategy",
        "amazon-display-ads",
        "amazon-dayparting-strategy",
        "amazon-negative-keywords",
        "amazon-coupon-strategy",
        "amazon-deal-finder",
        "amazon-brand-tailored-promotions",
    ],
    "trust": [
        "amazon-review-analyzer",
        "amazon-review-strategy",
        "amazon-return-reduction",
        "amazon-product-compliance",
        "amazon-category-ungating",
        "amazon-brand-registry",
        "amazon-suspension-appeal",
        "amazon-vine-program",
    ],
    "commercial": [
        "amazon-fba-calculator",
        "amazon-profit-analyzer",
        "amazon-buy-box",
        "amazon-repricing-strategy",
        "amazon-inventory-management",
        "amazon-fba-prep",
        "amazon-shipping-calculator",
        "amazon-subscribe-save",
        "amazon-seasonal-planning",
        "amazon-global-selling",
        "amazon-private-label",
        "amazon-wholesale-sourcing",
        "tariff-calculator-amazon",
    ],
}

ALIGNX_CONTEXT_SKILL_GROUPS: dict[str, list[str]] = {
    "asin": ["selection", "competition", "ads", "trust", "commercial"],
    "asin_selection": ["selection", "competition", "ads", "trust", "commercial"],
    "competitor": ["competition", "listing", "ads", "trust"],
    "listing": ["listing", "ads", "trust"],
    "prelaunch": ["listing", "ads", "trust", "commercial"],
    "ad_validation": ["ads", "commercial", "trust"],
    "execution": ["ads", "commercial"],
    "feedback": ["trust", "ads", "listing", "commercial"],
}

PUBLIC_GROUP_LABELS: dict[str, str] = {
    "selection": "选品判断",
    "listing": "Listing承接",
    "competition": "竞品拆解",
    "ads": "广告验证",
    "trust": "评论与风险",
    "commercial": "利润与执行",
}

INTERNAL_TOOLBOX_KEYS = {
    "source_skills",
    "internal_skill_ids",
    "skill_ids",
    "internal_toolchain",
    "_internal",
}


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


def _parse_count(value: Any, fallback: int = 0) -> int:
    if value is None:
        return fallback
    if isinstance(value, (int, float)):
        return max(0, int(value))
    text = str(value).replace(",", "").strip()
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return fallback
    return max(0, int(float(match.group(0))))


def _parse_float(value: Any, fallback: float = 0) -> float:
    if value is None:
        return fallback
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return fallback
    return float(match.group(0))


def _clamp_score(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(round(value))))


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


def _context_groups(context: str) -> list[str]:
    return ALIGNX_CONTEXT_SKILL_GROUPS.get(context, ALIGNX_CONTEXT_SKILL_GROUPS["listing"])


def build_toolbox_invocation_plan(context: str = "asin") -> dict[str, Any]:
    """Return the internal toolbox routing plan plus a safe public summary."""
    groups = _context_groups(context)
    internal_ids: list[str] = []
    for group in groups:
        internal_ids.extend(AMAZON_SKILL_GROUPS.get(group, []))
    deduped_ids = list(dict.fromkeys(internal_ids))
    return {
        "context": context,
        "capability_groups": [PUBLIC_GROUP_LABELS.get(group, group) for group in groups],
        "public_summary": "系统会按当前业务场景调用对应运营能力，前台只展示诊断结论和下一步动作。",
        "internal_skill_ids": deduped_ids,
        "internal_group_count": len(groups),
        "internal_skill_count": len(deduped_ids),
    }


def _strip_internal_fields(value: Any) -> Any:
    if isinstance(value, list):
        return [_strip_internal_fields(item) for item in value]
    if not isinstance(value, dict):
        return value
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if key in INTERNAL_TOOLBOX_KEYS:
            continue
        cleaned[key] = _strip_internal_fields(item)
    return cleaned


_REVIEW_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "have", "has", "had",
    "are", "was", "were", "you", "your", "our", "out", "all", "but", "not", "very",
    "just", "more", "less", "than", "then", "they", "them", "its", "it's", "can",
    "will", "would", "could", "should", "about", "after", "before", "when", "what",
    "there", "their", "because", "only", "also", "really", "product", "item", "one",
}

_REVIEW_INTENT_PATTERNS: list[tuple[str, str, str]] = [
    ("odor removal", "task", r"\b(odor|odour|smell|stink|ammonia|deodor|fresh|scent)\b"),
    ("quiet operation", "attribute", r"\b(quiet|silent|noise|noisy|whisper)\b"),
    ("safe for pets", "risk", r"\b(cat|cats|dog|dogs|pet|pets|kid|kids|safe|ozone|chemical)\b"),
    ("easy setup", "task", r"\b(easy|simple|setup|install|use|clean|maintenance|filter)\b"),
    ("small space fit", "scenario", r"\b(small|compact|bathroom|bedroom|kitchen|room|apartment|car|closet|home)\b"),
    ("durability risk", "risk", r"\b(broke|broken|stopped|dead|defect|defective|cheap|quality|durable|last)\b"),
    ("battery or power", "attribute", r"\b(battery|charge|charger|power|plug|usb|cord|voltage)\b"),
    ("size and fit", "attribute", r"\b(size|fit|fits|large|small|dimension|space|room)\b"),
    ("water or leak risk", "risk", r"\b(leak|water|wet|spill|waterproof|moisture)\b"),
    ("value for money", "commercial", r"\b(price|expensive|cheap|value|worth|money|cost)\b"),
]

_POSITIVE_REVIEW_RE = re.compile(
    r"\b(works|worked|effective|great|love|loved|perfect|easy|quiet|safe|fresh|"
    r"recommend|helped|reduced|removed|excellent|happy|satisfied|worth)\b",
    re.I,
)
_NEGATIVE_REVIEW_RE = re.compile(
    r"\b(broke|broken|stopped|not work|doesn'?t work|didn'?t work|waste|return|"
    r"refund|disappointed|smell|odor|noisy|cheap|danger|unsafe|leak|defective)\b",
    re.I,
)


def _review_rating_value(value: Any) -> float:
    if isinstance(value, dict):
        for key in ("rating_value", "rating", "stars", "star_rating"):
            parsed = _review_rating_value(value.get(key))
            if parsed:
                return parsed
        return 0
    rating = _parse_float(value)
    return rating if 0 < rating <= 5 else 0


def _review_polarity(title: str, body: str, rating_value: float) -> str:
    text = f"{title} {body}".lower()
    if rating_value >= 4:
        return "positive"
    if 0 < rating_value <= 3:
        return "negative"
    pos = len(_POSITIVE_REVIEW_RE.findall(text))
    neg = len(_NEGATIVE_REVIEW_RE.findall(text))
    if neg > pos:
        return "negative"
    if pos > 0:
        return "positive"
    return "neutral"


def normalize_review_samples(value: Any, limit: int = 40) -> list[dict[str, Any]]:
    """Normalize browser/server review snippets into a stable evidence ledger."""
    samples: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _as_list(value):
        if isinstance(item, str):
            raw: dict[str, Any] = {"body": item}
        elif isinstance(item, dict):
            raw = item
        else:
            continue

        title = _text(raw.get("title") or raw.get("review_title")).strip()
        body = _text(raw.get("body") or raw.get("text") or raw.get("content") or raw.get("review")).strip()
        body = re.sub(r"\s+", " ", body)
        if not title and not body:
            continue
        rating_value = _review_rating_value(raw)
        fingerprint = re.sub(r"\W+", "", f"{title} {body}".lower())[:180]
        if not fingerprint or fingerprint in seen:
            continue
        seen.add(fingerprint)
        samples.append({
            "rating": str(raw.get("rating") or raw.get("stars") or raw.get("star_rating") or "").strip(),
            "rating_value": rating_value,
            "title": title[:240],
            "body": body[:1200],
            "date": _text(raw.get("date")).strip()[:120],
            "verified": bool(raw.get("verified")) if raw.get("verified") is not None else False,
            "helpful": _text(raw.get("helpful")).strip()[:120],
            "polarity": _review_polarity(title, body, rating_value),
            "source": "review_sample",
        })
        if len(samples) >= limit:
            break
    return samples


def _collect_review_samples(product_data: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for key in ("review_samples", "reviews", "positive_reviews", "low_star_reviews"):
        samples.extend(normalize_review_samples(product_data.get(key), limit=40))
    return normalize_review_samples(samples, limit=40)


def _review_terms(text: str, limit: int = 18) -> list[str]:
    words = [
        w.lower()
        for w in re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", text)
        if w.lower() not in _REVIEW_STOPWORDS
    ]
    phrases: list[str] = []
    for n in (3, 2):
        for i in range(max(0, len(words) - n + 1)):
            phrase = " ".join(words[i : i + n])
            if phrase not in phrases and not any(tok in _REVIEW_STOPWORDS for tok in phrase.split()):
                phrases.append(phrase)
            if len(phrases) >= limit:
                break
        if len(phrases) >= limit:
            break
    if len(phrases) < limit:
        for word in words:
            if word not in phrases:
                phrases.append(word)
            if len(phrases) >= limit:
                break
    return phrases[:limit]


def build_review_intent_assets(product_data: dict[str, Any]) -> dict[str, Any]:
    """Extract user-intent assets from review evidence for downstream diagnosis/ad validation."""
    samples = _collect_review_samples(product_data)
    positives = [item for item in samples if item.get("polarity") == "positive"]
    negatives = [item for item in samples if item.get("polarity") == "negative"]
    all_text = " ".join(f"{item.get('title', '')} {item.get('body', '')}" for item in samples)

    intent_keywords: list[dict[str, Any]] = []
    seen_keywords: set[str] = set()
    for label, kind, pattern in _REVIEW_INTENT_PATTERNS:
        matches = re.findall(pattern, all_text, flags=re.I)
        if not matches:
            continue
        polarity = "negative" if any(_NEGATIVE_REVIEW_RE.search(f"{item.get('title', '')} {item.get('body', '')}") for item in negatives) and kind == "risk" else "neutral"
        keyword = label
        if keyword in seen_keywords:
            continue
        seen_keywords.add(keyword)
        intent_keywords.append({
            "keyword": keyword,
            "type": kind,
            "polarity": polarity,
            "source": "review",
            "evidence_count": len(matches),
            "confidence": _clamp_score(55 + min(len(matches), 8) * 5),
        })

    positive_terms = _review_terms(" ".join(f"{item.get('title', '')} {item.get('body', '')}" for item in positives), 14)
    negative_terms = _review_terms(" ".join(f"{item.get('title', '')} {item.get('body', '')}" for item in negatives), 14)
    for term in positive_terms[:8]:
        if term not in seen_keywords:
            seen_keywords.add(term)
            intent_keywords.append({
                "keyword": term,
                "type": "buying_reason",
                "polarity": "positive",
                "source": "review",
                "evidence_count": 1,
                "confidence": 62,
            })
    for term in negative_terms[:8]:
        if term not in seen_keywords:
            seen_keywords.add(term)
            intent_keywords.append({
                "keyword": term,
                "type": "pain_point",
                "polarity": "negative",
                "source": "review",
                "evidence_count": 1,
                "confidence": 64,
            })

    buying_reasons: list[dict[str, Any]] = []
    if positive_terms:
        buying_reasons.append({
            "reason": "好评反复验证的购买触发点",
            "evidence_terms": positive_terms[:8],
            "maps_to": ["需求承接", "Listing承接"],
            "ad_metric": "CTR/CVR",
        })
    complaints: list[dict[str, Any]] = []
    if negative_terms:
        complaints.append({
            "complaint": "评论暴露的反购买风险",
            "severity": "high" if len(negatives) >= 4 else "medium",
            "evidence_terms": negative_terms[:8],
            "maps_to": ["风险消除", "验证参考"],
            "ad_metric": "CVR/ACOS/退货率",
        })

    ad_keywords = [
        {
            "keyword": item["keyword"],
            "keyword_type": "关系词" if item["type"] in {"scenario", "task"} else "状态词" if item["type"] == "risk" else "属性词",
            "hypothesis": "用评论证据验证该词是否能带来更高CTR/CVR且不恶化ACOS。",
            "metric": "CTR/CVR/ACOS",
        }
        for item in intent_keywords[:10]
    ]

    confidence = "high" if len(samples) >= 15 else "medium" if len(samples) >= 5 else "low"
    return {
        "schema": "alignx-review-intent-assets-v1",
        "sample_count": len(samples),
        "positive_sample_count": len(positives),
        "negative_sample_count": len(negatives),
        "intent_keywords": intent_keywords[:18],
        "buying_reasons": buying_reasons,
        "complaints": complaints,
        "feature_requests": [
            {"request": term, "source": "negative_review", "priority": "medium"}
            for term in negative_terms[:5]
        ],
        "listing_actions": [
            {"module": "bullets/images", "action": "把好评理由写成可验证承诺，把抱怨风险放进风险消除证据链。", "why": "评论是用户真实语言，不应只用标题和参数推断。"},
            {"module": "ads", "action": "把高频好评词与痛点词拆成小预算广告假设。", "why": "用CTR、CVR和ACOS验证评论意图是否能承接流量。"},
        ],
        "ad_validation_keywords": ad_keywords,
        "confidence": confidence,
        "notes": [] if samples else ["未获得评论样本，仅能使用标题/五点/图片等Listing证据。"],
    }


def build_asin_selection_assist(report: dict[str, Any] | None) -> dict[str, Any]:
    """Turn keyword-sales validation into business-facing selection signals.

    The output deliberately contains no skill/source names. It is safe to send
    to the UI as professional guidance while the internal playbooks stay hidden.
    """
    report = report or {}
    summary = report.get("keyword_rank_summary") if isinstance(report.get("keyword_rank_summary"), dict) else {}
    organic_strength = _parse_float(report.get("organic_rank_strength"))
    ad_risk = _parse_float(report.get("ad_dependency_risk"))
    score = _parse_float(report.get("keyword_sales_score"))
    opportunity_keywords = _keyword_pool({}, report.get("opportunity_keywords"))
    risk_keywords = _keyword_pool({}, report.get("risk_keywords"))
    suspicious = _as_list(report.get("suspicious_signals"))
    inventory_blocked = bool(summary.get("inventory_blocker"))

    if inventory_blocked:
        return {
            "entry_strategy": "先恢复可售再判断销量来源，当前不建议进入6维正向评分。",
            "six_dimension_calibration": [
                {
                    "dimension": "风险与趋势",
                    "signal": "库存/可售状态阻断",
                    "impact": "暂缓判断",
                    "reason": "无库存或不可售会扭曲自然位、广告位和销量来源判断。",
                }
            ],
            "validation_actions": ["补库存并确认页面可售后重新抓取", "重新验证核心词Top40自然位和广告位", "不要把当前销量缺口当作需求弱"],
            "keyword_expansion": risk_keywords[:6],
            "risk_followups": ["确认FBA/FBM可售状态、购物车和配送时效恢复正常"],
        }

    calibration: list[dict[str, str]] = []
    if organic_strength >= 75:
        calibration.append({
            "dimension": "搜索入口",
            "signal": "核心词自然位较强",
            "impact": "加分",
            "reason": "自然搜索能承接销量，说明语义入口和排名基础较好。",
        })
    elif organic_strength < 45:
        calibration.append({
            "dimension": "搜索入口",
            "signal": "自然位证据偏弱",
            "impact": "扣分/待验证",
            "reason": "需要确认销量是否来自广告、促销、站外或历史流量。",
        })

    if ad_risk >= 55:
        calibration.append({
            "dimension": "商业承受力",
            "signal": "广告依赖风险高",
            "impact": "扣分",
            "reason": "进入时需要更强毛利、CPC容忍度和长尾切入方案。",
        })
    elif ad_risk <= 25 and organic_strength >= 65:
        calibration.append({
            "dimension": "竞争结构",
            "signal": "广告压力相对可控",
            "impact": "加分",
            "reason": "自然入口更健康，正面竞争成本压力较小。",
        })

    if opportunity_keywords:
        calibration.append({
            "dimension": "差异化切口",
            "signal": "存在可测试机会词",
            "impact": "加分",
            "reason": "机会词可用于验证场景、属性或人群切入点。",
        })
    if suspicious:
        calibration.append({
            "dimension": "风险与趋势",
            "signal": "存在异常销量来源信号",
            "impact": "扣分/复查",
            "reason": "需要复核BSR、促销、广告位和评论增长是否一致。",
        })

    if score >= 75 and organic_strength >= 70 and ad_risk <= 35:
        entry_strategy = "可进入下一轮选品验证，优先围绕自然位强词做长尾切入。"
    elif ad_risk >= 55:
        entry_strategy = "先做小预算广告验证和毛利测算，不建议直接放量。"
    elif score < 55:
        entry_strategy = "暂不作为主机会，先补排名、BSR和广告位证据。"
    else:
        entry_strategy = "保留为观察候选，补充不同时段排名和促销/广告证据。"

    actions = [
        "用机会词复查Top40自然位，确认是否有低评论进入案例",
        "用同一组词检查Sponsored密度，估算首轮CPC压力",
        "把高意图机会词带入6维评分的搜索入口和差异化切口",
    ]
    if ad_risk >= 45:
        actions.append("拆出长尾词小预算测试，避免一开始正面打高竞争核心词")
    if suspicious:
        actions.append("复核BSR、Coupon/Deal和评论增长，排除促销或站外流量放大")

    return {
        "entry_strategy": entry_strategy,
        "six_dimension_calibration": calibration[:5],
        "validation_actions": actions[:6],
        "keyword_expansion": opportunity_keywords[:8],
        "risk_followups": risk_keywords[:6],
    }


def build_listing_toolbox(product_data: dict[str, Any], scores: dict[str, Any] | None = None) -> dict[str, Any]:
    """Selected listing rules from amazon-listing-optimization/images/A+/backend-keywords."""
    scores = scores or {}
    title = product_data.get("title") or ""
    bullets = _as_list(product_data.get("bullet_points"))
    image_count = _parse_count(product_data.get("image_count"), fallback=len(_as_list(product_data.get("image_urls"))))
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
        "role": "把诊断问题转成可执行的Listing修改建议。",
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
        "role": "把诊断结论转成小预算广告验证计划。",
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
    review_assets = build_review_intent_assets(product_data)
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
        "role": "把评论证据转成买家理由、抱怨和复盘动作。",
        "low_star_theme_candidates": themes[:6],
        "review_intent_assets": review_assets,
        "user_intent_keywords": review_assets.get("intent_keywords", [])[:12],
        "buying_reasons": review_assets.get("buying_reasons", []),
        "complaints": review_assets.get("complaints", []),
        "ad_validation_keywords": review_assets.get("ad_validation_keywords", [])[:10],
        "actions": [
            "把竞品低星痛点转成我方图片/五点/A+必须回答的问题。",
            "好评支撑的卖点才允许进入广告承诺；未被评论验证的强承诺降级为测试假设。",
            "退货/差评主题要回流到风险消除维度和副图证据链。",
        ],
    }


def build_competitor_toolbox(product_data: dict[str, Any], scores: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "source_skills": ["amazon-competitor-analysis", "amazon-competitor-monitoring", "amazon-keyword-research"],
        "role": "把竞品强弱点转成我方可测试机会。",
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
        "role": "把广告执行数据转成保留、暂停、优化或复测动作。",
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
    include_internal: bool = False,
) -> dict[str, Any]:
    product_data = product_data or {}
    scores = scores or {}
    groups = _context_groups(context)
    enabled: list[str] = []
    if "competition" in groups:
        enabled.append("competitor")
    if "listing" in groups:
        enabled.append("listing")
    if "ads" in groups:
        enabled.append("ppc")
    if "trust" in groups:
        enabled.append("review")
    if "commercial" in groups or context in {"execution", "ad_validation"}:
        enabled.append("execution")
    enabled = list(dict.fromkeys(enabled))
    plan = build_toolbox_invocation_plan(context)

    result: dict[str, Any] = {
        "principle": "按当前业务场景调用对应运营能力，前台只展示结论、原因、建议和下一步。",
        "context": context,
        "capability_groups": plan.get("capability_groups", []),
        "public_summary": plan.get("public_summary", ""),
        "internal_toolchain": plan,
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
    return result if include_internal else _strip_internal_fields(result)


def merge_toolbox_into_ad_validation_plan(plan: dict[str, Any] | None, toolbox: dict[str, Any]) -> dict[str, Any]:
    plan = dict(plan or {})
    ppc = toolbox.get("ppc") if isinstance(toolbox, dict) else None
    if not isinstance(ppc, dict):
        return plan
    plan.setdefault("toolbox_source", "诊断建议")
    plan.setdefault("toolbox_principle", "广告计划只验证本轮诊断假设，不替代最终投放判断。")
    if not plan.get("campaign_blueprint"):
        plan["campaign_blueprint"] = ppc.get("campaign_blueprint", [])
    if not plan.get("negative_seed"):
        plan["negative_seed"] = ppc.get("negative_seed", [])
    if not plan.get("feedback_rules"):
        plan["feedback_rules"] = ppc.get("feedback_rules", [])
    return plan
