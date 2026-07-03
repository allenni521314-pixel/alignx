from __future__ import annotations
"""Account API — user account info (plan, balance, usage)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Account
from app.api.deps import get_current_user_id
from app.services.access import require_user_id

router = APIRouter(prefix="/api/v1/account", tags=["account"])


@router.get("")
async def get_account(
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_current_user_id),
):
    uid = require_user_id(user_id)
    q = select(Account).where(Account.user_id == uid)
    result = await db.execute(q)
    account = result.scalar_one_or_none()

    if not account:
        return {
            "user_id": uid,
            "plan": "free",
            "balance": 0.0,
            "total_calls": 0,
            "used_calls": 0,
            "created_at": None,
        }

    return {
        "user_id": account.user_id,
        "plan": account.plan,
        "balance": float(account.balance or 0),
        "total_calls": account.total_calls or 0,
        "used_calls": account.used_calls or 0,
        "created_at": account.created_at.isoformat() if account.created_at else None,
    }
