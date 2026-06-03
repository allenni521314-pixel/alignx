import json
from typing import Any, Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.opc_os_executions import OPCOSExecutionRecord


def _dump(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value or {}, ensure_ascii=False)


def _load(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        return {}


def _object_id(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if not isinstance(value, dict):
        return ""
    for key in (
        "opportunity_id",
        "uncertainty_id",
        "proof_plan_id",
        "execution_id",
        "evidence_id",
        "capital_decision_id",
        "id",
    ):
        if value.get(key):
            return str(value[key])
    return ""


def _opportunity_id(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if not isinstance(value, dict):
        return ""
    return str(value.get("opportunity_id") or "")


def _status(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if not isinstance(value, dict):
        return ""
    return str(value.get("status") or value.get("suggested_action") or "")


class OPCOSPersistenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_object(
        self,
        *,
        user_id: str,
        object_type: str,
        payload: Any,
        opportunity_id: str = "",
        source_module: str = "",
        source_record_id: int | None = None,
        asin: str = "",
        title: str = "",
    ) -> OPCOSExecutionRecord:
        obj = OPCOSExecutionRecord(
            user_id=user_id,
            object_type=object_type,
            object_id=_object_id(payload),
            opportunity_id=opportunity_id or _opportunity_id(payload),
            source_module=source_module,
            source_record_id=source_record_id,
            asin=asin,
            title=title,
            status=_status(payload),
            payload=_dump(payload),
        )
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def save_execution_bundle(
        self,
        *,
        user_id: str,
        bundle: dict[str, Any],
        source_module: str = "",
        source_record_id: int | None = None,
        asin: str = "",
        title: str = "",
    ) -> list[OPCOSExecutionRecord]:
        opportunity = bundle.get("opportunity") if isinstance(bundle.get("opportunity"), dict) else {}
        opportunity_id = str(opportunity.get("opportunity_id") or "")
        rows: list[OPCOSExecutionRecord] = []
        for object_type, payload in (
            ("opportunity", bundle.get("opportunity")),
            ("proof_plan", bundle.get("proof_plan")),
            ("experiment_execution", bundle.get("experiment_execution")),
            ("evidence", bundle.get("evidence")),
            ("capital_decision", bundle.get("capital_decision")),
            ("knowledge_evolution", bundle.get("knowledge_evolution")),
        ):
            if payload:
                rows.append(
                    await self.save_object(
                        user_id=user_id,
                        object_type=object_type,
                        payload=payload,
                        opportunity_id=opportunity_id,
                        source_module=source_module,
                        source_record_id=source_record_id,
                        asin=asin,
                        title=title,
                    )
                )
        for item in bundle.get("uncertainty_queue") or []:
            rows.append(
                await self.save_object(
                    user_id=user_id,
                    object_type="uncertainty",
                    payload=item,
                    opportunity_id=opportunity_id,
                    source_module=source_module,
                    source_record_id=source_record_id,
                    asin=asin,
                    title=title,
                )
            )
        return rows

    async def list_objects(
        self,
        *,
        user_id: str | Sequence[str],
        object_type: str = "",
        opportunity_id: str = "",
        source_module: str = "",
        asin: str = "",
        skip: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        query = select(OPCOSExecutionRecord)
        count_query = select(func.count()).select_from(OPCOSExecutionRecord)
        filters = []
        if isinstance(user_id, (list, tuple)):
            filters.append(OPCOSExecutionRecord.user_id.in_(list(user_id)))
        else:
            filters.append(OPCOSExecutionRecord.user_id == user_id)
        if object_type:
            filters.append(OPCOSExecutionRecord.object_type == object_type)
        if opportunity_id:
            filters.append(OPCOSExecutionRecord.opportunity_id == opportunity_id)
        if source_module:
            filters.append(OPCOSExecutionRecord.source_module == source_module)
        if asin:
            filters.append(OPCOSExecutionRecord.asin == asin)
        for item in filters:
            query = query.where(item)
            count_query = count_query.where(item)
        total_res = await self.db.execute(count_query)
        rows_res = await self.db.execute(query.order_by(desc(OPCOSExecutionRecord.id)).offset(skip).limit(limit))
        rows = list(rows_res.scalars().all())
        return {
            "items": [self.to_dict(row) for row in rows],
            "total": int(total_res.scalar() or 0),
            "skip": skip,
            "limit": limit,
        }

    @staticmethod
    def to_dict(row: OPCOSExecutionRecord) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "object_type": row.object_type,
            "object_id": row.object_id,
            "opportunity_id": row.opportunity_id,
            "source_module": row.source_module,
            "source_record_id": row.source_record_id,
            "asin": row.asin,
            "title": row.title,
            "status": row.status,
            "payload": _load(row.payload),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }