import { useEffect, useMemo, useRef, useState } from "react";
import { AppSidebar } from "@/components/AppSidebar";
import { PageHeader } from "@/components/PageHeader";
import { NextStepActions } from "@/components/NextStepActions";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { getAuthHeaders } from "@/lib/auth-headers";
import { saveActionSnapshot } from "@/lib/workflow-api";
import { finishModuleTask, removeModuleTask, upsertModuleTask } from "@/lib/module-task-store";
import {
  RotateCcw,
  AlertTriangle,
  Lightbulb,
  ArrowRight,
  CheckCircle2,
  Target,
  Database,
  ClipboardCheck,
  BarChart3,
  XCircle,
  ShieldCheck,
} from "lucide-react";
import { useLocation } from "react-router-dom";

type AdMetrics = {
  impressions?: number;
  clicks?: number;
  spend?: number;
  orders?: number;
  sales?: number;
  ctr?: number;
  cvr?: number;
  acos?: number;
};

type HypothesisValidation = {
  hypothesis_id: string;
  keyword_group_id?: string;
  optimization_round?: number;
  keywords?: string[];
  metrics?: AdMetrics;
  hit_status?: string;
  failure_reason?: string;
  confidence?: string;
  record_count?: number;
};

type AgentDecision = {
  chief_decision?: {
    current_stage?: string;
    decision?: string;
    why?: string;
    next_action?: string;
    risk_if_ignored?: string;
    confidence?: string;
  };
  error_evidence_cards?: Array<{
    id: string;
    error: string;
    evidence: string;
    impact_area: string;
    suggested_action: string;
    validation_hypothesis_id: string;
    priority?: { level?: string; score?: number };
  }>;
  action_priority?: Array<{
    rank: number;
    level: string;
    score: number;
    action: string;
    expected_impact: string;
    validation_hypothesis_id: string;
    difficulty?: string;
    verification_cost?: string;
  }>;
  hit_rate_learning?: {
    status?: string;
    hit_rate?: number;
    basis?: string;
    reusable_learning?: string;
    next_iteration?: string;
    likely_failure_reason?: string;
    hypothesis_validations?: HypothesisValidation[];
    assigned_hypothesis_count?: number;
    completed_hypothesis_count?: number;
  };
  listing_version_contract?: {
    current_round?: number;
    next_snapshot_timing?: string;
    required_fields?: string[];
  };
  failure_reason_taxonomy?: Array<{ key: string; label: string; rule: string }>;
  learning_memory?: {
    scope?: string;
    total_rounds?: number;
    completed_rounds?: number;
    hit_rounds?: number;
    miss_rounds?: number;
    hit_rate?: number;
    confidence?: string;
    next_memory_action?: string;
    top_failure_reasons?: Array<{ reason: string; count: number }>;
    top_actions?: Array<{ action: string; count: number }>;
    reusable_learnings?: Array<{
      round_id: number;
      optimization_round?: number;
      diagnosis_issue?: string;
      suggested_action?: string;
      confidence_gain?: number;
    }>;
  };
};

type WorkflowChain = {
  product?: { asin?: string; title?: string; optimization_round?: number };
  chain_status?: string;
  agent_decision?: AgentDecision;
};

const mockSuggestions = [
  {
    problem: "除味主需求验证成立",
    reason: "当前ASIN在 cat litter box odor eliminator 和 ammonia odor remover 两组词上点击与转化同时达标，说明评论高频需求已被Listing承接。",
    action: "保留标题前半段 Odor Control 和 Activated Carbon Filter 表达，下一轮把除味场景同步到主图和第一张副图。",
    verify: "继续观察除味词CTR、CVR和ACOS是否保持稳定",
    priority: "高",
  },
  {
    problem: "滤芯更换成本解释不足",
    reason: "本品诊断显示信任解释低于需求承接，用户可能理解了除味承诺，但仍担心滤芯寿命和后续维护。",
    action: "在五点和A+中补充滤芯更换周期、单次维护成本和清洁步骤。",
    verify: "用详情页承接优化后的CVR变化验证",
    priority: "高",
  },
  {
    problem: "cat litter deodorizer 转化弱于主词",
    reason: "广告验证中 deodorizer 词点击有响应但订单贡献低，语义可能偏向除味剂而不是猫砂盆产品。",
    action: "降低 deodorizer 词预算，新增 enclosed litter box odor control 和 apartment cat litter box odor control 做下一轮测试。",
    verify: "对比新词ACOS和订单贡献",
    priority: "中",
  },
];

const feedbackRecords = [
  {
    source: "效果验证",
    item: "除味关键词测试",
    before: "Listing 未明确承接 ammonia odor remover",
    after: "标题/五点补充 Activated Carbon Odor Control",
    metric: "点击157，CVR 10.19%，ACOS 19.05%",
    status: "命中",
  },
  {
    source: "执行记录",
    item: "cat litter deodorizer",
    before: "按除味主词同预算测试",
    after: "识别为偏除味剂意图，下一轮降低预算",
    metric: "点击41，订单3，贡献弱于主词",
    status: "待校准",
  },
  {
    source: "本品诊断",
    item: "滤芯信任解释",
    before: "未说明更换周期和维护成本",
    after: "待进入下一轮 Listing 修改",
    metric: "风险消除分 76",
    status: "待执行",
  },
];

const reviewConclusions = [
  {
    label: "成立假设",
    text: "除味和氨气风险表达能提升当前ASIN的点击确认和下单信任。",
    action: "保留 odor eliminator、ammonia odor remover 两组关键词和对应 Listing 表达。",
  },
  {
    label: "未成立原因",
    text: "deodorizer 词偏向除味剂品类，和猫砂盆购买意图存在错配。",
    action: "降低该词预算，拆分测试 enclosed litter box odor control。",
  },
  {
    label: "保留项",
    text: "Activated Carbon Filter 与 Odor Control 的表达方向被广告验证支持。",
    action: "下一轮同步到主图、第一张副图和 A+ 首屏。",
  },
  {
    label: "放弃项",
    text: "暂停高花费低订单的泛除味剂词，避免广告验证污染判断。",
    action: "从下一轮测试计划中移除泛除味剂词组。",
  },
];

