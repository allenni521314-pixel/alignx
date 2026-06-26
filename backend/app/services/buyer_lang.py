from __future__ import annotations
"""Buyer language translation service."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.buyer_lang import BUYER_LANG_SYSTEM, build_buyer_lang_prompt
from app.services.ai_calls import complete_json_with_log


async def translate_seller_to_buyer(input_data: dict, db: AsyncSession, user_id: str) -> dict:
    """Translate seller claims to buyer language using AI."""
    prompt = build_buyer_lang_prompt(input_data)
    return await complete_json_with_log(
        db=db,
        user_id=user_id,
        module_name="buyer_lang_translate",
        prompt_version="buyer_lang_translate:v1",
        prompt=prompt,
        system=BUYER_LANG_SYSTEM,
        input_payload={"input_data": input_data},
        max_tokens=4096,
    )
