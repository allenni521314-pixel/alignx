from __future__ import annotations
"""AlignX V1 — SQLAlchemy ORM models (13 tables per V1 Clean Architecture)."""

import uuid
import time
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def new_uuid() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.utcnow()


# ═══════════════════════════════════════════
# 1. Users
# ═══════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    id          = Column(String(32), primary_key=True, default=new_uuid)
    email       = Column(String(255), unique=True, nullable=False, index=True)
    name        = Column(String(255), nullable=False)
    role        = Column(String(32), nullable=False, default="seller")  # seller | admin
    created_at  = Column(DateTime, nullable=False, default=utcnow)

    stores      = relationship("Store", back_populates="user")
    account     = relationship("Account", back_populates="user", uselist=False)


class VerificationCode(Base):
    __tablename__ = "verification_codes"
    id          = Column(String(32), primary_key=True, default=new_uuid)
    email       = Column(String(255), nullable=False, index=True)
    code        = Column(String(6), nullable=False)
    expires_at  = Column(Float, nullable=False)
    created_at  = Column(Float, default=time.time)


# ═══════════════════════════════════════════
# 2. Accounts
# ═══════════════════════════════════════════

class Account(Base):
    __tablename__ = "accounts"

    id          = Column(String(32), primary_key=True, default=new_uuid)
    user_id         = Column(String(32), ForeignKey("users.id"), nullable=False, default="00000000default0000000000000000", unique=True)
    plan        = Column(String(32), nullable=False, default="free")  # free | pro | enterprise
    balance     = Column(Float, nullable=False, default=0.0)
    total_calls = Column(Integer, nullable=False, default=0)
    used_calls  = Column(Integer, nullable=False, default=0)
    created_at  = Column(DateTime, nullable=False, default=utcnow)

    user = relationship("User", back_populates="account")


# ═══════════════════════════════════════════
# 3. Stores
# ═══════════════════════════════════════════

class Store(Base):
    __tablename__ = "stores"

    id          = Column(String(32), primary_key=True, default=new_uuid)
    user_id         = Column(String(32), ForeignKey("users.id"), nullable=False, default="00000000default0000000000000000", index=True)
    marketplace = Column(String(16), nullable=False, default="amazon.com")  # amazon.com | amazon.co.jp | ...
    store_name  = Column(String(255), nullable=False)
    seller_id   = Column(String(64), nullable=True)
    created_at  = Column(DateTime, nullable=False, default=utcnow)

    user  = relationship("User", back_populates="stores")
    asins = relationship("Asin", back_populates="store")


# ═══════════════════════════════════════════
# 4. ASINs
# ═══════════════════════════════════════════

class Asin(Base):
    __tablename__ = "asins"

    id              = Column(String(32), primary_key=True, default=new_uuid)
    user_id         = Column(String(32), ForeignKey("users.id"), nullable=False, default="00000000default0000000000000000", index=True)
    store_id        = Column(String(32), ForeignKey("stores.id"), nullable=True)

    asin            = Column(String(16), nullable=False, index=True)
    parent_asin     = Column(String(16), nullable=True)
    marketplace     = Column(String(16), nullable=False, default="amazon.com")
    product_title   = Column(Text, nullable=True)
    brand           = Column(String(255), nullable=True)
    category        = Column(String(255), nullable=True)
    subcategory     = Column(String(255), nullable=True)
    sp_api_product_type = Column(String(128), nullable=True)
    sp_api_product_type_version = Column(String(64), nullable=True)
    sp_api_product_type_schema_version = Column(String(64), nullable=True)
    sp_api_product_type_synced_at = Column(DateTime, nullable=True)
    lifecycle_stage = Column(String(32), nullable=True)  # prelaunch | active | declining | retired
    created_at      = Column(DateTime, nullable=False, default=utcnow)
    updated_at      = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    store = relationship("Store", back_populates="asins")


# ═══════════════════════════════════════════
# 5. Capture Jobs
# ═══════════════════════════════════════════

