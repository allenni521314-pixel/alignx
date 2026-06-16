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
    clicks = Column(Integer, nullable=True)
    orders = Column(Integer, nullable=True)
    sales = Column(Float, nullable=True)
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
    upload_time = Column(DateTime(timezone=True), nullable=True)
    parse_status = Column(String, nullable=False, default="Pending")
    parse_error = Column(Text, nullable=True)
    date_range_start = Column(Date, nullable=True)
    date_range_end = Column(Date, nullable=True)
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
    evidence_metrics = Column(Text, nullable=True)
    reasoning_summary = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    recommended_action = Column(Text, nullable=True)
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
