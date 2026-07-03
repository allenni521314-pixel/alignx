from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from models.prelaunch_test_results import Prelaunch_test_results


class Prelaunch_test_resultsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict, user_id: str) -> Prelaunch_test_results:
        record = Prelaunch_test_results(**data, user_id=user_id)
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def get_by_id(self, record_id: int, user_id: str | list[str]):
        user_filter = (
            Prelaunch_test_results.user_id.in_(user_id)
            if isinstance(user_id, list)
            else Prelaunch_test_results.user_id == user_id
        )
        q = select(Prelaunch_test_results).where(
            Prelaunch_test_results.id == record_id,
            user_filter,
        )
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: str | list[str], skip: int = 0, limit: int = 50, search: str = ""):
        base = [
            Prelaunch_test_results.user_id.in_(user_id)
            if isinstance(user_id, list)
            else Prelaunch_test_results.user_id == user_id
        ]
        if search.strip():
            base.append(Prelaunch_test_results.title.ilike(f"%{search.strip()}%"))

        count_q = select(func.count(Prelaunch_test_results.id)).where(*base)
        count_result = await self.db.execute(count_q)
        total = count_result.scalar() or 0

        items_q = (
            select(Prelaunch_test_results)
            .where(*base)
            .order_by(Prelaunch_test_results.id.desc())
            .offset(skip)
            .limit(limit)
        )
        items_result = await self.db.execute(items_q)
        rows = items_result.scalars().all()
        return rows, total

    async def delete(self, record_id: int, user_id: str) -> bool:
        q = delete(Prelaunch_test_results).where(
            Prelaunch_test_results.id == record_id,
            Prelaunch_test_results.user_id == user_id,
        )
        result = await self.db.execute(q)
        await self.db.commit()
        return result.rowcount > 0
