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


@dataclass(frozen=True)
class EvidenceTier:
    key: str
    name: str
    priority: int
    purpose: str
    examples: tuple[str, ...]


@dataclass(frozen=True)
class JudgmentQuestion:
    key: str
    question: str
    required_output: str


@dataclass(frozen=True)
class LearningSignal:
    key: str
    source: str
    updates: str


@dataclass(frozen=True)
class UnifiedJudgmentStandard:
    key: str
    name: str
    root_layer: dict[str, object]
    evidence_priority: tuple[EvidenceTier, ...]
    required_questions: tuple[JudgmentQuestion, ...]
    decision_rules: tuple[str, ...]
    learning_signals: tuple[LearningSignal, ...]


UNIFIED_JUDGMENT_STANDARD = UnifiedJudgmentStandard(
    key="alignx_unified_judgment_v4",
    name="AlignX V4 人性驱动统一判断标准",
    root_layer={
        "system_positioning": "Human Nature Driven Business Intelligence System",
        "reasoning_order": [
            "Human Nature Model",
            "User Intent Model",
            "Platform Model",
            "Advertising Validation Model",
            "Capital Allocation Model",
            "Knowledge Evolution Model",
        ],
        "root_drives": ["seek_gain", "avoid_loss"],
        "evolution_drives": ["survival", "reproduction", "resource", "exploration"],
        "motivation_nodes": [
            {"key": "survival", "label": "生存", "description": "活下去"},
            {"key": "security", "label": "安全", "description": "避免风险"},
            {"key": "health", "label": "健康", "description": "维持生命质量"},
            {"key": "love", "label": "爱", "description": "关爱、情感连接"},
            {"key": "belonging", "label": "归属", "description": "融入群体"},
            {"key": "status", "label": "尊严", "description": "获得认同和身份"},
            {"key": "power", "label": "权力", "description": "获得控制力和影响力"},
            {"key": "freedom", "label": "自由", "description": "减少约束"},
            {"key": "expansion", "label": "扩张", "description": "获得更多资源和边界"},
            {"key": "curiosity", "label": "好奇", "description": "探索未知"},
            {"key": "pleasure", "label": "娱乐", "description": "获得愉悦"},
            {"key": "convenience", "label": "懒惰", "description": "降低成本和能量消耗"},
            {"key": "fear", "label": "恐惧", "description": "规避损失和危险"},
        ],
        "highest_principle": "产品只是树叶，需求是树枝，动机是树干，人性才是树根。",
    },
    evidence_priority=(
        EvidenceTier(
            key="market_feedback",
            name="真实市场反馈",
            priority=1,
            purpose="最终校验诊断是否被真实流量和成交支持",
            examples=("ad CTR/CVR/ACOS", "orders", "search term performance", "refund/return signals"),
        ),
        EvidenceTier(
            key="buyer_voice",
            name="买家声音",
            priority=2,
            purpose="识别真实购买动机、痛点、犹豫点和未披露副作用",
            examples=("reviews", "Q&A", "buyer complaints", "positive purchase reasons"),
        ),
        EvidenceTier(
            key="listing_facts",
            name="Listing事实",
            priority=3,
            purpose="确认标题、五点、图片、A+、价格、类目、库存和合规基础是否完整",
            examples=("title", "bullets", "images", "A+ content", "price", "category"),
        ),
        EvidenceTier(
            key="semantic_reasoning",
            name="语义与因果推理",
            priority=4,
            purpose="判断平台是否理解商品、买家是否理解价值、因果承诺是否可信",
            examples=("COSMO relations", "Rufus questions", "causal claims", "vector mapping"),
        ),
        EvidenceTier(
            key="model_inference",
            name="模型推理",
            priority=5,
            purpose="在证据充分时综合判断；证据不足时只能输出假设或待验证",
            examples=("agent decision", "LLM summary", "strategy recommendation"),
        ),
    ),
    required_questions=(
        JudgmentQuestion("human_root", "这个购买行为背后是哪类趋利或避害驱动力？", "root drive + active human motivation nodes"),
        JudgmentQuestion("motivation_path", "人性驱动力如何转成需求、场景、解决方案和表达？", "motivation → need → scenario → solution → expression"),
        JudgmentQuestion("problem", "当前最重要的问题是什么？", "problem title + impacted metric"),
        JudgmentQuestion("evidence", "证据来自哪里，强度如何？", "source table/ref + confidence + sample size"),
        JudgmentQuestion("cause", "为什么这个问题会影响点击、转化或广告效率？", "causal explanation"),
        JudgmentQuestion("action", "应该执行什么动作？", "specific listing/ad/review action"),
        JudgmentQuestion("validation", "如何验证动作是否有效？", "hypothesis_id + metric rule + observation window"),
        JudgmentQuestion("learning", "验证结果如何回流到下一轮？", "hit_status + miss_reason + reusable learning"),
    ),
    decision_rules=(
        "所有判断必须先经过Human Nature Root Layer，再进入用户意图和平台识别；禁止从关键词直接开始推理。",
        "Product Layer统一改为Solution Layer；产品只是解决方案的一种承载，不作为根节点。",
        "没有事实来源的建议只能作为低置信度假设，不能进入P0动作。",
        "广告记录未绑定hypothesis_id时，只能标记未归因，不能判定诊断命中或失败。",
        "假设级点击少于100时，只能输出待验证，不能输出未命中。",
        "真实广告/成交/退货反馈优先级高于评论，评论优先级高于Listing语义推理，语义推理优先级高于模型总结。",
        "规则兜底、样本不足、mock/demo数据必须显式标记，不能伪装成AI主判断。",
        "每个复盘结论必须写入hit_status、miss_reason和下一轮action，否则不进入学习记忆。",
    ),
    learning_signals=(
        LearningSignal("motivation_hit", "ad_validation", "提升对应人性动机、需求、场景和表达链路权重"),
        LearningSignal("motivation_miss", "ad_validation", "降低对应动机链路权重并记录误判发生在哪一层"),
        LearningSignal("hypothesis_hit", "ad_validation", "提升相似假设和关键词意图的权重"),
        LearningSignal("hypothesis_miss", "ad_validation", "降低对应诊断路径权重并记录失败原因"),
        LearningSignal("sample_not_enough", "ad_validation", "保持假设中立，继续拉样本或缩小关键词组"),
        LearningSignal("review_gap", "review_validation", "把未承接痛点回填到Listing诊断和广告假设"),
        LearningSignal("version_result", "optimization_timeline", "把Listing改动前后效果写入ASIN长期记忆"),
    ),
)


