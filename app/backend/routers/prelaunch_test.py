"""
PreLaunch Test Results Router.
Save, list, and retrieve pre-launch listing test scoring results.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from schemas.auth import UserResponse
from services.ai_gateway import AgentRequest, AIGatewayService
from services.prelaunch_test_results import Prelaunch_test_resultsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/prelaunch-test", tags=["prelaunch-test"])


# ---------- Request / Response Models ----------

class DimensionScoreInput(BaseModel):
    score: float = 0
    analysis: str = ""
    suggestions: list[str] = []


class SaveResultRequest(BaseModel):
    title: str = ""
    keywords: str = ""
    bullet_points: str = ""
    a_plus_desc: str = ""
    input_snapshot: dict[str, Any] = {}
    saved_kind: str = "full_prelaunch_record"
    optimization_round: int = 1
    overall_score: float = 0
    title_keywords: DimensionScoreInput = DimensionScoreInput()
    main_image: DimensionScoreInput = DimensionScoreInput()
    a_plus_description: DimensionScoreInput = DimensionScoreInput()
    bullet_points_score: DimensionScoreInput = DimensionScoreInput()
    backend_keywords: DimensionScoreInput = DimensionScoreInput()
    overall_summary: str = ""
    cosmo_alignment: str = ""
    rufus_alignment: str = ""
    ordered_first_fixes: list[str] = []
    rule_context: dict[str, Any] = {}
    vision_alignment: dict[str, Any] = {}
    has_images: int = 0  # 0=none, 1=main, 2=a+, 3=both


class EvaluateLaunchRequest(BaseModel):
    title: str = ""
    keywords: str = ""
    bullet_points: str = ""
    a_plus_desc: str = ""
    category: str = ""
    price: str = ""
    target_price_band: str = ""
    main_image_count: int = 0
    a_plus_image_count: int = 0
    main_image_texts: list[str] = []
    a_plus_image_texts: list[str] = []
    use_ai: bool = True


class HistoryItemResponse(BaseModel):
    id: int
    title: str
    overall_score: float
    score_title_keywords: float
    score_main_image: float
    score_a_plus: float
    score_bullet_points: float
    has_images: int
    created_at: Optional[str] = None


# ---------- Endpoints ----------

def _clamp_score(value: float) -> int:
    return max(35, min(96, round(value)))


def _cap_score(value: float, cap: int) -> int:
    return max(35, min(cap, round(value)))


def _split_list(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[\n,，;；]+", value or "") if item.strip()]


def _count_hits(text: str, terms: list[str]) -> int:
    lower = (text or "").lower()
    return sum(1 for term in terms if term in lower)


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _has_any(text: str, terms: list[str]) -> bool:
    lower = (text or "").lower()
    return any(term in lower for term in terms)


def _copy_title_case_rate(lines: list[str]) -> float:
    words = re.findall(r"\b[A-Za-z][A-Za-z0-9'-]*\b", " ".join(lines or []))
    meaningful = [word for word in words if len(word) > 2]
    if not meaningful:
        return 0.0
    capitalized = [word for word in meaningful if word[0].isupper()]
    return len(capitalized) / len(meaningful)


def _keyword_bucket_counts(items: list[str]) -> dict[str, int]:
    attr_terms = [
        "waterproof", "bluetooth", "wireless", "portable", "battery", "led", "speaker",
        "odor", "filter", "sealed", "litter", "cat", "easy", "clean", "usb", "compact",
        "large", "small", "slim", "rechargeable", "fm", "sound", "bass",
    ]
    relation_terms = [
        "for", "with", "without", "compatible", "fits", "gift", "travel", "outdoor",
        "camping", "pool", "beach", "hiking", "bedroom", "office", "apartment",
        "kids", "women", "men", "cats", "dogs", "mom", "dad",
    ]
    state_terms = [
        "reduce", "control", "remove", "safe", "sealed", "odor", "ammonia", "waterproof",
        "splash", "easy", "quiet", "clean", "fast", "long lasting", "low noise",
        "anti", "no", "less", "risk", "backup", "emergency",
    ]
    text_items = [item.lower() for item in items]
    return {
        "attribute": sum(1 for item in text_items if _has_any(item, attr_terms)),
        "relation": sum(1 for item in text_items if _has_any(item, relation_terms)),
        "state": sum(1 for item in text_items if _has_any(item, state_terms)),
    }


def _dimension(score: int, analysis: str, suggestions: list[str]) -> dict[str, Any]:
    return {"score": score, "analysis": analysis, "suggestions": suggestions[:3]}


MAIN_IMAGE_SEQUENCE = [
    "1 主图：白底真实商品，负责点击率",
    "2 核心卖点图：让用户马上知道核心差异",
    "3 使用场景图：证明适合谁、在哪里用",
    "4 尺寸/结构图：降低尺寸和结构误解",
    "5 竞品对比图：说明为什么选你",
    "6 安全/材质/认证图：消除风险和信任顾虑",
    "7 包装/安装/使用步骤图：降低使用门槛",
]


A_PLUS_SEQUENCE = [
    "1 品牌承诺：建立品牌可信度",
    "2 核心技术/原理：解释为什么有效",
    "3 目标人群/使用场景：让买家代入",
    "4 核心利益证明：展示效果和结果",
    "5 差异化对比：说明相对竞品的优势",
    "6 尺寸/兼容/适配：减少买错风险",
    "7 安全/材质/认证：建立信任",
    "8 使用方法/维护：降低使用门槛",
    "9 售后/保障/品牌闭环：完成信任闭环",
]


def _sequence_missing(sequence: list[str], count: int) -> list[str]:
    return sequence[max(0, count):]


def _build_rule_evaluation(request: EvaluateLaunchRequest) -> dict[str, Any]:
    title = request.title.strip()
    keyword_items = _split_list(request.keywords)
    bullet_items = _split_list(request.bullet_points)
    all_text = " ".join([
        request.title,
        request.keywords,
        request.bullet_points,
        request.a_plus_desc,
        request.category,
    ])
    title_text = request.title or ""
    bullet_text = request.bullet_points or ""
    aplus_text = request.a_plus_desc or ""
    main_image_copy_rate = _copy_title_case_rate(request.main_image_texts)
    a_plus_image_copy_rate = _copy_title_case_rate(request.a_plus_image_texts)
    has_main_image_copy = bool(" ".join(request.main_image_texts).strip())
    has_a_plus_image_copy = bool(" ".join(request.a_plus_image_texts).strip())
    function_hits = _count_hits(all_text, [
        "waterproof", "bluetooth", "wireless", "portable", "battery", "led",
        "speaker", "odor", "filter", "sealed", "cat", "litter", "easy", "clean",
    ])
    scenario_hits = _count_hits(all_text, [
        "beach", "camping", "outdoor", "pool", "travel", "apartment", "bedroom",
        "party", "gift", "kids", "office", "home", "car", "patio",
    ])
    risk_hits = _count_hits(all_text, [
        "safe", "sealed", "reduce", "control", "warranty", "replaceable",
        "waterproof", "leak", "odor", "tracking", "ammonia", "noise", "dust",
    ])
    intent_hits = _count_hits(all_text, [
        "for ", "with ", "without ", "easy", "gift", "portable", "large", "small",
        "kids", "women", "men", "cats", "dogs",
    ])
    bullet_purchase_reasons = {
        "function": _has_any(bullet_text, ["feature", "function", "bluetooth", "waterproof", "filter", "battery", "speaker", "charge", "clean", "portable"]),
        "effect": _has_any(bullet_text, ["reduce", "remove", "control", "keep", "clear", "fast", "long", "strong", "easy", "quiet"]),
        "scenario": _has_any(bullet_text, ["for ", "travel", "outdoor", "camping", "pool", "beach", "home", "office", "apartment", "gift"]),
        "trust": _has_any(bullet_text, ["safe", "warranty", "certified", "tested", "durable", "material", "bpa", "replaceable", "support"]),
        "after_sale": _has_any(bullet_text, ["warranty", "support", "return", "replacement", "service", "guarantee", "after-sale"]),
    }
    bullet_reason_hits = sum(1 for value in bullet_purchase_reasons.values() if value)

    keyword_counts = _keyword_bucket_counts(keyword_items)
    forbidden_keyword_hits = _count_hits(request.keywords, [
        "best", "cheap", "free", "discount", "sale", "deal", "official", "amazon",
    ]) + len(re.findall(r"\bB0[A-Z0-9]{8}\b", request.keywords or "", flags=re.IGNORECASE))
    has_product_identity = _has_any(title_text, [
        "speaker", "power bank", "charger", "cat litter", "litter box", "filter",
        "deodorizer", "organizer", "case", "bag", "toy", "humidifier", "light",
    ])
    has_title_relation = _has_any(title_text, [
        " for ", " with ", " without ", "compatible", "gift", "travel", "outdoor",
        "camping", "pool", "beach", "home", "office", "apartment", "kids",
    ])
    has_title_state = _has_any(title_text, [
        "waterproof", "odor", "reduce", "safe", "easy", "portable", "long", "fast",
        "sealed", "quiet", "splash", "clean", "backup", "low",
    ])
    title_score_raw = (
        38
        + (14 if 80 <= len(title) <= 180 else 8 if 45 <= len(title) < 80 else 3)
        + (14 if has_product_identity else 0)
        + (10 if has_title_relation else 0)
        + (10 if has_title_state else 0)
        + min(keyword_counts["relation"], 3) * 3
        + min(keyword_counts["state"], 3) * 3
        + min(keyword_counts["attribute"], 4) * 2
        - (_count_hits(title_text, ["best", "cheap", "free", "discount", "sale", "deal"]) * 6)
    )
    title_cap = 96
    if not has_product_identity:
        title_cap = min(title_cap, 68)
    if not has_title_relation or not has_title_state:
        title_cap = min(title_cap, 78)
    if len(keyword_items) < 5:
        title_cap = min(title_cap, 82)
    title_score = _cap_score(title_score_raw, title_cap)

    main_count = max(0, request.main_image_count)
    missing_main_roles = _sequence_missing(MAIN_IMAGE_SEQUENCE, main_count)
    if main_count == 0:
        image_score = 35
    else:
        image_score_raw = (
            38
            + min(main_count, 7) * 5
            + min(function_hits, 4) * 3
            + min(scenario_hits, 4) * 3
            + min(risk_hits, 3) * 2
            + (6 if has_main_image_copy and main_image_copy_rate >= 0.7 else 0)
        )
        image_cap = 96 if main_count >= 7 else 75 if main_count >= 4 else 62 if main_count >= 2 else 50
        if main_count >= 7 and not has_main_image_copy:
            image_cap = min(image_cap, 88)
        if has_main_image_copy and main_image_copy_rate < 0.7:
            image_cap = min(image_cap, 78)
        image_score = _cap_score(image_score_raw, image_cap)

    aplus_count = max(0, request.a_plus_image_count)
    missing_aplus_roles = _sequence_missing(A_PLUS_SEQUENCE, aplus_count)
    aplus_text_ready = len(aplus_text.strip()) >= 500
    if aplus_count == 0 and not aplus_text.strip():
        a_plus_score = 35
    else:
        a_plus_score_raw = (
            36
            + min(aplus_count, 9) * 4
            + min(len(aplus_text) / 120, 8) * 2
            + min(scenario_hits, 5) * 3
            + min(risk_hits, 5) * 3
            + (8 if aplus_text_ready else 0)
            + (6 if has_a_plus_image_copy and a_plus_image_copy_rate >= 0.7 else 0)
        )
        aplus_cap = 96 if aplus_count >= 9 and aplus_text_ready else 78 if aplus_count >= 6 else 65 if aplus_count >= 3 else 55
        if aplus_count >= 9 and not has_a_plus_image_copy:
            aplus_cap = min(aplus_cap, 88)
        if has_a_plus_image_copy and a_plus_image_copy_rate < 0.7:
            aplus_cap = min(aplus_cap, 76)
        a_plus_score = _cap_score(a_plus_score_raw, aplus_cap)

    bullet_structure_ready = 4 <= len(bullet_items) <= 6
    too_many_bullets = len(bullet_items) > 8
    bullet_score_raw = (
        38
        + (16 if bullet_structure_ready else 8 if len(bullet_items) >= 3 else 2)
        + min(function_hits, 6) * 3
        + min(scenario_hits, 5) * 3
        + min(risk_hits, 5) * 3
        + min(intent_hits, 5) * 2
        + bullet_reason_hits * 3
    )
    bullet_cap = 96 if bullet_structure_ready else 76 if len(bullet_items) >= 3 else 58
    if bullet_reason_hits < 4:
        bullet_cap = min(bullet_cap, 82)
    if too_many_bullets:
        bullet_cap = min(bullet_cap, 72)
    bullet_score = _cap_score(bullet_score_raw, bullet_cap)

    duplicate_keywords = len(keyword_items) - len({item.lower() for item in keyword_items})
    keyword_score_raw = (
        35
        + min(len(keyword_items), 10) * 3
        + min(keyword_counts["attribute"], 4) * 4
        + min(keyword_counts["relation"], 4) * 5
        + min(keyword_counts["state"], 4) * 5
        - max(0, duplicate_keywords) * 4
        - (18 if _has_cjk(request.keywords) else 0)
    )
    keyword_cap = 96
    if _has_cjk(request.keywords):
        keyword_cap = min(keyword_cap, 68)
    if forbidden_keyword_hits:
        keyword_cap = min(keyword_cap, 70)
    if keyword_counts["relation"] == 0 or keyword_counts["state"] == 0:
        keyword_cap = min(keyword_cap, 72)
    if len(keyword_items) < 8:
        keyword_cap = min(keyword_cap, 78)
    backend_keyword_score = _cap_score(keyword_score_raw, keyword_cap)

    overall_score = _clamp_score(
        title_score * 0.22
        + image_score * 0.2
        + a_plus_score * 0.2
        + bullet_score * 0.23
        + backend_keyword_score * 0.15
    )
    launch_advice = "建议上架" if overall_score >= 80 else "修改后上架" if overall_score >= 65 else "暂缓上架"
    ordered_first_fixes: list[str] = []
    if title_score < 80:
        ordered_first_fixes.append("先改标题：标题负责搜索识别，归类不准会影响后续全部判断。")
    if image_score < 80:
        ordered_first_fixes.append(f"再改主图/辅图顺序：优先补齐或调整 {missing_main_roles[0] if missing_main_roles else '第1主图点击逻辑'}。")
    if bullet_score < 80:
        ordered_first_fixes.append("再改五点：每点只讲一个购买理由，按功能、效果、场景、信任、售后拆开。")
    if backend_keyword_score < 80:
        ordered_first_fixes.append("再改后台Search Terms：补标题和五点未覆盖的真实相关长尾词。")
    if a_plus_score < 80:
        ordered_first_fixes.append(f"最后改A+信任闭环：优先补齐或调整 {missing_aplus_roles[0] if missing_aplus_roles else '品牌信任和差异化证明'}。")
    ordered_first_fixes = ordered_first_fixes[:5]
    image_basis = (
        f"已记录{request.main_image_count}张主图、{request.a_plus_image_count}张A+图片；后台按固定顺序评分：主图/辅图必须依次承接点击、卖点、场景、尺寸、对比、安全和使用步骤。"
        if request.main_image_count or request.a_plus_image_count
        else "未提供图片素材，后台按Listing文本反推主图应承接的点击理由，图片维度为低置信评分。"
    )

    return {
        "title_keywords": _dimension(
            title_score,
            f"标题职责是平台搜索识别和用户一眼归类；按品牌/核心关键词/关键属性/规格/使用对象或场景反向评分。禁止促销词、特殊符号、同词重复超过两次和无关堆词。关键词{len(keyword_items)}个，功能命中{function_hits}，场景命中{scenario_hits}。",
            [
                "标题按Brand + Core Product + Key Attribute + Spec/Quantity + Use Case重组。",
                "删除促销词、夸大词、竞品品牌词、无关高流量词和重复堆砌词。",
                "标题不负责说服转化，只负责让平台准确归类、让用户一眼知道卖什么。",
            ],
        ),
        "main_image": _dimension(
            image_score,
            image_basis,
            [
                "第1张主图只解决点击率：白底、真实商品、高清、主体占比足够、无文字水印、无夸张场景。",
                "7张图职责为：1点击、2核心卖点、3使用场景、4尺寸/结构、5竞品对比、6安全/材质认证、7包装/安装/使用步骤。",
                missing_main_roles[0] if missing_main_roles else "辅图顺序完整；后续接视觉模型后继续校验每张图是否放在正确位置。",
            ],
        ),
        "a_plus_description": _dimension(
            a_plus_score,
            f"A+按9张信任闭环顺序评分：品牌承诺、技术原理、场景教育、利益证明、差异化对比、适配、认证、使用维护、售后闭环；A+文本{len(request.a_plus_desc)}字符，风险消除命中{risk_hits}。",
            [
                "A+不要复用Listing图库同一套图文，必须承担品牌信任和深度说服。",
                "A+用于品牌故事、技术原理、场景教育、差异化证明和信任闭环。",
                missing_aplus_roles[0] if missing_aplus_roles else "A+顺序完整；后续接视觉模型后继续校验每张图文案和信任点是否匹配。",
            ],
        ),
        "bullet_points": _dimension(
            bullet_score,
            f"五点职责是给出5个购买理由；按功能、效果、场景、信任和售后覆盖评分。识别{len(bullet_items)}条五点，购买理由覆盖{bullet_reason_hits}/5，意图结构命中{intent_hits}。",
            [
                "五点每点只讲一个购买理由：功能、效果、场景、信任、售后。",
                "不要空喊high quality、best、premium等无法验证的词。",
                "每条五点从用户问题出发，用美国买家自然表达承接意图。",
            ],
        ),
        "backend_keywords": _dimension(
            backend_keyword_score,
            f"后台Search Terms按相关性高于堆词评分；共{len(keyword_items)}个，属性词{keyword_counts['attribute']}个，关系词{keyword_counts['relation']}个，状态触发词{keyword_counts['state']}个，违规/无效词命中{forbidden_keyword_hits}。",
            [
                "Search Terms放标题和五点未覆盖的次级词、长尾词和同义词。",
                "不要重复前台词，不要写竞品品牌、ASIN、促销词和无关流量词。",
                "后台词负责补语义入口，关键词应覆盖标题、五点、后台词等不同位置。",
            ],
        ),
        "overall_score": overall_score,
        "overall_summary": f"{launch_advice}。后台已按Amazon上新准入规则反向评分：标题、7张主图顺序、9张A+信任顺序、五点和后台关键词分别判定；AI只作为修改意见辅助，不改后台分数。",
        "cosmo_alignment": f"COSMO判断：标题负责搜索识别，主图负责点击，辅图负责转化，五点负责购买理由，后台词负责补语义，A+负责信任闭环。当前功能覆盖{function_hits}，场景覆盖{scenario_hits}。",
        "rufus_alignment": "Rufus判断：Listing是否用美国消费者自然语言承接搜索意图。标题不堆词，五点讲购买理由，后台词补充前台未覆盖的真实相关词。",
        "ordered_first_fixes": ordered_first_fixes,
        "vision_alignment": {
            "required": True,
            "status": "pending_vision_model",
            "rule": "主图/副图/A+图片必须由视觉模型识别商品、场景、图中文字、Alt Text和图文承接；并按固定顺序判断每张图是否承担正确任务。图片英文文案主要单词首字母必须大写。",
            "main_image_copy_title_case_rate": main_image_copy_rate,
            "a_plus_image_copy_title_case_rate": a_plus_image_copy_rate,
        },
        "rule_context": {
            "function_hits": function_hits,
            "scenario_hits": scenario_hits,
            "risk_hits": risk_hits,
            "intent_hits": intent_hits,
            "keyword_count": len(keyword_items),
            "keyword_type_counts": keyword_counts,
            "bullet_count": len(bullet_items),
            "bullet_purchase_reasons": bullet_purchase_reasons,
            "bullet_purchase_reason_hits": bullet_reason_hits,
            "main_image_required": 7,
            "a_plus_image_required": 9,
            "seven_image_roles": MAIN_IMAGE_SEQUENCE,
            "missing_main_image_roles": missing_main_roles,
            "a_plus_image_roles": A_PLUS_SEQUENCE,
            "missing_a_plus_image_roles": missing_aplus_roles,
            "module_responsibilities": {
                "title": "search recognition",
                "main_image": "click-through",
                "secondary_images": "conversion",
                "bullet_points": "purchase reasons",
                "backend_search_terms": "semantic supplement",
                "a_plus": "trust loop",
            },
            "main_image_copy_checked": has_main_image_copy,
            "main_image_copy_title_case_rate": main_image_copy_rate,
            "a_plus_image_copy_checked": has_a_plus_image_copy,
            "a_plus_image_copy_title_case_rate": a_plus_image_copy_rate,
            "image_copy_rule": "视觉/OCR模型接入后，后台按主图/辅图/A+图片文案识别结果校验英文主要单词首字母大写，并检查图文承接。",
            "data_source": "backend_rule_reverse_alignment",
        },
        "ai_called": False,
    }


async def _enrich_with_ai(request: EvaluateLaunchRequest, result: dict[str, Any]) -> dict[str, Any]:
    if not request.use_ai:
        return result
    gateway = AIGatewayService()
    if not gateway.status().configured:
        return result
    payload = {
        "listing_input": request.model_dump(),
        "rule_reverse_score": result,
        "instruction": "基于后台规则评分，只补充可执行修改意见。不要重算分数，不要输出中文关键词作为广告词；广告验证词必须是美式英语。图片文案必须按美国站规范检查主要英文单词首字母大写，且文案必须和图片真实内容、标题、五点、A+承诺一致。",
    }
    agent_request = AgentRequest(
        agent="launch_check_agent",
        task="根据上新前Listing输入和后台规则评分，指出上架前必改项、依据来源、修改建议和广告验证方向。",
        payload=payload,
        depth="light",
        dry_run=False,
    )
    try:
        ai_response = await asyncio.wait_for(gateway.run_agent(agent_request), timeout=45)
        ai_result = ai_response.result
        result["ai_called"] = True
        result["ai_model"] = ai_response.model
        result["ai_launch_opinion"] = ai_result.model_dump()
        ai_actions = [item.title for item in ai_result.actions[:3]]
        ai_problems = [item.title for item in ai_result.problems[:3]]
        if ai_actions:
            result["overall_summary"] = f"{result['overall_summary']} AI补充建议：{'；'.join(ai_actions)}"
        if ai_problems:
            result["title_keywords"]["suggestions"] = (ai_problems + result["title_keywords"]["suggestions"])[:3]
        return result
    except Exception as exc:
        logger.warning("Prelaunch AI enrichment failed, using rule result: %s", exc)
        result["ai_error"] = "AI辅助意见暂不可用，已使用后台规则评分。"
        return result


@router.post("/evaluate")
async def evaluate_prelaunch(
    request: EvaluateLaunchRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Evaluate launch readiness through the backend rule-first judgment path."""
    if not request.title.strip() and not request.bullet_points.strip():
        raise HTTPException(status_code=400, detail="请至少输入标题或五点描述")
    result = _build_rule_evaluation(request)
    result = await _enrich_with_ai(request, result)
    result["user_id"] = str(current_user.id)
    return result

