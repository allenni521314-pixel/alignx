import json
import logging
import math
import os
import re
import asyncio
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user, get_user_scope_ids
from models.asin_keyword_sales_validation import (
    AsinKeywordIntentScore,
    AsinKeywordRankSnapshot,
    AsinKeywordSalesValidationReport,
)
from models.action_snapshots import ActionSnapshot
from schemas.auth import UserResponse
from services.amazon_scraper import scrape_amazon_product
from services.amazon_skill_toolbox import build_asin_selection_assist
from services.ai_gateway import AgentRequest, AIGatewayService
from services.core_engine_adapter import CoreEngineBusinessAdapter
from services.cosmo_operator_agent import CosmoOperatorAgent
from services.local_hermes_client import LocalHermesClient, LocalHermesError
from services.scrapling_amazon_capture import SCRAPLING_TOP40_RULES, capture_top40_batch
from services.top40_market_analysis import analyze_top40_market, _rule_analysis
from services.review_miner import mine_competitor_weaknesses

router = APIRouter(prefix="/api/v1/asin-selection", tags=["asin-selection"])
logger = logging.getLogger(__name__)
_HERMES_KEYWORD_RESEARCH_LOCK = asyncio.Lock()
_HERMES_KEYWORD_TASK_CREATE_LOCK = asyncio.Lock()
_HERMES_KEYWORD_RESEARCH_ACTIVE_TASK_ID: str | None = None
_HERMES_KEYWORD_RESEARCH_TASKS: dict[str, dict[str, Any]] = {}
_HERMES_KEYWORD_ALLOWED_TOOLS = {
    "browser_back",
    "browser_click",
    "browser_navigate",
    "browser_press",
    "browser_snapshot",
    "browser_scroll",
    "browser_type",
    "browser_vision",
}
_HERMES_KEYWORD_FORBIDDEN_TOOLS = {
    "execute_code",
    "terminal",
    "read_file",
    "write_file",
    "edit_file",
    "skill_view",
    "skill_manage",
    "skills_list",
    "browser_console",
}


class KeywordSalesValidationRequest(BaseModel):
    asin: str
    marketplace: str = "US"
    category: str = ""
    target_keywords: list[str] = Field(default_factory=list)
    competitor_asins: list[str] = Field(default_factory=list)
    days_range: int = 30
    inventory_status: str = ""
    is_own_product: bool = False


class KeywordRankCrawlRequest(KeywordSalesValidationRequest):
    pass


class ScraplingTop40BatchRequest(BaseModel):
    keyword: str = Field(..., min_length=2, max_length=120)
    marketplace: str = "US"
    batch_index: int = Field(1, ge=1, le=4)
    include_details: bool = False


class Top40MarketAnalysisRequest(BaseModel):
    keyword: str = Field(..., min_length=2, max_length=120)
    marketplace: str = "US"
    items: list[dict[str, Any]] = Field(default_factory=list)


class HermesKeywordResearchRequest(BaseModel):
    keyword: str = Field(..., min_length=2, max_length=120)
    marketplace: str = "US"
    max_keywords: int = Field(3, ge=1, le=4)
    batches_per_keyword: int = Field(1, ge=1, le=1)


TOP40_DAILY_RUN_LIMIT = 5
TOP40_MIN_RUN_INTERVAL_HOURS = 1


def _num(value: Any) -> float:
    if value is None:
        return 0
    found = re.search(r"[\d,.]+", str(value))
    if not found:
        return 0
    try:
        return float(found.group(0).replace(",", ""))
    except ValueError:
        return 0


def _clean_keyword(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff\\s+-]", " ", value or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def _has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value or ""))


def _extract_json_object(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text or "{}")
        return data if isinstance(data, dict) else None
    except Exception:
        pass
    start = (text or "").find("{")
    end = (text or "").rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except Exception:
            return None
    return None


