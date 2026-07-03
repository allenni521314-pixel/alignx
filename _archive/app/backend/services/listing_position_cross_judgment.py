from __future__ import annotations

import re
from typing import Any


POSITION_DIMENSION_MAP: dict[str, list[str]] = {
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


def _safe_text(value: Any) -> str:
    if value is None:
        return "暂无"
    if isinstance(value, str):
        text = value.strip()
        return text or "暂无"
    if isinstance(value, list):
        items = [_safe_text(item) for item in value]
        items = [item for item in items if item != "暂无"]
        return "；".join(items) or "暂无"
    if isinstance(value, dict):
        items = [_safe_text(item) for item in value.values()]
        items = [item for item in items if item != "暂无"]
        return "；".join(items) or "暂无"
    return str(value).strip() or "暂无"


def _clamp_score(value: Any) -> int:
    try:
        number = round(float(value or 0))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, number))


def _score_100(value: Any) -> int:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0
    if 0 < number <= 10:
        number *= 10
    return _clamp_score(number)


def _avg_dimension_scores(scores: dict[str, Any], keys: list[str]) -> int:
    values = [_score_100(scores.get(key)) for key in keys if _score_100(scores.get(key)) > 0]
    return _clamp_score(sum(values) / len(values)) if values else 0


def _position_final_score(cross_scores: dict[str, int]) -> int:
    amazon = _score_100(cross_scores.get("amazon_rule_score"))
    cosmo = _score_100(cross_scores.get("cosmo_alignment_score"))
    buyer_language = _score_100(cross_scores.get("buyer_language_score"))
    weighted = _clamp_score((amazon * 0.3) + (cosmo * 0.35) + (buyer_language * 0.35))
    if min(amazon, cosmo, buyer_language) < 60:
        return min(weighted, 59)
    if min(amazon, cosmo, buyer_language) < 80:
        return min(weighted, 79)
    return weighted


def _parse_count(value: Any) -> int:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else 0


def _split_bullets(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"\n+", value or "") if item.strip()]


def _buyer_language_has_text(value: Any) -> bool:
    if isinstance(value, list):
        return any(_buyer_language_has_text(item) for item in value)
    text = str(value or "").strip()
    return bool(text and text not in {"暂无", "待录入"})


def _violation_penalty(amazon_compliance: dict[str, Any], module: str) -> int:
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


def _content_present(facts: dict[str, Any]) -> bool:
    return bool(facts.get("content_present"))


def _amazon_position_rule_score(facts: dict[str, Any], data: dict[str, Any], module: str) -> int:
    if not _content_present(facts):
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
        count = _clamp_score(facts.get("bullet_count"))
        score = 90 if count >= 5 else 70 if count > 0 else 0
    return _clamp_score(score - _violation_penalty(data.get("amazon_compliance") or {}, module))


def _buyer_language_position_score(data: dict[str, Any], module: str, facts: dict[str, Any]) -> int:
    if not _content_present(facts):
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


