"""AlignX V4 Human Nature root layer.

This module is the layer above user intent and platform matching. It does not
replace the two rulers. It explains where buyer intent comes from before the
system evaluates Listing, platform fit, ads, capital allocation, and learning.
"""

from __future__ import annotations

import re
from typing import Any


ROOT_DRIVES = ("seek_gain", "avoid_loss")

EVOLUTION_DRIVES = ("survival", "reproduction", "resource", "exploration")

HUMAN_MOTIVATIONS = (
    "survival",
    "security",
    "health",
    "love",
    "belonging",
    "status",
    "power",
    "freedom",
    "expansion",
    "curiosity",
    "pleasure",
    "convenience",
    "fear",
)


MOTIVATION_LABELS = {
    "survival": "生存",
    "security": "安全",
    "health": "健康",
    "love": "爱",
    "belonging": "归属",
    "status": "尊严",
    "power": "权力",
    "freedom": "自由",
    "expansion": "扩张",
    "curiosity": "好奇",
    "pleasure": "娱乐",
    "convenience": "懒惰",
    "fear": "恐惧",
}

MOTIVATION_DESCRIPTIONS = {
    "survival": "活下去",
    "security": "避免风险",
    "health": "维持生命质量",
    "love": "关爱、情感连接",
    "belonging": "融入群体",
    "status": "获得认同和身份",
    "power": "获得控制力和影响力",
    "freedom": "减少约束",
    "expansion": "获得更多资源和边界",
    "curiosity": "探索未知",
    "pleasure": "获得愉悦",
    "convenience": "降低成本和能量消耗",
    "fear": "规避损失和危险",
}


MOTIVATION_PATTERNS: dict[str, tuple[str, ...]] = {
    "survival": ("survive", "emergency", "backup", "protect", "protection", "safe"),
    "security": ("safe", "ozone free", "non toxic", "secure", "worry", "risk", "protect", "pet friendly"),
    "health": ("health", "clean air", "odor", "smell", "ammonia", "hygiene", "bacteria", "uv", "uv-c", "fresh"),
    "love": ("pet", "cat", "dog", "baby", "family", "care", "comfort", "love"),
    "belonging": ("guest", "friend", "home", "apartment", "room", "family", "social"),
    "status": ("embarrass", "stink", "odor", "smell", "clean home", "presentable", "premium"),
    "power": ("control", "manage", "monitor", "smart", "automatic", "command"),
    "freedom": ("travel", "vacation", "busy", "hands free", "automatic", "less worry"),
    "expansion": ("multi pet", "large", "capacity", "expand", "whole home"),
    "curiosity": ("new", "photocatalyst", "uv-c", "technology", "innovative"),
    "pleasure": ("fun", "toy", "music", "party", "play", "enjoy", "pleasant"),
    "convenience": ("easy", "no refill", "maintenance free", "automatic", "simple", "quiet", "low maintenance"),
    "fear": ("odor", "smell", "ammonia", "urine", "mold", "dust", "allergy", "danger", "ozone"),
}


EVOLUTION_MAP = {
    "survival": ("survival", "health", "security", "fear"),
    "reproduction": ("love", "belonging", "status"),
    "resource": ("resource", "power", "freedom", "convenience", "expansion"),
    "exploration": ("exploration", "curiosity", "pleasure"),
}


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _dedupe(items: list[str], limit: int = 12) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in items:
        item = re.sub(r"\s+", " ", str(raw or "").strip())
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def _infer_pet_odor_graph(text: str) -> dict[str, Any]:
    return {
        "human_nodes": ["security", "health", "love", "belonging", "status", "convenience", "fear"],
        "motivations": [
            "avoid unsafe deodorizing around pets",
            "keep indoor air and pet areas cleaner",
            "care for pets without creating extra risk",
            "avoid embarrassment from home pet odor",
            "reduce manual odor-control work",
        ],
        "needs": ["pet odor control", "cat litter odor reduction", "clean indoor air", "safe deodorizing"],
        "scenarios": [
            "cat litter box",
            "pet room",
            "bathroom",
            "shoe cabinet",
            "closet",
            "storage room",
            "small pet cage",
            "multi pet home",
        ],
        "solutions": ["photocatalyst deodorizing", "UV-C deodorizing", "ozone free odor control", "continuous air freshening"],
        "expressions": ["No Ozone", "Pet Friendly", "Odor Control", "Fresh Home", "No Fragrance Masking", "Low Maintenance"],
        "behavior_signals": ["impression", "click", "detail stay", "add to cart", "purchase", "review"],
        "outcome_signals": ["CTR", "CVR", "return risk", "review sentiment", "ROI"],
        "summary": "用户不是先买除臭器，而是先想降低宠物异味带来的安全、健康、体面和家庭舒适风险。",
    }


