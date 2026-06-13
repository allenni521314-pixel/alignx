"""Single judgment kernel for AlignX diagnosis and feedback loops.

This service keeps the Amazon COSMO/Rufus operator skill as the only
decision standard used by business modules. Public responses should stay
simple ("10维诊断"), while prompts and backend metadata preserve the
ordered action logic and user-scoped learning contract.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from services.canonical_10d_scoring import align_amazon_skill_scores
from services.intent_platform_memory import build_action_tags
from services.model_invocation_contract import WORKFLOW_CONTRACTS, WorkflowContract

logger = logging.getLogger(__name__)


STANDARD_SCHEMA = "alignx-cosmo-operator-v1"
STANDARD_VERSION = "human-nature-v4-10d-learning-v1"
INTERNAL_SKILL_ID = "amazon-cosmo-operator-perspective"
PUBLIC_STANDARD_NAME = "AlignX 10维诊断"

JUDGMENT_ORDER = (
    "人性根层",
    "用户意图",
    "平台规则",
    "验证回流",
)

CANONICAL_10D_PUBLIC = (
    "功能表达",
    "场景表达",
    "身份适配",
    "心理利益",
    "风险消除",
    "差异化",
    "产品身份",
    "兼容搭配",
    "主观属性",
    "市场趋势",
)


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {}


def _contract_to_dict(contract: WorkflowContract | None) -> dict[str, Any]:
    if not contract:
        return {}
    return asdict(contract)


def workflow_for_context(context: str | None) -> str:
    """Normalize loose business names into model invocation workflow keys."""
    key = (context or "").strip().lower()
    aliases = {
        "asin": "asin_selection",
        "asin_analysis": "asin_selection",
        "asin_selection": "asin_selection",
        "listing": "listing_diagnosis",
        "listing_diagnosis": "listing_diagnosis",
        "own_listing": "listing_diagnosis",
        "competitor": "competitor_diagnosis",
        "competitor_analysis": "competitor_diagnosis",
        "competitor_diagnosis": "competitor_diagnosis",
        "ad": "ad_validation",
        "ad_validation": "ad_validation",
        "feedback": "ad_validation",
    }
    return aliases.get(key, "listing_diagnosis")


class CosmoOperatorAgent:
    """Backend-only operator standard shared by all AlignX modules."""

    def __init__(self, db: AsyncSession | None = None):
        self.db = db

    @staticmethod
    def public_standard_meta(workflow: str | None = None) -> dict[str, Any]:
        workflow_key = workflow_for_context(workflow)
        contract = WORKFLOW_CONTRACTS.get(workflow_key)
        return {
            "schema": STANDARD_SCHEMA,
            "version": STANDARD_VERSION,
            "public_name": PUBLIC_STANDARD_NAME,
            "workflow": {
                "key": workflow_key,
                "name": contract.name if contract else "",
            },
            "score_system": "10维诊断",
            "dimensions": list(CANONICAL_10D_PUBLIC),
            "rule_role": "兜底校验",
            "learning_enabled": False,
        }

    @staticmethod
    def align_scores(scores: Any, product: Any) -> dict[str, Any]:
        return align_amazon_skill_scores(scores, _as_dict(product))

    async def build_context(
        self,
        *,
        user_id: str | None,
        workflow: str,
        product: Any,
        asin: str | None = None,
        marketplace: str = "US",
        current_scores: Any = None,
    ) -> dict[str, Any]:
        product_data = _as_dict(product)
        workflow_key = workflow_for_context(workflow)
        contract = WORKFLOW_CONTRACTS.get(workflow_key)

        memories: list[Any] = []
        feedback_memory: dict[str, Any] = {}
        tags = build_action_tags(
            product=product_data,
            current_scores=current_scores,
            memories=memories,
            feedback_memory=feedback_memory,
        )

        prompt_summary = self._build_prompt_summary(
            workflow_key=workflow_key,
            contract=contract,
            memory_context={},
        )

        return {
            "schema": STANDARD_SCHEMA,
            "version": STANDARD_VERSION,
            "internal_skill_id": INTERNAL_SKILL_ID,
            "public_name": PUBLIC_STANDARD_NAME,
            "workflow_key": workflow_key,
            "workflow_contract": _contract_to_dict(contract),
            "order": list(JUDGMENT_ORDER),
            "action_tags": tags,
            "memory_samples": memories,
            "feedback_memory": feedback_memory,
            "prompt_summary": prompt_summary,
        }

    def attach_result_metadata(
        self,
        result: dict[str, Any],
        context: dict[str, Any],
        *,
        product: Any = None,
        scores: Any = None,
    ) -> dict[str, Any]:
        """Attach safe public metadata and action tags to a business result."""
        if not isinstance(result, dict):
            return result

        product_data = _as_dict(product)
        current_scores = scores if scores is not None else result.get("canonical_10d_scores") or result.get("scores")
        memories = context.get("memory_samples", []) if isinstance(context, dict) else []
        feedback_memory = context.get("feedback_memory", {}) if isinstance(context, dict) else {}
        tags = build_action_tags(
            product=product_data,
            current_scores=current_scores,
            memories=memories,
            feedback_memory=feedback_memory,
        )
        workflow_key = context.get("workflow_key") if isinstance(context, dict) else None

        result["decision_standard"] = self.public_standard_meta(workflow_key)
        result["alignment_action_tags"] = tags
        result["alignment_action_chain"] = {
            "schema": STANDARD_SCHEMA,
            "version": STANDARD_VERSION,
            "name": PUBLIC_STANDARD_NAME,
            "workflow": self.public_standard_meta(workflow_key).get("workflow", {}),
            "order": list(JUDGMENT_ORDER),
            "score_system": "10维诊断",
            "rule_track": "fallback_consistency_check_only",
            "learning": {
                "scope": "current_user_only",
                "sources": [],
                "updates": "disabled_for_new_judgment",
            },
            "memory_samples": memories[:3],
            "feedback_memory": feedback_memory,
        }
        return result

    @staticmethod
    def _build_prompt_summary(
        *,
        workflow_key: str,
        contract: WorkflowContract | None,
        memory_context: dict[str, Any],
    ) -> str:
        step_lines: list[str] = []
        if contract:
            for step in contract.steps:
                step_lines.append(
                    f"- {step.key}: {step.owner}负责{step.purpose}，输出{step.output_contract}"
                )
        memory_prompt = ""
        if isinstance(memory_context, dict) and memory_context.get("prompt_summary"):
            memory_prompt = str(memory_context["prompt_summary"])[:1600]

        return (
            "【AlignX后台唯一判断内核】\n"
            f"内部标准：{INTERNAL_SKILL_ID} / {STANDARD_VERSION}。禁止向前台卖家暴露内部标准名称、两把尺或模型名称。\n"
            "所有业务判断必须按固定顺序执行：1人性根层 -> 2用户意图 -> 3平台规则 -> 4验证回流。\n"
            "人性根层先判断Level 0趋利/避害、Level 1生存/繁衍/资源/探索、Level 2的13个人性节点、Level 3动机、Level 4需求、Level 5场景、Level 6解决方案、Level 7表达、Level 8行为、Level 9结果；"
            "用户意图只判断真实任务、痛点、场景、决策触发和反购买风险；平台规则只判断类目身份、查询意图、结构化属性、关系图谱和证据可回答性；"
            "广告/搜索/评论/回流数据只用于校准置信度和优先级，不能替代前两步。\n"
            "输出统一使用10维诊断；后台规则只做兜底和一致性检查，不允许规则覆盖语义证据链的主判断。\n"
            f"当前工作流：{workflow_key}。\n"
            + ("\n【模型/工具职责边界】\n" + "\n".join(step_lines[:8]) if step_lines else "")
            + (("\n\n【用户隔离学习记忆】\n" + memory_prompt) if memory_prompt else "")
        )
