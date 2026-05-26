"""Email verification-code authentication for beta users."""

import hashlib
import logging
import re
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional

from core.auth import create_access_token
from core.config import settings
from core.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from models.auth import User
from models.email_verification_codes import EmailVerificationCode
from pydantic import BaseModel
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth/email", tags=["email-authentication"])

EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
CODE_TTL_MINUTES = 10
RESEND_COOLDOWN_SECONDS = 60
MAX_VERIFY_ATTEMPTS = 5


class EmailCodeRequest(BaseModel):
    email: str
    display_name: str = ""


class EmailCodeResponse(BaseModel):
    message: str
    expires_in: int
    delivery: str
    debug_code: Optional[str] = None


class EmailLoginRequest(BaseModel):
    email: str
    code: str
    display_name: str = ""


class EmailLoginResponse(BaseModel):
    token: str
    user: dict


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized or not EMAIL_RE.match(normalized):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入正确的邮箱地址")
    return normalized


def _hash_code(email: str, code: str) -> str:
    secret = settings.jwt_secret_key or "alignx-local-secret"
    raw = f"{email}:{code}:{secret}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _email_user_id(email: str) -> str:
    return f"email_{hashlib.sha256(email.encode('utf-8')).hexdigest()[:20]}"


def _super_admin_emails() -> set[str]:
    values = set()
    admin_email = getattr(settings, "admin_user_email", "")
    if admin_email:
        values.add(str(admin_email).strip().lower())
    raw = getattr(settings, "super_admin_emails", "")
    if raw:
        values.update(item.strip().lower() for item in str(raw).split(",") if item.strip())
    return values


def _email_debug_enabled() -> bool:
    raw = getattr(settings, "email_code_debug", "")
    return str(raw).lower() in {"1", "true", "yes", "on"}


def _smtp_port() -> int:
    try:
        return int(getattr(settings, "smtp_port", "587"))
    except (TypeError, ValueError):
        return 587


def _send_email_code(email: str, code: str) -> str:
    smtp_host = getattr(settings, "smtp_host", "")
    smtp_user = getattr(settings, "smtp_username", "")
    smtp_password = getattr(settings, "smtp_password", "")
    from_email = getattr(settings, "smtp_from_email", "") or smtp_user
    from_name = getattr(settings, "smtp_from_name", "AlignX")

    if not smtp_host or not from_email:
        if _email_debug_enabled():
            return "debug"
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="邮件验证码服务未配置")

    message = EmailMessage()
    message["Subject"] = "AlignX 登录验证码"
    message["From"] = f"{from_name} <{from_email}>"
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                "你的 AlignX 登录验证码：",
                "",
                code,
                "",
                f"验证码 {CODE_TTL_MINUTES} 分钟内有效。若非本人操作，请忽略本邮件。",
            ]
        )
    )

    port = _smtp_port()
    use_ssl = str(getattr(settings, "smtp_use_ssl", "")).lower() in {"1", "true", "yes", "on"} or port == 465
    use_tls = str(getattr(settings, "smtp_use_tls", "true")).lower() not in {"0", "false", "no", "off"}

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, port, timeout=15) as server:
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(smtp_host, port, timeout=15) as server:
                if use_tls:
                    server.starttls()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.send_message(message)
    except Exception as exc:
        logger.exception("Failed to send login code email")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="验证码邮件发送失败，请稍后重试") from exc

    return "email"


@router.post("/send-code", response_model=EmailCodeResponse)
async def send_email_code(payload: EmailCodeRequest, db: AsyncSession = Depends(get_db)):
    email = _normalize_email(payload.email)
    now = datetime.now(timezone.utc)

    await db.execute(delete(EmailVerificationCode).where(EmailVerificationCode.expires_at < now))

    latest_result = await db.execute(
        select(EmailVerificationCode)
        .where(EmailVerificationCode.email == email, EmailVerificationCode.purpose == "login")
        .order_by(desc(EmailVerificationCode.created_at))
    )
    latest = latest_result.scalars().first()
    if latest and latest.created_at and (now - latest.created_at).total_seconds() < RESEND_COOLDOWN_SECONDS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="验证码发送过快，请稍后再试")

    code = f"{secrets.randbelow(1_000_000):06d}"
    delivery = _send_email_code(email, code)

    db.add(
        EmailVerificationCode(
            email=email,
            code_hash=_hash_code(email, code),
            purpose="login",
            attempts=0,
            created_at=now,
            expires_at=now + timedelta(minutes=CODE_TTL_MINUTES),
        )
    )
    await db.commit()

    return EmailCodeResponse(
        message="验证码已发送",
        expires_in=CODE_TTL_MINUTES * 60,
        delivery=delivery,
        debug_code=code if delivery == "debug" else None,
    )


@router.post("/login", response_model=EmailLoginResponse)
async def email_login(payload: EmailLoginRequest, db: AsyncSession = Depends(get_db)):
    email = _normalize_email(payload.email)
    code = payload.code.strip()
    display_name = payload.display_name.strip()

    if not re.fullmatch(r"\d{6}", code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入6位邮箱验证码")

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == "login",
            EmailVerificationCode.consumed_at.is_(None),
            EmailVerificationCode.expires_at >= now,
        )
        .order_by(desc(EmailVerificationCode.created_at))
    )
    record = result.scalars().first()

    if not record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="验证码不存在或已过期")

    if record.attempts >= MAX_VERIFY_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="验证码错误次数过多，请重新获取")

    if record.code_hash != _hash_code(email, code):
        record.attempts += 1
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="验证码错误")

    record.consumed_at = now

    user_id = _email_user_id(email)
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        existing_email_result = await db.execute(select(User).where(User.email == email))
        user = existing_email_result.scalar_one_or_none()

    role = "super_admin" if email in _super_admin_emails() else "user"
    if user:
        user.email = email
        user.last_login = now
        if display_name:
            user.name = display_name
        if role == "super_admin" and user.role != "super_admin":
            user.role = "super_admin"
    else:
        user = User(
            id=user_id,
            email=email,
            name=display_name or email.split("@", 1)[0],
            role=role,
            last_login=now,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    try:
        expires_minutes = int(getattr(settings, "jwt_expire_minutes", 1440))
    except (TypeError, ValueError):
        expires_minutes = 1440

    claims = {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
    }
    if user.last_login:
        claims["last_login"] = user.last_login.isoformat()

    token = create_access_token(claims, expires_minutes=expires_minutes)
    return EmailLoginResponse(
        token=token,
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name or email,
            "role": user.role,
        },
    )
