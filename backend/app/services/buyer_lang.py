from __future__ import annotations
"""Buyer language translation service."""

from app.core.ai import AI
from app.core.buyer_lang import BUYER_LANG_SYSTEM, build_buyer_lang_prompt


async def translate_seller_to_buyer(input_data: dict) -> dict:
    """Translate seller claims to buyer language using AI."""
    ai = AI()
    prompt = build_buyer_lang_prompt(input_data)
    result = await ai.complete_json(prompt=prompt, system=BUYER_LANG_SYSTEM, max_tokens=4096)
    return result
