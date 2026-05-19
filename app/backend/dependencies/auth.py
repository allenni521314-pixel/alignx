import hashlib
import logging
from datetime import datetime
from typing import Optional

from core.auth import AccessTokenError, decode_access_token
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from schemas.auth import UserResponse

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


async def get_bearer_token(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> Optional[str]:
    """Extract bearer token from Authorization header. Returns None for guest access."""
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials

    # Allow guest access — return None instead of raising 401
    return None


async def get_current_user(token: Optional[str] = Depends(get_bearer_token)) -> UserResponse:
    """Dependency to get current authenticated user via JWT token.
    Returns a guest user when no token is provided.
    """
    # Guest access — no token provided
    if token is None:
        return UserResponse(
            id="guest",
            email="guest@alignx.local",
            name="Guest",
            role="user",
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
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def is_super_admin(user: UserResponse) -> bool:
    """Check if the given user has super_admin privileges.
    Super admins can see all sellers' data across tenants.
    Both 'super_admin' and 'admin' roles are treated as super admins for data viewing.
    """
    return user.role in ("super_admin", "admin")


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