from __future__ import annotations
"""Login & verification code management with SQLite persistence."""

import random
import string
import time
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models import User, VerificationCode


def generate_code_sync() -> str:
    return "".join(random.choices(string.digits, k=6))


async def send_code(email: str, db: AsyncSession) -> str | None:
    """Generate code, store in DB, return code."""
    # Rate limit: check recent codes
    now = time.time()
    q = select(VerificationCode).where(
        VerificationCode.email == email,
        VerificationCode.created_at > now - 60
    )
    result = await db.execute(q)
    recent = result.scalars().all()
    if len(recent) >= 3:
        return None

    # Delete old codes for this email
    await db.execute(delete(VerificationCode).where(VerificationCode.email == email))

    code = generate_code_sync()
    vc = VerificationCode(email=email, code=code, expires_at=now + 300)
    db.add(vc)
    await db.flush()
    print(f"[AUTH] Code for {email}: {code}")
    return code


async def verify_code(email: str, code: str, db: AsyncSession) -> bool:
    """Verify code from DB."""
    q = select(VerificationCode).where(
        VerificationCode.email == email,
        VerificationCode.code == code
    )
    result = await db.execute(q)
    vc = result.scalars().first()
    if not vc or time.time() > vc.expires_at:
        return False
    await db.execute(delete(VerificationCode).where(VerificationCode.id == vc.id))
    await db.flush()
    return True


# ── Session management (in-memory, per-process lifetime) ──

_sessions: dict[str, dict] = {}

def create_session(user_id: str, email: str) -> str:
    token = uuid.uuid4().hex
    _sessions[token] = {"user_id": user_id, "email": email, "expires_at": time.time() + 86400}
    return token

def validate_session(token: str) -> dict | None:
    sess = _sessions.get(token)
    if not sess or time.time() > sess["expires_at"]:
        _sessions.pop(token, None)
        return None
    return sess


# ── User management ──

async def get_or_create_user(email: str, store_name: str, db: AsyncSession) -> User:
    """Get existing user or create new one."""
    q = select(User).where(User.email == email)
    result = await db.execute(q)
    user = result.scalars().first()
    if not user:
        # Super admin: allenni521314@gmail.com gets admin role
        is_admin = email == "allenni521314@gmail.com"
        user = User(
            id=uuid.uuid4().hex[:32],
            email=email,
            name=store_name or email,
            role="admin" if is_admin else "seller",
        )
        db.add(user)
        await db.flush()
    return user


def create_session(user_id: str, email: str, role: str = "seller") -> str:
    """Create a session token."""
    token = uuid.uuid4().hex
    _sessions[token] = {"user_id": user_id, "email": email, "role": role, "expires_at": time.time() + 86400}
    return token


def validate_session(token: str) -> dict | None:
    """Validate session token, return session data or None."""
    sess = _sessions.get(token)
    if not sess or time.time() > sess["expires_at"]:
        _sessions.pop(token, None)
        return None
    return sess