@router.post("/save")
async def save_test_result(
    request: SaveResultRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a pre-launch test scoring result."""
    try:
        full_report = json.dumps({
            "title_keywords": request.title_keywords.model_dump(),
            "main_image": request.main_image.model_dump(),
            "a_plus_description": request.a_plus_description.model_dump(),
            "bullet_points": request.bullet_points_score.model_dump(),
            "backend_keywords": request.backend_keywords.model_dump(),
            "overall_score": request.overall_score,
            "overall_summary": request.overall_summary,
            "cosmo_alignment": request.cosmo_alignment,
            "rufus_alignment": request.rufus_alignment,
            "ordered_first_fixes": request.ordered_first_fixes,
            "rule_context": request.rule_context,
            "vision_alignment": request.vision_alignment,
            "input_snapshot": request.input_snapshot,
            "saved_kind": request.saved_kind,
            "optimization_round": request.optimization_round,
        }, ensure_ascii=False)

        svc = Prelaunch_test_resultsService(db)
        record = await svc.create({
            "title": (request.title or "")[:500],
            "keywords": request.keywords,
            "bullet_points": request.bullet_points,
            "a_plus_desc": request.a_plus_desc,
            "overall_score": request.overall_score,
            "score_title_keywords": request.title_keywords.score,
            "score_main_image": request.main_image.score,
            "score_a_plus": request.a_plus_description.score,
            "score_bullet_points": request.bullet_points_score.score,
            "overall_summary": request.overall_summary,
            "cosmo_alignment": request.cosmo_alignment,
            "rufus_alignment": request.rufus_alignment,
            "full_report": full_report,
            "has_images": request.has_images,
            "created_at": datetime.now(timezone.utc),
        }, user_id=str(current_user.id))

        return {"success": True, "id": record.id if record else None}
    except Exception as e:
        logger.error(f"Save prelaunch test result error: {e}")
        return {"success": False, "message": str(e)}


@router.get("/history")
async def get_history(
    skip: int = 0,
    limit: int = 50,
    search: str = "",
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's pre-launch test history."""
    svc = Prelaunch_test_resultsService(db)
    rows, total = await svc.list_by_user(
        user_id=str(current_user.id),
        skip=skip,
        limit=limit,
        search=search,
    )

    items = []
    for item in rows:
        items.append({
            "id": item.id,
            "title": item.title or "",
            "overall_score": item.overall_score or 0,
            "score_title_keywords": item.score_title_keywords or 0,
            "score_main_image": item.score_main_image or 0,
            "score_a_plus": item.score_a_plus or 0,
            "score_bullet_points": item.score_bullet_points or 0,
            "has_images": item.has_images or 0,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        })

    return {"items": items, "total": total}


@router.get("/history/{result_id}")
async def get_result_detail(
    result_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full detail of a pre-launch test result."""
    svc = Prelaunch_test_resultsService(db)
    record = await svc.get_by_id(result_id, user_id=str(current_user.id))
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    full_report = {}
    try:
        if record.full_report:
            full_report = json.loads(record.full_report)
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "id": record.id,
        "title": record.title or "",
        "keywords": record.keywords or "",
        "bullet_points": record.bullet_points or "",
        "a_plus_desc": record.a_plus_desc or "",
        "overall_score": record.overall_score or 0,
        "score_title_keywords": record.score_title_keywords or 0,
        "score_main_image": record.score_main_image or 0,
        "score_a_plus": record.score_a_plus or 0,
        "score_bullet_points": record.score_bullet_points or 0,
        "overall_summary": record.overall_summary or "",
        "cosmo_alignment": record.cosmo_alignment or "",
        "rufus_alignment": record.rufus_alignment or "",
        "full_report": full_report,
        "has_images": record.has_images or 0,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@router.delete("/history/{result_id}")
async def delete_result(
    result_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a pre-launch test result."""
    svc = Prelaunch_test_resultsService(db)
    deleted = await svc.delete(result_id, user_id=str(current_user.id))
    if not deleted:
        raise HTTPException(status_code=404, detail="记录不存在或无权删除")
    return {"success": True}
