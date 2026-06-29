from __future__ import annotations
"""Help Assistant API — customer support only, separated from operation agents."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.database import get_db
from app.schemas import HelpChatRequest, HelpChatResponse, HelpFaqResponse, HelpTicketCreate, HelpTicketResponse
from app.services.help_assistant import chat, create_ticket, list_faq, list_tickets

router = APIRouter(prefix="/api/v1/help", tags=["help"])


@router.post("/chat", response_model=HelpChatResponse)
async def help_chat(req: HelpChatRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    result = await chat(req, db, user_id=user_id)
    await db.commit()
    return HelpChatResponse(
        answer=result.answer,
        source=result.source,
        should_create_ticket=result.should_create_ticket,
        suggested_issue_type=result.suggested_issue_type,
        message_id=result.message_id,
    )


@router.post("/tickets", response_model=HelpTicketResponse)
async def create_help_ticket(req: HelpTicketCreate, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    ticket = await create_ticket(req, db, user_id=user_id)
    await db.commit()
    return ticket


@router.get("/tickets", response_model=list[HelpTicketResponse])
async def get_help_tickets(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return await list_tickets(db, user_id=user_id)


@router.get("/faq", response_model=list[HelpFaqResponse])
async def get_help_faq(language: str = "zh", db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    items = await list_faq("en" if language == "en" else "zh", db)
    await db.commit()
    return items


@router.post("/upload-screenshot")
async def upload_screenshot():
    return {"status": "pending", "message": "待接入文件存储"}
