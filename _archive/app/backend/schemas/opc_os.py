from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _id() -> str:
    return str(uuid4())


NodeType = Literal["驱动力", "动机", "需求", "场景", "解决方案", "表达", "行为", "结果"]
CapitalAction = Literal["Close", "Observe", "Continue", "Scale"]
ExperimentStatus = Literal[
    "draft",
    "pending_manual_launch",
    "awaiting_manual_result",
    "completed",
    "blocked",
]


class KnowledgeNode(BaseModel):
    id: str = Field(default_factory=_id)
    name: str = "待录入"
    type: NodeType = "需求"
    parent_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(
        default_factory=lambda: {
            "confidence": 0,
            "evidence_count": 0,
            "evidence_quality": 0,
            "time_decay": 1,
        }
    )


class KnowledgeEdge(BaseModel):
    id: str = Field(default_factory=_id)
    from_node: str
    to_node: str
    relation_type: str = "未设置"
    weight: float = 0
    evidence_sources: list[str] = Field(default_factory=list)


class Opportunity(BaseModel):
    opportunity_id: str = Field(default_factory=_id)
    title: str = "待录入"
    human_drivers: list[str] = Field(default_factory=lambda: ["待录入"])
    demand: str = "待录入"
    scenario: str = "待录入"
    initial_score: float = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class OpportunityInput(BaseModel):
    title: str = "待录入"
    human_drivers: list[str] = Field(default_factory=list)
    demand: str = "待录入"
    scenario: str = "待录入"
    initial_score: float = 0


class Uncertainty(BaseModel):
    uncertainty_id: str = Field(default_factory=_id)
    opportunity_id: str
    question: str = "待录入"
    risk_type: str = "未设置"
    risk_score: float = 0
    priority: int = 0
    status: str = "待验证"


class UncertaintyQueue(BaseModel):
    opportunity_id: str
    uncertainty_queue: list[Uncertainty] = Field(default_factory=list)


class MetricThreshold(BaseModel):
    metric: Literal["CTR", "CVR", "订单", "转化", "ROI"]
    success: float = 0
    failure: float = 0


class ProofPlan(BaseModel):
    proof_plan_id: str = Field(default_factory=_id)
    opportunity_id: str
    validation_goal: str = "待录入"
    metrics: list[MetricThreshold] = Field(default_factory=list)
    sample_size: int = 0
    budget_suggestion: float = 0
    status: str = "待确认"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProofPlanInput(BaseModel):
    opportunity_id: str
    validation_goal: str = "待录入"
    metrics: list[MetricThreshold] = Field(default_factory=list)
    sample_size: int = 0
    budget_suggestion: float = 0


class ExperimentExecution(BaseModel):
    execution_id: str = Field(default_factory=_id)
    proof_plan_id: str
    channel: Literal["landing_page", "seo_content", "small_budget_ad", "survey"] = "small_budget_ad"
    status: ExperimentStatus = "pending_manual_launch"
    manual_required: bool = True
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExperimentExecutionInput(BaseModel):
    proof_plan_id: str
    channel: Literal["landing_page", "seo_content", "small_budget_ad", "survey"] = "small_budget_ad"
    manual_confirmed: bool = False


class Evidence(BaseModel):
    evidence_id: str = Field(default_factory=_id)
    proof_plan_id: str
    execution_id: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    evidence_quality: float = 0
    proof_score: float = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EvidenceInput(BaseModel):
    proof_plan_id: str
    execution_id: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    evidence_quality: float = 0


class CapitalDecision(BaseModel):
    capital_decision_id: str = Field(default_factory=_id)
    opportunity_id: str
    proof_score: float = 0
    risk_score: float = 0
    information_gain: float = 0
    suggested_action: CapitalAction = "Observe"
    requires_human_confirmation: bool = True
    confirmed: bool = False
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CapitalDecisionInput(BaseModel):
    opportunity_id: str
    proof_score: float = 0
    risk_score: float = 0
    information_gain: float = 0


class CapitalDecisionConfirmInput(BaseModel):
    confirmed: bool


class CapitalAllocationInput(BaseModel):
    opportunity_ids: list[str] = Field(default_factory=list)
    source_module: str = ""
    asin: str = ""
    budget: float = 0


class CapitalAllocationItem(BaseModel):
    opportunity_id: str
    suggested_action: CapitalAction = "Observe"
    proof_score: float = 0
    risk_score: float = 0
    information_gain: float = 0
    allocation_weight: float = 0
    suggested_budget: float = 0


class CapitalAllocation(BaseModel):
    allocation_id: str = Field(default_factory=_id)
    budget: float = 0
    items: list[CapitalAllocationItem] = Field(default_factory=list)
    requires_human_confirmation: bool = True
    status: str = "待确认"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ListingActionCandidate(BaseModel):
    action_id: str = Field(default_factory=_id)
    opportunity_id: str
    source_evidence_id: str | None = None
    field: str = "待录入"
    status: str = "待处理"
    priority: int = 0


class KnowledgeEvolutionResult(BaseModel):
    opportunity_id: str
    evidence_id: str | None = None
    node_updates: list[KnowledgeNode] = Field(default_factory=list)
    edge_updates: list[KnowledgeEdge] = Field(default_factory=list)
    status: str = "待确认"


class KnowledgeEvolutionInput(BaseModel):
    opportunity_id: str
    evidence_id: str | None = None
    nodes: list[KnowledgeNode] = Field(default_factory=list)
    edges: list[KnowledgeEdge] = Field(default_factory=list)


class OPCExecutionResult(BaseModel):
    opportunity: Opportunity
    uncertainty_queue: list[Uncertainty]
    proof_plan: ProofPlan
    experiment_execution: ExperimentExecution
    evidence: Evidence
    capital_decision: CapitalDecision
    knowledge_evolution: KnowledgeEvolutionResult
