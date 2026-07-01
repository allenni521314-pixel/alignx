from __future__ import annotations

"""Top20 keyword mapping for conversion diagnosis.

Input source is the seller's own listing title. Top20 data is used only as
evidence for position mapping; it does not replace seller listing data.
"""

import re
from collections import Counter
from typing import Any


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "without",
    "your",
}

PRODUCT_NOUN_HINTS = {
    "adapter",
    "bag",
    "box",
    "cleaner",
    "deodorizer",
    "device",
    "eliminator",
    "freshener",
    "holder",
    "kit",
    "machine",
    "organizer",
    "purifier",
    "rack",
    "set",
    "sprayer",
    "stand",
    "tool",
}


def extract_title_keyword_candidates(title: str | None, limit: int = 8) -> list[str]:
    tokens = _title_tokens(title)
    if len(tokens) >= 5 and _looks_like_brand_prefix(tokens):
        tokens = tokens[1:]
    if not tokens:
        return []

    scored: list[tuple[float, str]] = []
    for length in (4, 3, 2):
        for index in range(0, max(len(tokens) - length + 1, 0)):
            phrase_tokens = tokens[index:index + length]
            if not _valid_phrase(phrase_tokens):
                continue
            phrase = " ".join(phrase_tokens)
            score = 100 - index * 4 - abs(length - 3) * 8
            if phrase_tokens[-1] in PRODUCT_NOUN_HINTS:
                score += 20
            if any(token in PRODUCT_NOUN_HINTS for token in phrase_tokens):
                score += 8
            scored.append((score, phrase))

    ordered: list[str] = []
    for _, phrase in sorted(scored, reverse=True):
        if phrase not in ordered:
            ordered.append(phrase)
        if len(ordered) >= limit:
            break
    return ordered


def select_core_keyword(title: str | None) -> str | None:
    candidates = extract_title_keyword_candidates(title, limit=1)
    return candidates[0] if candidates else None


def build_top20_keyword_position_data(
    *,
    title: str | None,
    top20_results: list[dict[str, Any]],
    source_keyword: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates = extract_title_keyword_candidates(title)
    keyword = source_keyword or (candidates[0] if candidates else None)
    if not keyword:
        return [], {
            "source": "own_listing_title",
            "source_keyword": None,
            "source_keyword_candidates": [],
            "top20_sample_count": len(top20_results),
            "top20_asins": _top20_asins(top20_results),
        }

    keyword_pool = _rank_keywords([keyword, *candidates], top20_results)
    rows = []
    for index, item in enumerate(keyword_pool[:8]):
        phrase = item["keyword"]
        top1_5 = _position_pattern(phrase, top20_results[:5])
        top16_20 = _position_pattern(phrase, top20_results[15:20])
        rows.append({
            "keyword": phrase,
            "keyword_role": "核心产品词" if index == 0 else "辅助关键词",
            "buyer_intent": "待录入",
            "top1_5_position_pattern": top1_5,
            "top16_20_position_pattern": top16_20,
            "position_consistency_score": item["score"],
            "recommended_positions": ["title_front"] if top1_5["title_count"] else ["title_middle"],
            "reason": "Top20 搜索结果标题样本",
            "data_source": "own_listing_title_to_top20",
        })

    return rows, {
        "source": "own_listing_title",
        "source_keyword": keyword,
        "source_keyword_candidates": candidates,
        "top20_sample_count": len(top20_results),
        "top20_asins": _top20_asins(top20_results),
    }


def _rank_keywords(candidates: list[str], top20_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter()
    for phrase in candidates:
        normalized = phrase.lower().strip()
        if not normalized:
            continue
        for result in top20_results:
            title = str(result.get("title") or "").lower()
            if normalized in title:
                counts[normalized] += 1

    ranked = []
    seen = set()
    for candidate in candidates:
        phrase = candidate.lower().strip()
        if not phrase or phrase in seen:
            continue
        seen.add(phrase)
        count = counts.get(phrase, 0)
        score = min(100, count * 12 + (20 if count else 0))
        ranked.append({"keyword": phrase, "score": score})
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


def _position_pattern(keyword: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    keyword = keyword.lower().strip()
    title_count = 0
    title_front_count = 0
    asin_hits = []
    for result in results:
        title = str(result.get("title") or "").lower()
        if keyword and keyword in title:
            title_count += 1
            asin = result.get("asin")
            if asin:
                asin_hits.append(asin)
            if keyword in " ".join(_title_tokens(title)[:8]):
                title_front_count += 1
    return {
        "title_count": title_count,
        "title_front_count": title_front_count,
        "asin_hits": asin_hits[:5],
    }


def _top20_asins(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, result in enumerate(results[:20], start=1):
        rows.append({
            "rank": index,
            "asin": result.get("asin") or "暂无",
            "title": result.get("title") or "暂无",
        })
    return rows


def _title_tokens(title: str | None) -> list[str]:
    raw = re.findall(r"[a-zA-Z0-9]+", title or "")
    return [token.lower() for token in raw if token.lower() not in STOPWORDS and len(token) > 1]


def _valid_phrase(tokens: list[str]) -> bool:
    return bool(tokens) and not all(token.isdigit() for token in tokens)


def _looks_like_brand_prefix(tokens: list[str]) -> bool:
    if len(tokens[0]) <= 3 or tokens[0] in PRODUCT_NOUN_HINTS:
        return False
    return any(token in PRODUCT_NOUN_HINTS for token in tokens[1:5])
