"""
AlignX six-node Agent chain.

This layer connects the existing workflow stages to the AI Gateway while keeping
legacy business modules untouched. Each node receives standardized chain data
and returns the same structured decision contract.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from services.ai_gateway import AgentRequest, AgentResponse, AIGatewayService

AgentNodeKey = Literal[
    "selection",
    "launch_check",
    "listing_diagnosis",
    "competitor",
    "ad_validation",
    "review_optimization",
]


class AgentNodeDefinition(BaseModel):
    key: AgentNodeKey
    agent: str
    title: str
    module: str
    path: str
    task: str
    required_stage_keys: list[str] = Field(default_factory=list)


class AgentNodeRunRequest(BaseModel):
    node: AgentNodeKey
    depth: Literal["light", "standard", "deep"] = "standard"
    dry_run: Optional[bool] = None
    extra_context: dict[str, Any] = Field(default_factory=dict)


class AgentNodeRunResponse(BaseModel):
    node: AgentNodeDefinition
    connected: bool
    missing_stage_keys: list[str]
    ai: AgentResponse


NODE_DEFINITIONS: dict[AgentNodeKey, AgentNodeDefinition] = {
    "selection": AgentNodeDefinition(
        key="selection",
        agent="selection_agent",
        title="6维选品判断",
        module="选品决策",
        path="/asin-manager",
        task="判断当前 ASIN 是否值得进入机会池，并说明进入、观察或淘汰的依据。",
        required_stage_keys=["selection"],
    ),
    "launch_check": AgentNodeDefinition(
        key="launch_check",
        agent="launch_check_agent",
        title="Listing 上新检测",
        module="Listing 运营",
        path="/listing-diagnosis?view=launch-check",
        task="判断上架前 Listing 是否具备上线条件，输出风险等级、必改项和上新前修改建议。",
        required_stage_keys=["selection", "launch_check"],
    ),
    "listing_diagnosis": AgentNodeDefinition(
        key="listing_diagnosis",
        agent="listing_diagnosis_agent",
        title="本品上线后诊断",
        module="Listing 运营",
        path="/listing-diagnosis",
        task="基于评论需求对齐度、Cosmo 语义对齐度和因果转化对齐度定位本品不转化原因。",
        required_stage_keys=["selection", "launch_check", "listing_diagnosis"],
    ),
    "competitor": AgentNodeDefinition(
        key="competitor",
        agent="competitor_agent",
        title="竞品同尺诊断",
        module="Listing 运营",
        path="/listing-diagnosis?view=competitor",
        task="用同一套标准比较 Top 竞品与本品表达差距，输出差距、优先级和建议动作。",
        required_stage_keys=["selection", "listing_diagnosis"],
    ),
    "ad_validation": AgentNodeDefinition(
        key="ad_validation",
        agent="ad_validation_agent",
        title="广告验证判断",
        module="广告投放",
        path="/ad-analytics?view=validation",
        task="用广告点击、转化、ACOS 和搜索词表现验证 Listing 诊断假设是否成立。",
        required_stage_keys=["listing_diagnosis", "ab_test", "ad_validation"],
    ),
    "review_optimization": AgentNodeDefinition(
        key="review_optimization",
        agent="review_optimization_agent",
        title="复盘回流优化",
        module="复盘优化",
        path="/optimization-suggestions?view=next-round",
        task="沉淀执行结果、判断命中率和失败原因，生成下一轮优化动作。",
        required_stage_keys=["ad_validation", "review"],
    ),
}


def get_agent_node_status(chain: dict[str, Any]) -> list[dict[str, Any]]:
    stages = {stage.get("key"): stage for stage in chain.get("stages", [])}
    status: list[dict[str, Any]] = []

    for node in NODE_DEFINITIONS.values():
        missing = [
            stage_key
            for stage_key in node.required_stage_keys
            if not stages.get(stage_key) or stages[stage_key].get("status") != "completed"
        ]
        status.append(
            {
                **node.model_dump(),
                "connected": True,
                "ready": len(missing) == 0,
                "missing_stage_keys": missing,
                "mode": "live_or_dry_run",
            }
        )
    return status


async def run_agent_node(chain: dict[str, Any], request: AgentNodeRunRequest) -> AgentNodeRunResponse:
    node = NODE_DEFINITIONS[request.node]
    gateway = AIGatewayService()
    configured = gateway.status().configured
    dry_run = request.dry_run if request.dry_run is not None else not configured
    stages = {stage.get("key"): stage for stage in chain.get("stages", [])}
    missing = [
        stage_key
        for stage_key in node.required_stage_keys
        if not stages.get(stage_key) or stages[stage_key].get("status") != "completed"
    ]

    payload = {
        "product": chain.get("product"),
        "chain_status": {
            "completed_stages": chain.get("completed_stages"),
            "total_stages": chain.get("total_stages"),
            "integrity_score": chain.get("integrity_score"),
        },
        "current_node": node.model_dump(),
        "missing_stage_keys": missing,
        "stages": chain.get("stages", []),
        "existing_agent_decision": chain.get("agent_decision"),
        "extra_context": request.extra_context,
    }

    ai = await gateway.run_agent(
        AgentRequest(
            agent=node.agent,  # type: ignore[arg-type]
            task=node.task,
            payload=payload,
            depth=request.depth,
            dry_run=dry_run,
        )
    )
    return AgentNodeRunResponse(node=node, connected=True, missing_stage_keys=missing, ai=ai)


async def run_all_agent_nodes(chain: dict[str, Any], depth: Literal["light", "standard", "deep"] = "standard") -> list[AgentNodeRunResponse]:
    responses: list[AgentNodeRunResponse] = []
    for node_key in NODE_DEFINITIONS:
        responses.append(await run_agent_node(chain, AgentNodeRunRequest(node=node_key, depth=depth)))
    return responses
