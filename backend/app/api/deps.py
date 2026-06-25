from __future__ import annotations
"""Auth dependency — extract user from Bearer token."""

from fastapi import Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.auth import validate_session


async def get_current_user_id(
    authorization: str = Header(None),
) -> str | None:
    """Extract user_id from Bearer token. Returns None if unauthenticated.
    If admin, returns special admin marker that services use to skip filtering."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    sess = validate_session(token)
    if not sess:
        return None
    # Admin can see all data — return marker
    if sess.get("role") == "admin":
        return "__admin__"  # Services check: if user_id=="__admin__" → skip filter
    return sess["user_id"]
