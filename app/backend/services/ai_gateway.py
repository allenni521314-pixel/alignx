"""
AlignX AI Gateway.

This module is the single backend entry point for model calls used by decision agents.
It keeps provider/model configuration outside business modules so models can be swapped
without rewriting the selection, listing, ad validation, or review loop.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Literal, Optional

import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from services.ai_usage import record_ai_usage
from services.model_invocation_contract import judgment_standard_summary, workflow_summary
from services.unified_ai import UnifiedAIClient

logger = logging.getLogger(__name__)

AgentKey = Literal[
    "selection_agent",
    "launch_check_agent",
    "listing_diagnosis_agent",
    "competitor_agent",
    "ad_validation_agent",
    "review_optimization_agent",
]
DecisionDepth = Literal["light", "standard", "deep"]
ConfidenceLevel = Literal["low", "medium", "high"]
PriorityLevel = Literal["P0", "P1", "P2"]
RiskLevel = Literal["low", "medium", "high"]


class AIGatewayStatus(BaseModel):
    provider: str
    configured: bool
    base_url: str
    default_model: str
    light_model: str
    reasoning_model: str
    deep_model: str
    api_mode: str
    supported_agents: list[str]


class AgentRequest(BaseModel):
    agent: AgentKey
    task: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    depth: DecisionDepth = "standard"
    dry_run: bool = True


class AgentProblem(BaseModel):
    title: str
    evidence: str
    impact: str
    priority: PriorityLevel


class AgentAction(BaseModel):
    title: str
    target_module: str
    reason: str
    validation: str


class AgentNextStep(BaseModel):
    module: str
    path: str
    reason: str


class AgentEvidenceSource(BaseModel):
    source_type: str
    source_ref: str
    evidence_tier: str
    confidence: ConfidenceLevel
    summary: str


class AgentValidationHypothesis(BaseModel):
    hypothesis_id: str
    hypothesis: str
    metric_rule: str
    observation_window: str
    required_sample: str


class AgentLearningUpdate(BaseModel):
    can_enter_learning_memory: bool
    hit_status: str
    miss_reason: str
    reusable_learning: str
    next_round_action: str


class AgentDecisionResult(BaseModel):
    score: int = Field(..., ge=0, le=100)
    confidence: ConfidenceLevel
    problems: list[AgentProblem]
    actions: list[AgentAction]
    next_step: AgentNextStep
    risk_level: RiskLevel
    evidence_sources: list[AgentEvidenceSource] = Field(default_factory=list)
    validation_hypotheses: list[AgentValidationHypothesis] = Field(default_factory=list)
    learning_update: AgentLearningUpdate = Field(
        default_factory=lambda: AgentLearningUpdate(
            can_enter_learning_memory=False,
            hit_status="待验证",
            miss_reason="",
            reusable_learning="",
            next_round_action="",
        )
    )
    blocked_by: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    agent: AgentKey
    provider: str
    model: str
    mode: Literal["dry_run", "live"]
    result: AgentDecisionResult
    usage: Optional[dict[str, Any]] = None


class AIGatewayService:
    """Provider-neutral AI gateway for AlignX decision agents."""

    supported_agents = [
        "selection_agent",
        "launch_check_agent",
        "listing_diagnosis_agent",
        "competitor_agent",
        "ad_validation_agent",
        "review_optimization_agent",
    ]

    def __init__(self):
        self.unified = UnifiedAIClient()
        status = self.unified.status()
        self.provider = status.provider
        self.api_key = self.unified.text_api_key
        self.base_url = status.text_base_url
        self.default_model = status.default_model
        self.light_model = status.light_model
        self.reasoning_model = status.reasoning_model
        self.deep_model = status.deep_model
        self.api_mode = status.api_mode
        self.request_timeout = float(os.getenv("AI_REQUEST_TIMEOUT", "180"))
        self.client: AsyncOpenAI | None = None

        if self.api_key:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.request_timeout,
            )

    def status(self) -> AIGatewayStatus:
        return AIGatewayStatus(
            provider=self.provider,
            configured=bool(self.api_key and self.base_url),
            base_url=self.base_url,
            default_model=self.default_model,
            light_model=self.light_model,
            reasoning_model=self.reasoning_model,
            deep_model=self.deep_model,
            api_mode=self.api_mode,
            supported_agents=self.supported_agents,
        )

    @staticmethod
    def workflow_contract() -> list[dict[str, object]]:
        return workflow_summary()

    @staticmethod
    def judgment_standard() -> dict[str, object]:
        return judgment_standard_summary()

    def select_model(self, depth: DecisionDepth) -> str:
        if depth == "light":
            if self.provider.lower() == "deepseek":
                return "deepseek-v4-flash"
            return self._normalize_text_model(self.light_model)
        if depth == "deep":
            return self._normalize_text_model(self.deep_model)
        return self._normalize_text_model(self.reasoning_model)

    def _normalize_text_model(self, model: str) -> str:
        """Keep text agents on a text-capable model when env vars were edited manually."""
        if self.provider.lower() == "deepseek" and not model.startswith("deepseek-"):
            fallback = self.default_model if self.default_model.startswith("deepseek-") else "deepseek-v4-flash"
            logger.warning("Invalid DeepSeek text model %s, falling back to %s", model, fallback)
            return fallback
        return model

    async def _create_chat_completion(self, model: str, messages: list[dict[str, str]]) -> tuple[str, dict[str, Any] | None]:
        """Call an OpenAI-compatible chat endpoint directly for public deploy stability."""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.request_timeout, trust_env=False) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"].get("content") or "{}", data.get("usage")

    def _agent_role_prompt(self, agent: AgentKey) -> str:
        roles = {
            "selection_agent": "你是 AlignX 选品决策 Agent，判断 ASIN 是否值得进入机会池。",
            "launch_check_agent": "你是 AlignX Listing 上新检测 Agent，判断上架前是否具备上线条件。",
            "listing_diagnosis_agent": "你是 AlignX Listing 诊断 Agent，定位上线后不转化的表达错配原因。",
            "competitor_agent": "你是 AlignX 竞品诊断 Agent，用同一套标准比较 Top 竞品与本品差距。",
            "ad_validation_agent": "你是 AlignX 广告验证 Agent，用广告数据验证诊断假设是否成立。",
            "review_optimization_agent": "你是 AlignX 复盘优化 Agent，把执行结果回流为下一轮动作。",
        }
        return roles[agent]

    def _system_prompt(self, agent: AgentKey) -> str:
        return (
            f"{self._agent_role_prompt(agent)}\n"
            "你必须基于标准化输入、可解释依据、广告验证和反馈回流做判断。\n"
            "不要输出空泛营销建议。每个问题都要说明依据来源、影响、优先级和验证方法。\n"
            "输出必须是一个JSON对象，且只能使用以下字段：\n"
            "{\n"
            '  "score": 0-100的整数,\n'
            '  "confidence": "low" | "medium" | "high",\n'
            '  "problems": [{"title": "问题", "evidence": "依据", "impact": "影响", "priority": "P0" | "P1" | "P2"}],\n'
            '  "actions": [{"title": "动作", "target_module": "模块", "reason": "原因", "validation": "验证方式"}],\n'
            '  "next_step": {"module": "下一模块", "path": "前端路径", "reason": "原因"},\n'
            '  "risk_level": "low" | "medium" | "high",\n'
            '  "evidence_sources": [{"source_type": "来源类型", "source_ref": "表/记录/字段", "evidence_tier": "market_feedback|buyer_voice|listing_facts|semantic_reasoning|model_inference", "confidence": "low|medium|high", "summary": "证据摘要"}],\n'
            '  "validation_hypotheses": [{"hypothesis_id": "hypothesis-1", "hypothesis": "要验证的判断", "metric_rule": "命中/失败规则", "observation_window": "观察周期", "required_sample": "最小样本要求"}],\n'
            '  "learning_update": {"can_enter_learning_memory": false, "hit_status": "待验证|已命中|未命中", "miss_reason": "失败原因", "reusable_learning": "可复用经验", "next_round_action": "下一轮动作"},\n'
            '  "blocked_by": ["缺失或阻塞原因"]\n'
            "}\n"
            "不要输出 diagnosis、suggestions、summary 等额外顶层字段。"
        )

    @staticmethod
    def _safe_priority(value: Any) -> PriorityLevel:
        if value in {"P0", "P1", "P2"}:
            return value
        text = str(value or "").lower()
        if "high" in text or "高" in text or "urgent" in text:
            return "P0"
        if "low" in text or "低" in text:
            return "P2"
        return "P1"

    @staticmethod
    def _safe_confidence(value: Any) -> ConfidenceLevel:
        text = str(value or "").lower()
        if value in {"low", "medium", "high"}:
            return value
        if "高" in text or "high" in text:
            return "high"
        if "低" in text or "low" in text:
            return "low"
        return "medium"

    @staticmethod
    def _safe_risk(value: Any) -> RiskLevel:
        text = str(value or "").lower()
        if value in {"low", "medium", "high"}:
            return value
        if "高" in text or "high" in text:
            return "high"
        if "低" in text or "low" in text:
            return "low"
        return "medium"

    def _normalize_agent_result(self, raw: dict[str, Any]) -> AgentDecisionResult:
        """Normalize OpenAI-compatible JSON output into the AlignX contract."""
        try:
            return AgentDecisionResult.model_validate(raw)
        except Exception:
            pass

        raw_problems = raw.get("problems") or raw.get("diagnosis") or raw.get("issues") or raw.get("risks") or []
        if isinstance(raw_problems, dict):
            raw_problems = [raw_problems]
        problems: list[AgentProblem] = []
        for item in raw_problems[:5]:
            if not isinstance(item, dict):
                item = {"title": str(item)}
            problems.append(
                AgentProblem(
                    title=str(item.get("title") or item.get("issue") or item.get("problem") or "需要补充判断问题"),
                    evidence=str(item.get("evidence") or item.get("basis") or item.get("reason") or "模型未提供明确证据，需回到来源数据核实。"),
                    impact=str(item.get("impact") or item.get("effect") or "可能影响点击、转化或广告验证效率。"),
                    priority=self._safe_priority(item.get("priority") or item.get("level")),
                )
            )
        if not problems:
            problems.append(
                AgentProblem(
                    title="模型输出未明确问题项",
                    evidence="返回JSON缺少problems字段，系统已归一化为低风险提示。",
                    impact="需要补充标准化输入后再次判断。",
                    priority="P2",
                )
            )

        raw_actions = raw.get("actions") or raw.get("suggestions") or raw.get("recommendations") or raw.get("next_actions") or []
        if isinstance(raw_actions, dict):
            raw_actions = [raw_actions]
        actions: list[AgentAction] = []
        for item in raw_actions[:5]:
            if not isinstance(item, dict):
                item = {"title": str(item)}
            actions.append(
                AgentAction(
                    title=str(item.get("title") or item.get("action") or item.get("suggestion") or "补充可验证动作"),
                    target_module=str(item.get("target_module") or item.get("module") or "Listing 运营"),
                    reason=str(item.get("reason") or item.get("basis") or "基于当前诊断问题生成。"),
                    validation=str(item.get("validation") or item.get("verify") or "通过广告点击、转化和ACOS进行验证。"),
                )
            )
        if not actions:
            actions.append(
                AgentAction(
                    title="回到标准化输入补齐证据",
                    target_module="今日决策",
                    reason="模型输出缺少动作字段。",
                    validation="补齐后重新运行节点判断。",
                )
            )

        raw_next = raw.get("next_step") or raw.get("next") or {}
        if not isinstance(raw_next, dict):
            raw_next = {}
        score = raw.get("score") or raw.get("overall_score") or raw.get("rating") or 70
        try:
            score_int = max(0, min(100, int(float(score))))
        except (TypeError, ValueError):
            score_int = 70

        raw_evidence = raw.get("evidence_sources") or raw.get("evidence") or raw.get("sources") or []
        if isinstance(raw_evidence, dict):
            raw_evidence = [raw_evidence]
        evidence_sources: list[AgentEvidenceSource] = []
        for item in raw_evidence[:5]:
            if not isinstance(item, dict):
                item = {"summary": str(item)}
            evidence_sources.append(
                AgentEvidenceSource(
                    source_type=str(item.get("source_type") or item.get("type") or "model_inference"),
                    source_ref=str(item.get("source_ref") or item.get("ref") or item.get("source") or "agent_output"),
                    evidence_tier=str(item.get("evidence_tier") or item.get("tier") or "model_inference"),
                    confidence=self._safe_confidence(item.get("confidence")),
                    summary=str(item.get("summary") or item.get("evidence") or item.get("reason") or "模型未提供明确证据摘要。"),
                )
            )
        if not evidence_sources:
            evidence_sources.append(
                AgentEvidenceSource(
                    source_type="agent_normalized_output",
                    source_ref="ai_gateway._normalize_agent_result",
                    evidence_tier="model_inference",
                    confidence="low",
                    summary="模型未提供结构化证据来源，系统已降为低置信度模型推理。",
                )
            )

        raw_hypotheses = raw.get("validation_hypotheses") or raw.get("hypotheses") or raw.get("tests") or []
        if isinstance(raw_hypotheses, dict):
            raw_hypotheses = [raw_hypotheses]
        validation_hypotheses: list[AgentValidationHypothesis] = []
        for index, item in enumerate(raw_hypotheses[:5], start=1):
            if not isinstance(item, dict):
                item = {"hypothesis": str(item)}
            validation_hypotheses.append(
                AgentValidationHypothesis(
                    hypothesis_id=str(item.get("hypothesis_id") or item.get("id") or f"hypothesis-{index}"),
                    hypothesis=str(item.get("hypothesis") or item.get("statement") or "Listing动作后，核心广告指标应改善。"),
                    metric_rule=str(item.get("metric_rule") or item.get("decision_rule") or "点击>=100后，CVR提升且ACOS不恶化视为初步命中。"),
                    observation_window=str(item.get("observation_window") or "7-14天"),
                    required_sample=str(item.get("required_sample") or "假设级点击至少100次"),
                )
            )
        if not validation_hypotheses:
            validation_hypotheses.append(
                AgentValidationHypothesis(
                    hypothesis_id="hypothesis-1",
                    hypothesis=actions[0].validation if actions else "补齐证据后再生成验证假设。",
                    metric_rule="点击少于100只能待验证；点击达到100后再判断CTR、CVR、ACOS。",
                    observation_window="7-14天",
                    required_sample="假设级点击至少100次",
                )
            )

        raw_learning = raw.get("learning_update") or raw.get("learning") or {}
        if not isinstance(raw_learning, dict):
            raw_learning = {}
        learning_update = AgentLearningUpdate(
            can_enter_learning_memory=bool(raw_learning.get("can_enter_learning_memory", False)),
            hit_status=str(raw_learning.get("hit_status") or "待验证"),
            miss_reason=str(raw_learning.get("miss_reason") or raw_learning.get("failure_reason") or ""),
            reusable_learning=str(raw_learning.get("reusable_learning") or ""),
            next_round_action=str(raw_learning.get("next_round_action") or raw_learning.get("next_action") or ""),
        )

        raw_blocked = raw.get("blocked_by") or raw.get("blockers") or []
        if isinstance(raw_blocked, str):
            blocked_by = [raw_blocked]
        elif isinstance(raw_blocked, list):
            blocked_by = [str(item) for item in raw_blocked if str(item).strip()]
        else:
            blocked_by = []
        if not evidence_sources or evidence_sources[0].confidence == "low":
            blocked_by.append("缺少结构化证据来源，不能进入高置信最终判断。")

        return AgentDecisionResult(
            score=score_int,
            confidence=self._safe_confidence(raw.get("confidence")),
            problems=problems,
            actions=actions,
            next_step=AgentNextStep(
                module=str(raw_next.get("module") or raw_next.get("target_module") or "广告投放"),
                path=str(raw_next.get("path") or "/ad-analytics?view=ab-test-plan"),
                reason=str(raw_next.get("reason") or "进入广告验证，用真实流量验证诊断假设。"),
            ),
            risk_level=self._safe_risk(raw.get("risk_level") or raw.get("risk")),
            evidence_sources=evidence_sources,
            validation_hypotheses=validation_hypotheses,
            learning_update=learning_update,
            blocked_by=list(dict.fromkeys(blocked_by)),
        )

    def dry_run(self, request: AgentRequest) -> AgentResponse:
        model = self.select_model(request.depth)
        agent_name = request.agent
        return AgentResponse(
            agent=agent_name,
            provider=self.provider,
            model=model,
            mode="dry_run",
            result=AgentDecisionResult(
                score=72,
                confidence="medium",
                risk_level="medium",
                problems=[
                    AgentProblem(
                        title="Listing 核心承诺与买家高频需求未完全对齐",
                        evidence="输入数据中存在评论需求、关键词和广告验证字段，但缺少足够执行后反馈样本。",
                        impact="会导致点击后信任承接不足，广告验证阶段可能出现 CTR 提升但 CVR 不同步提升。",
                        priority="P1",
                    )
                ],
                actions=[
                    AgentAction(
                        title="补齐证据字段后生成可验证动作",
                        target_module="Listing 运营",
                        reason="AlignX 判断必须让每个结论能追溯到评论、平台语义或广告数据来源。",
                        validation="进入广告验证，观察 CTR、CVR、ACOS 与搜索词相关性变化。",
                    )
                ],
                next_step=AgentNextStep(
                    module="广告投放",
                    path="/ad-analytics?view=ab-test-plan",
                    reason="当前诊断应进入 A/B 测试计划，用真实流量验证假设。",
                ),
                evidence_sources=[
                    AgentEvidenceSource(
                        source_type="dry_run_payload",
                        source_ref="agent_request.payload",
                        evidence_tier="model_inference",
                        confidence="low",
                        summary="当前为dry run，仅用于验证Agent输出契约，不进入高置信判断。",
                    )
                ],
                validation_hypotheses=[
                    AgentValidationHypothesis(
                        hypothesis_id="hypothesis-dry-run",
                        hypothesis="补齐结构化证据后，Listing动作应能通过广告指标验证。",
                        metric_rule="点击少于100只标记待验证；点击达到100后判断CTR、CVR和ACOS。",
                        observation_window="7-14天",
                        required_sample="假设级点击至少100次",
                    )
                ],
                learning_update=AgentLearningUpdate(
                    can_enter_learning_memory=False,
                    hit_status="待验证",
                    miss_reason="dry_run不能作为学习结果",
                    reusable_learning="",
                    next_round_action="配置真实模型并补齐证据后重新运行Agent。",
                ),
                blocked_by=["dry_run模式不能进入学习记忆。"],
            ),
            usage=None,
        )

    async def run_agent(self, request: AgentRequest) -> AgentResponse:
        if request.dry_run:
            return self.dry_run(request)

        if not self.api_key:
            raise RuntimeError("AI Gateway is not configured.")

        model = self.select_model(request.depth)
        schema = AgentDecisionResult.model_json_schema()
        user_input = {
            "task": request.task,
            "agent": request.agent,
            "payload": request.payload,
            "required_flow": "Scraping事实 -> 规则结构化 -> BGE语义召回 -> BGE重排 -> DeepSeek判断 -> 快照保存 -> 广告验证回流",
            "model_contract": self.workflow_contract(),
            "unified_judgment_standard": self.judgment_standard(),
        }

        try:
            messages = [
                {"role": "system", "content": self._system_prompt(request.agent)},
                {"role": "user", "content": json.dumps(user_input, ensure_ascii=False)},
            ]
            response = await self.unified.chat_completion(
                messages=messages,
                model=model,
                temperature=0.2,
                response_format_json=True,
            )
            content = response.content or "{}"
            usage = response.usage

            raw_result = json.loads(content or "{}")
            if not isinstance(raw_result, dict):
                raw_result = {"problems": [{"title": str(raw_result)}]}
            result = self._normalize_agent_result(raw_result)
            await record_ai_usage(
                provider=self.provider,
                model=model,
                module=f"ai_gateway.{request.agent}",
                endpoint="chat/completions",
                usage=usage,
            )
            return AgentResponse(
                agent=request.agent,
                provider=self.provider,
                model=model,
                mode="live",
                result=result,
                usage=usage,
            )
        except Exception as exc:
            logger.exception("AI Gateway call failed")
            raise RuntimeError(f"AI Gateway call failed: {exc}") from exc
