from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4()}"


NodeLayer = Literal["Root", "Evolution", "HumanMotivation", "Motivation", "Need", "Scenario", "Solution", "Expression", "Behavior", "Outcome"]
ProofState = Literal["验证成功", "验证失败", "继续验证", "样本不足"]
CapitalAction = Literal["Close", "Observe", "Continue", "Scale"]
KnowledgeEventType = Literal["enter", "decay", "reinforce", "eliminate"]


class GraphNodeInput(BaseModel):
    id: str = ""
    name: str = "待录入"
    node_type: str = "待录入"
    layer: NodeLayer = "Need"
    parent_ids: list[str] = Field(default_factory=list)
    confidence: float = 0
    evidence_count: int = 0
    evidence_quality: float = 0
    time_decay: float = 1
    attributes: dict[str, Any] = Field(default_factory=dict)


class GraphNode(GraphNodeInput):
    id: str = Field(default_factory=lambda: _id("node"))
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GraphEdgeInput(BaseModel):
    id: str = ""
    from_node_id: str
    to_node_id: str
    relation_type: str = "未设置"
    weight: float = 0
    confidence: float = 0
    evidence_count: int = 0
    evidence_quality: float = 0
    time_decay: float = 1
    evidence_sources: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(GraphEdgeInput):
    id: str = Field(default_factory=lambda: _id("edge"))
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WeightUpdateInput(BaseModel):
    evidence_quality: float = 0
    statistical_confidence: float = 0
    consistency: float = 0
    time_decay: float = 1
    evidence_id: str | None = None


class ProofScoreInput(BaseModel):
    graph_node_ids: list[str] = Field(default_factory=list)
    graph_edge_ids: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    evidence_quality: float = 0
    sample_size: int = 0
    conversion_signal: float = 0
    consistency: float = 0
    statistical_confidence: float = 0
    source_type: str = ""
    source_id: str = ""
    metrics: dict[str, float] = Field(default_factory=dict)


class ProofScoreResult(ProofScoreInput):
    evidence_id: str = Field(default_factory=lambda: _id("evidence"))
    proof_score: float = 0
    proof_state: ProofState = "样本不足"
    created_at: datetime | None = None


class CapitalAllocationInput(BaseModel):
    opportunity_id: str
    evidence_id: str | None = None
    graph_node_ids: list[str] = Field(default_factory=list)
    graph_edge_ids: list[str] = Field(default_factory=list)
    opportunity_score: float = 0
    proof_score: float = 0
    risk_score: float = 0
    information_gain: float = 0
    budget: float = 0


class CapitalAllocationResult(CapitalAllocationInput):
    allocation_id: str = Field(default_factory=lambda: _id("allocation"))
    priority_score: float = 0
    suggested_action: CapitalAction = "Observe"
    suggested_budget: float = 0
    requires_human_confirmation: bool = True
    confirmed: bool = False
    created_at: datetime | None = None


class KnowledgeEvolutionInput(BaseModel):
    evidence_id: str | None = None
    node_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)
    proof_score: float = 0
    proof_state: ProofState = "样本不足"
    evidence_quality: float = 0
    statistical_confidence: float = 0
    time_decay: float = 1


class KnowledgeEvolutionEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: _id("event"))
    evidence_id: str | None = None
    node_id: str | None = None
    edge_id: str | None = None
    event_type: KnowledgeEventType
    previous_weight: float = 0
    new_weight: float = 0
    previous_confidence: float = 0
    new_confidence: float = 0
    reason: str = "未设置"
    created_at: datetime | None = None


class KnowledgeEvolutionResult(BaseModel):
    events: list[KnowledgeEvolutionEvent] = Field(default_factory=list)


class CoreEngineSchema(BaseModel):
    graph_schema: dict[str, Any]
    proof_score_algorithm: dict[str, Any]
    capital_allocation_algorithm: dict[str, Any]
    knowledge_evolution_algorithm: dict[str, Any]
    er_diagram: str
    service_architecture: dict[str, Any]
