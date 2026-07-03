from __future__ import annotations

import json
import re
from typing import Any


def split_bullets(value: str) -> list[str]:
    text = (value or "").strip()
    if not text:
        return []
    lines = [line.strip() for line in re.split(r"\n+", text) if line.strip()]
    if len(lines) <= 1:
        marker_parts = re.split(r"(?:^|\s)(?:[•\-*]|\d+[.)]|[A-Z][.)])\s+", text)
        lines = [part.strip() for part in marker_parts if part.strip()]
    return [re.sub(r"^(?:[•\-*]|\d+[.)]|[A-Z][.)])\s*", "", line).strip() for line in lines if line.strip()]


def _dedupe_keep_order(items: list[str], limit: int = 12) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in items:
        item = re.sub(r"\s+", " ", (raw or "").strip())
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


def build_buyer_language_payload(
    *,
    title: str = "",
    bullet_points: str | list[str] = "",
    a_plus_desc: str = "",
    keywords: str = "",
    main_image_texts: list[str] | None = None,
    a_plus_image_texts: list[str] | None = None,
) -> dict[str, Any]:
    bullets = bullet_points if isinstance(bullet_points, list) else split_bullets(str(bullet_points or ""))
    return {
        "title": title or "",
        "bullet_points": bullets,
        "a_plus_desc": a_plus_desc or "",
        "keywords": keywords or "",
        "main_image_texts": main_image_texts or [],
        "a_plus_image_texts": a_plus_image_texts or [],
    }


def empty_buyer_language_translation(payload: dict[str, Any]) -> dict[str, Any]:
    image_texts = _dedupe_keep_order(
        [*payload.get("main_image_texts", []), *payload.get("a_plus_image_texts", [])],
        12,
    )
    bullet_items = payload.get("bullet_points") if isinstance(payload.get("bullet_points"), list) else []
    return {
        "engine_basis": "人性树引擎判断链路",
        "seller_language": {
            "title": str(payload.get("title") or "").strip() or "暂无",
            "bullet_points": bullet_items or ["暂无"],
            "a_plus_desc": str(payload.get("a_plus_desc") or "").strip() or "暂无",
            "image_texts": image_texts or ["暂无"],
        },
        "buyer_language": {
            "title": "暂无",
            "bullet_points": ["暂无"],
            "a_plus_desc": "暂无",
            "image_texts": ["暂无"],
        },
        "buyer_questions": ["暂无"],
        "unclear_terms": ["暂无"],
        "missing_information": ["暂无"],
        "rewrite_priority": ["暂无"],
    }


def normalize_buyer_language_translation(raw: Any, payload: dict[str, Any]) -> dict[str, Any]:
    fallback = empty_buyer_language_translation(payload)
    if not isinstance(raw, dict):
        return fallback

    def clean_text(value: Any) -> str:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        return text or "暂无"

    def clean_list(value: Any) -> list[str]:
        if isinstance(value, list):
            items = [clean_text(item) for item in value if clean_text(item) != "暂无"]
        elif isinstance(value, str):
            items = [clean_text(item) for item in re.split(r"[\n;；]+", value) if clean_text(item) != "暂无"]
        else:
            items = []
        return items[:12] or ["暂无"]

    seller = raw.get("seller_language") if isinstance(raw.get("seller_language"), dict) else {}
    buyer = raw.get("buyer_language") if isinstance(raw.get("buyer_language"), dict) else {}
    fallback["seller_language"].update({
        "title": clean_text(seller.get("title") or fallback["seller_language"]["title"]),
        "bullet_points": clean_list(seller.get("bullet_points") or fallback["seller_language"]["bullet_points"]),
        "a_plus_desc": clean_text(seller.get("a_plus_desc") or fallback["seller_language"]["a_plus_desc"]),
        "image_texts": clean_list(seller.get("image_texts") or fallback["seller_language"]["image_texts"]),
    })
    fallback["buyer_language"].update({
        "title": clean_text(buyer.get("title")),
        "bullet_points": clean_list(buyer.get("bullet_points")),
        "a_plus_desc": clean_text(buyer.get("a_plus_desc")),
        "image_texts": clean_list(buyer.get("image_texts")),
    })
    fallback["buyer_questions"] = clean_list(raw.get("buyer_questions"))
    fallback["unclear_terms"] = clean_list(raw.get("unclear_terms"))
    fallback["missing_information"] = clean_list(raw.get("missing_information"))
    fallback["rewrite_priority"] = clean_list(raw.get("rewrite_priority"))
    fallback["engine_basis"] = "人性树引擎判断链路"
    return fallback


def build_buyer_language_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    human_nature_graph = payload.get("human_nature_graph") if isinstance(payload.get("human_nature_graph"), dict) else {}
    return [
        {
            "role": "system",
            "content": (
                "你只做Amazon Listing买家语言转译。"
                "依据是输入中的human_nature_graph；它来自系统的人性树引擎判断链路。"
                "目标是把卖家自说自话的功能、参数、技术词、营销词，转成买家能看懂、会搜索、会点击、会相信的表达。"
                "只基于输入字段和图片OCR文本，不新增产品功能、场景、功效、认证、适配对象或数据。"
                "没有证据的字段必须填“暂无”。"
                "输出必须是严格JSON对象。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    **{key: value for key, value in payload.items() if key != "human_nature_graph"},
                    "human_nature_graph": human_nature_graph,
                    "required_schema": {
                        "seller_language": {
                            "title": "原始标题",
                            "bullet_points": ["原始五点"],
                            "a_plus_desc": "原始A+",
                            "image_texts": ["图片OCR文本"],
                        },
                        "buyer_language": {
                            "title": "买家能理解的标题表达",
                            "bullet_points": ["买家能理解的五点表达"],
                            "a_plus_desc": "买家能理解的A+表达",
                            "image_texts": ["买家能理解的图片表达"],
                        },
                        "buyer_questions": ["买家看完后仍可能问的问题"],
                        "unclear_terms": ["买家不一定懂的词"],
                        "missing_information": ["缺失信息"],
                        "rewrite_priority": ["优先改写顺序"],
                        "engine_basis": "人性树引擎判断链路",
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]
