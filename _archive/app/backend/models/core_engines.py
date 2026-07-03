from core.database import Base
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, func


class HumanNatureGraphNode(Base):
    __tablename__ = "human_nature_graph_nodes"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, index=True, nullable=False)
    name = Column(String, nullable=False, index=True)
    node_type = Column(String, nullable=False, index=True)
    layer = Column(String, nullable=False, index=True)
    parent_ids = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, default=0)
    evidence_count = Column(Integer, nullable=False, default=0)
    evidence_quality = Column(Float, nullable=False, default=0)
    time_decay = Column(Float, nullable=False, default=1)
    attributes = Column(Text, nullable=True)
    created_by = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HumanNatureGraphEdge(Base):
    __tablename__ = "human_nature_graph_edges"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, index=True, nullable=False)
    from_node_id = Column(String, nullable=False, index=True)
    to_node_id = Column(String, nullable=False, index=True)
    relation_type = Column(String, nullable=False, index=True)
    weight = Column(Float, nullable=False, default=0)
    confidence = Column(Float, nullable=False, default=0)
    evidence_count = Column(Integer, nullable=False, default=0)
    evidence_quality = Column(Float, nullable=False, default=0)
    time_decay = Column(Float, nullable=False, default=1)
    evidence_sources = Column(Text, nullable=True)
    attributes = Column(Text, nullable=True)
    created_by = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CoreEngineEvidence(Base):
    __tablename__ = "core_engine_evidence"
    __table_args__ = {"extend_existing": True}

    evidence_id = Column(String, primary_key=True, index=True, nullable=False)
    source_type = Column(String, nullable=True, index=True)
    source_id = Column(String, nullable=True, index=True)
    graph_node_ids = Column(Text, nullable=True)
    graph_edge_ids = Column(Text, nullable=True)
    metrics = Column(Text, nullable=True)
    evidence_count = Column(Integer, nullable=False, default=0)
    evidence_quality = Column(Float, nullable=False, default=0)
    sample_size = Column(Integer, nullable=False, default=0)
    conversion_signal = Column(Float, nullable=False, default=0)
    consistency = Column(Float, nullable=False, default=0)
    statistical_confidence = Column(Float, nullable=False, default=0)
    proof_score = Column(Float, nullable=False, default=0)
    proof_state = Column(String, nullable=False, index=True)
    created_by = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CapitalAllocationRecord(Base):
    __tablename__ = "capital_allocation_records"
    __table_args__ = {"extend_existing": True}

    allocation_id = Column(String, primary_key=True, index=True, nullable=False)
    opportunity_id = Column(String, nullable=False, index=True)
    evidence_id = Column(String, nullable=True, index=True)
    graph_node_ids = Column(Text, nullable=True)
    graph_edge_ids = Column(Text, nullable=True)
    opportunity_score = Column(Float, nullable=False, default=0)
    proof_score = Column(Float, nullable=False, default=0)
    risk_score = Column(Float, nullable=False, default=0)
    information_gain = Column(Float, nullable=False, default=0)
    priority_score = Column(Float, nullable=False, default=0)
    suggested_action = Column(String, nullable=False, index=True)
    budget = Column(Float, nullable=False, default=0)
    suggested_budget = Column(Float, nullable=False, default=0)
    requires_human_confirmation = Column(Boolean, nullable=False, default=True)
    confirmed = Column(Boolean, nullable=False, default=False)
    created_by = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class KnowledgeEvolutionEvent(Base):
    __tablename__ = "knowledge_evolution_events"
    __table_args__ = {"extend_existing": True}

    event_id = Column(String, primary_key=True, index=True, nullable=False)
    evidence_id = Column(String, nullable=True, index=True)
    node_id = Column(String, nullable=True, index=True)
    edge_id = Column(String, nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    previous_weight = Column(Float, nullable=False, default=0)
    new_weight = Column(Float, nullable=False, default=0)
    previous_confidence = Column(Float, nullable=False, default=0)
    new_confidence = Column(Float, nullable=False, default=0)
    reason = Column(String, nullable=False, default="未设置")
    created_by = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
