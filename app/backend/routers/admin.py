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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_super_admin_user, get_current_user
from models.auth import User
from models.products import Products
from models.asin_analyses import Asin_analyses
from models.listings import Listings
from schemas.auth import UserResponse
from services.ai_gateway import AIGatewayService

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
    legacy_alias_policy: str


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
    vision_base_url = (
        os.getenv("VISION_BASE_URL")
        or os.getenv("QWEN_BASE_URL")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ).rstrip("/")
    vision_model = os.getenv("AI_VISION_MODEL") or os.getenv("VISION_MODEL") or "qwen3-vl-plus"

    text_endpoint = f"{gateway_status.base_url.rstrip('/')}/chat/completions"
    vision_endpoint = f"{vision_base_url}/chat/completions"
    embedding_endpoint = f"{gateway_status.base_url.rstrip('/')}/embeddings"
    rerank_endpoint = f"{gateway_status.base_url.rstrip('/')}/rerank"

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
            module="图片/视觉理解",
            env_key="AI_VISION_MODEL",
            model=vision_model,
            provider=os.getenv("VISION_PROVIDER") or "qwen",
            configured=bool(vision_api_key),
            endpoint=vision_endpoint,
            purpose="主图、副图、A+图片和图片内文字理解。",
        ),
        AdminAIModelItem(
            module="语义向量召回",
            env_key="AI_EMBEDDING_MODEL",
            model=embedding_model or "deterministic_hash_embedding_384d",
            provider=gateway_status.provider if embedding_model else "local-fallback",
            configured=bool(embedding_model and text_api_key),
            endpoint=embedding_endpoint if embedding_model else "local deterministic fallback",
            purpose="历史诊断、COSMO语义映射和相似证据召回。",
            source="environment" if embedding_model else "local fallback",
        ),
        AdminAIModelItem(
            module="语义精排",
            env_key="RERANK_MODEL",
            model=rerank_model or "未启用",
            provider=gateway_status.provider if rerank_model else "disabled",
            configured=bool(rerank_model and text_api_key),
            endpoint=rerank_endpoint if rerank_model else "disabled",
            purpose="过滤低相关召回结果，提升历史证据进入Prompt的准确度。",
            source="environment" if rerank_model else "disabled",
        ),
    ]

    return AdminAIModelStatus(
        provider=gateway_status.provider,
        api_mode=gateway_status.api_mode,
        text_base_url=gateway_status.base_url,
        vision_base_url=vision_base_url,
        gateway_configured=gateway_status.configured,
        vision_configured=bool(vision_api_key),
        embedding_configured=bool(embedding_model and text_api_key),
        rerank_configured=bool(rerank_model and text_api_key),
        models=models,
        legacy_alias_policy="gemini-*、gpt-4*、gpt-5*、claude-* 会映射到 AI_DEFAULT_MODEL，不作为当前生产模型直接调用。",
    )


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
