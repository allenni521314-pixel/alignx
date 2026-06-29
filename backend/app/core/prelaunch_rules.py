from __future__ import annotations

"""Deterministic guardrails for Prelaunch / Listing readiness results."""

from copy import deepcopy
import re
from typing import Any


TITLE_MAX = 75
ITEM_HIGHLIGHT_MAX = 125

HIGH_RISK_ALTERNATIVES: dict[str, str] = {
    "safe for pets": "Made for pet areas",
    "safe for cats": "Made for litter box areas",
    "safe for dogs": "Made for pet spaces",
    "safe for family": "Made for everyday home areas",
    "no harmful ozone": "No ozone design",
    "no ozone emissions": "No ozone design",
    "non-toxic": "No fragrance refills",
    "chemical-free": "No fragrance refills",
    "no harsh chemicals": "No heavy fragrance or spray cover-ups",
    "kills bacteria": "Helps reduce everyday odors",
    "kills germs": "Helps reduce everyday odors",
    "disinfects": "Helps reduce everyday odors",
    "sterilizes": "Helps reduce everyday odors",
    "100% odor removal": "Helps reduce everyday odors",
    "completely eliminates odors": "Helps reduce everyday odors",
    "eliminates odors": "Helps reduce everyday odors",
    "odor-free home": "Fresher odor-prone spaces",
    "guaranteed freshness": "Helps freshen odor-prone spaces",
    "works while pets are present": "No room-clearing ozone routine",
    "naturally removes odors": "Freshens small pet spaces",
    "medical grade": "待录入",
    "hypoallergenic": "待录入",
    "purifies all air": "Freshens small odor-prone spaces",
    "whole home odor removal": "Best for small odor-prone spaces",
    "every corner of your home": "Small odor-prone spaces",
}

PRIMARY_SEARCH_TERMS = [
    "pet odor eliminator",
    "litter box odor eliminator",
    "cat litter odor eliminator",
    "pet odor air purifier",
]

DIFFERENTIATION_TERMS = ["no ozone", "ozone free", "no filters", "no refills", "no fragrance"]
PLACEMENT_TERMS = ["usb powered", "wall mount", "small spaces", "bathroom", "closet", "shoe cabinet", "pet cage"]

A_PLUS_MODULES = [
    ("aplus_1", "A+1 Brand Hero", "建立品牌和产品第一印象", "missing_required_module"),
    ("aplus_2", "A+2 Differentiation Comparison", "解释为什么不是传统除味方案", "missing_required_module"),
    ("aplus_3", "A+3 Benefit Deep Dive 1", "强化 No Ozone 或无臭氧设计", "missing_required_module"),
    ("aplus_4", "A+4 Benefit Deep Dive 2", "强化 No Filters / No Refills", "missing_required_module"),
    ("aplus_5", "A+5 Benefit Deep Dive 3", "强化安装便利", "missing_required_module"),
    ("aplus_6", "A+6 Technical Specs", "提供可信参数", "missing_required_module"),
    ("aplus_7", "A+7 Usage Scenarios", "说明适用小空间", "missing_required_module"),
    ("aplus_8", "A+8 Certification & Warranty", "建立认证、质保和支持信任", "missing_required_trust_module"),
    ("aplus_9", "A+9 FAQ & After-Sales", "解除购买前疑虑和售后疑虑", "missing_required_faq_module"),
]


