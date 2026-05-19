"""Super Admin router - provides cross-tenant data viewing for super admins.

Endpoints here allow super admins to:
- List all sellers (users)
- View any seller's ASINs, products, and listings
- Promote a user to super_admin role
"""

import logging
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


@router.get("/me")
async def get_admin_me(current_user: UserResponse = Depends(get_current_user)):
    """Get current user info including whether they are a super admin."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role,
        "is_super_admin": current_user.role in ("super_admin", "admin"),
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