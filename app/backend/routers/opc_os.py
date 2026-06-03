from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies.auth import get_current_user
from schemas.auth import UserResponse
from schemas.opc_os import (
    CapitalDecision,
    CapitalDecisionConfirmInput,
    CapitalDecisionInput,
    Evidence,
    EvidenceInput,
    ExperimentExecution,
    ExperimentExecutionInput,
    KnowledgeEdge,
    KnowledgeEvolutionInput,
    KnowledgeEvolutionResult,
    KnowledgeNode,
    OPCExecutionResult,
    Opportunity,
    OpportunityInput,
    ProofPlan,
    ProofPlanInput,
    Uncertainty,
    UncertaintyQueue,
)
from services.opc_os_v5 import OPCOSV5ExecutionService

router = APIRouter(prefix="/api/v1/opc-os", tags=["opc-os"])


def _service(current_user: UserResponse) -> OPCOSV5ExecutionService:
    return OPCOSV5ExecutionService(user_id=str(current_user.id))


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "V5"}


@router.post("/opportunities", response_model=Opportunity)
async def create_opportunity(
    payload: OpportunityInput,
    current_user: UserResponse = Depends(get_current_user),
):
    return _service(current_user).create_opportunity(payload)


@router.get("/opportunities", response_model=list[Opportunity])
async def list_opportunities(current_user: UserResponse = Depends(get_current_user)):
    return _service(current_user).list_opportunities()


@router.post("/uncertainties/{opportunity_id}", response_model=UncertaintyQueue)
async def build_uncertainties(
    opportunity_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    result = _service(current_user).build_uncertainties(opportunity_id)
    if not result.uncertainty_queue:
        raise HTTPException(status_code=404, detail="暂无")
    return result


@router.get("/uncertainties", response_model=list[Uncertainty])
async def list_uncertainties(
    opportunity_id: str | None = Query(default=None),
    current_user: UserResponse = Depends(get_current_user),
):
    return _service(current_user).list_uncertainties(opportunity_id)


@router.post("/proof_plans", response_model=ProofPlan)
async def create_proof_plan(
    payload: ProofPlanInput,
    current_user: UserResponse = Depends(get_current_user),
):
    return _service(current_user).create_proof_plan(payload)


@router.get("/proof_plans", response_model=list[ProofPlan])
async def list_proof_plans(
    opportunity_id: str | None = Query(default=None),
    current_user: UserResponse = Depends(get_current_user),
):
    return _service(current_user).list_proof_plans(opportunity_id)


@router.post("/experiments", response_model=ExperimentExecution)
async def execute_experiment(
    payload: ExperimentExecutionInput,
    current_user: UserResponse = Depends(get_current_user),
):
    return _service(current_user).execute_experiment(payload)


@router.get("/experiments", response_model=list[ExperimentExecution])
async def list_experiments(
    proof_plan_id: str | None = Query(default=None),
    current_user: UserResponse = Depends(get_current_user),
):
    return _service(current_user).list_executions(proof_plan_id)


@router.post("/evidence", response_model=Evidence)
async def score_evidence(
    payload: EvidenceInput,
    current_user: UserResponse = Depends(get_current_user),
):
    return _service(current_user).score_evidence(payload)


@router.get("/evidence", response_model=list[Evidence])
async def list_evidence(
    proof_plan_id: str | None = Query(default=None),
    current_user: UserResponse = Depends(get_current_user),
):
    return _service(current_user).list_evidence(proof_plan_id)


@router.post("/capital_decisions", response_model=CapitalDecision)
async def create_capital_decision(
    payload: CapitalDecisionInput,
    current_user: UserResponse = Depends(get_current_user),
):
    return _service(current_user).create_capital_decision(payload)


@router.get("/capital_decisions", response_model=list[CapitalDecision])
async def list_capital_decisions(
    opportunity_id: str | None = Query(default=None),
    current_user: UserResponse = Depends(get_current_user),
):
    return _service(current_user).list_capital_decisions(opportunity_id)


@router.post("/capital_decisions/{decision_id}/confirm", response_model=CapitalDecision)
async def confirm_capital_decision(
    decision_id: str,
    payload: CapitalDecisionConfirmInput,
    current_user: UserResponse = Depends(get_current_user),
):
    result = _service(current_user).confirm_capital_decision(
        decision_id=decision_id,
        confirmed=payload.confirmed,
        confirmed_by=str(current_user.id),
    )
    if not result:
        raise HTTPException(status_code=404, detail="暂无")
    return result


@router.post("/knowledge_graph/evolve", response_model=KnowledgeEvolutionResult)
async def evolve_knowledge_graph(
    payload: KnowledgeEvolutionInput,
    current_user: UserResponse = Depends(get_current_user),
):
    return _service(current_user).evolve_knowledge_graph(payload)


@router.get("/knowledge_graph/nodes", response_model=list[KnowledgeNode])
async def list_knowledge_nodes(current_user: UserResponse = Depends(get_current_user)):
    return _service(current_user).list_nodes()


@router.get("/knowledge_graph/edges", response_model=list[KnowledgeEdge])
async def list_knowledge_edges(current_user: UserResponse = Depends(get_current_user)):
    return _service(current_user).list_edges()


@router.post("/run", response_model=OPCExecutionResult)
async def run_execution_loop(
    payload: OpportunityInput,
    current_user: UserResponse = Depends(get_current_user),
):
    return _service(current_user).run_execution_loop(payload)