from __future__ import annotations
"""Yesterday report + today decisions — aggregate from profiles, executions, validations."""

from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    AsinOperationProfile,
    ExecutionRecord,
    Proposition,
    ValidationResult,
    ValidationTask,
)
from app.config import get_settings
from app.services.access import require_user_id, user_scoped


async def generate_yesterday_report(db: AsyncSession, user_id: str | None = None) -> dict:
    """Aggregate yesterday's data across all ASINs."""
    uid = require_user_id(user_id)

    yesterday = datetime.utcnow() - timedelta(days=1)

    # ASIN profiles
    profiles_q = user_scoped(select(AsinOperationProfile), AsinOperationProfile, uid)
    profiles_q = profiles_q.order_by(AsinOperationProfile.updated_at.desc())
    profiles = (await db.execute(profiles_q)).scalars().all()

    # Yesterday's executions
    execs_q = user_scoped(select(ExecutionRecord), ExecutionRecord, uid)
    execs_q = execs_q.where(ExecutionRecord.executed_at >= yesterday)
    executions = (await db.execute(execs_q)).scalars().all()

    # Validation results
    results_q = user_scoped(select(ValidationResult), ValidationResult, uid)
    results = (await db.execute(results_q)).scalars().all()

    # Pending validation tasks
    tasks_q = user_scoped(select(ValidationTask), ValidationTask, uid)
    tasks_q = tasks_q.where(ValidationTask.execution_status == "pending")
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


