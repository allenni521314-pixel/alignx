from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OperationAuditLog
from app.services.access import require_user_id


async def record_audit_log(
    *,
    db: AsyncSession,
    user_id: str | None,
    module_name: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    asin: str | None = None,
    store_id: str | None = None,
    source_type: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> OperationAuditLog:
    uid = require_user_id(user_id)
    log = OperationAuditLog(
        user_id=uid,
        store_id=store_id,
        asin=asin,
        module_name=module_name,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        source_type=source_type,
        before_json=before,
        after_json=after,
    )
    db.add(log)
    await db.flush()
    return log
