import hashlib
import logging
from datetime import datetime
from typing import Optional

from core.auth import AccessTokenError, decode_access_token
from core.database import get_db
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from models.auth import User
from schemas.auth import UserResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)
LOCAL_DEV_TOKEN = "dev-local-token"


def _is_local_request(request: Request) -> bool:
    host = (request.client.host if request.client else "") or ""
    request_host = request.url.hostname or ""
    return host in {"127.0.0.1", "::1", "localhost"} or request_host in {"127.0.0.1", "::1", "localhost"}


async def get_bearer_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> str:
    """Extract bearer token from Authorization header."""
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    if _is_local_request(request):
        return LOCAL_DEV_TOKEN

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(request: Request, token: str = Depends(get_bearer_token)) -> UserResponse:
    """Dependency to get current authenticated user via JWT token."""
    if token == LOCAL_DEV_TOKEN and _is_local_request(request):
        return UserResponse(
            id="dev-user",
            email="dev@local.alignx",
            name="本地开发",
            role="admin",
            last_login=None,
        )

    try:
        payload = decode_access_token(token)
    except AccessTokenError as exc:
        # Log error type only, not the full exception which may contain sensitive token data
        logger.warning("Token validation failed: %s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.message)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")

    last_login_raw = payload.get("last_login")
    last_login = None
    if isinstance(last_login_raw, str):
        try:
            last_login = datetime.fromisoformat(last_login_raw)
        except ValueError:
            # Log user hash instead of actual user ID to avoid exposing sensitive information
            user_hash = hashlib.sha256(str(user_id).encode()).hexdigest()[:8] if user_id else "unknown"
            logger.debug("Failed to parse last_login for user hash: %s", user_hash)

    return UserResponse(
        id=user_id,
        email=payload.get("email", ""),
        name=payload.get("name"),
        role=payload.get("role", "user"),
        last_login=last_login,
    )


async def get_admin_user(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Dependency to ensure current user has admin role."""
    if current_user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def is_super_admin(user: UserResponse) -> bool:
    """Check if the given user has super_admin privileges.
    Super admins can see all sellers' data across tenants.
    """
    return user.role == "super_admin"


async def get_super_admin_user(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Dependency to ensure current user has super_admin role."""
    if not is_super_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return current_user


def get_effective_user_id(current_user: UserResponse, view_all: bool = False) -> Optional[str]:
    """Get the effective user_id for data filtering.
    - For super_admin with view_all=True: returns None (no filtering, see all users' data)
    - Otherwise: returns current_user.id (filter to own data only)
    """
    if view_all and is_super_admin(current_user):
        return None
    return str(current_user.id)


def get_canonical_email_user_id(email: str) -> str:
    normalized = (email or "").strip().lower()
    if not normalized:
        return ""
    return f"email_{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:20]}"


async def get_user_scope_ids(current_user: UserResponse, db: AsyncSession) -> list[str]:
    """Return user ids that belong to the same normalized email identity.

    AlignX moved from OIDC/phone-style ids to deterministic email ids during
    beta auth. Historical records may still be attached to the older id, so
    read paths should include same-email aliases while keeping cross-email
    tenant isolation intact.
    """
    ids = {str(current_user.id)}
    email = (current_user.email or "").strip().lower()
    if not email:
        return list(ids)

    canonical_email_id = get_canonical_email_user_id(email)
    if canonical_email_id:
        ids.add(canonical_email_id)

    result = await db.execute(select(User.id).where(func.lower(User.email) == email))
    ids.update(str(row[0]) for row in result.all() if row and row[0])
    return list(ids)
