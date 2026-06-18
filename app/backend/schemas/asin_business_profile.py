from datetime import date as date_type, datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class AsinProfileKey(BaseModel):
    seller_id: str
    store_id: str
    marketplace: str
    asin: str


class AsinProfileUpsert(BaseModel):
    store_id: str = "default"
    marketplace: str = "US"
    asin: str
    sku: Optional[str] = None
    brand: Optional[str] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    launch_date: Optional[date_type] = None
    current_price: Optional[float] = None
    lifecycle_stage: Optional[str] = None
    data_source: Optional[str] = None
    is_demo: bool = False


class AsinProfileResponse(BaseModel):
    id: int
    seller_id: str
    store_id: str
    marketplace: str
    asin: str
    sku: Optional[str] = None
    brand: Optional[str] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    launch_date: Optional[date_type] = None
    current_price: Optional[float] = None
    lifecycle_stage: Optional[str] = None
    overall_score: Optional[float] = None
    traffic_score: Optional[float] = None
    ctr_score: Optional[float] = None
    cvr_score: Optional[float] = None
    ads_score: Optional[float] = None
    profit_score: Optional[float] = None
    competition_score: Optional[float] = None
    title_score: Optional[float] = None
    main_image_score: Optional[float] = None
    gallery_score: Optional[float] = None
    aplus_score: Optional[float] = None
    bullet_score: Optional[float] = None
    review_score: Optional[float] = None
    price_score: Optional[float] = None
    current_primary_problem: Optional[str] = None
    priority_actions: Optional[str] = None
    confidence_score: Optional[float] = None
    data_source: Optional[str] = None
    is_demo: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AsinProfileListResponse(BaseModel):
    items: List[AsinProfileResponse]
    total: int
    skip: int
    limit: int


class DailySnapshotResponse(BaseModel):
    id: int
    seller_id: str
    store_id: str
    marketplace: str
    asin: str
    date: date_type
    sessions: Optional[int] = None
    page_views: Optional[int] = None
    units_ordered: Optional[int] = None
    clicks: Optional[int] = None
    orders: Optional[int] = None
    sales: Optional[float] = None
    impressions: Optional[int] = None
    ctr: Optional[float] = None
    cvr: Optional[float] = None
    acos: Optional[float] = None
    tacos: Optional[float] = None
    ad_spend: Optional[float] = None
    ad_sales: Optional[float] = None
    organic_sales: Optional[float] = None
    total_sales: Optional[float] = None
    inventory: Optional[int] = None
    buybox_status: Optional[str] = None
    source_report_id: Optional[str] = None
    data_source: Optional[str] = None
    is_demo: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DailySnapshotCreate(BaseModel):
    store_id: str = "default"
    marketplace: str = "US"
    asin: str
    date: date_type
    sessions: Optional[int] = None
    page_views: Optional[int] = None
    units_ordered: Optional[int] = None
    clicks: Optional[int] = None
    orders: Optional[int] = None
    sales: Optional[float] = None
    impressions: Optional[int] = None
    ctr: Optional[float] = None
    cvr: Optional[float] = None
    acos: Optional[float] = None
    tacos: Optional[float] = None
    ad_spend: Optional[float] = None
    ad_sales: Optional[float] = None
    organic_sales: Optional[float] = None
    total_sales: Optional[float] = None
    inventory: Optional[int] = None
    buybox_status: Optional[str] = None
    source_report_id: Optional[str] = None
    data_source: Optional[str] = None
    is_demo: bool = False


class DailySnapshotListResponse(BaseModel):
    items: List[DailySnapshotResponse]
    total: int
    skip: int
    limit: int


class ReportUploadCreate(BaseModel):
    store_id: str = "default"
    marketplace: Optional[str] = "US"
    report_type: str
    original_filename: Optional[str] = None
    file_path: Optional[str] = None
    uploaded_by: Optional[str] = None
    parse_status: str = "Pending"
    parse_error: Optional[str] = None
    date_range_start: Optional[date_type] = None
    date_range_end: Optional[date_type] = None
    row_count: Optional[int] = None
    source_file_url: Optional[str] = None
    data_source: Optional[str] = None
    is_demo: bool = False