def apply_prelaunch_rules(ai_result: dict[str, Any], materials: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(ai_result or {})
    result.setdefault("position_diagnoses", [])
    result["position_diagnoses"] = _normalize_diagnoses(result.get("position_diagnoses"))

    hard_blockers: list[dict[str, Any]] = []
    title_analysis = _title_analysis(materials.get("title_draft") or "")
    result["title_analysis"] = title_analysis
    _upsert_position(result["position_diagnoses"], _title_position(title_analysis))
    if title_analysis["is_over_limit"]:
        hard_blockers.append({"type": "title_over_75_characters", "position": "title"})

    item_highlight_analysis = _item_highlight_analysis(materials.get("key_highlights") or "", title_analysis)
    result["item_highlight_analysis"] = item_highlight_analysis
    _upsert_position(result["position_diagnoses"], _highlight_position(item_highlight_analysis))

    claim_analysis = _claim_risk_analysis(materials)
    result["claim_risk_analysis"] = claim_analysis
    if claim_analysis["risk_level"] == "high":
        hard_blockers.append({"type": "high_risk_claim_without_evidence", "position": "listing_text"})

    image_blocker = _main_image_guardrail(materials)
    if image_blocker:
        hard_blockers.append({"type": "main_image_non_compliant", "position": "main_image"})
        _upsert_position(result["position_diagnoses"], image_blocker)

    a_plus_analysis = _a_plus_analysis(materials)
    result["a_plus_analysis"] = a_plus_analysis
    for module in a_plus_analysis:
        _upsert_position(result["position_diagnoses"], _a_plus_position(module))
        if module["module"] in {"A+8 Certification & Warranty", "A+9 FAQ & After-Sales"} and not module["uploaded"]:
            hard_blockers.append({"type": module["status"], "position": module["position_id"]})

    result["position_diagnoses"] = [_sanitize_diagnosis(d) for d in result["position_diagnoses"]]
    result["hard_blockers"] = hard_blockers
    result["overall_status"] = _overall_status(hard_blockers)
    result["admission_result"] = _admission_result(result["overall_status"])
    result["conclusion"] = _overall_summary(result["overall_status"], hard_blockers)
    result["next_action"] = _next_action(hard_blockers)
    return result


def _normalize_diagnoses(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _visible_texts(materials: dict[str, Any]) -> list[str]:
    texts = [
        materials.get("title_draft") or "",
        materials.get("key_highlights") or "",
        *[x or "" for x in materials.get("bullet_points") or []],
    ]
    ocr_texts = materials.get("ocr_texts") or {}
    if isinstance(ocr_texts, dict):
        texts.extend(str(v) for v in ocr_texts.values() if v)
    return texts


def _find_risk_phrases(text: str) -> list[str]:
    lowered = (text or "").lower()
    return [phrase for phrase in HIGH_RISK_ALTERNATIVES if phrase in lowered]


def _sanitize_text(text: str) -> tuple[str, list[str]]:
    result = text or ""
    replaced: list[str] = []
    for phrase, alternative in HIGH_RISK_ALTERNATIVES.items():
        if phrase in result.lower():
            result = re.sub(re.escape(phrase), alternative, result, flags=re.I)
            replaced.append(phrase)
    return result, replaced


def _title_analysis(title: str) -> dict[str, Any]:
    clean_title, replaced = _sanitize_text(title)
    suggested = _suggest_title(clean_title)
    lowered = clean_title.lower()
    kept = [term for term in PRIMARY_SEARCH_TERMS + DIFFERENTIATION_TERMS if term in lowered]
    moved_highlight = [term for term in PLACEMENT_TERMS if term in lowered and len(suggested) + len(term) + 2 > TITLE_MAX]
    moved_bullets = [term for term in PLACEMENT_TERMS if term in lowered and term not in moved_highlight]
    return {
        "current_title": title,
        "character_count": len(title),
        "max_characters": TITLE_MAX,
        "is_over_limit": len(title) > TITLE_MAX,
        "kept_keywords": kept,
        "missing_keywords": [term for term in PRIMARY_SEARCH_TERMS if term not in lowered],
        "moved_to_item_highlight": moved_highlight,
        "moved_to_bullets": moved_bullets,
        "suggested_title": suggested,
        "suggested_title_character_count": len(suggested),
        "title_tradeoff_reason": "Title must stay within 75 characters and remain readable.",
        "replaced_risk_phrases": replaced,
    }


def _suggest_title(title: str) -> str:
    title = " ".join((title or "").split())
    if len(title) <= TITLE_MAX:
        return title
    parts = [p.strip() for p in re.split(r"[,;|]", title) if p.strip()]
    if not parts:
        return title[:TITLE_MAX].rstrip(" ,;-")
    suggestion = parts[0]
    for part in parts[1:]:
        candidate = f"{suggestion}, {part}"
        if len(candidate) <= TITLE_MAX:
            suggestion = candidate
    if len(suggestion) <= TITLE_MAX:
        return suggestion
    words = suggestion.split()
    while words and len(" ".join(words)) > TITLE_MAX:
        words.pop()
    return " ".join(words)[:TITLE_MAX].rstrip(" ,;-")


def _item_highlight_analysis(text: str, title_analysis: dict[str, Any]) -> dict[str, Any]:
    clean, replaced = _sanitize_text(text)
    suggested = " ".join(clean.split())
    if len(suggested) > ITEM_HIGHLIGHT_MAX:
        suggested = suggested[:ITEM_HIGHLIGHT_MAX].rstrip(" ,;-")
    return {
        "current_text": text,
        "character_count": len(text),
        "max_characters": ITEM_HIGHLIGHT_MAX,
        "is_over_limit": len(text) > ITEM_HIGHLIGHT_MAX,
        "suggested_highlight": suggested,
        "suggested_highlight_character_count": len(suggested),
        "title_keyword_tradeoff": {
            "kept": title_analysis.get("kept_keywords", []),
            "moved_to_item_highlight": title_analysis.get("moved_to_item_highlight", []),
            "moved_to_bullets": title_analysis.get("moved_to_bullets", []),
            "omitted_from_title_reason": title_analysis.get("title_tradeoff_reason"),
        },
        "replaced_risk_phrases": replaced,
    }


def _claim_risk_analysis(materials: dict[str, Any]) -> dict[str, Any]:
    phrases: list[str] = []
    for text in _visible_texts(materials):
        phrases.extend(_find_risk_phrases(text))
    phrases = _dedupe(phrases)
    return {
        "risk_phrases_found": phrases,
        "risk_level": "high" if phrases else "low",
        "evidence_required": bool(phrases),
        "safer_alternatives": {phrase: HIGH_RISK_ALTERNATIVES[phrase] for phrase in phrases},
    }


def _main_image_guardrail(materials: dict[str, Any]) -> dict[str, Any] | None:
    missing = set(materials.get("missing_images") or [])
    ocr_texts = materials.get("ocr_texts") or {}
    main_text = ""
    if isinstance(ocr_texts, dict):
        main_text = str(ocr_texts.get("main") or ocr_texts.get("main_image") or "")
    if "main_image" in missing:
        issue = "主图缺失。主图是上架准入硬规则，缺失时不能判断为可直接上架。"
    elif main_text.strip():
        issue = "主图检测到文字或标识。主图必须纯白底、仅产品、无文字、logo、水印或第三方品牌标识。"
    else:
        return None
    return {
        "position_id": "main_image",
        "position": "main_image",
        "position_name": "主图",
        "position_type": "image",
        "uploaded": "main_image" not in missing,
        "status": "缺失" if "main_image" in missing else "需修改",
        "issue_type": ["main_image_non_compliant"],
        "issue": issue,
        "recommendation": "重新拍摄主图：纯白底，产品居中，占画面约 85%，无任何文字、logo、水印、第三方品牌标识。",
        "suggested_action": "重新拍摄主图：纯白底，产品居中，占画面约 85%，无任何文字、logo、水印、第三方品牌标识。",
        "final_score": 1.0,
        "score": 1.0,
        "usable_status": "不可使用",
        "risk_level": "high",
        "validation_metric": "CTR",
        "impact_metrics": ["CTR"],
    }


def _a_plus_analysis(materials: dict[str, Any]) -> list[dict[str, Any]]:
    missing = set(materials.get("missing_images") or [])
    uploaded = {item.get("position") for item in materials.get("uploaded_images") or [] if isinstance(item, dict)}
    modules: list[dict[str, Any]] = []
    for position_id, module, role, missing_status in A_PLUS_MODULES:
        is_uploaded = position_id in uploaded and position_id not in missing
        modules.append({
            "position_id": position_id,
            "module": module,
            "expected_role": role,
            "uploaded": is_uploaded,
            "score": 3.0 if is_uploaded else 1.0,
            "status": "uploaded_requires_task_review" if is_uploaded else missing_status,
            "missing_reason": None if is_uploaded else "未上传",
            "content_risk": "待识别" if is_uploaded else "暂无",
            "suggested_action": "按该位置承接任务检查图片文案、场景和证据。" if is_uploaded else "补充该 A+ 模块。",
        })
    return modules


def _title_position(analysis: dict[str, Any]) -> dict[str, Any]:
    over = analysis["is_over_limit"]
    issue_type = ["title_over_75_characters"] if over else []
    issue = (
        f"标题当前 {analysis['character_count']} / 75 characters，超过 Amazon 标题限制；标题不是关键词仓库，需要保留核心搜索词和主要差异点。"
        if over
        else f"标题当前 {analysis['character_count']} / 75 characters。"
    )
    return {
        "position_id": "title",
        "position": "title",
        "position_name": "标题",
        "position_type": "text",
        "uploaded": bool(analysis["current_title"]),
        "status": "需修改" if over else "通过",
        "issue_type": issue_type,
        "issue": issue,
        "recommendation": analysis["suggested_title"],
        "suggested_rewrite": analysis["suggested_title"],
        "final_score": 2.0 if over else 4.2,
        "score": 2.0 if over else 4.2,
        "usable_status": "表达弱需重写" if over else "可使用但建议优化",
        "evidence": f"character_count: {analysis['character_count']} / 75",
        "risk_level": "low",
        "validation_metric": "CTR",
        "impact_metrics": ["CTR"],
    }


def _highlight_position(analysis: dict[str, Any]) -> dict[str, Any]:
    over = analysis["is_over_limit"]
    return {
        "position_id": "highlights",
        "position": "item_highlight",
        "position_name": "Item Highlight",
        "position_type": "text",
        "uploaded": bool(analysis["current_text"]),
        "status": "需修改" if over else "通过",
        "issue_type": ["item_highlight_over_125_characters"] if over else [],
        "issue": f"Item Highlight 当前 {analysis['character_count']} / 125 characters。",
        "recommendation": analysis["suggested_highlight"],
        "suggested_rewrite": analysis["suggested_highlight"],
        "final_score": 2.0 if over else 4.0,
        "score": 2.0 if over else 4.0,
        "usable_status": "表达弱需重写" if over else "可使用但建议优化",
        "evidence": f"character_count: {analysis['character_count']} / 125",
        "risk_level": "low",
        "validation_metric": "CVR",
        "impact_metrics": ["CVR"],
    }


def _a_plus_position(module: dict[str, Any]) -> dict[str, Any]:
    return {
        "position_id": module["position_id"],
        "position": module["position_id"],
        "position_name": module["module"],
        "position_type": "a_plus",
        "uploaded": module["uploaded"],
        "status": "需修改" if module["uploaded"] else "缺失",
        "issue_type": [module["status"]],
        "issue": f"{module['module']}：{module['expected_role']}。{module['missing_reason'] or '需按承接任务逐图检查。'}",
        "recommendation": module["suggested_action"],
        "suggested_action": module["suggested_action"],
        "final_score": module["score"],
        "score": module["score"],
        "usable_status": "可使用但建议优化" if module["uploaded"] else "不可使用",
        "risk_level": "medium" if module["uploaded"] else "low",
        "validation_metric": "CVR",
        "impact_metrics": ["CVR", "Add to Cart"],
    }


def _sanitize_diagnosis(diagnosis: dict[str, Any]) -> dict[str, Any]:
    for key in ["recommendation", "modification_example", "suggested_rewrite", "suggested_action"]:
        if diagnosis.get(key):
            sanitized, rejected = _sanitize_text(str(diagnosis[key]))
            diagnosis[key] = sanitized
            if rejected:
                diagnosis["risk_level"] = "high"
                diagnosis["safer_alternative"] = sanitized
                existing = diagnosis.get("issue_type") or []
                diagnosis["issue_type"] = _dedupe([*existing, "suggested_rewrite_had_high_risk_claim"])
    if diagnosis.get("position_id") == "title" and diagnosis.get("suggested_rewrite"):
        diagnosis["suggested_rewrite"] = _suggest_title(str(diagnosis["suggested_rewrite"]))
        diagnosis["recommendation"] = diagnosis["suggested_rewrite"]
    return diagnosis


def _upsert_position(items: list[dict[str, Any]], replacement: dict[str, Any]) -> None:
    key = replacement.get("position_id") or replacement.get("position")
    for index, item in enumerate(items):
        item_key = item.get("position_id") or item.get("position")
        if item_key == key:
            merged = {**item, **replacement}
            items[index] = merged
            return
    items.append(replacement)


def _overall_status(hard_blockers: list[dict[str, Any]]) -> str:
    types = {item["type"] for item in hard_blockers}
    if not hard_blockers:
        return "ready_to_launch"
    if types & {"main_image_non_compliant", "title_over_75_characters", "high_risk_claim_without_evidence"}:
        return "fix_required_before_launch"
    if types & {"missing_required_trust_module", "missing_required_faq_module"}:
        return "cautious_launch_after_fix"
    return "not_recommended"


def _admission_result(overall_status: str) -> str:
    return {
        "ready_to_launch": "可以上架",
        "cautious_launch_after_fix": "谨慎上架",
        "fix_required_before_launch": "暂不建议上架",
        "not_recommended": "暂不建议上架",
    }[overall_status]


def _overall_summary(overall_status: str, blockers: list[dict[str, Any]]) -> str:
    if overall_status == "ready_to_launch":
        return "当前未发现硬拦截项。"
    names = "、".join(_dedupe([item["type"] for item in blockers]))
    return f"当前存在上架前必须处理的问题：{names}。"


def _next_action(blockers: list[dict[str, Any]]) -> str:
    if not blockers:
        return "暂无"
    first = blockers[0]["type"]
    if first == "title_over_75_characters":
        return "先重写标题，确保不超过 75 characters including spaces。"
    if first == "main_image_non_compliant":
        return "先重新拍摄或替换主图。"
    if first == "high_risk_claim_without_evidence":
        return "先移除或替换高风险 claim。"
    return "先补齐缺失的 A+ 关键模块。"


def _dedupe(values: list[Any]) -> list[Any]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
