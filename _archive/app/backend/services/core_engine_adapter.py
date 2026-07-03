from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from schemas.core_engines import CapitalAllocationInput, KnowledgeEvolutionInput, ProofScoreInput
from services.core_engines import (
    CapitalAllocationEngine,
    HumanNatureGraphEngine,
    KnowledgeEvolutionEngine,
    ProofScoreEngine,
)


class CoreEngineBusinessAdapter:
    """Internal adapter that anchors business results to the root graph before scoring."""

    def __init__(self, db: AsyncSession, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    async def ensure_root_path(self) -> dict[str, list[str]]:
        graph = HumanNatureGraphEngine(self.db, "system_core_engine")
        await graph.seed_graph()
        graph = HumanNatureGraphEngine(self.db, self.user_id)
        nodes = await graph.list_nodes()
        edges = await graph.list_edges()
        return {
            "graph_node_ids": [node.id for node in nodes if node.layer in {"Root", "Evolution", "HumanMotivation"}],
            "graph_edge_ids": [edge.id for edge in edges],
        }

    async def evaluate_cycle(
        self,
        *,
        source_type: str,
        source_id: str,
        opportunity_id: str,
        opportunity_score: float = 0,
        risk_score: float = 0,
        information_gain: float = 0,
        budget: float = 0,
        evidence_count: int = 0,
        evidence_quality: float = 0,
        sample_size: int = 0,
        conversion_signal: float = 0,
        consistency: float = 0,
        statistical_confidence: float = 0,
        metrics: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        path = await self.ensure_root_path()
        proof = await ProofScoreEngine(self.db, self.user_id).evaluate(
            ProofScoreInput(
                **path,
                evidence_count=evidence_count,
                evidence_quality=evidence_quality,
                sample_size=sample_size,
                conversion_signal=conversion_signal,
                consistency=consistency,
                statistical_confidence=statistical_confidence,
                source_type=source_type,
                source_id=source_id,
                metrics=metrics or {},
            )
        )
        capital = await CapitalAllocationEngine(self.db, self.user_id).evaluate(
            CapitalAllocationInput(
                opportunity_id=opportunity_id,
                evidence_id=proof.evidence_id,
                **path,
                opportunity_score=opportunity_score,
                proof_score=proof.proof_score,
                risk_score=risk_score,
                information_gain=information_gain,
                budget=budget,
            )
        )
        evolution = await KnowledgeEvolutionEngine(self.db, self.user_id).evaluate(
            KnowledgeEvolutionInput(
                evidence_id=proof.evidence_id,
                node_ids=path["graph_node_ids"],
                edge_ids=path["graph_edge_ids"],
                proof_score=proof.proof_score,
                proof_state=proof.proof_state,
                evidence_quality=evidence_quality,
                statistical_confidence=statistical_confidence,
            )
        )
        return {
            "evidence": proof.model_dump(mode="json", exclude={"graph_node_ids", "graph_edge_ids"}),
            "capital_decision": capital.model_dump(mode="json", exclude={"graph_node_ids", "graph_edge_ids"}),
            "knowledge_evolution": evolution.model_dump(mode="json", exclude={"events"}),
        }
