import json
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.asin_business_profile import (
    AiDecisionTrace,
    AsinBusinessProfile,
    AsinDailySnapshot,
    AsinExecutionLog,
    AsinKeywordProfile,
    ListingVersion,
    MetricDictionary,
    ReportUpload,
    ValidationTask,
)
from models.listing_diagnoses import Listing_diagnoses
from services.listing_diagnoses import Listing_diagnosesService


DEMO_SOURCE = "demo_listing_diagnosis_history"
DEFAULT_STORE_ID = "default"
COMPLETE_APLUS_MIN_IMAGES = 8


METRIC_DEFINITIONS = [
    ("CTR", "CTR", "Clicks / Impressions", "Click-through rate"),
    ("CVR", "CVR", "Orders / Sessions", "Conversion rate"),
    ("ACOS", "ACOS", "Ad Spend / Ad Sales", "Advertising cost of sales"),
    ("TACOS", "TACOS", "Ad Spend / Total Sales", "Total advertising cost of sales"),
    ("UNIT_SESSION_PERCENTAGE", "Unit Session Percentage", "Units Ordered / Sessions", "Unit session percentage"),
    ("ORGANIC_SALES_RATIO", "Organic Sales Ratio", "Organic Sales / Total Sales", "Organic sales ratio"),
    ("ADS_SALES_RATIO", "Ads Sales Ratio", "Ads Sales / Total Sales", "Ads sales ratio"),
]