def _position_ad_validation(data: dict[str, Any], module: str) -> dict[str, Any]:
    plan = data.get("ad_validation_plan") if isinstance(data.get("ad_validation_plan"), dict) else {}
    items = plan.get("validation_items") if isinstance(plan.get("validation_items"), list) else []
    module_index = {"title": 0, "highlights": 0, "main_image": 1, "secondary_images": 2, "bullets": 3, "a_plus": 4}.get(module, 0)
    item = items[module_index] if module_index < len(items) and isinstance(items[module_index], dict) else {}
    keywords = []
    for value in (
        item.get("ad_test_keywords"),
        item.get("validation_keywords"),
        item.get("keywords"),
        (item.get("ad_action") or {}).get("keywords"),
    ):
        _collect_keywords(value, keywords)
    if not keywords:
        _collect_keywords((data.get("ad_keywords") or {}).get("high_conversion"), keywords)
        _collect_keywords((data.get("ad_keywords") or {}).get("traffic"), keywords)
        _collect_keywords((data.get("ad_keywords") or {}).get("long_tail"), keywords)
        _collect_keywords((data.get("suggestions") or {}).get("backend_keywords_addition"), keywords)
        coverage = data.get("keyword_coverage") if isinstance(data.get("keyword_coverage"), dict) else {}
        missing = coverage.get("missing_categories") if isinstance(coverage.get("missing_categories"), dict) else {}
        for values in missing.values():
            _collect_keywords(values, keywords)
    hypothesis = _safe_text(item.get("hypothesis"))
    if re.search(r"Listing补强|对应搜索词点击|对应搜索词.*转化|点击和转化应提升|验证Listing是否承接", hypothesis):
        hypothesis = "暂无"
    return {
        "hypothesis": hypothesis,
        "keywords": keywords[:8],
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


def _indexed_text(value: Any, index: int) -> str:
    if isinstance(value, list):
        return _safe_text(value[index]) if len(value) > index else "暂无"
    if isinstance(value, dict):
        for key in (str(index), f"image_{index + 1}", f"aplus_{index + 1}", f"position_{index + 1}"):
            if key in value:
                return _safe_text(value.get(key))
    if index == 0:
        return _safe_text(value)
    return "暂无"


def _position_suggestion(data: dict[str, Any], module: str, index: int = 0) -> str:
    suggestions = data.get("suggestions") if isinstance(data.get("suggestions"), dict) else {}
    if module == "title":
        return _safe_text(suggestions.get("title_rewrite"))
    if module == "highlights":
        return _safe_text(suggestions.get("item_highlights") or suggestions.get("highlights") or suggestions.get("highlight_suggestion"))
    if module == "bullets":
        return _safe_text(suggestions.get("bullet_points_optimization"))
    if module == "a_plus":
        return _indexed_text(suggestions.get("a_plus_suggestions"), max(0, index - 1))
    if module in {"main_image", "secondary_images"}:
        return _indexed_text(suggestions.get("image_suggestions"), index)
    return "暂无"


def _source_facts(payload: dict[str, Any], module: str, index: int = 0) -> dict[str, Any]:
    if module == "title":
        text = str(payload.get("title") or "")
        return {"source": "amazon_listing_data", "field": "title", "content_present": bool(text.strip()), "text": text or "暂无"}
    if module == "highlights":
        text = str(payload.get("item_highlights") or "")
        return {"source": "amazon_listing_data", "field": "item_highlights", "content_present": bool(text.strip()), "text": text or "暂无"}
    if module == "bullets":
        text = str(payload.get("bullet_points") or "")
        bullets = _split_bullets(text)
        return {"source": "amazon_listing_data", "field": "bullet_points", "content_present": bool(bullets), "bullet_count": len(bullets), "text": text or "暂无"}
    if module == "main_image":
        urls = payload.get("image_urls") if isinstance(payload.get("image_urls"), list) else []
        url = urls[0] if urls else ""
        texts = payload.get("main_image_texts") if isinstance(payload.get("main_image_texts"), list) else []
        text = str((texts[0] if texts else "") or payload.get("main_image_description") or "")
        return {"source": "amazon_listing_data", "field": "image_urls[0]", "content_present": bool(url or text), "image_url": url or "暂无", "text": text or "暂无"}
    if module == "secondary_images":
        urls = payload.get("image_urls") if isinstance(payload.get("image_urls"), list) else []
        url = urls[index] if len(urls) > index else ""
        texts = payload.get("main_image_texts") if isinstance(payload.get("main_image_texts"), list) else []
        text = texts[index] if len(texts) > index else ""
        return {"source": "amazon_listing_data", "field": f"image_urls[{index}]", "content_present": bool(url or text), "image_url": url or "暂无", "text": text or "暂无"}
    if module == "a_plus":
        image_index = max(0, index - 1)
        urls = payload.get("aplus_image_urls") if isinstance(payload.get("aplus_image_urls"), list) else []
        url = urls[image_index] if len(urls) > image_index else ""
        texts = payload.get("a_plus_image_texts") if isinstance(payload.get("a_plus_image_texts"), list) else []
        text = texts[image_index] if len(texts) > image_index else str(payload.get("a_plus_content") or "")
        return {"source": "amazon_listing_data", "field": f"aplus_image_urls[{image_index}]", "content_present": bool(url or text), "image_url": url or "暂无", "text": text or "暂无"}
    return {"source": "amazon_listing_data", "content_present": False}


def build_listing_position_diagnosis(data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    alignment = (data.get("judgment_system") or {}).get("alignment_scores") if isinstance(data.get("judgment_system"), dict) else {}
    platform_score = _score_100((alignment or {}).get("platform_semantic_alignment"))

    def row(label: str, module: str, key: str, focus: str, index: int = 0) -> dict[str, Any]:
        facts = _source_facts(payload, module, index)
        dimension_keys = POSITION_DIMENSION_MAP.get(key) or POSITION_DIMENSION_MAP.get(module) or []
        mapped_score = _avg_dimension_scores(scores, dimension_keys)
        cosmo_score = _clamp_score(mapped_score * 0.7 + platform_score * 0.3) if platform_score and mapped_score else mapped_score
        cross_scores = {
            "amazon_rule_score": _amazon_position_rule_score(facts, data, module),
            "cosmo_alignment_score": cosmo_score,
            "buyer_language_score": _buyer_language_position_score(data, module, facts),
        }
        final_score = _position_final_score(cross_scores) if cross_scores else 0
        return {
            "id": f"{module}-{index}",
            "label": label,
            "module": module,
            "position_key": key,
            "index": index,
            "focus": focus,
            "source_facts": facts,
            **cross_scores,
            "final_score": final_score,
            "status": "优秀" if final_score >= 80 else "待优化",
            "dimension_keys": dimension_keys,
            "problem": _position_problem_from_scores(cross_scores),
            "optimization_suggestion": _position_suggestion(data, module, index),
            "ad_validation": _position_ad_validation(data, module),
        }

    positions = [
        row("标题", "title", "title", "title"),
        row("亮点差异化", "highlights", "highlights", "item-highlights"),
        row("5点描述", "bullets", "bullets", "bullets"),
    ]
    image_count = min(9, max(len(payload.get("image_urls") or []), _parse_count(payload.get("image_count")), _clamp_score(payload.get("main_image_count"))))
    if image_count > 0:
        positions.append(row("主图", "main_image", "main_image", "main-images", 0))
        for image_index in range(1, image_count):
            positions.append(row(f"副图{image_index}", "secondary_images", f"secondary_{image_index}", "main-images", image_index))
    aplus_text_count = re.search(r"A\+图片数[:：]\s*(\d+)", str(payload.get("a_plus_content") or ""), re.I)
    aplus_count = max(
        len(payload.get("aplus_image_urls") or []),
        _parse_count(payload.get("aplus_image_count")),
        int(aplus_text_count.group(1)) if aplus_text_count else 0,
        _clamp_score(payload.get("a_plus_image_count")),
    )
    for aplus_index in range(1, min(aplus_count, 9) + 1):
        positions.append(row(f"A+图{aplus_index}", "a_plus", f"aplus_{aplus_index}", "aplus-images", aplus_index))

    return {
        "basis": "amazon_rule_cosmo_buyer_language_position_cross",
        "threshold": 80,
        "positions": positions,
    }