ASIN_SELECTION_CONTRACT = WorkflowContract(
    key="asin_selection",
    name="ASIN选品决策",
    steps=(
        PipelineStep("human_nature_reasoning", "rules", "识别趋利/避害、13驱动力、动机、需求、场景和Solution层", "human_nature_graph", True),
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
        PipelineStep("human_nature_reasoning", "rules", "先识别人性驱动力，再推导用户意图和平台理解路径", "human_nature_graph", True),
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
        PipelineStep("human_nature_reasoning", "rules", "先拆竞品抓住了哪些人性驱动力，再判断我方借鉴/避开/攻击/差异化", "human_nature_graph", True),
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
        PipelineStep("human_nature_reasoning", "rules", "先确认广告正在验证哪条动机-需求-场景-表达链路", "human_nature_graph", True),
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
        PipelineStep("human_nature_reasoning", "rules", "回流命中/未命中时修正人性动机图谱权重", "human_motivation_graph", True),
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


def judgment_standard_summary() -> dict[str, object]:
    standard = UNIFIED_JUDGMENT_STANDARD
    return {
        "key": standard.key,
        "name": standard.name,
        "root_layer": standard.root_layer,
        "evidence_priority": [
            {
                "key": item.key,
                "name": item.name,
                "priority": item.priority,
                "purpose": item.purpose,
                "examples": list(item.examples),
            }
            for item in standard.evidence_priority
        ],
        "required_questions": [
            {
                "key": item.key,
                "question": item.question,
                "required_output": item.required_output,
            }
            for item in standard.required_questions
        ],
        "decision_rules": list(standard.decision_rules),
        "learning_signals": [
            {
                "key": item.key,
                "source": item.source,
                "updates": item.updates,
            }
            for item in standard.learning_signals
        ],
    }
