import json
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user, get_user_scope_ids
from models.ad_data import Ad_data
from models.ad_validation_results import AdValidationResult
from models.asin_keyword_sales_validation import AsinKeywordRankSnapshot
from models.execution_records import ExecutionRecord
from models.products import Products
from models.sales_metrics import Sales_metrics
from schemas.auth import UserResponse

router = APIRouter(prefix="/api/v1/yesterday-report", tags=["yesterday_report"])

UNKNOWN = "数据不足，不能判断"
EMPTY = "暂无"


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _pct(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator * 100, 2)


def _fmt_money(value: float | None) -> str:
    if value is None:
        return UNKNOWN
    return f"{value:.2f}美元"


def _fmt_number(value: float | int | None) -> str:
    if value is None:
        return UNKNOWN
    if isinstance(value, float) and not value.is_integer():
        return f"{value:.2f}"
    return str(int(value))


def _fmt_percent(value: float | None) -> str:
    if value is None:
        return UNKNOWN
    return f"{value:.2f}%"


def _day(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _created_on(row: Any) -> date | None:
    return _day(getattr(row, "created_at", None)) or _day(getattr(row, "updated_at", None))


def _created_or_executed_on(row: ExecutionRecord) -> date | None:
    if row.execution_time:
        try:
            return datetime.fromisoformat(row.execution_time.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    return _created_on(row)


def _empty_day_metrics() -> dict[str, Any]:
    return {
        "revenue": 0.0,
        "orders": 0,
        "sessions": 0,
        "profit_weighted": 0.0,
        "profit_base": 0.0,
        "sales_rows": 0,
        "impressions": 0,
        "clicks": 0,
        "ad_spend": 0.0,
        "ad_orders": 0,
        "ad_sales": 0.0,
        "ad_rows": 0,
    }


def _finalize_metrics(raw: dict[str, Any]) -> dict[str, Any]:
    revenue = raw["revenue"]
    orders = raw["orders"]
    sessions = raw["sessions"]
    ad_spend = raw["ad_spend"]
    ad_sales = raw["ad_sales"]
    impressions = raw["impressions"]
    clicks = raw["clicks"]
    ad_orders = raw["ad_orders"]
    profit_margin = None
    if raw["profit_base"] > 0:
        profit_margin = round(raw["profit_weighted"] / raw["profit_base"], 2)
    organic_sales = revenue - ad_sales if revenue or ad_sales else None
    if organic_sales is not None and organic_sales < 0:
        organic_sales = 0.0

    return {
        **raw,
        "ctr": _pct(clicks, impressions),
        "cvr": _pct(orders if orders else ad_orders, clicks),
        "acos": _pct(ad_spend, ad_sales),
        "tacos": _pct(ad_spend, revenue),
        "organic_sales": round(organic_sales, 2) if organic_sales is not None else None,
        "organic_share": _pct(organic_sales or 0, revenue) if organic_sales is not None else None,
        "profit_margin": profit_margin,
        "gross_profit": round(revenue * profit_margin / 100, 2) if profit_margin is not None else None,
        "has_sales": raw["sales_rows"] > 0,
        "has_ads": raw["ad_rows"] > 0,
    }


def _avg_metrics(days: list[dict[str, Any]]) -> dict[str, Any]:
    if not days:
        return _finalize_metrics(_empty_day_metrics())
    total = _empty_day_metrics()
    for item in days:
        for key in total:
            total[key] += item.get(key, 0) or 0
    count = len(days)
    for key in ("revenue", "orders", "sessions", "impressions", "clicks", "ad_spend", "ad_orders", "ad_sales"):
        total[key] = total[key] / count
    return _finalize_metrics(total)


def _change(current: float | None, previous: float | None) -> str:
    if current is None or previous is None:
        return UNKNOWN
    if previous == 0:
        return UNKNOWN
    delta = current - previous
    pct_change = delta / previous * 100
    sign = "+" if delta > 0 else ""
    return f"{sign}{delta:.2f} / {sign}{pct_change:.2f}%"


def _metric_card(label: str, value: str, previous: str = UNKNOWN, seven_day_avg: str = UNKNOWN) -> dict[str, str]:
    return {
        "label": label,
        "value": value,
        "previous_day": previous,
        "seven_day_avg": seven_day_avg,
    }


def _empty_yesterday_report(report_day: date, product_count: int) -> dict[str, Any]:
    return {
        "report_date": report_day.isoformat(),
        "generated_at": datetime.now().isoformat(),
        "data_mode": EMPTY,
        "overview": {
            "result_judgment": UNKNOWN,
            "metrics": [
                _metric_card("销售额", UNKNOWN),
                _metric_card("订单量", UNKNOWN),
                _metric_card("广告花费", UNKNOWN),
                _metric_card("广告销售额", UNKNOWN),
                _metric_card("自然销售额", UNKNOWN),
                _metric_card("ACOS", UNKNOWN),
                _metric_card("TACOS", UNKNOWN),
                _metric_card("CTR", UNKNOWN),
                _metric_card("CVR", UNKNOWN),
                _metric_card("Sessions", UNKNOWN),
                _metric_card("利润/毛利率", UNKNOWN),
                _metric_card("库存可售天数", UNKNOWN),
            ],
        },
        "key_changes": [],
        "cause_judgments": [],
        "validation_actions": [],
        "today_priorities": {
            "A类": [],
            "B类": [],
            "C类": [],
        },
        "risk_warnings": [],
        "final_conclusion": {
            "largest_problem": UNKNOWN,
            "most_important_action": UNKNOWN,
            "product_status": UNKNOWN,
        },
        "data_coverage": {
            "sales_days": 0,
            "ad_days": 0,
            "validation_actions": 0,
            "product_count": product_count,
        },
    }


def _comparison_item(label: str, current: float | None, previous: float | None, avg: float | None, fmt) -> dict[str, str] | None:
    if current is None or previous is None:
        return None
    return {
        "metric": label,
        "yesterday": fmt(current),
        "previous_day": fmt(previous),
        "seven_day_avg": fmt(avg) if avg is not None else UNKNOWN,
        "change": _change(current, previous),
    }


def _result_judgment(yesterday_metrics: dict[str, Any], previous_metrics: dict[str, Any]) -> str:
    if not yesterday_metrics["has_sales"]:
        return UNKNOWN
    revenue = yesterday_metrics["revenue"]
    previous_revenue = previous_metrics["revenue"]
    if previous_metrics["has_sales"] and previous_revenue > 0:
        delta = (revenue - previous_revenue) / previous_revenue * 100
        if delta >= 15:
            return "增长"
        if delta <= -15:
            return "下滑"
        return "稳定"
    return "稳定"


def _cause_judgments(yesterday_metrics: dict[str, Any], previous_metrics: dict[str, Any]) -> list[dict[str, str]]:
    causes: list[dict[str, str]] = []
    if not yesterday_metrics["has_sales"] and not yesterday_metrics["has_ads"]:
        return [{"phenomenon": UNKNOWN, "possible_reason": UNKNOWN, "evidence": UNKNOWN, "confidence": "低"}]

    revenue_down = previous_metrics["revenue"] > 0 and yesterday_metrics["revenue"] < previous_metrics["revenue"] * 0.85
    sessions_down = previous_metrics["sessions"] > 0 and yesterday_metrics["sessions"] < previous_metrics["sessions"] * 0.85
    cvr_down = (
        previous_metrics["cvr"] is not None
        and yesterday_metrics["cvr"] is not None
        and yesterday_metrics["cvr"] < previous_metrics["cvr"] * 0.85
    )
    ad_spend_up = previous_metrics["ad_spend"] > 0 and yesterday_metrics["ad_spend"] > previous_metrics["ad_spend"] * 1.3
    acos_up = (
        previous_metrics["acos"] is not None
        and yesterday_metrics["acos"] is not None
        and yesterday_metrics["acos"] > previous_metrics["acos"] * 1.2
    )

    if revenue_down and sessions_down:
        causes.append({
            "phenomenon": "销售额下降",
            "possible_reason": "流量下降",
            "evidence": f"Sessions：{_fmt_number(previous_metrics['sessions'])} → {_fmt_number(yesterday_metrics['sessions'])}",
            "confidence": "中",
        })
    if revenue_down and cvr_down:
        causes.append({
            "phenomenon": "销售额下降",
            "possible_reason": "转化下降",
            "evidence": f"CVR：{_fmt_percent(previous_metrics['cvr'])} → {_fmt_percent(yesterday_metrics['cvr'])}",
            "confidence": "中",
        })
    if ad_spend_up and acos_up:
        causes.append({
            "phenomenon": "广告花费增加",
            "possible_reason": "广告效率下降",
            "evidence": f"ACOS：{_fmt_percent(previous_metrics['acos'])} → {_fmt_percent(yesterday_metrics['acos'])}",
            "confidence": "中",
        })
    if not causes:
        causes.append({
            "phenomenon": UNKNOWN,
            "possible_reason": UNKNOWN,
            "evidence": UNKNOWN,
            "confidence": "低",
        })
    return causes[:5]


def _risk_warnings(yesterday_metrics: dict[str, Any], previous_metrics: dict[str, Any], rank_change: dict[str, Any] | None) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    if previous_metrics["ad_spend"] > 0 and yesterday_metrics["ad_spend"] > previous_metrics["ad_spend"] * 1.3:
        risks.append({"risk": "广告花费异常增加", "evidence": _change(yesterday_metrics["ad_spend"], previous_metrics["ad_spend"]), "status": "需验证"})
    if previous_metrics["tacos"] is not None and yesterday_metrics["tacos"] is not None and yesterday_metrics["tacos"] > previous_metrics["tacos"] * 1.2:
        risks.append({"risk": "TACOS异常升高", "evidence": _change(yesterday_metrics["tacos"], previous_metrics["tacos"]), "status": "需验证"})
    if previous_metrics["cvr"] is not None and yesterday_metrics["cvr"] is not None and yesterday_metrics["cvr"] < previous_metrics["cvr"] * 0.8:
        risks.append({"risk": "转化率突然下降", "evidence": _change(yesterday_metrics["cvr"], previous_metrics["cvr"]), "status": "需验证"})
    if previous_metrics["sessions"] > 0 and yesterday_metrics["sessions"] < previous_metrics["sessions"] * 0.8:
        risks.append({"risk": "Sessions下降", "evidence": _change(yesterday_metrics["sessions"], previous_metrics["sessions"]), "status": "需验证"})
    if rank_change and rank_change.get("risk"):
        risks.append(rank_change["risk"])
    return risks


def _priority_items(risks: list[dict[str, str]], validation_actions: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    groups = {"A类": [], "B类": [], "C类": []}
    if risks:
        first = risks[0]
        groups["A类"].append({
            "action": "处理风险",
            "target": first.get("risk", UNKNOWN),
            "expected_impact": UNKNOWN,
            "risk_note": first.get("evidence", UNKNOWN),
            "observation_cycle": UNKNOWN,
        })
    if validation_actions:
        first_action = validation_actions[0]
        groups["B类"].append({
            "action": first_action.get("action", UNKNOWN),
            "target": first_action.get("target", UNKNOWN),
            "expected_impact": first_action.get("expected_target", UNKNOWN),
            "risk_note": first_action.get("actual_result", UNKNOWN),
            "observation_cycle": first_action.get("validation_cycle", UNKNOWN),
        })
    if not groups["A类"] and not groups["B类"]:
        groups["C类"].append({
            "action": UNKNOWN,
            "target": UNKNOWN,
            "expected_impact": UNKNOWN,
            "risk_note": UNKNOWN,
            "observation_cycle": UNKNOWN,
        })
    return groups


async def _load_metrics(db: AsyncSession, scope_user_ids: list[str], start_day: date, end_day: date) -> dict[date, dict[str, Any]]:
    metrics: dict[date, dict[str, Any]] = defaultdict(_empty_day_metrics)

    sales_result = await db.execute(
        select(Sales_metrics).where(
            Sales_metrics.user_id.in_(scope_user_ids),
            Sales_metrics.date >= start_day,
            Sales_metrics.date <= end_day,
        )
    )
    for row in sales_result.scalars().all():
        day = row.date
        bucket = metrics[day]
        revenue = _safe_float(row.revenue)
        bucket["revenue"] += revenue
        bucket["orders"] += _safe_int(row.orders)
        bucket["sessions"] += _safe_int(row.sessions)
        if row.profit_margin is not None:
            bucket["profit_weighted"] += revenue * _safe_float(row.profit_margin)
            bucket["profit_base"] += revenue
        bucket["sales_rows"] += 1

    start_dt = datetime.combine(start_day, time.min)
    end_dt = datetime.combine(end_day + timedelta(days=1), time.min)
    ad_result = await db.execute(
        select(Ad_data).where(
            Ad_data.user_id.in_(scope_user_ids),
            Ad_data.date >= start_dt,
            Ad_data.date < end_dt,
        )
    )
    for row in ad_result.scalars().all():
        day = _day(row.date)
        if not day:
            continue
        bucket = metrics[day]
        bucket["impressions"] += _safe_int(row.impressions)
        bucket["clicks"] += _safe_int(row.clicks)
        bucket["ad_spend"] += _safe_float(row.spend)
        bucket["ad_orders"] += _safe_int(row.orders)
        bucket["ad_sales"] += _safe_float(row.sales)
        bucket["ad_rows"] += 1

    return {day: _finalize_metrics(values) for day, values in metrics.items()}


async def _load_keyword_rank_change(db: AsyncSession, scope_user_ids: list[str], yesterday: date, previous_day: date) -> dict[str, Any] | None:
    start_dt = datetime.combine(previous_day, time.min)
    end_dt = datetime.combine(yesterday + timedelta(days=1), time.min)
    result = await db.execute(
        select(AsinKeywordRankSnapshot).where(
            AsinKeywordRankSnapshot.user_id.in_(scope_user_ids),
            AsinKeywordRankSnapshot.crawl_time >= start_dt,
            AsinKeywordRankSnapshot.crawl_time < end_dt,
        )
    )
    snapshots = result.scalars().all()
    if not snapshots:
        return None

    by_day: dict[date, list[AsinKeywordRankSnapshot]] = defaultdict(list)
    for snap in snapshots:
        snap_day = _day(snap.crawl_time)
        if snap_day:
            by_day[snap_day].append(snap)
    if not by_day.get(yesterday) or not by_day.get(previous_day):
        return None

    def average_position(items: list[AsinKeywordRankSnapshot]) -> float | None:
        values = [_safe_int(item.organic_position or item.overall_position) for item in items if item.organic_position or item.overall_position]
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    current = average_position(by_day[yesterday])
    previous = average_position(by_day[previous_day])
    if current is None or previous is None:
        return None

    risk = None
    if current > previous + 5:
        risk = {
            "risk": "核心关键词排名下降",
            "evidence": f"{previous:.2f} → {current:.2f}",
            "status": "需验证",
        }
    return {
        "metric": "关键词排名",
        "yesterday": f"{current:.2f}",
        "previous_day": f"{previous:.2f}",
        "seven_day_avg": UNKNOWN,
        "change": f"{previous - current:+.2f}",
        "risk": risk,
    }


async def _load_validation_actions(db: AsyncSession, scope_user_ids: list[str], report_day: date) -> list[dict[str, str]]:
    executions_result = await db.execute(select(ExecutionRecord).where(ExecutionRecord.user_id.in_(scope_user_ids)))
    validations_result = await db.execute(select(AdValidationResult).where(AdValidationResult.user_id.in_(scope_user_ids)))
    executions = [row for row in executions_result.scalars().all() if _created_or_executed_on(row) == report_day]
    validations = [row for row in validations_result.scalars().all() if _created_on(row) == report_day]
    validation_by_execution = {item.execution_id: item for item in validations if item.execution_id}

    items: list[dict[str, str]] = []
    for record in executions:
        linked = validation_by_execution.get(record.execution_id)
        items.append({
            "action": record.execution_content or record.suggested_action or UNKNOWN,
            "expected_target": record.suggested_action or UNKNOWN,
            "actual_result": linked.conclusion if linked else record.result or UNKNOWN,
            "conclusion": linked.conclusion if linked else record.validation_status or UNKNOWN,
            "next_action": (linked.next_suggestion if linked else record.suggested_action) or UNKNOWN,
            "target": record.execution_target or UNKNOWN,
            "executor": record.executor or UNKNOWN,
            "validation_cycle": (linked.validation_period if linked else record.validation_cycle) or UNKNOWN,
            "execution_id": record.execution_id,
        })

    for validation in validations:
        if validation.execution_id in validation_by_execution and any(item["execution_id"] == validation.execution_id for item in items):
            continue
        items.append({
            "action": validation.execution_action or UNKNOWN,
            "expected_target": validation.original_hypothesis or UNKNOWN,
            "actual_result": validation.conclusion or UNKNOWN,
            "conclusion": validation.conclusion or UNKNOWN,
            "next_action": validation.next_suggestion or UNKNOWN,
            "target": validation.asin or UNKNOWN,
            "executor": UNKNOWN,
            "validation_cycle": validation.validation_period or UNKNOWN,
            "execution_id": validation.execution_id or validation.verification_id,
        })
    return items


async def _load_product_count(db: AsyncSession, scope_user_ids: list[str]) -> int:
    result = await db.execute(select(Products.id).where(Products.user_id.in_(scope_user_ids)))
    return len(result.scalars().all())


@router.get("")
async def get_yesterday_report(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope_user_ids = await get_user_scope_ids(current_user, db)
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    previous_day = yesterday - timedelta(days=1)
    seven_start = yesterday - timedelta(days=7)

    metrics_by_day = await _load_metrics(db, scope_user_ids, seven_start, yesterday)
    yesterday_metrics = metrics_by_day.get(yesterday, _finalize_metrics(_empty_day_metrics()))
    previous_metrics = metrics_by_day.get(previous_day, _finalize_metrics(_empty_day_metrics()))
    seven_days = [metrics_by_day[seven_start + timedelta(days=i)] for i in range(7) if (seven_start + timedelta(days=i)) in metrics_by_day]
    seven_avg = _avg_metrics(seven_days)
    rank_change = await _load_keyword_rank_change(db, scope_user_ids, yesterday, previous_day)
    validation_actions = await _load_validation_actions(db, scope_user_ids, yesterday)
    risks = _risk_warnings(yesterday_metrics, previous_metrics, rank_change)

    overview_metrics = [
        _metric_card("销售额", _fmt_money(yesterday_metrics["revenue"]) if yesterday_metrics["has_sales"] else UNKNOWN, _fmt_money(previous_metrics["revenue"]) if previous_metrics["has_sales"] else UNKNOWN, _fmt_money(seven_avg["revenue"]) if seven_days else UNKNOWN),
        _metric_card("订单量", _fmt_number(yesterday_metrics["orders"]) if yesterday_metrics["has_sales"] else UNKNOWN, _fmt_number(previous_metrics["orders"]) if previous_metrics["has_sales"] else UNKNOWN, _fmt_number(seven_avg["orders"]) if seven_days else UNKNOWN),
        _metric_card("广告花费", _fmt_money(yesterday_metrics["ad_spend"]) if yesterday_metrics["has_ads"] else UNKNOWN, _fmt_money(previous_metrics["ad_spend"]) if previous_metrics["has_ads"] else UNKNOWN, _fmt_money(seven_avg["ad_spend"]) if seven_days else UNKNOWN),
        _metric_card("广告销售额", _fmt_money(yesterday_metrics["ad_sales"]) if yesterday_metrics["has_ads"] else UNKNOWN, _fmt_money(previous_metrics["ad_sales"]) if previous_metrics["has_ads"] else UNKNOWN, _fmt_money(seven_avg["ad_sales"]) if seven_days else UNKNOWN),
        _metric_card("自然销售额", _fmt_money(yesterday_metrics["organic_sales"]) if yesterday_metrics["organic_sales"] is not None else UNKNOWN, _fmt_money(previous_metrics["organic_sales"]) if previous_metrics["organic_sales"] is not None else UNKNOWN, _fmt_money(seven_avg["organic_sales"]) if seven_days and seven_avg["organic_sales"] is not None else UNKNOWN),
        _metric_card("ACOS", _fmt_percent(yesterday_metrics["acos"]), _fmt_percent(previous_metrics["acos"]), _fmt_percent(seven_avg["acos"]) if seven_days else UNKNOWN),
        _metric_card("TACOS", _fmt_percent(yesterday_metrics["tacos"]), _fmt_percent(previous_metrics["tacos"]), _fmt_percent(seven_avg["tacos"]) if seven_days else UNKNOWN),
        _metric_card("CTR", _fmt_percent(yesterday_metrics["ctr"]), _fmt_percent(previous_metrics["ctr"]), _fmt_percent(seven_avg["ctr"]) if seven_days else UNKNOWN),
        _metric_card("CVR", _fmt_percent(yesterday_metrics["cvr"]), _fmt_percent(previous_metrics["cvr"]), _fmt_percent(seven_avg["cvr"]) if seven_days else UNKNOWN),
        _metric_card("Sessions", _fmt_number(yesterday_metrics["sessions"]) if yesterday_metrics["has_sales"] else UNKNOWN, _fmt_number(previous_metrics["sessions"]) if previous_metrics["has_sales"] else UNKNOWN, _fmt_number(seven_avg["sessions"]) if seven_days else UNKNOWN),
        _metric_card("利润/毛利率", _fmt_percent(yesterday_metrics["profit_margin"]), _fmt_percent(previous_metrics["profit_margin"]), _fmt_percent(seven_avg["profit_margin"]) if seven_days else UNKNOWN),
        _metric_card("库存可售天数", UNKNOWN, UNKNOWN, UNKNOWN),
    ]

    key_changes: list[dict[str, str]] = []
    for item in [
        _comparison_item("销售额变化", yesterday_metrics["revenue"] if yesterday_metrics["has_sales"] else None, previous_metrics["revenue"] if previous_metrics["has_sales"] else None, seven_avg["revenue"] if seven_days else None, _fmt_money),
        _comparison_item("订单量变化", yesterday_metrics["orders"] if yesterday_metrics["has_sales"] else None, previous_metrics["orders"] if previous_metrics["has_sales"] else None, seven_avg["orders"] if seven_days else None, _fmt_number),
        _comparison_item("广告花费变化", yesterday_metrics["ad_spend"] if yesterday_metrics["has_ads"] else None, previous_metrics["ad_spend"] if previous_metrics["has_ads"] else None, seven_avg["ad_spend"] if seven_days else None, _fmt_money),
        _comparison_item("ACOS变化", yesterday_metrics["acos"], previous_metrics["acos"], seven_avg["acos"] if seven_days else None, _fmt_percent),
        _comparison_item("TACOS变化", yesterday_metrics["tacos"], previous_metrics["tacos"], seven_avg["tacos"] if seven_days else None, _fmt_percent),
        _comparison_item("CTR变化", yesterday_metrics["ctr"], previous_metrics["ctr"], seven_avg["ctr"] if seven_days else None, _fmt_percent),
        _comparison_item("CVR变化", yesterday_metrics["cvr"], previous_metrics["cvr"], seven_avg["cvr"] if seven_days else None, _fmt_percent),
        _comparison_item("自然单量占比变化", yesterday_metrics["organic_share"], previous_metrics["organic_share"], seven_avg["organic_share"] if seven_days else None, _fmt_percent),
        rank_change,
    ]:
        if item:
            key_changes.append({k: v for k, v in item.items() if k != "risk"})

    product_status = "稳定验证中"
    if risks:
        risk_name = risks[0]["risk"]
        if "广告" in risk_name or "ACOS" in risk_name or "TACOS" in risk_name:
            product_status = "广告浪费"
        elif "排名" in risk_name:
            product_status = "排名下滑"
        elif "Sessions" in risk_name or "转化" in risk_name:
            product_status = "转化受阻"
    elif _result_judgment(yesterday_metrics, previous_metrics) == "增长":
        product_status = "增长中"

    priorities = _priority_items(risks, validation_actions)
    product_count = await _load_product_count(db, scope_user_ids)
    if _result_judgment(yesterday_metrics, previous_metrics) == UNKNOWN or not key_changes:
        return _empty_yesterday_report(yesterday, product_count)

    return {
        "report_date": yesterday.isoformat(),
        "generated_at": datetime.now().isoformat(),
        "data_mode": "真实数据",
        "overview": {
            "result_judgment": _result_judgment(yesterday_metrics, previous_metrics),
            "metrics": overview_metrics,
        },
        "key_changes": key_changes[:5],
        "cause_judgments": _cause_judgments(yesterday_metrics, previous_metrics),
        "validation_actions": validation_actions,
        "today_priorities": priorities,
        "risk_warnings": risks,
        "final_conclusion": {
            "largest_problem": risks[0]["risk"] if risks else UNKNOWN,
            "most_important_action": priorities["A类"][0]["action"] if priorities["A类"] else UNKNOWN,
            "product_status": product_status,
        },
        "data_coverage": {
            "sales_days": sum(1 for item in metrics_by_day.values() if item["has_sales"]),
            "ad_days": sum(1 for item in metrics_by_day.values() if item["has_ads"]),
            "validation_actions": len(validation_actions),
            "product_count": product_count,
        },
    }
