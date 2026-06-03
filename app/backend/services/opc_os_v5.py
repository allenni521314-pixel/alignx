from datetime import datetime

from schemas.opc_os import (
    CapitalDecision,
    CapitalDecisionInput,
    CapitalAllocation,
    CapitalAllocationInput,
    CapitalAllocationItem,
    Evidence,
    EvidenceInput,
    ExperimentExecution,
    ExperimentExecutionInput,
    KnowledgeEdge,
    KnowledgeEvolutionInput,
    KnowledgeEvolutionResult,
    KnowledgeNode,
    MetricThreshold,
    OPCExecutionResult,
    Opportunity,
    OpportunityInput,
    ProofPlan,
    ProofPlanInput,
    Uncertainty,
    UncertaintyQueue,
)


class OPCOSV5Store:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, object]]] = {}

    def bucket(self, user_id: str) -> dict[str, dict[str, object]]:
        if user_id not in self._data:
            self._data[user_id] = {
                "opportunities": {},
                "uncertainties": {},
                "proof_plans": {},
                "executions": {},
                "evidence": {},
                "capital_decisions": {},
                "capital_allocations": {},
                "knowledge_nodes": {},
                "knowledge_edges": {},
            }
        return self._data[user_id]


store = OPCOSV5Store()


class OPCOSV5ExecutionService:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self.data = store.bucket(user_id)

    def create_opportunity(self, payload: OpportunityInput) -> Opportunity:
        opportunity = Opportunity(
            title=payload.title or "待录入",
            human_drivers=payload.human_drivers or ["待录入"],
            demand=payload.demand or "待录入",
            scenario=payload.scenario or "待录入",
            initial_score=max(0, min(100, payload.initial_score)),
        )
        self.data["opportunities"][opportunity.opportunity_id] = opportunity
        return opportunity

    def list_opportunities(self) -> list[Opportunity]:
        return list(self.data["opportunities"].values())

    def get_opportunity(self, opportunity_id: str) -> Opportunity | None:
        value = self.data["opportunities"].get(opportunity_id)
        return value if isinstance(value, Opportunity) else None

    def build_uncertainties(self, opportunity_id: str) -> UncertaintyQueue:
        opportunity = self.get_opportunity(opportunity_id)
        if not opportunity:
            return UncertaintyQueue(opportunity_id=opportunity_id, uncertainty_queue=[])

        checks = [
            ("用户需求是否成立", "demand", 90 - opportunity.initial_score),
            ("平台是否能识别", "platform", 70),
            ("页面是否能承接", "conversion", 70),
            ("广告是否能验证", "ad_validation", 65),
            ("投入是否值得继续", "roi", 60),
        ]
        queue = [
            Uncertainty(
                opportunity_id=opportunity_id,
                question=question,
                risk_type=risk_type,
                risk_score=max(0, min(100, risk_score)),
                priority=index + 1,
            )
            for index, (question, risk_type, risk_score) in enumerate(checks)
        ]
        queue.sort(key=lambda item: item.risk_score, reverse=True)
        for index, item in enumerate(queue, start=1):
            item.priority = index
            self.data["uncertainties"][item.uncertainty_id] = item
        return UncertaintyQueue(opportunity_id=opportunity_id, uncertainty_queue=queue)

    def list_uncertainties(self, opportunity_id: str | None = None) -> list[Uncertainty]:
        values = list(self.data["uncertainties"].values())
        items = [item for item in values if isinstance(item, Uncertainty)]
        if opportunity_id:
            return [item for item in items if item.opportunity_id == opportunity_id]
        return items

    def create_proof_plan(self, payload: ProofPlanInput) -> ProofPlan:
        metrics = payload.metrics or [
            MetricThreshold(metric="CTR"),
            MetricThreshold(metric="CVR"),
            MetricThreshold(metric="订单"),
            MetricThreshold(metric="转化"),
            MetricThreshold(metric="ROI"),
        ]
        plan = ProofPlan(
            opportunity_id=payload.opportunity_id,
            validation_goal=payload.validation_goal or "待录入",
            metrics=metrics,
            sample_size=max(0, payload.sample_size),
            budget_suggestion=max(0, payload.budget_suggestion),
        )
        self.data["proof_plans"][plan.proof_plan_id] = plan
        return plan

    def list_proof_plans(self, opportunity_id: str | None = None) -> list[ProofPlan]:
        values = list(self.data["proof_plans"].values())
        items = [item for item in values if isinstance(item, ProofPlan)]
        if opportunity_id:
            return [item for item in items if item.opportunity_id == opportunity_id]
        return items

    def execute_experiment(self, payload: ExperimentExecutionInput) -> ExperimentExecution:
        status = "awaiting_manual_result" if payload.manual_confirmed else "pending_manual_launch"
        execution = ExperimentExecution(
            proof_plan_id=payload.proof_plan_id,
            channel=payload.channel,
            status=status,
            manual_required=True,
            started_at=datetime.utcnow() if payload.manual_confirmed else None,
        )
        self.data["executions"][execution.execution_id] = execution
        return execution

    def list_executions(self, proof_plan_id: str | None = None) -> list[ExperimentExecution]:
        values = list(self.data["executions"].values())
        items = [item for item in values if isinstance(item, ExperimentExecution)]
        if proof_plan_id:
            return [item for item in items if item.proof_plan_id == proof_plan_id]
        return items

    def score_evidence(self, payload: EvidenceInput) -> Evidence:
        score = self._calculate_proof_score(payload)
        evidence = Evidence(
            proof_plan_id=payload.proof_plan_id,
            execution_id=payload.execution_id,
            metrics=payload.metrics,
            evidence_quality=max(0, min(100, payload.evidence_quality)),
            proof_score=score,
        )
        self.data["evidence"][evidence.evidence_id] = evidence
        return evidence

    def list_evidence(self, proof_plan_id: str | None = None) -> list[Evidence]:
        values = list(self.data["evidence"].values())
        items = [item for item in values if isinstance(item, Evidence)]
        if proof_plan_id:
            return [item for item in items if item.proof_plan_id == proof_plan_id]
        return items

    def create_capital_decision(self, payload: CapitalDecisionInput) -> CapitalDecision:
        proof_score = max(0, min(100, payload.proof_score))
        risk_score = max(0, min(100, payload.risk_score))
        information_gain = max(0, min(100, payload.information_gain))
        action = self._capital_action(proof_score, risk_score)
        decision = CapitalDecision(
            opportunity_id=payload.opportunity_id,
            proof_score=proof_score,
            risk_score=risk_score,
            information_gain=information_gain,
            suggested_action=action,
            requires_human_confirmation=True,
            confirmed=False,
        )
        self.data["capital_decisions"][decision.capital_decision_id] = decision
        return decision

    def confirm_capital_decision(self, decision_id: str, confirmed: bool, confirmed_by: str) -> CapitalDecision | None:
        value = self.data["capital_decisions"].get(decision_id)
        if not isinstance(value, CapitalDecision):
            return None
        value.confirmed = confirmed
        value.confirmed_by = confirmed_by
        value.confirmed_at = datetime.utcnow()
        return value

    def list_capital_decisions(self, opportunity_id: str | None = None) -> list[CapitalDecision]:
        values = list(self.data["capital_decisions"].values())
        items = [item for item in values if isinstance(item, CapitalDecision)]
        if opportunity_id:
            return [item for item in items if item.opportunity_id == opportunity_id]
        return items

    def allocate_capital(self, payload: CapitalAllocationInput, decisions: list[CapitalDecision]) -> CapitalAllocation:
        selected_ids = set(payload.opportunity_ids or [])
        filtered = [
            item
            for item in decisions
            if not selected_ids or item.opportunity_id in selected_ids
        ]
        latest_by_opportunity: dict[str, CapitalDecision] = {}
        for item in filtered:
            previous = latest_by_opportunity.get(item.opportunity_id)
            if not previous or item.created_at >= previous.created_at:
                latest_by_opportunity[item.opportunity_id] = item

        scored: list[tuple[CapitalDecision, float]] = []
        for item in latest_by_opportunity.values():
            if item.suggested_action == "Close":
                score = 0
            else:
                score = max(0, item.proof_score - item.risk_score * 0.35 + item.information_gain * 0.1)
            scored.append((item, round(score, 2)))
        total_score = sum(score for _, score in scored)
        budget = max(0, payload.budget)
        items = [
            CapitalAllocationItem(
                opportunity_id=item.opportunity_id,
                suggested_action=item.suggested_action,
                proof_score=item.proof_score,
                risk_score=item.risk_score,
                information_gain=item.information_gain,
                allocation_weight=round(score / total_score * 100, 2) if total_score else 0,
                suggested_budget=round(budget * score / total_score, 2) if total_score and budget else 0,
            )
            for item, score in sorted(scored, key=lambda pair: pair[1], reverse=True)
        ]
        allocation = CapitalAllocation(budget=budget, items=items)
        self.data["capital_allocations"][allocation.allocation_id] = allocation
        return allocation

    def evolve_knowledge_graph(self, payload: KnowledgeEvolutionInput) -> KnowledgeEvolutionResult:
        node_updates = [self._updated_node(node) for node in payload.nodes]
        edge_updates = [self._updated_edge(edge, payload.evidence_id) for edge in payload.edges]
        for node in node_updates:
            self.data["knowledge_nodes"][node.id] = node
        for edge in edge_updates:
            self.data["knowledge_edges"][edge.id] = edge
        return KnowledgeEvolutionResult(
            opportunity_id=payload.opportunity_id,
            evidence_id=payload.evidence_id,
            node_updates=node_updates,
            edge_updates=edge_updates,
            status="待确认",
        )

    def list_nodes(self) -> list[KnowledgeNode]:
        return [item for item in self.data["knowledge_nodes"].values() if isinstance(item, KnowledgeNode)]

    def list_edges(self) -> list[KnowledgeEdge]:
        return [item for item in self.data["knowledge_edges"].values() if isinstance(item, KnowledgeEdge)]

    def run_execution_loop(self, opportunity_payload: OpportunityInput) -> OPCExecutionResult:
        opportunity = self.create_opportunity(opportunity_payload)
        uncertainty = self.build_uncertainties(opportunity.opportunity_id)
        proof_plan = self.create_proof_plan(
            ProofPlanInput(
                opportunity_id=opportunity.opportunity_id,
                validation_goal="待录入",
                sample_size=0,
                budget_suggestion=0,
            )
        )
        experiment = self.execute_experiment(
            ExperimentExecutionInput(
                proof_plan_id=proof_plan.proof_plan_id,
                channel="small_budget_ad",
                manual_confirmed=False,
            )
        )
        evidence = self.score_evidence(EvidenceInput(proof_plan_id=proof_plan.proof_plan_id))
        capital_decision = self.create_capital_decision(
            CapitalDecisionInput(
                opportunity_id=opportunity.opportunity_id,
                proof_score=evidence.proof_score,
                risk_score=uncertainty.uncertainty_queue[0].risk_score if uncertainty.uncertainty_queue else 0,
                information_gain=0,
            )
        )
        knowledge_evolution = self.evolve_knowledge_graph(
            KnowledgeEvolutionInput(
                opportunity_id=opportunity.opportunity_id,
                evidence_id=evidence.evidence_id,
            )
        )
        return OPCExecutionResult(
            opportunity=opportunity,
            uncertainty_queue=uncertainty.uncertainty_queue,
            proof_plan=proof_plan,
            experiment_execution=experiment,
            evidence=evidence,
            capital_decision=capital_decision,
            knowledge_evolution=knowledge_evolution,
        )

    def _calculate_proof_score(self, payload: EvidenceInput) -> float:
        if not payload.metrics:
            return 0
        metric_score = sum(max(0, min(100, value)) for value in payload.metrics.values()) / len(payload.metrics)
        quality = max(0, min(100, payload.evidence_quality))
        return round(metric_score * 0.7 + quality * 0.3, 2)

    def _capital_action(self, proof_score: float, risk_score: float) -> str:
        if proof_score <= 0:
            return "Observe"
        adjusted = proof_score - risk_score * 0.35
        if adjusted >= 75:
            return "Scale"
        if adjusted >= 55:
            return "Continue"
        if adjusted >= 35:
            return "Observe"
        return "Close"

    def _updated_node(self, node: KnowledgeNode) -> KnowledgeNode:
        attributes = dict(node.attributes)
        attributes["evidence_count"] = int(attributes.get("evidence_count", 0)) + 1
        attributes["confidence"] = min(100, float(attributes.get("confidence", 0)) + 5)
        attributes["time_decay"] = max(0, float(attributes.get("time_decay", 1)) * 0.98)
        node.attributes = attributes
        return node

    def _updated_edge(self, edge: KnowledgeEdge, evidence_id: str | None) -> KnowledgeEdge:
        edge.weight = min(100, max(0, edge.weight + 5))
        if evidence_id and evidence_id not in edge.evidence_sources:
            edge.evidence_sources.append(evidence_id)
        return edge
