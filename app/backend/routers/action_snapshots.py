import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user, get_user_scope_ids
from schemas.auth import UserResponse
from services.action_snapshots import ActionSnapshotsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/action-snapshots", tags=["action-snapshots"])


class SnapshotCreateRequest(BaseModel):
    module_key: str
    module_name: str
    action_key: str
    action_name: str
    product_id: Optional[int] = None
    asin: str = ""
    title: str = ""
    input_snapshot: Any = None
    output_snapshot: Any = None
    data_source: str = ""
    confidence: str = ""
    ai_called: bool = False
    source_record_table: str = ""
    source_record_id: Optional[int] = None


def _json_dump(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _json_load(value: str | None):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _row_to_dict(row):
    return {
        "id": row.id,
        "module_key": row.module_key,
        "module_name": row.module_name,
        "action_key": row.action_key,
        "action_name": row.action_name,
        "product_id": row.product_id,
        "asin": row.asin or "",
        "title": row.title or "",
        "input_snapshot": _json_load(row.input_snapshot),
        "output_snapshot": _json_load(row.output_snapshot),
        "data_source": row.data_source or "",
        "confidence": row.confidence or "",
        "ai_called": bool(row.ai_called),
        "source_record_table": row.source_record_table or "",
        "source_record_id": row.source_record_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("")
async def create_snapshot(
    request: SnapshotCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an immutable action snapshot. Viewing snapshots never triggers AI."""
    svc = ActionSnapshotsService(db)
    row = await svc.create(
        {
            "module_key": request.module_key[:80],
            "module_name": request.module_name[:120],
            "action_key": request.action_key[:80],
            "action_name": request.action_name[:120],
            "product_id": request.product_id,
            "asin": (request.asin or "")[:80],
            "title": (request.title or "")[:500],
            "input_snapshot": _json_dump(request.input_snapshot),
            "output_snapshot": _json_dump(request.output_snapshot),
            "data_source": (request.data_source or "")[:120],
            "confidence": (request.confidence or "")[:40],
            "ai_called": request.ai_called,
            "source_record_table": (request.source_record_table or "")[:120],
            "source_record_id": request.source_record_id,
            "created_at": datetime.now(timezone.utc),
        },
        user_id=str(current_user.id),
    )
    return {"success": True, "id": row.id}


@router.get("")
async def list_snapshots(
    module_key: str = "",
    action_key: str = "",
    product_id: Optional[int] = None,
    asin: str = "",
    skip: int = 0,
    limit: int = 50,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ActionSnapshotsService(db)
    scope_user_ids = await get_user_scope_ids(current_user, db)
    rows, total = await svc.list(
        user_id=scope_user_ids,
        module_key=module_key,
        action_key=action_key,
        product_id=product_id,
        asin=asin,
        skip=skip,
        limit=min(limit, 200),
    )
    return {"items": [_row_to_dict(row) for row in rows], "total": total}


@router.get("/{snapshot_id}")
async def get_snapshot(
    snapshot_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ActionSnapshotsService(db)
    scope_user_ids = await get_user_scope_ids(current_user, db)
    row = await svc.get(snapshot_id, user_id=scope_user_ids)
    if not row:
        raise HTTPException(status_code=404, detail="快照不存在")
    return _row_to_dict(row)
