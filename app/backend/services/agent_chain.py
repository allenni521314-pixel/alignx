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


class HermesDispatchStep(BaseModel):
    node: AgentNodeKey
    priority: Literal["P0", "P1", "P2"] = "P1"
    status: Literal["ready", "blocked", "skip"] = "blocked"
    reason: str = "暂无"
    blocked_by: list[str] = Field(default_factory=list)


class HermesDispatchPlan(BaseModel):
    supervisor: str = "Hermes"
    mode: Literal["dry_run", "live"] = "dry_run"
    dispatch_order: list[HermesDispatchStep] = Field(default_factory=list)
    run_now: list[AgentNodeKey] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    learning_update: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


class HermesOrchestrationRequest(BaseModel):
    depth: Literal["light", "standard", "deep"] = "deep"
    dry_run: Optional[bool] = None
    auto_run: bool = True
    max_nodes: int = Field(default=3, ge=0, le=6)
    extra_context: dict[str, Any] = Field(default_factory=dict)


class HermesOrchestrationResponse(BaseModel):
    plan: HermesDispatchPlan
    executed_nodes: list[AgentNodeRunResponse] = Field(default_factory=list)


NODE_DEFINITIONS: dict[AgentNodeKey, AgentNodeDefinition] = {
    "selection": AgentNodeDefinition(
        key="selection",
        agent="selection_agent",
        title="6维选品判断",
        module="选品决策",
        path="/asin-manager",
        task="判断当前 ASIN 是否值得进入机会池，并说明进入、观察或淘汰的依据。",
        required_stage_keys=["selection"],
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

HERMES_MODEL_ROUTING_POLICY = {
    "supervisor": {
        "role": "hermes_ceo",
        "model_role": "HERMES_CEO_MODEL|AI_DEEP_MODEL",
        "allowed_actions": ["dispatch", "block", "prioritize", "learning_gate"],
        "forbidden_actions": ["replace_business_agent", "generate_listing_directly", "generate_image_directly"],
    },
    "model_roles": {
        "text_light": {
            "env": "AI_LIGHT_MODEL",
            "recommended_model": "deepseek-v4-flash",
            "allowed_for": ["light_labels", "minor_summary"],
            "forbidden_for": ["final_listing_judgment", "learning_attribution"],
        },
        "text_reasoning": {
            "env": "AI_REASONING_MODEL",
            "recommended_model": "deepseek-v4-pro",
            "allowed_for": ["asin_selection", "competitor_strategy", "ad_validation"],
        },
        "text_deep": {
            "env": "AI_DEEP_MODEL",
            "recommended_model": "deepseek-v4-pro|qwen3-32b",
            "allowed_for": ["launch_check", "listing_diagnosis", "feedback_loop", "cross_module_reasoning"],
        },
        "vision_ocr": {
            "env": "AI_VISION_MODEL",
            "recommended_model": "qwen3-vl-plus",
            "allowed_for": ["main_image_ocr", "secondary_image_ocr", "aplus_ocr", "visual_evidence"],
            "forbidden_for": ["final_seller_decision"],
        },
        "image_generation": {
            "env": "PRODUCT_IMAGE_MODEL",
            "recommended_model": "wan2.7-image",
            "allowed_for": ["listing_image_generation_after_brief_ready"],
            "forbidden_for": ["judgment", "evidence_scoring", "learning_memory"],
        },
        "embedding_recall": {
            "env": "AI_EMBEDDING_MODEL",
            "recommended_model": "BAAI/bge-m3",
            "allowed_for": ["semantic_recall", "history_recall", "intent_matching"],
            "forbidden_for": ["final_answer_generation"],
        },
        "evidence_rerank": {
            "env": "RERANK_MODEL",
            "recommended_model": "BAAI/bge-reranker-v2-m3",
            "allowed_for": ["evidence_filtering", "history_precision"],
            "forbidden_for": ["business_advice_generation"],
        },
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

HERMES_DISPATCH_SYSTEM_PROMPT = "\n".join([
    "你是 AlignX Hermes CEO 调度中枢。",
    "你只负责指挥现有 Agent，不替代任何业务 Agent 直接完成判断。",
    "你必须根据 workflow chain、stage 状态、缺失项、已有 agent_decision 和学习记忆决定执行顺序。",
    "只允许调度 allowed_nodes 中列出的节点。",
    "你必须遵守 model_routing_policy 中的模型角色分工。",
    "Embedding 只做召回，Reranker 只做证据精排，Vision/OCR 只做图片证据，图片生成模型只做图片生成。",
    "文本最终判断只能交给对应业务 Agent 的 text_reasoning 或 text_deep 路由。",
    "Hermes 只能输出调度、阻塞、优先级、学习门控，不得直接输出 Listing 成品或图片成品。",
    "如果节点缺少必要证据，status 必须是 blocked，并写入 blocked_by。",
    "如果节点可以执行，status 必须是 ready。",
    "必须优先补齐阻塞上架准入和 Listing 自动化生成的节点。",
    "输出必须是JSON对象，不要输出Markdown，不要输出额外解释。",
])


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


def _rule_dispatch_plan(chain: dict[str, Any], *, reason: str) -> HermesDispatchPlan:
    stage_status = {stage.get("key"): stage.get("status") for stage in chain.get("stages", [])}
    steps: list[HermesDispatchStep] = []
    run_now: list[AgentNodeKey] = []
    for node_key, node in NODE_DEFINITIONS.items():
        missing = _node_missing_stage_keys(chain, node)
        stage_missing = stage_status.get(node_key) == "missing"
        if stage_missing:
            status: Literal["ready", "blocked", "skip"] = "ready"
        elif missing:
            status = "blocked"
        else:
            status = "skip"
        if status == "ready" and len(run_now) == 0:
            run_now.append(node_key)
        steps.append(
            HermesDispatchStep(
                node=node_key,
                priority="P1",
                status=status,
                reason=reason if status == "ready" else "待录入",
                blocked_by=missing,
            )
        )
    if not run_now and NODE_DEFINITIONS:
        run_now = ["review_optimization"]
    return HermesDispatchPlan(
        mode="dry_run",
        dispatch_order=steps,
        run_now=run_now,
        blocked_by=[] if run_now else ["待录入"],
        learning_update={
            "can_enter_learning_memory": False,
            "hit_status": "待验证",
            "miss_reason": "Hermes未配置",
            "next_round_action": "配置Hermes后重新调度",
        },
    )


def _normalize_dispatch_plan(raw: dict[str, Any], *, mode: Literal["dry_run", "live"]) -> HermesDispatchPlan:
    raw_steps = raw.get("dispatch_order") or raw.get("steps") or raw.get("dispatch_plan") or []
    if isinstance(raw_steps, dict):
        raw_steps = [raw_steps]
    steps: list[HermesDispatchStep] = []
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
            HermesDispatchStep(
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
    run_now = []
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
    return HermesDispatchPlan(
        mode=mode,
        dispatch_order=steps,
        run_now=run_now,
        blocked_by=blocked_by,
        learning_update=learning,
        raw=raw,
    )


async def build_hermes_dispatch_plan(chain: dict[str, Any], request: HermesOrchestrationRequest) -> HermesDispatchPlan:
    gateway = AIGatewayService()
    status = gateway.status()
    dry_run = request.dry_run if request.dry_run is not None else not status.ceo_configured
    if dry_run:
        return _rule_dispatch_plan(chain, reason="Hermes未配置")

    payload = {
        "workflow_chain": chain,
        "allowed_nodes": [node.model_dump() for node in NODE_DEFINITIONS.values()],
        "model_routing_policy": HERMES_MODEL_ROUTING_POLICY,
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
    raw = await gateway.run_json(
        system_prompt=HERMES_DISPATCH_SYSTEM_PROMPT,
        payload=payload,
        module="hermes_ceo_dispatch",
        depth=request.depth,
        model_override=status.ceo_model,
        base_url_override=gateway.ceo_base_url,
        api_key_override=gateway.ceo_api_key,
        provider_override=gateway.ceo_provider,
    )
    plan = _normalize_dispatch_plan(raw, mode="live")
    if not plan.dispatch_order:
        return _rule_dispatch_plan(chain, reason="Hermes返回待录入")
    return plan


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


async def run_hermes_orchestration(chain: dict[str, Any], request: HermesOrchestrationRequest) -> HermesOrchestrationResponse:
    plan = await build_hermes_dispatch_plan(chain, request)
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
                            "hermes_dispatch_plan": plan.model_dump(),
                            "model_routing_policy": HERMES_MODEL_ROUTING_POLICY,
                        },
                    ),
                )
            )
    return HermesOrchestrationResponse(plan=plan, executed_nodes=executed)
