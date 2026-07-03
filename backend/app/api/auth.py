from __future__ import annotations
"""Login & auth API."""

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings
from app.core.auth import (
    send_code,
    verify_code,
    get_or_create_user,
    create_session,
    validate_session,
    is_smtp_configured,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class SendCodeRequest(BaseModel):
    email: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str
    store_name: str = ""


def _is_local_request(request: Request) -> bool:
    client_host = request.client.host if request.client else ""
    return client_host in {"127.0.0.1", "::1", "localhost"}


async def get_current_user(authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    """Extract user_id from Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    sess = validate_session(token)
    if not sess:
        return None
    return {"user_id": sess["user_id"], "email": sess["email"]}


@router.post("/send-code")
async def send(req: SendCodeRequest, request: Request, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    is_development = settings.environment.lower() == "development"
    allow_debug_code = is_development and _is_local_request(request)

    if not is_smtp_configured() and not allow_debug_code:
        raise HTTPException(status_code=503, detail="邮件服务未配置")

    code = await send_code(req.email, db)
    if code is None:
        raise HTTPException(status_code=429, detail="发送过于频繁，请稍后重试")
    response = {"success": True, "message": "验证码已发送"}
    if allow_debug_code:
        response["debug_code"] = code
    return response


@router.post("/verify-code")
async def verify(req: VerifyCodeRequest, db: AsyncSession = Depends(get_db)):
    ok = await verify_code(req.email, req.code, db)
    if not ok:
        raise HTTPException(status_code=401, detail="验证码错误或已过期")

    user = await get_or_create_user(req.email, req.store_name, db)
    token = create_session(user.id, user.email, user.role)

    return {
        "success": True,
        "message": "登录成功",
        "token": token,
        "user_id": user.id,
        "email": user.email,
        "store_name": user.name,
    }
