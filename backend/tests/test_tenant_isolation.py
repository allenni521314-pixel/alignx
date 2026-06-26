from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.ai_orchestration import AIResponse
from app.core.capture import CaptureResult
from app.database import Base
from app.models import (
    AiCallLog,
    Asin,
    CaptureJob,
    ConversionDiagnosis,
    ExecutionRecord,
    ListingSnapshot,
    OperationAuditLog,
    ReportUploadStagingRecord,
    User,
)
from app.schemas import (
    ConversionDiagnosisRequest,
    ExecutionRecordCreate,
    ReportUploadStagingRequest,
    ValidationResultCreate,
    ValidationTaskCreate,
    ValidationTaskUpdate,
)
from app.services.ai_calls import complete_json_with_log
from app.services.asin_operation_tree import build_closed_loop_audit
from app.services.conversion_diagnosis import diagnose
from app.services.lifecycle_engine import detect_lifecycle
from app.services.proposition_library import (
    ensure_proposition_library,
    list_propositions,
    proposition_library_status,
)
from app.services.report_uploads import confirm_staging_record, stage_report_upload
from app.services.validation import create_execution, create_result, get_profile
from app.services.validation_tasks import create_task, get_task, list_tasks, update_task


class TenantIsolationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.db = self.sessions()
        self.user_a = User(id="user_a", email="a@example.com", name="A")
        self.user_b = User(id="user_b", email="b@example.com", name="B")
        self.db.add_all([self.user_a, self.user_b])
        await self.db.flush()

    async def asyncTearDown(self):
        await self.db.close()
        await self.engine.dispose()

    async def test_user_cannot_read_other_users_validation_task(self):
        task = await create_task(
            ValidationTaskCreate(
                asin="B0TENANT01",
                proposition_code="P01-001",
                hypothesis_text="待录入",
            ),
            self.db,
            user_id=self.user_a.id,
        )

        other_user_list = await list_tasks(None, 1, 20, self.db, user_id=self.user_b.id)
        other_user_detail = await get_task(task.id, self.db, user_id=self.user_b.id)

        self.assertEqual(other_user_list["total"], 0)
        self.assertIsNone(other_user_detail)

    async def test_validation_result_writes_only_own_asin_profile(self):
        task = await create_task(
            ValidationTaskCreate(
                asin="B0TENANT02",
                proposition_code="P01-001",
                hypothesis_text="待录入",
            ),
            self.db,
            user_id=self.user_a.id,
        )

        await create_result(
            ValidationResultCreate(
                validation_task_id=task.id,
                asin=task.asin,
                final_result_status="effective",
            ),
            self.db,
            user_id=self.user_a.id,
        )

        owner_profile = await get_profile(task.asin, self.db, user_id=self.user_a.id)
        other_profile = await get_profile(task.asin, self.db, user_id=self.user_b.id)

        self.assertIsNotNone(owner_profile)
        self.assertEqual(owner_profile.effective_count, 1)
        self.assertIsNone(other_profile)

    async def test_execution_record_must_bind_owned_validation_task(self):
        task = await create_task(
            ValidationTaskCreate(
                asin="B0TENANT03",
                proposition_code="P01-001",
                hypothesis_text="待录入",
            ),
            self.db,
            user_id=self.user_b.id,
        )

        with self.assertRaises(ValueError):
            await create_execution(
                ExecutionRecordCreate(
                    validation_task_id=task.id,
                    asin=task.asin,
                    action_summary="待录入",
                ),
                self.db,
                user_id=self.user_a.id,
            )

    async def test_ai_call_log_saves_input_output_model_and_prompt_version(self):
        class FakeAI:
            provider_name = "deepseek"

            async def complete(self, **kwargs):
                return AIResponse(
                    raw='{"status":"ok"}',
                    provider="deepseek",
                    model=kwargs.get("model") or "deepseek-chat",
                    tokens_used=12,
                )

        with patch("app.services.ai_calls.AI", return_value=FakeAI()):
            result = await complete_json_with_log(
                db=self.db,
                user_id=self.user_a.id,
                asin="B0TENANT04",
                module_name="conversion_diagnosis",
                prompt_version="conversion_diagnosis:v1",
                prompt="prompt",
                system="system",
                input_payload={"asin": "B0TENANT04"},
            )

        logs = (await self.db.execute(select(AiCallLog))).scalars().all()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].user_id, self.user_a.id)
        self.assertEqual(logs[0].asin, "B0TENANT04")
        self.assertEqual(logs[0].module_name, "conversion_diagnosis")
        self.assertEqual(logs[0].model_name, "deepseek-chat")
        self.assertEqual(logs[0].model_provider, "deepseek")
        self.assertEqual(logs[0].prompt_version, "conversion_diagnosis:v1")
        self.assertEqual(logs[0].input_payload["prompt"], "prompt")
        self.assertEqual(logs[0].output_parsed["status"], "ok")
        self.assertEqual(logs[0].token_usage, 12)

    async def test_unresolved_report_upload_goes_to_staging_only(self):
        result = await stage_report_upload(
            ReportUploadStagingRequest(
                report_type="advertising",
                rows=[{"Campaign": "C1", "Spend": "12.5"}],
            ),
            self.db,
            user_id=self.user_a.id,
        )

        records = (await self.db.execute(select(ReportUploadStagingRecord))).scalars().all()
        executions = (await self.db.execute(select(ExecutionRecord))).scalars().all()

        self.assertEqual(result.unresolved_count, 1)
        self.assertEqual(records[0].attribution_status, "unresolved")
        self.assertEqual(len(executions), 0)

        with self.assertRaises(ValueError):
            await confirm_staging_record(records[0].id, "missing_task", self.db, user_id=self.user_a.id)

    async def test_resolved_report_upload_requires_confirmation_before_execution_record(self):
        asin = Asin(user_id=self.user_a.id, asin="B0TENANT05", marketplace="amazon.com")
        self.db.add(asin)
        await self.db.flush()
        task = await create_task(
            ValidationTaskCreate(
                asin=asin.asin,
                proposition_code="P01-001",
                hypothesis_text="待录入",
            ),
            self.db,
            user_id=self.user_a.id,
        )
        result = await stage_report_upload(
            ReportUploadStagingRequest(
                report_type="advertising",
                rows=[{"ASIN": task.asin, "Date": "2026-06-25", "Campaign": "C1", "Spend": "12.5"}],
            ),
            self.db,
            user_id=self.user_a.id,
        )

        executions_before = (await self.db.execute(select(ExecutionRecord))).scalars().all()
        execution_id = await confirm_staging_record(result.items[0].id, task.id, self.db, user_id=self.user_a.id)
        executions_after = (await self.db.execute(select(ExecutionRecord))).scalars().all()
        staged = (
            await self.db.execute(
                select(ReportUploadStagingRecord).where(ReportUploadStagingRecord.id == result.items[0].id)
            )
        ).scalar_one()

        self.assertEqual(result.resolved_count, 1)
        self.assertEqual(result.items[0].asin_id, asin.id)
        self.assertEqual(result.items[0].asin_attribution_status, "matched")
        self.assertEqual(len(executions_before), 0)
        self.assertEqual(len(executions_after), 1)
        self.assertEqual(executions_after[0].id, execution_id)
        self.assertEqual(staged.source_record_id, staged.id)
        self.assertEqual(staged.validation_task_id, task.id)
        self.assertEqual(staged.execution_record_id, execution_id)

    async def test_unregistered_asin_report_upload_cannot_be_confirmed(self):
        task = await create_task(
            ValidationTaskCreate(
                asin="B0TENANT5U",
                proposition_code="P01-001",
                hypothesis_text="待录入",
            ),
            self.db,
            user_id=self.user_a.id,
        )
        result = await stage_report_upload(
            ReportUploadStagingRequest(
                report_type="advertising",
                rows=[{"ASIN": task.asin, "Date": "2026-06-25", "Campaign": "C1", "Spend": "12.5"}],
            ),
            self.db,
            user_id=self.user_a.id,
        )

        executions_before = (await self.db.execute(select(ExecutionRecord))).scalars().all()

        self.assertEqual(result.items[0].attribution_status, "resolved")
        self.assertEqual(result.items[0].asin_attribution_status, "unregistered")
        with self.assertRaises(ValueError):
            await confirm_staging_record(result.items[0].id, task.id, self.db, user_id=self.user_a.id)

        executions_after = (await self.db.execute(select(ExecutionRecord))).scalars().all()
        self.assertEqual(len(executions_before), 0)
        self.assertEqual(len(executions_after), 0)

    async def test_today_decision_start_and_execution_create_are_audited(self):
        task = await create_task(
            ValidationTaskCreate(
                asin="B0TENANT06",
                proposition_code="P01-001",
                hypothesis_text="待录入",
            ),
            self.db,
            user_id=self.user_a.id,
        )

        await update_task(
            task.id,
            ValidationTaskUpdate(execution_status="running", audit_source="today_decisions"),
            self.db,
            user_id=self.user_a.id,
        )
        await create_execution(
            ExecutionRecordCreate(
                validation_task_id=task.id,
                asin=task.asin,
                action_summary="待录入",
            ),
            self.db,
            user_id=self.user_a.id,
        )

        logs = (await self.db.execute(select(OperationAuditLog).order_by(OperationAuditLog.created_at))).scalars().all()

        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0].action, "today_decision.start_validation")
        self.assertEqual(logs[0].before_json["execution_status"], "pending")
        self.assertEqual(logs[0].after_json["execution_status"], "running")
        self.assertEqual(logs[1].action, "execution_record.create")
        self.assertEqual(logs[1].asin, task.asin)

    async def test_reserved_product_type_and_readability_fields_exist(self):
        asin_columns = Asin.__table__.columns
        snapshot_columns = ListingSnapshot.__table__.columns
        diagnosis_columns = ConversionDiagnosis.__table__.columns

        self.assertIn("sp_api_product_type", asin_columns)
        self.assertIn("sp_api_product_type_version", asin_columns)
        self.assertIn("sp_api_product_type_schema_version", asin_columns)
        self.assertIn("ai_readability_score_json", snapshot_columns)
        self.assertIn("ai_readability_score_version", snapshot_columns)
        self.assertIn("ai_readability_score_json", diagnosis_columns)
        self.assertIn("ai_readability_score_version", diagnosis_columns)

    async def test_lifecycle_includes_keyword_groups_from_conversion_asin_sources(self):
        capture = CaptureJob(
            user_id=self.user_a.id,
            input_type="asin",
            input_value="B0TENANT07",
            marketplace="amazon.com",
            status="success",
        )
        self.db.add(capture)
        await self.db.flush()
        snapshot = ListingSnapshot(
            capture_job_id=capture.id,
            asin="B0TENANT07",
            marketplace="amazon.com",
            title="Rechargeable camping lantern with magnetic base",
            bullet_points=[
                "waterproof emergency light for power outage",
                "portable tent light for hiking and storm kit",
            ],
            product_details={"Material": "aluminum flashlight body"},
        )
        diagnosis = ConversionDiagnosis(
            user_id=self.user_a.id,
            asin="B0TENANT07",
            marketplace="amazon.com",
            priority_action="Rewrite title around emergency lantern and camping light",
            position_diagnoses_json=[
                {
                    "position_name": "标题",
                    "recommendation": "Use rechargeable camping lantern and emergency light keywords",
                }
            ],
        )
        self.db.add_all([snapshot, diagnosis])
        await self.db.flush()

        data = await detect_lifecycle("B0TENANT07", self.db, user_id=self.user_a.id)
        groups = data["keyword_groups"]
        all_keywords = {keyword for group in groups for keyword in group["keywords"]}

        self.assertEqual(len(groups), 3)
        self.assertIn("rechargeable camping lantern", all_keywords)
        self.assertTrue(any("emergency light" in keyword for keyword in all_keywords))
        self.assertTrue(all(group["source_record_id"] for group in groups))

    async def test_conversion_pipeline_does_not_use_other_users_listing_snapshot(self):
        other_capture = CaptureJob(
            user_id=self.user_b.id,
            input_type="asin",
            input_value="B0TENANT08",
            marketplace="amazon.com",
            status="success",
        )
        self.db.add(other_capture)
        await self.db.flush()
        self.db.add(
            ListingSnapshot(
                capture_job_id=other_capture.id,
                asin="B0TENANT08",
                marketplace="amazon.com",
                title="User B private title",
                ocr_image_texts={"主图": "产品场景吻合度：无法判断"},
            )
        )
        await self.db.flush()

        class FakeProvider:
            async def capture_product_by_asin(self, asin, marketplace):
                return CaptureResult(
                    capture_status="failed",
                    capture_provider="scraperapi",
                    error_message="blocked",
                )

            async def capture_product_by_url(self, url, marketplace):
                return await self.capture_product_by_asin("B0TENANT08", marketplace)

        with patch("app.services.listing_ai_pipeline.ScraperAPIProvider", return_value=FakeProvider()):
            result = await diagnose(
                ConversionDiagnosisRequest(asin="B0TENANT08", marketplace="amazon.com"),
                self.db,
                user_id=self.user_a.id,
            )

        self.assertIsNone(result.product_title)
        self.assertEqual(result.overall_conclusion, "抓取失败")

    async def test_conversion_pipeline_ai_payload_contains_capture_ocr_evidence(self):
        capture = CaptureJob(
            user_id=self.user_a.id,
            input_type="asin",
            input_value="B0TENANT09",
            marketplace="amazon.com",
            status="success",
        )
        self.db.add(capture)
        await self.db.flush()
        snapshot = ListingSnapshot(
            capture_job_id=capture.id,
            asin="B0TENANT09",
            marketplace="amazon.com",
            title="Rechargeable lantern",
            bullet_points=["Rechargeable camping light"],
            ocr_image_texts={"主图": "可见文案：Rechargeable lantern\n产品场景吻合度：吻合"},
        )
        self.db.add(snapshot)
        await self.db.flush()
        captured_payload = {}

        async def fake_complete_json_with_log(**kwargs):
            captured_payload.update(kwargs["input_payload"])
            return {
                "overall_conclusion": "待录入",
                "biggest_breakpoint": "title",
                "priority_position": "title",
                "priority_action": "待录入",
                "impacted_ad_metrics": ["CVR"],
                "current_status": "pending",
                "position_diagnoses": [],
            }

        with patch("app.services.listing_ai_pipeline.complete_json_with_log", side_effect=fake_complete_json_with_log):
            result = await diagnose(
                ConversionDiagnosisRequest(asin="B0TENANT09", marketplace="amazon.com"),
                self.db,
                user_id=self.user_a.id,
            )

        pipeline = captured_payload["pipeline"]

        self.assertEqual(result.product_title, "Rechargeable lantern")
        self.assertEqual(pipeline["capture_job_id"], capture.id)
        self.assertEqual(pipeline["listing_snapshot_id"], snapshot.id)
        self.assertEqual(pipeline["capture_status"], "snapshot")
        self.assertEqual(pipeline["ocr_status"], "success")
        self.assertEqual(captured_payload["listing_data"]["ocr_image_texts"], snapshot.ocr_image_texts)

    async def test_proposition_library_module_ensures_7x7_library(self):
        await ensure_proposition_library(self.db)

        status = await proposition_library_status(self.db)
        propositions = await list_propositions(self.db)

        self.assertTrue(status["complete"])
        self.assertEqual(status["expected_categories"], 7)
        self.assertEqual(status["expected_propositions"], 49)
        self.assertEqual(len(propositions), 49)
        self.assertEqual(propositions[0].proposition_code, "P01-001")

    async def test_asin_operation_tree_module_returns_closed_loop_audit(self):
        await ensure_proposition_library(self.db)
        task = await create_task(
            ValidationTaskCreate(
                asin="B0TENANT10",
                proposition_code="P01-001",
                hypothesis_text="待录入",
            ),
            self.db,
            user_id=self.user_a.id,
        )
        await create_result(
            ValidationResultCreate(
                validation_task_id=task.id,
                asin=task.asin,
                final_result_status="effective",
            ),
            self.db,
            user_id=self.user_a.id,
        )

        audit = await build_closed_loop_audit(self.db, asin=task.asin)

        self.assertEqual(audit["asin"], task.asin)
        self.assertEqual(audit["stages"]["propositions_total"], 49)
        self.assertEqual(len(audit["stages"]["tasks"]), 1)
        self.assertEqual(len(audit["stages"]["results"]), 1)
        self.assertTrue(audit["loop_health"]["profile_synced"])
