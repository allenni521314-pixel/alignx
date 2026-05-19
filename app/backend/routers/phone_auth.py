"""Phone-based authentication router for test version.

Allows users to register/login with phone number and a fixed password.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timezone

from core.auth import create_access_token
from core.config import settings
from core.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from models.auth import User
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth/phone", tags=["phone-authentication"])

# Fixed password for test version
FIXED_PASSWORD = "alignx2026"

# Super admin phone numbers - these users get super_admin role on login.
# TODO: Migrate to env variables in production.
SUPER_ADMIN_PHONES = {"13924666118"}


class PhoneLoginRequest(BaseModel):
    phone: str
    password: str


class PhoneLoginResponse(BaseModel):
    token: str
    user: dict


@router.post("/login", response_model=PhoneLoginResponse)
async def phone_login(payload: PhoneLoginRequest, db: AsyncSession = Depends(get_db)):
    """Register or login with phone number and fixed password.
    
    If the phone number doesn't exist, a new user is created.
    If it exists, the user is logged in.
    Password must match the fixed test password.
    """
    phone = payload.phone.strip()
    password = payload.password.strip()

    if not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号不能为空",
        )

    # Validate phone format (basic check for Chinese phone numbers)
    if not (phone.isdigit() and len(phone) >= 10):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请输入有效的手机号",
        )

    # Validate fixed password
    if password != FIXED_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="密码错误",
        )

    # Generate a deterministic user ID from phone number
    user_id = f"phone_{hashlib.sha256(phone.encode()).hexdigest()[:16]}"
    email = f"{phone}@phone.alignx.com"

    # Try to find existing user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    desired_role = "super_admin" if phone in SUPER_ADMIN_PHONES else "user"

    if user:
        # Update last login
        user.last_login = datetime.now(timezone.utc)
        # Auto-upgrade role if phone is in super admin list
        if phone in SUPER_ADMIN_PHONES and user.role != "super_admin":
            user.role = "super_admin"
        await db.commit()
        await db.refresh(user)
        logger.info(f"Phone login: existing user {user_id} role={user.role}")
    else:
        # Create new user
        user = User(
            id=user_id,
            email=email,
            name=phone,
            role=desired_role,
            last_login=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"Phone register: new user {user_id} role={desired_role}")

    # Issue JWT token
    try:
        expires_minutes = int(getattr(settings, "jwt_expire_minutes", 1440))
    except (TypeError, ValueError):
        expires_minutes = 1440  # 24 hours default

    claims = {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
    }
    if user.last_login:
        claims["last_login"] = user.last_login.isoformat()

    token = create_access_token(claims, expires_minutes=expires_minutes)

    return PhoneLoginResponse(
        token=token,
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name or phone,
            "role": user.role,
        },
    )