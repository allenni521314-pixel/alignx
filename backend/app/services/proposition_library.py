from __future__ import annotations

"""7 x 7 proposition library service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.proposition_engine import PROPOSITION_CATEGORIES, PROPOSITIONS, seed_propositions
from app.models import Proposition, PropositionCategory
from app.schemas import PropositionResponse


async def ensure_proposition_library(db: AsyncSession) -> dict:
    return await seed_propositions(db)


async def list_proposition_categories(db: AsyncSession) -> list[dict]:
    q = select(PropositionCategory).order_by(PropositionCategory.category_code)
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "category_code": row.category_code,
            "category_name": row.category_name,
            "description": row.description,
            "archived": row.archived,
        }
        for row in rows
    ]


async def list_propositions(db: AsyncSession) -> list[PropositionResponse]:
    q = select(Proposition).order_by(Proposition.category_code, Proposition.proposition_code)
    rows = (await db.execute(q)).scalars().all()
    return [PropositionResponse.model_validate(row, from_attributes=True) for row in rows]


async def proposition_library_status(db: AsyncSession) -> dict:
    category_count = len((await db.execute(select(PropositionCategory))).scalars().all())
    proposition_count = len((await db.execute(select(Proposition))).scalars().all())
    return {
        "expected_categories": len(PROPOSITION_CATEGORIES),
        "expected_propositions": len(PROPOSITIONS),
        "category_count": category_count,
        "proposition_count": proposition_count,
        "complete": category_count >= len(PROPOSITION_CATEGORIES) and proposition_count >= len(PROPOSITIONS),
    }
