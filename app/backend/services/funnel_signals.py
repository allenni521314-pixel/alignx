from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ad_data import Ad_data
from models.listings import Listings


async def fetch_funnel_signals(asin: str, user_id: str, db: AsyncSession) -> dict:
    """Pre-diagnosis step: fetch real 30-day funnel data. No AI calls."""
    normalized_asin = str(asin or "").strip().upper()
    if not normalized_asin:
        return {
            "has_real_data": False,
            "sessions_30d": None,
            "conversion_rate": None,
            "ctr": None,
            "cvr": None,
            "acos": None,
            "impressions": None,
        }

    cutoff = datetime.utcnow() - timedelta(days=30)

    listing_result = await db.execute(
        select(Listings).where(
            Listings.asin == normalized_asin,
            Listings.user_id == user_id,
        )
    )
    listing_row = listing_result.scalar_one_or_none()

    ad_result = await db.execute(
        select(
            func.sum(Ad_data.impressions),
            func.sum(Ad_data.clicks),
            func.sum(Ad_data.orders),
            func.sum(Ad_data.spend),
            func.sum(Ad_data.sales),
        ).where(
            Ad_data.user_id == user_id,
            Ad_data.date >= cutoff,
        )
    )
    impressions, clicks, orders, spend, sales = ad_result.first() or (None, None, None, None, None)

    ctr = round(clicks / impressions, 4) if impressions else None
    cvr = round(orders / clicks, 4) if clicks else None
    acos = round(spend / sales, 4) if sales else None

    return {
        "has_real_data": bool(listing_row or impressions),
        "sessions_30d": getattr(listing_row, "sessions_30d", None),
        "conversion_rate": getattr(listing_row, "conversion_rate", None),
        "ctr": ctr,
        "cvr": cvr,
        "acos": acos,
        "impressions": impressions,
    }


def route_diagnosis_focus(funnel: dict) -> str:
    if not funnel["has_real_data"]:
        return "no_data_text_only"
    if funnel.get("ctr") is not None and funnel["ctr"] < 0.003:
        return "image_and_title_focus"
    if funnel.get("cvr") is not None and funnel["cvr"] < 0.08:
        return "content_and_trust_focus"
    if funnel.get("acos") is not None and funnel["acos"] > 0.35:
        return "pricing_and_positioning_focus"
    return "balanced"


def build_funnel_prompt_context(funnel: dict, focus: str) -> str:
    if funnel["has_real_data"]:
        return f"""
[Real performance data - last 30 days]
Impressions: {funnel['impressions']}, CTR: {funnel['ctr']},
CVR: {funnel['cvr']}, ACOS: {funnel['acos']}
Diagnosis focus direction: {focus}
Prioritize analysis around this direction. Do not analyze all dimensions equally.
"""
    return """
[Warning] No real performance data available for this ASIN.
All conclusions below are inferred from listing text only.
Mark confidence as LOW throughout.
"""
