from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

ADMIN_USER_ID = "__admin__"


def require_user_id(user_id: str | None) -> str:
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id


def is_admin_user(user_id: str | None) -> bool:
    return user_id == ADMIN_USER_ID


def require_admin_user(user_id: str | None) -> str:
    uid = require_user_id(user_id)
    if not is_admin_user(uid):
        raise HTTPException(status_code=403, detail="Admin only")
    return uid


def user_scoped(query: Select, model, user_id: str) -> Select:
    if is_admin_user(user_id):
        return query
    return query.where(model.user_id == user_id)


async def ensure_asin_record(
    db: AsyncSession,
    *,
    user_id: str,
    asin: str,
    marketplace: str = "amazon.com",
    store_id: str | None = None,
    product_title: str | None = None,
):
    from app.models import Asin

    q = select(Asin).where(
        Asin.user_id == user_id,
        Asin.asin == asin,
        Asin.marketplace == marketplace,
    )
    if store_id:
        q = q.where(Asin.store_id == store_id)
    record = (await db.execute(q)).scalar_one_or_none()
    if not record:
        record = Asin(
            user_id=user_id,
            store_id=store_id,
            asin=asin,
            marketplace=marketplace,
            product_title=product_title,
        )
        db.add(record)
        await db.flush()
    elif product_title and not record.product_title:
        record.product_title = product_title
        await db.flush()
    return record


@dataclass
class TenantScope:
    db: AsyncSession
    user_id: str

    @classmethod
    def require(cls, db: AsyncSession, user_id: str | None) -> "TenantScope":
        return cls(db=db, user_id=require_user_id(user_id))

    def apply(self, query: Select, model) -> Select:
        return user_scoped(query, model, self.user_id)

    def select(self, model) -> Select:
        return self.apply(select(model), model)

    async def validation_task(self, task_id: str):
        from app.models import ValidationTask

        q = self.apply(select(ValidationTask), ValidationTask).where(ValidationTask.id == task_id)
        return (await self.db.execute(q)).scalar_one_or_none()

    async def asin_record(self, asin: str, marketplace: str, store_id: str | None = None):
        from app.models import Asin

        q = self.apply(select(Asin), Asin).where(
            Asin.asin == asin,
            Asin.marketplace == marketplace,
        )
        if store_id:
            q = q.where(Asin.store_id == store_id)
        return (await self.db.execute(q)).scalar_one_or_none()

    async def latest_listing_snapshot(self, asin: str, marketplace: str):
        from app.models import CaptureJob, ListingSnapshot

        q = (
            select(ListingSnapshot, CaptureJob)
            .join(CaptureJob, ListingSnapshot.capture_job_id == CaptureJob.id)
            .where(
                ListingSnapshot.asin == asin,
                ListingSnapshot.marketplace == marketplace,
            )
            .order_by(desc(ListingSnapshot.created_at))
            .limit(1)
        )
        if not is_admin_user(self.user_id):
            q = q.where(CaptureJob.user_id == self.user_id)
        row = (await self.db.execute(q)).first()
        if not row:
            return None, None
        return row[0], row[1]