def normalize_asin(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text if len(text) == 10 and text.isalnum() else ""


def normalize_marketplace(value: Any) -> str:
    return (str(value or "US").strip().upper() or "US")


def parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def parse_int(value: Any) -> Optional[int]:
    parsed = parse_float(value)
    return int(parsed) if parsed is not None else None


def safe_json_loads(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def json_dumps(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def score_average(values: Iterable[Any]) -> Optional[float]:
    nums = [float(v) for v in values if isinstance(v, (int, float)) and float(v) > 0]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 1)


class AsinBusinessProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ensure_metric_dictionary(self) -> None:
        for metric_key, metric_name, formula, description in METRIC_DEFINITIONS:
            result = await self.db.execute(select(MetricDictionary).where(MetricDictionary.metric_key == metric_key))
            existing = result.scalar_one_or_none()
            if existing:
                existing.metric_name = metric_name
                existing.formula = formula
                existing.description = description
            else:
                self.db.add(
                    MetricDictionary(
                        metric_key=metric_key,
                        metric_name=metric_name,
                        formula=formula,
                        description=description,
                    )
                )
        await self.db.commit()

    async def list_metrics(self) -> list[MetricDictionary]:
        await self.ensure_metric_dictionary()
        result = await self.db.execute(select(MetricDictionary).order_by(MetricDictionary.id.asc()))
        return list(result.scalars().all())

    async def get_profile(
        self,
        *,
        seller_id: str,
        store_id: str,
        marketplace: str,
        asin: str,
    ) -> Optional[AsinBusinessProfile]:
        result = await self.db.execute(
            select(AsinBusinessProfile).where(
                AsinBusinessProfile.seller_id == seller_id,
                AsinBusinessProfile.store_id == store_id,
                AsinBusinessProfile.marketplace == normalize_marketplace(marketplace),
                AsinBusinessProfile.asin == normalize_asin(asin),
            )
        )
        return result.scalar_one_or_none()

    async def list_profiles(
        self,
        *,
        seller_id: str,
        store_id: Optional[str] = None,
        marketplace: Optional[str] = None,
        is_demo: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        query = select(AsinBusinessProfile).where(AsinBusinessProfile.seller_id == seller_id)
        count_query = select(func.count(AsinBusinessProfile.id)).where(AsinBusinessProfile.seller_id == seller_id)
        if store_id:
            query = query.where(AsinBusinessProfile.store_id == store_id)
            count_query = count_query.where(AsinBusinessProfile.store_id == store_id)
        if marketplace:
            normalized_marketplace = normalize_marketplace(marketplace)
            query = query.where(AsinBusinessProfile.marketplace == normalized_marketplace)
            count_query = count_query.where(AsinBusinessProfile.marketplace == normalized_marketplace)
        if is_demo is not None:
            query = query.where(AsinBusinessProfile.is_demo == is_demo)
            count_query = count_query.where(AsinBusinessProfile.is_demo == is_demo)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        result = await self.db.execute(query.order_by(AsinBusinessProfile.updated_at.desc()).offset(skip).limit(limit))
        return {"items": list(result.scalars().all()), "total": total, "skip": skip, "limit": limit}

    async def get_module_view(
        self,
        *,
        seller_id: str,
        view_type: str,
        asin: Optional[str] = None,
        store_id: str = DEFAULT_STORE_ID,
        marketplace: str = "US",
    ) -> dict:
        profile = await self._get_view_profile(
            seller_id=seller_id,
            store_id=store_id,
            marketplace=marketplace,
            asin=asin,
        )
        if not profile:
            return {
                "view_type": view_type,
                "seller_id": seller_id,
                "store_id": store_id,
                "marketplace": normalize_marketplace(marketplace),
                "asin": normalize_asin(asin) if asin else "",
                "summary": self._empty_summary(),
                "metrics": {},
                "records": [],
            }

        view = {
            "view_type": view_type,
            "seller_id": seller_id,
            "store_id": profile.store_id,
            "marketplace": profile.marketplace,
            "asin": profile.asin,
            "summary": self._profile_summary(profile),
            "metrics": self._profile_metrics(profile),
            "records": [],
        }
        if view_type == "yesterday-report":
            view["records"] = await self._latest_snapshots(profile)
        elif view_type == "today-decision":
            view["records"] = await self._validation_records(profile)
        elif view_type == "listing-diagnosis":
            view["records"] = await self._decision_records(profile, "Listing Diagnosis")
        elif view_type == "traffic-strategy":
            view["records"] = await self._decision_records(profile, "Traffic Strategy")
        elif view_type == "execution-records":
            view["records"] = await self._execution_records(profile)
        elif view_type == "effect-validation":
            view["records"] = await self._validation_records(profile)
        return view

    async def _get_view_profile(
        self,
        *,
        seller_id: str,
        store_id: str,
        marketplace: str,
        asin: Optional[str],
    ) -> Optional[AsinBusinessProfile]:
        if asin:
            return await self.get_profile(
                seller_id=seller_id,
                store_id=store_id,
                marketplace=marketplace,
                asin=asin,
            )
        result = await self.db.execute(
            select(AsinBusinessProfile)
            .where(
                AsinBusinessProfile.seller_id == seller_id,
                AsinBusinessProfile.store_id == store_id,
                AsinBusinessProfile.marketplace == normalize_marketplace(marketplace),
            )
            .order_by(AsinBusinessProfile.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _empty_summary() -> dict:
        return {
            "conclusion": "暂无",
            "current_primary_problem": "暂无",
            "priority_actions": "暂无",
            "recommended_action": "暂无",
            "overall_score": None,
            "confidence_score": None,
        }

    def _profile_summary(self, profile: AsinBusinessProfile) -> dict:
        return {
            "product_name": profile.product_name or "暂无",
            "lifecycle_stage": profile.lifecycle_stage or "未设置",
            "conclusion": profile.next_recommended_action or profile.priority_actions or "暂无",
            "current_primary_problem": profile.current_primary_problem or "暂无",
            "priority_actions": profile.priority_actions or "暂无",
            "recommended_action": profile.next_recommended_action or "暂无",
            "overall_score": profile.overall_score,
            "confidence_score": profile.confidence_score,
        }

    @staticmethod
    def _profile_metrics(profile: AsinBusinessProfile) -> dict:
        return {
            "traffic_score": profile.traffic_score,
            "ctr_score": profile.ctr_score,
            "cvr_score": profile.cvr_score,
            "ads_score": profile.ads_score,
            "profit_score": profile.profit_score,
            "competition_score": profile.competition_score,
            "title_score": profile.title_score,
            "main_image_score": profile.main_image_score,
            "gallery_score": profile.gallery_score,
            "aplus_score": profile.aplus_score,
            "bullet_score": profile.bullet_score,
            "review_score": profile.review_score,
            "price_score": profile.price_score,
            "sessions": profile.sessions,
            "ctr": profile.ctr,
            "cvr": profile.cvr,
            "organic_sales_ratio": profile.organic_sales_ratio,
            "ads_sales_ratio": profile.ads_sales_ratio,
            "acos": profile.acos,
            "tacos": profile.tacos,
            "keyword_count": profile.keyword_count,
        }

    async def _latest_snapshots(self, profile: AsinBusinessProfile) -> list[dict]:
        result = await self.db.execute(
            select(AsinDailySnapshot)
            .where(
                AsinDailySnapshot.seller_id == profile.seller_id,
                AsinDailySnapshot.store_id == profile.store_id,
                AsinDailySnapshot.marketplace == profile.marketplace,
                AsinDailySnapshot.asin == profile.asin,
            )
            .order_by(AsinDailySnapshot.date.desc())
            .limit(30)
        )
        return [
            {
                "date": item.date.isoformat(),
                "sessions": item.sessions,
                "clicks": item.clicks,
                "orders": item.orders,
                "sales": item.sales,
                "ctr": item.ctr,
                "cvr": item.cvr,
                "acos": item.acos,
                "tacos": item.tacos,
                "ad_spend": item.ad_spend,
                "ad_sales": item.ad_sales,
                "organic_sales": item.organic_sales,
                "total_sales": item.total_sales,
                "inventory": item.inventory,
                "buybox_status": item.buybox_status or "暂无",
            }
            for item in result.scalars().all()
        ]

    async def _decision_records(self, profile: AsinBusinessProfile, decision_type: str) -> list[dict]:
        result = await self.db.execute(
            select(AiDecisionTrace)
            .where(
                AiDecisionTrace.seller_id == profile.seller_id,
                AiDecisionTrace.store_id == profile.store_id,
                AiDecisionTrace.marketplace == profile.marketplace,
                AiDecisionTrace.asin == profile.asin,
                AiDecisionTrace.decision_type == decision_type,
            )
            .order_by(AiDecisionTrace.created_at.desc())
            .limit(20)
        )
        return [
            {
                "decision_id": item.decision_id,
                "decision_type": item.decision_type,
                "conclusion": item.conclusion or "暂无",
                "reasoning_summary": item.reasoning_summary or "暂无",
                "confidence_score": item.confidence_score,
                "recommended_action": item.recommended_action or "暂无",
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in result.scalars().all()
        ]

    async def _execution_records(self, profile: AsinBusinessProfile) -> list[dict]:
        result = await self.db.execute(
            select(AsinExecutionLog)
            .where(
                AsinExecutionLog.seller_id == profile.seller_id,
                AsinExecutionLog.store_id == profile.store_id,
                AsinExecutionLog.marketplace == profile.marketplace,
                AsinExecutionLog.asin == profile.asin,
            )
            .order_by(AsinExecutionLog.created_at.desc())
            .limit(50)
        )
        return [
            {
                "execution_id": item.execution_id,
                "validation_id": item.validation_id,
                "action_type": item.action_type,
                "before_value": item.before_value or "暂无",
                "after_value": item.after_value or "暂无",
                "executed_by": item.executed_by or "暂无",
                "executed_at": item.executed_at.isoformat() if item.executed_at else None,
                "note": item.note or "暂无",
            }
            for item in result.scalars().all()
        ]

    async def _validation_records(self, profile: AsinBusinessProfile) -> list[dict]:
        result = await self.db.execute(
            select(ValidationTask)
            .where(
                ValidationTask.seller_id == profile.seller_id,
                ValidationTask.store_id == profile.store_id,
                ValidationTask.marketplace == profile.marketplace,
                ValidationTask.asin == profile.asin,
            )
            .order_by(ValidationTask.created_at.desc())
            .limit(50)
        )
        return [
            {
                "validation_id": item.validation_id,
                "validation_type": item.validation_type,
                "problem": item.problem or "暂无",
                "hypothesis": item.hypothesis or "暂无",
                "action_plan": item.action_plan or "暂无",
                "target_metric": item.target_metric or "暂无",
                "baseline_start_date": item.baseline_start_date.isoformat() if item.baseline_start_date else None,
                "baseline_end_date": item.baseline_end_date.isoformat() if item.baseline_end_date else None,
                "test_start_date": item.test_start_date.isoformat() if item.test_start_date else None,
                "test_end_date": item.test_end_date.isoformat() if item.test_end_date else None,
                "result_start_date": item.result_start_date.isoformat() if item.result_start_date else None,
                "result_end_date": item.result_end_date.isoformat() if item.result_end_date else None,
                "baseline_value": item.baseline_value,
                "target_value": item.target_value,
                "result_value": item.result_value,
                "improvement_rate": item.improvement_rate,
                "confidence_score": item.confidence_score,
                "status": item.status,
            }
            for item in result.scalars().all()
        ]

    async def upsert_profile(self, *, seller_id: str, data: Dict[str, Any]) -> AsinBusinessProfile:
        asin = normalize_asin(data.get("asin"))
        if not asin:
            raise ValueError("asin is required")
        store_id = str(data.get("store_id") or DEFAULT_STORE_ID)
        marketplace = normalize_marketplace(data.get("marketplace"))
        profile = await self.get_profile(seller_id=seller_id, store_id=store_id, marketplace=marketplace, asin=asin)
        if not profile:
            profile = AsinBusinessProfile(
                seller_id=seller_id,
                store_id=store_id,
                marketplace=marketplace,
                asin=asin,
            )
            self.db.add(profile)

        for key, value in data.items():
            if hasattr(profile, key) and key not in {"id", "seller_id"}:
                setattr(profile, key, value)
        profile.asin = asin
        profile.marketplace = marketplace
        profile.store_id = store_id
        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    async def create_report_upload(self, *, seller_id: str, data: Dict[str, Any]) -> ReportUpload:
        report = ReportUpload(
            report_id=f"report_{uuid.uuid4().hex}",
            seller_id=seller_id,
            store_id=str(data.get("store_id") or DEFAULT_STORE_ID),
            marketplace=normalize_marketplace(data.get("marketplace")),
            report_type=data.get("report_type"),
            original_filename=data.get("original_filename"),
            upload_time=datetime.now(timezone.utc),
            parse_status=data.get("parse_status") or "Pending",
            parse_error=data.get("parse_error"),
            date_range_start=data.get("date_range_start"),
            date_range_end=data.get("date_range_end"),
            source_file_url=data.get("source_file_url"),
            data_source=data.get("data_source"),
            is_demo=bool(data.get("is_demo")),
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def upsert_daily_snapshot(self, *, seller_id: str, data: Dict[str, Any]) -> AsinDailySnapshot:
        asin = normalize_asin(data.get("asin"))
        if not asin:
            raise ValueError("asin is required")
        snapshot_date = data.get("date")
        if not snapshot_date:
            raise ValueError("date is required")
        store_id = str(data.get("store_id") or DEFAULT_STORE_ID)
        marketplace = normalize_marketplace(data.get("marketplace"))
        result = await self.db.execute(
            select(AsinDailySnapshot).where(
                AsinDailySnapshot.seller_id == seller_id,
                AsinDailySnapshot.store_id == store_id,
                AsinDailySnapshot.marketplace == marketplace,
                AsinDailySnapshot.asin == asin,
                AsinDailySnapshot.date == snapshot_date,
            )
        )
        snapshot = result.scalar_one_or_none()
        if not snapshot:
            snapshot = AsinDailySnapshot(
                seller_id=seller_id,
                store_id=store_id,
                marketplace=marketplace,
                asin=asin,
                date=snapshot_date,
            )
            self.db.add(snapshot)

        for key, value in data.items():
            if hasattr(snapshot, key) and key not in {"id", "seller_id"}:
                setattr(snapshot, key, value)
        snapshot.store_id = store_id
        snapshot.marketplace = marketplace
        snapshot.asin = asin
        await self.db.commit()
        await self.db.refresh(snapshot)
        return snapshot

    async def list_daily_snapshots(
        self,
        *,
        seller_id: str,
        asin: Optional[str] = None,
        store_id: Optional[str] = None,
        marketplace: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        query = select(AsinDailySnapshot).where(AsinDailySnapshot.seller_id == seller_id)
        count_query = select(func.count(AsinDailySnapshot.id)).where(AsinDailySnapshot.seller_id == seller_id)
        if asin:
            normalized_asin = normalize_asin(asin)
            query = query.where(AsinDailySnapshot.asin == normalized_asin)
            count_query = count_query.where(AsinDailySnapshot.asin == normalized_asin)
        if store_id:
            query = query.where(AsinDailySnapshot.store_id == store_id)
            count_query = count_query.where(AsinDailySnapshot.store_id == store_id)
        if marketplace:
            normalized_marketplace = normalize_marketplace(marketplace)
            query = query.where(AsinDailySnapshot.marketplace == normalized_marketplace)
            count_query = count_query.where(AsinDailySnapshot.marketplace == normalized_marketplace)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        result = await self.db.execute(query.order_by(AsinDailySnapshot.date.desc()).offset(skip).limit(limit))
        return {"items": list(result.scalars().all()), "total": total, "skip": skip, "limit": limit}

    async def create_validation_task(self, *, seller_id: str, data: Dict[str, Any]) -> ValidationTask:
        asin = normalize_asin(data.get("asin"))
        if not asin:
            raise ValueError("asin is required")
        task = ValidationTask(
            validation_id=f"val_{uuid.uuid4().hex}",
            seller_id=seller_id,
            store_id=str(data.get("store_id") or DEFAULT_STORE_ID),
            marketplace=normalize_marketplace(data.get("marketplace")),
            asin=asin,
            validation_type=data.get("validation_type"),
            problem=data.get("problem"),
            hypothesis=data.get("hypothesis"),
            action_plan=data.get("action_plan"),
            target_metric=data.get("target_metric"),
            baseline_start_date=data.get("baseline_start_date"),
            baseline_end_date=data.get("baseline_end_date"),
            test_start_date=data.get("test_start_date"),
            test_end_date=data.get("test_end_date"),
            result_start_date=data.get("result_start_date"),
            result_end_date=data.get("result_end_date"),
            baseline_value=data.get("baseline_value"),
            target_value=data.get("target_value"),
            result_value=data.get("result_value"),
            improvement_rate=data.get("improvement_rate"),
            confidence_score=data.get("confidence_score"),
            status=data.get("status") or "Pending",
            data_source=data.get("data_source"),
            is_demo=bool(data.get("is_demo")),
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def list_validation_tasks(
        self,
        *,
        seller_id: str,
        asin: Optional[str] = None,
        store_id: Optional[str] = None,
        marketplace: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        query = select(ValidationTask).where(ValidationTask.seller_id == seller_id)
        count_query = select(func.count(ValidationTask.id)).where(ValidationTask.seller_id == seller_id)
        if asin:
            normalized_asin = normalize_asin(asin)
            query = query.where(ValidationTask.asin == normalized_asin)
            count_query = count_query.where(ValidationTask.asin == normalized_asin)
        if store_id:
            query = query.where(ValidationTask.store_id == store_id)
            count_query = count_query.where(ValidationTask.store_id == store_id)
        if marketplace:
            normalized_marketplace = normalize_marketplace(marketplace)
            query = query.where(ValidationTask.marketplace == normalized_marketplace)
            count_query = count_query.where(ValidationTask.marketplace == normalized_marketplace)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        result = await self.db.execute(query.order_by(ValidationTask.created_at.desc()).offset(skip).limit(limit))
        return {"items": list(result.scalars().all()), "total": total, "skip": skip, "limit": limit}

    async def create_execution_log(self, *, seller_id: str, data: Dict[str, Any]) -> AsinExecutionLog:
        asin = normalize_asin(data.get("asin"))
        if not asin:
            raise ValueError("asin is required")
        log = AsinExecutionLog(
            execution_id=f"exec_{uuid.uuid4().hex}",
            validation_id=data.get("validation_id"),
            seller_id=seller_id,
            store_id=str(data.get("store_id") or DEFAULT_STORE_ID),
            marketplace=normalize_marketplace(data.get("marketplace")),
            asin=asin,
            action_type=data.get("action_type"),
            before_value=data.get("before_value"),
            after_value=data.get("after_value"),
            executed_by=data.get("executed_by") or seller_id,
            executed_at=data.get("executed_at") or datetime.now(timezone.utc),
            note=data.get("note"),
            data_source=data.get("data_source"),
            is_demo=bool(data.get("is_demo")),
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def list_execution_logs(
        self,
        *,
        seller_id: str,
        asin: Optional[str] = None,
        validation_id: Optional[str] = None,
        store_id: Optional[str] = None,
        marketplace: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        query = select(AsinExecutionLog).where(AsinExecutionLog.seller_id == seller_id)
        count_query = select(func.count(AsinExecutionLog.id)).where(AsinExecutionLog.seller_id == seller_id)
        if asin:
            normalized_asin = normalize_asin(asin)
            query = query.where(AsinExecutionLog.asin == normalized_asin)
            count_query = count_query.where(AsinExecutionLog.asin == normalized_asin)
        if validation_id:
            query = query.where(AsinExecutionLog.validation_id == validation_id)
            count_query = count_query.where(AsinExecutionLog.validation_id == validation_id)
        if store_id:
            query = query.where(AsinExecutionLog.store_id == store_id)
            count_query = count_query.where(AsinExecutionLog.store_id == store_id)
        if marketplace:
            normalized_marketplace = normalize_marketplace(marketplace)
            query = query.where(AsinExecutionLog.marketplace == normalized_marketplace)
            count_query = count_query.where(AsinExecutionLog.marketplace == normalized_marketplace)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        result = await self.db.execute(query.order_by(AsinExecutionLog.created_at.desc()).offset(skip).limit(limit))
        return {"items": list(result.scalars().all()), "total": total, "skip": skip, "limit": limit}

    async def create_ai_decision_trace(self, *, seller_id: str, data: Dict[str, Any]) -> AiDecisionTrace:
        asin = normalize_asin(data.get("asin"))
        if not asin:
            raise ValueError("asin is required")
        trace = AiDecisionTrace(
            decision_id=f"decision_{uuid.uuid4().hex}",
            seller_id=seller_id,
            store_id=str(data.get("store_id") or DEFAULT_STORE_ID),
            marketplace=normalize_marketplace(data.get("marketplace")),
            asin=asin,
            related_validation_id=data.get("related_validation_id"),
            decision_type=data.get("decision_type"),
            conclusion=data.get("conclusion"),
            evidence_metrics=json_dumps(data.get("evidence_metrics")),
            reasoning_summary=data.get("reasoning_summary"),
            confidence_score=data.get("confidence_score"),
            recommended_action=data.get("recommended_action"),
            data_source=data.get("data_source"),
            is_demo=bool(data.get("is_demo")),
        )
        self.db.add(trace)
        await self.db.commit()
        await self.db.refresh(trace)
        return trace

    async def list_ai_decision_traces(
        self,
        *,
        seller_id: str,
        asin: Optional[str] = None,
        decision_type: Optional[str] = None,
        related_validation_id: Optional[str] = None,
        store_id: Optional[str] = None,
        marketplace: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        query = select(AiDecisionTrace).where(AiDecisionTrace.seller_id == seller_id)
        count_query = select(func.count(AiDecisionTrace.id)).where(AiDecisionTrace.seller_id == seller_id)
        if asin:
            normalized_asin = normalize_asin(asin)
            query = query.where(AiDecisionTrace.asin == normalized_asin)
            count_query = count_query.where(AiDecisionTrace.asin == normalized_asin)
        if decision_type:
            query = query.where(AiDecisionTrace.decision_type == decision_type)
            count_query = count_query.where(AiDecisionTrace.decision_type == decision_type)
        if related_validation_id:
            query = query.where(AiDecisionTrace.related_validation_id == related_validation_id)
            count_query = count_query.where(AiDecisionTrace.related_validation_id == related_validation_id)
        if store_id:
            query = query.where(AiDecisionTrace.store_id == store_id)
            count_query = count_query.where(AiDecisionTrace.store_id == store_id)
        if marketplace:
            normalized_marketplace = normalize_marketplace(marketplace)
            query = query.where(AiDecisionTrace.marketplace == normalized_marketplace)
            count_query = count_query.where(AiDecisionTrace.marketplace == normalized_marketplace)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        result = await self.db.execute(query.order_by(AiDecisionTrace.created_at.desc()).offset(skip).limit(limit))
        return {"items": list(result.scalars().all()), "total": total, "skip": skip, "limit": limit}

    @staticmethod
    def evaluate_validation_status(
        *,
        baseline_value: Optional[float],
        target_value: Optional[float],
        result_value: Optional[float],
        minimum_sample_ready: bool = True,
    ) -> str:
        if not minimum_sample_ready:
            return "Inconclusive"
        if baseline_value is None or result_value is None:
            return "Inconclusive"
        if target_value is not None and result_value >= target_value:
            return "Success"
        if result_value < baseline_value:
            return "Failed"
        return "Inconclusive"

    async def import_demo_from_listing_history(
        self,
        *,
        seller_id: str,
        source_seller_ids: Optional[list[str]] = None,
        store_id: str = DEFAULT_STORE_ID,
        marketplace: Optional[str] = None,
        limit: int = 20,
    ) -> dict:
        source_ids = source_seller_ids or [seller_id]
        query = select(Listing_diagnoses).where(Listing_diagnoses.user_id.in_(source_ids))
        if marketplace:
            query = query.where(Listing_diagnoses.marketplace == normalize_marketplace(marketplace))
        result = await self.db.execute(query.order_by(Listing_diagnoses.id.desc()).limit(limit * 5))
        rows = result.scalars().all()

        imported_profiles = 0
        imported_snapshots = 0
        imported_validation_tasks = 0
        imported_ai_traces = 0
        skipped_without_complete_aplus = 0
        seen: set[tuple[str, str]] = set()

        for row in rows:
            asin = Listing_diagnosesService._record_asin(row)
            if not asin:
                continue

            row_marketplace = normalize_marketplace(row.marketplace)
            key = (row_marketplace, asin)
            if key in seen:
                continue
            seen.add(key)

            input_data = safe_json_loads(row.input_data)
            report = safe_json_loads(row.diagnosis_report)
            complete_aplus_count = self._complete_aplus_count(input_data)
            if complete_aplus_count < COMPLETE_APLUS_MIN_IMAGES:
                skipped_without_complete_aplus += 1
                continue

            scores = self._extract_scores(row, report)
            profile = await self._upsert_demo_profile_from_history(
                seller_id=seller_id,
                store_id=store_id,
                marketplace=row_marketplace,
                asin=asin,
                row=row,
                input_data=input_data,
                report=report,
                scores=scores,
            )
            imported_profiles += 1 if profile else 0
            imported_snapshots += await self._upsert_demo_snapshot_from_history(
                seller_id=seller_id,
                store_id=store_id,
                marketplace=row_marketplace,
                asin=asin,
                row=row,
                input_data=input_data,
                scores=scores,
            )
            validation_id = await self._create_demo_validation_task_from_history(
                seller_id=seller_id,
                store_id=store_id,
                marketplace=row_marketplace,
                asin=asin,
                row=row,
                report=report,
                scores=scores,
            )
            if validation_id:
                imported_validation_tasks += 1
                imported_ai_traces += await self._create_demo_ai_trace_from_history(
                    seller_id=seller_id,
                    store_id=store_id,
                    marketplace=row_marketplace,
                    asin=asin,
                    row=row,
                    report=report,
                    scores=scores,
                    validation_id=validation_id,
                )

            if imported_profiles >= limit:
                break

        await self.db.commit()
        return {
            "imported_profiles": imported_profiles,
            "imported_snapshots": imported_snapshots,
            "imported_validation_tasks": imported_validation_tasks,
            "imported_ai_traces": imported_ai_traces,
            "skipped_without_complete_aplus": skipped_without_complete_aplus,
            "source": DEMO_SOURCE,
        }

    async def clear_demo_data(self, *, seller_id: str) -> dict:
        tables = [
            AiDecisionTrace,
            AsinExecutionLog,
            ValidationTask,
            AsinDailySnapshot,
            AsinKeywordProfile,
            ListingVersion,
            AsinBusinessProfile,
            ReportUpload,
        ]
        deleted_counts: dict[str, int] = {}
        for model in tables:
            result = await self.db.execute(delete(model).where(model.seller_id == seller_id, model.is_demo.is_(True)))
            deleted_counts[model.__tablename__] = int(result.rowcount or 0)
        await self.db.commit()
        return deleted_counts

    def _complete_aplus_count(self, input_data: dict) -> int:
        urls = input_data.get("aplus_image_urls") or []
        if isinstance(urls, list) and len([url for url in urls if str(url or "").strip()]) >= COMPLETE_APLUS_MIN_IMAGES:
            return len([url for url in urls if str(url or "").strip()])
        return parse_int(input_data.get("aplus_image_count")) or 0

    def _extract_scores(self, row: Listing_diagnoses, report: dict) -> dict:
        scores = report.get("scores") if isinstance(report.get("scores"), dict) else {}
        return {
            "function_expression": row.score_function_expression or scores.get("function_expression"),
            "scenario_expression": row.score_scenario_expression or scores.get("scenario_expression"),
            "identity_fit": row.score_identity_fit or scores.get("identity_fit"),
            "psychology_benefit": row.score_psychology_benefit or scores.get("psychology_benefit"),
            "risk_elimination": row.score_risk_elimination or scores.get("risk_elimination"),
            "product_identity": row.score_product_identity or scores.get("product_identity"),
            "compatibility": row.score_compatibility or scores.get("compatibility"),
            "subjective_properties": row.score_subjective_properties or scores.get("subjective_properties"),
            "differentiation": row.score_differentiation or scores.get("differentiation"),
            "market_trend": row.score_market_trend or scores.get("market_trend"),
        }

    async def _upsert_demo_profile_from_history(
        self,
        *,
        seller_id: str,
        store_id: str,
        marketplace: str,
        asin: str,
        row: Listing_diagnoses,
        input_data: dict,
        report: dict,
        scores: dict,
    ) -> Optional[AsinBusinessProfile]:
        profile = await self.get_profile(seller_id=seller_id, store_id=store_id, marketplace=marketplace, asin=asin)
        if not profile:
            profile = AsinBusinessProfile(seller_id=seller_id, store_id=store_id, marketplace=marketplace, asin=asin)
            self.db.add(profile)

        overall = score_average(scores.values())
        profile.product_name = input_data.get("title") or row.listing_title
        profile.brand = input_data.get("brand")
        profile.category = input_data.get("category")
        profile.current_price = parse_float(input_data.get("price"))
        profile.lifecycle_stage = profile.lifecycle_stage or "Testing"
        profile.overall_score = overall
        profile.traffic_score = scores.get("market_trend")
        profile.ctr_score = scores.get("scenario_expression")
        profile.cvr_score = score_average([
            scores.get("function_expression"),
            scores.get("psychology_benefit"),
            scores.get("risk_elimination"),
        ])
        profile.ads_score = score_average([
            scores.get("scenario_expression"),
            scores.get("differentiation"),
            scores.get("compatibility"),
        ])
        profile.competition_score = scores.get("differentiation")
        profile.title_score = scores.get("product_identity")
        profile.main_image_score = scores.get("scenario_expression")
        profile.gallery_score = score_average([scores.get("scenario_expression"), scores.get("risk_elimination")])
        profile.aplus_score = score_average([scores.get("psychology_benefit"), scores.get("risk_elimination"), scores.get("differentiation")])
        profile.bullet_score = score_average([scores.get("function_expression"), scores.get("compatibility")])
        rating = parse_float(input_data.get("rating"))
        profile.review_score = rating * 20 if rating is not None and rating <= 5 else rating
        profile.price_score = 80 if profile.current_price is not None else None
        profile.current_primary_problem = self._first_problem(report)
        profile.priority_actions = self._first_action(report)
        profile.confidence_score = report.get("confidence_score") or overall
        profile.data_source = DEMO_SOURCE
        profile.is_demo = True
        await self._upsert_demo_listing_version(
            seller_id=seller_id,
            store_id=store_id,
            marketplace=marketplace,
            asin=asin,
            row=row,
        )
        return profile

    async def _upsert_demo_listing_version(
        self,
        *,
        seller_id: str,
        store_id: str,
        marketplace: str,
        asin: str,
        row: Listing_diagnoses,
    ) -> None:
        result = await self.db.execute(
            select(ListingVersion).where(
                ListingVersion.seller_id == seller_id,
                ListingVersion.store_id == store_id,
                ListingVersion.marketplace == marketplace,
                ListingVersion.asin == asin,
                ListingVersion.version == "V1",
            )
        )
        version = result.scalar_one_or_none()
        if not version:
            version = ListingVersion(
                seller_id=seller_id,
                store_id=store_id,
                marketplace=marketplace,
                asin=asin,
                version="V1",
            )
            self.db.add(version)
        version.modified_at = row.created_at
        version.change_content = row.listing_title
        version.change_reason = "待录入"
        version.data_source = DEMO_SOURCE
        version.is_demo = True

    async def _upsert_demo_snapshot_from_history(
        self,
        *,
        seller_id: str,
        store_id: str,
        marketplace: str,
        asin: str,
        row: Listing_diagnoses,
        input_data: dict,
        scores: dict,
    ) -> int:
        snapshot_date = (row.created_at.date() if row.created_at else date.today())
        result = await self.db.execute(
            select(AsinDailySnapshot).where(
                AsinDailySnapshot.seller_id == seller_id,
                AsinDailySnapshot.store_id == store_id,
                AsinDailySnapshot.marketplace == marketplace,
                AsinDailySnapshot.asin == asin,
                AsinDailySnapshot.date == snapshot_date,
            )
        )
        snapshot = result.scalar_one_or_none()
        created = 0
        if not snapshot:
            snapshot = AsinDailySnapshot(
                seller_id=seller_id,
                store_id=store_id,
                marketplace=marketplace,
                asin=asin,
                date=snapshot_date,
            )
            self.db.add(snapshot)
            created = 1
        snapshot.sales = parse_float(input_data.get("sales"))
        snapshot.total_sales = parse_float(input_data.get("sales"))
        snapshot.inventory = parse_int(input_data.get("inventory"))
        snapshot.buybox_status = input_data.get("buybox_status")
        snapshot.data_source = DEMO_SOURCE
        snapshot.is_demo = True
        return created

    async def _create_demo_validation_task_from_history(
        self,
        *,
        seller_id: str,
        store_id: str,
        marketplace: str,
        asin: str,
        row: Listing_diagnoses,
        report: dict,
        scores: dict,
    ) -> Optional[str]:
        validation_id = f"demo_val_{row.id}_{asin}"
        result = await self.db.execute(select(ValidationTask).where(ValidationTask.validation_id == validation_id))
        existing = result.scalar_one_or_none()
        if existing:
            return existing.validation_id
        task = ValidationTask(
            validation_id=validation_id,
            seller_id=seller_id,
            store_id=store_id,
            marketplace=marketplace,
            asin=asin,
            validation_type="Listing",
            problem=self._first_problem(report),
            hypothesis="待录入",
            action_plan=self._first_action(report),
            target_metric="CVR",
            confidence_score=score_average(scores.values()),
            status="Pending",
            data_source=DEMO_SOURCE,
            is_demo=True,
        )
        self.db.add(task)
        return validation_id

    async def _create_demo_ai_trace_from_history(
        self,
        *,
        seller_id: str,
        store_id: str,
        marketplace: str,
        asin: str,
        row: Listing_diagnoses,
        report: dict,
        scores: dict,
        validation_id: str,
    ) -> int:
        decision_id = f"demo_decision_{row.id}_{asin}"
        result = await self.db.execute(select(AiDecisionTrace).where(AiDecisionTrace.decision_id == decision_id))
        existing = result.scalar_one_or_none()
        if existing:
            return 0
        trace = AiDecisionTrace(
            decision_id=decision_id,
            seller_id=seller_id,
            store_id=store_id,
            marketplace=marketplace,
            asin=asin,
            related_validation_id=validation_id,
            decision_type="Listing Diagnosis",
            conclusion=report.get("overall_summary") or self._first_problem(report) or "待录入",
            evidence_metrics=json_dumps(scores),
            reasoning_summary=self._first_problem(report),
            confidence_score=score_average(scores.values()),
            recommended_action=self._first_action(report),
            data_source=DEMO_SOURCE,
            is_demo=True,
        )
        self.db.add(trace)
        return 1

    def _first_problem(self, report: dict) -> str:
        analysis = report.get("analysis")
        if isinstance(analysis, dict):
            for value in analysis.values():
                if isinstance(value, str) and value.strip():
                    return value.strip()[:1000]
        position = report.get("listing_position_diagnosis")
        if isinstance(position, dict):
            rows = position.get("rows")
            if isinstance(rows, list):
                for item in rows:
                    if isinstance(item, dict):
                        value = item.get("problem") or item.get("issue") or item.get("current_problem")
                        if value:
                            return str(value).strip()[:1000]
        return "待录入"

    def _first_action(self, report: dict) -> str:
        suggestions = report.get("suggestions")
        if isinstance(suggestions, dict):
            for value in suggestions.values():
                if isinstance(value, str) and value.strip():
                    return value.strip()[:1000]
                if isinstance(value, list) and value:
                    return "；".join(str(item) for item in value[:3])[:1000]
        return "待录入"
