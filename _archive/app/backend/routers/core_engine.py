from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_super_admin_user
from schemas.auth import UserResponse
from schemas.core_engines import (
    CapitalAllocationInput,
    CapitalAllocationResult,
    CoreEngineSchema,
    GraphEdge,
    GraphEdgeInput,
    GraphNode,
    GraphNodeInput,
    KnowledgeEvolutionInput,
    KnowledgeEvolutionResult,
    ProofScoreInput,
    ProofScoreResult,
    WeightUpdateInput,
)
from services.core_engines import (
    CapitalAllocationEngine,
    HumanNatureGraphEngine,
    KnowledgeEvolutionEngine,
    ProofScoreEngine,
    core_engine_schema,
)

router = APIRouter(
    prefix="/api/v1/core-engine",
    tags=["core-engine"],
    dependencies=[Depends(get_super_admin_user)],
)


@router.get("/schema", response_model=CoreEngineSchema)
async def get_core_engine_schema() -> CoreEngineSchema:
    return core_engine_schema()


@router.post("/graph/seed")
async def seed_human_nature_graph(
    current_user: UserResponse = Depends(get_super_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await HumanNatureGraphEngine(db, str(current_user.id)).seed_graph()


@router.post("/graph/nodes", response_model=GraphNode)
async def create_graph_node(
    payload: GraphNodeInput,
    current_user: UserResponse = Depends(get_super_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await HumanNatureGraphEngine(db, str(current_user.id)).create_node(payload)


@router.get("/graph/nodes", response_model=list[GraphNode])
async def list_graph_nodes(
    layer: str = Query(default=""),
    current_user: UserResponse = Depends(get_super_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await HumanNatureGraphEngine(db, str(current_user.id)).list_nodes(layer)


@router.post("/graph/edges", response_model=GraphEdge)
async def create_graph_edge(
    payload: GraphEdgeInput,
    current_user: UserResponse = Depends(get_super_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await HumanNatureGraphEngine(db, str(current_user.id)).create_edge(payload)


@router.get("/graph/edges", response_model=list[GraphEdge])
async def list_graph_edges(
    relation_type: str = Query(default=""),
    current_user: UserResponse = Depends(get_super_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await HumanNatureGraphEngine(db, str(current_user.id)).list_edges(relation_type)


@router.post("/graph/edges/{edge_id}/weight", response_model=GraphEdge)
async def update_graph_edge_weight(
    edge_id: str,
    payload: WeightUpdateInput,
    current_user: UserResponse = Depends(get_super_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await HumanNatureGraphEngine(db, str(current_user.id)).update_edge_weight(edge_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="暂无")
    return result


@router.post("/proof-score/evaluate", response_model=ProofScoreResult)
async def evaluate_proof_score(
    payload: ProofScoreInput,
    current_user: UserResponse = Depends(get_super_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await ProofScoreEngine(db, str(current_user.id)).evaluate(payload)


@router.post("/capital-allocation/evaluate", response_model=CapitalAllocationResult)
async def evaluate_capital_allocation(
    payload: CapitalAllocationInput,
    current_user: UserResponse = Depends(get_super_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await CapitalAllocationEngine(db, str(current_user.id)).evaluate(payload)


@router.post("/knowledge-evolution/evaluate", response_model=KnowledgeEvolutionResult)
async def evaluate_knowledge_evolution(
    payload: KnowledgeEvolutionInput,
    current_user: UserResponse = Depends(get_super_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await KnowledgeEvolutionEngine(db, str(current_user.id)).evaluate(payload)
