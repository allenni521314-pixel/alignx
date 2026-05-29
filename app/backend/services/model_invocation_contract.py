"""Central model invocation contract for the AlignX decision loop.

Business modules should depend on these role aliases instead of hard-coding
provider model names. This keeps ASIN, Listing, ad validation, and feedback
attribution auditable when providers or model versions change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ModelRole = Literal[
    "scraping",
    "rules",
    "text_light",
    "text_reasoning",
    "text_deep",
    "vision",
    "embedding",
    "rerank",
]

TEXT_MODEL_ALIASES = {
    "AI_DEFAULT_MODEL",
    "AI_LIGHT_MODEL",
    "AI_REASONING_MODEL",
    "AI_DEEP_MODEL",
}

VISION_MODEL_ALIASES = {"AI_VISION_MODEL"}


@dataclass(frozen=True)
class PipelineStep:
    key: str
    owner: ModelRole
    purpose: str
    output_contract: str
    blocks_final_score: bool = False


@dataclass(frozen=True)
class WorkflowContract:
    key: str
    name: str
    steps: tuple[PipelineStep, ...]


ASIN_SELECTION_CONTRACT = WorkflowContract(
    key="asin_selection",
    name="ASIN选品决策",
    steps=(
        PipelineStep("amazon_snapshot", "scraping", "抓Top40和单个ASIN真实事实", "raw_amazon_snapshot", True),
        PipelineStep("fact_rules", "rules", "校验价格、BSR、评论、库存、广告位/自然位", "structured_facts", True),
        PipelineStep("semantic_recall", "embedding", "召回相似机会、关键词意图和历史判断", "semantic_candidates"),
        PipelineStep("evidence_rerank", "rerank", "过滤低相关历史证据", "ranked_evidence"),
        PipelineStep("opportunity_reasoning", "text_reasoning", "输出6维选品判断和下一步动作", "asin_decision"),
    ),
)

LISTING_DIAGNOSIS_CONTRACT = WorkflowContract(
    key="listing_diagnosis",
    name="本品Listing诊断",
    steps=(
        PipelineStep("listing_snapshot", "scraping", "抓/接收标题、主图、副图、五点、A+、评论和可售状态", "listing_snapshot", True),
        PipelineStep("fact_rules", "rules", "结构化商品身份、属性、场景、库存和合规事实", "structured_listing_facts", True),
        PipelineStep("semantic_recall", "embedding", "召回相似Listing错误、评论痛点和语义锚点", "semantic_candidates"),
        PipelineStep("evidence_rerank", "rerank", "选择最相关证据进入诊断Prompt", "ranked_evidence"),
        PipelineStep("visual_ocr_evidence", "vision", "用Qwen Vision/OCR读取主图、副图、A+图片中的产品、场景、文字、徽章、认证和风险承诺", "visual_ocr_evidence"),
        PipelineStep("diagnosis_reasoning", "text_deep", "输出10维诊断、本品问题和广告验证假设", "listing_diagnosis"),
    ),
)

COMPETITOR_CONTRACT = WorkflowContract(
    key="competitor_diagnosis",
    name="竞品诊断",
    steps=(
        PipelineStep("competitor_snapshot", "scraping", "抓竞品Listing、价格、评论、图片和搜索位置", "competitor_snapshot", True),
        PipelineStep("fact_rules", "rules", "统一竞品与本品可比字段", "comparison_facts", True),
        PipelineStep("semantic_recall", "embedding", "召回相似竞品打法、评论痛点和广告词意图", "semantic_candidates"),
        PipelineStep("evidence_rerank", "rerank", "选出可用于优劣势判断的证据", "ranked_evidence"),
        PipelineStep("visual_ocr_evidence", "vision", "用Qwen Vision/OCR比较主图/副图/A+图片证据链和图片内文案", "visual_ocr_evidence"),
        PipelineStep("strategy_reasoning", "text_reasoning", "把优劣势转成可测试广告假设", "competitor_strategy"),
    ),
)

AD_VALIDATION_CONTRACT = WorkflowContract(
    key="ad_validation",
    name="广告验证",
    steps=(
        PipelineStep("ad_snapshot", "scraping", "接收广告计划、搜索词、CTR、CPC、CVR、ACOS和订单事实", "ad_snapshot", True),
        PipelineStep("fact_rules", "rules", "计算命中/未命中和异常指标", "ad_metric_facts", True),
        PipelineStep("semantic_recall", "embedding", "匹配广告词与Listing承诺、评论痛点、历史意图", "semantic_candidates"),
        PipelineStep("evidence_rerank", "rerank", "筛出最能解释指标的语义证据", "ranked_evidence"),
        PipelineStep("validation_reasoning", "text_reasoning", "判断保留、暂停、改Listing或重测", "ad_validation_decision"),
    ),
)

FEEDBACK_CONTRACT = WorkflowContract(
    key="feedback_loop",
    name="数据回流",
    steps=(
        PipelineStep("result_snapshot", "rules", "保存每轮Listing版本、广告结果和诊断快照", "versioned_snapshot", True),
        PipelineStep("semantic_recall", "embedding", "把新结果写入并召回相似历史轮次", "semantic_candidates"),
        PipelineStep("evidence_rerank", "rerank", "找出最像当前问题的历史验证", "ranked_evidence"),
        PipelineStep("loop_reasoning", "text_deep", "修正权重、解释未命中原因并生成下一轮动作", "feedback_decision"),
    ),
)

WORKFLOW_CONTRACTS = {
    item.key: item
    for item in (
        ASIN_SELECTION_CONTRACT,
        LISTING_DIAGNOSIS_CONTRACT,
        COMPETITOR_CONTRACT,
        AD_VALIDATION_CONTRACT,
        FEEDBACK_CONTRACT,
    )
}


def text_alias_for_role(role: ModelRole) -> str:
    if role == "text_light":
        return "AI_LIGHT_MODEL"
    if role == "text_deep":
        return "AI_DEEP_MODEL"
    return "AI_REASONING_MODEL"


def workflow_summary() -> list[dict[str, object]]:
    return [
        {
            "key": contract.key,
            "name": contract.name,
            "steps": [
                {
                    "key": step.key,
                    "owner": step.owner,
                    "purpose": step.purpose,
                    "output_contract": step.output_contract,
                    "blocks_final_score": step.blocks_final_score,
                }
                for step in contract.steps
            ],
        }
        for contract in WORKFLOW_CONTRACTS.values()
    ]
