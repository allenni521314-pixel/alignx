"""Deprecated phone authentication router."""

from core.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/auth/phone", tags=["phone-authentication"])


class PhoneLoginRequest(BaseModel):
    phone: str
    password: str
    display_name: str = ""


class PhoneLoginResponse(BaseModel):
    token: str
    user: dict


@router.post("/login", response_model=PhoneLoginResponse)
async def phone_login(payload: PhoneLoginRequest, db: AsyncSession = Depends(get_db)):
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="手机号固定密码登录已关闭，请使用邮箱验证码登录")
