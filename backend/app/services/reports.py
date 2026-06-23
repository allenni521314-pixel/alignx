from __future__ import annotations
"""Yesterday report + today decisions — aggregate from profiles, executions, validations."""

from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    AsinOperationProfile,
    ExecutionRecord,
    ValidationResult,
    ValidationTask,
)


async def generate_yesterday_report(db: AsyncSession) -> dict:
    """Aggregate yesterday's data across all ASINs."""

    yesterday = datetime.utcnow() - timedelta(days=1)

    # ASIN profiles
    profiles_q = select(AsinOperationProfile).order_by(AsinOperationProfile.updated_at.desc())
    profiles = (await db.execute(profiles_q)).scalars().all()

    # Yesterday's executions
    execs_q = select(ExecutionRecord).where(ExecutionRecord.executed_at >= yesterday)
    executions = (await db.execute(execs_q)).scalars().all()

    # Validation results
    results_q = select(ValidationResult)
    results = (await db.execute(results_q)).scalars().all()

    # Pending validation tasks
    tasks_q = select(ValidationTask).where(ValidationTask.execution_status == "pending")
    tasks = (await db.execute(tasks_q)).scalars().all()

    # Calculate totals
    total_executions = len(executions)
    total_cost = sum(e.cost_amount or 0 for e in executions)
    ad_spend = sum(e.cost_amount or 0 for e in executions if e.cost_type == "ad_spend")
    changed_positions = len(set(e.changed_position for e in executions if e.changed_position))

    # Recent ad records
    recent_ads = [
        {
            "asin": e.asin,
            "cost": e.cost_amount,
            "summary": e.action_summary,
            "date": e.executed_at.strftime("%m-%d") if e.executed_at else "",
        }
        for e in executions
        if e.cost_type == "ad_spend"
    ][:10]

    # Profile summaries with per-ASIN ad metrics
    profile_summaries = []
    for p in profiles:
        asin_execs = [e for e in executions if e.asin == p.asin]
        asin_ad_spend = sum(e.cost_amount or 0 for e in asin_execs if e.cost_type == "ad_spend")
        asin_ad_count = len([e for e in asin_execs if e.cost_type == "ad_spend"])

        # Parse ad metrics from evidence_note JSON
        total_impressions = 0
        total_clicks = 0
        total_orders = 0
        total_sales = 0.0
        for e in asin_execs:
            if e.cost_type == "ad_spend" and e.evidence_note:
                try:
                    metrics = __import__("json").loads(e.evidence_note)
                    if metrics.get("type") == "ad_metrics":
                        total_impressions += int(float(metrics.get("impressions", 0)))
                        total_clicks += int(float(metrics.get("clicks", 0)))
                        total_orders += int(float(metrics.get("orders", 0)))
                        total_sales += float(metrics.get("sales", 0))
                except Exception:
                    pass

        profile_summaries.append({
            "asin": p.asin,
            "product_title": p.product_title,
            "total_validations": p.total_validation_count,
            "effective": p.effective_count,
            "ineffective": p.ineffective_count,
            "current_problem": p.current_main_problem,
            "next_recommended": p.next_recommended_proposition,
            "learning": p.asin_learning_summary,
            "ad_spend": asin_ad_spend,
            "ad_executions": asin_ad_count,
            "total_cost": sum(e.cost_amount or 0 for e in asin_execs),
            "impressions": total_impressions,
            "clicks": total_clicks,
            "orders": total_orders,
            "sales": total_sales,
        })

    # Effective / ineffective breakdown
    effective = sum(1 for r in results if r.final_result_status == "effective")
    ineffective = sum(1 for r in results if r.final_result_status == "ineffective")
    interfered = sum(1 for r in results if r.final_result_status == "interfered")
    insufficient = sum(1 for r in results if r.final_result_status == "insufficient_data")

    # Main problems to highlight
    active_problems = []
    for p in profiles:
        if p.current_main_problem:
            active_problems.append({
                "asin": p.asin,
                "problem": p.current_main_problem,
                "next_action": p.next_recommended_proposition,
            })

    return {
        "date": yesterday.strftime("%Y-%m-%d"),
        "summary": {
            "total_executions": total_executions,
            "total_cost": total_cost,
            "ad_spend": ad_spend,
            "changed_positions": changed_positions,
            "active_asins": len(profiles),
            "pending_tasks": len(tasks),
        },
        "recent_ads": recent_ads,
        "validation_stats": {
            "effective": effective,
            "ineffective": ineffective,
            "interfered": interfered,
            "insufficient_data": insufficient,
        },
        "active_problems": active_problems,
        "profile_summaries": profile_summaries,
    }


async def generate_today_decisions(db: AsyncSession) -> dict:
    """Generate today's recommended actions based on current state."""

    profiles_q = select(AsinOperationProfile).order_by(AsinOperationProfile.updated_at.desc())
    profiles = (await db.execute(profiles_q)).scalars().all()

    tasks_q = select(ValidationTask).where(
        ValidationTask.execution_status.in_(["pending", "running"])
    )
    tasks = (await db.execute(tasks_q)).scalars().all()

    decisions = []

    for p in profiles:
        decision = {
            "asin": p.asin,
            "product_title": p.product_title,
            "lifecycle_stage": p.lifecycle_stage,
            "current_problem": p.current_main_problem,
            "recommended_action": p.next_recommended_proposition,
            "priority": _calculate_priority(p),
            "reasoning": _build_reasoning(p),
        }

        # Attach related tasks
        related_tasks = [t for t in tasks if t.asin == p.asin]
        if related_tasks:
            decision["active_tasks"] = [
                {
                    "proposition": t.proposition_name or t.proposition_code,
                    "status": t.execution_status,
                }
                for t in related_tasks
            ]

        decisions.append(decision)

    # Sort by priority
    decisions.sort(key=lambda d: d["priority"], reverse=True)

    return {
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "total_decisions": len(decisions),
        "urgent_count": sum(1 for d in decisions if d["priority"] >= 4),
        "decisions": decisions,
        "global_recommendation": (
            "重点关注高优先级 ASIN 的验证任务执行"
            if any(d["priority"] >= 4 for d in decisions)
            else "当前无紧急事项，按计划推进验证任务"
        ),
    }


def _calculate_priority(profile: AsinOperationProfile) -> int:
    """1-5 priority score based on profile state."""
    score = 1

    # Repeated failures = high priority
    if profile.repeated_failure_patterns_json:
        score += 2

    # Current main problem = high priority
    if profile.current_main_problem:
        score += 1

    # Low effectiveness rate
    total = profile.total_validation_count
    if total > 0:
        rate = profile.effective_count / total
        if rate < 0.3:
            score += 1

    return min(score, 5)


def _build_reasoning(profile: AsinOperationProfile) -> str:
    """Build concise reasoning — avoid duplicating current_problem/recommended_action."""
    parts = []
    total = profile.total_validation_count
    if total > 0:
        parts.append(f"验证{total}次，有效{profile.effective_count}，无效{profile.ineffective_count}")
    if profile.asin_learning_summary:
        parts.append(profile.asin_learning_summary)
    return "；".join(parts) if parts else "暂无足够数据"
