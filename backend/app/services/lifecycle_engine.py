from __future__ import annotations
"""Lifecycle detection engine — 4-stage auto-classification + ad strategy.

新品期 → 成长期 → 成熟期 → 衰退期
Each stage transition is triggered by data rules.
"""

import json
import re
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import ConversionDiagnosis, ExecutionRecord, AsinOperationProfile, ValidationResult
from app.services.access import TenantScope, require_user_id, user_scoped

STAGES = ["new_product", "growth", "maturity", "decline"]

STAGE_LABELS: dict[str, str] = {
    "new_product": "新品期",
    "growth": "成长期",
    "maturity": "成熟期",
    "decline": "衰退期",
}

# ── Per-stage ad strategy ──────────────────────────────

AD_STRATEGY: dict[str, dict] = {
    "new_product": {
        "budget": "未设置",
        "acos_target": "未设置",
        "keyword_strategy": "未设置",
        "bid_strategy": "未设置",
        "focus": "待录入",
    },
    "growth": {
        "budget": "未设置",
        "acos_target": "未设置",
        "keyword_strategy": "未设置",
        "bid_strategy": "未设置",
        "focus": "待录入",
    },
    "maturity": {
        "budget": "未设置",
        "acos_target": "未设置",
        "keyword_strategy": "未设置",
        "bid_strategy": "未设置",
        "focus": "待录入",
    },
    "decline": {
        "budget": "未设置",
        "acos_target": "未设置",
        "keyword_strategy": "未设置",
        "bid_strategy": "未设置",
        "focus": "待录入",
    },
}

STOPWORDS = {
    "about", "after", "against", "amazon", "and", "are", "best", "but", "can", "for", "from", "has",
    "have", "into", "not", "of", "on", "or", "our", "the", "this", "to", "use", "with", "your",
    "that", "will", "without", "product", "products", "feature", "features", "make", "makes",
}


def _parse_evidence_metrics(evidence_note: str | None) -> dict | None:
    """Extract ad metrics from evidence_note JSON."""
    if not evidence_note:
        return None
    try:
        data = json.loads(evidence_note)
        if isinstance(data, dict) and data.get("type") == "ad_metrics":
            return data
    except Exception:
        pass
    return None


async def _get_ad_data(asin: str, db: AsyncSession, user_id: str) -> list[dict]:
    """Pull execution records with ad metrics for an ASIN, sorted by date."""
    q = user_scoped(select(ExecutionRecord), ExecutionRecord, user_id)
    q = q.where(
        ExecutionRecord.asin == asin,
        ExecutionRecord.cost_type == "ad_spend",
    ).order_by(ExecutionRecord.executed_at)
    rows = (await db.execute(q)).scalars().all()

    records = []
    for r in rows:
        metrics = _parse_evidence_metrics(r.evidence_note)
        if not metrics:
            continue
        records.append({
            "date": r.executed_at,
            "impressions": int(float(metrics.get("impressions", 0))),
            "clicks": int(float(metrics.get("clicks", 0))),
            "orders": int(float(metrics.get("orders", 0))),
            "sales": float(metrics.get("sales", 0)),
            "spend": r.cost_amount or 0,
        })
    return records


def _weekly_aggregate(records: list[dict]) -> list[dict]:
    """Group daily records into weekly buckets. Returns ordered list."""
    weeks: dict[str, dict] = defaultdict(lambda: {"orders": 0, "impressions": 0, "clicks": 0, "spend": 0, "sales": 0.0})
    for r in records:
        d = r["date"]
        if isinstance(d, datetime):
            iso = d.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
        else:
            key = str(d)[:10]  # fallback
        weeks[key]["orders"] += r["orders"]
        weeks[key]["impressions"] += r["impressions"]
        weeks[key]["clicks"] += r["clicks"]
        weeks[key]["spend"] += r["spend"]
        weeks[key]["sales"] += r["sales"]

    return [{"week": k, **v} for k, v in sorted(weeks.items())]


def _growth_rate(values: list[float]) -> float | None:
    """Average week-over-week growth rate over the last N values."""
    if len(values) < 2:
        return None
    rates = []
    for i in range(1, len(values)):
        if values[i - 1] > 0:
            rates.append((values[i] - values[i - 1]) / values[i - 1])
    return sum(rates) / len(rates) if rates else 0.0