async def _hermes_research_keywords(keyword: str, marketplace: str, limit: int) -> tuple[list[dict[str, str]], bool, str]:
    cleaned = _clean_keyword(keyword)
    fallback = [{"keyword": cleaned or keyword.strip(), "source": "用户输入"}]
    display_source = "搜索词矩阵"
    try:
        service = AIGatewayService()
        if not service.status().configured:
            return fallback, False, display_source
        model = service.select_model("light")
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 AlignX 舒老师关键词研究助手。"
                    "只基于用户输入生成 Amazon 搜索词矩阵，不编造市场数据。"
                    "输出必须是JSON对象。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "keyword": keyword,
                        "marketplace": marketplace,
                        "limit": limit,
                        "required_schema": {
                            "research_keywords": [
                                {"keyword": "Amazon search keyword", "source": "主词/产品形态/使用场景/技术路线/相邻形态"}
                            ]
                        },
                        "rules": [
                            "第一个词必须尽量贴近用户输入。",
                            "其余词用于覆盖不同产品形态、使用场景、技术路线或相邻形态。",
                            "不要输出解释，不要输出市场结论。",
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        response = await service.unified.chat_completion(
            messages=messages,
            model=model,
            temperature=0.2,
            response_format_json=True,
        )
        data = _extract_json_object(response.content or "") or {}
        rows = data.get("research_keywords") or []
        if not isinstance(rows, list):
            rows = []
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        seed_rows = rows if (marketplace or "US").upper() == "US" and _has_cjk(keyword) else [{"keyword": keyword, "source": "用户输入"}, *rows]
        for row in seed_rows:
            item_keyword = _clean_keyword(str(row.get("keyword") if isinstance(row, dict) else row))
            if not item_keyword or item_keyword in seen:
                continue
            seen.add(item_keyword)
            result.append({
                "keyword": item_keyword,
                "source": str(row.get("source") or display_source) if isinstance(row, dict) else display_source,
            })
            if len(result) >= limit:
                break
        return (result or fallback), True, display_source
    except Exception as exc:
        logger.info("Hermes keyword expansion fell back to input keyword: %s", exc)
        return fallback, False, display_source


def _classify_technology_route(item: dict[str, Any]) -> str:
    text = " ".join(
        str(item.get(key) or "")
        for key in ["title", "brand", "category", "bulletPoints", "bestSellerCategory"]
    ).lower()
    route_rules = [
        ("喷雾/酶解", ["enzyme", "spray", "stain remover", "urine destroyer"]),
        ("活性炭", ["activated charcoal", "carbon filter", "bamboo charcoal", "charcoal"]),
        ("臭氧", ["ozone generator", "ozone odor", "ozone"]),
        ("负离子", ["negative ion", "ionizer", "plug in air purifier", "plug-in air purifier"]),
        ("UV-C", ["uv-c", "uv c", "ultraviolet", "uv light", "sanitizer"]),
        ("HEPA复合", ["hepa filter", "4-in-1", "air purifier"]),
        ("光触媒", ["photocatalyst", "photocatalytic", "tio2"]),
        ("蜡烛/凝胶", ["candle", "gel", "beads", "solid air freshener"]),
    ]
    for route, words in route_rules:
        if any(word in text for word in words):
            return route
    return "其他"


def _median_number(values: list[Any]) -> float:
    numbers = [float(v) for v in values if isinstance(v, (int, float)) and float(v) > 0]
    return float(median(numbers)) if numbers else 0


def _build_keyword_six_dimension(
    keyword: str,
    items: list[dict[str, Any]],
    analyses: list[dict[str, Any]],
    route_summary: list[dict[str, Any]],
) -> dict[str, Any]:
    total = len(items)
    if total <= 0:
        analysis = {
            "需求强度": {"basis": "未获取到真实搜索页样本。", "opinion": "不做需求强度判断，先补真实样本。"},
            "搜索入口": {"basis": "未获取到自然位或广告位样本。", "opinion": "不判断入口压力，先完成关键词页面取样。"},
            "竞争结构": {"basis": "未获取到Top20样本。", "opinion": "不判断竞争结构，先补头部搜索结果。"},
            "差异化切口": {"basis": "未获取到产品标题、价格、评论等样本。", "opinion": "不推断差异化路线。"},
            "商业承受力": {"basis": "未获取到价格样本。", "opinion": "不测算价格带和利润承受力。"},
            "风险与趋势": {"basis": "未获取到市场样本。", "opinion": "不做趋势、合规、差评风险判断。"},
        }
        return {
            "success": False,
            "asin": "",
            "product_title": keyword,
            "total_score": None,
            "qualified": False,
            "dimension_scores": {},
            "detail_scores": {},
            "analysis": analysis,
            "suggestions": ["待补真实样本"],
            "confidence_level": "low",
            "risk_level": "unknown",
            "decision": "待补样本",
            "pool_status": "not_entered",
            "recommended_path": "selection",
            "one_sentence_reason": "未获取到真实市场样本，不生成选品判断。",
            "analysis_mode": "keyword_market_snapshot",
            "sample_status": "insufficient",
            "ai_called": False,
        }
    top20_items = [row for row in items if int(row.get("searchRank") or 999) <= 20]
    prices = [row.get("price") if row.get("price") is not None else row.get("searchPrice") for row in items]
    reviews = [row.get("reviewCount") for row in items]
    median_reviews = _median_number(reviews)
    sponsored_count = sum(1 for row in items if row.get("isSponsored"))
    route_count = len([row for row in route_summary if row.get("count")])
    low_review_ranked = sum(
        1
        for row in top20_items
        if int(row.get("reviewCount") or 0) > 0 and int(row.get("reviewCount") or 0) <= max(300, median_reviews * 0.55)
    )
    price_count = len([value for value in prices if isinstance(value, (int, float)) and float(value) > 0])
    price_median = _median_number(prices)
    top_routes = [row for row in route_summary if row.get("count")][:3]
    route_text = "、".join(
        f"{row.get('route')}({row.get('count')})"
        for row in top_routes
        if row.get("route")
    ) or "暂无"
    lane_headlines = [
        str(row.get("headline") or "").strip()
        for row in analyses
        if str(row.get("headline") or "").strip()
    ]
    lane_text = "；".join(list(dict.fromkeys(lane_headlines))[:3]) or "暂无"
    ai_scores = [
        int(row.get("recommendedPriceBand", {}).get("avgOpportunityScore") or 0)
        for row in analyses
        if isinstance(row.get("recommendedPriceBand"), dict)
    ]
    base_opportunity = round(sum(ai_scores) / max(1, len(ai_scores))) if ai_scores else 55
    dimension_scores = {
        "demand": max(35, min(92, 45 + min(30, total * 2) + (8 if median_reviews >= 500 else 0))),
        "search_entry": max(30, min(90, 42 + min(25, total) - min(20, sponsored_count * 3))),
        "competition": max(25, min(88, 62 + low_review_ranked * 6 - (12 if median_reviews >= 2000 else 0))),
        "differentiation": max(30, min(90, 45 + route_count * 7 + low_review_ranked * 4)),
        "business": max(30, min(86, 42 + min(24, price_count * 3) + (8 if base_opportunity >= 65 else 0))),
        "risk_trend": max(25, min(86, 62 - min(20, sponsored_count * 2) + min(12, route_count * 2))),
    }
    analysis = {
        "需求强度": {
            "basis": (
                f"搜索页形成{total}个有效样本，Top20可观察样本{len(top20_items)}个，"
                f"评论中位数{round(median_reviews)}。"
            ),
            "opinion": (
                "头部评论门槛高，需求已被验证但新品进入要避开正面硬打。"
                if median_reviews >= 1500
                else "评论门槛不算极端，可继续验证需求稳定性。"
            ),
        },
        "搜索入口": {
            "basis": f"自然样本{max(0, total - sponsored_count)}个，广告样本{sponsored_count}个。",
            "opinion": (
                "广告位压力偏高，进入前要验证自然排名入口和长尾词入口。"
                if sponsored_count >= max(8, total * 0.25)
                else "广告位压力暂未明显压住自然入口，可继续找细分关键词。"
            ),
        },
        "竞争结构": {
            "basis": f"Top20低评论高排名样本{low_review_ranked}个，评论中位数{round(median_reviews)}。",
            "opinion": (
                "存在低评论高排名样本，可围绕这些样本拆切入口。"
                if low_review_ranked
                else "头部样本评论优势明显，新品直接打主词难度偏高。"
            ),
        },
        "差异化切口": {
            "basis": f"识别到{route_count}类产品路线：{route_text}。",
            "opinion": (
                "路线分散，适合比较不同形态、场景和痛点表达。"
                if route_count >= 3
                else "路线集中，差异化需要从场景、功能或痛点表达里找。"
            ),
        },
        "商业承受力": {
            "basis": f"有效价格样本{price_count}个，价格中位数{price_median:.2f}美元，价格带机会分{base_opportunity}。",
            "opinion": (
                "价格带有承接空间，可继续核算成本、广告承受力和利润空间。"
                if base_opportunity >= 65
                else "价格带机会一般，需要先算成本和获客压力。"
            ),
        },
        "风险与趋势": {
            "basis": f"搜索词判断：{lane_text}。",
            "opinion": (
                "样本分布有分化，需继续验证趋势、合规和差评痛点。"
                if route_count >= 2
                else "样本路线集中，需防止同质化和价格战。"
            ),
        },
    }
    total_score = round(sum(dimension_scores.values()) / len(dimension_scores))
    return {
        "success": True,
        "asin": "",
        "product_title": keyword,
        "total_score": total_score,
        "qualified": total_score >= 65,
        "dimension_scores": dimension_scores,
        "detail_scores": dimension_scores,
        "analysis": analysis,
        "suggestions": [],
        "confidence_level": "medium" if total >= 20 else "low",
        "risk_level": "medium",
        "decision": "可进入验证" if total_score >= 65 else "补证后再评估",
        "pool_status": "opportunity_pool" if total_score >= 70 else "validation_pool" if total_score >= 58 else "not_entered",
        "recommended_path": "launch_check",
        "one_sentence_reason": analysis["竞争结构"],
        "analysis_mode": "keyword_market_snapshot",
        "sample_status": "sufficient",
        "ai_called": False,
    }


def _build_keyword_decision_points(
    keyword: str,
    research_keywords: list[dict[str, str]],
    items: list[dict[str, Any]],
    analyses: list[dict[str, Any]],
    route_summary: list[dict[str, Any]],
    six_dimension: dict[str, Any],
) -> list[dict[str, Any]]:
    total = len(items)
    if total <= 0:
        keyword_text = "、".join([row.get("keyword") or "" for row in research_keywords[:4] if row.get("keyword")]) or keyword
        return [
            {
                "point": "真实需求",
                "status": "待补样本",
                "basis": "未获取到真实搜索页样本。",
                "opinion": "不做需求判断，先完成关键词页面取样。",
            },
            {
                "point": "买家意图",
                "status": "待补样本",
                "basis": f"搜索词：{keyword_text}。",
                "opinion": "搜索词已生成，但必须结合真实搜索结果再判断。",
            },
            {
                "point": "搜索入口",
                "status": "待补样本",
                "basis": "自然样本0，广告样本0。",
                "opinion": "不判断入口压力，先取真实样本。",
            },
            {
                "point": "竞争结构",
                "status": "待补样本",
                "basis": "Top20样本0。",
                "opinion": "不判断头部壁垒和新品切入口。",
            },
            {
                "point": "差异化机会",
                "status": "待补样本",
                "basis": "产品路线：暂无。",
                "opinion": "不推断差异化路线。",
            },
            {
                "point": "商业承受力",
                "status": "待补样本",
                "basis": "价格样本0。",
                "opinion": "不测算成本、广告承受力和价格带。",
            },
            {
                "point": "风险判断",
                "status": "待补样本",
                "basis": "未获取到市场样本。",
                "opinion": "不做趋势、合规、偏差和售后风险判断。",
            },
            {
                "point": "进入方式",
                "status": "待补样本",
                "basis": "无真实样本，不生成机会评分。",
                "opinion": "待补真实样本后再决定。",
            },
        ]
    top20_items = [row for row in items if int(row.get("searchRank") or 999) <= 20]
    prices = [row.get("price") if row.get("price") is not None else row.get("searchPrice") for row in items]
    reviews = [row.get("reviewCount") for row in items]
    median_reviews = _median_number(reviews)
    median_price = _median_number(prices)
    sponsored_count = sum(1 for row in items if row.get("isSponsored"))
    organic_count = max(0, total - sponsored_count)
    top20_low_review = sum(
        1
        for row in top20_items
        if int(row.get("reviewCount") or 0) > 0 and int(row.get("reviewCount") or 0) <= max(300, median_reviews * 0.55)
    )
    opportunity_rows: list[dict[str, Any]] = []
    price_bands: list[dict[str, Any]] = []
    lane_headlines: list[str] = []
    for analysis in analyses:
        if not isinstance(analysis, dict):
            continue
        lane_headline = str(analysis.get("headline") or "").strip()
        if lane_headline:
            lane_headlines.append(lane_headline)
        opportunity_rows.extend(analysis.get("opportunityAsins") or [])
        price_bands.extend(analysis.get("priceBands") or [])
    best_price_band = sorted(
        [row for row in price_bands if isinstance(row, dict)],
        key=lambda row: int(row.get("avgOpportunityScore") or 0),
        reverse=True,
    )[:1]
    route_names = [str(row.get("route") or "").strip() for row in route_summary if row.get("route")]
    route_text = "、".join(route_names[:4]) or "暂无"
    keyword_text = "、".join([row.get("keyword") or "" for row in research_keywords[:4] if row.get("keyword")]) or keyword
    demand_score = int((six_dimension.get("dimension_scores") or {}).get("demand") or 0)
    entry_score = int((six_dimension.get("dimension_scores") or {}).get("search_entry") or 0)
    competition_score = int((six_dimension.get("dimension_scores") or {}).get("competition") or 0)
    differentiation_score = int((six_dimension.get("dimension_scores") or {}).get("differentiation") or 0)
    business_score = int((six_dimension.get("dimension_scores") or {}).get("business") or 0)
    risk_score = int((six_dimension.get("dimension_scores") or {}).get("risk_trend") or 0)
    total_score = int(six_dimension.get("total_score") or 0)
    decision = str(six_dimension.get("decision") or "待录入")

    def level(score: int) -> str:
        if score >= 72:
            return "可验证"
        if score >= 58:
            return "需补证"
        return "暂缓"

    return [
        {
            "point": "真实需求",
            "status": level(demand_score),
            "basis": f"关键词样本已形成商品池，评论中位数{round(median_reviews)}。",
            "opinion": "先确认需求是否稳定，再决定是否进入。" if demand_score < 72 else "需求已被市场验证，可进入判断。",
        },
        {
            "point": "买家意图",
            "status": "可验证" if len(research_keywords) >= 2 else "需补证",
            "basis": f"搜索词：{keyword_text}。",
            "opinion": "按主词、形态词、场景词拆开看，不把所有需求混成一个市场。",
        },
        {
            "point": "搜索入口",
            "status": level(entry_score),
            "basis": f"自然样本{organic_count}，广告样本{sponsored_count}。",
            "opinion": "优先验证自然排名入口和长尾词入口。" if entry_score >= 58 else "主词入口压力偏高，先换更窄关键词。",
        },
        {
            "point": "竞争结构",
            "status": level(competition_score),
            "basis": f"Top20低评论样本{top20_low_review}，机会样本{len(opportunity_rows)}。",
            "opinion": "围绕低评论高排名样本拆切入口。" if top20_low_review else "头部壁垒偏强，避免直接正面打主词。",
        },
        {
            "point": "差异化机会",
            "status": level(differentiation_score),
            "basis": f"产品路线：{route_text}。",
            "opinion": "从产品形态、使用场景、痛点表达中找差异化。" if route_names else "差异化证据不足，需要继续拆评论和场景。",
        },
        {
            "point": "商业承受力",
            "status": level(business_score),
            "basis": f"价格中位数{median_price:.2f}美元，价格带{best_price_band[0].get('label') if best_price_band else '暂无'}。",
            "opinion": "进入前必须核算成本、广告承受力、退货和仓储压力。",
        },
        {
            "point": "风险判断",
            "status": level(risk_score),
            "basis": "；".join(list(dict.fromkeys(lane_headlines))[:3]) or "待补充关键词样本。",
            "opinion": "继续复查趋势、合规、侵权、差评痛点和售后风险。",
        },
        {
            "point": "进入方式",
            "status": level(total_score),
            "basis": f"综合评分{total_score}/100，建议{decision}。",
            "opinion": "先小样本验证，再决定主品、细分品、配件或放弃。",
        },
    ]


async def _synthesize_hermes_keyword_result(
    keyword: str,
    marketplace: str,
    research_keywords: list[dict[str, str]],
    route_summary: list[dict[str, Any]],
    analyses: list[dict[str, Any]],
    six_dimension: dict[str, Any],
    decision_points: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_score = six_dimension.get("total_score")
    score = int(raw_score) if isinstance(raw_score, (int, float)) else None
    rows = [
        {
            "keyword": row.get("keyword"),
            "headline": row.get("analysis", {}).get("headline") if isinstance(row.get("analysis"), dict) else row.get("headline"),
            "summary": row.get("analysis", {}).get("summary") if isinstance(row.get("analysis"), dict) else row.get("summary"),
            "top_items": [
                {
                    "rank": item.get("searchRank"),
                    "asin": item.get("asin") or "暂无",
                    "title": item.get("title"),
                    "price": item.get("price") or item.get("priceText"),
                    "rating": item.get("rating"),
                    "reviews": item.get("reviewCount"),
                    "source": item.get("source"),
                }
                for item in ((row.get("analysis", {}) or {}).get("tableRows") or [])[:8]
            ] if isinstance(row.get("analysis"), dict) else [],
        }
        for row in analyses
    ]
    fact_lines: list[str] = []
    for row in rows:
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        top_items = row.get("top_items") if isinstance(row.get("top_items"), list) else []
        sample_count = summary.get("totalListings") or summary.get("sampleCount") or len(top_items)
        median_price = summary.get("medianPrice")
        median_reviews = summary.get("medianReviews")
        parts = [f"搜索词：{row.get('keyword') or '待录入'}", f"样本：{sample_count or '暂无'}"]
        if median_price:
            parts.append(f"价格中位数：{float(median_price):.2f}美元")
        if median_reviews:
            parts.append(f"评论中位数：{round(float(median_reviews))}")
        fact_lines.append(" / ".join(parts))
        for item in top_items[:3]:
            fact_lines.append(
                " / ".join(
                    [
                        f"排名：{item.get('rank') or '暂无'}",
                        f"ASIN：{item.get('asin') or '暂无'}",
                        f"标题：{item.get('title') or '暂无'}",
                        f"价格：{item.get('price') or '暂无'}",
                        f"评论：{item.get('reviews') or '暂无'}",
                    ]
                )
            )
    if not fact_lines:
        fact_lines = [
            f"搜索词：{keyword} / 样本：{len(research_keywords) or '暂无'}",
            f"市场路线：{len(route_summary) or '暂无'}",
        ]
    decision_point_lines = [
        f"{row.get('point') or '待录入'}：{row.get('status') or '待录入'}；{row.get('basis') or '暂无'}；{row.get('opinion') or '暂无'}"
        for row in decision_points
    ]
    semantic_lines = [
        f"{row.get('keyword') or '待录入'}：{row.get('headline') or '暂无'}。"
        for row in rows
        if row.get("keyword")
    ]
    semantic_lines.extend(
        [
            f"{route.get('route') or '待录入'}：样本{route.get('count') or '暂无'}，价格中位数{float(route.get('medianPrice') or 0):.2f}美元，评论中位数{round(float(route.get('medianReviews') or 0))}。"
            for route in route_summary[:6]
        ]
    )
    reasoning_lines = []
    for row in rows:
        for item in (row.get("top_items") or [])[:4]:
            reasoning_lines.append(
                " / ".join(
                    [
                        f"搜索词：{row.get('keyword') or '待录入'}",
                        f"Rank：{item.get('rank') or '暂无'}",
                        f"ASIN：{item.get('asin') or '暂无'}",
                        f"价格：{item.get('price') or '暂无'}",
                        f"评论：{item.get('reviews') or '暂无'}",
                    ]
                )
            )
    if not reasoning_lines:
        reasoning_lines = [six_dimension.get("one_sentence_reason") or "暂无"]
    dimension_analysis = six_dimension.get("analysis") if isinstance(six_dimension.get("analysis"), dict) else {}
    decision_lines = [
        f"机会评分：{score}/100。" if score is not None else "机会评分：待补样本。",
        f"建议：{six_dimension.get('decision') or '待录入'}。",
        *[
            f"{title}：{(detail.get('basis') + ' ' + detail.get('opinion')) if isinstance(detail, dict) else detail}"
            for title, detail in list(dimension_analysis.items())[:6]
        ],
    ]
    validation_lines = [
        f"复查关键词：{row.get('keyword') or '待录入'}。"
        for row in rows[:4]
        if row.get("keyword")
    ]
    validation_lines.extend(
        [
            f"复查样本：{item.get('asin') or '暂无'} / Rank {item.get('rank') or '暂无'} / {item.get('title') or '暂无'}"
            for row in rows[:2]
            for item in (row.get("top_items") or [])[:2]
        ]
    )

    # ── Competitor weakness mining ──
    weakness_data = mine_competitor_weaknesses(route_summary, decision_points)
    fallback = {
        "score": score,
        "confidence": six_dimension.get("confidence_level") or "low",
        "risk_level": six_dimension.get("risk_level") or "medium",
        "fact_layer": fact_lines,
        "semantic_layer": decision_point_lines[:4] or semantic_lines or ["暂无"],
        "reasoning_layer": reasoning_lines or ["暂无"],
        "decision_layer": decision_point_lines[4:] or decision_lines or ["暂无"],
        "validation_suggestions": validation_lines or [row.get("opinion") for row in decision_points if row.get("opinion")] or ["暂无"],
        "selection_decision_points": decision_points,
        "problems": [],
        "actions": [],
        "next_step": {"module": six_dimension.get("recommended_path") or "launch_check", "path": "/listing-diagnosis?view=launch-check", "reason": "进入验证。"},
        "evidence_sources": [
            {
                "source_type": "amazon_search_snapshot",
                "source_ref": "scrapling_top40_batch",
                "evidence_tier": "market_feedback",
                "confidence": "medium",
                "summary": f"{marketplace}站关键词搜索样本。",
            }
        ],
        "validation_hypotheses": [],
        "learning_update": {
            "can_enter_learning_memory": False,
            "hit_status": "待验证",
            "miss_reason": "",
            "reusable_learning": "",
            "next_round_action": "",
        },
        "blocked_by": [],
        "sample_status": six_dimension.get("sample_status") or "unknown",
        "competitor_weaknesses": weakness_data,
    }
    if six_dimension.get("sample_status") == "insufficient":
        fallback["blocked_by"] = ["未获取到真实市场样本"]
        fallback["next_step"] = {
            "module": "selection",
            "path": "/asin-manager",
            "reason": "待补真实样本。",
        }
        return fallback
    try:
        service = AIGatewayService()
        if not service.status().configured:
            return fallback
        response = await service.run_agent(
            AgentRequest(
                agent="selection_agent",
                task=(
                    "基于关键词研究样本输出关键词选品完整调研报告。"
                    "必须按事实层、语义层、推理层、决策层、验证建议组织。"
                    "必须引用market_rows里的搜索词、排名、标题、价格、评分、评论样本。"
                    "不要输出任何内部模型名称。"
                ),
                payload={
                    "keyword": keyword,
                    "marketplace": marketplace,
                    "research_keywords": research_keywords,
                    "route_summary": route_summary,
                    "market_rows": rows,
                    "six_dimension": six_dimension,
                    "selection_decision_points": decision_points,
                    "competitor_weaknesses": weakness_data,
                },
                depth="deep",
                dry_run=False,
            )
        )
        result = response.result.model_dump()
        result["selection_decision_points"] = decision_points
        return result
    except Exception as exc:
        logger.info("Hermes keyword synthesis fell back to rules: %s", exc)
        return fallback


async def _top40_usage(db: AsyncSession, user_id: str) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    run_filter = ActionSnapshot.input_snapshot.like('%"batch_index": 1%')
    query = select(func.count()).select_from(ActionSnapshot).where(
        ActionSnapshot.user_id == user_id,
        ActionSnapshot.module_key == "asin_selection",
        ActionSnapshot.action_key == "scrapling_top40_batch",
        run_filter,
        ActionSnapshot.created_at >= since,
    )
    result = await db.execute(query)
    used = int(result.scalar() or 0)
    latest_query = (
        select(ActionSnapshot.created_at)
        .where(
            ActionSnapshot.user_id == user_id,
            ActionSnapshot.module_key == "asin_selection",
            ActionSnapshot.action_key == "scrapling_top40_batch",
            run_filter,
        )
        .order_by(ActionSnapshot.created_at.desc())
        .limit(1)
    )
    latest_result = await db.execute(latest_query)
    latest_started_at = latest_result.scalar()
    next_allowed_at = None
    if latest_started_at:
        if latest_started_at.tzinfo is None:
            latest_started_at = latest_started_at.replace(tzinfo=timezone.utc)
        next_allowed_at = latest_started_at + timedelta(hours=TOP40_MIN_RUN_INTERVAL_HOURS)
    return {
        "usedRuns": used,
        "remainingRuns": max(0, TOP40_DAILY_RUN_LIMIT - used),
        "dailyRunLimit": TOP40_DAILY_RUN_LIMIT,
        "minIntervalHours": TOP40_MIN_RUN_INTERVAL_HOURS,
        "latestRunStartedAt": latest_started_at.isoformat() if latest_started_at else None,
        "nextAllowedAt": next_allowed_at.isoformat() if next_allowed_at else None,
        "windowHours": 24,
    }


async def _has_keyword_history(db: AsyncSession, user_id: str, keyword: str, marketplace: str) -> bool:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    normalized_keyword = keyword.strip()
    normalized_marketplace = (marketplace or "US").upper()
    query = (
        select(ActionSnapshot.id)
        .where(
            ActionSnapshot.user_id == user_id,
            ActionSnapshot.module_key == "asin_selection",
            ActionSnapshot.action_key == "scrapling_top40_batch",
            ActionSnapshot.created_at >= since,
            ActionSnapshot.input_snapshot.like(f'%"keyword": "{normalized_keyword}"%'),
            ActionSnapshot.input_snapshot.like(f'%"marketplace": "{normalized_marketplace}"%'),
        )
        .limit(1)
    )
    result = await db.execute(query)
    return result.scalar() is not None


def _derive_keywords(title: str, category: str = "", limit: int = 10) -> list[str]:
    text = f"{title} {category}".lower()
    candidates: list[str] = []
    words = [w for w in re.split(r"[^a-z0-9]+", text) if len(w) >= 4]
    for size in (3, 2):
        for i in range(0, max(0, len(words) - size + 1)):
            candidates.append(" ".join(words[i : i + size]))
    seen: set[str] = set()
    result = []
    for kw in candidates:
        cleaned = _clean_keyword(kw)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _keyword_quality(keyword: str, title: str, category: str) -> dict[str, Any]:
    kw_words = [w for w in re.split(r"[^a-z0-9]+", keyword.lower()) if len(w) >= 2]
    text = f"{title} {category}".lower()
    matched = sum(1 for word in kw_words if word in text)
    relevance = round(100 * matched / max(1, len(kw_words)))
    long_tail_bonus = min(20, max(0, len(kw_words) - 2) * 8)
    conversion = max(20, min(100, relevance * 0.75 + long_tail_bonus + (10 if any(w in keyword for w in ["for", "odor", "waterproof", "usb", "men"]) else 0)))
    volume = max(500, int((12000 - len(kw_words) * 1800) * (0.5 + relevance / 200)))
    cpc = round(0.45 + (100 - min(relevance, 100)) / 100 + max(0, 4 - len(kw_words)) * 0.18, 2)
    competition = "high" if len(kw_words) <= 2 else "medium" if len(kw_words) == 3 else "low"
    intent_type = "long_tail_conversion" if len(kw_words) >= 4 else "core_search" if relevance >= 60 else "exploratory"
    return {
        "keyword": keyword,
        "estimated_search_volume": volume,
        "estimated_cpc": cpc,
        "competition_level": competition,
        "relevance_score": relevance,
        "intent_type": intent_type,
        "conversion_intent_score": round(conversion),
    }


def _rank_snapshot(asin: str, marketplace: str, keyword: str, product: dict[str, Any], quality: dict[str, Any], crawl_time: datetime) -> dict[str, Any]:
    bsr = _num(product.get("bsr_rank"))
    reviews = _num(product.get("review_count"))
    relevance = float(quality["relevance_score"])
    has_promo = bool(product.get("coupon") or product.get("deal_status"))
    organic_position = None
    if relevance >= 75:
        organic_position = 4 if bsr and bsr <= 2000 else 9 if reviews >= 300 else 16
    elif relevance >= 45:
        organic_position = 18 if bsr and bsr <= 5000 else 32
    elif relevance >= 20:
        organic_position = 45
    # Coupon/Deal is a promotion signal, not proof that every keyword is ad-driven.
    # Only treat weakly related keywords as likely sponsored exposure in this
    # estimated snapshot; strong relevance should first be credited as organic.
    sponsored_position = 2 if has_promo and relevance < 45 else 6 if has_promo and relevance < 75 else None
    is_organic = organic_position is not None and organic_position <= 48
    is_sponsored = sponsored_position is not None
    overall = min([p for p in [organic_position, sponsored_position] if p], default=None)
    return {
        "asin": asin,
        "keyword": keyword,
        "search_page": math.ceil((overall or 49) / 16),
        "organic_position": organic_position,
        "sponsored_position": sponsored_position,
        "overall_position": overall,
        "is_organic": is_organic,
        "is_sponsored": is_sponsored,
        "rank_type": "estimated_search_snapshot",
        "crawl_time": crawl_time,
        "marketplace": marketplace,
    }


async def _scrapling_rank_snapshots(
    asin: str,
    marketplace: str,
    keywords: list[str],
    crawl_time: datetime,
) -> tuple[list[dict[str, Any]], list[str]]:
    ranks: list[dict[str, Any]] = []
    errors: list[str] = []
    target_asin = asin.strip().upper()
    for keyword in keywords[:3]:
        keyword_items: list[dict[str, Any]] = []
        for batch_index in range(1, 5):
            try:
                batch = await capture_top40_batch(keyword=keyword, marketplace=marketplace, batch_index=batch_index, include_details=False)
            except Exception as exc:
                errors.append(f"{keyword}: batch_{batch_index}: {str(exc)[:160]}")
                break
            if batch.get("status") == "blocked":
                errors.append(f"{keyword}: batch_{batch_index}: blocked")
                break
            keyword_items.extend(batch.get("items") or [])
            if any(str(item.get("asin") or "").upper() == target_asin for item in keyword_items):
                break

        matched = [item for item in keyword_items if str(item.get("asin") or "").upper() == target_asin]
        organic_positions = [int(item["searchRank"]) for item in matched if not item.get("isSponsored") and item.get("searchRank")]
        sponsored_positions = [int(item["searchRank"]) for item in matched if item.get("isSponsored") and item.get("searchRank")]
        organic_position = min(organic_positions) if organic_positions else None
        sponsored_position = min(sponsored_positions) if sponsored_positions else None
        overall = min([p for p in [organic_position, sponsored_position] if p], default=None)
        ranks.append(
            {
                "asin": target_asin,
                "keyword": keyword,
                "search_page": math.ceil((overall or 49) / 16),
                "organic_position": organic_position,
                "sponsored_position": sponsored_position,
                "overall_position": overall,
                "is_organic": organic_position is not None and organic_position <= 40,
                "is_sponsored": sponsored_position is not None,
                "rank_type": "scrapling_top40_search_snapshot" if overall else "scrapling_top40_not_found",
                "crawl_time": crawl_time,
                "marketplace": marketplace,
            }
        )
    return ranks, errors


def _traffic_level(score: float) -> str:
    if score >= 80:
        return "关键词销量健康，适合进入机会池"
    if score >= 65:
        return "基本可信，但需要继续观察"
    if score >= 50:
        return "销量结构不稳定，谨慎进入"
    return "销量可信度低，不建议作为选品参考"


def _is_inventory_blocked(product: dict[str, Any]) -> bool:
    stock_status = str(product.get("stock_status") or "").lower()
    manual_inventory_status = str(product.get("manual_inventory_status") or "").lower()
    availability = str(product.get("availability") or "").lower()
    if manual_inventory_status in {"out_of_stock", "zero_inventory", "unavailable", "not_available"}:
        return True
    if stock_status == "unavailable":
        return True
    return any(
        term in availability
        for term in [
            "currently unavailable",
            "temporarily out of stock",
            "out of stock",
            "currently not available",
            "无货",
            "暂时缺货",
            "目前无货",
            "不可用",
        ]
    )


def _normalize_keyword_sales_report(report: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy keyword-sales reports before returning them to the UI."""
    if not isinstance(report, dict):
        return {}

    summary = report.get("keyword_rank_summary")
    if not isinstance(summary, dict):
        summary = {}
        report["keyword_rank_summary"] = summary

    ad_risk = _num(report.get("ad_dependency_risk"))
    rank_snapshots = report.get("rank_snapshots") if isinstance(report.get("rank_snapshots"), list) else []
    sponsored_count = sum(1 for row in rank_snapshots if isinstance(row, dict) and row.get("is_sponsored"))
    rank_source = str(summary.get("rank_data_source") or "")
    has_real_search_snapshot = rank_source == "scrapling_top40_search" or any(
        isinstance(row, dict) and str(row.get("rank_type") or "").startswith("scrapling_top40")
        for row in rank_snapshots
    )
    organic_strength = _num(report.get("organic_rank_strength"))
    product = report.get("product_snapshot") if isinstance(report.get("product_snapshot"), dict) else {}
    if _is_inventory_blocked(product):
        report["keyword_sales_score"] = 0
        report["traffic_quality_level"] = "无库存/不可售，销量来源不可判定"
        report["sales_source_judgment"] = "待补库存后验证"
        report["organic_rank_strength"] = 0
        report["ad_dependency_risk"] = 0
        summary["inventory_blocker"] = True
        summary["stock_status"] = product.get("stock_status") or "unavailable"
        summary["availability"] = product.get("availability") or ""
        summary["inventory_note"] = "该ASIN当前显示无库存或不可售，关键词销量验证不成立；请补库存并上架可售后重新抓取自然位、广告位和BSR。"
        report["suspicious_signals"] = ["ASIN当前无库存/不可售，不能据此判断销量来源。"]
        report["final_recommendation"] = "先补库存并确认页面可售，再重新进行关键词销量验证。"
        report["market_validation_assist"] = build_asin_selection_assist(report)
        return report

    # Legacy reports saved ad_dependency_risk=0 when no Sponsored slot was
    # captured. That is missing evidence, not proof of zero ad dependence.
    if ad_risk <= 0 and sponsored_count == 0:
        evidence_floor = 20 if has_real_search_snapshot and organic_strength >= 75 else 28
        if not has_real_search_snapshot:
            evidence_floor = 35
        report["ad_dependency_risk"] = evidence_floor
        summary["ad_risk_level"] = (
            "优秀自然流量结构" if evidence_floor <= 20 else "健康可控" if evidence_floor <= 35 else "需要观察"
        )
        summary["ad_risk_note"] = (
            "未抓到Sponsored广告位时，系统按优秀卖家的低风险下限20%处理；这代表低广告依赖风险，不代表广告依赖为0。"
            if has_real_search_snapshot and organic_strength >= 75
            else "当前广告位证据不足，系统不把缺失广告位当成0风险；建议用不同时段/账号复查Sponsored位置。"
        )

    if not isinstance(report.get("market_validation_assist"), dict):
        report["market_validation_assist"] = build_asin_selection_assist(report)
    if not isinstance(report.get("v5_market_decision"), dict):
        report["v5_market_decision"] = _build_v5_market_decision(report)
    if not isinstance(report.get("market_evolution_matrix"), dict):
        report["market_evolution_matrix"] = _empty_market_evolution_matrix()
    if not isinstance(report.get("solution_evolution"), dict):
        report["solution_evolution"] = _empty_solution_evolution()
    report.setdefault("decision_standard", CosmoOperatorAgent.public_standard_meta("asin_selection"))

    return report


def _v5_opportunity_level(action: str, score: float) -> str:
    if action == "Scale" or score >= 75:
        return "建议推进"
    if action == "Continue" or score >= 55:
        return "小预算验证"
    if action == "Close" or score < 35:
        return "建议放弃"
    return "暂缓观察"


def _v5_next_step(level: str, inventory_blocked: bool) -> str:
    if inventory_blocked:
        return "补齐可售状态后重新验证"
    if level == "建议推进":
        return "进入Listing承接"
    if level == "小预算验证":
        return "补充验证样本"
    if level == "建议放弃":
        return "放弃该机会"
    return "加入观察池"


def _build_v5_market_decision(report: dict[str, Any], core_cycle: dict[str, Any] | None = None) -> dict[str, Any]:
    summary = report.get("keyword_rank_summary") if isinstance(report.get("keyword_rank_summary"), dict) else {}
    inventory_blocked = bool(summary.get("inventory_blocker"))
    capital = core_cycle.get("capital_decision") if isinstance(core_cycle, dict) and isinstance(core_cycle.get("capital_decision"), dict) else {}
    success_probability = round(_num(capital.get("priority_score")) or _num(report.get("keyword_sales_score")))
    demand_strength = round(_num(report.get("keyword_sales_score")))
    competition_pressure = round(min(100, max(_num(report.get("ad_dependency_risk")), 100 - _num(report.get("organic_rank_strength")))))
    rank_count = len(report.get("rank_snapshots") or [])
    validation_cost = "低" if rank_count >= 8 and not inventory_blocked else "中" if rank_count >= 3 else "高"
    risks = report.get("suspicious_signals") if isinstance(report.get("suspicious_signals"), list) else []
    risk_keywords = report.get("risk_keywords") if isinstance(report.get("risk_keywords"), list) else []
    max_risk = str(risks[0]) if risks else str(risk_keywords[0]) if risk_keywords else "暂无"
    action = str(capital.get("suggested_action") or "")
    opportunity_level = "暂缓观察" if inventory_blocked else _v5_opportunity_level(action, success_probability)
    return {
        "success_probability": success_probability,
        "demand_strength": demand_strength,
        "competition_pressure": competition_pressure,
        "validation_cost": validation_cost,
        "max_risk": max_risk,
        "opportunity_level": opportunity_level,
        "next_step": _v5_next_step(opportunity_level, inventory_blocked),
    }


def _empty_market_evolution_matrix() -> dict[str, Any]:
    return {
        "horizontal_evolution_index": None,
        "technology_evolution_index": None,
        "current_position": "待录入",
        "recommendation": "待录入",
    }


def _empty_solution_evolution() -> dict[str, Any]:
    return {
        "generations": [],
        "solved_problems": [],
        "unsolved_problems": [],
        "current_opportunity": "待录入",
    }


def _bounded_index(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return None


def _text_list(value: Any, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _normalize_market_evolution_payload(payload: dict[str, Any]) -> dict[str, Any]:
    matrix = payload.get("market_evolution_matrix") if isinstance(payload.get("market_evolution_matrix"), dict) else {}
    solution = payload.get("solution_evolution") if isinstance(payload.get("solution_evolution"), dict) else {}
    horizontal_source = (
        matrix.get("horizontal_evolution_index")
        if matrix.get("horizontal_evolution_index") is not None
        else matrix.get("meaning_evolution_index")
    )
    horizontal_index = _bounded_index(horizontal_source)
    technology_index = _bounded_index(matrix.get("technology_evolution_index"))
    return {
        "market_evolution_matrix": {
            "horizontal_evolution_index": horizontal_index,
            "technology_evolution_index": technology_index,
            "current_position": str(matrix.get("current_position") or "待录入").strip() or "待录入",
            "recommendation": str(matrix.get("recommendation") or "待录入").strip() or "待录入",
        },
        "solution_evolution": {
            "generations": _text_list(solution.get("generations")),
            "solved_problems": _text_list(solution.get("solved_problems")),
            "unsolved_problems": _text_list(solution.get("unsolved_problems")),
            "current_opportunity": str(solution.get("current_opportunity") or "待录入").strip() or "待录入",
        },
    }


def _market_evolution_input(report: dict[str, Any]) -> dict[str, Any]:
    product = report.get("product_snapshot") if isinstance(report.get("product_snapshot"), dict) else {}
    summary = report.get("keyword_rank_summary") if isinstance(report.get("keyword_rank_summary"), dict) else {}
    return {
        "product": {
            "asin": product.get("asin"),
            "title": product.get("title"),
            "brand": product.get("brand"),
            "category": product.get("category"),
            "price": product.get("price"),
            "rating": product.get("rating"),
            "review_count": product.get("review_count"),
            "bsr_rank": product.get("bsr_rank"),
            "image_count": product.get("image_count"),
            "aplus_status": product.get("aplus_status"),
            "video_status": product.get("video_status"),
        },
        "keywords": {
            "opportunity_keywords": report.get("opportunity_keywords") or [],
            "risk_keywords": report.get("risk_keywords") or [],
            "target_keywords": [
                item.get("keyword")
                for item in report.get("keyword_intent_scores") or []
                if isinstance(item, dict) and item.get("keyword")
            ],
        },
        "market_facts": {
            "rank_data_source": summary.get("rank_data_source"),
            "core_keywords_checked": summary.get("core_keywords_checked"),
            "organic_top20_count": summary.get("organic_top20_count"),
            "sponsored_keyword_count": summary.get("sponsored_keyword_count"),
            "keyword_sales_score": report.get("keyword_sales_score"),
        },
    }


async def _attach_market_evolution_reasoning(report: dict[str, Any]) -> dict[str, Any]:
    gateway = AIGatewayService()
    if not gateway.status().configured:
        report["market_evolution_matrix"] = _empty_market_evolution_matrix()
        report["solution_evolution"] = _empty_solution_evolution()
        report["market_evolution_source"] = "ai_not_configured"
        return report

    system_prompt = (
        "你是 AlignX 市场演化矩阵推理模型。必须只输出JSON对象。\n"
        "X轴是横向演化：同一核心功能下，材质、外形、颜色、细分类目、使用场景、人群、风格、使用位置等变化。\n"
        "Y轴是技术演化：解决方案、技术路线、机制、代际升级变化。\n"
        "禁止把广告位、自然排名、Sponsored密度、投放强度当成X轴或Y轴来源。\n"
        "根据产品属性推理，不确定时使用待录入或空数组。\n"
        "输出字段必须为："
        '{"market_evolution_matrix":{"horizontal_evolution_index":0-100或null,"technology_evolution_index":0-100或null,"current_position":"横向红海 / 技术红海|横向红海 / 技术蓝海|横向蓝海 / 技术红海|横向蓝海 / 技术蓝海|待录入","recommendation":"一句卖家可执行方向或待录入"},"solution_evolution":{"generations":["第一代方案","第二代方案"],"solved_problems":[""],"unsolved_problems":[""],"current_opportunity":"一句机会或待录入"}}'
    )
    try:
        payload = await asyncio.wait_for(
            gateway.run_json(
                system_prompt=system_prompt,
                payload=_market_evolution_input(report),
                module="asin_selection.market_evolution_matrix",
                depth="deep",
            ),
            timeout=60,
        )
        normalized = _normalize_market_evolution_payload(payload)
        report["market_evolution_matrix"] = normalized["market_evolution_matrix"]
        report["solution_evolution"] = normalized["solution_evolution"]
        report["market_evolution_source"] = "deepseek_v4_reasoning"
    except Exception as exc:
        logger.warning("market evolution reasoning failed: %s", exc)
        report["market_evolution_matrix"] = _empty_market_evolution_matrix()
        report["solution_evolution"] = _empty_solution_evolution()
        report["market_evolution_source"] = "reasoning_unavailable"
    return report


def _build_report(asin: str, marketplace: str, category: str, product: dict[str, Any], ranks: list[dict[str, Any]], qualities: list[dict[str, Any]], days_range: int) -> dict[str, Any]:
    bsr = _num(product.get("bsr_rank"))
    reviews = _num(product.get("review_count"))
    has_promo = bool(product.get("coupon") or product.get("deal_status"))
    inventory_blocked = _is_inventory_blocked(product)
    organic_positions = [r["organic_position"] for r in ranks if r.get("organic_position")]
    sponsored_count = sum(1 for r in ranks if r.get("is_sponsored"))
    core = ranks[: min(3, len(ranks))]
    core_good = sum(1 for r in core if r.get("organic_position") and r["organic_position"] <= 20)
    long_tail = [q for q in qualities if len(str(q["keyword"]).split()) >= 3 and q["relevance_score"] >= 45]
    organic_strength = round(max(0, 100 - (sum(organic_positions) / max(1, len(organic_positions))) * 2)) if organic_positions else 0
    top20_count = sum(1 for r in ranks if r.get("organic_position") and r["organic_position"] <= 20)
    top20_coverage = top20_count / max(1, len(ranks))
    sponsored_ratio = sponsored_count / max(1, len(ranks))
    rank_types = {str(r.get("rank_type") or "") for r in ranks}
    has_real_search_snapshot = any(rank_type.startswith("scrapling_top40") for rank_type in rank_types)
    ad_signal = sponsored_ratio * 60 + (12 if has_promo else 0) + (25 if not organic_positions else 0)
    organic_credit = organic_strength * 0.45 + top20_coverage * 25
    bsr_credit = 0
    if organic_positions and bsr:
        if bsr <= 100:
            bsr_credit = 15
        elif bsr <= 1000:
            bsr_credit = 10
        elif bsr <= 5000:
            bsr_credit = 6
    raw_ad_risk = max(0, min(100, ad_signal - organic_credit - bsr_credit))
    # Do not show 0 risk just because no Sponsored slot was captured. Top40
    # snapshots are sparse and ad placement changes by time, account and query.
    # A zero here would imply "no ad risk", which is too strong for seller use.
    if sponsored_count == 0:
        evidence_floor = 20 if has_real_search_snapshot and organic_strength >= 75 else 28
        if not has_real_search_snapshot:
            evidence_floor = 35
        raw_ad_risk = max(raw_ad_risk, evidence_floor)
    ad_risk = round(raw_ad_risk)
    core_match = round(core_good / max(1, len(core)) * 25)
    long_tail_score = min(15, len(long_tail) * 3)
    stability_score = 10 if organic_positions else 2
    ad_score = max(0, 15 - round(ad_risk * 0.15))
    bsr_score = 15 if (bsr and bsr <= 5000 and organic_strength >= 45) or (not bsr and organic_strength >= 55) else 7 if bsr and organic_strength >= 20 else 3
    review_score = 10 if reviews >= 100 and organic_strength >= 35 else 6 if reviews >= 50 else 3
    promo_penalty = 5 if has_promo else 0
    total = max(0, min(100, core_match + long_tail_score + stability_score + ad_score + bsr_score + review_score - promo_penalty))
    if organic_strength >= 80 and ad_risk <= 20:
        total = max(total, 78 if top20_coverage < 0.6 else 85)

    suspicious: list[str] = []
    if bsr and bsr <= 3000 and organic_strength < 35:
        suspicious.append("BSR靠前但核心关键词自然排名弱，可能不是自然搜索驱动。")
    if ad_risk >= 55 and organic_strength < 55:
        suspicious.append("广告位或促销信号较强，存在广告依赖型销量风险。")
    if has_promo:
        suspicious.append("当前伴随 Coupon/Deal，销量表现可能被促销放大。")
    if reviews >= 500 and organic_strength < 30:
        suspicious.append("评论体量较高但关键词覆盖弱，需要排查站外或历史促销流量。")

    if organic_strength >= 80 and ad_risk <= 20 and top20_coverage < 0.6:
        judgment = "核心词自然流量强，长尾覆盖不足"
    elif organic_strength >= 80 and ad_risk <= 20:
        judgment = "自然流量优秀"
    elif total >= 80:
        judgment = "自然流量健康"
    elif ad_risk >= 55 and organic_strength < 55:
        judgment = "广告依赖型销量"
    elif has_promo and ad_risk >= 35:
        judgment = "促销辅助销量"
    elif bsr and bsr <= 3000 and organic_strength < 35:
        judgment = "非自然搜索驱动"
    elif has_promo and organic_strength < 60:
        judgment = "促销驱动销量"
    elif total < 50:
        judgment = "销量来源可疑"
    else:
        judgment = "基本可信，继续观察"

    opportunity = [q["keyword"] for q in qualities if q["conversion_intent_score"] >= 65 and q["relevance_score"] >= 45][:8]
    risk_keywords = [r["keyword"] for r in ranks if not r.get("organic_position") or (r.get("organic_position") or 99) > 35][:8]
    summary = {
        "core_keywords_checked": len(core),
        "organic_top20_count": sum(1 for r in ranks if r.get("organic_position") and r["organic_position"] <= 20),
        "organic_top50_count": len(organic_positions),
        "sponsored_keyword_count": sponsored_count,
        "avg_organic_position": round(sum(organic_positions) / len(organic_positions), 1) if organic_positions else None,
        "rank_data_source": "scrapling_top40_search" if has_real_search_snapshot else "estimated_search_snapshot",
        "rank_data_note": (
            "当前使用核心关键词亚马逊Top40搜索快照，区分自然位和Sponsored广告位。"
            if has_real_search_snapshot
            else "当前为风险雷达估算快照，建议接入真实关键词排名数据源校准。"
        ),
        "ad_risk_note": (
            "未抓到Sponsored广告位时，系统按优秀卖家的低风险下限20%处理，不再显示0；请用不同时段/账号复查广告位。"
            if sponsored_count == 0
            else "已抓到Sponsored广告位，广告依赖风险按广告位占比、自然位和促销信号综合计算。"
        ),
        "ad_risk_level": "优秀自然流量结构" if ad_risk <= 20 else "健康可控" if ad_risk <= 35 else "需要观察" if ad_risk <= 55 else "广告依赖风险高",
    }
    if inventory_blocked:
        summary.update(
            {
                "inventory_blocker": True,
                "stock_status": product.get("stock_status") or "unavailable",
                "availability": product.get("availability") or "",
                "inventory_note": "该ASIN当前显示无库存或不可售，关键词销量验证不成立；请补库存并上架可售后重新抓取自然位、广告位和BSR。",
                "ad_risk_level": "库存阻断，暂不判断",
            }
        )
        blocked_report = {
            "asin": asin,
            "marketplace": marketplace,
            "days_range": days_range,
            "product_snapshot": product,
            "keyword_sales_score": 0,
            "traffic_quality_level": "无库存/不可售，销量来源不可判定",
            "sales_source_judgment": "待补库存后验证",
            "keyword_rank_summary": summary,
            "organic_rank_strength": 0,
            "ad_dependency_risk": 0,
            "suspicious_signals": ["ASIN当前无库存/不可售，不能据此判断销量来源。"],
            "opportunity_keywords": [],
            "risk_keywords": [r["keyword"] for r in ranks[:8]],
            "rank_snapshots": ranks,
            "keyword_intent_scores": qualities,
            "final_recommendation": "先补库存并确认页面可售，再重新进行关键词销量验证；不要把当前无销量误判为广告或促销驱动。",
        }
        blocked_report["market_validation_assist"] = build_asin_selection_assist(blocked_report)
        blocked_report["market_evolution_matrix"] = _empty_market_evolution_matrix()
        blocked_report["solution_evolution"] = _empty_solution_evolution()
        return blocked_report
    report = {
        "asin": asin,
        "marketplace": marketplace,
        "days_range": days_range,
        "product_snapshot": product,
        "keyword_sales_score": total,
        "traffic_quality_level": _traffic_level(total),
        "sales_source_judgment": judgment,
        "keyword_rank_summary": summary,
        "organic_rank_strength": organic_strength,
        "ad_dependency_risk": ad_risk,
        "suspicious_signals": suspicious,
        "opportunity_keywords": opportunity,
        "risk_keywords": risk_keywords,
        "rank_snapshots": ranks,
        "keyword_intent_scores": qualities,
        "final_recommendation": "适合作为候选机会继续验证。" if total >= 65 else "建议先补充真实关键词排名、广告曝光和7-30天评论/BSR趋势后再决定。",
    }
    report["market_validation_assist"] = build_asin_selection_assist(report)
    report["market_evolution_matrix"] = _empty_market_evolution_matrix()
    report["solution_evolution"] = _empty_solution_evolution()
    return report


async def _generate_validation(request: KeywordSalesValidationRequest, user_id: str, db: AsyncSession, save_report: bool = True) -> dict[str, Any]:
    asin = request.asin.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{10}", asin):
        raise HTTPException(status_code=400, detail="请输入有效的10位ASIN")
    marketplace = (request.marketplace or "US").upper()
    crawl_time = datetime.now(timezone.utc)
    scraped = await scrape_amazon_product(asin, marketplace)
    product = {
        "asin": asin,
        "title": scraped.get("title") or "",
        "brand": scraped.get("brand") or "",
        "category": request.category or scraped.get("category") or "",
        "price": scraped.get("price") or "",
        "rating": scraped.get("rating") or "",
        "review_count": scraped.get("review_count") or "",
        "bsr_rank": scraped.get("bsr_rank") or "",
        "coupon": scraped.get("coupon") or "",
        "deal_status": scraped.get("deal_status") or "",
        "availability": scraped.get("availability") or "",
        "stock_status": scraped.get("stock_status") or "unknown",
        "manual_inventory_status": request.inventory_status or "",
        "is_own_product": bool(request.is_own_product),
        "image_count": scraped.get("image_count") or "",
        "aplus_status": bool(scraped.get("has_a_plus")),
        "video_status": bool(scraped.get("has_video")),
        "crawl_time": crawl_time.isoformat(),
        "data_source": scraped.get("data_source") or "amazon_scrape",
    }
    keywords = [_clean_keyword(k) for k in request.target_keywords if _clean_keyword(k)]
    if not keywords:
        keywords = _derive_keywords(product["title"], product["category"], 10)
    if not keywords:
        keywords = [asin.lower()]

    qualities = [_keyword_quality(keyword, product["title"], product["category"]) for keyword in keywords]
    ranks, rank_errors = await _scrapling_rank_snapshots(asin, marketplace, keywords, crawl_time)
    if not ranks or all(not rank.get("overall_position") for rank in ranks):
        ranks = [_rank_snapshot(asin, marketplace, q["keyword"], product, q, crawl_time) for q in qualities]
        rank_errors = rank_errors + ["scrapling_top40_no_match_fallback_to_estimated"]
    report = _build_report(asin, marketplace, product["category"], product, ranks, qualities, request.days_range)
    if rank_errors:
        report["keyword_rank_summary"]["rank_capture_errors"] = rank_errors[:8]
    report = await _attach_market_evolution_reasoning(report)
    try:
        operator_agent = CosmoOperatorAgent(db)
        operator_context = await operator_agent.build_context(
            user_id=user_id,
            workflow="asin_selection",
            product=product,
            asin=asin,
            marketplace=marketplace,
        )
        report = operator_agent.attach_result_metadata(report, operator_context, product=product)
    except Exception:
        report.setdefault("decision_standard", CosmoOperatorAgent.public_standard_meta("asin_selection"))

    try:
        opc_payload = await CoreEngineBusinessAdapter(db, user_id).evaluate_cycle(
            source_type="asin_selection",
            source_id=asin,
            opportunity_id=asin,
            opportunity_score=float(report.get("keyword_sales_score") or 0),
            risk_score=max(0, 100 - float(report.get("keyword_sales_score") or 0)),
            information_gain=100 if report.get("rank_snapshots") else 0,
            evidence_count=len(report.get("rank_snapshots") or []),
            evidence_quality=float(report.get("keyword_sales_score") or 0),
            sample_size=len(report.get("rank_snapshots") or []),
            conversion_signal=0,
            consistency=float(report.get("organic_rank_strength") or 0),
            statistical_confidence=100 if report.get("keyword_rank_summary", {}).get("rank_data_source") == "scrapling_top40_search" else 50 if report.get("rank_snapshots") else 0,
            metrics={},
        )
        report["v5_market_decision"] = _build_v5_market_decision(report, opc_payload)
        report["opc_v5_execution"] = opc_payload
    except Exception as exc:
        logger.warning("asin_selection v5 market decision failed for %s: %s", asin, exc)
        report["v5_market_decision"] = _build_v5_market_decision(report)

    for rank in ranks:
        db.add(AsinKeywordRankSnapshot(user_id=user_id, **rank))
    for quality in qualities:
        db.add(AsinKeywordIntentScore(user_id=user_id, marketplace=marketplace, category=product["category"], crawl_time=crawl_time, **quality))
    if save_report:
        db.add(
            AsinKeywordSalesValidationReport(
                user_id=user_id,
                asin=asin,
                marketplace=marketplace,
                category=product["category"],
                days_range=request.days_range,
                keyword_sales_score=report["keyword_sales_score"],
                traffic_quality_level=report["traffic_quality_level"],
                sales_source_judgment=report["sales_source_judgment"],
                organic_rank_strength=report["organic_rank_strength"],
                ad_dependency_risk=report["ad_dependency_risk"],
                product_snapshot=json.dumps(product, ensure_ascii=False),
                keyword_rank_summary=json.dumps(report["keyword_rank_summary"], ensure_ascii=False),
                suspicious_signals=json.dumps(report["suspicious_signals"], ensure_ascii=False),
                opportunity_keywords=json.dumps(report["opportunity_keywords"], ensure_ascii=False),
                risk_keywords=json.dumps(report["risk_keywords"], ensure_ascii=False),
                final_recommendation=report["final_recommendation"],
                report_payload=json.dumps(report, ensure_ascii=False, default=str),
                created_at=crawl_time,
            )
        )
    await db.commit()
    return report


@router.post("/keyword-sales-validation")
async def keyword_sales_validation(
    request: KeywordSalesValidationRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _generate_validation(request, str(current_user.id), db, save_report=True)


@router.post("/keyword-rank-crawl")
async def keyword_rank_crawl(
    request: KeywordRankCrawlRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await _generate_validation(request, str(current_user.id), db, save_report=False)
    return {"asin": report["asin"], "marketplace": report["marketplace"], "rank_snapshots": report["rank_snapshots"], "keyword_intent_scores": report["keyword_intent_scores"]}


@router.get("/scrapling/top40-rules")
async def scrapling_top40_rules(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    usage = await _top40_usage(db, str(current_user.id))
    return {
        "captureMode": "scrapling_top40_batch",
        "batchRanges": ["1-10", "11-20", "21-30", "31-40"],
        "rules": SCRAPLING_TOP40_RULES,
        "usage": usage,
    }


@router.post("/scrapling/top40-batch")
async def scrapling_top40_batch(
    request: ScraplingTop40BatchRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        usage = await _top40_usage(db, str(current_user.id))
        if request.batch_index == 1:
            now = datetime.now(timezone.utc)
            next_allowed_at = usage.get("nextAllowedAt")
            if usage["remainingRuns"] <= 0:
                raise HTTPException(
                    status_code=429,
                    detail=f"24小时内Top40分析额度已用完。当前限制为{TOP40_DAILY_RUN_LIMIT}次，建议使用历史快照。",
                )
            if next_allowed_at and datetime.fromisoformat(next_allowed_at) > now:
                raise HTTPException(
                    status_code=429,
                    detail=f"两次Top40分析间隔不得低于{TOP40_MIN_RUN_INTERVAL_HOURS}小时，请稍后再试或使用历史快照。",
                )
            if await _has_keyword_history(db, str(current_user.id), request.keyword, request.marketplace):
                raise HTTPException(
                    status_code=409,
                    detail="该关键词24小时内已有Top40历史快照，请直接从抓取历史载入，不重复抓取。",
                )
        result = await capture_top40_batch(
            keyword=request.keyword,
            marketplace=request.marketplace,
            batch_index=request.batch_index,
            include_details=request.include_details,
        )
        result["usage"] = usage
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/top40-market-analysis")
async def top40_market_analysis(
    request: Top40MarketAnalysisRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    if not request.items:
        raise HTTPException(status_code=400, detail="请先完成Top40抓取，再进行AI分析")
    return await analyze_top40_market(
        keyword=request.keyword,
        marketplace=request.marketplace,
        items=request.items,
    )


def _build_local_hermes_keyword_prompt(keyword: str, marketplace: str, max_keywords: int) -> str:
    schema = {
        "score": "0-100整数；无真实样本时为null",
        "confidence": "low|medium|high",
        "risk_level": "low|medium|high",
        "sample_status": "sufficient|insufficient",
        "fact_layer": ["事实层：市场真实数据"],
        "semantic_layer": ["语义层：这意味着什么"],
        "reasoning_layer": ["推理层：机会在哪"],
        "decision_layer": ["决策层：选品师的建议"],
        "validation_suggestions": ["验证建议"],
        "keyword_six_dimension": {
            "success": True,
            "total_score": "0-100整数；无真实样本时为null",
            "dimension_scores": {
                "demand": 0,
                "search_entry": 0,
                "competition": 0,
                "differentiation": 0,
                "business": 0,
                "risk_trend": 0,
            },
            "analysis": {
                "需求强度": {"basis": "真实样本依据", "opinion": "选品意见"},
                "搜索入口": {"basis": "真实样本依据", "opinion": "选品意见"},
                "竞争结构": {"basis": "真实样本依据", "opinion": "选品意见"},
                "差异化切口": {"basis": "真实样本依据", "opinion": "选品意见"},
                "商业承受力": {"basis": "真实样本依据", "opinion": "选品意见"},
                "风险与趋势": {"basis": "真实样本依据", "opinion": "选品意见"},
            },
            "decision": "可验证|需补证|暂缓|待补样本",
        },
        "selection_decision_points": [
            {"point": "真实需求", "status": "可验证|需补证|暂缓|待补样本", "basis": "依据", "opinion": "意见"},
            {"point": "买家意图", "status": "可验证|需补证|暂缓|待补样本", "basis": "依据", "opinion": "意见"},
            {"point": "搜索入口", "status": "可验证|需补证|暂缓|待补样本", "basis": "依据", "opinion": "意见"},
            {"point": "竞争结构", "status": "可验证|需补证|暂缓|待补样本", "basis": "依据", "opinion": "意见"},
            {"point": "差异化机会", "status": "可验证|需补证|暂缓|待补样本", "basis": "依据", "opinion": "意见"},
            {"point": "商业承受力", "status": "可验证|需补证|暂缓|待补样本", "basis": "依据", "opinion": "意见"},
            {"point": "风险判断", "status": "可验证|需补证|暂缓|待补样本", "basis": "依据", "opinion": "意见"},
            {"point": "进入方式", "status": "可验证|需补证|暂缓|待补样本", "basis": "依据", "opinion": "意见"},
        ],
        "market_research": {
            "keyword": keyword,
            "marketplace": marketplace,
            "research_keywords": [{"keyword": "搜索词", "source": "主词|形态词|场景词|技术路线|相邻形态"}],
            "source_steps": [{"step": "步骤", "status": "completed|partial|blocked", "source": "亚马逊搜索页|浏览器截图", "count": 0}],
            "lanes": [
                {
                    "keyword": "搜索词",
                    "source": "浏览器截图",
                    "status": "ok|partial|blocked",
                    "items": [
                        {
                            "searchRank": 1,
                            "asin": "ASIN；看不到则填暂无",
                            "title": "标题",
                            "price": 0,
                            "priceText": "价格文本",
                            "rating": 0,
                            "reviewCount": 0,
                            "isSponsored": False,
                            "source": "浏览器截图",
                            "route": "产品/技术路线",
                            "weakness": "竞品弱点",
                            "complaintSignal": "差评痛点",
                        }
                    ],
                    "analysis": {
                        "headline": "判断",
                        "summary": {
                            "totalListings": 0,
                            "top20Count": 0,
                            "medianPrice": 0,
                            "medianReviews": 0,
                            "sponsoredCount": 0,
                        },
                        "tableRows": [],
                    },
                }
            ],
            "route_summary": [{"route": "路线", "count": 0, "medianPrice": 0, "medianReviews": 0, "weakness": "弱点"}],
            "complaint_insights": [{"asin": "ASIN", "signal": "差评痛点", "evidence": "依据", "opportunity": "机会"}],
            "competitor_weaknesses": [{"asin": "ASIN", "weakness": "弱点", "evidence": "依据", "opportunity": "机会"}],
            "item_count": 0,
            "data_source": "亚马逊搜索页 / 浏览器截图",
        },
    }
    return "\n".join(
        [
            "你是 AlignX 系统里的舒老师，任务只限于关键词选品调研。",
            "本消息就是完整任务规则；不要读取、搜索或调用任何本机规则、Skill、文件或历史记忆。",
            f"关键词：{keyword}",
            f"站点：{marketplace}",
            f"最多搜索词数量：{max_keywords}",
            "",
            "任务边界：",
            "1. 必须使用 Hermes 内置 Browserbase/browser_* 浏览器工具打开亚马逊搜索页、滚动、按键、输入、截图视觉读取、必要点击和返回。",
            "2. 禁止使用 execute_code、terminal、curl、HTML解析、API抓取、本地脚本、browser_console。",
            "3. 禁止使用 skill_view、skill_manage、skills_list、read_file、write_file、edit_file、memory 或任何文件工具。",
            "4. 不读取本机规则文件，不创建文件，不保存文件，不调用 AlignX 旧抓取。",
            "5. 不绕过验证码、不登录、不访问账号/订单/地址/支付等私有数据。",
            "6. 每个搜索词只读取亚马逊搜索结果第一页可见样本，最多Top20；样本不足则如实标记。",
            "7. 样本必须来自可见亚马逊页面；看不到的字段填暂无，不要猜。",
            "8. 必须输出6维评分、每个维度的真实依据与意见、事实层、语义层、推理层、决策层、验证建议。",
            "9. 必须做竞品弱点识别；看不到评论原文时，不编造差评原文，只写搜索页可见弱点或填暂无。",
            "10. 没有真实可见样本时，score和total_score必须为null，sample_status=insufficient。",
            "11. 输出里不要写模型名、供应商名或内部模型信息。",
            "12. 如果站点是美国站或英语站，且用户关键词不是英语，必须先转成美国买家会使用的英文搜索词；原关键词只作为用户意图，不作为唯一搜索词。",
            "13. 搜索词必须围绕真实买家入口，不要用直译词硬搜；优先选择平台能返回真实商品样本的词。",
            "14. 先搜索1个最贴近买家入口的英文词；如果已获得可见商品样本，立即进入分析，不要继续扩展搜索词。",
            "15. 每个搜索词最多滚动3次；browser_vision最多使用1次，若截图超时，改用browser_snapshot可见文本继续，不要重复截图。",
            "16. 一边读取一边整理样本；只要可见样本达到10个即可输出JSON，不等待抓满Top20。",
            "17. 若搜索结果列表不可读，输出sample_status=insufficient并写明不可读原因，不要继续按键或重复打开页面。",
            "18. 只返回一个JSON对象，不要Markdown，不要代码块，不要解释。",
            "",
            "输出JSON Schema：",
            json.dumps(schema, ensure_ascii=False),
        ]
    )


def _build_route_summary(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        route = _classify_technology_route(item)
        item["route"] = route
        grouped.setdefault(route, []).append(item)
    rows: list[dict[str, Any]] = []
    for route, route_items in grouped.items():
        rows.append(
            {
                "route": route,
                "count": len(route_items),
                "medianPrice": _median_number([
                    item.get("price") if item.get("price") is not None else item.get("searchPrice")
                    for item in route_items
                ]),
                "medianReviews": _median_number([item.get("reviewCount") for item in route_items]),
                "weakness": "暂无",
            }
        )
    return sorted(rows, key=lambda row: int(row.get("count") or 0), reverse=True)


def _strip_internal_ai_meta(value: Any) -> Any:
    if isinstance(value, list):
        return [_strip_internal_ai_meta(item) for item in value]
    if not isinstance(value, dict):
        return value
    blocked_keys = {"_hermes_usage", "_hermes_session_id", "usage", "model", "provider"}
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if str(key).lower() in blocked_keys:
            continue
        cleaned[key] = _strip_internal_ai_meta(item)
    return cleaned


def _build_local_hermes_sample_synthesis_prompt(
    keyword: str,
    marketplace: str,
    research_keywords: list[dict[str, str]],
    analyses: list[dict[str, Any]],
    route_summary: list[dict[str, Any]],
    six_dimension: dict[str, Any],
    decision_points: list[dict[str, Any]],
) -> str:
    market_rows = []
    for analysis in analyses:
        table_rows = _list_value(_dict_value(analysis.get("analysis")).get("tableRows") or analysis.get("tableRows"))
        market_rows.append(
            {
                "keyword": analysis.get("keyword"),
                "summary": _dict_value(_dict_value(analysis.get("analysis")).get("summary") or analysis.get("summary")),
                "items": [
                    {
                        "rank": item.get("searchRank"),
                        "asin": item.get("asin") or "暂无",
                        "title": item.get("title") or "暂无",
                        "price": item.get("price") or item.get("priceText") or "暂无",
                        "rating": item.get("rating") or "暂无",
                        "reviews": item.get("reviewCount") or "暂无",
                        "sponsored": bool(item.get("isSponsored")),
                        "route": item.get("route") or "暂无",
                    }
                    for item in table_rows[:20]
                ],
            }
        )
    schema = {
        "score": "0-100整数",
        "confidence": "low|medium|high",
        "risk_level": "low|medium|high",
        "sample_status": "sufficient",
        "fact_layer": ["事实层：只写样本里的排名、标题、价格、评分、评论、广告位、路线"],
        "semantic_layer": ["语义层：这些样本意味着什么"],
        "reasoning_layer": ["推理层：机会在哪"],
        "decision_layer": ["决策层：选品师的建议"],
        "validation_suggestions": ["验证建议"],
        "keyword_six_dimension": {
            "total_score": 0,
            "dimension_scores": {
                "demand": 0,
                "search_entry": 0,
                "competition": 0,
                "differentiation": 0,
                "business": 0,
                "risk_trend": 0,
            },
            "analysis": {
                "需求强度": {"basis": "依据", "opinion": "意见"},
                "搜索入口": {"basis": "依据", "opinion": "意见"},
                "竞争结构": {"basis": "依据", "opinion": "意见"},
                "差异化切口": {"basis": "依据", "opinion": "意见"},
                "商业承受力": {"basis": "依据", "opinion": "意见"},
                "风险与趋势": {"basis": "依据", "opinion": "意见"},
            },
            "decision": "可验证|需补证|暂缓",
            "sample_status": "sufficient",
        },
        "selection_decision_points": decision_points,
        "market_research": {
            "keyword": keyword,
            "marketplace": marketplace,
            "research_keywords": research_keywords,
            "lanes": market_rows,
            "route_summary": route_summary,
            "item_count": sum(len(row.get("items") or []) for row in market_rows),
            "data_source": "亚马逊搜索页 / 舒老师",
        },
    }
    return "\n".join(
        [
            "你是 AlignX 系统里的舒老师，任务只限于关键词选品判断。",
            "不要使用任何工具，不要打开浏览器，不要读取文件，不要调用Skill。",
            "只基于下面JSON样本分析；样本没有的字段写暂无，不要推测。",
            "必须输出完整调研报告：6维评分、每维依据与意见、事实层、语义层、推理层、决策层、验证建议。",
            "必须做竞品弱点识别；没有评论原文时，不编造差评原文。",
            "不要输出模型名、供应商名或内部模型信息。",
            "只返回一个JSON对象，不要Markdown，不要代码块，不要解释。",
            "",
            "输入JSON：",
            json.dumps(
                {
                    "keyword": keyword,
                    "marketplace": marketplace,
                    "research_keywords": research_keywords,
                    "market_rows": market_rows,
                    "route_summary": route_summary,
                    "rule_six_dimension": six_dimension,
                    "selection_decision_points": decision_points,
                    "required_schema": schema,
                },
                ensure_ascii=False,
            ),
        ]
    )


async def _execute_sampled_hermes_keyword_research(
    keyword: str,
    marketplace: str,
    max_keywords: int,
    on_event: Any = None,
) -> dict[str, Any]:
    if on_event:
        await on_event("status.update", {"text": "生成搜索词"})
    research_keywords, _ai_called, _source = await _hermes_research_keywords(keyword, marketplace, max_keywords)
    all_items: list[dict[str, Any]] = []
    analyses: list[dict[str, Any]] = []
    source_steps: list[dict[str, Any]] = [{"step": "搜索词确认", "status": "completed", "source": "舒老师", "count": len(research_keywords)}]

    for row in research_keywords[:max_keywords]:
        search_keyword = str(row.get("keyword") or "").strip()
        if not search_keyword:
            continue
        if on_event:
            await on_event("status.update", {"text": f"读取亚马逊搜索页：{search_keyword}"})
        try:
            batch = await capture_top40_batch(keyword=search_keyword, marketplace=marketplace, batch_index=1, include_details=False)
        except Exception as exc:
            source_steps.append({"step": "读取亚马逊搜索页", "status": "blocked", "source": "亚马逊搜索页", "count": 0})
            logger.info("Hermes keyword sample capture failed for %s: %s", search_keyword, exc)
            continue
        items = [item for item in _list_value(batch.get("items")) if isinstance(item, dict)]
        source_steps.append(
            {
                "step": "读取亚马逊搜索页",
                "status": "completed" if items else "partial",
                "source": "亚马逊搜索页",
                "count": len(items),
            }
        )
        all_items.extend(items)
        if items:
            rule = _rule_analysis(search_keyword, marketplace, items)
            analyses.append({"keyword": search_keyword, "analysis": rule})
        if len(all_items) >= 10:
            break

    route_summary = _build_route_summary(all_items)
    six_dimension = _build_keyword_six_dimension(keyword, all_items, analyses, route_summary)
    decision_points = _build_keyword_decision_points(keyword, research_keywords, all_items, analyses, route_summary, six_dimension)

    if not all_items:
        fallback = await _synthesize_hermes_keyword_result(
            keyword, marketplace, research_keywords, route_summary, analyses, six_dimension, decision_points
        )
        fallback["keyword_six_dimension"] = six_dimension
        fallback["selection_decision_points"] = decision_points
        fallback["market_research"] = {
            "keyword": keyword,
            "marketplace": marketplace,
            "research_keywords": research_keywords,
            "source_steps": source_steps,
            "lanes": [],
            "route_summary": route_summary,
            "complaint_insights": [],
            "competitor_weaknesses": [],
            "item_count": 0,
            "data_source": "亚马逊搜索页 / 舒老师",
        }
        return _build_hermes_keyword_response(keyword, marketplace, _normalize_local_hermes_keyword_result(fallback, keyword, marketplace))

    if on_event:
        await on_event("status.update", {"text": "舒老师分析市场样本"})
    prompt = _build_local_hermes_sample_synthesis_prompt(
        keyword, marketplace, research_keywords, analyses, route_summary, six_dimension, decision_points
    )
    try:
        raw_result = await LocalHermesClient().run_json(
            prompt,
            title=f"AlignX 舒老师样本分析 {keyword} {datetime.now().strftime('%Y%m%d%H%M%S')}",
            cwd=os.getcwd(),
            on_event=on_event,
        )
        hermes_result = _normalize_local_hermes_keyword_result(raw_result, keyword, marketplace)
    except Exception as exc:
        logger.info("Local Hermes sample synthesis fell back to sampled rules for %s: %s", keyword, exc)
        hermes_result = await _synthesize_hermes_keyword_result(
            keyword, marketplace, research_keywords, route_summary, analyses, six_dimension, decision_points
        )
        hermes_result = _normalize_local_hermes_keyword_result(hermes_result, keyword, marketplace)

    hermes_result["sample_status"] = "sufficient"
    hermes_result["score"] = hermes_result.get("score") if hermes_result.get("score") is not None else six_dimension.get("total_score")
    current_six = _dict_value(hermes_result.get("keyword_six_dimension"))
    if not current_six.get("dimension_scores") or current_six.get("total_score") is None:
        current_six = six_dimension
    current_six["sample_status"] = "sufficient"
    hermes_result["keyword_six_dimension"] = current_six
    hermes_result["selection_decision_points"] = _list_value(hermes_result.get("selection_decision_points")) or decision_points
    market = _dict_value(hermes_result.get("market_research"))
    market.update(
        {
            "keyword": keyword,
            "marketplace": marketplace,
            "research_keywords": research_keywords,
            "source_steps": [*source_steps, {"step": "舒老师分析", "status": "completed", "source": "舒老师", "count": len(all_items)}],
            "route_summary": route_summary,
            "item_count": max(int(_num(market.get("item_count")) or 0), len(all_items)),
            "data_source": "亚马逊搜索页 / 舒老师",
        }
    )
    if not _list_value(market.get("lanes")):
        market["lanes"] = [
            {
                "keyword": row.get("keyword"),
                "source": "亚马逊搜索页",
                "status": "ok",
                "items": _list_value(_dict_value(row.get("analysis")).get("tableRows"))[:20],
                "analysis": row.get("analysis"),
            }
            for row in analyses
        ]
    hermes_result["market_research"] = market
    hermes_result = _strip_internal_ai_meta(hermes_result)
    return _build_hermes_keyword_response(keyword, marketplace, hermes_result)


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_local_hermes_keyword_result(raw: dict[str, Any], keyword: str, marketplace: str) -> dict[str, Any]:
    data = _dict_value(raw.get("result")) or raw
    market = _dict_value(data.get("market_research"))
    lanes = _list_value(market.get("lanes"))
    normalized_lanes: list[dict[str, Any]] = []
    item_count = 0
    for lane in lanes:
        lane_dict = _dict_value(lane)
        items = _list_value(lane_dict.get("items"))
        analysis = _dict_value(lane_dict.get("analysis"))
        table_rows = _list_value(analysis.get("tableRows")) or items
        item_count += len(items) or len(table_rows)
        summary = _dict_value(analysis.get("summary"))
        summary.setdefault("totalListings", len(items) or len(table_rows))
        summary.setdefault("top20Count", len([row for row in table_rows if int(_num(_dict_value(row).get("searchRank") or _dict_value(row).get("rank")) or 0) <= 20]))
        analysis["summary"] = summary
        analysis["tableRows"] = table_rows
        normalized_lanes.append({**lane_dict, "items": items, "analysis": analysis})

    if item_count <= 0:
        item_count = int(_num(market.get("item_count")) or 0)

    sample_status = str(data.get("sample_status") or ("sufficient" if item_count > 0 else "insufficient"))
    if item_count <= 0:
        sample_status = "insufficient"

    market.setdefault("keyword", keyword)
    market.setdefault("marketplace", marketplace)
    market["lanes"] = normalized_lanes
    market.setdefault("research_keywords", [{"keyword": keyword, "source": "用户输入"}])
    market.setdefault(
        "source_steps",
        [{"step": "Hermes", "status": "completed" if item_count > 0 else "partial", "source": "浏览器截图", "count": item_count}],
    )
    market.setdefault("route_summary", [])
    market.setdefault("complaint_insights", [])
    market.setdefault("competitor_weaknesses", [])
    market["item_count"] = item_count
    market.setdefault("data_source", "亚马逊搜索页 / 浏览器截图")

    six = _dict_value(data.get("keyword_six_dimension"))
    if sample_status == "insufficient":
        six = {
            "success": False,
            "total_score": None,
            "dimension_scores": {},
            "detail_scores": {},
            "analysis": {},
            "decision": "待补样本",
            "sample_status": "insufficient",
        }
        data["score"] = None
    else:
        six.setdefault("success", True)
        six.setdefault("dimension_scores", {})
        six.setdefault("detail_scores", six.get("dimension_scores") or {})
        six.setdefault("analysis", {})
        six.setdefault("sample_status", "sufficient")
        if data.get("score") is None and isinstance(six.get("total_score"), (int, float)):
            data["score"] = int(six["total_score"])

    data["keyword_six_dimension"] = six
    data["market_research"] = market
    data["selection_decision_points"] = _list_value(data.get("selection_decision_points")) or _list_value(market.get("decision_points"))
    data["sample_status"] = sample_status
    data.setdefault("confidence", "medium" if item_count > 0 else "low")
    data.setdefault("risk_level", "medium" if item_count > 0 else "high")
    for key in ["fact_layer", "semantic_layer", "reasoning_layer", "decision_layer", "validation_suggestions"]:
        data[key] = _list_value(data.get(key))
    data.setdefault("blocked_by", [] if item_count > 0 else ["未获取到真实市场样本"])
    data.setdefault("problems", [])
    data.setdefault("actions", [])
    data.setdefault("evidence_sources", [])
    data.setdefault("validation_hypotheses", [])
    data.setdefault("learning_update", {})
    data.setdefault(
        "next_step",
        {"module": "launch_check" if item_count > 0 else "selection", "path": "/asin-manager", "reason": "待验证" if item_count > 0 else "待补真实样本"},
    )
    return data


def _build_hermes_keyword_response(keyword: str, marketplace: str, hermes_result: dict[str, Any]) -> dict[str, Any]:
    hermes_result = _strip_internal_ai_meta(hermes_result)
    market_research = hermes_result.get("market_research") or {}
    source_steps = market_research.get("source_steps") or []
    research_keywords = market_research.get("research_keywords") or []
    route_summary = market_research.get("route_summary") or []
    decision_points = hermes_result.get("selection_decision_points") or market_research.get("decision_points") or []
    item_count = int(_num(market_research.get("item_count")) or 0)
    return {
        "status": "ok" if item_count > 0 else "partial",
        "keyword": keyword,
        "marketplace": marketplace,
        "result": hermes_result,
        "source_steps": source_steps,
        "research_keywords": research_keywords,
        "route_summary": route_summary,
        "decision_points": decision_points,
        "item_count": item_count,
    }


def _partial_hermes_keyword_response(task: dict[str, Any]) -> dict[str, Any]:
    keyword = str(task.get("keyword") or "")
    marketplace = str(task.get("marketplace") or "US")
    source_steps = _list_value(task.get("source_steps"))
    partial_observations = [str(line) for line in _list_value(task.get("partial_observations")) if str(line).strip()]
    partial_item_count = int(_num(task.get("partial_item_count")) or 0)
    research_keywords = [{"keyword": keyword, "source": "用户输入"}] if keyword else []
    result = {
        "score": None,
        "confidence": "low",
        "risk_level": "待录入",
        "sample_status": "running",
        "fact_layer": partial_observations,
        "semantic_layer": [],
        "reasoning_layer": [],
        "decision_layer": [],
        "validation_suggestions": [],
        "keyword_six_dimension": {
            "success": False,
            "total_score": None,
            "dimension_scores": {},
            "detail_scores": {},
            "analysis": {},
            "decision": "待补样本",
            "sample_status": "running",
        },
        "selection_decision_points": [],
        "market_research": {
            "keyword": keyword,
            "marketplace": marketplace,
            "research_keywords": research_keywords,
            "source_steps": source_steps,
            "lanes": [],
            "route_summary": [],
            "complaint_insights": [],
            "competitor_weaknesses": [],
            "item_count": partial_item_count,
            "data_source": "亚马逊搜索页 / 浏览器截图",
        },
        "blocked_by": [],
        "problems": [],
        "actions": [],
    }
    return {
        "status": "running",
        "keyword": keyword,
        "marketplace": marketplace,
        "result": result,
        "source_steps": source_steps,
        "research_keywords": research_keywords,
        "route_summary": [],
        "decision_points": [],
        "item_count": partial_item_count,
    }


def _event_payload_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in ("result_text", "summary", "result", "text", "args_text"):
        value = payload.get(key)
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, (dict, list)):
            try:
                chunks.append(json.dumps(value, ensure_ascii=False))
            except Exception:
                pass
    return "\n".join(chunks)


def _extract_visible_sample_count(text: str) -> int:
    if not text:
        return 0
    candidates: list[int] = []
    patterns = [
        r"(\d{1,3})\s*(?:个)?(?:商品|产品|结果|样本|ASIN)",
        r"(\d{1,3})\s*(?:products|items|listings|results|ASINs?)",
        r"(?:商品|产品|结果|样本|ASIN)[^\d]{0,12}(\d{1,3})",
        r"(?:products|items|listings|results|ASINs?)[^\d]{0,12}(\d{1,3})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            value = int(match.group(1))
            if 1 <= value <= 200:
                candidates.append(value)
    asin_count = len(set(re.findall(r"\bB0[A-Z0-9]{8}\b", text.upper())))
    if asin_count:
        candidates.append(asin_count)
    return max(candidates, default=0)


def _observation_text_candidates(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        data = None
    if isinstance(data, dict):
        if data.get("file") or data.get("content") or str(data.get("name") or "").startswith("alignx-"):
            return []
        values: list[str] = []
        analysis = data.get("analysis")
        if isinstance(analysis, str):
            values.append(analysis)
        result = data.get("result")
        if isinstance(result, list):
            for row in result[:8]:
                if isinstance(row, dict) and row.get("text"):
                    values.append(str(row["text"]))
                elif isinstance(row, str):
                    values.append(row)
        snapshot = data.get("snapshot")
        if isinstance(snapshot, str):
            values.append(snapshot)
        return values
    return [raw]


def _extract_visible_observations(text: str) -> list[str]:
    if not text:
        return []
    rows: list[str] = []
    markers = [
        "$",
        "review",
        "rating",
        "star",
        "sponsored",
        "best seller",
        "amazon's choice",
        "评论",
        "评分",
        "赞助",
        "价格",
        "商品",
        "产品",
        "样本",
        "第",
    ]
    for candidate in _observation_text_candidates(text):
        for raw_line in re.split(r"[\r\n]+", candidate):
            line = re.sub(r"\s+", " ", raw_line).strip(" -•|")
            if len(line) < 8:
                continue
            lower = line.lower()
            if not any(marker in lower for marker in markers):
                continue
            if "model=" in lower or "provider=" in lower or "api" in lower or "success" in lower:
                continue
            if len(line) > 180:
                line = line[:177].rstrip() + "..."
            rows.append(line)
            if len(rows) >= 6:
                return rows
    return rows


def _hermes_event_source_step(event_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    tool_name = str(payload.get("name") or payload.get("tool_name") or payload.get("tool") or "")
    text = str(payload.get("text") or payload.get("summary") or payload.get("context") or "")
    status = "completed" if event_type == "tool.complete" else "running"
    if event_type == "session.created":
        return {"step": "会话创建", "status": "completed", "source": "舒老师"}
    if event_type == "status.update":
        return {"step": text[:80] or "分析中", "status": "running", "source": "舒老师"}
    if event_type not in {"tool.start", "tool.complete"}:
        return None
    lowered = tool_name.lower()
    if "browser_navigate" in lowered or "navigate" in lowered:
        step = "打开亚马逊搜索页"
        source = "亚马逊搜索页"
    elif "browser_vision" in lowered or "vision" in lowered:
        step = "视觉读取页面"
        source = "浏览器截图"
    elif "browser_snapshot" in lowered or "screenshot" in lowered or "snapshot" in lowered:
        step = "读取页面截图"
        source = "浏览器截图"
    elif "browser_scroll" in lowered or "scroll" in lowered:
        step = "读取更多样本"
        source = "亚马逊搜索页"
    elif "browser_click" in lowered or "click" in lowered:
        step = "打开样本页面"
        source = "亚马逊搜索页"
    elif "browser" in lowered:
        step = "读取亚马逊页面"
        source = "亚马逊搜索页"
    else:
        step = "分析市场样本"
        source = "舒老师"
    result_text = _event_payload_text(payload)
    sample_count = _extract_visible_sample_count(result_text)
    step_payload: dict[str, Any] = {"step": step, "status": status, "source": source}
    if sample_count > 0:
        step_payload["count"] = sample_count
    return step_payload


def _record_hermes_task_event(task: dict[str, Any], event_type: str, payload: dict[str, Any]) -> None:
    step = _hermes_event_source_step(event_type, payload)
    if event_type == "tool.complete":
        result_text = _event_payload_text(payload)
        sample_count = _extract_visible_sample_count(result_text)
        if sample_count:
            task["partial_item_count"] = max(int(_num(task.get("partial_item_count")) or 0), sample_count)
        observations = _extract_visible_observations(result_text)
        if observations:
            current_observations = [str(line) for line in _list_value(task.get("partial_observations"))]
            for observation in observations:
                if observation not in current_observations:
                    current_observations.append(observation)
            task["partial_observations"] = current_observations[-12:]
    current_progress = float(task.get("progress_percent") or 0)
    if event_type == "session.created":
        next_progress = max(current_progress, 10)
    elif event_type == "status.update":
        next_progress = max(current_progress, 14)
    elif event_type == "tool.start":
        next_progress = min(88, max(current_progress + 4, 22))
    elif event_type == "tool.complete":
        next_progress = min(92, max(current_progress + 8, 30))
    elif event_type in {"thinking.delta", "reasoning.delta", "reasoning.available"}:
        next_progress = min(90, max(current_progress, 60))
    else:
        next_progress = current_progress

    if step:
        source_steps = task.setdefault("source_steps", [])
        if isinstance(source_steps, list):
            if source_steps and source_steps[-1].get("step") == step.get("step"):
                source_steps[-1].update({k: v for k, v in step.items() if v not in (None, "")})
            else:
                source_steps.append(step)
                del source_steps[:-12]

    task.update(
        {
            "progress_percent": next_progress,
            "result_payload": _partial_hermes_keyword_response(task),
            "updated_at": _now_iso(),
        }
    )


def _hermes_tool_name(payload: dict[str, Any]) -> str:
    return str(payload.get("name") or payload.get("tool_name") or payload.get("tool") or "").strip()


def _enforce_hermes_keyword_tool_boundary(event_type: str, payload: dict[str, Any]) -> None:
    if event_type != "tool.start":
        return
    tool_name = _hermes_tool_name(payload)
    lowered = tool_name.lower()
    if not lowered:
        return
    if lowered in _HERMES_KEYWORD_FORBIDDEN_TOOLS or any(forbidden in lowered for forbidden in _HERMES_KEYWORD_FORBIDDEN_TOOLS):
        raise LocalHermesError(f"任务边界越界：{tool_name}")
    if lowered.startswith("browser_") and lowered not in _HERMES_KEYWORD_ALLOWED_TOOLS:
        raise LocalHermesError(f"任务边界越界：{tool_name}")


async def _execute_hermes_keyword_research(
    keyword: str,
    marketplace: str,
    max_keywords: int,
    on_event: Any = None,
) -> dict[str, Any]:
    return await _execute_direct_hermes_keyword_research(keyword, marketplace, max_keywords, on_event=on_event)


async def _execute_direct_hermes_keyword_research(
    keyword: str,
    marketplace: str,
    max_keywords: int,
    on_event: Any = None,
) -> dict[str, Any]:
    prompt = _build_local_hermes_keyword_prompt(keyword, marketplace, max_keywords)
    raw_result = await LocalHermesClient().run_json(
        prompt,
        title=f"AlignX 舒老师关键词选品 {keyword} {datetime.now().strftime('%Y%m%d%H%M%S')}",
        cwd=os.getcwd(),
        on_event=on_event,
    )
    hermes_result = _normalize_local_hermes_keyword_result(raw_result, keyword, marketplace)
    return _build_hermes_keyword_response(keyword, marketplace, hermes_result)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cleanup_hermes_keyword_tasks() -> None:
    now = datetime.now(timezone.utc)
    expired: list[str] = []
    for task_id, task in _HERMES_KEYWORD_RESEARCH_TASKS.items():
        created_at = task.get("created_at")
        try:
            created = datetime.fromisoformat(str(created_at))
        except Exception:
            continue
        if (now - created).total_seconds() > 7200:
            expired.append(task_id)
    for task_id in expired:
        _HERMES_KEYWORD_RESEARCH_TASKS.pop(task_id, None)


def _public_hermes_keyword_task(task_id: str) -> dict[str, Any]:
    task = _HERMES_KEYWORD_RESEARCH_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": task_id,
        "task_type": "hermes_keyword_research",
        "status": task.get("status") or "pending",
        "progress_percent": float(task.get("progress_percent") or 0),
        "keyword": task.get("keyword") or "",
        "marketplace": task.get("marketplace") or "US",
        "result_payload": task.get("result_payload") if isinstance(task.get("result_payload"), dict) else None,
        "error_message": task.get("error_message") or "",
        "created_at": task.get("created_at"),
        "started_at": task.get("started_at"),
        "completed_at": task.get("completed_at"),
        "updated_at": task.get("updated_at"),
    }


def _has_hermes_browser_evidence(task: dict[str, Any]) -> bool:
    for step in _list_value(task.get("source_steps")):
        if not isinstance(step, dict):
            continue
        source = str(step.get("source") or "")
        name = str(step.get("step") or "")
        if source in {"亚马逊搜索页", "浏览器截图"}:
            return True
        if any(token in name for token in ["打开亚马逊", "读取页面", "视觉读取", "读取更多样本"]):
            return True
    return False


async def _run_hermes_keyword_research_task(task_id: str, keyword: str, marketplace: str, max_keywords: int) -> None:
    global _HERMES_KEYWORD_RESEARCH_ACTIVE_TASK_ID
    task = _HERMES_KEYWORD_RESEARCH_TASKS.get(task_id)
    if not task:
        return
    task.update(
        {
            "status": "running",
            "progress_percent": 8,
            "source_steps": [{"step": "任务创建", "status": "completed", "source": "舒老师"}],
            "started_at": _now_iso(),
            "updated_at": _now_iso(),
        }
    )
    task["result_payload"] = _partial_hermes_keyword_response(task)

    async def on_hermes_event(event_type: str, payload: dict[str, Any]) -> None:
        _enforce_hermes_keyword_tool_boundary(event_type, payload)
        _record_hermes_task_event(task, event_type, payload)

    try:
        async with _HERMES_KEYWORD_RESEARCH_LOCK:
            task.update({"progress_percent": 18, "updated_at": _now_iso()})
            task["result_payload"] = _partial_hermes_keyword_response(task)
            result = await _execute_hermes_keyword_research(keyword, marketplace, max_keywords, on_event=on_hermes_event)
            if not _has_hermes_browser_evidence(task):
                raise LocalHermesError("Hermes未调用Browserbase/browser工具")
        task.update(
            {
                "status": "completed",
                "progress_percent": 100,
                "result_payload": result,
                "completed_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        )
    except LocalHermesError as exc:
        logger.warning("Local Hermes keyword research task failed for %s: %s", keyword, exc)
        task.update({"status": "failed", "progress_percent": 100, "error_message": f"舒老师分析失败：{exc}", "completed_at": _now_iso(), "updated_at": _now_iso()})
    except asyncio.TimeoutError:
        logger.warning("Local Hermes keyword research task timed out for %s", keyword)
        task.update({"status": "failed", "progress_percent": 100, "error_message": "舒老师分析超时", "completed_at": _now_iso(), "updated_at": _now_iso()})
    except Exception as exc:
        logger.exception("Local Hermes keyword research task crashed for %s", keyword)
        task.update({"status": "failed", "progress_percent": 100, "error_message": str(exc), "completed_at": _now_iso(), "updated_at": _now_iso()})
    finally:
        if _HERMES_KEYWORD_RESEARCH_ACTIVE_TASK_ID == task_id:
            _HERMES_KEYWORD_RESEARCH_ACTIVE_TASK_ID = None


@router.post("/hermes-keyword-research")
async def hermes_keyword_research(
    request: HermesKeywordResearchRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    keyword = request.keyword.strip()
    marketplace = (request.marketplace or "US").upper()
    if _HERMES_KEYWORD_RESEARCH_LOCK.locked():
        raise HTTPException(status_code=409, detail="舒老师正在分析，请等待本次完成")
    try:
        async with _HERMES_KEYWORD_RESEARCH_LOCK:
            return await _execute_hermes_keyword_research(keyword, marketplace, request.max_keywords)
    except LocalHermesError as exc:
        logger.warning("Local Hermes keyword research failed for %s: %s", keyword, exc)
        raise HTTPException(status_code=502, detail=f"舒老师分析失败：{exc}") from exc
    except asyncio.TimeoutError as exc:
        logger.warning("Local Hermes keyword research timed out for %s", keyword)
        raise HTTPException(status_code=504, detail="舒老师分析超时") from exc


@router.post("/hermes-keyword-research/tasks")
async def create_hermes_keyword_research_task(
    request: HermesKeywordResearchRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
):
    global _HERMES_KEYWORD_RESEARCH_ACTIVE_TASK_ID
    keyword = request.keyword.strip()
    marketplace = (request.marketplace or "US").upper()
    _cleanup_hermes_keyword_tasks()
    async with _HERMES_KEYWORD_TASK_CREATE_LOCK:
        active_id = _HERMES_KEYWORD_RESEARCH_ACTIVE_TASK_ID
        active_task = _HERMES_KEYWORD_RESEARCH_TASKS.get(active_id or "")
        if active_task and active_task.get("status") in {"pending", "running"}:
            raise HTTPException(status_code=409, detail="舒老师正在分析，请等待本次完成")
        if _HERMES_KEYWORD_RESEARCH_LOCK.locked():
            raise HTTPException(status_code=409, detail="舒老师正在分析，请等待本次完成")
        task_id = f"hkw_{uuid4().hex}"
        _HERMES_KEYWORD_RESEARCH_ACTIVE_TASK_ID = task_id
        _HERMES_KEYWORD_RESEARCH_TASKS[task_id] = {
            "status": "pending",
            "progress_percent": 0,
            "keyword": keyword,
            "marketplace": marketplace,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
    background_tasks.add_task(_run_hermes_keyword_research_task, task_id, keyword, marketplace, request.max_keywords)
    return _public_hermes_keyword_task(task_id)


@router.get("/hermes-keyword-research/tasks/{task_id}")
async def get_hermes_keyword_research_task(
    task_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    return _public_hermes_keyword_task(task_id)


@router.get("/{asin}/keyword-sales-history")
async def keyword_sales_history(
    asin: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asin = asin.strip().upper()
    scope_user_ids = await get_user_scope_ids(current_user, db)
    result = await db.execute(
        select(AsinKeywordSalesValidationReport)
        .where(AsinKeywordSalesValidationReport.user_id.in_(scope_user_ids), AsinKeywordSalesValidationReport.asin == asin)
        .order_by(AsinKeywordSalesValidationReport.created_at.desc())
        .limit(30)
    )
    items = []
    for row in result.scalars().all():
        try:
            payload = json.loads(row.report_payload or "{}")
        except Exception:
            payload = {}
        payload = _normalize_keyword_sales_report(payload)
        items.append({
            "id": row.id,
            "asin": row.asin,
            "marketplace": row.marketplace,
            "keyword_sales_score": row.keyword_sales_score,
            "traffic_quality_level": row.traffic_quality_level,
            "sales_source_judgment": row.sales_source_judgment,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "report": payload,
        })
    return {"asin": asin, "items": items}
