import json
import logging
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
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
from schemas.opc_os import OpportunityInput
from services.amazon_scraper import scrape_amazon_product
from services.amazon_skill_toolbox import build_asin_selection_assist
from services.cosmo_operator_agent import CosmoOperatorAgent
from services.opc_os_persistence import OPCOSPersistenceService
from services.opc_os_v5 import OPCOSV5ExecutionService
from services.scrapling_amazon_capture import SCRAPLING_TOP40_RULES, capture_top40_batch
from services.top40_market_analysis import analyze_top40_market

router = APIRouter(prefix="/api/v1/asin-selection", tags=["asin-selection"])
logger = logging.getLogger(__name__)


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
    patterns = [
        (r"\bcat\b|\blitter\b|\bodor\b", ["cat litter odor control", "cat litter deodorizer", "litter box odor eliminator"]),
        (r"\bbluetooth\b|\bspeaker\b", ["bluetooth speaker", "portable bluetooth speaker", "waterproof speaker"]),
        (r"\bpower bank\b|\bcharger\b|\bbattery\b", ["portable charger", "power bank", "usb c power bank"]),
        (r"\bunderwear\b|\bboxer\b|\bbamboo\b", ["bamboo boxer briefs", "men boxer briefs", "breathable underwear"]),
    ]
    for pattern, kws in patterns:
        if re.search(pattern, text):
            candidates.extend(kws)
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
    report.setdefault("decision_standard", CosmoOperatorAgent.public_standard_meta("asin_selection"))

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
    try:
        opc_result = OPCOSV5ExecutionService(user_id).run_execution_loop(
            OpportunityInput(
                title=product.get("title") or asin,
                human_drivers=["待录入"],
                demand=", ".join(keywords) if keywords else "待录入",
                scenario=product.get("category") or "待录入",
                initial_score=float(report.get("keyword_sales_score") or 0),
            )
        )
        opc_payload = opc_result.model_dump(mode="json")
        await OPCOSPersistenceService(db).save_execution_bundle(
            user_id=user_id,
            bundle=opc_payload,
            source_module="asin_selection",
            asin=asin,
            title=product.get("title") or asin,
        )
        report["opc_v5_execution"] = opc_payload
    except Exception as exc:
        logger.warning("asin_selection opc_v5 persist failed for %s: %s", asin, exc)
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