class ReportUploadResponse(BaseModel):
    report_id: str
    seller_id: str
    store_id: str
    marketplace: Optional[str] = None
    report_type: str
    original_filename: Optional[str] = None
    file_path: Optional[str] = None
    upload_time: Optional[datetime] = None
    uploaded_by: Optional[str] = None
    parse_status: str
    parse_error: Optional[str] = None
    date_range_start: Optional[date_type] = None
    date_range_end: Optional[date_type] = None
    row_count: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReportParseSummary(BaseModel):
    report_id: str
    report_type: str
    parse_status: str
    total_rows: int
    matched_asin_rows: int
    unmatched_rows: int
    ambiguous_rows: int
    writable_rows: int


class StagingRowResponse(BaseModel):
    id: int
    report_id: str
    seller_id: str
    store_id: str
    marketplace: str
    asin: Optional[str] = None
    date: Optional[date_type] = None
    row_number: int
    report_type: str
    match_status: str
    raw_data: Optional[str] = None
    normalized_data: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StagingRowListResponse(BaseModel):
    items: List[StagingRowResponse]
    total: int
    skip: int
    limit: int


class StagingRowResolveRequest(BaseModel):
    report_id: str
    action: str
    asin: Optional[str] = None
    staging_row_ids: List[int] = Field(default_factory=list)


class StagingRowResolveResponse(BaseModel):
    report_id: str
    report_type: str
    parse_status: str
    action: str
    total_rows: int
    matched_asin_rows: int
    unmatched_rows: int
    ambiguous_rows: int
    writable_rows: int


class ValidationTaskCreate(BaseModel):
    store_id: str = "default"
    marketplace: str = "US"
    asin: str
    validation_type: str
    problem: Optional[str] = None
    hypothesis: Optional[str] = None
    action_plan: Optional[str] = None
    target_metric: Optional[str] = None
    baseline_start_date: Optional[date_type] = None
    baseline_end_date: Optional[date_type] = None
    test_start_date: Optional[date_type] = None
    test_end_date: Optional[date_type] = None
    result_start_date: Optional[date_type] = None
    result_end_date: Optional[date_type] = None
    baseline_value: Optional[float] = None
    target_value: Optional[float] = None
    result_value: Optional[float] = None
    improvement_rate: Optional[float] = None
    confidence_score: Optional[float] = None
    status: str = "Pending"
    data_source: Optional[str] = None
    is_demo: bool = False


class ValidationTaskResponse(ValidationTaskCreate):
    id: int
    validation_id: str
    seller_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExecutionLogCreate(BaseModel):
    validation_id: str
    store_id: str = "default"
    marketplace: str = "US"
    asin: str
    action_type: str
    before_value: Optional[str] = None
    after_value: Optional[str] = None
    executed_by: Optional[str] = None
    executed_at: Optional[datetime] = None
    note: Optional[str] = None
    source: Optional[str] = None
    data_source: Optional[str] = None
    is_demo: bool = False


class ExecutionLogResponse(ExecutionLogCreate):
    id: int
    execution_id: str
    seller_id: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExecutionLogListResponse(BaseModel):
    items: List[ExecutionLogResponse]
    total: int
    skip: int
    limit: int


class AiDecisionTraceCreate(BaseModel):
    store_id: str = "default"
    marketplace: str = "US"
    asin: str
    related_validation_id: Optional[str] = None
    decision_type: str
    conclusion: Optional[str] = None
    evidence_metrics: Union[Dict[str, Any], str] = Field(default_factory=dict)
    reasoning_summary: Optional[str] = None
    confidence_score: Optional[float] = None
    recommended_action: Optional[str] = None
    data_source: Optional[str] = None
    is_demo: bool = False


class AiDecisionTraceResponse(AiDecisionTraceCreate):
    id: int
    decision_id: str
    seller_id: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AiDecisionTraceListResponse(BaseModel):
    items: List[AiDecisionTraceResponse]
    total: int
    skip: int
    limit: int


class AsinModuleViewResponse(BaseModel):
    view_type: str
    seller_id: str
    store_id: str
    marketplace: str
    asin: str
    summary: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    records: List[Dict[str, Any]] = Field(default_factory=list)


class MetricDictionaryResponse(BaseModel):
    id: int
    metric_key: str
    metric_name: str
    formula: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class DemoImportResponse(BaseModel):
    imported_profiles: int
    imported_snapshots: int
    imported_validation_tasks: int
    imported_ai_traces: int
    skipped_without_complete_aplus: int
    source: str