class CaptureJob(Base):
    __tablename__ = "capture_jobs"

    id                = Column(String(32), primary_key=True, default=new_uuid)
    user_id         = Column(String(32), ForeignKey("users.id"), nullable=False, default="00000000default0000000000000000", index=True)
    input_type        = Column(String(16), nullable=False)  # keyword | asin | product_url
    input_value       = Column(Text, nullable=False)
    marketplace       = Column(String(16), nullable=False, default="amazon.com")
    provider          = Column(String(32), nullable=False, default="scraperapi")  # scraperapi | rainforest | manual
    status            = Column(String(16), nullable=False, default="pending")  # pending | running | success | partial | failed
    raw_html_path     = Column(Text, nullable=True)
    screenshot_path   = Column(Text, nullable=True)
    raw_response_path = Column(Text, nullable=True)
    started_at        = Column(DateTime, nullable=True)
    finished_at       = Column(DateTime, nullable=True)
    error_message     = Column(Text, nullable=True)


# ═══════════════════════════════════════════
# 6. Listing Snapshots
# ═══════════════════════════════════════════

class ListingSnapshot(Base):
    __tablename__ = "listing_snapshots"

    id                       = Column(String(32), primary_key=True, default=new_uuid)
    capture_job_id           = Column(String(32), ForeignKey("capture_jobs.id"), nullable=False)
    asin                     = Column(String(16), nullable=False, index=True)
    marketplace              = Column(String(16), nullable=False, default="amazon.com")

    title                    = Column(Text, nullable=True)
    price                    = Column(String(32), nullable=True)
    price_value              = Column(Float, nullable=True)
    currency                 = Column(String(8), nullable=True)
    rating                   = Column(Float, nullable=True)
    review_count             = Column(Integer, nullable=True)
    bought_in_past_month_raw = Column(String(64), nullable=True)
    bought_in_past_month_value = Column(Integer, nullable=True)
    revenue_floor_30d        = Column(Float, nullable=True)
    first_available_date     = Column(String(32), nullable=True)
    availability             = Column(String(32), nullable=True)

    main_image               = Column(Text, nullable=True)
    image_urls               = Column(JSON(none_as_null=True), nullable=True)
    bullet_points            = Column(JSON(none_as_null=True), nullable=True)
    aplus_content            = Column(JSON(none_as_null=True), nullable=True)
    product_details          = Column(JSON(none_as_null=True), nullable=True)
    ocr_image_texts          = Column(JSON(none_as_null=True), nullable=True)
    ai_readability_score_json = Column(JSON(none_as_null=True), nullable=True)
    ai_readability_score_version = Column(String(64), nullable=True)
    review_summary           = Column(Text, nullable=True)
    negative_review_summary  = Column(Text, nullable=True)

    parse_status             = Column(String(16), nullable=True)  # success | partial | failed
    missing_fields           = Column(JSON, nullable=True)
    field_completeness_score = Column(Float, nullable=True)
    created_at               = Column(DateTime, nullable=False, default=utcnow)


# ═══════════════════════════════════════════
# 7. Market Opportunity Reports
# ═══════════════════════════════════════════

class MarketOpportunityReport(Base):
    __tablename__ = "market_opportunity_reports"

    id                          = Column(String(32), primary_key=True, default=new_uuid)
    user_id         = Column(String(32), ForeignKey("users.id"), nullable=False, default="00000000default0000000000000000", index=True)
    keyword                     = Column(String(255), nullable=False)
    marketplace                 = Column(String(16), nullable=False, default="amazon.com")
    category                    = Column(String(255), nullable=True)
    subcategory                 = Column(String(255), nullable=True)
    category_confidence         = Column(Float, nullable=True)

    opportunity_score           = Column(Float, nullable=True)
    entry_level                 = Column(String(32), nullable=True)  # 强建议进入 | 谨慎进入 | 不建议进入
    market_entry_conclusion     = Column(Text, nullable=True)
    top20_competition_strength  = Column(String(32), nullable=True)  # 低 | 中 | 高 | 极高
    price_band_judgment         = Column(Text, nullable=True)
    main_risk                   = Column(Text, nullable=True)
    next_action                 = Column(Text, nullable=True)

    seven_layer_result_json     = Column(JSON, nullable=True)
    created_at                  = Column(DateTime, nullable=False, default=utcnow)


