from __future__ import annotations
"""Login & verification code management with SQLite persistence."""

import random
import string
import time
import uuid
import base64
import hashlib
import hmac
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.config import get_settings
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


# ── Session management ──

SESSION_TTL_SECONDS = 86400 * 30


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _session_signature(payload: str) -> str:
    secret = get_settings().auth_secret_key.encode("utf-8")
    return _b64url_encode(hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest())


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
    """Create a signed session token that survives process restarts."""
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "expires_at": time.time() + SESSION_TTL_SECONDS,
    }
    payload_raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_raw)
    return f"{payload_b64}.{_session_signature(payload_b64)}"


def validate_session(token: str) -> dict | None:
    """Validate signed session token, return session data or None."""
    try:
        payload_b64, signature = token.split(".", 1)
        expected_signature = _session_signature(payload_b64)
        if not hmac.compare_digest(signature, expected_signature):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if time.time() > float(payload.get("expires_at", 0)):
            return None
        return payload
    except Exception:
        return None
