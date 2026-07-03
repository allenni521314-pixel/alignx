"""Super Admin router - provides cross-tenant data viewing for super admins.

Endpoints here allow super admins to:
- List all sellers (users)
- View any seller's ASINs, products, and listings
- Promote a user to super_admin role
"""

import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_super_admin_user, get_current_user
from models.auth import User
from models.products import Products
from models.asin_analyses import Asin_analyses
from models.listings import Listings
from schemas.auth import UserResponse
from services.ai_usage import get_ai_usage_summary, get_model_price_cny
from services.ai_gateway import AIGatewayService
from services.model_invocation_contract import workflow_summary
from services.model_probe import probe_ai_models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["super-admin"])


class SellerInfo(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    role: str
    product_count: int = 0
    asin_score_count: int = 0
    listing_count: int = 0


class RoleUpdateRequest(BaseModel):
    role: str  # user / admin / super_admin


class AdminAIModelItem(BaseModel):
    module: str
    env_key: str
    model: str
    provider: str
    configured: bool
    endpoint: str
    purpose: str
    source: str = "environment"
    input_cost_per_1m_cny: float = 0.0
    output_cost_per_1m_cny: float = 0.0
    calls_7d: int = 0
    prompt_tokens_7d: int = 0
    completion_tokens_7d: int = 0
    total_tokens_7d: int = 0
    estimated_cost_cny_7d: float = 0.0
    last_called_at: Optional[str] = None
    real_called: bool = False


class AdminAIModelStatus(BaseModel):
    provider: str
    api_mode: str
    text_base_url: str
    vision_base_url: str
    gateway_configured: bool
    vision_configured: bool
    embedding_configured: bool
    rerank_configured: bool
    models: List[AdminAIModelItem]
    usage_7d: dict
    recharge_links: List[dict]
    legacy_alias_policy: str
    invocation_contract: List[dict]


MODULE_HISTORY_TABLES = [
    "action_snapshots",
    "ad_campaigns",
    "ad_data",
    "ad_recommendations",
    "ad_validation_results",
    "advertising_strategy_records",
    "ai_usage_logs",
    "asin_analyses",
    "asin_keyword_intent_scores",
    "asin_keyword_rank_snapshots",
    "asin_keyword_sales_validation_reports",
    "batch_causal_tasks",
    "capital_allocation_records",
    "causal_ab_comparisons",
    "competitor_insights",
    "consumer_intent_results",
    "core_engine_evidence",
    "cosmo_results",
    "diagnosis_tasks",
    "execution_records",
    "fetch_history",
    "health_reports",
    "human_nature_graph_edges",
    "human_nature_graph_nodes",
    "human_state_body",
    "judgment_feedback_rounds",
    "keywords",
    "knowledge_evolution_events",
    "listing_diagnoses",
    "listings",
    "opc_os_executions",
    "optimization_timeline",
    "prelaunch_test_results",
    "products",
    "review_causal_validations",
    "sales_metrics",
    "scrape_logs",
]


@router.get("/me")
async def get_admin_me(current_user: UserResponse = Depends(get_current_user)):
    """Get current user info including whether they are a super admin."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role,
        "is_super_admin": current_user.role == "super_admin",
    }


@router.get("/sellers", response_model=List[SellerInfo])
async def list_all_sellers(
    search: Optional[str] = Query(None, description="Search by email, name or id"),
    db: AsyncSession = Depends(get_db),
    _: UserResponse = Depends(get_super_admin_user),
):
    """List all registered sellers with their data counts."""
    query = select(User)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            (User.email.ilike(pattern))
            | (User.name.ilike(pattern))
            | (User.id.ilike(pattern))
        )
    query = query.order_by(User.created_at.desc())
    result = await db.execute(query)
    users = result.scalars().all()

    # Batch count products/analyses/listings per user
    out: List[SellerInfo] = []
    for u in users:
        product_count = (
            await db.execute(
                select(func.count(Products.id)).where(Products.user_id == u.id)
            )
        ).scalar() or 0
        asin_score_count = (
            await db.execute(
                select(func.count(Asin_analyses.id)).where(
                    Asin_analyses.user_id == u.id
                )
            )
        ).scalar() or 0
        listing_count = (
            await db.execute(
                select(func.count(Listings.id)).where(Listings.user_id == u.id)
            )
        ).scalar() or 0
        out.append(
            SellerInfo(
                id=u.id,
                email=u.email,
                name=u.name,
                role=u.role,
                product_count=product_count,
                asin_score_count=asin_score_count,
                listing_count=listing_count,
            )
        )
    return out


@router.get("/sellers/{seller_id}/products")
async def get_seller_products(
    seller_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: UserResponse = Depends(get_super_admin_user),
):
    """Get all products of a specific seller."""
    total_q = select(func.count(Products.id)).where(Products.user_id == seller_id)
    total = (await db.execute(total_q)).scalar() or 0

    query = (
        select(Products)
        .where(Products.user_id == seller_id)
        .order_by(Products.id.desc())
        .offset(skip)
        .limit(limit)
    )
    items = (await db.execute(query)).scalars().all()
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/sellers/{seller_id}/asin-scores")
async def get_seller_asin_scores(
    seller_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: UserResponse = Depends(get_super_admin_user),
):
    """Get all 5D ASIN scores of a specific seller."""
    base_filter = (Asin_analyses.user_id == seller_id) & (
        Asin_analyses.score_5d_total.isnot(None)
    )
    total = (
        await db.execute(select(func.count(Asin_analyses.id)).where(base_filter))
    ).scalar() or 0

    query = (
        select(Asin_analyses)
        .where(base_filter)
        .order_by(Asin_analyses.id.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = (await db.execute(query)).scalars().all()

    items = [
        {
            "id": r.id,
            "asin": r.asin,
            "marketplace": r.marketplace,
            "product_title": r.product_title,
            "total_score": r.score_5d_total,
            "qualified": bool(r.qualified),
            "dimension_scores": {
                "demand": r.score_5d_demand,
                "scenario": r.score_5d_scenario,
                "competition": r.score_5d_competition,
                "profit": r.score_5d_profit,
                "trend": r.score_5d_trend,
            },
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/sellers/{seller_id}/listings")
async def get_seller_listings(
    seller_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: UserResponse = Depends(get_super_admin_user),
):
    """Get all listings of a specific seller."""
    total = (
        await db.execute(
            select(func.count(Listings.id)).where(Listings.user_id == seller_id)
        )
    ).scalar() or 0

    query = (
        select(Listings)
        .where(Listings.user_id == seller_id)
        .order_by(Listings.id.desc())
        .offset(skip)
        .limit(limit)
    )
    items = (await db.execute(query)).scalars().all()
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/overview")
async def admin_overview(
    db: AsyncSession = Depends(get_db),
    _: UserResponse = Depends(get_super_admin_user),
):
    """Get platform-wide overview stats for super admins."""
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_products = (await db.execute(select(func.count(Products.id)))).scalar() or 0
    total_asin_scores = (
        await db.execute(
            select(func.count(Asin_analyses.id)).where(
                Asin_analyses.score_5d_total.isnot(None)
            )
        )
    ).scalar() or 0
    qualified_count = (
        await db.execute(
            select(func.count(Asin_analyses.id)).where(Asin_analyses.qualified == 1)
        )
    ).scalar() or 0
    total_listings = (await db.execute(select(func.count(Listings.id)))).scalar() or 0

    return {
        "total_users": total_users,
        "total_products": total_products,
        "total_asin_scores": total_asin_scores,
        "qualified_count": qualified_count,
        "total_listings": total_listings,
    }


@router.get("/ai-models", response_model=AdminAIModelStatus)
async def get_admin_ai_models(
    _: UserResponse = Depends(get_super_admin_user),
):
    """Return the effective AI model map for super admins without exposing secrets."""
    gateway = AIGatewayService()
    gateway_status = gateway.status()

    text_api_key = (os.getenv("OPENAI_API_KEY") or os.getenv("APP_AI_KEY") or "").strip()
    vision_api_key = (os.getenv("VISION_API_KEY") or os.getenv("QWEN_API_KEY") or "").strip()
    embedding_model = (os.getenv("AI_EMBEDDING_MODEL") or os.getenv("EMBEDDING_MODEL") or "").strip()
    rerank_model = (os.getenv("RERANK_MODEL") or os.getenv("AI_RERANK_MODEL") or "").strip()
    embedding_api_key = (
        os.getenv("EMBEDDING_API_KEY")
        or os.getenv("SILICONFLOW_API_KEY")
        or ""
    ).strip()
    rerank_api_key = (
        os.getenv("RERANK_API_KEY")
        or os.getenv("SILICONFLOW_API_KEY")
        or ""
    ).strip()
    embedding_base_url = (
        os.getenv("EMBEDDING_BASE_URL")
        or os.getenv("SILICONFLOW_BASE_URL")
        or gateway_status.base_url
    ).strip().rstrip("/")
    rerank_base_url = (
        os.getenv("RERANK_BASE_URL")
        or os.getenv("SILICONFLOW_BASE_URL")
        or gateway_status.base_url
    ).strip().rstrip("/")
    vision_base_url = (
        os.getenv("VISION_BASE_URL")
        or os.getenv("QWEN_BASE_URL")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ).rstrip("/")
    vision_model = os.getenv("AI_VISION_MODEL") or os.getenv("VISION_MODEL") or "qwen3-vl-plus"

    text_endpoint = f"{gateway_status.base_url.rstrip('/')}/chat/completions"
    vision_endpoint = f"{vision_base_url}/chat/completions"
    embedding_endpoint = f"{embedding_base_url}/embeddings"
    rerank_endpoint = f"{rerank_base_url}/rerank"
    embedding_provider = (
        "SiliconFlow"
        if embedding_model and "siliconflow" in embedding_base_url.lower()
        else ("OpenAI-compatible" if embedding_model else "local-fallback")
    )
    rerank_provider = (
        "SiliconFlow"
        if rerank_model and "siliconflow" in rerank_base_url.lower()
        else ("OpenAI-compatible" if rerank_model else "disabled")
    )
    embedding_configured = bool(embedding_model and embedding_api_key and embedding_base_url)
    rerank_configured = bool(rerank_model and rerank_api_key and rerank_base_url)

    models = [
        AdminAIModelItem(
            module="主文本诊断",
            env_key="AI_DEFAULT_MODEL",
            model=gateway_status.default_model,
            provider=gateway_status.provider,
            configured=bool(text_api_key),
            endpoint=text_endpoint,
            purpose="Listing诊断、竞品分析、ASIN判断等默认文本推理。",
        ),
        AdminAIModelItem(
            module="轻量判断",
            env_key="AI_LIGHT_MODEL",
            model=gateway_status.light_model,
            provider=gateway_status.provider,
            configured=bool(text_api_key),
            endpoint=text_endpoint,
            purpose="低成本快速判断、辅助动作生成和轻量Agent任务。",
        ),
        AdminAIModelItem(
            module="标准推理",
            env_key="AI_REASONING_MODEL",
            model=gateway_status.reasoning_model,
            provider=gateway_status.provider,
            configured=bool(text_api_key),
            endpoint=text_endpoint,
            purpose="需要更强推理的选品、诊断、广告验证判断。",
        ),
        AdminAIModelItem(
            module="深度分析",
            env_key="AI_DEEP_MODEL",
            model=gateway_status.deep_model,
            provider=gateway_status.provider,
            configured=bool(text_api_key),
            endpoint=text_endpoint,
            purpose="复杂复盘、跨模块归因和高价值诊断任务。",
        ),
        AdminAIModelItem(
            module="图片/OCR视觉理解",
            env_key="AI_VISION_MODEL",
            model=vision_model,
            provider=os.getenv("VISION_PROVIDER") or "qwen",
            configured=bool(vision_api_key),
            endpoint=vision_endpoint,
            purpose="主图、副图、A+图片、图片内文字、徽章、认证、风险承诺和合规话术识别。",
        ),
        AdminAIModelItem(
            module="语义向量召回",
            env_key="AI_EMBEDDING_MODEL",
            model=embedding_model or "deterministic_hash_embedding_384d",
            provider=embedding_provider,
            configured=embedding_configured,
            endpoint=embedding_endpoint if embedding_model else "local deterministic fallback",
            purpose="历史诊断、COSMO语义映射和相似证据召回。",
            source="environment" if embedding_model else "local fallback",
        ),
        AdminAIModelItem(
            module="语义精排",
            env_key="RERANK_MODEL",
            model=rerank_model or "未启用",
            provider=rerank_provider,
            configured=rerank_configured,
            endpoint=rerank_endpoint if rerank_model else "disabled",
            purpose="过滤低相关召回结果，提升历史证据进入Prompt的准确度。",
            source="environment" if rerank_model else "disabled",
        ),
    ]
    for item in models:
        input_price, output_price = get_model_price_cny(item.model)
        item.input_cost_per_1m_cny = input_price
        item.output_cost_per_1m_cny = output_price

    usage_7d = await get_ai_usage_summary(days=7)
    usage_by_model: dict[str, dict] = {}
    for row in usage_7d.get("by_model", []):
        key = str(row.get("model") or "")
        if not key:
            continue
        bucket = usage_by_model.setdefault(
            key,
            {
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_cny": 0.0,
                "last_called_at": None,
            },
        )
        bucket["calls"] += int(row.get("calls") or 0)
        bucket["prompt_tokens"] += int(row.get("prompt_tokens") or 0)
        bucket["completion_tokens"] += int(row.get("completion_tokens") or 0)
        bucket["total_tokens"] += int(row.get("total_tokens") or 0)
        bucket["estimated_cost_cny"] += float(row.get("estimated_cost_cny") or 0.0)
        last_called_at = row.get("last_called_at")
        if last_called_at and (
            not bucket["last_called_at"] or str(last_called_at) > str(bucket["last_called_at"])
        ):
            bucket["last_called_at"] = last_called_at

    for item in models:
        usage = usage_by_model.get(item.model, {})
        item.calls_7d = int(usage.get("calls") or 0)
        item.prompt_tokens_7d = int(usage.get("prompt_tokens") or 0)
        item.completion_tokens_7d = int(usage.get("completion_tokens") or 0)
        item.total_tokens_7d = int(usage.get("total_tokens") or 0)
        item.estimated_cost_cny_7d = round(float(usage.get("estimated_cost_cny") or 0.0), 6)
        item.last_called_at = usage.get("last_called_at")
        item.real_called = item.calls_7d > 0

    return AdminAIModelStatus(
        provider=gateway_status.provider,
        api_mode=gateway_status.api_mode,
        text_base_url=gateway_status.base_url,
        vision_base_url=vision_base_url,
        gateway_configured=gateway_status.configured,
        vision_configured=bool(vision_api_key),
        embedding_configured=embedding_configured,
        rerank_configured=rerank_configured,
        models=models,
        usage_7d=usage_7d,
        recharge_links=[
            {"provider": "DeepSeek", "url": "https://platform.deepseek.com/usage"},
            {"provider": "SiliconFlow", "url": "https://cloud.siliconflow.cn/account/bill"},
            {"provider": "阿里云百炼 DashScope", "url": "https://bailian.console.aliyun.com/"},
        ],
        legacy_alias_policy="业务代码只能使用职责别名：AI_LIGHT_MODEL、AI_REASONING_MODEL、AI_DEEP_MODEL、AI_VISION_MODEL、AI_EMBEDDING_MODEL、RERANK_MODEL；旧模型名前缀会映射到文本默认模型，不作为生产模型直接调用。",
        invocation_contract=workflow_summary(),
    )


@router.post("/ai-models/probe")
async def probe_admin_ai_models(
    _: UserResponse = Depends(get_super_admin_user),
):
    """Run tiny real calls against every configured model family."""
    return await probe_ai_models()


@router.post("/module-history/clear")
async def clear_module_history(
    db: AsyncSession = Depends(get_db),
    _: UserResponse = Depends(get_super_admin_user),
):
    deleted: dict[str, int] = {}
    try:
        dialect_name = db.get_bind().dialect.name if db.get_bind() is not None else "sqlite"
        if dialect_name == "postgresql":
            existing_result = await db.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            )
        else:
            existing_result = await db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        existing_tables = {str(row[0]) for row in existing_result.fetchall()}
        for table_name in MODULE_HISTORY_TABLES:
            if table_name not in existing_tables:
                deleted[table_name] = 0
                continue
            result = await db.execute(text(f"DELETE FROM {table_name}"))
            deleted[table_name] = int(result.rowcount or 0)
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to clear module history")
        raise HTTPException(status_code=500, detail="清除失败")
    return {"status": "ok", "deleted": deleted}


@router.post("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    payload: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: UserResponse = Depends(get_super_admin_user),
):
    """Promote or demote a user's role. Only super_admin can perform this."""
    if payload.role not in ("user", "admin", "super_admin"):
        raise HTTPException(status_code=400, detail="Invalid role")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = payload.role
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "email": user.email, "role": user.role}