def _generic_graph(text: str) -> dict[str, Any]:
    human_nodes = []
    for key, patterns in MOTIVATION_PATTERNS.items():
        if _contains(text, patterns):
            human_nodes.append(key)
    if not human_nodes:
        human_nodes = ["security", "convenience", "fear"]
    return {
        "human_nodes": _dedupe(human_nodes, 8),
        "motivations": ["avoid wrong purchase", "save effort", "reduce uncertainty"],
        "needs": ["reduce uncertainty", "solve daily friction", "lower purchase risk"],
        "scenarios": ["daily use", "home use", "busy schedule", "first purchase"],
        "solutions": ["clear mechanism", "low risk setup", "easy maintenance"],
        "expressions": ["Easy to Use", "Low Risk", "Clear Benefit", "Reliable Result"],
        "behavior_signals": ["impression", "click", "detail stay", "add to cart", "purchase"],
        "outcome_signals": ["CTR", "CVR", "ACOS", "ROI", "repeat purchase"],
        "summary": "用户先追求收益或避免损失，再把动机转成具体购买任务。",
    }


def build_human_nature_graph(source: dict[str, Any] | Any) -> dict[str, Any]:
    """Build the V4 root graph from Listing/product context.

    The return value is intentionally structured so every downstream module can
    start from human motivation before user intent, platform matching, ads, and
    feedback learning.
    """
    if isinstance(source, dict):
        text = " ".join(str(source.get(key) or "") for key in (
            "title",
            "keywords",
            "bullet_points",
            "description",
            "a_plus_content",
            "category",
            "brand",
        ))
    else:
        text = " ".join(str(getattr(source, key, "") or "") for key in (
            "title",
            "keywords",
            "bullet_points",
            "description",
            "a_plus_content",
            "category",
            "brand",
        ))
    lower = text.lower()

    graph = _infer_pet_odor_graph(lower) if _contains(
        lower,
        ("pet", "cat", "dog", "litter", "odor", "smell", "deodorizer", "photocatalyst", "uv-c", "ammonia"),
    ) else _generic_graph(lower)

    active_nodes = _dedupe(graph["human_nodes"], 13)
    motivations = _dedupe(graph["motivations"], 8)
    evolution = {
        key: [node for node in active_nodes if node in values]
        for key, values in EVOLUTION_MAP.items()
    }
    root_balance = {
        "gain": [item for item in active_nodes if item in {"love", "belonging", "status", "freedom", "expansion", "curiosity", "pleasure", "convenience"}],
        "loss": [item for item in active_nodes if item in {"survival", "security", "health", "fear"}],
    }
    human_node_payload = [
        {
            "key": key,
            "label": MOTIVATION_LABELS[key],
            "description": MOTIVATION_DESCRIPTIONS[key],
            "active": key in active_nodes,
        }
        for key in HUMAN_MOTIVATIONS
    ]
    levels = [
        {
            "level": 0,
            "key": "gain_loss",
            "name": "趋利/避害",
            "items": [{"key": "gain", "label": "趋利"}, {"key": "loss", "label": "避害"}],
            "active_mapping": root_balance,
        },
        {
            "level": 1,
            "key": "evolution",
            "name": "进化驱动力",
            "items": [
                {"key": "survival", "label": "生存"},
                {"key": "reproduction", "label": "繁衍"},
                {"key": "resource", "label": "资源"},
                {"key": "exploration", "label": "探索"},
            ],
            "active_mapping": evolution,
        },
        {
            "level": 2,
            "key": "human_nodes",
            "name": "13个人性节点",
            "items": human_node_payload,
            "active_nodes": active_nodes,
        },
        {
            "level": 3,
            "key": "motivation",
            "name": "动机",
            "items": motivations,
        },
        {"level": 4, "key": "need", "name": "需求", "items": graph["needs"]},
        {"level": 5, "key": "scenario", "name": "场景", "items": graph["scenarios"]},
        {"level": 6, "key": "solution", "name": "解决方案", "items": graph["solutions"]},
        {"level": 7, "key": "expression", "name": "表达", "items": graph["expressions"]},
        {"level": 8, "key": "behavior", "name": "行为", "items": graph["behavior_signals"]},
        {"level": 9, "key": "outcome", "name": "结果", "items": graph["outcome_signals"]},
    ]

    return {
        "version": "alignx-human-nature-v4",
        "position": "above_two_rulers",
        "levels": levels,
        "level_0": levels[0],
        "level_1": levels[1],
        "level_2": levels[2],
        "level_3": levels[3],
        "level_4": levels[4],
        "level_5": levels[5],
        "level_6": levels[6],
        "level_7": levels[7],
        "level_8": levels[8],
        "level_9": levels[9],
        "root_layer": {
            "drives": ["gain", "loss"],
            "gain": "趋利",
            "loss": "避害",
            "balance": root_balance,
        },
        "evolution_layer": {
            "drives": list(EVOLUTION_DRIVES),
            "active_mapping": evolution,
        },
        "human_motivation_layer": {
            "note": "兼容旧字段；V4标准中此层对应Level 2的13个人性节点，不等同Level 3动机。",
            "nodes": human_node_payload,
            "active_nodes": active_nodes,
        },
        "motivation_layer": {
            "level": 3,
            "items": motivations,
        },
        "user_intent_layer": {
            "task": "把人性驱动力转成购买意图",
            "intent_seeds": graph["needs"],
        },
        "need_layer": graph["needs"],
        "scenario_layer": graph["scenarios"],
        "solution_layer": graph["solutions"],
        "expression_layer": graph["expressions"],
        "behavior_layer": graph["behavior_signals"],
        "outcome_layer": graph["outcome_signals"],
        "summary": graph["summary"],
    }