def _flatten_text(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        parts = []
        for item in value:
            parts.extend(_flatten_text(item))
        return parts
    if isinstance(value, dict):
        parts = []
        for item in value.values():
            parts.extend(_flatten_text(item))
        return parts
    return [str(value)]


def _keyword_candidates(texts: list[str], limit: int = 24) -> list[str]:
    counts: dict[str, int] = {}
    for text in texts:
        words = [
            w.lower()
            for w in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", text or "")
            if w.lower() not in STOPWORDS
        ]
        for size in (4, 3, 2):
            for i in range(0, max(0, len(words) - size + 1)):
                phrase = " ".join(words[i:i + size])
                counts[phrase] = counts.get(phrase, 0) + 1
        if len(words) < 8:
            for word in words:
                counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
    result: list[str] = []
    seen = set()
    for phrase, _ in ranked:
        if phrase in seen:
            continue
        if any(phrase != existing and phrase in existing for existing in result):
            continue
        result.append(phrase)
        seen.add(phrase)
        if len(result) >= limit:
            break
    return result


async def _get_keyword_groups(asin: str, marketplace: str, db: AsyncSession, user_id: str) -> list[dict]:
    snapshot, _ = await TenantScope.require(db, user_id).latest_listing_snapshot(asin, marketplace)

    diagnosis_q = user_scoped(select(ConversionDiagnosis), ConversionDiagnosis, user_id)
    diagnosis_q = (
        diagnosis_q.where(
            ConversionDiagnosis.asin == asin,
            ConversionDiagnosis.marketplace == marketplace,
        )
        .order_by(desc(ConversionDiagnosis.created_at))
        .limit(1)
    )
    diagnosis = (await db.execute(diagnosis_q)).scalar_one_or_none()

    listing_texts: list[str] = []
    if snapshot:
        listing_texts.extend(_flatten_text(snapshot.title))
        listing_texts.extend(_flatten_text(snapshot.bullet_points))
        listing_texts.extend(_flatten_text(snapshot.product_details))

    diagnosis_texts: list[str] = []
    if diagnosis:
        diagnosis_texts.extend(_flatten_text(diagnosis.biggest_breakpoint))
        diagnosis_texts.extend(_flatten_text(diagnosis.priority_position))
        diagnosis_texts.extend(_flatten_text(diagnosis.priority_action))
        diagnosis_texts.extend(_flatten_text(diagnosis.position_diagnoses_json))

    listing_keywords = _keyword_candidates(listing_texts, limit=40)
    diagnosis_keywords = _keyword_candidates(diagnosis_texts, limit=40)
    merged_keywords = _keyword_candidates(listing_texts + diagnosis_texts, limit=64)

    return [
        {
            "group_name": "Listing关键词",
            "source_type": "listing_snapshot",
            "source_record_id": snapshot.id if snapshot else None,
            "keywords": listing_keywords,
        },
        {
            "group_name": "承接转化关键词",
            "source_type": "conversion_diagnosis",
            "source_record_id": diagnosis.id if diagnosis else None,
            "keywords": diagnosis_keywords,
        },
        {
            "group_name": "测试投放关键词",
            "source_type": "listing_snapshot+conversion_diagnosis",
            "source_record_id": diagnosis.id if diagnosis else (snapshot.id if snapshot else None),
            "keywords": merged_keywords,
        },
    ]


async def detect_lifecycle(asin: str, db: AsyncSession, profile: AsinOperationProfile | None = None, user_id: str | None = None) -> dict:
    """Detect current lifecycle stage for an ASIN and return stage + strategy + alerts.

    Returns:
        {
            "asin": str,
            "current_stage": "new_product" | "growth" | "maturity" | "decline",
            "stage_label": "新品期",
            "days_active": int,
            "should_transition": True | False,
            "transition_alert": str | None,
            "ad_strategy": {...},              # per-stage ad strategy
            "metrics": {...},                  # key detection metrics
        }
    """
    uid = require_user_id(user_id)

    if not profile:
        q = user_scoped(select(AsinOperationProfile), AsinOperationProfile, uid)
        q = q.where(AsinOperationProfile.asin == asin, AsinOperationProfile.marketplace == "amazon.com")
        profile = (await db.execute(q)).scalar_one_or_none()

    records = await _get_ad_data(asin, db, user_id=uid)
    weeks = _weekly_aggregate(records)
    order_values = [w["orders"] for w in weeks]
    total_orders = sum(order_values)
    total_spend = sum(w["spend"] for w in weeks)

    # First activity date
    first_date = records[0]["date"] if records else None
    days_active = (datetime.utcnow() - first_date).days if first_date else 0

    # Validation effective count
    effective_count = profile.effective_count if profile else 0

    # Determine stage
    current = profile.lifecycle_stage if profile else None
    if current not in STAGES:
        current = None

    detected, alert = _classify(
        current_stage=current,
        days_active=days_active,
        total_orders=total_orders,
        order_values=order_values,
        weeks=weeks,
        effective_count=effective_count,
        total_spend=total_spend,
    )

    # Growth metrics
    recent_orders = order_values[-4:] if len(order_values) >= 4 else order_values
    recent_growth = _growth_rate(recent_orders) if len(recent_orders) >= 2 else None

    # ACoS
    total_sales = sum(w["sales"] for w in weeks)
    acos = (total_spend / total_sales * 100) if total_sales > 0 else None

    # Impressions trend
    impression_vals = [w["impressions"] for w in weeks[-4:]] if len(weeks) >= 4 else []
    impression_trend = _growth_rate(impression_vals) if len(impression_vals) >= 2 else None
    keyword_groups = await _get_keyword_groups(asin, "amazon.com", db, uid)

    return {
        "asin": asin,
        "current_stage": detected,
        "stage_label": STAGE_LABELS.get(detected, detected),
        "days_active": days_active,
        "should_transition": detected != current if current else True,
        "transition_alert": alert,
        "ad_strategy": AD_STRATEGY.get(detected, {}),
        "keyword_groups": keyword_groups,
        "metrics": {
            "total_orders": total_orders,
            "total_spend": round(total_spend, 2),
            "total_sales": round(total_sales, 2),
            "acos": round(acos, 1) if acos is not None else None,
            "weeks_active": len(weeks),
            "recent_weekly_orders": recent_orders,
            "weekly_order_growth_pct": round(recent_growth * 100, 1) if recent_growth is not None else None,
            "impression_trend_pct": round(impression_trend * 100, 1) if impression_trend is not None else None,
            "effective_validations": effective_count,
        },
    }


def _classify(
    current_stage: str | None,
    days_active: int,
    total_orders: int,
    order_values: list[int],
    weeks: list[dict],
    effective_count: int,
    total_spend: float,
) -> tuple[str, str | None]:
    """Classify into one of 4 stages. Returns (stage, transition_alert)."""

    # Helper: weekly growth over last N weeks
    def growth(n: int) -> float | None:
        vals = order_values[-n:] if len(order_values) >= n else order_values
        return _growth_rate(vals) if len(vals) >= 2 else None

    # ── No data → 新品期 ──
    if days_active == 0:
        return "new_product", None

    # ── 新品期 ──
    if not current_stage or current_stage == "new_product":
        # Stay in 新品期 if < 60 days or very few orders
        if days_active < 60 and total_orders < 20:
            return "new_product", None

        # Transition to 成长期:
        # (a) 60+ days AND (week growth > 10% for 4 weeks OR 2+ effective validations)
        # (b) OR total_orders >= 50 with positive growth
        g4 = growth(4)
        transitioning = (
            (days_active >= 60 and ((g4 is not None and g4 > 0.10) or effective_count >= 2))
            or (total_orders >= 50 and g4 is not None and g4 > 0)
        )
        if transitioning:
            alert = "阶段切换：成长期"
            return "growth", alert
        return "new_product", None

    # ── 成长期 ──
    if current_stage == "growth":
        g4 = growth(4)
        # Transition to 成熟期:
        # (a) Growth flattened (< 5% for 4 weeks) AND total orders > 100
        # (b) OR days_active > 365
        # (c) OR effective_count >= 5 (lots of validated optimizations)
        flattening = g4 is not None and g4 < 0.05 and total_orders > 100
        if flattening or days_active > 365 or effective_count >= 5:
            alert = "阶段切换：成熟期"
            return "maturity", alert

        # Downgrade to 新品期 if growth negative and low orders
        if g4 is not None and g4 < -0.10 and total_orders < 30:
            alert = "阶段切换：新品期"
            return "new_product", alert

        return "growth", None

    # ── 成熟期 ──
    if current_stage == "maturity":
        g8 = growth(8)
        # Transition to 衰退期:
        # (a) Orders declining > 10% for 8+ weeks
        # (b) OR days_active > 730 (2 years) with negative growth
        declining = g8 is not None and g8 < -0.10 and len(order_values) >= 8
        aging = days_active > 730 and g8 is not None and g8 < 0
        if declining or aging:
            alert = "阶段切换：衰退期"
            return "decline", alert
        return "maturity", None

    # ── 衰退期 ──
    if current_stage == "decline":
        g4 = growth(4)
        # Recovery: back to maturity if growing again for 4+ weeks
        recovering = g4 is not None and g4 > 0.10
        if recovering:
            alert = "阶段切换：成熟期"
            return "maturity", alert
        return "decline", None

    # Fallback
    return current_stage or "new_product", None


async def apply_lifecycle(asin: str, db: AsyncSession, user_id: str | None = None) -> dict:
    """Detect lifecycle, persist to profile, return result."""
    uid = require_user_id(user_id)
    result = await detect_lifecycle(asin, db, user_id=uid)

    # Persist
    q = user_scoped(select(AsinOperationProfile), AsinOperationProfile, uid)
    q = q.where(AsinOperationProfile.asin == asin, AsinOperationProfile.marketplace == "amazon.com")
    profile = (await db.execute(q)).scalar_one_or_none()
    if profile and result["current_stage"] != profile.lifecycle_stage:
        profile.lifecycle_stage = result["current_stage"]
        await db.flush()

    return result
