from __future__ import annotations
"""Auth dependency — extract user from Bearer token."""

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.auth import validate_session
from app.services.access import ADMIN_USER_ID


async def get_current_user_id(
    authorization: str | None = Header(None),
) -> str:
    """Extract user_id from Bearer token. Admin returns a special marker."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization[7:]
    sess = validate_session(token)
    if not sess:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if sess.get("role") == "admin":
        return ADMIN_USER_ID
    return sess["user_id"]