async def generate_today_decisions(db: AsyncSession, user_id: str | None = None) -> dict:
    """返回三区面板数据：待验证 / 测试中 / 已验证有效。"""
    uid = require_user_id(user_id)

    # All validation tasks
    tasks_q = user_scoped(select(ValidationTask), ValidationTask, uid)
    tasks_q = tasks_q.order_by(ValidationTask.created_at.desc())
    tasks = (await db.execute(tasks_q)).scalars().all()

    # All validation results
    results_q = user_scoped(select(ValidationResult), ValidationResult, uid)
    results_q = results_q.order_by(ValidationResult.created_at.desc())
    results = (await db.execute(results_q)).scalars().all()

    # Execution records (for cost calculation)
    execs_q = user_scoped(select(ExecutionRecord), ExecutionRecord, uid)
    executions = (await db.execute(execs_q)).scalars().all()

    # ASIN profiles (for product titles)
    profiles_q = user_scoped(select(AsinOperationProfile), AsinOperationProfile, uid)
    profiles = (await db.execute(profiles_q)).scalars().all()
    profile_map = {p.asin: p for p in profiles}

    propositions_q = select(Proposition)
    propositions = (await db.execute(propositions_q)).scalars().all()
    proposition_map = {p.proposition_code: p for p in propositions}
    budget_limit = get_settings().validation_budget_limit

    def _profile(asin: str):
        return profile_map.get(asin)

    def _task_cost(task_id: str) -> float | None:
        costs = [e.cost_amount for e in executions if e.validation_task_id == task_id and e.cost_amount]
        return round(sum(costs), 2) if costs else None

    task_map = {t.id: t for t in tasks}
    history: dict[str, dict[str, int]] = {}
    failed_next: dict[str, str] = {}
    # Cross-ASIN learning: per proposition code, which ASINs were effective / ineffective
    cross_asin_success: dict[str, list[str]] = {}
    cross_asin_fail: dict[str, list[str]] = {}
    for r in results:
        task = task_map.get(r.validation_task_id)
        if not task:
            continue
        code = task.proposition_code
        stats = history.setdefault(code, {
            "effective": 0,
            "ineffective": 0,
            "interfered": 0,
            "insufficient_data": 0,
        })
        status = r.final_result_status or "insufficient_data"
        if status in stats:
            stats[status] += 1
        prop = proposition_map.get(code)
        if status == "ineffective" and prop and prop.next_proposition_if_failed:
            failed_next[code] = prop.next_proposition_if_failed
        # Cross-ASIN tracking
        if status == "effective":
            cs = cross_asin_success.setdefault(code, [])
            if task.asin not in cs:
                cs.append(task.asin)
        elif status == "ineffective":
            cf = cross_asin_fail.setdefault(code, [])
            if task.asin not in cf:
                cf.append(task.asin)

    next_codes = set(failed_next.values())
    # Category affinity: group ASINs by category for same-category boost
    asin_category: dict[str, str] = {}
    for p in profiles:
        if p.category:
            asin_category[p.asin] = p.category

    def _history_score(task: ValidationTask) -> int:
        code = task.proposition_code
        stats = history.get(code, {})
        score = 100
        # Same-proposition history
        score += int(stats.get("effective", 0)) * 20
        score -= int(stats.get("ineffective", 0)) * 15
        score -= int(stats.get("interfered", 0)) * 8
        if code in next_codes:
            score += 25
        # Cross-ASIN boost: this proposition was effective on other ASINs
        cross_eff = cross_asin_success.get(code, [])
        if cross_eff:
            score += 15  # base cross-ASIN bonus
            my_cat = asin_category.get(task.asin)
            if my_cat:
                same_cat = [a for a in cross_eff if asin_category.get(a) == my_cat]
                if same_cat:
                    score += 25  # same-category success is strong signal
        # Cross-ASIN penalty: widespread failure
        cross_fail = cross_asin_fail.get(code, [])
        if len(cross_fail) >= 3:
            score -= 20
        return score

    def _history_signal(task: ValidationTask) -> str:
        code = task.proposition_code
        stats = history.get(code, {})
        if code in next_codes:
            return "换方向再试"
        cross_eff = cross_asin_success.get(code, [])
        if cross_eff:
            return "可靠方向" if stats.get("effective", 0) else "值得尝试"
        if stats.get("effective", 0):
            return "已验证可靠"
        if stats.get("ineffective", 0) >= 2:
            return "不建议重试"
        if stats.get("ineffective", 0):
            return "效果不理想"
        if stats.get("interfered", 0):
            return "上次受干扰"
        return "新方向"

    def _budget_gate(cost: float | None) -> dict:
        if budget_limit <= 0:
            return {"status": "未设置", "limit": None, "blocked": False}
        if cost is not None and cost > budget_limit:
            return {"status": "超过上限", "limit": budget_limit, "blocked": True}
        return {"status": "通过", "limit": budget_limit, "blocked": False}

    def _build_item(task: ValidationTask, extra: dict | None = None) -> dict:
        p = _profile(task.asin)
        cost = _task_cost(task.id)
        item = {
            "id": task.id,
            "asin": task.asin,
            "product_title": p.product_title if p else None,
            "hypothesis": task.hypothesis_text or task.proposition_name or task.proposition_code,
            "source": _source_label(task.source_module),
            "validation_period": task.validation_period,
            "estimated_cost": cost,
            "created_at": task.created_at.strftime("%m-%d") if task.created_at else "",
            "priority_score": _history_score(task),
            "history_signal": _history_signal(task),
            "budget_gate": _budget_gate(cost),
        }
        if extra:
            item.update(extra)
        return item

    # ── 🔴 待验证 ──
    pending = [
        _build_item(t)
        for t in tasks
        if t.execution_status == "pending"
    ]
    pending.sort(
        key=lambda item: (
            item["budget_gate"]["blocked"],
            -item["priority_score"],
            item["estimated_cost"] if item["estimated_cost"] is not None else 999999,
        )
    )

    # ── 🟡 测试中 ──
    running = [
        _build_item(t, {"running_days": _running_days(t)})
        for t in tasks
        if t.execution_status == "running"
    ]

    # ── 🟢 已验证有效 ──
    effective = []
    for r in results:
        if r.final_result_status == "effective":
            t = task_map.get(r.validation_task_id)
            if t:
                item = _build_item(t, {
                    "result_id": r.id,
                    "conclusion": r.attribution_conclusion or r.notes,
                    "verified_at": r.created_at.strftime("%m-%d") if r.created_at else "",
                    "next_step": "加大投入",
                })
                effective.append(item)

    # Global recommendation
    if pending:
        top = pending[0]
        rec = f"有 {len(pending)} 个假设待验证，优先：{top['history_signal']}"
    elif running:
        rec = f"{len(running)} 个测试进行中，等待数据收敛"
    else:
        rec = "暂无待验证假设，去做一次产品调研或竞品分析"

    return {
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "summary": {
            "pending": len(pending),
            "running": len(running),
            "effective": len(effective),
        },
        "pending": pending,
        "running": running,
        "effective": effective,
        "global_recommendation": rec,
        "budget_gate": {
            "limit": budget_limit if budget_limit > 0 else None,
            "status": "已设置" if budget_limit > 0 else "未设置",
        },
    }


def _source_label(module: str | None) -> str:
    mapping = {
        "conversion_diagnosis": "承接转化",
        "competitor_analysis": "竞品分析",
        "prelaunch_check": "上架准入",
        "market_opportunity": "产品调研",
        "ad_strategy": "流量策略",
        "manual": "手动创建",
    }
    return mapping.get(module or "", "手动创建")


def _running_days(task: ValidationTask) -> int:
    if not task.created_at:
        return 0
    delta = datetime.utcnow() - task.created_at
    return max(1, delta.days)