# ═══════════════════════════════════════════
# 8. Competitor Analysis Reports
# ═══════════════════════════════════════════

class CompetitorAnalysisReport(Base):
    __tablename__ = "competitor_analysis_reports"

    id                       = Column(String(32), primary_key=True, default=new_uuid)
    user_id         = Column(String(32), ForeignKey("users.id"), nullable=False, default="00000000default0000000000000000", index=True)
    asin                     = Column(String(16), nullable=False)
    product_url              = Column(Text, nullable=True)
    marketplace              = Column(String(16), nullable=False, default="amazon.com")

    product_title            = Column(Text, nullable=True)
    brand                    = Column(String(255), nullable=True)
    seller_name              = Column(String(255), nullable=True)
    store_name               = Column(String(255), nullable=True)
    category                 = Column(String(255), nullable=True)
    subcategory              = Column(String(255), nullable=True)

    price                    = Column(String(32), nullable=True)
    rating                   = Column(Float, nullable=True)
    review_count             = Column(Integer, nullable=True)
    bought_in_past_month_raw = Column(String(64), nullable=True)
    revenue_floor_30d        = Column(Float, nullable=True)

    overall_judgment         = Column(Text, nullable=True)
    main_strengths           = Column(JSON, nullable=True)
    main_weaknesses          = Column(JSON, nullable=True)
    attack_points            = Column(JSON, nullable=True)
    worth_benchmarking       = Column(Boolean, nullable=True)

    listing_presentation_json = Column(JSON, nullable=True)
    twelve_dimension_result_json = Column(JSON, nullable=True)
    created_at                = Column(DateTime, nullable=False, default=utcnow)


# ═══════════════════════════════════════════
# 9. Pre-launch Checks
# ═══════════════════════════════════════════

class PrelaunchCheck(Base):
    __tablename__ = "prelaunch_checks"

    id              = Column(String(32), primary_key=True, default=new_uuid)
    user_id         = Column(String(32), ForeignKey("users.id"), nullable=False, default="00000000default0000000000000000", index=True)
    product_name    = Column(String(255), nullable=False)
    marketplace     = Column(String(16), nullable=False, default="amazon.com")

    title_draft     = Column(Text, nullable=True)
    key_highlights  = Column(Text, nullable=True)
    bullet_1        = Column(Text, nullable=True)
    bullet_2        = Column(Text, nullable=True)
    bullet_3        = Column(Text, nullable=True)
    bullet_4        = Column(Text, nullable=True)
    bullet_5        = Column(Text, nullable=True)

    main_image_path  = Column(Text, nullable=True)
    image_2_path     = Column(Text, nullable=True)
    image_3_path     = Column(Text, nullable=True)
    image_4_path     = Column(Text, nullable=True)
    image_5_path     = Column(Text, nullable=True)
    image_6_path     = Column(Text, nullable=True)
    image_7_path     = Column(Text, nullable=True)
    aplus_images_json = Column(JSON, nullable=True)

    admission_result      = Column(String(32), nullable=True)  # 可以上架 | 谨慎上架 | 暂不建议上架
    conclusion            = Column(Text, nullable=True)
    position_diagnoses_json = Column(JSON, nullable=True)
    next_action           = Column(Text, nullable=True)
    created_at            = Column(DateTime, nullable=False, default=utcnow)


# ═══════════════════════════════════════════
# 10. Conversion Diagnoses
# ═══════════════════════════════════════════

