import json
from datetime import datetime
from typing import Any, Optional

from core.database import get_db
from dependencies.auth import get_current_user, get_user_scope_ids
from fastapi import APIRouter, Depends, HTTPException
from models.ad_data import Ad_data
from models.asin_analyses import Asin_analyses
from models.causal_ab_comparison import CausalABComparison
from models.listing_diagnoses import Listing_diagnoses
from models.optimization_timeline import OptimizationTimeline
from models.prelaunch_test_results import Prelaunch_test_results
from models.products import Products
from schemas.auth import UserResponse
from services.agent_chain import AgentNodeRunRequest, get_agent_node_status, run_agent_node, run_all_agent_nodes
from services.agent_decision_system import build_agent_decision_system
from services.cosmo_operator_agent import CosmoOperatorAgent
from services.judgment_feedback_rounds import JudgmentFeedbackRoundService
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/workflow-chain", tags=["workflow-chain"])


def _json(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _dt(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _stage(
    key: str,
    title: str,
    source_table: str,
    row: Any,
    score: Optional[float] = None,
    summary: str = "",
    result: Any = None,
    next_action: str = "",
) -> dict:
    return {
        "key": key,
        "title": title,
        "status": "completed" if row else "missing",
        "source_table": source_table,
        "source_id": getattr(row, "id", None) if row else None,
        "timestamp": _dt(getattr(row, "created_at", None)) if row else None,
        "score": score,
        "summary": summary,
        "result": result or {},
        "next_action": next_action,
    }


def _confidence_from_score(score: Optional[float], status: str = "completed") -> str:
    if status != "completed":
        return "低"
    if score is None:
        return "中"
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "中"
    if value >= 80:
        return "高"
    if value >= 65:
        return "中"
    return "低"


def _stage_evidence_meta(stage: dict, ad_totals: Optional[dict] = None, timeline_count: int = 0) -> dict:
    key = stage.get("key")
    status = stage.get("status", "missing")
    score = stage.get("score")
    source_table = stage.get("source_table")
    source_id = stage.get("source_id")
    source_ref = f"{source_table} #{source_id}" if source_id else source_table

    meta_map = {
        "selection": {
            "data_source": "ASIN 6维评分记录",
            "source_type": "standardized_asin_input",
            "ai_role": "selection_agent",
            "judgment_basis": "基于需求、场景、竞争、利润、趋势、价格带的标准化评分判断是否进入机会池。",
        },
        "launch_check": {
            "data_source": "上新检测记录",
            "source_type": "manual_listing_or_authorized_data",
            "ai_role": "launch_check_agent",
            "judgment_basis": "基于标题、五点、图片、A+、价格、类目和关键词判断上架前风险。",
        },
        "listing_diagnosis": {
            "data_source": "Listing 诊断记录",
            "source_type": "listing_alignment_system",
            "ai_role": "listing_diagnosis_agent",
            "judgment_basis": "基于评论需求对齐度、Cosmo语义对齐度、因果转化对齐度定位表达错配。",
        },
        "ab_test": {
            "data_source": "A/B 测试计划与结果",
            "source_type": "causal_ab_test",
            "ai_role": "ad_validation_agent",
            "judgment_basis": "基于测试版本差异、置信分和胜出版本判断是否进入广告执行。",
        },
        "ad_validation": {
            "data_source": "广告表现记录",
            "source_type": "real_traffic_validation",
            "ai_role": "ad_validation_agent",
            "judgment_basis": "基于曝光、点击、订单、CVR、ACOS 和搜索词表现验证诊断假设是否成立。",
        },
        "review": {
            "data_source": "复盘优化记录",
            "source_type": "feedback_loop",
            "ai_role": "review_optimization_agent",
            "judgment_basis": "基于执行记录、修改前后数据和广告验证结果沉淀命中率与下一轮动作。",
        },
    }
    meta = meta_map.get(key, {})
    confidence = _confidence_from_score(score, status)

    if key == "ad_validation" and ad_totals:
        clicks = ad_totals.get("clicks", 0) or 0
        if clicks >= 100:
            confidence = "高"
        elif clicks >= 50:
            confidence = "中"
        else:
            confidence = "低"
    if key == "review":
        confidence = "高" if timeline_count >= 3 else "中" if timeline_count else "低"

    if status != "completed":
        confidence_reason = "该节点暂无完整记录，判断只能作为低置信度提示。"
    elif key == "ad_validation":
        clicks = (ad_totals or {}).get("clicks", 0) or 0
        confidence_reason = f"广告点击样本 {clicks}，超过100次点击后判断更可靠。"
    elif key == "review":
        confidence_reason = f"已沉淀 {timeline_count} 条复盘记录，记录越多命中率越可靠。"
    else:
        confidence_reason = "该节点已有结构化业务记录，可作为当前判断依据。"

    return {
        "data_source": meta.get("data_source", source_ref),
        "source_type": meta.get("source_type", "business_record"),
        "source_ref": source_ref,
        "decision_standard": CosmoOperatorAgent.public_standard_meta("feedback_loop"),
        "confidence": confidence,
        "confidence_reason": confidence_reason,
        "judgment_basis": meta.get("judgment_basis", stage.get("summary") or "基于当前节点结构化记录生成判断。"),
        "ai_role": meta.get("ai_role", "alignx_agent"),
        "ai_used": False,
        "ai_status": "待接入真实模型，当前为规则化判断 + 结构化数据证据。",
    }


async def _first(db: AsyncSession, stmt):
    result = await db.execute(stmt)
    return result.scalars().first()


async def _all(db: AsyncSession, stmt):
    result = await db.execute(stmt)
    return result.scalars().all()


def _text_similarity(a: str | None, b: str | None) -> float:
    """Small deterministic guardrail to avoid joining another ASIN's records."""
    left = {part for part in (a or "").lower().replace("-", " ").split() if len(part) >= 3}
    right = {part for part in (b or "").lower().replace("-", " ").split() if len(part) >= 3}
    if not left or not right:
        return 0
    return len(left & right) / max(len(left), len(right))


def _record_matches_product(row: Any, product: Products) -> bool:
    if not row or not product:
        return False
    asin = (product.asin or "").strip().lower()
    product_title = product.title or ""
    text_parts = [
        getattr(row, "title", None),
        getattr(row, "listing_title", None),
        getattr(row, "input_data", None),
        getattr(row, "text_report", None),
    ]
    for key in ("variant_a_info", "variant_b_info", "full_diagnosis_a"):
        value = getattr(row, key, None)
        if isinstance(value, dict):
            text_parts.extend(str(value.get(field, "")) for field in ("asin", "title", "listing_title"))
        elif value:
            text_parts.append(str(value))
    joined = " ".join(str(part or "") for part in text_parts).lower()
    if asin and asin in joined:
        return True
    return _text_similarity(product_title, joined) >= 0.25


async def _first_matching_product(
    db: AsyncSession,
    stmt,
    product: Products,
    *,
    allow_latest_bridge: bool = False,
):
    """Pick the latest record that belongs to the active product.

    Some legacy tables do not have product_id/asin columns yet. Returning the
    latest account record would contaminate the workflow chain when a seller
    tests multiple ASINs, so we only bridge records with matching ASIN/title.
    """
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    for row in rows:
        if _record_matches_product(row, product):
            return row
    return rows[0] if allow_latest_bridge and len(rows) == 1 else None


def _ad_metrics(records: list[Ad_data]) -> dict:
    metrics = {
        "impressions": sum(a.impressions or 0 for a in records),
        "clicks": sum(a.clicks or 0 for a in records),
        "spend": round(sum(a.spend or 0 for a in records), 2),
        "orders": sum(a.orders or 0 for a in records),
        "sales": round(sum(a.sales or 0 for a in records), 2),
    }
    metrics["ctr"] = round(metrics["clicks"] / metrics["impressions"] * 100, 2) if metrics["impressions"] else 0
    metrics["cvr"] = round(metrics["orders"] / metrics["clicks"] * 100, 2) if metrics["clicks"] else 0
    metrics["acos"] = round(metrics["spend"] / metrics["sales"] * 100, 2) if metrics["sales"] else 0
    return metrics


def _failure_reason(metrics: dict) -> str:
    impressions = metrics.get("impressions", 0) or 0
    clicks = metrics.get("clicks", 0) or 0
    ctr = metrics.get("ctr", 0) or 0
    cvr = metrics.get("cvr", 0) or 0
    acos = metrics.get("acos", 0) or 0
    if clicks < 100:
        return "sample_not_enough"
    if impressions >= 1000 and ctr < 0.25:
        return "image_click_gap"
    if ctr < 0.4:
        return "keyword_mismatch"
    if cvr < 8:
        return "detail_trust_gap"
    if acos > 35:
        return "price_promise_gap"
    return "none"


def _hit_status(metrics: dict) -> str:
    clicks = metrics.get("clicks", 0) or 0
    cvr = metrics.get("cvr", 0) or 0
    acos = metrics.get("acos", 0) or 0
    if clicks < 100:
        return "待验证"
    return "已命中" if cvr >= 8 and (acos == 0 or acos <= 35) else "未命中"


def _hypothesis_validations(ads: list[Ad_data]) -> list[dict]:
    grouped: dict[tuple[str, str, int], list[Ad_data]] = {}
    for ad in ads:
        hypothesis_id = getattr(ad, "hypothesis_id", None) or "unassigned"
        keyword_group_id = getattr(ad, "keyword_group_id", None) or getattr(ad, "ad_group_name", None) or "default"
        optimization_round = getattr(ad, "optimization_round", None) or 1
        grouped.setdefault((hypothesis_id, keyword_group_id, optimization_round), []).append(ad)

    validations: list[dict] = []
    for (hypothesis_id, keyword_group_id, optimization_round), records in grouped.items():
        metrics = _ad_metrics(records)
        keywords = sorted({record.keyword for record in records if record.keyword})
        validations.append(
            {
                "hypothesis_id": hypothesis_id,
                "keyword_group_id": keyword_group_id,
                "optimization_round": optimization_round,
                "keywords": keywords,
                "metrics": metrics,
                "hit_status": _hit_status(metrics),
                "failure_reason": _failure_reason(metrics),
                "confidence": "高" if metrics["clicks"] >= 100 else "中" if metrics["clicks"] >= 50 else "低",
                "record_count": len(records),
            }
        )
    return sorted(
        validations,
        key=lambda item: (item["optimization_round"], item["metrics"]["clicks"], item["metrics"]["sales"]),
        reverse=True,
    )


async def _build_chain(product: Products, user_ids: list[str], db: AsyncSession) -> dict:
    asin_analysis = await _first(
        db,
        select(Asin_analyses)
        .where(Asin_analyses.user_id.in_(user_ids), Asin_analyses.asin == product.asin)
        .order_by(desc(Asin_analyses.created_at), desc(Asin_analyses.id)),
    )

    prelaunch = await _first_matching_product(
        db,
        select(Prelaunch_test_results)
        .where(Prelaunch_test_results.user_id.in_(user_ids))
        .order_by(desc(Prelaunch_test_results.created_at), desc(Prelaunch_test_results.id)),
        product,
    )
    diagnosis = await _first_matching_product(
        db,
        select(Listing_diagnoses)
        .where(Listing_diagnoses.user_id.in_(user_ids))
        .order_by(desc(Listing_diagnoses.created_at), desc(Listing_diagnoses.id)),
        product,
    )
    ab = await _first_matching_product(
        db,
        select(CausalABComparison)
        .where(CausalABComparison.user_id.in_(user_ids))
        .order_by(desc(CausalABComparison.created_at), desc(CausalABComparison.id)),
        product,
    )
    ads = await _all(
        db,
        select(Ad_data)
        .where(Ad_data.user_id.in_(user_ids), Ad_data.product_id == product.id)
        .order_by(desc(Ad_data.date), desc(Ad_data.id)),
    )
    timeline = await _all(
        db,
        select(OptimizationTimeline)
        .where(OptimizationTimeline.user_id.in_(user_ids), OptimizationTimeline.product_id == product.id)
        .order_by(desc(OptimizationTimeline.created_at), desc(OptimizationTimeline.id)),
    )

    ad_totals = _ad_metrics(ads)
    hypothesis_validations = _hypothesis_validations(ads)
    assigned_validations = [item for item in hypothesis_validations if item["hypothesis_id"] != "unassigned"]

    stages = [
        _stage(
            "selection",
            "选品决策",
            "asin_analyses",
            asin_analysis,
            score=getattr(asin_analysis, "score_5d_total", None),
            summary="6维评分进入机会池" if getattr(asin_analysis, "qualified", 0) else "未进入机会池",
            result={
                "asin": product.asin,
                "qualified": bool(getattr(asin_analysis, "qualified", 0)) if asin_analysis else False,
                "dimension_scores": {
                    "demand": getattr(asin_analysis, "score_5d_demand", None),
                    "scenario": getattr(asin_analysis, "score_5d_scenario", None),
                    "competition": getattr(asin_analysis, "score_5d_competition", None),
                    "profit": getattr(asin_analysis, "score_5d_profit", None),
                    "trend": getattr(asin_analysis, "score_5d_trend", None),
                    "price_tier": getattr(asin_analysis, "score_5d_price_tier", None),
                } if asin_analysis else {},
            },
            next_action="进入Listing上新检测",
        ),
        _stage(
            "launch_check",
            "Listing 上新检测",
            "prelaunch_test_results",
            prelaunch,
            score=getattr(prelaunch, "overall_score", None),
            summary=getattr(prelaunch, "overall_summary", "") or "上新前检测已完成",
            result={
                "title_score": getattr(prelaunch, "score_title_keywords", None),
                "main_image_score": getattr(prelaunch, "score_main_image", None),
                "a_plus_score": getattr(prelaunch, "score_a_plus", None),
                "bullet_score": getattr(prelaunch, "score_bullet_points", None),
            } if prelaunch else {},
            next_action="进入上线后本品诊断",
        ),
        _stage(
            "listing_diagnosis",
            "Listing 上线后诊断",
            "listing_diagnoses",
            diagnosis,
            score=round(sum(
                v for v in [
                    getattr(diagnosis, "score_function_expression", None),
                    getattr(diagnosis, "score_scenario_expression", None),
                    getattr(diagnosis, "score_risk_elimination", None),
                    getattr(diagnosis, "score_differentiation", None),
                ] if v is not None
            ) / 4, 1) if diagnosis else None,
            summary="本品诊断已生成对齐度和优化建议",
            result={
                "function_expression": getattr(diagnosis, "score_function_expression", None),
                "scenario_expression": getattr(diagnosis, "score_scenario_expression", None),
                "risk_elimination": getattr(diagnosis, "score_risk_elimination", None),
                "diagnosis_report": _json(getattr(diagnosis, "diagnosis_report", None), {}),
            } if diagnosis else {},
            next_action="进入A/B测试和广告验证",
        ),
        _stage(
            "ab_test",
            "A/B 测试计划",
            "causal_ab_comparisons",
            ab,
            score=getattr(ab, "confidence_score", None),
            summary=f"{getattr(ab, 'winner', '')} 版本胜出" if ab else "",
            result={
                "winner": getattr(ab, "winner", None),
                "win_margin": getattr(ab, "win_margin", None),
                "confidence_score": getattr(ab, "confidence_score", None),
                "recommendations": getattr(ab, "actionable_recommendations", None),
            } if ab else {},
            next_action="进入广告执行记录",
        ),
        _stage(
            "ad_validation",
            "广告投放验证",
            "ad_data",
            ads[0] if ads else None,
            score=ad_totals["cvr"] if ads else None,
            summary=(
                f"{len(assigned_validations)} 个假设已进入广告验证"
                if assigned_validations
                else "广告验证待绑定具体诊断假设"
            ),
            result={
                **ad_totals,
                "hypothesis_validations": hypothesis_validations,
                "assigned_hypothesis_count": len(assigned_validations),
                "unassigned_record_count": sum(
                    item["record_count"] for item in hypothesis_validations if item["hypothesis_id"] == "unassigned"
                ),
            },
            next_action="进入数据回流",
        ),
        _stage(
            "review",
            "复盘优化",
            "optimization_timeline",
            timeline[0] if timeline else None,
            score=getattr(timeline[0], "listing_score", None) if timeline else None,
            summary="验证结果已回流，进入下一轮优化" if timeline else "",
            result={
                "events": [
                    {
                        "id": item.id,
                        "step_name": item.step_name,
                        "score": item.listing_score,
                        "details": _json(item.score_details, {}),
                        "round": item.optimization_round,
                    }
                    for item in timeline
                ]
            },
            next_action="生成下一轮优化动作",
        ),
    ]

    completed = sum(1 for stage in stages if stage["status"] == "completed")
    for stage in stages:
        stage["evidence_meta"] = _stage_evidence_meta(stage, ad_totals=ad_totals, timeline_count=len(timeline))

    product_payload = {
        "id": product.id,
        "asin": product.asin,
        "title": product.title,
        "category": product.category,
        "lifecycle_stage": product.lifecycle_stage,
        "optimization_round": product.optimization_round,
    }
    learning_memory = await JudgmentFeedbackRoundService(db).learning_memory(
        user_id=user_ids,
        asin=product.asin,
        product_id=product.id,
        limit=200,
    )
    decision_product_payload = {**product_payload, "learning_memory": learning_memory}
    return {
        "product": product_payload,
        "chain_status": "complete" if completed == len(stages) else "partial",
        "completed_stages": completed,
        "total_stages": len(stages),
        "integrity_score": round(completed / len(stages) * 100),
        "stages": stages,
        "agent_decision": build_agent_decision_system(decision_product_payload, stages),
    }


@router.get("/current")
async def get_current_workflow_chain(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope_user_ids = await get_user_scope_ids(current_user, db)
    product = await _first(
        db,
        select(Products)
        .where(Products.user_id.in_(scope_user_ids))
        .order_by(desc(Products.updated_at), desc(Products.created_at), desc(Products.id)),
    )
    if not product:
        return {
            "product": None,
            "chain_status": "empty",
            "completed_stages": 0,
            "total_stages": 6,
            "integrity_score": 0,
            "stages": [],
            "agent_decision": None,
            "agent_nodes": [],
        }
    chain = await _build_chain(product, scope_user_ids, db)
    chain["agent_nodes"] = get_agent_node_status(chain)
    return chain


@router.get("/products/{product_id}")
async def get_product_workflow_chain(
    product_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope_user_ids = await get_user_scope_ids(current_user, db)
    product = await _first(
        db,
        select(Products).where(Products.id == product_id, Products.user_id.in_(scope_user_ids)),
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    chain = await _build_chain(product, scope_user_ids, db)
    chain["agent_nodes"] = get_agent_node_status(chain)
    return chain


@router.post("/current/agent-node")
async def run_current_agent_node(
    request: AgentNodeRunRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope_user_ids = await get_user_scope_ids(current_user, db)
    product = await _first(
        db,
        select(Products)
        .where(Products.user_id.in_(scope_user_ids))
        .order_by(desc(Products.updated_at), desc(Products.created_at), desc(Products.id)),
    )
    if not product:
        raise HTTPException(status_code=404, detail="No product found for workflow chain")
    chain = await _build_chain(product, scope_user_ids, db)
    return await run_agent_node(chain, request)


@router.post("/current/agent-nodes")
async def run_current_agent_nodes(
    depth: str = "standard",
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope_user_ids = await get_user_scope_ids(current_user, db)
    product = await _first(
        db,
        select(Products)
        .where(Products.user_id.in_(scope_user_ids))
        .order_by(desc(Products.updated_at), desc(Products.created_at), desc(Products.id)),
    )
    if not product:
        raise HTTPException(status_code=404, detail="No product found for workflow chain")
    if depth not in {"light", "standard", "deep"}:
        raise HTTPException(status_code=400, detail="depth must be light, standard, or deep")
    chain = await _build_chain(product, scope_user_ids, db)
    return await run_all_agent_nodes(chain, depth=depth)  # type: ignore[arg-type]
