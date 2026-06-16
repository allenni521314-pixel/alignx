"""
AlignX six-node Agent chain.

This layer connects the existing workflow stages to the AI Gateway while keeping
legacy business modules untouched. Each node receives standardized chain data
and returns the same structured decision contract.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from services.ai_gateway import AgentRequest, AgentResponse, AIGatewayService
from services.unified_ai import UnifiedAIClient

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
    execution_roles: list[str] = Field(default_factory=list)
    forbidden_model_roles: list[str] = Field(default_factory=list)
    default_depth: Literal["light", "standard", "deep"] = "standard"


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


class SelectionDispatchStep(BaseModel):
    node: AgentNodeKey
    priority: Literal["P0", "P1", "P2"] = "P1"
    status: Literal["ready", "blocked", "skip"] = "blocked"
    reason: str = "暂无"
    blocked_by: list[str] = Field(default_factory=list)


class SelectionDispatchPlan(BaseModel):
    supervisor: str = "Selection"
    mode: Literal["dry_run", "live"] = "dry_run"
    dispatch_order: list[SelectionDispatchStep] = Field(default_factory=list)
    run_now: list[AgentNodeKey] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    learning_update: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


class SelectionOrchestrationRequest(BaseModel):
    depth: Literal["light", "standard", "deep"] = "deep"
    dry_run: Optional[bool] = None
    auto_run: bool = True
    max_nodes: int = Field(default=3, ge=0, le=6)
    extra_context: dict[str, Any] = Field(default_factory=dict)


class SelectionOrchestrationResponse(BaseModel):
    plan: SelectionDispatchPlan
    executed_nodes: list[AgentNodeRunResponse] = Field(default_factory=list)


NODE_DEFINITIONS: dict[AgentNodeKey, AgentNodeDefinition] = {
    "selection": AgentNodeDefinition(
        key="selection",
        agent="selection_agent",
        title="6维选品判断",
        module="选品决策",
        path="/asin-manager",
        task="判断当前 ASIN 是否值得进入机会池，并说明进入、观察或淘汰的依据。",
        required_stage_keys=[],
        execution_roles=["scraping", "rules", "embedding_recall", "evidence_rerank", "text_reasoning"],
        forbidden_model_roles=["vision_ocr", "image_generation"],
        default_depth="standard",
    ),
    "launch_check": AgentNodeDefinition(
        key="launch_check",
        agent="launch_check_agent",
        title="Listing 上新检测",
        module="Listing 运营",
        path="/listing-diagnosis?view=launch-check",
        task="判断上架前 Listing 是否具备上线条件，输出风险等级、必改项和上新前修改建议。",
        required_stage_keys=["selection", "launch_check"],
        execution_roles=["rules", "vision_ocr", "embedding_recall", "evidence_rerank", "text_deep"],
        forbidden_model_roles=["image_generation_before_brief_ready"],
        default_depth="deep",
    ),
    "listing_diagnosis": AgentNodeDefinition(
        key="listing_diagnosis",
        agent="listing_diagnosis_agent",
        title="本品上线后诊断",
        module="Listing 运营",
        path="/listing-diagnosis",
        task="基于评论需求对齐度、Cosmo 语义对齐度和因果转化对齐度定位本品不转化原因。",
        required_stage_keys=["selection", "launch_check", "listing_diagnosis"],
        execution_roles=["rules", "buyer_voice", "vision_ocr", "embedding_recall", "evidence_rerank", "text_deep"],
        forbidden_model_roles=["image_generation"],
        default_depth="deep",
    ),
    "competitor": AgentNodeDefinition(
        key="competitor",
        agent="competitor_agent",
        title="竞品同尺诊断",
        module="Listing 运营",
        path="/listing-diagnosis?view=competitor",
        task="用同一套标准比较 Top 竞品与本品表达差距，输出差距、优先级和建议动作。",
        required_stage_keys=["selection", "listing_diagnosis"],
        execution_roles=["scraping", "rules", "vision_ocr", "embedding_recall", "evidence_rerank", "text_deep"],
        forbidden_model_roles=["image_generation"],
        default_depth="deep",
    ),
    "ad_validation": AgentNodeDefinition(
        key="ad_validation",
        agent="ad_validation_agent",
        title="广告验证判断",
        module="广告投放",
        path="/ad-analytics?view=validation",
        task="用广告点击、转化、ACOS 和搜索词表现验证 Listing 诊断假设是否成立。",
        required_stage_keys=["listing_diagnosis", "ab_test", "ad_validation"],
        execution_roles=["rules", "embedding_recall", "evidence_rerank", "text_reasoning"],
        forbidden_model_roles=["vision_ocr", "image_generation"],
        default_depth="standard",
    ),
    "review_optimization": AgentNodeDefinition(
        key="review_optimization",
        agent="review_optimization_agent",
        title="复盘回流优化",
        module="复盘优化",
        path="/optimization-suggestions?view=next-round",
        task="沉淀执行结果、判断命中率和失败原因，生成下一轮优化动作。",
        required_stage_keys=["ad_validation", "review"],
        execution_roles=["rules", "embedding_recall", "evidence_rerank", "text_deep"],
        forbidden_model_roles=["vision_ocr", "image_generation"],
        default_depth="deep",
    ),
}

SELECTION_MODEL_ROUTING_POLICY = {
    "supervisor": {
        "role": "selection_coordinator",
        "model_role": "AI_DEEP_MODEL",
        "allowed_actions": ["dispatch", "block", "prioritize", "learning_gate"],
        "forbidden_actions": ["replace_business_agent", "generate_listing_directly", "generate_image_directly"],
    },
    "stage_routes": {
        node_key: {
            "agent": node.agent,
            "model_route": node.execution_roles,
            "forbidden_model_roles": node.forbidden_model_roles,
            "default_depth": node.default_depth,
        }
        for node_key, node in NODE_DEFINITIONS.items()
    },
    "hard_gates": [
        "缺少 required_stage_keys 的节点必须 blocked。",
        "广告记录未绑定 hypothesis_id 时不能判断命中或失败。",
        "假设级点击少于100时只能输出待验证，不能输出未命中。",
        "没有 hit_status、miss_reason、next_action 的复盘结论不能进入学习记忆。",
        "图片生成只能在上架准入与图片Brief完整后执行，不能参与判断。",
    ],
}

SELECTION_DISPATCH_SYSTEM_PROMPT = "\n".join(
    [
        "你是 AlignX 选品调度。",
        "你只负责调度现有 Agent，不替代任何业务 Agent 直接完成判断。",
        "你必须根据 workflow chain、stage 状态、缺失项、已有 agent_decision 和学习记忆决定执行顺序。",
        "只允许调度 allowed_nodes 中列出的节点。",
        "你必须遵守 model_routing_policy 中的模型角色分工。",
        "系统只能输出调度、阻塞、优先级、学习门控，不得直接输出 Listing 成品、广告方案成品或图片成品。",
        "如果节点缺少必要证据，status 必须是 blocked，并写入 blocked_by。",
        "如果节点可以执行，status 必须是 ready。",
        "输出必须是JSON对象，不要输出Markdown，不要输出额外解释。",
    ]
)


def _safe_node_key(value: Any) -> AgentNodeKey | None:
    text = str(value or "").strip()
    return text if text in NODE_DEFINITIONS else None  # type: ignore[return-value]


def _safe_priority(value: Any) -> Literal["P0", "P1", "P2"]:
    text = str(value or "").strip().upper()
    if text in {"P0", "P1", "P2"}:
        return text  # type: ignore[return-value]
    return "P1"


def _safe_dispatch_status(value: Any) -> Literal["ready", "blocked", "skip"]:
    text = str(value or "").strip().lower()
    if text in {"ready", "blocked", "skip"}:
        return text  # type: ignore[return-value]
    return "blocked"


def _node_missing_stage_keys(chain: dict[str, Any], node: AgentNodeDefinition) -> list[str]:
    stages = {stage.get("key"): stage for stage in chain.get("stages", [])}
    return [
        stage_key
        for stage_key in node.required_stage_keys
        if not stages.get(stage_key) or stages[stage_key].get("status") != "completed"
    ]


def _rule_dispatch_plan(chain: dict[str, Any], *, reason: str, mode: Literal["dry_run", "live"] = "dry_run") -> SelectionDispatchPlan:
    stage_status = {stage.get("key"): stage.get("status") for stage in chain.get("stages", [])}
    steps: list[SelectionDispatchStep] = []
    run_now: list[AgentNodeKey] = []

    for node_key, node in NODE_DEFINITIONS.items():
        missing = _node_missing_stage_keys(chain, node)
        if stage_status.get(node_key) == "missing":
            status: Literal["ready", "blocked", "skip"] = "ready"
        elif missing:
            status = "blocked"
        else:
            status = "skip"
        if status == "ready" and node_key not in run_now:
            run_now.append(node_key)
        steps.append(
            SelectionDispatchStep(
                node=node_key,
                priority="P1",
                status=status,
                reason=reason if status == "ready" else "待录入",
                blocked_by=missing,
            )
        )

    return SelectionDispatchPlan(
        mode=mode,
        dispatch_order=steps,
        run_now=run_now[:3],
        blocked_by=[],
        learning_update={
            "can_enter_learning_memory": False,
            "hit_status": "待验证",
            "miss_reason": "",
            "next_round_action": "待录入",
        },
    )


def _normalize_dispatch_plan(raw: dict[str, Any], *, mode: Literal["dry_run", "live"]) -> SelectionDispatchPlan:
    raw_steps = raw.get("dispatch_order") or raw.get("steps") or raw.get("dispatch_plan") or []
    if isinstance(raw_steps, dict):
        raw_steps = [raw_steps]
    steps: list[SelectionDispatchStep] = []
    for item in raw_steps:
        if not isinstance(item, dict):
            item = {"node": item}
        node_key = _safe_node_key(item.get("node") or item.get("agent") or item.get("key"))
        if not node_key:
            continue
        blocked = item.get("blocked_by") or item.get("missing_stage_keys") or []
        if isinstance(blocked, str):
            blocked_by = [blocked]
        elif isinstance(blocked, list):
            blocked_by = [str(value) for value in blocked if str(value).strip()]
        else:
            blocked_by = []
        steps.append(
            SelectionDispatchStep(
                node=node_key,
                priority=_safe_priority(item.get("priority")),
                status=_safe_dispatch_status(item.get("status")),
                reason=str(item.get("reason") or "暂无"),
                blocked_by=blocked_by,
            )
        )

    raw_run_now = raw.get("run_now") or raw.get("execute_now") or []
    if isinstance(raw_run_now, str):
        raw_run_now = [raw_run_now]
    run_now: list[AgentNodeKey] = []
    if isinstance(raw_run_now, list):
        for value in raw_run_now:
            node_key = _safe_node_key(value.get("node") if isinstance(value, dict) else value)
            if node_key and node_key not in run_now:
                run_now.append(node_key)
    if not run_now:
        run_now = [step.node for step in steps if step.status == "ready"]

    blocked = raw.get("blocked_by") or []
    if isinstance(blocked, str):
        blocked_by = [blocked]
    elif isinstance(blocked, list):
        blocked_by = [str(value) for value in blocked if str(value).strip()]
    else:
        blocked_by = []
    learning = raw.get("learning_update") if isinstance(raw.get("learning_update"), dict) else {}
    return SelectionDispatchPlan(
        mode=mode,
        dispatch_order=steps,
        run_now=run_now,
        blocked_by=blocked_by,
        learning_update=learning,
        raw=raw,
    )


def _apply_selection_hard_gates(chain: dict[str, Any], plan: SelectionDispatchPlan) -> SelectionDispatchPlan:
    rule_plan = _rule_dispatch_plan(chain, reason="待录入", mode=plan.mode)
    rule_steps = {step.node: step for step in rule_plan.dispatch_order}
    existing_nodes = {step.node for step in plan.dispatch_order}
    complete_steps = [
        *plan.dispatch_order,
        *[step for step in rule_plan.dispatch_order if step.node not in existing_nodes],
    ]

    gated_steps: list[SelectionDispatchStep] = []
    ready_nodes: list[AgentNodeKey] = []
    for step in complete_steps:
        node = NODE_DEFINITIONS[step.node]
        missing = _node_missing_stage_keys(chain, node)
        if missing:
            gated_steps.append(
                step.model_copy(
                    update={
                        "status": "blocked",
                        "blocked_by": list(dict.fromkeys([*step.blocked_by, *missing])),
                        "reason": step.reason if step.reason != "暂无" else "待录入",
                    }
                )
            )
            continue
        rule_step = rule_steps.get(step.node)
        if rule_step and rule_step.status == "ready" and step.status == "blocked":
            step = step.model_copy(update={"status": "ready", "blocked_by": [], "reason": "待录入"})
        gated_steps.append(step)
        if step.status == "ready" and step.node not in ready_nodes:
            ready_nodes.append(step.node)

    gated_run_now = [node for node in plan.run_now if node in ready_nodes]
    if not gated_run_now:
        gated_run_now = ready_nodes
    blocked_by = plan.blocked_by if not ready_nodes else []

    return plan.model_copy(
        update={
            "dispatch_order": gated_steps,
            "run_now": gated_run_now,
            "blocked_by": blocked_by,
        }
    )


async def build_selection_dispatch_plan(chain: dict[str, Any], request: SelectionOrchestrationRequest) -> SelectionDispatchPlan:
    unified = UnifiedAIClient()
    status = unified.status()
    dry_run = request.dry_run if request.dry_run is not None else not status.text_configured
    if dry_run:
        return _rule_dispatch_plan(chain, reason="AI调度未配置", mode="dry_run")

    payload = {
        "workflow_chain": chain,
        "allowed_nodes": [node.model_dump() for node in NODE_DEFINITIONS.values()],
        "model_routing_policy": SELECTION_MODEL_ROUTING_POLICY,
        "extra_context": request.extra_context,
        "output_contract": {
            "dispatch_order": [
                {
                    "node": "selection|launch_check|listing_diagnosis|competitor|ad_validation|review_optimization",
                    "priority": "P0|P1|P2",
                    "status": "ready|blocked|skip",
                    "reason": "string",
                    "blocked_by": ["string"],
                }
            ],
            "run_now": ["selection|launch_check|listing_diagnosis|competitor|ad_validation|review_optimization"],
            "blocked_by": ["string"],
            "learning_update": {
                "can_enter_learning_memory": False,
                "hit_status": "待验证",
                "miss_reason": "string",
                "next_round_action": "string",
            },
        },
    }
    response = await unified.chat_completion(
        messages=[
            {"role": "system", "content": SELECTION_DISPATCH_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        model="AI_DEEP_MODEL",
        temperature=0.1,
        max_tokens=1800,
        response_format_json=True,
    )
    raw = json.loads(response.content or "{}")
    if not isinstance(raw, dict):
        return _rule_dispatch_plan(chain, reason="AI调度返回待录入", mode="dry_run")
    plan = _normalize_dispatch_plan(raw, mode="live")
    if not plan.dispatch_order:
        return _rule_dispatch_plan(chain, reason="AI调度返回待录入", mode="dry_run")
    return _apply_selection_hard_gates(chain, plan)


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


async def run_selection_orchestration(chain: dict[str, Any], request: SelectionOrchestrationRequest) -> SelectionOrchestrationResponse:
    plan = await build_selection_dispatch_plan(chain, request)
    executed: list[AgentNodeRunResponse] = []
    ready_nodes = {step.node for step in plan.dispatch_order if step.status == "ready"}

    if request.auto_run and request.max_nodes > 0 and plan.mode == "live":
        for node_key in plan.run_now[: request.max_nodes]:
            if node_key not in NODE_DEFINITIONS or node_key not in ready_nodes:
                continue
            executed.append(
                await run_agent_node(
                    chain,
                    AgentNodeRunRequest(
                        node=node_key,
                        depth=NODE_DEFINITIONS[node_key].default_depth,
                        extra_context={
                            **request.extra_context,
                            "selection_dispatch_plan": plan.model_dump(),
                            "model_routing_policy": SELECTION_MODEL_ROUTING_POLICY,
                        },
                    ),
                )
            )

    return SelectionOrchestrationResponse(plan=plan, executed_nodes=executed)
