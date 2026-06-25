from __future__ import annotations
"""AlignX V1 — Pydantic request/response schemas."""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════
# Shared
# ═══════════════════════════════════════════

class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int = 1
    page_size: int = 20


# ═══════════════════════════════════════════
# Market Opportunity
# ═══════════════════════════════════════════

class MarketOpportunityRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=255)
    marketplace: str = Field(default="amazon.com")


class SevenLayerResult(BaseModel):
    market_entry_conclusion: Optional[str] = None
    top20_competition_structure: Optional[Any] = None
    price_band_and_margin: Optional[Any] = None
    demand_strength_and_gap: Optional[Any] = None
    competitor_selling_point_commonality: Optional[Any] = None
    traffic_and_ad_risk: Optional[Any] = None
    suggested_entry_strategy: Optional[str] = None


class MarketOpportunityResponse(BaseModel):
    id: str
    keyword: str
    marketplace: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    category_confidence: Optional[float] = None
    opportunity_score: Optional[float] = None
    entry_level: Optional[str] = None
    market_entry_conclusion: Optional[str] = None
    top20_competition_strength: Optional[str] = None
    price_band_judgment: Optional[str] = None
    main_risk: Optional[str] = None
    next_action: Optional[str] = None
    best_opportunity_category: Optional[str] = None
    product_categories: Optional[list] = None
    seven_layer_result_json: Optional[dict] = None
    created_at: datetime


# ═══════════════════════════════════════════
# Competitor Analysis
# ═══════════════════════════════════════════

class CompetitorAnalysisRequest(BaseModel):
    asin: Optional[str] = Field(None, min_length=10, max_length=16)
    product_url: Optional[str] = Field(None, max_length=2048)
    marketplace: str = Field(default="amazon.com")


class TwelveDimensionResult(BaseModel):
    price_band_position: Optional[Any] = None
    review_count_barrier: Optional[Any] = None
    rating_trust: Optional[Any] = None
    main_image_click_power: Optional[Any] = None
    secondary_image_engagement: Optional[Any] = None
    title_keyword_match: Optional[Any] = None
    bullet_point_expression: Optional[Any] = None
    aplus_persuasion: Optional[Any] = None
    review_pain_points: Optional[Any] = None
    differentiation_strength: Optional[Any] = None
    organic_vs_ad_dependency: Optional[Any] = None
    conversion_risk_and_attack_points: Optional[Any] = None


class CompetitorAnalysisResponse(BaseModel):
    id: str
    asin: str
    product_url: Optional[str] = None
    marketplace: str
    product_title: Optional[str] = None
    brand: Optional[str] = None
    seller_name: Optional[str] = None
    store_name: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    price: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    bought_in_past_month_raw: Optional[str] = None
    revenue_floor_30d: Optional[float] = None
    overall_judgment: Optional[str] = None
    main_strengths: Optional[list] = None
    main_weaknesses: Optional[list] = None
    attack_points: Optional[list] = None
    worth_benchmarking: Optional[bool] = None
    listing_presentation_json: Optional[dict] = None
    twelve_dimension_result_json: Optional[dict] = None
    created_at: datetime


# ═══════════════════════════════════════════
# Pre-launch Check
# ═══════════════════════════════════════════

class PrelaunchCheckRequest(BaseModel):
    class Config:
        extra = "allow"
    product_name: str = Field(..., min_length=1, max_length=255)
    marketplace: str = Field(default="amazon.com")
    title_draft: Optional[str] = None
    key_highlights: Optional[str] = None
    bullet_1: Optional[str] = None
    bullet_2: Optional[str] = None
    bullet_3: Optional[str] = None
    bullet_4: Optional[str] = None
    bullet_5: Optional[str] = None
    image_count: int = 0
    image_slots: list = []
    main_image_path: Optional[str] = None
    image_2_path: Optional[str] = None
    image_3_path: Optional[str] = None
    image_4_path: Optional[str] = None
    image_5_path: Optional[str] = None
    image_6_path: Optional[str] = None
    image_7_path: Optional[str] = None
    aplus_images_json: Optional[list] = None


class PositionDiagnosis(BaseModel):
    position_id: str
    position_name: str
    position_type: str
    content_text: Optional[str] = None
    image_url: Optional[str] = None
    status: str  # 通过 | 需修改 | 缺失
    issue: Optional[str] = None
    impact: Optional[str] = None
    recommendation: Optional[str] = None
    modification_example: Optional[str] = None


class PrelaunchCheckResponse(BaseModel):
    id: str
    product_name: str
    marketplace: str
    title_draft: Optional[str] = None
    key_highlights: Optional[str] = None
    bullet_1: Optional[str] = None
    bullet_2: Optional[str] = None
    bullet_3: Optional[str] = None
    bullet_4: Optional[str] = None
    bullet_5: Optional[str] = None
    main_image_path: Optional[str] = None
    image_2_path: Optional[str] = None
    image_3_path: Optional[str] = None
    image_4_path: Optional[str] = None
    image_5_path: Optional[str] = None
    image_6_path: Optional[str] = None
    image_7_path: Optional[str] = None
    aplus_images_json: Optional[list] = None
    admission_result: Optional[str] = None
    conclusion: Optional[str] = None
    position_diagnoses_json: Optional[list] = None
    next_action: Optional[str] = None
    created_at: datetime


# ═══════════════════════════════════════════
# Conversion Diagnosis
# ═══════════════════════════════════════════

class ConversionDiagnosisRequest(BaseModel):
    asin: Optional[str] = Field(None, min_length=10, max_length=16)
    product_url: Optional[str] = Field(None, max_length=2048)
    marketplace: str = Field(default="amazon.com")