class ConversionDiagnosis(Base):
    __tablename__ = "conversion_diagnoses"

    id                              = Column(String(32), primary_key=True, default=new_uuid)
    user_id         = Column(String(32), ForeignKey("users.id"), nullable=False, default="00000000default0000000000000000", index=True)
    asin                            = Column(String(16), nullable=False)
    product_url                     = Column(Text, nullable=True)
    marketplace                     = Column(String(16), nullable=False, default="amazon.com")
    product_title                   = Column(Text, nullable=True)

    overall_conclusion              = Column(Text, nullable=True)
    biggest_breakpoint              = Column(String(255), nullable=True)
    priority_position               = Column(String(255), nullable=True)
    priority_action                 = Column(Text, nullable=True)
    impacted_ad_metrics             = Column(JSON, nullable=True)
    current_status                  = Column(String(32), nullable=True)

    position_diagnoses_json         = Column(JSON, nullable=True)
    ai_readability_score_json       = Column(JSON, nullable=True)
    ai_readability_score_version    = Column(String(64), nullable=True)
    primary_matched_proposition_code = Column(String(16), nullable=True)
    created_at                      = Column(DateTime, nullable=False, default=utcnow)


# ═══════════════════════════════════════════
# 11. Proposition Library
# ═══════════════════════════════════════════

class PropositionCategory(Base):
    __tablename__ = "proposition_categories"

    id            = Column(String(32), primary_key=True, default=new_uuid)
    category_code = Column(String(8), nullable=False, unique=True, index=True)  # P01 - P07
    category_name = Column(String(255), nullable=False)
    description   = Column(Text, nullable=True)
    archived      = Column(Boolean, nullable=False, default=False)
    created_at    = Column(DateTime, nullable=False, default=utcnow)

    propositions = relationship("Proposition", back_populates="category")


class Proposition(Base):
    __tablename__ = "propositions"

    id                       = Column(String(32), primary_key=True, default=new_uuid)
    proposition_code         = Column(String(16), nullable=False, unique=True, index=True)  # P01-001 ~ P07-007
    category_code            = Column(String(8), ForeignKey("proposition_categories.category_code"), nullable=False)

    name                     = Column(String(255), nullable=False)
    definition               = Column(Text, nullable=True)
    applicable_conditions    = Column(Text, nullable=True)
    required_evidence        = Column(Text, nullable=True)
    recommended_action       = Column(Text, nullable=True)
    controlled_variable      = Column(Text, nullable=True)
    success_criteria         = Column(Text, nullable=True)
    failure_criteria         = Column(Text, nullable=True)
    next_proposition_if_failed = Column(String(16), nullable=True)

    archived    = Column(Boolean, nullable=False, default=False)
    created_at  = Column(DateTime, nullable=False, default=utcnow)

    category = relationship("PropositionCategory", back_populates="propositions")


# ═══════════════════════════════════════════
# 12. Validation Tasks
# ═══════════════════════════════════════════

class ValidationTask(Base):
    __tablename__ = "validation_tasks"

    id                           = Column(String(32), primary_key=True, default=new_uuid)
    user_id         = Column(String(32), ForeignKey("users.id"), nullable=False, default="00000000default0000000000000000", index=True)
    asin                         = Column(String(16), nullable=False)
    proposition_code             = Column(String(16), nullable=False)
    proposition_name             = Column(String(255), nullable=True)

    source_module                = Column(String(64), nullable=True)  # conversion_diagnosis | ad_strategy | manual
    source_record_id             = Column(String(32), nullable=True)

    hypothesis_text              = Column(Text, nullable=True)
    evidence_snapshot            = Column(JSON, nullable=True)
    controlled_variable          = Column(Text, nullable=True)
    forbidden_simultaneous_changes = Column(JSON, nullable=True)
    validation_period            = Column(String(32), nullable=True)  # 7d | 14d | 30d

    success_criteria             = Column(Text, nullable=True)
    failure_criteria             = Column(Text, nullable=True)

    execution_status             = Column(String(32), nullable=False, default="pending")  # pending | running | completed
    result_status                = Column(String(32), nullable=True)  # effective | ineffective | interfered | insufficient_data
    next_action                  = Column(Text, nullable=True)
    created_at                   = Column(DateTime, nullable=False, default=utcnow)


# ═══════════════════════════════════════════
# 13. Execution Records
# ═══════════════════════════════════════════

