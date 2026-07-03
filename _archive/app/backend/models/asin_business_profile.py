from core.database import Base
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)


class AsinBusinessProfile(Base):
    __tablename__ = "asin_profiles"
    __table_args__ = (
        UniqueConstraint("seller_id", "store_id", "marketplace", "asin", name="uq_asin_profile_scope"),
        Index("ix_asin_profile_scope", "seller_id", "store_id", "marketplace", "asin"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)

    sku = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    product_name = Column(Text, nullable=True)
    category = Column(Text, nullable=True)
    launch_date = Column(Date, nullable=True)
    current_price = Column(Float, nullable=True)
    lifecycle_stage = Column(String, nullable=True)

    overall_score = Column(Float, nullable=True)
    traffic_score = Column(Float, nullable=True)
    ctr_score = Column(Float, nullable=True)
    cvr_score = Column(Float, nullable=True)
    ads_score = Column(Float, nullable=True)
    profit_score = Column(Float, nullable=True)
    competition_score = Column(Float, nullable=True)

    title_score = Column(Float, nullable=True)
    main_image_score = Column(Float, nullable=True)
    gallery_score = Column(Float, nullable=True)
    aplus_score = Column(Float, nullable=True)
    bullet_score = Column(Float, nullable=True)
    review_score = Column(Float, nullable=True)
    price_score = Column(Float, nullable=True)

    sessions = Column(Integer, nullable=True)
    ctr = Column(Float, nullable=True)
    cvr = Column(Float, nullable=True)
    organic_sales_ratio = Column(Float, nullable=True)
    ads_sales_ratio = Column(Float, nullable=True)
    acos = Column(Float, nullable=True)
    tacos = Column(Float, nullable=True)
    keyword_count = Column(Integer, nullable=True)

    current_primary_problem = Column(Text, nullable=True)
    priority_actions = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    traffic_dependency = Column(Float, nullable=True)
    listing_dependency = Column(Float, nullable=True)
    advertising_dependency = Column(Float, nullable=True)
    price_sensitivity = Column(Float, nullable=True)
    validation_success_rate = Column(Float, nullable=True)
    next_recommended_action = Column(Text, nullable=True)

    market_demand = Column(Text, nullable=True)
    keyword_opportunities = Column(Text, nullable=True)
    market_capacity = Column(Text, nullable=True)
    competitor_benchmarks = Column(Text, nullable=True)
    traffic_strategy = Column(Text, nullable=True)
    keyword_strategy = Column(Text, nullable=True)
    ad_strategy = Column(Text, nullable=True)

    data_source = Column(String, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AsinDailySnapshot(Base):
    __tablename__ = "asin_daily_snapshots"
    __table_args__ = (
        UniqueConstraint("seller_id", "store_id", "marketplace", "asin", "date", name="uq_asin_daily_snapshot_scope"),
        Index("ix_asin_daily_snapshot_scope", "seller_id", "store_id", "marketplace", "asin", "date"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    sessions = Column(Integer, nullable=True)
    page_views = Column(Integer, nullable=True)
    units_ordered = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    orders = Column(Integer, nullable=True)
    sales = Column(Float, nullable=True)
    impressions = Column(Integer, nullable=True)
    ctr = Column(Float, nullable=True)
    cvr = Column(Float, nullable=True)
    acos = Column(Float, nullable=True)
    tacos = Column(Float, nullable=True)
    ad_spend = Column(Float, nullable=True)
    ad_sales = Column(Float, nullable=True)
    organic_sales = Column(Float, nullable=True)
    total_sales = Column(Float, nullable=True)
    inventory = Column(Integer, nullable=True)
    buybox_status = Column(String, nullable=True)

    source_report_id = Column(String, nullable=True, index=True)
    data_source = Column(String, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReportUpload(Base):
    __tablename__ = "report_uploads"
    __table_args__ = (
        Index("ix_report_upload_scope", "seller_id", "store_id", "report_type"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    report_id = Column(String, nullable=False, unique=True, index=True)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=True, index=True)
    report_type = Column(String, nullable=False, index=True)
    original_filename = Column(String, nullable=True)
    file_path = Column(Text, nullable=True)
    upload_time = Column(DateTime(timezone=True), nullable=True)
    uploaded_by = Column(String, nullable=True)
    parse_status = Column(String, nullable=False, default="Pending")
    parse_error = Column(Text, nullable=True)
    date_range_start = Column(Date, nullable=True)
    date_range_end = Column(Date, nullable=True)
    row_count = Column(Integer, nullable=True)
    matched_rows = Column(Integer, nullable=True)
    unresolved_rows = Column(Integer, nullable=True)
    ambiguous_rows = Column(Integer, nullable=True)
    writable_rows = Column(Integer, nullable=True)
    match_summary = Column(Text, nullable=True)
    source_file_url = Column(Text, nullable=True)
    data_source = Column(String, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ValidationTask(Base):
    __tablename__ = "validation_tasks"
    __table_args__ = (
        Index("ix_validation_task_scope", "seller_id", "store_id", "marketplace", "asin"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    validation_id = Column(String, nullable=False, unique=True, index=True)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    intent_decision_id = Column(String, nullable=True, index=True)
    validation_type = Column(String, nullable=False, index=True)

    problem = Column(Text, nullable=True)
    hypothesis = Column(Text, nullable=True)
    action_plan = Column(Text, nullable=True)
    target_metric = Column(String, nullable=True)
    baseline_start_date = Column(Date, nullable=True)
    baseline_end_date = Column(Date, nullable=True)
    test_start_date = Column(Date, nullable=True)
    test_end_date = Column(Date, nullable=True)
    result_start_date = Column(Date, nullable=True)
    result_end_date = Column(Date, nullable=True)
    baseline_value = Column(Float, nullable=True)
    target_value = Column(Float, nullable=True)
    result_value = Column(Float, nullable=True)
    improvement_rate = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="Pending", index=True)

    data_source = Column(String, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AsinExecutionLog(Base):
    __tablename__ = "asin_execution_logs"
    __table_args__ = (
        Index("ix_asin_execution_log_scope", "validation_id", "asin"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    execution_id = Column(String, nullable=False, unique=True, index=True)
    validation_id = Column(String, ForeignKey("validation_tasks.validation_id"), nullable=False, index=True)
    intent_decision_id = Column(String, nullable=True, index=True)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    action_type = Column(String, nullable=False, index=True)
    before_value = Column(Text, nullable=True)
    after_value = Column(Text, nullable=True)
    executed_by = Column(String, nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    note = Column(Text, nullable=True)
    source = Column(String, nullable=True)
    data_source = Column(String, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AiDecisionTrace(Base):
    __tablename__ = "ai_decision_traces"
    __table_args__ = (
        Index("ix_ai_decision_trace_scope", "seller_id", "store_id", "marketplace", "asin"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    decision_id = Column(String, nullable=False, unique=True, index=True)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    related_validation_id = Column(String, nullable=True, index=True)
    decision_type = Column(String, nullable=False, index=True)
    conclusion = Column(Text, nullable=True)
    input_data_refs = Column(Text, nullable=True)
    evidence_metrics = Column(Text, nullable=True)
    metric_snapshot = Column(Text, nullable=True)
    semantic_evidence = Column(Text, nullable=True)
    reasoning_summary = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    recommended_action = Column(Text, nullable=True)
    prompt_version = Column(String, nullable=True)
    model_name = Column(String, nullable=True)
    data_source = Column(String, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MetricDictionary(Base):
    __tablename__ = "metric_dictionary"
    __table_args__ = (
        UniqueConstraint("metric_key", name="uq_metric_dictionary_key"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    metric_key = Column(String, nullable=False, index=True)
    metric_name = Column(String, nullable=False)
    formula = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ListingVersion(Base):
    __tablename__ = "listing_versions"
    __table_args__ = (
        UniqueConstraint("seller_id", "store_id", "marketplace", "asin", "version", name="uq_listing_version_scope"),
        Index("ix_listing_version_scope", "seller_id", "store_id", "marketplace", "asin"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    version = Column(String, nullable=False)
    modified_at = Column(DateTime(timezone=True), nullable=True)
    change_content = Column(Text, nullable=True)
    change_reason = Column(Text, nullable=True)
    data_source = Column(String, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AsinKeywordProfile(Base):
    __tablename__ = "asin_keyword_profiles"
    __table_args__ = (
        UniqueConstraint("seller_id", "store_id", "marketplace", "asin", "keyword", name="uq_asin_keyword_scope"),
        Index("ix_asin_keyword_profile_scope", "seller_id", "store_id", "marketplace", "asin"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    keyword = Column(String, nullable=False, index=True)
    rank = Column(Integer, nullable=True)
    traffic_share = Column(Float, nullable=True)
    trend = Column(String, nullable=True)
    data_source = Column(String, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AsinSkuMap(Base):
    __tablename__ = "asin_sku_maps"
    __table_args__ = (
        UniqueConstraint("seller_id", "store_id", "marketplace", "sku", name="uq_asin_sku_map_scope"),
        Index("ix_asin_sku_map_scope", "seller_id", "store_id", "marketplace", "asin"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    sku = Column(String, nullable=True, index=True)
    seller_sku = Column(String, nullable=True, index=True)
    product_name = Column(Text, nullable=True)
    status = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AdEntityAsinMap(Base):
    __tablename__ = "ad_entity_asin_maps"
    __table_args__ = (
        Index("ix_ad_entity_asin_map_scope", "seller_id", "store_id", "marketplace", "asin"),
        Index("ix_ad_entity_asin_map_entity", "campaign_id", "ad_group_id", "ad_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    sku = Column(String, nullable=True, index=True)
    campaign_id = Column(String, nullable=True, index=True)
    campaign_name = Column(Text, nullable=True)
    ad_group_id = Column(String, nullable=True, index=True)
    ad_group_name = Column(Text, nullable=True)
    ad_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ReportRowStaging(Base):
    __tablename__ = "report_row_staging"
    __table_args__ = (
        Index("ix_report_row_staging_scope", "seller_id", "store_id", "marketplace", "asin"),
        Index("ix_report_row_staging_report", "report_id", "match_status"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    report_id = Column(String, nullable=False, index=True)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=True, index=True)
    date = Column(Date, nullable=True, index=True)
    row_number = Column(Integer, nullable=False)
    report_type = Column(String, nullable=False, index=True)
    match_status = Column(String, nullable=False, index=True)
    match_method = Column(String, nullable=True)
    extracted_asin = Column(String, nullable=True, index=True)
    extracted_sku = Column(String, nullable=True, index=True)
    campaign_id = Column(String, nullable=True, index=True)
    ad_group_id = Column(String, nullable=True, index=True)
    ad_id = Column(String, nullable=True, index=True)
    matched_asin = Column(String, nullable=True, index=True)
    candidate_matches = Column(Text, nullable=True)
    is_writable = Column(Boolean, nullable=False, default=False)
    resolution_status = Column(String, nullable=True, index=True)
    raw_data = Column(Text, nullable=True)
    normalized_data = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdProductDaily(Base):
    __tablename__ = "ad_product_daily"
    __table_args__ = (
        Index("ix_ad_product_daily_scope", "seller_id", "store_id", "marketplace", "asin", "date"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    sku = Column(String, nullable=True, index=True)
    date = Column(Date, nullable=False, index=True)
    campaign_name = Column(Text, nullable=True)
    campaign_id = Column(String, nullable=True, index=True)
    ad_group_name = Column(Text, nullable=True)
    ad_group_id = Column(String, nullable=True, index=True)
    impressions = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    spend = Column(Float, nullable=True)
    sales = Column(Float, nullable=True)
    orders = Column(Integer, nullable=True)
    units = Column(Integer, nullable=True)
    ctr = Column(Float, nullable=True)
    cpc = Column(Float, nullable=True)
    acos = Column(Float, nullable=True)
    roas = Column(Float, nullable=True)
    source_report_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdSearchTermDaily(Base):
    __tablename__ = "ad_search_term_daily"
    __table_args__ = (
        Index("ix_ad_search_term_daily_scope", "seller_id", "store_id", "marketplace", "asin", "date"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    period_start = Column(Date, nullable=True, index=True)
    period_end = Column(Date, nullable=True, index=True)
    campaign_name = Column(Text, nullable=True)
    ad_group_name = Column(Text, nullable=True)
    keyword = Column(Text, nullable=True)
    match_type = Column(String, nullable=True)
    customer_search_term = Column(Text, nullable=True)
    impressions = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    spend = Column(Float, nullable=True)
    sales = Column(Float, nullable=True)
    orders = Column(Integer, nullable=True)
    units = Column(Integer, nullable=True)
    ctr = Column(Float, nullable=True)
    cpc = Column(Float, nullable=True)
    acos = Column(Float, nullable=True)
    roas = Column(Float, nullable=True)
    source_report_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdTargetDaily(Base):
    __tablename__ = "ad_target_daily"
    __table_args__ = (
        Index("ix_ad_target_daily_scope", "seller_id", "store_id", "marketplace", "asin", "date"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    period_start = Column(Date, nullable=True, index=True)
    period_end = Column(Date, nullable=True, index=True)
    campaign_name = Column(Text, nullable=True)
    ad_group_name = Column(Text, nullable=True)
    targeting = Column(Text, nullable=True)
    targeting_type = Column(String, nullable=True)
    match_type = Column(String, nullable=True)
    impressions = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    spend = Column(Float, nullable=True)
    sales = Column(Float, nullable=True)
    orders = Column(Integer, nullable=True)
    units = Column(Integer, nullable=True)
    ctr = Column(Float, nullable=True)
    cpc = Column(Float, nullable=True)
    acos = Column(Float, nullable=True)
    roas = Column(Float, nullable=True)
    source_report_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AsinListingSnapshot(Base):
    __tablename__ = "asin_listing_snapshots"
    __table_args__ = (
        Index("ix_asin_listing_snapshot_scope", "seller_id", "store_id", "marketplace", "asin", "snapshot_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    title = Column(Text, nullable=True)
    bullet_points = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    aplus = Column(Text, nullable=True)
    main_image = Column(Text, nullable=True)
    secondary_images = Column(Text, nullable=True)
    backend_terms = Column(Text, nullable=True)
    price = Column(Float, nullable=True)
    coupon = Column(Text, nullable=True)
    snapshot_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    data_source = Column(String, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AsinIntentDecision(Base):
    __tablename__ = "asin_intent_decisions"
    __table_args__ = (
        Index("ix_asin_intent_decision_scope", "seller_id", "store_id", "marketplace", "asin"),
        Index("ix_asin_intent_decision_status", "status", "recommended_action"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    intent_decision_id = Column(String, nullable=False, unique=True, index=True)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    intent_name = Column(String, nullable=False, index=True)
    intent_description = Column(Text, nullable=True)
    position_reception_result = Column(Text, nullable=True)
    semantic_audit_result = Column(Text, nullable=True)
    buyer_language_result = Column(Text, nullable=True)
    intent_evidence_status = Column(String, nullable=True)
    product_platform_safety_status = Column(String, nullable=True)
    investment_value_status = Column(String, nullable=True)
    reception_gap = Column(Text, nullable=True)
    safe_expression = Column(Text, nullable=True)
    blocked_expression = Column(Text, nullable=True)
    recommended_action = Column(String, nullable=False, index=True)
    priority_score = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    validation_task_id = Column(String, nullable=True, index=True)
    validation_result = Column(String, nullable=True)
    status = Column(String, nullable=False, default="Candidate", index=True)
    data_source = Column(String, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AsinIntentEvidence(Base):
    __tablename__ = "asin_intent_evidence"
    __table_args__ = (
        Index("ix_asin_intent_evidence_scope", "seller_id", "store_id", "marketplace", "asin"),
        Index("ix_asin_intent_evidence_decision", "intent_decision_id", "source_type"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    evidence_id = Column(String, nullable=False, unique=True, index=True)
    intent_decision_id = Column(String, nullable=False, index=True)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    intent_name = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False, index=True)
    evidence_text = Column(Text, nullable=True)
    metric_snapshot = Column(Text, nullable=True)
    strength_score = Column(Float, nullable=True)
    data_source = Column(String, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AsinSafeExpression(Base):
    __tablename__ = "asin_safe_expressions"
    __table_args__ = (
        Index("ix_asin_safe_expression_scope", "seller_id", "store_id", "marketplace", "asin"),
        Index("ix_asin_safe_expression_decision", "intent_decision_id", "status"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    safe_expression_id = Column(String, nullable=False, unique=True, index=True)
    intent_decision_id = Column(String, nullable=True, index=True)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    buyer_language = Column(Text, nullable=True)
    seller_language = Column(Text, nullable=True)
    safe_expression = Column(Text, nullable=True)
    blocked_expression = Column(Text, nullable=True)
    risk_reason = Column(Text, nullable=True)
    evidence_required = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="Needs Evidence", index=True)
    data_source = Column(String, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AsinAiMemory(Base):
    __tablename__ = "asin_ai_memory"
    __table_args__ = (
        UniqueConstraint("seller_id", "store_id", "marketplace", "asin", name="uq_asin_ai_memory_scope"),
        Index("ix_asin_ai_memory_scope", "seller_id", "store_id", "marketplace", "asin"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    seller_id = Column(String, nullable=False, index=True)
    store_id = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    validated_intents = Column(Text, nullable=True)
    failed_intents = Column(Text, nullable=True)
    current_main_bottleneck = Column(Text, nullable=True)
    current_listing_gap = Column(Text, nullable=True)
    current_traffic_problem = Column(Text, nullable=True)
    next_best_hypothesis = Column(Text, nullable=True)
    proven_actions = Column(Text, nullable=True)
    failed_actions = Column(Text, nullable=True)
    latest_learning = Column(Text, nullable=True)
    data_source = Column(String, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
