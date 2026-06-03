from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from dependencies.auth import get_user_scope_ids
from schemas.auth import UserResponse
from schemas.opc_os import (
    CapitalAllocation,
    CapitalAllocationInput,
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
from services.opc_os_persistence import OPCOSPersistenceService
from services.opc_os_v5 import OPCOSV5ExecutionService

router = APIRouter(prefix="/api/v1/opc-os", tags=["opc-os"])


class ModuleExecutionRequest(BaseModel):
    source_module: str
    source_record_id: int | None = None
    asin: str = ""
    title: str = ""
    opportunity: OpportunityInput


def _service(current_user: UserResponse) -> OPCOSV5ExecutionService:
    return OPCOSV5ExecutionService(user_id=str(current_user.id))


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "V5"}


@router.post("/opportunities", response_model=Opportunity)
async def create_opportunity(
    payload: OpportunityInput,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    opportunity = _service(current_user).create_opportunity(payload)
    await OPCOSPersistenceService(db).save_object(
        user_id=str(current_user.id),
        object_type="opportunity",
        payload=opportunity,
        title=opportunity.title,
    )
    return opportunity


@router.get("/opportunities", response_model=list[Opportunity])
async def list_opportunities(current_user: UserResponse = Depends(get_current_user)):
    return _service(current_user).list_opportunities()


@router.get("/records")
async def list_records(
    object_type: str = Query(default=""),
    opportunity_id: str = Query(default=""),
    source_module: str = Query(default=""),
    asin: str = Query(default=""),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope_user_ids = await get_user_scope_ids(current_user, db)
    return await OPCOSPersistenceService(db).list_objects(
        user_id=scope_user_ids,
        object_type=object_type,
        opportunity_id=opportunity_id,
        source_module=source_module,
        asin=asin,
        skip=skip,
        limit=limit,
    )


@router.post("/uncertainties/{opportunity_id}", response_model=UncertaintyQueue)
async def build_uncertainties(
    opportunity_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = _service(current_user).build_uncertainties(opportunity_id)
    if not result.uncertainty_queue:
        raise HTTPException(status_code=404, detail="暂无")
    persistence = OPCOSPersistenceService(db)
    for item in result.uncertainty_queue:
        await persistence.save_object(
            user_id=str(current_user.id),
            object_type="uncertainty",
            payload=item,
            opportunity_id=opportunity_id,
        )
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
    db: AsyncSession = Depends(get_db),
):
    plan = _service(current_user).create_proof_plan(payload)
    await OPCOSPersistenceService(db).save_object(
        user_id=str(current_user.id),
        object_type="proof_plan",
        payload=plan,
        opportunity_id=plan.opportunity_id,
    )
    return plan


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
    db: AsyncSession = Depends(get_db),
):
    execution = _service(current_user).execute_experiment(payload)
    await OPCOSPersistenceService(db).save_object(
        user_id=str(current_user.id),
        object_type="experiment_execution",
        payload=execution,
    )
    return execution


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
    db: AsyncSession = Depends(get_db),
):
    evidence = _service(current_user).score_evidence(payload)
    await OPCOSPersistenceService(db).save_object(
        user_id=str(current_user.id),
        object_type="evidence",
        payload=evidence,
    )
    return evidence


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
    db: AsyncSession = Depends(get_db),
):
    decision = _service(current_user).create_capital_decision(payload)
    await OPCOSPersistenceService(db).save_object(
        user_id=str(current_user.id),
        object_type="capital_decision",
        payload=decision,
        opportunity_id=decision.opportunity_id,
    )
    return decision


@router.get("/capital_decisions", response_model=list[CapitalDecision])
async def list_capital_decisions(
    opportunity_id: str | None = Query(default=None),
    current_user: UserResponse = Depends(get_current_user),
):
    return _service(current_user).list_capital_decisions(opportunity_id)


@router.post("/capital_allocations", response_model=CapitalAllocation)
async def allocate_capital(
    payload: CapitalAllocationInput,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope_user_ids = await get_user_scope_ids(current_user, db)
    records = await OPCOSPersistenceService(db).list_objects(
        user_id=scope_user_ids,
        object_type="capital_decision",
        source_module=payload.source_module,
        asin=payload.asin,
        limit=200,
    )
    decisions: list[CapitalDecision] = []
    for item in records.get("items") or []:
        data = item.get("payload") or {}
        if not isinstance(data, dict):
            continue
        try:
            decisions.append(CapitalDecision(**data))
        except Exception:
            continue
    allocation = _service(current_user).allocate_capital(payload, decisions)
    await OPCOSPersistenceService(db).save_object(
        user_id=str(current_user.id),
        object_type="capital_allocation",
        payload=allocation,
        source_module=payload.source_module,
        asin=payload.asin,
    )
    return allocation


@router.post("/capital_decisions/{decision_id}/confirm", response_model=CapitalDecision)
async def confirm_capital_decision(
    decision_id: str,
    payload: CapitalDecisionConfirmInput,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = _service(current_user).confirm_capital_decision(
        decision_id=decision_id,
        confirmed=payload.confirmed,
        confirmed_by=str(current_user.id),
    )
    if not result:
        raise HTTPException(status_code=404, detail="暂无")
    await OPCOSPersistenceService(db).save_object(
        user_id=str(current_user.id),
        object_type="capital_decision",
        payload=result,
        opportunity_id=result.opportunity_id,
    )
    return result


@router.post("/knowledge_graph/evolve", response_model=KnowledgeEvolutionResult)
async def evolve_knowledge_graph(
    payload: KnowledgeEvolutionInput,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = _service(current_user).evolve_knowledge_graph(payload)
    await OPCOSPersistenceService(db).save_object(
        user_id=str(current_user.id),
        object_type="knowledge_evolution",
        payload=result,
        opportunity_id=result.opportunity_id,
    )
    return result


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
    db: AsyncSession = Depends(get_db),
):
    result = _service(current_user).run_execution_loop(payload)
    await OPCOSPersistenceService(db).save_execution_bundle(
        user_id=str(current_user.id),
        bundle=result.model_dump(mode="json"),
        source_module="opc_os",
        title=result.opportunity.title,
    )
    return result


@router.post("/module-execution", response_model=OPCExecutionResult)
async def run_module_execution(
    payload: ModuleExecutionRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = _service(current_user).run_execution_loop(payload.opportunity)
    await OPCOSPersistenceService(db).save_execution_bundle(
        user_id=str(current_user.id),
        bundle=result.model_dump(mode="json"),
        source_module=payload.source_module,
        source_record_id=payload.source_record_id,
        asin=payload.asin,
        title=payload.title or result.opportunity.title,
    )
    return result
