import json
import logging
import re
from statistics import median
from typing import Any

from schemas.aihub import ChatMessage, GenTxtRequest
from services.aihub import AIHubService

logger = logging.getLogger(__name__)


def _num(value: Any) -> float | None:
    if value is None:
        return None
    found = re.search(r"[\d,.]+", str(value))
    if not found:
        return None
    try:
        return float(found.group(0).replace(",", ""))
    except ValueError:
        return None


def _int(value: Any) -> int:
    number = _num(value)
    return int(number or 0)


def _clean_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in sorted(items, key=lambda row: int(row.get("searchRank") or 999)):
        asin = str(item.get("asin") or "").upper()
        if not asin or asin in seen:
            continue
        seen.add(asin)
        price = _num(
            item.get("price")
            if item.get("price") is not None
            else item.get("searchPrice")
            if item.get("searchPrice") is not None
            else item.get("priceText")
            or item.get("searchPriceText")
        )
        rating = _num(item.get("rating"))
        review_count = _int(item.get("reviewCount"))
        rank = int(item.get("searchRank") or len(cleaned) + 1)
        cleaned.append({
            "searchRank": rank,
            "asin": asin,
            "title": str(item.get("title") or "")[:300],
            "price": price,
            "priceText": str(item.get("priceText") or item.get("searchPriceText") or item.get("price") or ""),
            "rating": rating,
            "reviewCount": review_count,
            "isSponsored": bool(item.get("isSponsored")),
            "status": str(item.get("status") or ""),
            "brand": str(item.get("brand") or ""),
            "category": str(item.get("category") or ""),
        })
    return cleaned[:40]


def _price_band(price: float | None, prices: list[float]) -> str:
    if price is None or not prices:
        return "unknown"
    ordered = sorted(prices)
    q1 = ordered[max(0, int(len(ordered) * 0.25) - 1)]
    q2 = median(ordered)
    q3 = ordered[max(0, int(len(ordered) * 0.75) - 1)]
    if price <= q1:
        return "low"
    if price <= q2:
        return "mainstream"
    if price <= q3:
        return "mid_high"
    return "premium"


def _band_label(band: str) -> str:
    return {
        "low": "低价带",
        "mainstream": "主流价带",
        "mid_high": "中高价带",
        "premium": "高价带",
        "unknown": "价格缺失",
    }.get(band, band)


def _score_item(item: dict[str, Any], prices: list[float], median_reviews: float) -> int:
    score = 50
    rank = int(item.get("searchRank") or 40)
    reviews = int(item.get("reviewCount") or 0)
    rating = item.get("rating") or 0
    price = item.get("price")
    band = _price_band(price, prices)

    if rank > 20:
        score += 14
    elif rank <= 10:
        score -= 10
    if reviews and reviews < max(300, median_reviews * 0.55):
        score += 18
    elif reviews > max(1500, median_reviews * 1.5):
        score -= 12
    if rating >= 4.4:
        score += 8
    elif 0 < rating < 4.0:
        score += 10
    if band in {"mainstream", "mid_high"}:
        score += 8
    if item.get("isSponsored"):
        score -= 6
    if item.get("status") not in {"ok", "partial", "search_snapshot"}:
        score -= 8
    return max(0, min(100, round(score)))