const nextRoundActions = [
  {
    rank: 1,
    problemType: "Listing表达承接问题",
    title: "补强主图和首张副图的除味证据",
    reason: "上新检测主图分 74，广告验证已证明除味需求有效，视觉证据仍需要承接。",
    decisionBasis: "视觉证据弱，但广告验证已证明买家需求真实存在。",
    owner: "本品诊断",
    path: "/listing-diagnosis",
    cta: "进入本品诊断",
    priority: "P0",
  },
  {
    rank: 2,
    problemType: "上架前表达完整性问题",
    title: "补充滤芯更换周期和维护成本",
    reason: "风险消除分 76，买家可能理解除味承诺，但仍担心后续耗材成本。",
    decisionBasis: "这是上架表达完整性和信任解释问题，需要回到上新检测重新校准。",
    owner: "上新检测",
    path: "/listing-launch-check",
    cta: "进入上新检测",
    priority: "P1",
  },
  {
    rank: 3,
    problemType: "广告关键词验证问题",
    title: "重建下一轮广告关键词分组",
    reason: "保留已命中除味主词，降低 deodorizer 预算，新增 apartment/enclosed 场景词。",
    decisionBasis: "问题来自广告关键词意图分化，需要重新生成测试计划再进入执行记录。",
    owner: "广告验证",
    path: "/ab-test-comparison",
    cta: "进入A/B测试",
    priority: "P1",
  },
  {
    rank: 4,
    problemType: "竞品变化问题",
    title: "复查竞品是否已强化除味场景",
    reason: "如果竞品近期同步强化 Odor Control 场景，本品需要重新判断差异化空间。",
    decisionBasis: "复盘结论依赖竞品环境，竞品变化会影响下一轮动作优先级。",
    owner: "竞品诊断",
    path: "/competitor-analysis?tab=strategy",
    cta: "进入竞品诊断",
    priority: "P2",
  },
];

const formatPercent = (value?: number) => {
  if (typeof value !== "number" || Number.isNaN(value)) return "0%";
  return `${value.toFixed(value % 1 === 0 ? 0 : 1)}%`;
};

const formatNumber = (value?: number) => {
  if (typeof value !== "number" || Number.isNaN(value)) return "0";
  return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
};

const normalizeStatus = (status?: string) => {
  if (!status) return "待验证";
  if (["hit", "命中", "已命中", "成立"].includes(status)) return "命中";
  if (["miss", "未命中", "不成立"].includes(status)) return "未命中";
  if (["pending", "待验证", "样本不足"].includes(status)) return "待验证";
  return status;
};

const failureReasonLabel = (reason?: string) => {
  const map: Record<string, string> = {
    none: "暂无失败归因",
    sample_not_enough: "样本不足，暂不判定",
    unassigned: "广告数据未绑定诊断假设",
    keyword_mismatch: "关键词意图错配",
    low_ctr: "点击吸引不足",
    low_cvr: "详情页承接不足",
    high_acos: "广告成本承压",
    price_trust_gap: "价格/信任承接不足",
    review_trust_gap: "评论信任不足",
  };
  if (!reason) return "等待样本验证";
  return map[reason] || reason;
};

