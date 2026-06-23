from __future__ import annotations
"""Buyer language translation service."""

from app.core.ai import AI
from app.core.buyer_lang import BUYER_LANG_SYSTEM, build_buyer_lang_prompt


async def translate_buyer_language(input_data: dict) -> dict:
    """Run buyer language translation pipeline."""
    ai = AI()
    prompt = build_buyer_lang_prompt(input_data)
    result = await ai.complete_json(prompt=prompt, system=BUYER_LANG_SYSTEM)
    return result