def _rule_analysis(keyword: str, marketplace: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _clean_items(items)
    prices = [row["price"] for row in rows if isinstance(row.get("price"), (int, float)) and row["price"] > 0]
    review_values = [row["reviewCount"] for row in rows if row.get("reviewCount")]
    median_price = median(prices) if prices else None
    median_reviews = median(review_values) if review_values else 0
    top20 = [row for row in rows if row["searchRank"] <= 20]
    mid20 = [row for row in rows if 21 <= row["searchRank"] <= 40]
    sponsored_count = sum(1 for row in rows if row.get("isSponsored"))

    table_rows = []
    bands: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        band = _price_band(row.get("price"), prices)
        score = _score_item(row, prices, median_reviews)
        segment = "top20" if row["searchRank"] <= 20 else "mid20"
        if score >= 76:
            tag = "重点机会"
        elif score >= 64:
            tag = "可观察"
        elif row["searchRank"] <= 20 and row.get("reviewCount", 0) >= median_reviews:
            tag = "头部门槛"
        else:
            tag = "普通样本"
        enriched = {
            **row,
            "segment": segment,
            "priceBand": band,
            "priceBandLabel": _band_label(band),
            "opportunityScore": score,
            "opportunityTag": tag,
            "analysisReason": (
                f"Rank {row['searchRank']}，{_band_label(band)}，评论数{row.get('reviewCount') or 0}，"
                f"评分{row.get('rating') or '-'}。"
            ),
        }
        table_rows.append(enriched)
        bands.setdefault(band, []).append(enriched)

    price_bands = []
    for band, band_rows in bands.items():
        valid_prices = [row["price"] for row in band_rows if isinstance(row.get("price"), (int, float))]
        valid_reviews = [row["reviewCount"] for row in band_rows if row.get("reviewCount")]
        avg_score = round(sum(row["opportunityScore"] for row in band_rows) / max(1, len(band_rows)))
        price_bands.append({
            "band": band,
            "label": _band_label(band),
            "count": len(band_rows),
            "minPrice": min(valid_prices) if valid_prices else None,
            "maxPrice": max(valid_prices) if valid_prices else None,
            "medianReviews": median(valid_reviews) if valid_reviews else 0,
            "sponsoredCount": sum(1 for row in band_rows if row.get("isSponsored")),
            "avgOpportunityScore": avg_score,
            "opportunityLevel": "high" if avg_score >= 70 else "medium" if avg_score >= 58 else "low",
        })
    price_bands.sort(key=lambda row: row["avgOpportunityScore"], reverse=True)

    best_band = price_bands[0] if price_bands else {}
    top_review_gate = median([row["reviewCount"] for row in top20 if row.get("reviewCount")] or [0])
    mid_low_review_count = sum(1 for row in mid20 if row.get("reviewCount", 0) and row["reviewCount"] < max(300, top_review_gate * 0.45))
    headline = "中段存在切入机会" if mid_low_review_count >= 3 else "头部门槛偏高，需谨慎切入"

    return {
        "keyword": keyword,
        "marketplace": marketplace,
        "status": "ok",
        "analysisSource": "rules",
        "headline": headline,
        "summary": {
            "totalListings": len(rows),
            "top20Count": len(top20),
            "mid20Count": len(mid20),
            "medianPrice": median_price,
            "medianReviews": median_reviews,
            "sponsoredCount": sponsored_count,
            "sponsoredRatio": round(sponsored_count / max(1, len(rows)), 2),
            "top20MedianReviews": top_review_gate,
            "mid20LowReviewCount": mid_low_review_count,
        },
        "priceBands": price_bands,
        "recommendedPriceBand": best_band,
        "tableRows": table_rows,
        "opportunityAsins": [row for row in table_rows if row["opportunityScore"] >= 70][:10],
        "risks": [
            "Top20评论门槛较高，新品需要广告和差异化主图配合。" if top_review_gate >= 1000 else "Top20评论门槛不算极端，可以继续拆中段机会。",
            "Sponsored占比较高，需区分自然排名和广告推上来的样本。" if sponsored_count >= 8 else "广告位占比未明显过高，但仍需保留Sponsored标记。",
        ],
        "recommendations": [
            f"优先验证{best_band.get('label', '主流价带')}，观察低评论但排名进入21-40的ASIN。",
            "把机会ASIN加入上表，后续用关键词销量验证和Listing诊断继续确认。",
        ],
    }


def _json_from_text(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except Exception:
            return None
    return None


async def analyze_top40_market(keyword: str, marketplace: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    base = _rule_analysis(keyword, marketplace, items)
    try:
        service = AIHubService()
        compact_items = [
            {
                "rank": row["searchRank"],
                "asin": row["asin"],
                "title": row["title"][:160],
                "price": row["price"],
                "rating": row["rating"],
                "reviews": row["reviewCount"],
                "sponsored": row["isSponsored"],
                "segment": row["segment"],
                "priceBand": row["priceBand"],
                "opportunityScore": row["opportunityScore"],
            }
            for row in base["tableRows"]
        ]
        prompt = {
            "task": "Analyze Amazon Top40 competitor snapshot for ASIN selection. Do not invent data.",
            "keyword": keyword,
            "marketplace": marketplace,
            "rule_analysis": {
                "summary": base["summary"],
                "priceBands": base["priceBands"],
                "recommendedPriceBand": base["recommendedPriceBand"],
                "risks": base["risks"],
            },
            "items": compact_items,
            "required_json_schema": {
                "headline": "short Chinese conclusion",
                "executiveSummary": ["3-5 Chinese bullets"],
                "marketOpportunity": "Chinese paragraph",
                "entryStrategy": ["3-5 Chinese actions"],
                "riskWarnings": ["2-4 Chinese risks"],
                "tableAnnotations": [{"asin": "ASIN", "aiTag": "标签", "aiReason": "短理由"}],
            },
        }
        response = await service.gentxt(
            GenTxtRequest(
                messages=[
                    ChatMessage(role="system", content="你是 AlignX ASIN选品市场机会分析Agent。只返回JSON，不输出Markdown。"),
                    ChatMessage(role="user", content=json.dumps(prompt, ensure_ascii=False)),
                ],
                model="AI_REASONING_MODEL",
                temperature=0.2,
                max_tokens=3000,
            )
        )
        ai = _json_from_text(response.content or "")
        if ai:
            annotation_map = {str(row.get("asin", "")).upper(): row for row in ai.get("tableAnnotations", []) if isinstance(row, dict)}
            for row in base["tableRows"]:
                note = annotation_map.get(row["asin"])
                if note:
                    row["aiTag"] = str(note.get("aiTag") or row["opportunityTag"])
                    row["aiReason"] = str(note.get("aiReason") or row["analysisReason"])
            base.update({
                "analysisSource": "ai",
                "headline": ai.get("headline") or base["headline"],
                "executiveSummary": ai.get("executiveSummary") or [],
                "marketOpportunity": ai.get("marketOpportunity") or "",
                "entryStrategy": ai.get("entryStrategy") or [],
                "riskWarnings": ai.get("riskWarnings") or base["risks"],
                "model": response.model,
                "usage": response.usage,
            })
            return base
    except Exception as exc:
        logger.info("Top40 AI analysis fell back to rules: %s", exc)

    base["executiveSummary"] = [
        f"共分析{base['summary']['totalListings']}个Listing，Top20看门槛，中段20看机会。",
        f"推荐优先观察{base.get('recommendedPriceBand', {}).get('label', '主流价带')}。",
        f"Sponsored占比约{round(base['summary']['sponsoredRatio'] * 100)}%，分析时需单独标记广告样本。",
    ]
    base["marketOpportunity"] = base["headline"]
    base["entryStrategy"] = base["recommendations"]
    base["riskWarnings"] = base["risks"]
    return base
