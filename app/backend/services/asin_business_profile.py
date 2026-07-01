import json
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.asin_business_profile import (
    AiDecisionTrace,
    AsinAiMemory,
    AsinBusinessProfile,
    AsinDailySnapshot,
    AsinExecutionLog,
    AsinIntentDecision,
    AsinIntentEvidence,
    AsinKeywordProfile,
    AsinListingSnapshot,
    AsinSafeExpression,
    ListingVersion,
    MetricDictionary,
    ReportUpload,
    ValidationTask,
)
from services.ai_service import AIService
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
    ("CPC", "CPC", "Ad Spend / Clicks", "Cost per click"),
    ("ROAS", "ROAS", "Ad Sales / Ad Spend", "Return on ad spend"),
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
        self.ai_service = AIService()

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

    async def run_intent_decision(self, *, seller_id: str, asin: str, data: Dict[str, Any]) -> AsinIntentDecision:
        normalized_asin = normalize_asin(asin)
        if not normalized_asin:
            raise ValueError("asin is required")
        intent_name = str(data.get("intent_name") or "").strip()
        if not intent_name:
            raise ValueError("intent_name is required")
        store_id = str(data.get("store_id") or DEFAULT_STORE_ID)
        marketplace = normalize_marketplace(data.get("marketplace"))
        await self._ensure_profile(seller_id=seller_id, store_id=store_id, marketplace=marketplace, asin=normalized_asin)

        listing_snapshot = data.get("listing_snapshot") if isinstance(data.get("listing_snapshot"), dict) else None
        has_listing = bool(listing_snapshot and any(listing_snapshot.get(key) for key in ("title", "bullet_points", "main_image", "secondary_images", "aplus")))
        if listing_snapshot:
            await self.create_listing_snapshot(
                seller_id=seller_id,
                data={**listing_snapshot, "store_id": store_id, "marketplace": marketplace, "asin": normalized_asin},
            )

        evidences = data.get("evidences") if isinstance(data.get("evidences"), list) else []
        safe_expression = self._first_safe_expression(data, listing_snapshot)
        blocked_expression = self._blocked_expression(data)
        engine_result = await self.ai_service.run_intent_reception_engine(
            {
                **data,
                "has_listing": has_listing,
                "evidence_count": len(evidences),
                "safe_expression": safe_expression,
                "blocked_expression": blocked_expression,
            }
        )

        decision = AsinIntentDecision(
            intent_decision_id=f"intent_{uuid.uuid4().hex}",
            seller_id=seller_id,
            store_id=store_id,
            marketplace=marketplace,
            asin=normalized_asin,
            intent_name=intent_name,
            intent_description=data.get("intent_description"),
            position_reception_result=engine_result.get("position_reception_result"),
            semantic_audit_result=engine_result.get("semantic_audit_result"),
            buyer_language_result=engine_result.get("buyer_language_result"),
            intent_evidence_status=engine_result.get("intent_evidence_status"),
            product_platform_safety_status=engine_result.get("product_platform_safety_status"),
            investment_value_status=engine_result.get("investment_value_status"),
            reception_gap=engine_result.get("reception_gap"),
            safe_expression=engine_result.get("safe_expression"),
            blocked_expression=engine_result.get("blocked_expression"),
            recommended_action=engine_result.get("recommended_action") or "Do Not Invest",
            priority_score=parse_float(engine_result.get("priority_score")),
            confidence_score=parse_float(engine_result.get("confidence_score")) or self._evidence_confidence(evidences),
            status=engine_result.get("status") or "Candidate",
            data_source=data.get("data_source"),
            is_demo=bool(data.get("is_demo")),
        )
        self.db.add(decision)
        await self.db.flush()

        for evidence in evidences:
            if not isinstance(evidence, dict):
                continue
            self.db.add(
                AsinIntentEvidence(
                    evidence_id=f"evidence_{uuid.uuid4().hex}",
                    intent_decision_id=decision.intent_decision_id,
                    seller_id=seller_id,
                    store_id=store_id,
                    marketplace=marketplace,
                    asin=normalized_asin,
                    intent_name=intent_name,
                    source_type=evidence.get("source_type") or "Manual",
                    evidence_text=evidence.get("evidence_text"),
                    metric_snapshot=json_dumps(evidence.get("metric_snapshot")),
                    strength_score=parse_float(evidence.get("strength_score")),
                    data_source=evidence.get("data_source") or data.get("data_source"),
                    is_demo=bool(evidence.get("is_demo") or data.get("is_demo")),
                )
            )

        self.db.add(
            AsinSafeExpression(
                safe_expression_id=f"safe_{uuid.uuid4().hex}",
                intent_decision_id=decision.intent_decision_id,
                seller_id=seller_id,
                store_id=store_id,
                marketplace=marketplace,
                asin=normalized_asin,
                buyer_language=data.get("intent_description") or intent_name,
                seller_language=data.get("seller_language"),
                safe_expression=decision.safe_expression,
                blocked_expression=decision.blocked_expression,
                risk_reason="待录入" if decision.product_platform_safety_status != "Blocked" else decision.blocked_expression,
                evidence_required="待录入" if decision.product_platform_safety_status == "Needs Evidence" else None,
                status=self._safe_expression_status(decision),
                data_source=data.get("data_source"),
                is_demo=bool(data.get("is_demo")),
            )
        )

        trace = AiDecisionTrace(
            decision_id=f"decision_{uuid.uuid4().hex}",
            seller_id=seller_id,
            store_id=store_id,
            marketplace=marketplace,
            asin=normalized_asin,
            related_validation_id=None,
            decision_type="Intent Decision",
            conclusion=decision.recommended_action,
            input_data_refs=json_dumps(data.get("input_data_refs")),
            evidence_metrics=json_dumps({"evidence_count": len(evidences)}),
            metric_snapshot=json_dumps(data.get("metric_snapshot")),
            semantic_evidence=json_dumps(
                {
                    "position_reception_result": decision.position_reception_result,
                    "semantic_audit_result": decision.semantic_audit_result,
                    "buyer_language_result": decision.buyer_language_result,
                }
            ),
            reasoning_summary=decision.reception_gap,
            confidence_score=decision.confidence_score,
            recommended_action=decision.recommended_action,
            prompt_version=self.ai_service.prompt_version,
            model_name=self.ai_service.model_name,
            data_source=data.get("data_source"),
            is_demo=bool(data.get("is_demo")),
        )
        self.db.add(trace)
        await self._update_ai_memory_from_decision(decision)
        await self.db.commit()
        await self.db.refresh(decision)
        return decision

    async def create_listing_snapshot(self, *, seller_id: str, data: Dict[str, Any]) -> AsinListingSnapshot:
        asin = normalize_asin(data.get("asin"))
        if not asin:
            raise ValueError("asin is required")
        snapshot = AsinListingSnapshot(
            seller_id=seller_id,
            store_id=str(data.get("store_id") or DEFAULT_STORE_ID),
            marketplace=normalize_marketplace(data.get("marketplace")),
            asin=asin,
            title=data.get("title"),
            bullet_points=json_dumps(data.get("bullet_points")) if isinstance(data.get("bullet_points"), list) else data.get("bullet_points"),
            description=data.get("description"),
            aplus=json_dumps(data.get("aplus")),
            main_image=data.get("main_image"),
            secondary_images=json_dumps(data.get("secondary_images")) if isinstance(data.get("secondary_images"), list) else data.get("secondary_images"),
            backend_terms=data.get("backend_terms"),
            price=parse_float(data.get("price")),
            coupon=data.get("coupon"),
            snapshot_at=data.get("snapshot_at") or datetime.now(timezone.utc),
            data_source=data.get("data_source"),
            is_demo=bool(data.get("is_demo")),
        )
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def list_intent_decisions(
        self,
        *,
        seller_id: str,
        asin: Optional[str] = None,
        store_id: Optional[str] = None,
        marketplace: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        query = select(AsinIntentDecision).where(AsinIntentDecision.seller_id == seller_id)
        count_query = select(func.count(AsinIntentDecision.id)).where(AsinIntentDecision.seller_id == seller_id)
        if asin:
            normalized_asin = normalize_asin(asin)
            query = query.where(AsinIntentDecision.asin == normalized_asin)
            count_query = count_query.where(AsinIntentDecision.asin == normalized_asin)
        if store_id:
            query = query.where(AsinIntentDecision.store_id == store_id)
            count_query = count_query.where(AsinIntentDecision.store_id == store_id)
        if marketplace:
            normalized_marketplace = normalize_marketplace(marketplace)
            query = query.where(AsinIntentDecision.marketplace == normalized_marketplace)
            count_query = count_query.where(AsinIntentDecision.marketplace == normalized_marketplace)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        result = await self.db.execute(query.order_by(AsinIntentDecision.updated_at.desc()).offset(skip).limit(limit))
        return {"items": list(result.scalars().all()), "total": total, "skip": skip, "limit": limit}

    async def get_asin_profile_detail(
        self,
        *,
        seller_id: str,
        asin: str,
        store_id: str = DEFAULT_STORE_ID,
        marketplace: str = "US",
    ) -> dict:
        normalized_asin = normalize_asin(asin)
        normalized_marketplace = normalize_marketplace(marketplace)
        profile = await self.get_profile(
            seller_id=seller_id,
            store_id=store_id or DEFAULT_STORE_ID,
            marketplace=normalized_marketplace,
            asin=normalized_asin,
        )
        memory_result = await self.db.execute(
            select(AsinAiMemory).where(
                AsinAiMemory.seller_id == seller_id,
                AsinAiMemory.store_id == (store_id or DEFAULT_STORE_ID),
                AsinAiMemory.marketplace == normalized_marketplace,
                AsinAiMemory.asin == normalized_asin,
            )
        )
        decisions = await self.list_intent_decisions(
            seller_id=seller_id,
            asin=normalized_asin,
            store_id=store_id or DEFAULT_STORE_ID,
            marketplace=normalized_marketplace,
            limit=20,
        )
        latest_snapshots = await self._latest_snapshots(profile) if profile else []
        return {
            "profile": profile,
            "memory": memory_result.scalar_one_or_none(),
            "intent_decisions": decisions["items"],
            "latest_snapshots": latest_snapshots,
        }

    async def run_effect_validation(
        self,
        *,
        seller_id: str,
        validation_id: str,
        result_start_date: Optional[date] = None,
        result_end_date: Optional[date] = None,
        minimum_sample_ready: bool = True,
    ) -> dict:
        result = await self.db.execute(
            select(ValidationTask).where(
                ValidationTask.validation_id == validation_id,
                ValidationTask.seller_id == seller_id,
            )
        )
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError("validation_id not found")

        if result_start_date:
            task.result_start_date = result_start_date
        if result_end_date:
            task.result_end_date = result_end_date

        metric_column = self._snapshot_metric_column(task.target_metric)
        baseline_value = await self._period_average(task, metric_column, task.baseline_start_date, task.baseline_end_date) if metric_column is not None else None
        result_value = await self._period_average(
            task,
            metric_column,
            task.result_start_date or task.test_start_date,
            task.result_end_date or task.test_end_date,
        ) if metric_column is not None else None
        task.baseline_value = baseline_value
        task.result_value = result_value
        task_meta = self.parse_validation_task_meta(task)
        is_orphan = not bool(
            task_meta.get("hypothesis_id") and task_meta.get("source_snapshot_id")
        )
        if is_orphan:
            task.status = "orphan_validation_result"
            task.result_summary = "缺少 hypothesis_id 或 source_snapshot_id，无法闭环回写"
            task.data_source = json_dumps(
                {
                    **task_meta,
                    "data_source": task.data_source,
                    "orphan_reason": "missing_hypothesis_id_or_source_snapshot_id",
                    "result_summary": task.result_summary,
                }
            )
            task.updated_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(task)
            return task

        task.status = self.evaluate_validation_status(
            baseline_value=baseline_value,
            target_value=task.target_value,
            result_value=result_value,
            minimum_sample_ready=minimum_sample_ready,
        )
        if baseline_value not in (None, 0) and result_value is not None:
            task.improvement_rate = round((result_value - baseline_value) / baseline_value, 6)
        task.updated_at = datetime.now(timezone.utc)

        decision = None
        if task.intent_decision_id:
            decision = await self._get_intent_decision(
                seller_id=seller_id,
                store_id=task.store_id,
                marketplace=task.marketplace,
                asin=task.asin,
                intent_decision_id=task.intent_decision_id,
            )
            if decision:
                decision.validation_task_id = task.validation_id
                decision.validation_result = task.status
                decision.status = {"Success": "Validated", "Failed": "Failed", "Inconclusive": "Inconclusive"}.get(task.status, decision.status)
                await self._update_ai_memory_from_decision(decision)

        ai_result = await self.ai_service.run_effect_validation(
            {
                "status": task.status,
                "recommended_action": task.action_plan,
                "reasoning_summary": task.target_metric,
            }
        )
        trace = AiDecisionTrace(
            decision_id=f"effect_{uuid.uuid4().hex}",
            seller_id=task.seller_id,
            store_id=task.store_id,
            marketplace=task.marketplace,
            asin=task.asin,
            related_validation_id=task.validation_id,
            decision_type="Effect Validation",
            conclusion=ai_result.get("conclusion") or task.status,
            input_data_refs=json_dumps({"validation_id": task.validation_id, "intent_decision_id": task.intent_decision_id}),
            evidence_metrics=json_dumps(
                {
                    "baseline_value": task.baseline_value,
                    "target_value": task.target_value,
                    "result_value": task.result_value,
                    "improvement_rate": task.improvement_rate,
                }
            ),
            metric_snapshot=json_dumps({task.target_metric or "metric": task.result_value}),
            semantic_evidence=json_dumps({"validation_result": task.status}),
            reasoning_summary=ai_result.get("reasoning_summary") or task.target_metric,
            confidence_score=task.confidence_score,
            recommended_action=ai_result.get("recommended_action") or task.action_plan,
            prompt_version=self.ai_service.prompt_version,
            model_name=self.ai_service.model_name,
        )
        self.db.add(trace)
        await self.db.commit()
        return {
            "validation_id": task.validation_id,
            "intent_decision_id": task.intent_decision_id,
            "asin": task.asin,
            "status": task.status,
            "baseline_value": task.baseline_value,
            "target_value": task.target_value,
            "result_value": task.result_value,
            "improvement_rate": task.improvement_rate,
            "decision_id": trace.decision_id,
        }

    async def _ensure_profile(self, *, seller_id: str, store_id: str, marketplace: str, asin: str) -> AsinBusinessProfile:
        profile = await self.get_profile(seller_id=seller_id, store_id=store_id, marketplace=marketplace, asin=asin)
        if profile:
            return profile
        profile = AsinBusinessProfile(seller_id=seller_id, store_id=store_id, marketplace=marketplace, asin=asin)
        self.db.add(profile)
        await self.db.flush()
        return profile

    async def _get_intent_decision(
        self,
        *,
        seller_id: str,
        store_id: str,
        marketplace: str,
        asin: str,
        intent_decision_id: str,
    ) -> Optional[AsinIntentDecision]:
        result = await self.db.execute(
            select(AsinIntentDecision).where(
                AsinIntentDecision.intent_decision_id == intent_decision_id,
                AsinIntentDecision.seller_id == seller_id,
                AsinIntentDecision.store_id == store_id,
                AsinIntentDecision.marketplace == marketplace,
                AsinIntentDecision.asin == asin,
            )
        )
        return result.scalar_one_or_none()

    def _first_safe_expression(self, data: dict, listing_snapshot: Optional[dict]) -> str:
        explicit = data.get("safe_expression")
        if explicit:
            return str(explicit)
        if listing_snapshot and listing_snapshot.get("title"):
            return str(listing_snapshot.get("title"))
        return ""

    def _blocked_expression(self, data: dict) -> str:
        value = data.get("blocked_expression")
        if value:
            return str(value)
        safety = str(data.get("product_platform_safety_status") or "").lower()
        return "平台安全风险" if safety in {"blocked", "high risk"} else ""

    def _evidence_confidence(self, evidences: list) -> Optional[float]:
        scores = [parse_float(item.get("strength_score")) for item in evidences if isinstance(item, dict)]
        return score_average([score for score in scores if score is not None])

    def _safe_expression_status(self, decision: AsinIntentDecision) -> str:
        if decision.recommended_action == "Blocked" or decision.product_platform_safety_status == "Blocked":
            return "Blocked"
        if decision.product_platform_safety_status == "Needs Evidence":
            return "Needs Evidence"
        if not decision.safe_expression or decision.safe_expression == "待录入":
            return "Needs Rewrite"
        return "Safe"

    async def _update_ai_memory_from_decision(self, decision: AsinIntentDecision) -> AsinAiMemory:
        result = await self.db.execute(
            select(AsinAiMemory).where(
                AsinAiMemory.seller_id == decision.seller_id,
                AsinAiMemory.store_id == decision.store_id,
                AsinAiMemory.marketplace == decision.marketplace,
                AsinAiMemory.asin == decision.asin,
            )
        )
        memory = result.scalar_one_or_none()
        if not memory:
            memory = AsinAiMemory(
                seller_id=decision.seller_id,
                store_id=decision.store_id,
                marketplace=decision.marketplace,
                asin=decision.asin,
            )
            self.db.add(memory)
        validated = safe_json_loads(memory.validated_intents).get("items", [])
        failed = safe_json_loads(memory.failed_intents).get("items", [])
        if decision.validation_result == "Success" or decision.status == "Validated":
            if decision.intent_name not in validated:
                validated.append(decision.intent_name)
        if decision.validation_result == "Failed" or decision.status == "Failed":
            if decision.intent_name not in failed:
                failed.append(decision.intent_name)
        memory.validated_intents = json_dumps({"items": validated})
        memory.failed_intents = json_dumps({"items": failed})
        memory.current_main_bottleneck = decision.reception_gap
        memory.current_listing_gap = decision.reception_gap if decision.recommended_action == "Listing First" else memory.current_listing_gap
        memory.current_traffic_problem = decision.reception_gap if decision.recommended_action in {"Low-Bid Test", "Scale Test"} else memory.current_traffic_problem
        memory.next_best_hypothesis = decision.intent_name
        memory.latest_learning = decision.validation_result or decision.recommended_action
        memory.data_source = decision.data_source
        memory.is_demo = bool(decision.is_demo)
        return memory

    def _snapshot_metric_column(self, metric: Optional[str]):
        metric_key = (metric or "").lower()
        return {
            "sessions": AsinDailySnapshot.sessions,
            "clicks": AsinDailySnapshot.clicks,
            "orders": AsinDailySnapshot.orders,
            "sales": AsinDailySnapshot.total_sales,
            "total_sales": AsinDailySnapshot.total_sales,
            "ctr": AsinDailySnapshot.ctr,
            "cvr": AsinDailySnapshot.cvr,
            "acos": AsinDailySnapshot.acos,
            "tacos": AsinDailySnapshot.tacos,
            "ad_spend": AsinDailySnapshot.ad_spend,
            "ad_sales": AsinDailySnapshot.ad_sales,
            "cpc": AsinDailySnapshot.ad_spend,
            "roas": AsinDailySnapshot.ad_sales,
        }.get(metric_key)

    async def _period_average(self, task: ValidationTask, metric_column, start_date, end_date) -> Optional[float]:
        if not start_date or not end_date:
            return None
        result = await self.db.execute(
            select(func.avg(metric_column)).where(
                AsinDailySnapshot.seller_id == task.seller_id,
                AsinDailySnapshot.store_id == task.store_id,
                AsinDailySnapshot.marketplace == task.marketplace,
                AsinDailySnapshot.asin == task.asin,
                AsinDailySnapshot.date >= start_date,
                AsinDailySnapshot.date <= end_date,
            )
        )
        value = result.scalar()
        return float(value) if value is not None else None

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
            file_path=data.get("file_path"),
            upload_time=datetime.now(timezone.utc),
            uploaded_by=data.get("uploaded_by"),
            parse_status=data.get("parse_status") or "Pending",
            parse_error=data.get("parse_error"),
            date_range_start=data.get("date_range_start"),
            date_range_end=data.get("date_range_end"),
            row_count=data.get("row_count"),
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
        intent_decision_id = data.get("intent_decision_id")
        if intent_decision_id:
            decision = await self._get_intent_decision(
                seller_id=seller_id,
                store_id=str(data.get("store_id") or DEFAULT_STORE_ID),
                marketplace=normalize_marketplace(data.get("marketplace")),
                asin=asin,
                intent_decision_id=intent_decision_id,
            )
            if not decision:
                raise ValueError("intent_decision_id not found")
        task = ValidationTask(
            validation_id=f"val_{uuid.uuid4().hex}",
            seller_id=seller_id,
            store_id=str(data.get("store_id") or DEFAULT_STORE_ID),
            marketplace=normalize_marketplace(data.get("marketplace")),
            asin=asin,
            intent_decision_id=intent_decision_id,
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
        if intent_decision_id:
            decision.validation_task_id = task.validation_id
            decision.status = "Testing" if task.status == "Running" else decision.status
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
        intent_decision_id = data.get("intent_decision_id")
        if intent_decision_id:
            decision = await self._get_intent_decision(
                seller_id=seller_id,
                store_id=str(data.get("store_id") or DEFAULT_STORE_ID),
                marketplace=normalize_marketplace(data.get("marketplace")),
                asin=asin,
                intent_decision_id=intent_decision_id,
            )
            if not decision:
                raise ValueError("intent_decision_id not found")
        log = AsinExecutionLog(
            execution_id=f"exec_{uuid.uuid4().hex}",
            validation_id=data.get("validation_id"),
            intent_decision_id=intent_decision_id,
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
            source=data.get("source") or data.get("data_source"),
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
            input_data_refs=json_dumps(data.get("input_data_refs")),
            evidence_metrics=json_dumps(data.get("evidence_metrics")),
            metric_snapshot=json_dumps(data.get("metric_snapshot")),
            semantic_evidence=json_dumps(data.get("semantic_evidence")),
            reasoning_summary=data.get("reasoning_summary"),
            confidence_score=data.get("confidence_score"),
            recommended_action=data.get("recommended_action"),
            prompt_version=data.get("prompt_version"),
            model_name=data.get("model_name"),
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
    def parse_validation_task_meta(task: ValidationTask) -> dict:
        meta: dict[str, Any] = {}
        for key in ("hypothesis_id", "source_snapshot_id"):
            value = getattr(task, key, None)
            if value:
                meta[key] = value

        for field in ("data_source", "action_plan"):
            raw_value = getattr(task, field, None)
            if not raw_value:
                continue
            try:
                parsed = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                for key in ("hypothesis_id", "source_snapshot_id"):
                    if parsed.get(key) and not meta.get(key):
                        meta[key] = parsed.get(key)
        return meta

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

    async def import_from_listing_history(
        self,
        *,
        seller_id: str,
        source_seller_ids: Optional[list[str]] = None,
        store_id: str = DEFAULT_STORE_ID,
        marketplace: Optional[str] = None,
        limit: int = 100,
    ) -> dict:
        source_ids = source_seller_ids or [seller_id]
        query = select(Listing_diagnoses).where(Listing_diagnoses.user_id.in_(source_ids))
        if marketplace:
            query = query.where(Listing_diagnoses.marketplace == normalize_marketplace(marketplace))
        result = await self.db.execute(query.order_by(Listing_diagnoses.id.desc()).limit(limit * 5))
        rows = result.scalars().all()

        imported_profiles = 0
        skipped_without_asin = 0
        seen: set[tuple[str, str]] = set()

        for row in rows:
            asin = Listing_diagnosesService._record_asin(row)
            if not asin:
                skipped_without_asin += 1
                continue

            row_marketplace = normalize_marketplace(row.marketplace)
            key = (row_marketplace, asin)
            if key in seen:
                continue
            seen.add(key)

            profile = await self.upsert_profile_from_listing_diagnosis_record(
                seller_id=seller_id,
                store_id=store_id,
                row=row,
            )
            imported_profiles += 1 if profile else 0

            if imported_profiles >= limit:
                break

        return {
            "imported_profiles": imported_profiles,
            "skipped_without_asin": skipped_without_asin,
            "source": "listing_diagnosis",
        }

    async def clear_demo_data(self, *, seller_id: str) -> dict:
        tables = [
            AiDecisionTrace,
            AsinExecutionLog,
            ValidationTask,
            AsinIntentEvidence,
            AsinSafeExpression,
            AsinIntentDecision,
            AsinListingSnapshot,
            AsinAiMemory,
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

    async def upsert_profile_from_listing_diagnosis_record(
        self,
        *,
        seller_id: str,
        row: Listing_diagnoses,
        store_id: str = DEFAULT_STORE_ID,
    ) -> Optional[AsinBusinessProfile]:
        asin = Listing_diagnosesService._record_asin(row)
        if not asin:
            return None

        marketplace = normalize_marketplace(row.marketplace)
        input_data = safe_json_loads(row.input_data)
        report = safe_json_loads(row.diagnosis_report)
        scores = self._extract_scores(row, report)
        profile = await self._upsert_demo_profile_from_history(
            seller_id=seller_id,
            store_id=store_id,
            marketplace=marketplace,
            asin=asin,
            row=row,
            input_data=input_data,
            report=report,
            scores=scores,
        )
        if not profile:
            return None

        profile.data_source = "listing_diagnosis"
        profile.is_demo = False

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
        if version:
            version.change_reason = "诊断保存"
            version.data_source = "listing_diagnosis"
            version.is_demo = False

        await self.db.commit()
        await self.db.refresh(profile)
        return profile

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