def human_nature_prompt_block(source: dict[str, Any] | Any) -> str:
    """Compact prompt block for model calls."""
    graph = build_human_nature_graph(source)
    human_nodes = ", ".join(graph["level_2"]["active_nodes"])
    motivations = ", ".join(graph["level_3"]["items"][:6])
    needs = ", ".join(graph["level_4"]["items"][:6])
    scenarios = ", ".join(graph["level_5"]["items"][:8])
    solutions = ", ".join(graph["level_6"]["items"][:5])
    expressions = ", ".join(graph["level_7"]["items"][:6])
    return (
        "## V4 Human Nature Root Layer\n"
        "所有判断必须严格按Level 0到Level 9推理，再进入用户意图、平台识别、Listing承接和广告验证。\n"
        "Level 0：趋利（Gain）/ 避害（Loss）。\n"
        "Level 1：生存 / 繁衍 / 资源 / 探索。\n"
        f"Level 2 13个人性节点：{human_nodes}。\n"
        f"Level 3 动机：{motivations}。\n"
        f"Level 4 需求：{needs}。\n"
        f"Level 5 场景：{scenarios}。\n"
        f"Level 6 解决方案：{solutions}。\n"
        f"Level 7 表达：{expressions}。\n"
        "Level 8 行为：曝光、点击、停留、收藏、加购、购买、复购、推荐。\n"
        "Level 9 结果：转化率、复购率、LTV、利润率、ROI。\n"
        "禁止从关键词开始推理；关键词只能作为Level 7表达或广告验证资产。"
    )
