import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.core_engines import (
    CapitalAllocationRecord,
    CoreEngineEvidence,
    HumanNatureGraphEdge,
    HumanNatureGraphNode,
    KnowledgeEvolutionEvent as KnowledgeEvolutionEventModel,
)
from schemas.core_engines import (
    CapitalAllocationInput,
    CapitalAllocationResult,
    CoreEngineSchema,
    GraphEdge,
    GraphEdgeInput,
    GraphNode,
    GraphNodeInput,
    KnowledgeEvolutionEvent,
    KnowledgeEvolutionInput,
    KnowledgeEvolutionResult,
    ProofScoreInput,
    ProofScoreResult,
    WeightUpdateInput,
)


def _clamp(value: float, lower: float = 0, upper: float = 100) -> float:
    return max(lower, min(upper, float(value or 0)))


def _dump(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def _load(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


ROOT_NODES = [
    {"id": "root_seek_gain", "name": "Seek Gain", "node_type": "Root", "layer": "Root", "parents": []},
    {"id": "root_avoid_loss", "name": "Avoid Loss", "node_type": "Root", "layer": "Root", "parents": []},
]

EVOLUTION_NODES = [
    {"id": "evolution_survival", "name": "Survival", "node_type": "Evolution", "layer": "Evolution", "parents": ["root_avoid_loss"]},
    {"id": "evolution_reproduction", "name": "Reproduction", "node_type": "Evolution", "layer": "Evolution", "parents": ["root_seek_gain"]},
    {"id": "evolution_resource", "name": "Resource", "node_type": "Evolution", "layer": "Evolution", "parents": ["root_seek_gain", "root_avoid_loss"]},
    {"id": "evolution_exploration", "name": "Exploration", "node_type": "Evolution", "layer": "Evolution", "parents": ["root_seek_gain"]},
]

HUMAN_MOTIVATION_NODES = [
    {"id": "driver_survival", "name": "生存", "node_type": "HumanMotivation", "layer": "HumanMotivation", "parents": ["evolution_survival"]},
    {"id": "driver_security", "name": "安全", "node_type": "HumanMotivation", "layer": "HumanMotivation", "parents": ["evolution_survival", "evolution_resource"]},
    {"id": "driver_health", "name": "健康", "node_type": "HumanMotivation", "layer": "HumanMotivation", "parents": ["evolution_survival"]},
    {"id": "driver_love", "name": "爱", "node_type": "HumanMotivation", "layer": "HumanMotivation", "parents": ["evolution_reproduction"]},
    {"id": "driver_belonging", "name": "归属", "node_type": "HumanMotivation", "layer": "HumanMotivation", "parents": ["evolution_reproduction", "evolution_resource"]},
    {"id": "driver_status", "name": "尊严", "node_type": "HumanMotivation", "layer": "HumanMotivation", "parents": ["evolution_resource"]},
    {"id": "driver_power", "name": "权力", "node_type": "HumanMotivation", "layer": "HumanMotivation", "parents": ["evolution_resource"]},
    {"id": "driver_freedom", "name": "自由", "node_type": "HumanMotivation", "layer": "HumanMotivation", "parents": ["evolution_resource", "evolution_exploration"]},
    {"id": "driver_expansion", "name": "扩张", "node_type": "HumanMotivation", "layer": "HumanMotivation", "parents": ["evolution_resource", "evolution_exploration"]},
    {"id": "driver_curiosity", "name": "好奇", "node_type": "HumanMotivation", "layer": "HumanMotivation", "parents": ["evolution_exploration"]},
    {"id": "driver_pleasure", "name": "娱乐", "node_type": "HumanMotivation", "layer": "HumanMotivation", "parents": ["evolution_exploration"]},
    {"id": "driver_convenience", "name": "懒惰", "node_type": "HumanMotivation", "layer": "HumanMotivation", "parents": ["evolution_resource"]},
    {"id": "driver_fear", "name": "恐惧", "node_type": "HumanMotivation", "layer": "HumanMotivation", "parents": ["evolution_survival"]},
]


class HumanNatureGraphEngine:
    def __init__(self, db: AsyncSession, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    async def seed_graph(self) -> dict[str, int]:
        node_count = 0
        edge_count = 0
        seed_nodes = ROOT_NODES + EVOLUTION_NODES + HUMAN_MOTIVATION_NODES
        for item in seed_nodes:
            node_id = item["id"]
            exists = await self.db.get(HumanNatureGraphNode, node_id)
            if exists:
                continue
            self.db.add(
                HumanNatureGraphNode(
                    id=node_id,
                    name=item["name"],
                    node_type=item["node_type"],
                    layer=item["layer"],
                    confidence=100,
                    evidence_count=0,
                    evidence_quality=0,
                    time_decay=1,
                    parent_ids=_dump(item["parents"]),
                    attributes="{}",
                    created_by=self.user_id,
                )
            )
            node_count += 1

        base_edges = []
        for item in seed_nodes:
            for parent_id in item["parents"]:
                relation = f"{parent_id.split('_')[0]}_to_{item['node_type'].lower()}"
                base_edges.append((f"edge_{parent_id}_{item['id']}", parent_id, item["id"], relation))
        for edge_id, from_id, to_id, relation in base_edges:
            exists = await self.db.get(HumanNatureGraphEdge, edge_id)
            if exists:
                continue
            self.db.add(
                HumanNatureGraphEdge(
                    id=edge_id,
                    from_node_id=from_id,
                    to_node_id=to_id,
                    relation_type=relation,
                    weight=50,
                    confidence=50,
                    evidence_count=0,
                    evidence_quality=0,
                    time_decay=1,
                    evidence_sources="[]",
                    attributes="{}",
                    created_by=self.user_id,
                )
            )
            edge_count += 1
        await self.db.commit()
        return {"nodes": node_count, "edges": edge_count}

    async def create_node(self, payload: GraphNodeInput) -> GraphNode:
        data = payload.model_dump()
        node_id = data.pop("id", "") or GraphNode().id
        node = GraphNode(**data, id=node_id)
        row = HumanNatureGraphNode(
            id=node.id,
            name=node.name,
            node_type=node.node_type,
            layer=node.layer,
            parent_ids=_dump(node.parent_ids),
            confidence=_clamp(node.confidence),
            evidence_count=max(0, int(node.evidence_count or 0)),
            evidence_quality=_clamp(node.evidence_quality),
            time_decay=max(0, min(1, float(node.time_decay or 0))),
            attributes=_dump(node.attributes),
            created_by=self.user_id,
        )
        self.db.add(row)
        await self.db.commit()
        return self._node_from_row(row)

    async def create_edge(self, payload: GraphEdgeInput) -> GraphEdge:
        data = payload.model_dump()
        edge_id = data.pop("id", "") or GraphEdge(from_node_id=payload.from_node_id, to_node_id=payload.to_node_id).id
        edge = GraphEdge(**data, id=edge_id)
        row = HumanNatureGraphEdge(
            id=edge.id,
            from_node_id=edge.from_node_id,
            to_node_id=edge.to_node_id,
            relation_type=edge.relation_type,
            weight=_clamp(edge.weight),
            confidence=_clamp(edge.confidence),
            evidence_count=max(0, int(edge.evidence_count or 0)),
            evidence_quality=_clamp(edge.evidence_quality),
            time_decay=max(0, min(1, float(edge.time_decay or 0))),
            evidence_sources=_dump(edge.evidence_sources),
            attributes=_dump(edge.attributes),
            created_by=self.user_id,
        )
        self.db.add(row)
        await self.db.commit()
        return self._edge_from_row(row)

    async def list_nodes(self, layer: str = "") -> list[GraphNode]:
        query = select(HumanNatureGraphNode).order_by(HumanNatureGraphNode.layer, HumanNatureGraphNode.name)
        if layer:
            query = query.where(HumanNatureGraphNode.layer == layer)
        rows = list((await self.db.execute(query)).scalars().all())
        return [self._node_from_row(row) for row in rows]

    async def list_edges(self, relation_type: str = "") -> list[GraphEdge]:
        query = select(HumanNatureGraphEdge).order_by(HumanNatureGraphEdge.relation_type, HumanNatureGraphEdge.id)
        if relation_type:
            query = query.where(HumanNatureGraphEdge.relation_type == relation_type)
        rows = list((await self.db.execute(query)).scalars().all())
        return [self._edge_from_row(row) for row in rows]

    async def update_edge_weight(self, edge_id: str, payload: WeightUpdateInput) -> GraphEdge | None:
        row = await self.db.get(HumanNatureGraphEdge, edge_id)
        if not row:
            return None
        update_delta = (
            _clamp(payload.evidence_quality) * 0.35
            + _clamp(payload.statistical_confidence) * 0.35
            + _clamp(payload.consistency) * 0.2
        ) / 10
        row.weight = _clamp(row.weight * max(0, min(1, payload.time_decay)) + update_delta)
        row.confidence = _clamp((row.confidence + _clamp(payload.statistical_confidence)) / 2)
        row.evidence_count = int(row.evidence_count or 0) + 1
        row.evidence_quality = _clamp((row.evidence_quality + _clamp(payload.evidence_quality)) / 2)
        row.time_decay = max(0, min(1, float(payload.time_decay or 0)))
        sources = _load(row.evidence_sources) or []
        if payload.evidence_id and payload.evidence_id not in sources:
            sources.append(payload.evidence_id)
        row.evidence_sources = _dump(sources)
        await self.db.commit()
        return self._edge_from_row(row)

    @staticmethod
    def _node_from_row(row: HumanNatureGraphNode) -> GraphNode:
        return GraphNode(
            id=row.id,
            name=row.name,
            node_type=row.node_type,
            layer=row.layer,
            parent_ids=_load(row.parent_ids) or [],
            confidence=float(row.confidence or 0),
            evidence_count=int(row.evidence_count or 0),
            evidence_quality=float(row.evidence_quality or 0),
            time_decay=float(row.time_decay or 0),
            attributes=_load(row.attributes) or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _edge_from_row(row: HumanNatureGraphEdge) -> GraphEdge:
        return GraphEdge(
            id=row.id,
            from_node_id=row.from_node_id,
            to_node_id=row.to_node_id,
            relation_type=row.relation_type,
            weight=float(row.weight or 0),
            confidence=float(row.confidence or 0),
            evidence_count=int(row.evidence_count or 0),
            evidence_quality=float(row.evidence_quality or 0),
            time_decay=float(row.time_decay or 0),
            evidence_sources=_load(row.evidence_sources) or [],
            attributes=_load(row.attributes) or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class ProofScoreEngine:
    def __init__(self, db: AsyncSession, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    async def evaluate(self, payload: ProofScoreInput, persist: bool = True) -> ProofScoreResult:
        has_graph_path = bool(payload.graph_node_ids or payload.graph_edge_ids)
        sample_score = _clamp(payload.sample_size / 100 * 100)
        evidence_count_score = _clamp(payload.evidence_count / 5 * 100)
        proof_score = round(
            evidence_count_score * 0.15
            + _clamp(payload.evidence_quality) * 0.2
            + sample_score * 0.15
            + _clamp(payload.conversion_signal) * 0.2
            + _clamp(payload.consistency) * 0.15
            + _clamp(payload.statistical_confidence) * 0.15,
            2,
        )
        if not has_graph_path:
            proof_score = 0
            state = "样本不足"
        elif payload.evidence_count <= 0 or payload.sample_size < 30:
            state = "样本不足"
        elif proof_score >= 75:
            state = "验证成功"
        elif proof_score <= 35:
            state = "验证失败"
        else:
            state = "继续验证"
        result = ProofScoreResult(**payload.model_dump(), proof_score=proof_score, proof_state=state)
        if persist:
            self.db.add(
                CoreEngineEvidence(
                    evidence_id=result.evidence_id,
                    source_type=result.source_type,
                    source_id=result.source_id,
                    graph_node_ids=_dump(result.graph_node_ids),
                    graph_edge_ids=_dump(result.graph_edge_ids),
                    metrics=_dump(result.metrics),
                    evidence_count=result.evidence_count,
                    evidence_quality=_clamp(result.evidence_quality),
                    sample_size=max(0, int(result.sample_size)),
                    conversion_signal=_clamp(result.conversion_signal),
                    consistency=_clamp(result.consistency),
                    statistical_confidence=_clamp(result.statistical_confidence),
                    proof_score=result.proof_score,
                    proof_state=result.proof_state,
                    created_by=self.user_id,
                )
            )
            await self.db.commit()
        return result


class CapitalAllocationEngine:
    def __init__(self, db: AsyncSession, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    async def evaluate(self, payload: CapitalAllocationInput, persist: bool = True) -> CapitalAllocationResult:
        has_graph_path = bool(payload.graph_node_ids or payload.graph_edge_ids)
        priority_score = round(
            _clamp(payload.opportunity_score) * 0.25
            + _clamp(payload.proof_score) * 0.35
            + (100 - _clamp(payload.risk_score)) * 0.25
            + _clamp(payload.information_gain) * 0.15,
            2,
        )
        if not has_graph_path:
            priority_score = 0
            action = "Observe"
        elif priority_score >= 75 and payload.proof_score >= 70:
            action = "Scale"
        elif priority_score >= 55:
            action = "Continue"
        elif priority_score >= 35:
            action = "Observe"
        else:
            action = "Close"
        suggested_budget = 0 if action == "Close" else round(max(0, payload.budget) * priority_score / 100, 2)
        result = CapitalAllocationResult(
            **payload.model_dump(),
            priority_score=priority_score,
            suggested_action=action,
            suggested_budget=suggested_budget,
        )
        if persist:
            self.db.add(
                CapitalAllocationRecord(
                    allocation_id=result.allocation_id,
                    opportunity_id=result.opportunity_id,
                    evidence_id=result.evidence_id,
                    graph_node_ids=_dump(result.graph_node_ids),
                    graph_edge_ids=_dump(result.graph_edge_ids),
                    opportunity_score=_clamp(result.opportunity_score),
                    proof_score=_clamp(result.proof_score),
                    risk_score=_clamp(result.risk_score),
                    information_gain=_clamp(result.information_gain),
                    priority_score=result.priority_score,
                    suggested_action=result.suggested_action,
                    budget=max(0, result.budget),
                    suggested_budget=result.suggested_budget,
                    requires_human_confirmation=True,
                    confirmed=False,
                    created_by=self.user_id,
                )
            )
            await self.db.commit()
        return result


class KnowledgeEvolutionEngine:
    def __init__(self, db: AsyncSession, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    async def evaluate(self, payload: KnowledgeEvolutionInput) -> KnowledgeEvolutionResult:
        events: list[KnowledgeEvolutionEvent] = []
        event_type = self._event_type(payload.proof_state, payload.proof_score)
        for edge_id in payload.edge_ids:
            row = await self.db.get(HumanNatureGraphEdge, edge_id)
            if not row:
                continue
            previous_weight = float(row.weight or 0)
            previous_confidence = float(row.confidence or 0)
            new_weight, new_confidence = self._next_values(previous_weight, previous_confidence, payload, event_type)
            row.weight = new_weight
            row.confidence = new_confidence
            row.time_decay = max(0, min(1, float(payload.time_decay or 0)))
            row.evidence_count = int(row.evidence_count or 0) + 1
            event = KnowledgeEvolutionEvent(
                evidence_id=payload.evidence_id,
                edge_id=edge_id,
                event_type=event_type,
                previous_weight=previous_weight,
                new_weight=new_weight,
                previous_confidence=previous_confidence,
                new_confidence=new_confidence,
                reason=payload.proof_state,
            )
            events.append(event)
            self._add_event(event)
        for node_id in payload.node_ids:
            row = await self.db.get(HumanNatureGraphNode, node_id)
            if not row:
                continue
            previous_confidence = float(row.confidence or 0)
            _, new_confidence = self._next_values(0, previous_confidence, payload, event_type)
            row.confidence = new_confidence
            row.time_decay = max(0, min(1, float(payload.time_decay or 0)))
            row.evidence_count = int(row.evidence_count or 0) + 1
            event = KnowledgeEvolutionEvent(
                evidence_id=payload.evidence_id,
                node_id=node_id,
                event_type=event_type,
                previous_confidence=previous_confidence,
                new_confidence=new_confidence,
                reason=payload.proof_state,
            )
            events.append(event)
            self._add_event(event)
        await self.db.commit()
        return KnowledgeEvolutionResult(events=events)

    @staticmethod
    def _event_type(proof_state: str, proof_score: float) -> str:
        if proof_state == "验证成功":
            return "reinforce"
        if proof_state == "验证失败":
            return "eliminate" if proof_score <= 20 else "decay"
        if proof_state == "继续验证":
            return "enter"
        return "decay"

    @staticmethod
    def _next_values(weight: float, confidence: float, payload: KnowledgeEvolutionInput, event_type: str) -> tuple[float, float]:
        if event_type == "reinforce":
            delta = (_clamp(payload.evidence_quality) + _clamp(payload.statistical_confidence)) / 20
            return _clamp(weight + delta), _clamp(confidence + delta)
        if event_type == "eliminate":
            return _clamp(weight * 0.5), _clamp(confidence * 0.5)
        if event_type == "decay":
            decay = max(0, min(1, float(payload.time_decay or 0)))
            return _clamp(weight * decay), _clamp(confidence * decay)
        delta = _clamp(payload.evidence_quality) / 50
        return _clamp(weight + delta), _clamp(confidence + delta)

    def _add_event(self, event: KnowledgeEvolutionEvent) -> None:
        self.db.add(
            KnowledgeEvolutionEventModel(
                event_id=event.event_id,
                evidence_id=event.evidence_id,
                node_id=event.node_id,
                edge_id=event.edge_id,
                event_type=event.event_type,
                previous_weight=event.previous_weight,
                new_weight=event.new_weight,
                previous_confidence=event.previous_confidence,
                new_confidence=event.new_confidence,
                reason=event.reason,
                created_by=self.user_id,
            )
        )


def core_engine_schema() -> CoreEngineSchema:
    return CoreEngineSchema(
        graph_schema={
            "node": ["id", "name", "node_type", "layer", "parent_ids", "confidence", "evidence_count", "evidence_quality", "time_decay", "attributes"],
            "edge": ["id", "from_node_id", "to_node_id", "relation_type", "weight", "confidence", "evidence_count", "evidence_quality", "time_decay", "evidence_sources", "attributes"],
            "root_layer": ["Seek Gain", "Avoid Loss"],
            "evolution_layer": ["Survival", "Reproduction", "Resource", "Exploration"],
            "human_motivation_layer": ["生存", "安全", "健康", "爱", "归属", "尊严", "权力", "自由", "扩张", "好奇", "娱乐", "懒惰", "恐惧"],
        },
        proof_score_algorithm={
            "root_dependency": "graph_node_ids + graph_edge_ids",
            "formula": "evidence_count*0.15 + evidence_quality*0.20 + sample_size*0.15 + conversion_signal*0.20 + consistency*0.15 + statistical_confidence*0.15",
            "state_machine": ["验证成功", "验证失败", "继续验证", "样本不足"],
        },
        capital_allocation_algorithm={
            "root_dependency": "evidence_id + graph_node_ids + graph_edge_ids",
            "formula": "opportunity_score*0.25 + proof_score*0.35 + (100-risk_score)*0.25 + information_gain*0.15",
            "actions": ["Close", "Observe", "Continue", "Scale"],
        },
        knowledge_evolution_algorithm={
            "root_dependency": "node_ids + edge_ids + evidence_id",
            "enter": "继续验证",
            "reinforce": "验证成功",
            "decay": "样本不足或弱验证失败",
            "eliminate": "低证明分验证失败",
        },
        er_diagram=(
            "erDiagram\n"
            "  human_nature_graph_nodes ||--o{ human_nature_graph_edges : from_node\n"
            "  human_nature_graph_nodes ||--o{ human_nature_graph_edges : to_node\n"
            "  human_nature_graph_nodes ||--o{ core_engine_evidence : graph_node_ids\n"
            "  human_nature_graph_edges ||--o{ core_engine_evidence : graph_edge_ids\n"
            "  core_engine_evidence ||--o{ knowledge_evolution_events : evidence\n"
            "  core_engine_evidence ||--o{ capital_allocation_records : evidence\n"
            "  human_nature_graph_nodes ||--o{ knowledge_evolution_events : node\n"
            "  human_nature_graph_edges ||--o{ knowledge_evolution_events : edge\n"
        ),
        service_architecture={
            "engines": [
                "HumanNatureGraphEngine",
                "ProofScoreEngine",
                "CapitalAllocationEngine",
                "KnowledgeEvolutionEngine",
            ],
            "visibility": "super_admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