class ExecutionRecord(Base):
    __tablename__ = "execution_records"

    id                  = Column(String(32), primary_key=True, default=new_uuid)
    user_id             = Column(String(32), nullable=False, default="00000000default0000000000000000")
    validation_task_id  = Column(String(32), ForeignKey("validation_tasks.id"), nullable=False, index=True)
    asin                = Column(String(16), nullable=False)

    executed_at         = Column(DateTime, nullable=False, default=utcnow)
    executor            = Column(String(255), nullable=True)
    action_summary      = Column(Text, nullable=True)
    changed_variable    = Column(String(255), nullable=True)
    changed_position    = Column(String(255), nullable=True)
    change_detail       = Column(Text, nullable=True)
    cost_amount         = Column(Float, nullable=True)
    cost_type           = Column(String(32), nullable=True)  # ad_spend | design_cost | other
    evidence_note       = Column(Text, nullable=True)
    created_at          = Column(DateTime, nullable=False, default=utcnow)


# ═══════════════════════════════════════════
# 14. Validation Results
# ═══════════════════════════════════════════

class ValidationResult(Base):
    __tablename__ = "validation_results"

    id                      = Column(String(32), primary_key=True, default=new_uuid)
    user_id                 = Column(String(32), nullable=False, default="00000000default0000000000000000")
    validation_task_id      = Column(String(32), ForeignKey("validation_tasks.id"), nullable=False, index=True)
    asin                    = Column(String(16), nullable=False)

    baseline_metrics_json   = Column(JSON, nullable=True)
    result_metrics_json     = Column(JSON, nullable=True)
    sample_days             = Column(Integer, nullable=True)
    sample_clicks           = Column(Integer, nullable=True)
    sample_orders           = Column(Integer, nullable=True)

    suggested_result_status = Column(String(32), nullable=True)
    final_result_status     = Column(String(32), nullable=True)  # effective | ineffective | interfered | insufficient_data
    attribution_conclusion  = Column(Text, nullable=True)
    notes                   = Column(Text, nullable=True)
    created_at              = Column(DateTime, nullable=False, default=utcnow)


# ═══════════════════════════════════════════
# 15. ASIN Operation Profiles
# ═══════════════════════════════════════════

class AsinOperationProfile(Base):
    __tablename__ = "asin_operation_profiles"

    id                           = Column(String(32), primary_key=True, default=new_uuid)
    user_id         = Column(String(32), ForeignKey("users.id"), nullable=False, default="00000000default0000000000000000", index=True)
    asin                         = Column(String(16), nullable=False, index=True)
    marketplace                  = Column(String(16), nullable=False, default="amazon.com", index=True)
    product_title                = Column(Text, nullable=True)
    category                     = Column(String(255), nullable=True)
    lifecycle_stage              = Column(String(32), nullable=True)

    total_validation_count       = Column(Integer, nullable=False, default=0)
    effective_count              = Column(Integer, nullable=False, default=0)
    ineffective_count            = Column(Integer, nullable=False, default=0)
    interfered_count             = Column(Integer, nullable=False, default=0)
    insufficient_data_count      = Column(Integer, nullable=False, default=0)

    successful_propositions_json = Column(JSON, nullable=True)
    failed_propositions_json     = Column(JSON, nullable=True)
    repeated_failure_patterns_json = Column(JSON, nullable=True)

    current_main_problem         = Column(Text, nullable=True)
    next_recommended_proposition = Column(String(16), nullable=True)
    asin_learning_summary        = Column(Text, nullable=True)
    updated_at                   = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


# ═══════════════════════════════════════════
# 16. AI Call Logs
# ═══════════════════════════════════════════

class AiCallLog(Base):
    __tablename__ = "ai_call_logs"

    id                = Column(String(32), primary_key=True, default=new_uuid)
    ai_call_id        = Column(String(32), nullable=False, default=new_uuid, unique=True, index=True)
    user_id           = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    store_id          = Column(String(32), ForeignKey("stores.id"), nullable=True)
    asin              = Column(String(16), nullable=True, index=True)
    module_name       = Column(String(64), nullable=False, index=True)
    model_name        = Column(String(64), nullable=False)
    model_provider    = Column(String(64), nullable=False)
    prompt_version    = Column(String(64), nullable=False)
    input_payload     = Column(JSON, nullable=True)
    output_raw        = Column(Text, nullable=True)
    output_parsed     = Column(JSON, nullable=True)
    confidence_score  = Column(Float, nullable=True)
    risk_flags        = Column(JSON, nullable=True)
    error_message     = Column(Text, nullable=True)
    token_usage       = Column(Integer, nullable=True)
    cost_estimate     = Column(Float, nullable=True)
    created_at        = Column(DateTime, nullable=False, default=utcnow)