class ConversionPositionDiagnosis(BaseModel):
    position_id: str
    position_name: str
    position_type: str
    content_text: Optional[str] = None
    image_url: Optional[str] = None
    status: str  # 通过 | 需修改 | 严重影响转化 | 缺失
    impacted_ad_metrics: Optional[list[str]] = None
    issue: Optional[str] = None
    evidence: Optional[str] = None
    conversion_impact: Optional[str] = None
    recommendation: Optional[str] = None
    priority: Optional[int] = None
    matched_proposition_code: Optional[str] = None
    matched_proposition_name: Optional[str] = None
    proposition_confidence: Optional[float] = None
    validation_ready: Optional[bool] = None


class ConversionDiagnosisResponse(BaseModel):
    id: str
    asin: str
    product_url: Optional[str] = None
    marketplace: str
    product_title: Optional[str] = None
    overall_conclusion: Optional[str] = None
    biggest_breakpoint: Optional[str] = None
    priority_position: Optional[str] = None
    priority_action: Optional[str] = None
    impacted_ad_metrics: Optional[list[str]] = None
    current_status: Optional[str] = None
    position_diagnoses_json: Optional[list] = None
    primary_matched_proposition_code: Optional[str] = None
    created_at: datetime


# ═══════════════════════════════════════════
# Validation Tasks
# ═══════════════════════════════════════════

class ValidationTaskCreate(BaseModel):
    asin: str
    proposition_code: str
    proposition_name: Optional[str] = None
    source_module: Optional[str] = None
    source_record_id: Optional[str] = None
    hypothesis_text: Optional[str] = None
    evidence_snapshot: Optional[dict] = None
    controlled_variable: Optional[str] = None
    forbidden_simultaneous_changes: Optional[list[str]] = None
    validation_period: Optional[str] = "14d"
    success_criteria: Optional[str] = None
    failure_criteria: Optional[str] = None


class ValidationTaskUpdate(BaseModel):
    execution_status: Optional[str] = None
    result_status: Optional[str] = None
    next_action: Optional[str] = None


class ValidationTaskResponse(BaseModel):
    id: str
    asin: str
    proposition_code: str
    proposition_name: Optional[str] = None
    source_module: Optional[str] = None
    source_record_id: Optional[str] = None
    hypothesis_text: Optional[str] = None
    evidence_snapshot: Optional[dict] = None
    controlled_variable: Optional[str] = None
    forbidden_simultaneous_changes: Optional[list] = None
    validation_period: Optional[str] = None
    success_criteria: Optional[str] = None
    failure_criteria: Optional[str] = None
    execution_status: str
    result_status: Optional[str] = None
    next_action: Optional[str] = None
    created_at: datetime


# ═══════════════════════════════════════════
# Execution Records
# ═══════════════════════════════════════════

class ExecutionRecordCreate(BaseModel):
    validation_task_id: str
    asin: str
    executor: Optional[str] = None
    action_summary: Optional[str] = None
    changed_variable: Optional[str] = None
    changed_position: Optional[str] = None
    change_detail: Optional[str] = None
    cost_amount: Optional[float] = None
    cost_type: Optional[str] = None
    evidence_note: Optional[str] = None


class ExecutionRecordResponse(BaseModel):
    id: str
    validation_task_id: str
    asin: str
    executed_at: datetime
    executor: Optional[str] = None
    action_summary: Optional[str] = None
    changed_variable: Optional[str] = None
    changed_position: Optional[str] = None
    change_detail: Optional[str] = None
    cost_amount: Optional[float] = None
    cost_type: Optional[str] = None
    evidence_note: Optional[str] = None
    created_at: datetime


# ═══════════════════════════════════════════
# Validation Results
# ═══════════════════════════════════════════

class ValidationResultCreate(BaseModel):
    validation_task_id: str
    asin: str
    baseline_metrics_json: Optional[dict] = None
    result_metrics_json: Optional[dict] = None
    sample_days: Optional[int] = None
    sample_clicks: Optional[int] = None
    sample_orders: Optional[int] = None
    suggested_result_status: Optional[str] = None
    final_result_status: Optional[str] = None
    attribution_conclusion: Optional[str] = None
    notes: Optional[str] = None


class ValidationResultResponse(BaseModel):
    id: str
    validation_task_id: str
    asin: str
    baseline_metrics_json: Optional[dict] = None
    result_metrics_json: Optional[dict] = None
    sample_days: Optional[int] = None
    sample_clicks: Optional[int] = None
    sample_orders: Optional[int] = None
    suggested_result_status: Optional[str] = None
    final_result_status: Optional[str] = None
    attribution_conclusion: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


# ═══════════════════════════════════════════
# ASIN Operation Profiles
# ═══════════════════════════════════════════

class AsinOperationProfileResponse(BaseModel):
    id: str
    asin: str
    product_title: Optional[str] = None
    category: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    total_validation_count: int
    effective_count: int
    ineffective_count: int
    interfered_count: int
    insufficient_data_count: int
    successful_propositions_json: Optional[list] = None
    failed_propositions_json: Optional[list] = None
    repeated_failure_patterns_json: Optional[list] = None
    current_main_problem: Optional[str] = None
    next_recommended_proposition: Optional[str] = None
    asin_learning_summary: Optional[str] = None
    updated_at: datetime


# ═══════════════════════════════════════════
# Proposition
# ═══════════════════════════════════════════

class PropositionResponse(BaseModel):
    id: str
    proposition_code: str
    category_code: str
    name: str
    definition: Optional[str] = None
    applicable_conditions: Optional[str] = None
    required_evidence: Optional[str] = None
    recommended_action: Optional[str] = None
    controlled_variable: Optional[str] = None
    success_criteria: Optional[str] = None
    failure_criteria: Optional[str] = None
    next_proposition_if_failed: Optional[str] = None
    archived: bool
