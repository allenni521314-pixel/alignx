from typing import Literal

from pydantic import BaseModel, Field


Grade = Literal["A", "B", "C", "D", "未设置"]
ProductStage = Literal["新品", "成长", "成熟", "衰退", "待录入"]
ProductType = Literal["标品", "半标品", "非标品", "待录入"]
BudgetLevel = Literal["低", "中", "高", "待录入"]


class CurrentAdStatus(BaseModel):
    product_stage: ProductStage = "待录入"
    product_type: ProductType = "待录入"
    budget_level: BudgetLevel = "待录入"
    ad_health_grade: Grade = "未设置"


class AdPathItem(BaseModel):
    channel: str
    ratio: str = "未设置"


class CampaignMatrixItem(BaseModel):
    campaign_type: str
    recommendation_grade: Grade = "未设置"


class PlacementStrategyItem(BaseModel):
    placement: str
    ratio: str = "未设置"


class BidStrategy(BaseModel):
    fixed_bid: str = "未设置"
    dynamic_down: str = "未设置"
    dynamic_up: str = "未设置"
    dynamic_up_down: str = "未设置"
    recommended: str = "未设置"


class BudgetAllocationItem(BaseModel):
    budget_type: str
    amount: str = "未设置"
    ratio: str = "未设置"


class ValidationGoal(BaseModel):
    goal_type: str = "未设置"
    ctr_target: str = "未设置"
    cvr_target: str = "未设置"
    acos_target: str = "未设置"
    roi_target: str = "未设置"
    validation_period: str = "未设置"


class ExpectedOutcome(BaseModel):
    ctr_lift: str = "未设置"
    cvr_lift: str = "未设置"
    acos_improvement: str = "未设置"
    roi_improvement: str = "未设置"


class AdvertisingStrategyInput(BaseModel):
    product_stage: ProductStage = "待录入"
    product_type: ProductType = "待录入"
    budget_level: BudgetLevel = "待录入"
    ad_validation_result: dict = Field(default_factory=dict)
    proof_score: float = 0
    competition_structure: dict = Field(default_factory=dict)


class AdvertisingStrategyOutput(BaseModel):
    current_ad_status: CurrentAdStatus = Field(default_factory=CurrentAdStatus)
    recommended_ad_path: list[AdPathItem] = Field(default_factory=list)
    campaign_matrix: list[CampaignMatrixItem] = Field(default_factory=list)
    placement_strategy: list[PlacementStrategyItem] = Field(default_factory=list)
    bid_strategy: BidStrategy = Field(default_factory=BidStrategy)
    budget_allocation: list[BudgetAllocationItem] = Field(default_factory=list)
    validation_goal: ValidationGoal = Field(default_factory=ValidationGoal)
    biggest_waste: str = "暂无"
    next_best_action: str = "暂无"
    expected_outcome: ExpectedOutcome = Field(default_factory=ExpectedOutcome)