# ═══════════════════════════════════════════
# 17. Uploaded Report Staging
# ═══════════════════════════════════════════

class ReportUploadBatch(Base):
    __tablename__ = "report_upload_batches"

    id                = Column(String(32), primary_key=True, default=new_uuid)
    user_id           = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    store_id          = Column(String(32), ForeignKey("stores.id"), nullable=True)
    marketplace       = Column(String(16), nullable=False, default="amazon.com", index=True)
    report_type       = Column(String(64), nullable=False, default="advertising")
    source_type       = Column(String(64), nullable=False, default="uploaded_report")
    source_filename   = Column(String(255), nullable=True)
    total_rows        = Column(Integer, nullable=False, default=0)
    resolved_count    = Column(Integer, nullable=False, default=0)
    ambiguous_count   = Column(Integer, nullable=False, default=0)
    unresolved_count  = Column(Integer, nullable=False, default=0)
    created_at        = Column(DateTime, nullable=False, default=utcnow)


class ReportUploadStagingRecord(Base):
    __tablename__ = "report_upload_staging_records"

    id                      = Column(String(32), primary_key=True, default=new_uuid)
    batch_id                = Column(String(32), ForeignKey("report_upload_batches.id"), nullable=False, index=True)
    user_id                 = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    store_id                = Column(String(32), ForeignKey("stores.id"), nullable=True)
    marketplace             = Column(String(16), nullable=False, default="amazon.com", index=True)
    report_type             = Column(String(64), nullable=False, default="advertising")
    source_type             = Column(String(64), nullable=False, default="uploaded_report")
    source_record_id        = Column(String(32), nullable=True, index=True)
    asin_id                 = Column(String(32), ForeignKey("asins.id"), nullable=True, index=True)
    asin                    = Column(String(16), nullable=True, index=True)
    sku                     = Column(String(128), nullable=True, index=True)
    campaign                = Column(String(255), nullable=True)
    ad_group                = Column(String(255), nullable=True)
    keyword                 = Column(String(255), nullable=True)
    target                  = Column(String(255), nullable=True)
    report_date             = Column(String(32), nullable=True, index=True)
    attribution_status      = Column(String(32), nullable=False, default="unresolved", index=True)
    asin_attribution_status = Column(String(32), nullable=False, default="missing", index=True)
    validation_task_id      = Column(String(32), ForeignKey("validation_tasks.id"), nullable=True, index=True)
    execution_record_id     = Column(String(32), ForeignKey("execution_records.id"), nullable=True, index=True)
    raw_row_json            = Column(JSON, nullable=True)
    normalized_metrics_json = Column(JSON, nullable=True)
    resolution_note         = Column(Text, nullable=True)
    confirmed_at            = Column(DateTime, nullable=True)
    created_at              = Column(DateTime, nullable=False, default=utcnow)


# ═══════════════════════════════════════════
# 18. Operation Audit Logs
# ═══════════════════════════════════════════

class OperationAuditLog(Base):
    __tablename__ = "operation_audit_logs"

    id              = Column(String(32), primary_key=True, default=new_uuid)
    user_id         = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    store_id        = Column(String(32), ForeignKey("stores.id"), nullable=True)
    asin            = Column(String(16), nullable=True, index=True)
    module_name     = Column(String(64), nullable=False, index=True)
    action          = Column(String(64), nullable=False, index=True)
    entity_type     = Column(String(64), nullable=False)
    entity_id       = Column(String(32), nullable=True, index=True)
    source_type     = Column(String(64), nullable=True)
    before_json     = Column(JSON, nullable=True)
    after_json      = Column(JSON, nullable=True)
    created_at      = Column(DateTime, nullable=False, default=utcnow)