export default function OptimizationSuggestions() {
  useRequireAuth();
  const location = useLocation();
  const view = new URLSearchParams(location.search).get("view") || "next-round";
  const savedViewRef = useRef("");
  const [workflowChain, setWorkflowChain] = useState<WorkflowChain | null>(null);
  const [feedbackStats, setFeedbackStats] = useState({
    rounds: 3,
    hitRate: "100%",
    learnings: 1,
  });

  useEffect(() => {
    async function loadFeedbackStats() {
      try {
        const [timelineRes, adRes] = await Promise.all([
          fetch("/api/v1/entities/optimization_timeline?limit=200", { headers: getAuthHeaders() }),
          fetch("/api/v1/entities/ad_data?limit=200", { headers: getAuthHeaders() }),
        ]);
        const timeline = await timelineRes.json();
        const ad = await adRes.json();
        const events = timeline?.items || [];
        const ads = ad?.items || [];
        const clicks = ads.reduce((sum: number, item: { clicks?: number }) => sum + (item.clicks || 0), 0);
        const orders = ads.reduce((sum: number, item: { orders?: number }) => sum + (item.orders || 0), 0);
        const cvr = clicks > 0 ? (orders / clicks) * 100 : 0;
        const hitRate = clicks >= 100 ? (cvr >= 8 ? "100%" : "0%") : "样本不足";
        setFeedbackStats({
          rounds: events.length,
          hitRate,
          learnings: events.filter((event: { score_details?: string }) =>
            String(event.score_details || "").includes("conclusion")
          ).length,
        });
      } catch {
        setFeedbackStats({ rounds: 3, hitRate: "100%", learnings: 1 });
      }
    }
    loadFeedbackStats();
  }, []);

  useEffect(() => {
    async function loadWorkflowChain() {
      try {
        const res = await fetch("/api/v1/workflow-chain/current", { headers: getAuthHeaders() });
        if (!res.ok) throw new Error(`workflow-chain ${res.status}`);
        const data = await res.json();
        setWorkflowChain(data);
      } catch {
        setWorkflowChain(null);
      }
    }
    loadWorkflowChain();
  }, []);

  const pageConfig = {
    "data-feedback": {
      title: "数据回流",
      objective: "沉淀广告验证和执行结果，形成可追溯的数据资产",
      input: "执行记录、效果验证、Listing诊断、A/B测试结果",
      process: "保存修改前后数据、广告指标、是否命中、未命中原因",
      output: "判断命中率、历史验证记录、可复用经验",
      action: "进入复盘结论判断原因",
      feedback: "用于校准下一轮诊断置信度",
      tone: "emerald" as const,
      icon: Database,
    },
    conclusion: {
      title: "复盘结论",
      objective: "判断本轮优化为什么成立或为什么未成立",
      input: "数据回流结果、CTR/CVR/ACOS变化、评论反馈、竞品变化",
      process: "归因命中/未命中原因，区分点击问题、承接问题和价格信任问题",
      output: "复盘结论、成立假设、失败原因、保留/放弃项",
      action: "沉淀结论后生成下一轮优化",
      feedback: "把结论写回经验库",
      tone: "purple" as const,
      icon: ClipboardCheck,
    },
    "next-round": {
      title: "下一轮优化",
      objective: "基于复盘结论生成下一轮Listing和广告动作",
      input: "复盘结论、未解决问题、有效关键词、无效关键词",
      process: "按影响度、置信度、执行成本排序下一轮动作",
      output: "下一轮优化清单、测试优先级、验证路径",
      action: "进入上新检测、本品诊断或A/B测试",
      feedback: "下一轮执行后继续回流",
      tone: "rose" as const,
      icon: RotateCcw,
    },
  }[view] || {
    title: "下一轮优化",
    objective: "基于复盘结论生成下一轮Listing和广告动作",
    input: "复盘结论、未解决问题、有效关键词、无效关键词",
    process: "按影响度、置信度、执行成本排序下一轮动作",
    output: "下一轮优化清单、测试优先级、验证路径",
    action: "进入上新检测、本品诊断或A/B测试",
    feedback: "下一轮执行后继续回流",
    tone: "rose" as const,
    icon: RotateCcw,
  };

  const PageIcon = pageConfig.icon;
  const agentDecision = workflowChain?.agent_decision;
  const hitLearning = agentDecision?.hit_rate_learning;
  const evidenceCards = agentDecision?.error_evidence_cards || [];
  const actionPriority = agentDecision?.action_priority || [];
  const hypothesisValidations = hitLearning?.hypothesis_validations || [];
  const listingContract = agentDecision?.listing_version_contract;
  const failureTaxonomy = agentDecision?.failure_reason_taxonomy || [];
  const learningMemory = agentDecision?.learning_memory;
  const contractGaps = ((listingContract as typeof listingContract & { current_gaps?: string[] })?.current_gaps || []) as string[];

  const liveFeedbackStats = useMemo(() => {
    if (!hitLearning && !workflowChain) return feedbackStats;
    const hitRate =
      typeof hitLearning?.hit_rate === "number"
        ? `${hitLearning.hit_rate}%`
        : hitLearning?.status || feedbackStats.hitRate;
    return {
      rounds: listingContract?.current_round || feedbackStats.rounds,
      hitRate,
      learnings: learningMemory?.completed_rounds || hitLearning?.completed_hypothesis_count || feedbackStats.learnings,
    };
  }, [feedbackStats, hitLearning, learningMemory, listingContract, workflowChain]);

  const liveFeedbackRecords = useMemo(() => {
    if (!hypothesisValidations.length) return feedbackRecords;
    return hypothesisValidations.map((item) => {
      const metrics = item.metrics || {};
      const keywords = item.keywords?.length ? item.keywords.join("、") : item.keyword_group_id || "未命名词组";
      const status = normalizeStatus(item.hit_status);
      const clicks = metrics.clicks || 0;
      const orders = metrics.orders || 0;
      const cvr = typeof metrics.cvr === "number" ? metrics.cvr : clicks ? (orders / clicks) * 100 : 0;
      const acos = typeof metrics.acos === "number" ? metrics.acos : 0;
      const isUnassigned = item.hypothesis_id === "unassigned";
      return {
        source: isUnassigned ? "待绑定广告数据" : "假设级广告验证",
        item: isUnassigned ? "尚未绑定具体诊断假设" : `${item.hypothesis_id} / ${item.keyword_group_id || "default"}`,
        before: `验证词组：${keywords}`,
        after: isUnassigned
          ? "先在广告执行记录中补充 hypothesis_id 与 keyword_group_id，避免数据污染命中率。"
          : `${failureReasonLabel(item.failure_reason)}；置信度：${item.confidence || "低"}`,
        metric: `曝光${formatNumber(metrics.impressions)}，点击${formatNumber(clicks)}，订单${formatNumber(orders)}，CVR ${formatPercent(cvr)}，ACOS ${formatPercent(acos)}`,
        status,
      };
    });
  }, [hypothesisValidations]);

  const feedbackQuality = useMemo(() => {
    const validations = hypothesisValidations;
    const totalClicks = validations.reduce((sum, item) => sum + (item.metrics?.clicks || 0), 0);
    const assignedCount = validations.filter((item) => item.hypothesis_id && item.hypothesis_id !== "unassigned").length;
    const completedCount = validations.filter((item) => ["命中", "已命中", "未命中", "hit", "miss"].includes(item.hit_status || "")).length;
    const hitCount = validations.filter((item) => ["命中", "已命中", "hit"].includes(item.hit_status || "")).length;
    const sampleReady = totalClicks >= 100;
    const bindingReady = assignedCount > 0 && assignedCount === validations.length;
    const canConclude = sampleReady && bindingReady && completedCount > 0;
    const hitRate = completedCount ? Math.round((hitCount / completedCount) * 100) : 0;
    const status = canConclude ? (hitRate >= 60 ? "可以沉淀经验" : "需要复盘归因") : "暂不判定";
    const reason = !validations.length
      ? "还没有广告验证记录进入回流。"
      : !bindingReady
        ? "存在广告记录未绑定诊断假设，不能直接用于校准下一轮判断。"
        : !sampleReady
          ? "广告点击样本不足100次，容易把偶然波动误判成结论。"
          : completedCount === 0
            ? "广告样本已有，但还没有形成命中/未命中的验证结论。"
            : hitRate >= 60
              ? "广告样本、假设绑定和验证结论已形成闭环，可以沉淀可复用经验。"
              : "已有验证结论但命中率偏低，需要先复盘失败原因再进入下一轮。";
    return {
      totalClicks,
      assignedCount,
      completedCount,
      hitCount,
      hitRate,
      sampleReady,
      bindingReady,
      canConclude,
      status,
      reason,
    };
  }, [hypothesisValidations]);

  const feedbackActions = useMemo(() => {
    if (!hypothesisValidations.length) {
      return [
        { label: "补录广告数据", path: "/ad-analytics?view=records", variant: "default" as const },
        { label: "查看效果验证", path: "/ad-analytics?view=validation", variant: "outline" as const },
      ];
    }
    if (!feedbackQuality.bindingReady) {
      return [
        { label: "绑定假设ID", path: "/ad-analytics?view=records", variant: "default" as const },
        { label: "查看测试计划", path: "/ab-test-comparison", variant: "outline" as const },
      ];
    }
    if (!feedbackQuality.sampleReady) {
      return [
        { label: "补样本记录", path: "/ad-analytics?view=records", variant: "default" as const },
        { label: "查看效果验证", path: "/ad-analytics?view=validation", variant: "outline" as const },
      ];
    }
    return [
      { label: "查看复盘结论", path: "/optimization-suggestions?view=conclusion", variant: "default" as const },
      { label: "生成下一轮优化", path: "/optimization-suggestions?view=next-round", variant: "outline" as const },
    ];
  }, [feedbackQuality.bindingReady, feedbackQuality.sampleReady, hypothesisValidations.length]);

  const conclusionQuality = useMemo(() => {
    const hitStatus = normalizeStatus(hitLearning?.status);
    const canFinalize = feedbackQuality.canConclude;
    const hasMiss = hypothesisValidations.some((item) => normalizeStatus(item.hit_status) === "未命中");
    const hasHit = hypothesisValidations.some((item) => normalizeStatus(item.hit_status) === "命中");
    const title = canFinalize
      ? hasMiss && !hasHit
        ? "本轮未成立，需要先复盘失败原因"
        : "本轮可形成复盘结论"
      : "暂不能形成最终复盘结论";
    const reason = canFinalize
      ? hitLearning?.basis || "广告样本、假设绑定和命中判断已满足复盘条件。"
      : feedbackQuality.reason;
    const nextAction = canFinalize
      ? hitLearning?.next_iteration || agentDecision?.chief_decision?.next_action || "沉淀结论后进入下一轮优化。"
      : "先补齐广告样本、假设绑定或效果验证结论，再生成下一轮优化。";
    return {
      title,
      reason,
      nextAction,
      canFinalize,
      status: canFinalize ? hitStatus : "暂不判定",
    };
  }, [agentDecision?.chief_decision?.next_action, feedbackQuality.canConclude, feedbackQuality.reason, hitLearning, hypothesisValidations]);

  const conclusionActions = useMemo(() => {
    if (!conclusionQuality.canFinalize) {
      return [
        { label: "回到数据回流", path: "/optimization-suggestions?view=data-feedback", variant: "default" as const },
        { label: "补录广告记录", path: "/ad-analytics?view=records", variant: "outline" as const },
      ];
    }
    return [
      { label: "生成下一轮优化", path: "/optimization-suggestions?view=next-round", variant: "default" as const },
      { label: "查看效果验证", path: "/ad-analytics?view=validation", variant: "outline" as const },
    ];
  }, [conclusionQuality.canFinalize]);

  const liveReviewConclusions = useMemo(() => {
    if (!agentDecision) return reviewConclusions;
    const failure = failureTaxonomy.find((item) => item.key === hitLearning?.likely_failure_reason);
    const topEvidence = evidenceCards[0];
    return [
      {
        label: "本轮判断",
        text: agentDecision.chief_decision?.decision || "暂无完整闭环决策",
        action: agentDecision.chief_decision?.next_action || "先补齐广告验证和复盘记录。",
      },
      {
        label: "命中状态",
        text: hitLearning?.basis || "广告验证尚未形成有效样本。",
        action: hitLearning?.reusable_learning || "继续绑定假设ID后再回流判断。",
      },
      {
        label: "主要未成立原因",
        text: failure ? `${failure.label}：${failure.rule}` : "当前没有明确失败归因。",
        action: hitLearning?.next_iteration || "下一轮继续按假设分组验证。",
      },
      {
        label: "优先修正项",
        text: topEvidence?.evidence || "暂无高优先级证据卡。",
        action: topEvidence?.suggested_action || "完成诊断、广告、复盘三段数据绑定。",
      },
    ];
  }, [agentDecision, evidenceCards, failureTaxonomy, hitLearning]);

  const liveNextRoundActions = useMemo(() => {
    if (!actionPriority.length) return nextRoundActions;
    return actionPriority.map((item) => {
      const target =
        item.expected_impact === "ranking_relevance"
          ? { path: "/listing-diagnosis", cta: "进入本品诊断", owner: "本品诊断", problemType: "平台语义错配" }
          : item.expected_impact === "click"
            ? { path: "/listing-launch-check", cta: "进入上新检测", owner: "上新检测", problemType: "点击证据不足" }
            : { path: "/listing-diagnosis", cta: "进入本品诊断", owner: "本品诊断", problemType: "转化信任承接不足" };
      return {
        rank: item.rank,
        problemType: target.problemType,
        title: item.action,
        reason: `来自 ${item.validation_hypothesis_id}，影响 ${item.expected_impact}，验证成本${item.verification_cost || "低"}。`,
        decisionBasis: `优先级分 ${item.score}，难度${item.difficulty || "中"}；需要在下一轮广告中继续绑定假设ID。`,
        owner: target.owner,
        path: target.path,
        cta: target.cta,
        priority: item.level,
      };
    });
  }, [actionPriority]);

  const nextRoundQuality = useMemo(() => {
    const ready = conclusionQuality.canFinalize;
    const highestPriority = liveNextRoundActions[0]?.priority || "P1";
    const primaryOwner = liveNextRoundActions[0]?.owner || "本品诊断";
    const blockedReason = !feedbackQuality.bindingReady
      ? "广告记录还没有完整绑定诊断假设，下一轮会失去归因依据。"
      : !feedbackQuality.sampleReady
        ? "广告点击样本未满100次，下一轮优先补足样本，不调整Listing。"
        : !feedbackQuality.completedCount
          ? "还没有完成命中/未命中判断，不能把动作写入下一轮。"
          : "复盘结论尚未满足沉淀条件。";
    return {
      ready,
      title: ready ? "可以生成下一轮优化任务" : "下一轮暂不应直接执行",
      reason: ready
        ? `优先从 ${primaryOwner} 开始，最高优先级为 ${highestPriority}；执行时只改一个核心变量并绑定同一假设ID。`
        : blockedReason,
      nextAction: ready
        ? "按优先级执行第一项，完成修改后进入广告验证。"
        : "先补齐数据回流和复盘判定，再生成下一轮动作。",
    };
  }, [
    conclusionQuality.canFinalize,
    feedbackQuality.bindingReady,
    feedbackQuality.completedCount,
    feedbackQuality.sampleReady,
    liveNextRoundActions,
  ]);

  const nextRoundBuckets = useMemo(() => {
    const buckets = [
      {
        key: "listing",
        title: "Listing修改",
        desc: "标题、五点、主图、副图、A+ 的表达和承接问题。",
        actions: liveNextRoundActions.filter((item) => ["本品诊断", "上新检测"].includes(item.owner)),
      },
      {
        key: "ad",
        title: "广告验证",
        desc: "关键词分组、预算、匹配方式和A/B测试变量。",
        actions: liveNextRoundActions.filter((item) => item.owner === "广告验证" || item.path.includes("ab-test")),
      },
      {
        key: "market",
        title: "市场复查",
        desc: "竞品变化、价格带变化和类目环境变化。",
        actions: liveNextRoundActions.filter((item) => item.owner === "竞品诊断" || item.path.includes("competitor")),
      },
    ];
    const assigned = new Set(buckets.flatMap((bucket) => bucket.actions.map((item) => item.rank)));
    const unassigned = liveNextRoundActions.filter((item) => !assigned.has(item.rank));
    if (unassigned.length) {
      buckets.push({
        key: "other",
        title: "其他动作",
        desc: "需要人工确认归属的下一轮任务。",
        actions: unassigned,
      });
    }
    return buckets.filter((bucket) => bucket.actions.length);
  }, [liveNextRoundActions]);

  const summaryChips = useMemo(() => {
    if (!agentDecision) {
      return [
        "当前ASIN已回流至判断系统",
        "除味需求已回流至 Listing 优化建议",
        "广告验证结果已回流至下一轮测试优先级",
      ];
    }
    return [
      workflowChain?.product?.asin ? `${workflowChain.product.asin} 已进入闭环判断` : "当前产品已进入闭环判断",
      hitLearning?.assigned_hypothesis_count
        ? `${hitLearning.assigned_hypothesis_count} 个广告假设已绑定验证`
        : "广告记录需要绑定假设ID",
      listingContract?.next_snapshot_timing || "下一轮修改前后必须保存版本快照",
    ];
  }, [agentDecision, hitLearning, listingContract, workflowChain]);

  useEffect(() => {
    const key = `${view}-${liveFeedbackStats.rounds}-${liveFeedbackStats.hitRate}-${liveFeedbackStats.learnings}-${workflowChain?.product?.asin || ""}`;
    if (savedViewRef.current === key) return;
    savedViewRef.current = key;
    const moduleTaskId = `optimization-snapshot:${key}`;
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "optimization-suggestions",
      label: `${pageConfig.title}沉淀`,
      status: "running",
      detail: "正在保存闭环优化页面快照",
      path: `/optimization-suggestions?view=${view}`,
    });
    saveActionSnapshot({
      module_key: "optimization",
      module_name: "数据回流",
      action_key: view,
      action_name: pageConfig.title,
      title: pageConfig.title,
      input_snapshot: {
        view,
        feedback_stats: liveFeedbackStats,
        product: workflowChain?.product || null,
      },
      output_snapshot: {
        page_config: pageConfig,
        feedback_records: view === "data-feedback" ? liveFeedbackRecords : [],
        review_conclusions: view === "conclusion" ? liveReviewConclusions : [],
        next_round_actions: view === "next-round" ? liveNextRoundActions : [],
        agent_decision: agentDecision || null,
        listing_version_contract: listingContract || null,
        learning_memory: learningMemory || null,
      },
      data_source: "workflow_records",
      confidence: liveFeedbackStats.hitRate === "样本不足" ? "low" : "medium",
      ai_called: false,
      source_record_table: "action_snapshots",
    })
      .then(() => finishModuleTask(moduleTaskId, "completed", "闭环优化快照已保存"))
      .catch(() => finishModuleTask(moduleTaskId, "failed", "闭环优化快照保存失败"))
      .finally(() => window.setTimeout(() => removeModuleTask(moduleTaskId), 1200));
  }, [
    view,
    liveFeedbackStats.rounds,
    liveFeedbackStats.hitRate,
    liveFeedbackStats.learnings,
    pageConfig,
    liveFeedbackRecords,
    liveReviewConclusions,
    liveNextRoundActions,
    agentDecision,
    listingContract,
    learningMemory,
    workflowChain?.product,
  ]);

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto bg-[#f5f5f7]">
        <div className="p-4 sm:p-6 lg:p-8 max-w-6xl mx-auto pt-14 md:pt-6">
          <h1 className="text-xl sm:text-2xl font-bold mb-4 flex items-center gap-2">
            <PageIcon className="w-5 h-5 text-emerald-600" />
            {pageConfig.title}
          </h1>

          <PageHeader
            objective={pageConfig.objective}
            inputSource={pageConfig.input}
            process={pageConfig.process}
            outputTarget={pageConfig.output}
            action={pageConfig.action}
            feedback={pageConfig.feedback}
            tone={pageConfig.tone}
          />

          {agentDecision && (
            <Card className="bg-white border-gray-200 p-5 mb-6">
              <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge className="bg-brand-50 text-brand-700 border-brand-200">
                      {agentDecision.chief_decision?.current_stage || "闭环决策"}
                    </Badge>
                    <span className="text-xs text-gray-500">
                      置信度：{agentDecision.chief_decision?.confidence || "低"}
                    </span>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900 mt-3">
                    {agentDecision.chief_decision?.decision || "暂无完整决策"}
                  </h2>
                  <p className="text-sm text-gray-600 mt-2">
                    {agentDecision.chief_decision?.why || "系统还在等待数据回流。"}
                  </p>
                  <p className="text-xs text-brand-600 mt-2">
                    下一步：{agentDecision.chief_decision?.next_action || "补齐诊断、广告验证和复盘记录。"}
                  </p>
                </div>
                <div className="grid grid-cols-3 gap-2 min-w-full lg:min-w-[360px]">
                  {[
                    { label: "绑定假设", value: String(hitLearning?.assigned_hypothesis_count || 0) },
                    { label: "完成假设", value: String(hitLearning?.completed_hypothesis_count || 0) },
                    { label: "版本轮次", value: String(listingContract?.current_round || 1) },
                  ].map((item) => (
                    <div key={item.label} className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                      <p className="text-[11px] text-gray-500">{item.label}</p>
                      <p className="text-lg font-bold text-gray-900 mt-1">{item.value}</p>
                    </div>
                  ))}
                </div>
              </div>
              {contractGaps.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {contractGaps.map((gap) => (
                    <span key={gap} className="text-xs px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-100">
                      {gap}
                    </span>
                  ))}
                </div>
              )}
            </Card>
          )}

          {view === "data-feedback" && (
            <>
              <Card className="bg-white border-gray-200 p-5 mb-6">
                <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-5">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge
                        className={
                          feedbackQuality.canConclude
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : "bg-amber-50 text-amber-700 border-amber-200"
                        }
                      >
                        {feedbackQuality.status}
                      </Badge>
                      <span className="text-xs text-gray-500">
                        样本门槛：广告点击达到100次后再判定
                      </span>
                    </div>
	                    <h2 className="text-lg font-semibold text-gray-900 mt-3">投放经验沉淀</h2>
                    <p className="text-sm text-gray-600 mt-2">{feedbackQuality.reason}</p>
                  </div>
                  <div className="flex flex-wrap gap-2 shrink-0">
                    {feedbackActions.map((action) => (
                      <Button
                        key={action.label}
                        asChild
                        variant={action.variant === "outline" ? "outline" : "default"}
                        className={action.variant === "outline" ? "border-gray-200 text-brand-700 hover:bg-brand-50" : "bg-brand-700 hover:bg-brand-800"}
                      >
                        <a href={action.path}>
                          {action.label}
                          <ArrowRight className="w-3.5 h-3.5 ml-1" />
                        </a>
                      </Button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mt-5">
                  {[
	                    { label: "投放轮次", value: String(liveFeedbackStats.rounds), desc: "当前版本链路" },
	                    { label: "点击够不够", value: formatNumber(feedbackQuality.totalClicks), desc: feedbackQuality.sampleReady ? "可以判断" : "未满100次" },
	                    { label: "是否知道在测什么", value: `${feedbackQuality.assignedCount}/${hypothesisValidations.length || 0}`, desc: feedbackQuality.bindingReady ? "已绑定卖点" : "需要补齐" },
	                    { label: "有效复盘项", value: String(feedbackQuality.completedCount), desc: "放量/暂停" },
	                    { label: "放量胜率", value: feedbackQuality.completedCount ? `${feedbackQuality.hitRate}%` : liveFeedbackStats.hitRate, desc: "只算已完成假设" },
                  ].map((item) => (
                    <div key={item.label} className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                      <p className="text-[11px] text-gray-500">{item.label}</p>
                      <p className="text-xl font-bold text-gray-900 mt-1">{item.value}</p>
                      <p className="text-[11px] text-gray-400 mt-1">{item.desc}</p>
                    </div>
                  ))}
                </div>
              </Card>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
                <Card className="bg-white border-gray-200 p-5">
                  <div className="flex items-center gap-2">
                    <ClipboardCheck className="w-4 h-4 text-emerald-600" />
	                    <p className="text-sm font-semibold text-gray-900">先确认在测哪个卖点</p>
                  </div>
                  <p className="text-sm text-gray-600 mt-3">
	                    {workflowChain?.product?.asin || "当前产品"} 的 Listing改动、广告关键词组和A/B变量必须绑定同一个假设ID，否则无法判断放量或暂停。
                  </p>
                </Card>
                <Card className="bg-white border-gray-200 p-5">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-amber-600" />
	                    <p className="text-sm font-semibold text-gray-900">暂缓判定</p>
                  </div>
                  <p className="text-sm text-gray-600 mt-3">
	                    先校验点击是否满100，再评估CTR、CVR、ACOS和订单贡献；未满样本只记录趋势。
                  </p>
                </Card>
                <Card className="bg-white border-gray-200 p-5">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-brand-600" />
	                    <p className="text-sm font-semibold text-gray-900">沉淀可复用经验</p>
                  </div>
                  <p className="text-sm text-gray-600 mt-3">
	                    只有“卖点已绑定 + 样本达标 + 能解释放量/暂停原因”的记录，才会校准下一轮运营动作。
                  </p>
                </Card>
              </div>
            </>
          )}

          {view === "conclusion" && (
            <>
              <Card className="bg-white border-gray-200 p-5 mb-6">
                <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-5">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge
                        className={
                          conclusionQuality.canFinalize
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : "bg-amber-50 text-amber-700 border-amber-200"
                        }
                      >
                        {conclusionQuality.status}
                      </Badge>
                      <span className="text-xs text-gray-500">
	                        复盘只使用已绑定卖点且样本达标的数据
                      </span>
                    </div>
                    <h2 className="text-lg font-semibold text-gray-900 mt-3">{conclusionQuality.title}</h2>
                    <p className="text-sm text-gray-600 mt-2">{conclusionQuality.reason}</p>
	                    <p className="text-sm text-brand-700 mt-3">下一步运营动作：{conclusionQuality.nextAction}</p>
                  </div>
                  <div className="flex flex-wrap gap-2 shrink-0">
                    {conclusionActions.map((action) => (
                      <Button
                        key={action.label}
                        asChild
                        variant={action.variant === "outline" ? "outline" : "default"}
                        className={action.variant === "outline" ? "border-gray-200 text-brand-700 hover:bg-brand-50" : "bg-brand-700 hover:bg-brand-800"}
                      >
                        <a href={action.path}>
                          {action.label}
                          <ArrowRight className="w-3.5 h-3.5 ml-1" />
                        </a>
                      </Button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-5">
                  {[
                    { label: "广告点击", value: formatNumber(feedbackQuality.totalClicks), desc: feedbackQuality.sampleReady ? "样本达标" : "样本不足" },
                    { label: "假设绑定", value: `${feedbackQuality.assignedCount}/${hypothesisValidations.length || 0}`, desc: feedbackQuality.bindingReady ? "完整" : "未完整" },
                    { label: "完成判断", value: String(feedbackQuality.completedCount), desc: "命中/未命中" },
                    { label: "可沉淀", value: conclusionQuality.canFinalize ? "是" : "否", desc: "是否写入经验库" },
                  ].map((item) => (
                    <div key={item.label} className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                      <p className="text-[11px] text-gray-500">{item.label}</p>
                      <p className="text-xl font-bold text-gray-900 mt-1">{item.value}</p>
                      <p className="text-[11px] text-gray-400 mt-1">{item.desc}</p>
                    </div>
                  ))}
                </div>
              </Card>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
                {liveReviewConclusions.map((item) => {
                  const isFailure = item.label.includes("未成立") || item.label.includes("修正");
                  const isPositive = item.label.includes("命中") || item.label.includes("判断") || item.label.includes("保留");
                  return (
                    <Card key={item.label} className="bg-white border-gray-200 p-5">
                      <div className="flex items-start gap-3">
                        <div
                          className={
                            isFailure
                              ? "w-9 h-9 rounded-lg bg-red-50 text-red-600 flex items-center justify-center shrink-0"
                              : isPositive
                                ? "w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0"
                                : "w-9 h-9 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center shrink-0"
                          }
                        >
                          {isFailure ? <XCircle className="w-4 h-4" /> : isPositive ? <ShieldCheck className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-gray-900">{item.label}</p>
                          <p className="text-sm text-gray-700 mt-2">{item.text}</p>
                          <p className="text-xs text-brand-600 mt-3">{item.action}</p>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>

              <Card className="bg-white border-gray-200 p-5 mb-6">
	                <h2 className="text-sm font-semibold text-gray-900 mb-3">下一轮投放依据</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {[
	                    { title: "可以放量", text: "点击样本达标且CTR/CVR/ACOS表现一致改善，才允许进入可复用经验。" },
	                    { title: "先停或先改", text: "先归因到点击、承接、价格信任、关键词意图或样本不足，不能直接否定整个Listing方向。" },
	                    { title: "单变量修改", text: "每轮只改一个核心变量，并把广告组、关键词组和Listing版本绑定到同一个假设ID。" },
                  ].map((item) => (
                    <div key={item.title} className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                      <p className="text-sm font-semibold text-gray-900">{item.title}</p>
                      <p className="text-xs text-gray-600 mt-2 leading-relaxed">{item.text}</p>
                    </div>
                  ))}
                </div>
              </Card>
            </>
          )}

          {view === "data-feedback" && (
            <Card className="bg-white border-gray-200 mb-6 overflow-hidden">
              <div className="p-5 border-b border-gray-100">
	                <h2 className="text-sm font-semibold text-gray-900">投放复盘记录</h2>
	                <p className="text-xs text-gray-500 mt-1">按假设ID追踪每一轮改动、广告指标、放量/暂停状态和下一步动作。</p>
              </div>
              <div className="divide-y divide-gray-100">
                {liveFeedbackRecords.length ? liveFeedbackRecords.map((record) => (
                  <div key={`${record.source}-${record.item}`} className="p-4 grid lg:grid-cols-[0.9fr_1.1fr_1.1fr_1fr_auto] gap-3 items-start">
                    <div>
	                      <p className="text-[11px] text-gray-400">钱花在哪</p>
                      <p className="text-sm font-semibold text-gray-900">{record.source}</p>
                      <p className="text-xs text-gray-500 mt-1">{record.item}</p>
                    </div>
                    <div>
	                      <p className="text-[11px] text-gray-400">投放前假设</p>
                      <p className="text-sm text-gray-700">{record.before}</p>
                    </div>
                    <div>
	                      <p className="text-[11px] text-gray-400">下一步怎么处理</p>
                      <p className="text-sm text-gray-700">{record.after}</p>
                    </div>
                    <div>
	                      <p className="text-[11px] text-gray-400">投放指标</p>
                      <p className="text-sm text-gray-700">{record.metric}</p>
                    </div>
                    <Badge
                      className={
                        record.status === "命中" || record.status === "已命中"
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : record.status === "未命中"
                            ? "bg-red-50 text-red-700 border-red-200"
                            : "bg-amber-50 text-amber-700 border-amber-200"
                      }
                    >
                      {record.status}
                    </Badge>
                  </div>
                )) : (
                  <div className="p-6 text-sm text-gray-500">
	                    暂无可指导下一轮投放的记录。请先上传Amazon广告报表，绑定卖点假设，满100点击后再复盘。
                  </div>
                )}
              </div>
            </Card>
          )}

          {view === "next-round" && (
            <Card className="bg-white border-gray-200 p-5 mb-6">
              <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-5">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge
                      className={
                        nextRoundQuality.ready
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : "bg-amber-50 text-amber-700 border-amber-200"
                      }
                    >
                      {nextRoundQuality.ready ? "可执行" : "先补齐"}
                    </Badge>
                    <span className="text-xs text-gray-500">
	                      下一轮单变量修改
                    </span>
                  </div>
                  <h2 className="text-lg font-semibold text-gray-900 mt-3">{nextRoundQuality.title}</h2>
                  <p className="text-sm text-gray-600 mt-2">{nextRoundQuality.reason}</p>
	                  <p className="text-sm text-brand-700 mt-3">下一步运营动作：{nextRoundQuality.nextAction}</p>
                </div>
                <div className="flex flex-wrap gap-2 shrink-0">
                  {(nextRoundQuality.ready
                    ? [
	                        { label: "先执行第一项", path: liveNextRoundActions[0]?.path || "/listing-diagnosis", variant: "default" as const },
	                        { label: "建立验证投放", path: "/ab-test-comparison", variant: "outline" as const },
                      ]
                    : [
	                        { label: "查看复盘结论", path: "/optimization-suggestions?view=conclusion", variant: "default" as const },
	                        { label: "补齐广告花费和订单", path: "/ad-analytics?view=records", variant: "outline" as const },
                      ]).map((action) => (
                    <Button
                      key={action.label}
                      asChild
                      variant={action.variant === "outline" ? "outline" : "default"}
                      className={action.variant === "outline" ? "border-gray-200 text-brand-700 hover:bg-brand-50" : "bg-brand-700 hover:bg-brand-800"}
                    >
                      <a href={action.path}>
                        {action.label}
                        <ArrowRight className="w-3.5 h-3.5 ml-1" />
                      </a>
                    </Button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mt-5">
                {[
                  { label: "动作数量", value: String(liveNextRoundActions.length), desc: "按复盘生成" },
                  { label: "最高优先级", value: liveNextRoundActions[0]?.priority || "P1", desc: liveNextRoundActions[0]?.owner || "待确认" },
                  { label: "版本轮次", value: String(listingContract?.current_round || 1), desc: "修改前后留快照" },
                  { label: "假设绑定", value: `${feedbackQuality.assignedCount}/${hypothesisValidations.length || 0}`, desc: feedbackQuality.bindingReady ? "完整" : "需补齐" },
                  { label: "样本状态", value: feedbackQuality.sampleReady ? "达标" : "不足", desc: `${formatNumber(feedbackQuality.totalClicks)} 次点击` },
                ].map((item) => (
                  <div key={item.label} className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                    <p className="text-[11px] text-gray-500">{item.label}</p>
                    <p className="text-xl font-bold text-gray-900 mt-1">{item.value}</p>
                    <p className="text-[11px] text-gray-400 mt-1">{item.desc}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {learningMemory && (
            <Card className="bg-white border-gray-200 p-5 mb-6">
              <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 mb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-emerald-600" />
                    <h2 className="text-sm font-semibold text-gray-900">类目/产品记忆</h2>
                  </div>
                  <p className="text-sm text-gray-600 mt-2">
                    {learningMemory.next_memory_action || "复盘完成后会沉淀可复用经验。"}
                  </p>
                </div>
                <div className="grid grid-cols-3 gap-2 min-w-full lg:min-w-[360px]">
                  {[
                    { label: "完成轮次", value: String(learningMemory.completed_rounds || 0) },
                    { label: "历史命中率", value: `${learningMemory.hit_rate || 0}%` },
                    { label: "记忆置信", value: learningMemory.confidence || "低" },
                  ].map((item) => (
                    <div key={item.label} className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                      <p className="text-[11px] text-gray-500">{item.label}</p>
                      <p className="text-lg font-bold text-gray-900 mt-1">{item.value}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                  <p className="text-[11px] font-semibold text-gray-500 mb-2">高频失败原因</p>
                  {(learningMemory.top_failure_reasons || []).length ? (
                    <div className="space-y-2">
                      {(learningMemory.top_failure_reasons || []).map((item) => (
                        <div key={item.reason} className="flex items-center justify-between gap-3 text-sm">
                          <span className="text-gray-700">{item.reason}</span>
                          <Badge className="bg-amber-50 text-amber-700 border-amber-200">{item.count}次</Badge>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500">暂无足够复盘样本。</p>
                  )}
                </div>
                <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                  <p className="text-[11px] font-semibold text-gray-500 mb-2">可复用动作</p>
                  {(learningMemory.top_actions || []).length ? (
                    <div className="space-y-2">
                      {(learningMemory.top_actions || []).map((item) => (
                        <div key={item.action} className="text-sm text-gray-700">
                          <span>{item.action}</span>
                          <span className="text-xs text-gray-400 ml-2">{item.count}次</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500">命中动作会在复盘后自动沉淀。</p>
                  )}
                </div>
              </div>
            </Card>
          )}

          {view === "next-round" && (
            <div className="space-y-5">
              {nextRoundBuckets.map((bucket) => (
                <Card key={bucket.key} className="bg-white border-gray-200 overflow-hidden">
                  <div className="p-5 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div>
                      <h2 className="text-sm font-semibold text-gray-900">{bucket.title}</h2>
                      <p className="text-xs text-gray-500 mt-1">{bucket.desc}</p>
                    </div>
                    <Badge className="bg-gray-50 text-gray-600 border-gray-200">{bucket.actions.length} 项</Badge>
                  </div>
                  <div className="divide-y divide-gray-100">
                    {bucket.actions.map((item) => (
                      <div key={item.rank} className="p-5">
                        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                          <div className="flex items-start gap-3">
                            <div className="w-9 h-9 rounded-lg bg-brand-50 text-brand-700 flex items-center justify-center font-bold text-sm shrink-0">
                              {item.rank}
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <h3 className="text-sm font-semibold text-gray-900">{item.title}</h3>
                                <Badge className="bg-red-50 text-red-600 border-red-200">{item.priority}</Badge>
                                <span className="text-[11px] text-gray-400">{item.owner}</span>
                              </div>
                              <p className="text-[11px] font-semibold text-brand-600 mt-2">{item.problemType}</p>
                              <p className="text-sm text-gray-600 mt-2">{item.reason}</p>
                              <div className="mt-3 grid grid-cols-1 lg:grid-cols-3 gap-2">
                                {[
                                  { label: "分流依据", value: item.decisionBasis },
                                  { label: "执行约束", value: "只改变一个核心变量，价格/主图/评价承诺保持稳定。" },
                                  { label: "验证方式", value: "下一轮广告记录必须绑定同一假设ID后回流。" },
                                ].map((detail) => (
                                  <div key={detail.label} className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                                    <p className="text-[11px] font-semibold text-gray-500">{detail.label}</p>
                                    <p className="text-xs text-gray-600 mt-1 leading-relaxed">{detail.value}</p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                          <Button
                            asChild
                            size="sm"
                            variant="outline"
                            className="border-gray-200 text-brand-600 hover:bg-brand-50 shrink-0"
                          >
                            <a href={item.path}>
                              {item.cta}
                              <ArrowRight className="w-3 h-3 ml-1" />
                            </a>
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              ))}

              <Card className="bg-white border-gray-200 p-5">
                <h2 className="text-sm font-semibold text-gray-900 mb-3">下一轮执行标准</h2>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                  {[
                    { title: "先改高置信项", text: "优先执行P0/P1，不同时改多个卖点。" },
                    { title: "保留对照组", text: "A版本保留原Listing，B版本只改一个变量。" },
                    { title: "广告验证投放", text: "固定竞价和关键词组，观察CTR、CVR、ACOS。" },
                    { title: "结果回流", text: "点击满100后回到效果验证和数据回流。" },
                  ].map((item) => (
                    <div key={item.title} className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                      <p className="text-sm font-semibold text-gray-900">{item.title}</p>
                      <p className="text-xs text-gray-600 mt-2 leading-relaxed">{item.text}</p>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {view !== "data-feedback" && view !== "conclusion" && view !== "next-round" && (
            <div className="space-y-4">
              {mockSuggestions.map((item, idx) => (
                <Card key={idx} className="bg-white border-gray-200 p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-500" />
                      <h3 className="text-sm font-semibold text-gray-900">{item.problem}</h3>
                    </div>
                    <Badge className={item.priority === "高" ? "bg-red-50 text-red-600 border-red-200" : "bg-amber-50 text-amber-600 border-amber-200"}>
                      {item.priority}优先
                    </Badge>
                  </div>
                  <p className="text-sm text-gray-600">{item.reason}</p>
                </Card>
              ))}
            </div>
          )}

          {/* Summary */}
          <Card className="bg-white border-gray-200 p-5 mt-6">
            <div className="flex items-center gap-2 mb-3">
              <Lightbulb className="w-4 h-4 text-amber-500" />
              <h3 className="text-sm font-semibold text-gray-900">
                本轮优化总结
              </h3>
            </div>
            <div className="flex flex-wrap gap-3">
              {summaryChips.map((text, i) => (
                <div
                  key={i}
                  className="flex items-center gap-1.5 text-sm text-gray-600 bg-emerald-50 px-3 py-1.5 rounded-full"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  {text}
                </div>
              ))}
            </div>
          </Card>

          <NextStepActions
            currentStep={view === "data-feedback" ? "验证回流" : view === "conclusion" ? "复盘结论" : "下一轮优化"}
            actions={[
              view === "data-feedback"
                ? { label: "查看复盘结论", path: "/optimization-suggestions?view=conclusion", variant: "default" }
                : view === "conclusion"
                  ? { label: "生成下一轮优化", path: "/optimization-suggestions?view=next-round", variant: "default" }
                  : undefined,
            ].filter(Boolean) as { label: string; path: string; variant?: "default" | "outline" }[]}
          />
        </div>
      </main>
    </div>
  );
}
