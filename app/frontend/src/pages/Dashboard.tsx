import { useEffect, useState, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { AppSidebar } from "@/components/AppSidebar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { toast } from "sonner";
import { getApiErrorMessage } from "@/lib/api-retry";
import {
  loadDashboardData,
  getProductStageInfo,
  getTimelineEvents,
  getActionSnapshots,
  type DashboardStats,
  type HealthReport,
  type TimelineEvent,
  type ActionSnapshot,
} from "@/lib/workflow-api";
import { mockAccountPlan, usagePercent, usageWarning } from "@/lib/plan-permissions";
import axios from "axios";
import { getAuthHeaders } from "@/lib/auth-headers";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadarChart as RechartsRadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from "recharts";
import {
  Package,
  ArrowRight,
  RotateCcw,
  Target,
  FileSearch,
  Stethoscope,
  Megaphone,
  CheckCircle2,
  AlertTriangle,
  Zap,
  ChevronRight,
  RefreshCw,
  TrendingUp,
  BarChart3,
  Activity,
  Clock,
  Filter,
  Award,
  Sparkles,
  CreditCard,
  Database,
  Layers3,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  6D Score Types                                                      */
/* ------------------------------------------------------------------ */

interface FiveDHistoryItem {
  id: number;
  asin: string;
  product_title: string;
  total_score: number;
  qualified: boolean;
  dimension_scores: {
    demand: number;
    scenario: number;
    competition: number;
    profit: number;
    trend: number;
    price_tier?: number;
  };
  created_at: string;
}

interface WorkflowChain {
  product?: {
    id?: number;
    asin: string;
    title: string;
  };
  chain_status: "complete" | "partial" | string;
  completed_stages: number;
  total_stages: number;
  integrity_score: number;
  judgment_summary?: {
    standard_key: string;
    decision_ready_count: number;
    learning_ready_count: number;
    blocked_count: number;
    blocked_stages: Array<{
      stage_key: string;
      title: string;
      reason: string;
      next_action: string;
    }>;
  };
  stages: Array<{
    key: string;
    title: string;
    status: "completed" | "missing" | string;
    source_table: string;
    source_id?: number | null;
    score?: number | null;
    summary?: string;
    next_action?: string;
    evidence_meta?: {
      data_source: string;
      source_type: string;
      source_ref: string;
      confidence: string;
      confidence_reason: string;
      judgment_basis: string;
      ai_role: string;
      ai_used: boolean;
      ai_status: string;
    };
    judgment_gate?: {
      standard_key: string;
      evidence_tier: string;
      can_influence_final_decision: boolean;
      can_enter_learning_memory: boolean;
      judgment_status: string;
      blocking_reason: string;
      required_next_action: string;
      rules_applied: string[];
    };
  }>;
  agent_decision?: {
    mode: string;
    chief_decision: {
      current_stage: string;
      decision: string;
      why: string;
      next_action: string;
      risk_if_ignored: string;
      confidence: string;
    };
    error_evidence_cards: Array<{
      id: string;
      error: string;
      source_type: string;
      source_table: string;
      source_id?: number | null;
      evidence: string;
      impact_area: string;
      confidence: string;
      evidence_strength: {
        score: number;
        level: string;
      };
      priority: {
        score: number;
        level: string;
        reason: string;
      };
      suggested_action: string;
      validation_hypothesis_id: string;
    }>;
    action_priority: Array<{
      rank: number;
      level: string;
      score: number;
      action: string;
      source_evidence_id: string;
      expected_impact: string;
      validation_hypothesis_id: string;
      difficulty: string;
      verification_cost: string;
    }>;
    validation_hypotheses: Array<{
      id: string;
      hypothesis: string;
      basis: string;
      listing_action: string;
      ad_test_keywords: string[];
      match_types: string[];
      budget_rule: string;
      observation_window: string;
      success_metrics: string[];
    }>;
    hit_rate_learning: {
      status: string;
      hit_rate: number;
      basis: string;
      reusable_learning: string;
      next_iteration: string;
      likely_failure_reason: string;
      binding_candidates?: Array<{
        keyword_group_id?: string;
        optimization_round?: number;
        keywords: string[];
        metrics: {
          impressions?: number;
          clicks?: number;
          spend?: number;
          orders?: number;
          sales?: number;
          ctr?: number;
          cvr?: number;
          acos?: number;
        };
        record_count: number;
        required_action: string;
      }>;
    };
    listing_version_contract: {
      current_round: number;
      next_snapshot_timing: string;
      required_fields: string[];
    };
  };
}

type AdBindingCandidate = NonNullable<
  NonNullable<WorkflowChain["agent_decision"]>["hit_rate_learning"]["binding_candidates"]
>[number];

const EMPTY_CHIEF_DECISION: NonNullable<WorkflowChain["agent_decision"]>["chief_decision"] = {
  current_stage: "今日决策",
  decision: "暂无完整闭环决策",
  why: "系统还在等待各模块数据回流。",
  next_action: "先完成选品、诊断或广告验证中的任一模块。",
  risk_if_ignored: "暂无",
  confidence: "低",
};

const EMPTY_HIT_RATE_LEARNING: NonNullable<WorkflowChain["agent_decision"]>["hit_rate_learning"] = {
  status: "暂无验证",
  hit_rate: 0,
  basis: "完成广告验证后会自动回流命中率。",
  reusable_learning: "暂无可复用结论。",
  next_iteration: "等待下一轮优化。",
  likely_failure_reason: "暂无",
  binding_candidates: [],
};

const EMPTY_LISTING_VERSION_CONTRACT: NonNullable<WorkflowChain["agent_decision"]>["listing_version_contract"] = {
  current_round: 1,
  next_snapshot_timing: "完成诊断后保存版本快照",
  required_fields: [],
};

function normalizeWorkflowChain(raw: WorkflowChain | null | undefined): WorkflowChain | null {
  if (!raw) return null;
  if (typeof raw !== "object" || Array.isArray(raw)) return null;
  const agentDecision = raw.agent_decision
    ? {
        ...raw.agent_decision,
        chief_decision: raw.agent_decision.chief_decision || EMPTY_CHIEF_DECISION,
        error_evidence_cards: Array.isArray(raw.agent_decision.error_evidence_cards)
          ? raw.agent_decision.error_evidence_cards
          : [],
        action_priority: Array.isArray(raw.agent_decision.action_priority)
          ? raw.agent_decision.action_priority
          : [],
        validation_hypotheses: Array.isArray(raw.agent_decision.validation_hypotheses)
          ? raw.agent_decision.validation_hypotheses
          : [],
        hit_rate_learning: {
          ...EMPTY_HIT_RATE_LEARNING,
          ...(raw.agent_decision.hit_rate_learning || {}),
          binding_candidates: Array.isArray(raw.agent_decision.hit_rate_learning?.binding_candidates)
            ? raw.agent_decision.hit_rate_learning.binding_candidates
            : [],
        },
        listing_version_contract:
          raw.agent_decision.listing_version_contract || EMPTY_LISTING_VERSION_CONTRACT,
      }
    : undefined;

  return {
    ...raw,
    stages: Array.isArray(raw.stages) ? raw.stages : [],
    agent_decision: agentDecision,
  };
}

/* ------------------------------------------------------------------ */
/*  5-Step Cycle Data                                                   */
/* ------------------------------------------------------------------ */

const CYCLE_STEPS = [
  {
    id: 1,
    label: "选品决策",
    desc: "先判断ASIN是否值得进入测试池",
    icon: Target,
    color: "bg-brand-600",
    textColor: "text-brand-600",
    borderColor: "border-brand-200",
    bgLight: "bg-brand-50",
    path: "/asin-manager",
    stepName: "机会判断",
    dotColor: "#0f2a24",
  },
  {
    id: 2,
    label: "上新检测",
    desc: "上架前补齐Listing基础表达",
    icon: FileSearch,
    color: "bg-teal-600",
    textColor: "text-teal-600",
    borderColor: "border-teal-200",
    bgLight: "bg-teal-50",
    path: "/listing-launch-check",
    stepName: "Listing上新检测",
    dotColor: "#0d9488",
  },
  {
    id: 3,
    label: "本品诊断",
    desc: "生成Listing问题和广告验证假设",
    icon: Stethoscope,
    color: "bg-emerald-600",
    textColor: "text-emerald-600",
    borderColor: "border-emerald-200",
    bgLight: "bg-emerald-50",
    path: "/listing-diagnosis",
    stepName: "本品诊断",
    dotColor: "#059669",
  },
  {
    id: 4,
    label: "广告验证",
    desc: "用CTR、CVR、ACOS验证假设",
    icon: Stethoscope,
    color: "bg-teal-600",
    textColor: "text-teal-600",
    borderColor: "border-teal-200",
    bgLight: "bg-teal-50",
    path: "/ad-analytics?view=validation",
    stepName: "效果验证",
    dotColor: "#0d9488",
  },
  {
    id: 5,
    label: "数据回流",
    desc: "回流命中结果并生成下一轮动作",
    icon: Megaphone,
    color: "bg-amber-600",
    textColor: "text-amber-600",
    borderColor: "border-amber-200",
    bgLight: "bg-amber-50",
    path: "/optimization-suggestions?view=conclusion",
    stepName: "复盘结论",
    dotColor: "#d97706",
  },
];

const NAV_CYCLE_STEPS = [
  {
    id: 1,
    label: "选品决策",
    desc: "先判断ASIN是否值得进入测试池",
    icon: Target,
    color: "bg-brand-600",
    textColor: "text-brand-600",
    borderColor: "border-brand-200",
    bgLight: "bg-brand-50",
    path: "/asin-manager",
  },
  {
    id: 2,
    label: "上新检测",
    desc: "上架前补齐Listing基础表达",
    icon: FileSearch,
    color: "bg-teal-600",
    textColor: "text-teal-600",
    borderColor: "border-teal-200",
    bgLight: "bg-teal-50",
    path: "/listing-launch-check",
  },
  {
    id: 3,
    label: "本品诊断",
    desc: "生成Listing问题和广告验证假设",
    icon: Stethoscope,
    color: "bg-emerald-600",
    textColor: "text-emerald-600",
    borderColor: "border-emerald-200",
    bgLight: "bg-emerald-50",
    path: "/listing-diagnosis",
  },
  {
    id: 4,
    label: "广告验证",
    desc: "用真实广告流量验证诊断假设",
    icon: Megaphone,
    color: "bg-amber-600",
    textColor: "text-amber-600",
    borderColor: "border-amber-200",
    bgLight: "bg-amber-50",
    path: "/ad-analytics?view=validation",
  },
  {
    id: 5,
    label: "数据回流",
    desc: "验证结果回流系统，启动下一轮",
    icon: RotateCcw,
    color: "bg-gold-600",
    textColor: "text-gold-600",
    borderColor: "border-gold-200",
    bgLight: "bg-gold-50",
    path: "/optimization-suggestions?view=next-round",
  },
];

const FEEDBACK_ICONS: Record<string, typeof RefreshCw> = {
  cosmo: TrendingUp,
  listing: BarChart3,
  ad: Activity,
};

const FEEDBACK_COLORS: Record<string, string> = {
  cosmo: "text-brand-600",
  listing: "text-emerald-600",
  ad: "text-amber-600",
};

const STEP_COLOR_MAP: Record<string, { bg: string; text: string; dot: string }> = {
  "选品决策": { bg: "bg-brand-100", text: "text-brand-700", dot: "#0f2a24" },
  "Listing上新检测": { bg: "bg-teal-100", text: "text-teal-700", dot: "#0d9488" },
  "本品诊断": { bg: "bg-emerald-100", text: "text-emerald-700", dot: "#059669" },
  "广告验证": { bg: "bg-amber-100", text: "text-amber-700", dot: "#d97706" },
  "数据回流": { bg: "bg-gold-100", text: "text-gold-700", dot: "#c6a86e" },
};

const STEP_ICON_MAP: Record<string, typeof Target> = {
  "选品决策": Target,
  "Listing上新检测": FileSearch,
  "本品诊断": Stethoscope,
  "广告验证": Megaphone,
  "数据回流": RotateCcw,
};

/* ------------------------------------------------------------------ */
/*  Mini Radar (SVG) for 6D scores                                     */
/* ------------------------------------------------------------------ */

function MiniRadar({
  scores,
  size = 100,
}: {
  scores: { demand: number; scenario: number; competition: number; profit: number; trend: number };
  size?: number;
}) {
  const cx = size / 2;
  const cy = size / 2;
  const maxR = size * 0.38;
  const dims = ["demand", "scenario", "competition", "profit", "trend"] as const;
  const angleStep = (2 * Math.PI) / 5;
  const startAngle = -Math.PI / 2;

  const getPoint = (dimIndex: number, value: number) => {
    const angle = startAngle + dimIndex * angleStep;
    const r = (value / 20) * maxR;
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  };

  // Grid
  const gridPath = [4, 8, 12, 16, 20].map((level) => {
    const points = dims.map((_, i) => getPoint(i, level));
    return points.map((p, i) => (i === 0 ? `M${p.x},${p.y}` : `L${p.x},${p.y}`)).join(" ") + "Z";
  });

  // Data
  const dataPoints = dims.map((d, i) => getPoint(i, scores[d] || 0));
  const dataPath =
    dataPoints.map((p, i) => (i === 0 ? `M${p.x},${p.y}` : `L${p.x},${p.y}`)).join(" ") + "Z";

  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
      {gridPath.map((d, i) => (
        <path key={i} d={d} fill="none" stroke="#e5e7eb" strokeWidth="0.5" />
      ))}
      {dims.map((_, i) => {
        const end = getPoint(i, 20);
        return <line key={i} x1={cx} y1={cy} x2={end.x} y2={end.y} stroke="#e5e7eb" strokeWidth="0.5" />;
      })}
      <path d={dataPath} fill="rgba(15,42,36,0.18)" stroke="#0f2a24" strokeWidth="1.5" />
      {dataPoints.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="2" fill="#0f2a24" />
      ))}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function Dashboard() {
  const navigate = useNavigate();
  const { loading: authLoading } = useRequireAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeStep, setActiveStep] = useState(1);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(true);
  const [selectedProductId, setSelectedProductId] = useState<number>(0);
  const [workflowChain, setWorkflowChain] = useState<WorkflowChain | null>(null);
  const [bindingKey, setBindingKey] = useState("");

  const goTo = (path: string) => {
    if (path.includes("?")) {
      window.location.assign(path);
      return;
    }
    navigate(path);
  };

  // 6D score data
  const [fiveDItems, setFiveDItems] = useState<FiveDHistoryItem[]>([]);
  const [fiveDLoading, setFiveDLoading] = useState(true);
  const [snapshots, setSnapshots] = useState<ActionSnapshot[]>([]);
  const [snapshotLoading, setSnapshotLoading] = useState(true);

  useEffect(() => {
    if (!authLoading) {
      loadData();
      loadTimeline();
      loadFiveDScores();
      loadWorkflowChain();
      loadSnapshots();
    }
  }, [authLoading]);

  useEffect(() => {
    if (!authLoading) loadTimeline();
  }, [selectedProductId]);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await loadDashboardData();
      setStats(data);
    } catch (e) {
      console.error("Failed to load dashboard data:", e);
      toast.error(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const loadTimeline = async () => {
    setTimelineLoading(true);
    try {
      const events = await getTimelineEvents(selectedProductId || undefined);
      setTimelineEvents(events);
    } catch (e) {
      console.error("Failed to load timeline:", e);
    } finally {
      setTimelineLoading(false);
    }
  };

  const loadWorkflowChain = async () => {
    try {
      const res = await axios.get("/api/v1/workflow-chain/current", {
        headers: getAuthHeaders(),
      });
      setWorkflowChain(normalizeWorkflowChain(res.data));
    } catch {
      setWorkflowChain(null);
    }
  };

  const bindHypothesis = async (
    candidate: AdBindingCandidate,
    hypothesisId: string
  ) => {
    const productId = workflowChain?.product?.id;
    if (!productId) {
      toast.error("当前商品缺少 product_id，无法绑定广告假设");
      return;
    }
    const key = `${candidate.keyword_group_id || "default"}-${candidate.optimization_round || 1}-${hypothesisId}`;
    setBindingKey(key);
    try {
      const res = await axios.post(
        "/api/v1/entities/ad_data/bind-hypothesis",
        {
          product_id: productId,
          hypothesis_id: hypothesisId,
          keyword_group_id: candidate.keyword_group_id,
          optimization_round: candidate.optimization_round,
          only_unassigned: true,
        },
        { headers: getAuthHeaders() }
      );
      const count = res.data?.updated_count || 0;
      toast.success(`已绑定 ${count} 条广告记录`);
      await loadWorkflowChain();
    } catch (e) {
      toast.error(getApiErrorMessage(e));
    } finally {
      setBindingKey("");
    }
  };

  const loadFiveDScores = useCallback(async () => {
    setFiveDLoading(true);
    try {
      const res = await axios.get("/api/v1/asin-analysis/six-dimension-history?limit=200", {
        headers: getAuthHeaders(),
      });
      const items: FiveDHistoryItem[] = res.data?.items || [];
      // Deduplicate: keep latest per ASIN
      const map = new Map<string, FiveDHistoryItem>();
      for (const item of items) {
        if (!map.has(item.asin)) {
          map.set(item.asin, item);
        }
      }
      setFiveDItems(Array.from(map.values()));
    } catch {
      // Silently fail
    } finally {
      setFiveDLoading(false);
    }
  }, []);

  const loadSnapshots = useCallback(async () => {
    setSnapshotLoading(true);
    try {
      setSnapshots(await getActionSnapshots({ limit: 12 }));
    } finally {
      setSnapshotLoading(false);
    }
  }, []);

  const totalProducts = stats?.totalProducts || 0;
  const needOptimization = stats?.needOptimization || 0;
  const verifyingCount = stats?.verifyingCount || 0;
  const completedRounds = stats?.completedRounds || 0;
  const products = stats?.products || [];
  const healthReports = (stats?.healthReports || []) as HealthReport[];
  const suggestions = stats?.suggestions || [];
  const feedbackItems = stats?.feedbackItems || [];
  const accountUsage = Array.isArray(mockAccountPlan.usage) ? mockAccountPlan.usage : [];
  const workflowStages = workflowChain?.stages || [];
  const agentDecision = workflowChain?.agent_decision;
  const errorEvidenceCards = agentDecision?.error_evidence_cards || [];
  const validationHypotheses = agentDecision?.validation_hypotheses || [];
  const actionPriority = agentDecision?.action_priority || [];
  const chiefDecision = agentDecision?.chief_decision || EMPTY_CHIEF_DECISION;
  const hitRateLearning = agentDecision?.hit_rate_learning || EMPTY_HIT_RATE_LEARNING;
  const bindingCandidates = hitRateLearning.binding_candidates || [];
  const judgmentSummary = workflowChain?.judgment_summary;
  const listingVersionContract = agentDecision?.listing_version_contract || EMPTY_LISTING_VERSION_CONTRACT;

  // 6D derived data
  const qualifiedItems = fiveDItems.filter((i) => i.qualified);
  const pendingItems = fiveDItems.filter((i) => !i.qualified);
  const avgScore =
    fiveDItems.length > 0
      ? Math.round(fiveDItems.reduce((s, i) => s + i.total_score, 0) / fiveDItems.length)
      : 0;

  /* Build chart data: group timeline events by optimization_round, pick listing_score */
  const chartData = useMemo(() => {
    const scoreEvents = timelineEvents.filter((e) => e.listing_score > 0);
    const roundMap = new Map<number, number>();
    for (const ev of scoreEvents) {
      const round = ev.optimization_round || 1;
      const existing = roundMap.get(round);
      if (!existing || ev.listing_score > existing) {
        roundMap.set(round, ev.listing_score);
      }
    }
    const entries = Array.from(roundMap.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([round, score]) => ({ round: `第${round}轮`, score }));
    return entries;
  }, [timelineEvents]);

  /* Sort timeline events by timestamp descending for display */
  const sortedTimeline = useMemo(() => {
    return [...timelineEvents].sort(
      (a, b) =>
        new Date(b.action_timestamp).getTime() -
        new Date(a.action_timestamp).getTime()
    );
  }, [timelineEvents]);

  /* 6D Radar chart data for recharts (aggregated average) */
  const fiveDRadarData = useMemo(() => {
    if (fiveDItems.length === 0) return [];
    const dims = ["demand", "scenario", "competition", "profit", "trend", "price_tier"] as const;
    const labels = { demand: "需求", scenario: "场景", competition: "竞争", profit: "利润", trend: "趋势", price_tier: "价格带" };
    return dims.map((d) => ({
      dimension: labels[d],
      value: Math.round(
        fiveDItems.reduce((s, i) => s + (i.dimension_scores?.[d] || 0), 0) / fiveDItems.length
      ),
      fullMark: 20,
    }));
  }, [fiveDItems]);

  const modulePriorityBoard = useMemo(() => {
    const topAction = actionPriority[0];
    const hitLearning = hitRateLearning;
    const chief = agentDecision?.chief_decision;
    const stages = new Map(workflowStages.map((stage) => [stage.key, stage]));
    const adGate = stages.get("ad_validation")?.judgment_gate;
    const reviewGate = stages.get("review")?.judgment_gate;
    const adBlocked = Boolean(adGate?.blocking_reason);
    const reviewBlocked = Boolean(reviewGate?.blocking_reason);
    const feedbackReady = Boolean(reviewGate?.can_enter_learning_memory || hitLearning?.status === "已命中");

    const firstAction = adBlocked || adGate?.judgment_status === "pending_sample"
      ? {
          rank: 1,
          module: "先守住广告预算",
          priority: "P0",
          status: adGate?.judgment_status === "unattributed" ? "先别判成败" : "先别放量",
          evidence: adGate?.blocking_reason || adGate?.required_next_action || "广告样本还不够，现在放大预算容易把偶然波动当成结论。",
          action: adGate?.judgment_status === "unattributed" ? "先绑定假设" : "继续跑到100点击",
          path: adGate?.judgment_status === "unattributed" ? "/ad-analytics?view=records" : "/ad-analytics?view=validation",
          icon: Megaphone,
          color: "amber",
        }
      : {
          rank: 1,
          module: "复盘这轮钱",
          priority: feedbackReady ? "P0" : "P1",
          status: feedbackReady ? "马上沉淀经验" : reviewBlocked ? "先补复盘记录" : "等广告验证",
          evidence: reviewGate?.blocking_reason || hitLearning?.basis || "只有把命中/未命中写回系统，下一轮才知道该放量、停词还是回Listing改承接。",
          action: reviewBlocked ? "补齐复盘记录" : "复盘命中原因",
          path: "/optimization-suggestions?view=data-feedback",
          icon: Database,
          color: "emerald",
        };

    return [
      firstAction,
      {
        rank: 2,
        module: "回Listing改承接",
        priority: topAction?.level || "P1",
        status: chief?.current_stage?.includes("复盘") ? "按复盘修正" : "先找转化卡点",
        evidence: topAction?.action || "先找出标题、主图、五点、A+里哪个环节拖累点击或转化，再决定要不要投广告验证。",
        action: "找出先改哪里",
        path: "/listing-diagnosis",
        icon: Stethoscope,
        color: "blue",
      },
      {
        rank: 3,
        module: "用广告验证改动",
        priority: adBlocked ? "P0" : "P1",
        status: adBlocked ? "先补条件" : stages.get("ad_validation")?.status === "completed" ? "可复盘" : "等数据",
        evidence: adGate?.blocking_reason || validationHypotheses[0]?.hypothesis || "Listing判断必须用真实点击、转化和ACOS验证，避免凭感觉改页面。",
        action: adBlocked ? adGate?.required_next_action || "补齐广告数据" : stages.get("ad_validation")?.status === "completed" ? "看能否放量" : "录入广告数据",
        path: adGate?.judgment_status === "unattributed" ? "/ad-analytics?view=records" : "/ad-analytics?view=validation",
        icon: Megaphone,
        color: "amber",
      },
      {
        rank: 4,
        module: "确认ASIN值不值得测",
        priority: "P2",
        status: stages.get("selection")?.status === "completed" ? "已进机会池" : "先别投入",
        evidence: stages.get("selection")?.summary || "先判断这个ASIN有没有需求、利润和竞争空间，再决定是否继续投入Listing和广告预算。",
        action: "看是否值得测",
        path: "/asin-manager",
        icon: Layers3,
        color: "indigo",
      },
    ];
  }, [actionPriority, agentDecision?.chief_decision, hitRateLearning, validationHypotheses, workflowStages]);

  const confidenceBadgeClass = (level?: string) => {
    if (level === "高") return "bg-emerald-50 text-emerald-700 border-emerald-200";
    if (level === "中") return "bg-amber-50 text-amber-700 border-amber-200";
    return "bg-red-50 text-red-600 border-red-200";
  };

  const statCards = [
    {
      label: "当前分析商品数",
      value: totalProducts,
      icon: Package,
      color: "text-brand-600",
      bgColor: "bg-brand-50",
    },
    {
      label: "机会池产品",
      value: qualifiedItems.length,
      icon: Award,
      color: "text-emerald-600",
      bgColor: "bg-emerald-50",
    },
    {
      label: "正在验证策略数",
      value: verifyingCount,
      icon: Megaphone,
      color: "text-teal-600",
      bgColor: "bg-teal-50",
    },
    {
      label: "已完成优化轮次",
      value: completedRounds,
      icon: CheckCircle2,
      color: "text-gold-600",
      bgColor: "bg-gold-50",
    },
  ];

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto pt-14 md:pt-6">
          {/* Hero Header */}
          <div className="mb-8">
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
              今天先做哪件事能赚钱或止损
            </h1>
            <p className="text-gray-500 mt-2 text-sm sm:text-base max-w-3xl">
              先找最该处理的ASIN、Listing或广告动作，再用真实点击和订单验证，避免凭感觉烧预算。
            </p>
          </div>

          <Card className="bg-white border-gray-200 p-4 sm:p-5 mb-6">
            <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center flex-shrink-0">
                  <CreditCard className="w-5 h-5 text-brand-600" />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-semibold text-gray-900">当前套餐与用量：{mockAccountPlan.planName}</p>
                    <Badge className="bg-amber-50 text-amber-700 border-amber-200">{mockAccountPlan.statusLabel}</Badge>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    到期时间 {mockAccountPlan.expiresAt}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="bg-white border-gray-200"
                  onClick={() => navigate("/settings")}
                >
                  账号中心
                </Button>
                <Button
                  className="bg-brand-600 hover:bg-brand-500 text-white"
                  onClick={() => navigate("/pricing")}
                >
                  升级套餐
                </Button>
              </div>
            </div>
            <div className="grid md:grid-cols-5 gap-3 mt-4">
              {accountUsage.map((item) => {
                const percent = usagePercent(item);
                const warning = usageWarning(item);
                return (
                  <div key={item.key} className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[11px] text-gray-500">{item.label}</p>
                      {warning && (
                        <span className={percent >= 100 ? "text-[10px] text-red-600" : "text-[10px] text-amber-600"}>
                          {warning}
                        </span>
                      )}
                    </div>
                    <p className="text-sm font-bold text-gray-900 mt-1">{item.used} / {item.total}</p>
                    <Progress value={percent} className="h-1.5 mt-2" />
                  </div>
                );
              })}
            </div>
          </Card>

          <Card className="bg-white border-gray-200 p-5 sm:p-6 mb-8">
            <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 mb-5">
              <div>
                <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                  <Target className="w-4.5 h-4.5 text-brand-600" />
                  今日运营指令
                </h2>
                <p className="text-xs text-gray-500 mt-1">
                  先处理 P0：该停词就停词，该补样本就补样本，该回Listing改承接就先改承接。
                </p>
              </div>
              {agentDecision && (
                <Badge className="bg-brand-50 text-brand-700 border-brand-200">
                  当前阶段：{chiefDecision.current_stage}
                </Badge>
              )}
            </div>

            <div className="grid lg:grid-cols-4 gap-3">
              {modulePriorityBoard.map((item) => (
                <div key={item.module} className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-white border border-gray-200 flex items-center justify-center">
                        <item.icon className="w-4 h-4 text-gray-700" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{item.module}</p>
                        <p className="text-[11px] text-gray-500">{item.status}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <Badge className={item.priority === "P0" ? "bg-red-50 text-red-600 border-red-200" : "bg-amber-50 text-amber-700 border-amber-200"}>
                        {item.priority}
                      </Badge>
                      <p className="text-[10px] text-gray-400 mt-1">#{item.rank}</p>
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 leading-relaxed min-h-[48px]">{item.evidence}</p>
                  <Button asChild size="sm" variant="outline" className="mt-4 w-full bg-white border-gray-200 text-gray-700 hover:bg-brand-50 hover:text-brand-700">
                    <a href={item.path}>
                      {item.action}
                      <ArrowRight className="w-3.5 h-3.5 ml-1" />
                    </a>
                  </Button>
                </div>
              ))}
            </div>
          </Card>

          {workflowChain && (
            <Card className="bg-white border-gray-200 p-5 sm:p-6 mb-8">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-5">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center flex-shrink-0">
                    <Database className="w-5 h-5 text-emerald-600" />
                  </div>
                  <div>
                    <h2 className="text-base font-semibold text-gray-900">闭环数据状态</h2>
                    <p className="text-xs text-gray-500 mt-1">
                      {workflowChain.product?.asin} · {workflowChain.product?.title}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className={workflowChain.chain_status === "complete" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-amber-50 text-amber-700 border-amber-200"}>
                    完整度 {workflowChain.integrity_score}%
                  </Badge>
                  <span className="text-xs text-gray-500">
                    {workflowChain.completed_stages}/{workflowChain.total_stages} 阶段已贯通
                  </span>
                </div>
              </div>
              {judgmentSummary && (
                <div className="mb-4 grid gap-3 md:grid-cols-3">
                  <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-3">
                    <p className="text-[11px] font-semibold text-emerald-700">可参与最终判断</p>
                    <p className="mt-1 text-2xl font-bold text-emerald-800">{judgmentSummary.decision_ready_count}</p>
                  </div>
                  <div className="rounded-lg border border-teal-100 bg-teal-50 p-3">
                    <p className="text-[11px] font-semibold text-teal-700">可进入学习记忆</p>
                    <p className="mt-1 text-2xl font-bold text-teal-800">{judgmentSummary.learning_ready_count}</p>
                  </div>
                  <div className="rounded-lg border border-amber-100 bg-amber-50 p-3">
                    <p className="text-[11px] font-semibold text-amber-700">阻塞节点</p>
                    <p className="mt-1 text-2xl font-bold text-amber-800">{judgmentSummary.blocked_count}</p>
                  </div>
                </div>
              )}
              <div className="grid md:grid-cols-6 gap-3">
                {workflowStages.map((stage) => (
                  <div key={stage.key} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <p className="text-xs font-semibold text-gray-700">{stage.title}</p>
                      <span className={`w-2 h-2 rounded-full ${stage.status === "completed" ? "bg-emerald-500" : "bg-gray-300"}`} />
                    </div>
                    <p className="text-[11px] text-gray-500 line-clamp-2">{stage.summary || "暂无数据"}</p>
                    <div className="mt-3 space-y-2">
                      <div className="flex flex-wrap gap-1.5">
                        <Badge variant="outline" className={confidenceBadgeClass(stage.evidence_meta?.confidence)}>
                          置信度 {stage.evidence_meta?.confidence || "低"}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={
                            stage.judgment_gate?.can_influence_final_decision
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                              : "bg-amber-50 text-amber-700 border-amber-200"
                          }
                        >
                          {stage.judgment_gate?.judgment_status || "missing"}
                        </Badge>
                        <Badge variant="outline" className="bg-white text-gray-600 border-gray-200">
                          {stage.evidence_meta?.ai_used ? "已生成" : "结构判断"}
                        </Badge>
                      </div>
                      <p className="text-[10px] text-gray-500 leading-relaxed">
                        来源：{stage.evidence_meta?.data_source || stage.source_table}
                      </p>
                      <p className="text-[10px] text-gray-500 leading-relaxed line-clamp-3">
                        依据：{stage.evidence_meta?.judgment_basis || stage.summary || "暂无判断依据"}
                      </p>
                      <p className="text-[10px] text-gray-400">
                        {stage.evidence_meta?.source_ref || `${stage.source_table}${stage.source_id ? ` #${stage.source_id}` : ""}`}
                      </p>
                      {stage.judgment_gate?.blocking_reason && (
                        <div className="rounded-md border border-amber-100 bg-amber-50 p-2 text-[10px] leading-relaxed text-amber-800">
                          {stage.judgment_gate.blocking_reason}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <p className="text-sm font-semibold text-gray-900">数据来源与判断可信度</p>
                  <span className="text-[11px] text-gray-500">每个节点都必须说明来源、依据和置信度</span>
                </div>
                <div className="grid md:grid-cols-3 gap-3">
                  {workflowStages.slice(0, 6).map((stage) => (
                    <div key={`${stage.key}-evidence`} className="rounded-md bg-white border border-gray-200 p-3">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-xs font-semibold text-gray-800">{stage.title}</p>
                        <Badge variant="outline" className={confidenceBadgeClass(stage.evidence_meta?.confidence)}>
                          {stage.evidence_meta?.confidence || "低"}
                        </Badge>
                      </div>
                      <p className="mt-2 text-[11px] text-gray-500 leading-relaxed">
                        数据来源：{stage.evidence_meta?.data_source}
                      </p>
                      <p className="mt-1 text-[11px] text-gray-600 leading-relaxed">
                        判断依据：{stage.evidence_meta?.judgment_basis}
                      </p>
                      <p className="mt-2 text-[10px] text-gray-400 leading-relaxed">
                        {stage.evidence_meta?.confidence_reason}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {agentDecision && (
                <div className="mt-5 border-t border-gray-100 pt-5">
                  <div className="grid lg:grid-cols-[1.1fr_1.4fr] gap-4">
                    <div className="rounded-lg border border-brand-100 bg-brand-50/60 p-4">
                      <div className="flex items-center justify-between gap-3 mb-3">
                        <div>
                          <p className="text-xs font-semibold text-brand-600">总决策 Agent</p>
                          <h3 className="text-lg font-bold text-gray-900 mt-1">
                            {chiefDecision.decision}
                          </h3>
                        </div>
                        <Badge className="bg-white text-brand-700 border-brand-200">
                          置信度 {chiefDecision.confidence}
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-700 leading-relaxed">
                        {chiefDecision.why}
                      </p>
                      <div className="mt-4 rounded-md bg-white border border-brand-100 p-3">
                        <p className="text-xs font-semibold text-gray-500 mb-1">下一步动作</p>
                        <p className="text-sm text-gray-800">
                          {chiefDecision.next_action}
                        </p>
                      </div>
                    </div>

                    <div className="grid sm:grid-cols-2 gap-3">
                        {errorEvidenceCards.slice(0, 2).map((card) => (
                        <div key={card.id} className="rounded-lg border border-gray-200 bg-white p-4">
                          <div className="flex items-start justify-between gap-2 mb-2">
                            <p className="text-sm font-semibold text-gray-900">{card.error}</p>
                            <div className="flex flex-col items-end gap-1">
                              <Badge variant="outline" className="text-[10px] border-amber-200 text-amber-700 bg-amber-50">
                                {card.priority.level}
                              </Badge>
                              <span className="text-[10px] text-gray-400">证据{card.evidence_strength.level} {card.evidence_strength.score}</span>
                            </div>
                          </div>
                          <p className="text-xs text-gray-500 leading-relaxed">{card.evidence}</p>
                          <p className="text-xs text-gray-800 mt-3 leading-relaxed">{card.suggested_action}</p>
                          <p className="text-[10px] text-gray-400 mt-3">
                            来源：{card.source_table}{card.source_id ? ` #${card.source_id}` : ""}
                          </p>
                        </div>
                      ))}

                      {validationHypotheses.slice(0, 1).map((hypothesis) => (
                        <div key={hypothesis.id} className="rounded-lg border border-gray-200 bg-white p-4">
                          <p className="text-xs font-semibold text-teal-600 mb-1">广告验证假设</p>
                          <p className="text-sm font-semibold text-gray-900">{hypothesis.hypothesis}</p>
                          <p className="text-xs text-gray-500 mt-2 leading-relaxed">{hypothesis.listing_action}</p>
                          <div className="flex flex-wrap gap-1.5 mt-3">
                            {(hypothesis.ad_test_keywords || []).slice(0, 3).map((keyword) => (
                              <span key={keyword} className="px-2 py-1 rounded-md bg-teal-50 text-teal-700 text-[10px]">
                                {keyword}
                              </span>
                            ))}
                          </div>
                          <p className="text-[10px] text-gray-400 mt-3">{hypothesis.budget_rule}</p>
                          <p className="text-[10px] text-gray-400 mt-1">{hypothesis.observation_window}</p>
                        </div>
                      ))}

                      <div className="rounded-lg border border-gray-200 bg-white p-4">
                        <p className="text-xs font-semibold text-gold-600 mb-1">命中率回流</p>
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-semibold text-gray-900">
                            {hitRateLearning.status}
                          </p>
                          <span className="text-2xl font-bold text-gold-700">
                            {hitRateLearning.hit_rate}%
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-2 leading-relaxed">
                          {hitRateLearning.basis}
                        </p>
                        <p className="text-xs text-gray-800 mt-3 leading-relaxed">
                          {hitRateLearning.reusable_learning}
                        </p>
                      </div>
                    </div>
                  </div>
                  {bindingCandidates.length > 0 && validationHypotheses.length > 0 && (
                    <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
                      <div className="mb-3 flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-amber-900">广告验证需要绑定诊断假设</p>
                          <p className="mt-1 text-xs leading-relaxed text-amber-700">
                            未绑定的广告数据只能算未归因流量，不能用于判断诊断命中或失败。
                          </p>
                        </div>
                        <Badge className="bg-white text-amber-700 border-amber-200">
                          {bindingCandidates.length} 组待绑定
                        </Badge>
                      </div>
                      <div className="space-y-3">
                        {bindingCandidates.slice(0, 3).map((candidate) => {
                          const candidateKey = `${candidate.keyword_group_id || "default"}-${candidate.optimization_round || 1}`;
                          return (
                            <div key={candidateKey} className="rounded-md border border-amber-100 bg-white p-3">
                              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                <div>
                                  <p className="text-xs font-semibold text-gray-900">
                                    {candidate.keyword_group_id || "default"} · 第 {candidate.optimization_round || 1} 轮
                                  </p>
                                  <p className="mt-1 text-[11px] text-gray-500">
                                    {candidate.record_count} 条记录 · 点击 {candidate.metrics?.clicks || 0} · CVR {candidate.metrics?.cvr || 0}% · ACOS {candidate.metrics?.acos || 0}%
                                  </p>
                                  <div className="mt-2 flex flex-wrap gap-1.5">
                                    {(candidate.keywords || []).slice(0, 4).map((keyword) => (
                                      <span key={keyword} className="rounded-md bg-gray-100 px-2 py-1 text-[10px] text-gray-600">
                                        {keyword}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                                <div className="flex flex-wrap gap-2 lg:justify-end">
                                  {validationHypotheses.slice(0, 3).map((hypothesis) => {
                                    const key = `${candidateKey}-${hypothesis.id}`;
                                    return (
                                      <Button
                                        key={hypothesis.id}
                                        size="sm"
                                        variant="outline"
                                        className="bg-white border-amber-200 text-amber-800 hover:bg-amber-100"
                                        disabled={bindingKey === key}
                                        onClick={() => void bindHypothesis(candidate, hypothesis.id)}
                                      >
                                        {bindingKey === key ? "绑定中..." : `绑定 ${hypothesis.id}`}
                                      </Button>
                                    );
                                  })}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  {actionPriority.length > 0 && (
                    <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-4">
                      <div className="flex items-center justify-between gap-3 mb-3">
                        <p className="text-sm font-semibold text-gray-900">优先动作排序</p>
                        <span className="text-[11px] text-gray-500">
                          第 {listingVersionContract.current_round} 轮优化需保存前后版本
                        </span>
                      </div>
                      <div className="grid md:grid-cols-2 gap-3">
                        {actionPriority.slice(0, 4).map((item) => (
                          <div key={item.source_evidence_id} className="rounded-md bg-white border border-gray-200 p-3">
                            <div className="flex items-center gap-2 mb-2">
                              <Badge className="bg-gray-900 text-white border-gray-900">#{item.rank}</Badge>
                              <Badge variant="outline" className="border-brand-200 text-brand-700 bg-brand-50">
                                {item.level} · {item.score}
                              </Badge>
                              <span className="text-[10px] text-gray-400">
                                难度{item.difficulty} · 验证成本{item.verification_cost}
                              </span>
                            </div>
                            <p className="text-xs text-gray-800 leading-relaxed">{item.action}</p>
                          </div>
                        ))}
                      </div>
                      <p className="text-[11px] text-gray-400 mt-3">
                        版本记录：{listingVersionContract.next_snapshot_timing}
                      </p>
                    </div>
                  )}
                  <p className="text-[11px] text-gray-400 mt-3">
                    当前为结构化决策流程，部分智能诊断能力会逐步开放。
                  </p>
                </div>
              )}
            </Card>
          )}

          {/* 4 Stat Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-8">
            {statCards.map((stat) => (
              <Card
                key={stat.label}
                className="bg-white border-gray-200 p-4 sm:p-5"
              >
                <div className="flex items-center justify-between mb-3">
                  <div
                    className={`w-9 h-9 rounded-lg ${stat.bgColor} flex items-center justify-center`}
                  >
                    <stat.icon className={`w-4.5 h-4.5 ${stat.color}`} />
                  </div>
                </div>
                <p className="text-2xl sm:text-3xl font-bold text-gray-900">
                  {loading && fiveDLoading ? "—" : stat.value}
                </p>
                <p className="text-xs text-gray-500 mt-1">{stat.label}</p>
              </Card>
            ))}
          </div>

          {/* ============================================================ */}
          {/*  6D Score Overview Section                                     */}
          {/* ============================================================ */}
          <Card className="bg-white border-gray-200 p-5 sm:p-6 mb-8">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                <Award className="w-4.5 h-4.5 text-brand-600" />
                6维产品评分总览
              </h2>
              <Button
                size="sm"
                variant="outline"
                className="border-gray-200 text-gray-600 hover:bg-gray-50 bg-transparent"
                onClick={() => navigate("/asin-manager")}
              >
                <Sparkles className="w-3.5 h-3.5 mr-1" /> 管理机会池
              </Button>
            </div>

            {fiveDLoading ? (
              <div className="animate-pulse space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-20 bg-gray-50 rounded-lg" />
                  ))}
                </div>
              </div>
            ) : fiveDItems.length === 0 ? (
              <div className="text-center py-8">
                <Award className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                <p className="text-sm text-gray-500 mb-3">
                  暂无6维评分数据，去ASIN库对产品进行评分
                </p>
                <Button
                  size="sm"
                  className="bg-brand-600 hover:bg-brand-500 text-white"
                  onClick={() => navigate("/asin-manager")}
                >
                  去评分 <ArrowRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              </div>
            ) : (
              <div className="space-y-5">
                {/* Summary stats row */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-brand-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-brand-700">{fiveDItems.length}</p>
                    <p className="text-[11px] text-brand-500">已评分产品</p>
                  </div>
                  <div className="bg-emerald-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-emerald-700">{qualifiedItems.length}</p>
                    <p className="text-[11px] text-emerald-500">机会池 (≥70分)</p>
                  </div>
                  <div className="bg-amber-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-amber-700">{pendingItems.length}</p>
                    <p className="text-[11px] text-amber-500">待优化 (&lt;70分)</p>
                  </div>
                  <div className="bg-gold-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-gold-700">{avgScore}</p>
                    <p className="text-[11px] text-gold-500">平均总分</p>
                  </div>
                </div>

                {/* Radar + Product list */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                  {/* Aggregated Radar Chart */}
                  <div className="flex flex-col items-center">
                    <p className="text-xs text-gray-500 mb-2">各维度平均得分</p>
                    {fiveDRadarData.length > 0 && (
                      <ResponsiveContainer width="100%" height={220}>
                        <RechartsRadarChart data={fiveDRadarData} cx="50%" cy="50%" outerRadius="75%">
                          <PolarGrid stroke="#e5e7eb" />
                          <PolarAngleAxis
                            dataKey="dimension"
                            tick={{ fontSize: 11, fill: "#6b7280" }}
                          />
                          <PolarRadiusAxis
                            domain={[0, 20]}
                            tick={{ fontSize: 9, fill: "#9ca3af" }}
                            axisLine={false}
                          />
                          <Radar
                            name="平均分"
                            dataKey="value"
                            stroke="#0f2a24"
                            fill="#0f2a24"
                            fillOpacity={0.2}
                            strokeWidth={2}
                          />
                        </RechartsRadarChart>
                      </ResponsiveContainer>
                    )}
                  </div>

                  {/* Top scored products */}
                  <div>
                    <p className="text-xs text-gray-500 mb-3">
                      {qualifiedItems.length > 0 ? "机会池产品" : "最近评分产品"}
                    </p>
                    <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                      {(qualifiedItems.length > 0 ? qualifiedItems : fiveDItems)
                        .slice(0, 6)
                        .map((item) => (
                          <div
                            key={item.id}
                            className="flex items-center gap-3 p-2.5 rounded-lg bg-gray-50 border border-gray-100 hover:border-gray-200 transition-colors cursor-pointer"
                            onClick={() => navigate("/asin-manager")}
                          >
                            <MiniRadar scores={item.dimension_scores} size={48} />
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-gray-900 truncate">
                                {item.product_title || item.asin}
                              </p>
                              <div className="flex items-center gap-2 mt-0.5">
                                <span className="text-[10px] font-mono text-brand-600 bg-brand-50 px-1.5 py-0.5 rounded">
                                  {item.asin}
                                </span>
                              </div>
                            </div>
                            <div className="text-right flex-shrink-0">
                              <span
                                className={`text-sm font-bold ${
                                  item.qualified ? "text-emerald-600" : "text-amber-600"
                                }`}
                              >
                                {item.total_score}
                              </span>
                              <p className="text-[9px] text-gray-400">/100</p>
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </Card>

          {/* 5-Step Conversion Cycle */}
          <Card className="bg-white border-gray-200 p-5 sm:p-6 mb-8">
            <h2 className="text-base font-semibold text-gray-900 mb-5 flex items-center gap-2">
              <RotateCcw className="w-4.5 h-4.5 text-brand-600" />
              转化优化循环
            </h2>
            <div className="flex flex-wrap items-center justify-center gap-1 sm:gap-2">
              {NAV_CYCLE_STEPS.map((step, idx) => {
                const isActive = activeStep === step.id;
                return (
                  <div key={step.id} className="flex items-center">
                    <button
                      onClick={() => {
                        setActiveStep(step.id);
                        goTo(step.path);
                      }}
                      className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border transition-all duration-200 text-left ${
                        isActive
                          ? `${step.bgLight} ${step.borderColor} border-2 shadow-sm`
                          : "bg-white border-gray-100 hover:border-gray-200 hover:shadow-sm"
                      }`}
                    >
                      <div
                        className={`w-8 h-8 rounded-lg ${
                          isActive ? step.color : "bg-gray-100"
                        } flex items-center justify-center flex-shrink-0`}
                      >
                        <step.icon
                          className={`w-4 h-4 ${
                            isActive ? "text-white" : "text-gray-400"
                          }`}
                        />
                      </div>
                      <div className="min-w-0">
                        <p
                          className={`text-xs font-semibold ${
                            isActive ? step.textColor : "text-gray-700"
                          }`}
                        >
                          {step.label}
                        </p>
                        <p className="text-[10px] text-gray-400 truncate max-w-[120px]">
                          {step.desc}
                        </p>
                      </div>
                    </button>
                    {idx < NAV_CYCLE_STEPS.length - 1 && (
                      <ChevronRight className="w-4 h-4 text-gray-300 flex-shrink-0 hidden sm:block mx-0.5" />
                    )}
                  </div>
                );
              })}
            </div>
            <div className="flex items-center justify-center mt-4 gap-2 text-xs text-gray-400">
              <RotateCcw className="w-3.5 h-3.5" />
              <span>第 5 步完成后自动回到第 1 步，形成持续优化闭环</span>
            </div>
          </Card>

          {/* Product Filter for Timeline & Chart */}
          <div className="flex items-center gap-3 mb-4">
            <Filter className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-600">按产品筛选：</span>
            <select
              value={selectedProductId}
              onChange={(e) => setSelectedProductId(Number(e.target.value))}
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
            >
              <option value={0}>全部产品</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title || p.asin} ({p.asin})
                </option>
              ))}
            </select>
          </div>

          {/* Two-column: Timeline + Line Chart */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mb-8">
            {/* Optimization Progress Timeline */}
            <Card className="bg-white border-gray-200 p-5">
              <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Clock className="w-4 h-4 text-brand-500" />
                优化进度时间线
              </h3>
              {timelineLoading ? (
                <div className="animate-pulse space-y-4">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="flex gap-3">
                      <div className="w-3 h-3 rounded-full bg-gray-200 mt-1" />
                      <div className="flex-1 space-y-2">
                        <div className="h-4 bg-gray-100 rounded w-3/4" />
                        <div className="h-3 bg-gray-50 rounded w-1/2" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : sortedTimeline.length === 0 ? (
                <div className="text-center py-8">
                  <Clock className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                  <p className="text-sm text-gray-400">
                    暂无优化记录，完成各模块分析后自动记录
                  </p>
                </div>
              ) : (
                <div className="relative max-h-[400px] overflow-y-auto pr-1">
                  {/* Vertical line */}
                  <div className="absolute left-[11px] top-2 bottom-2 w-0.5 bg-gray-100" />
                  <div className="space-y-4">
                    {sortedTimeline.slice(0, 20).map((event, idx) => {
                      const colors = STEP_COLOR_MAP[event.step_name] || {
                        bg: "bg-gray-100",
                        text: "text-gray-700",
                        dot: "#6b7280",
                      };
                      const StepIcon =
                        STEP_ICON_MAP[event.step_name] || CheckCircle2;
                      const ts = new Date(event.action_timestamp);
                      const timeStr = `${ts.getMonth() + 1}/${ts.getDate()} ${ts.getHours().toString().padStart(2, "0")}:${ts.getMinutes().toString().padStart(2, "0")}`;
                      return (
                        <div key={event.id || idx} className="flex gap-3 relative">
                          {/* Dot */}
                          <div
                            className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 z-10 border-2 border-white"
                            style={{ backgroundColor: colors.dot }}
                          >
                            <StepIcon className="w-3 h-3 text-white" />
                          </div>
                          {/* Content */}
                          <div className="flex-1 min-w-0 pb-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <Badge
                                className={`${colors.bg} ${colors.text} text-[10px] border-0 px-2 py-0.5`}
                              >
                                {event.step_name}
                              </Badge>
                              {event.listing_score > 0 && (
                                <span className="text-xs font-semibold text-teal-600">
                                  评分: {event.listing_score}
                                </span>
                              )}
                              <span className="text-[10px] text-gray-400 ml-auto">
                                第{event.optimization_round}轮
                              </span>
                            </div>
                            <p className="text-[11px] text-gray-400 mt-0.5">
                              {timeStr}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </Card>

            <Card className="bg-white border-gray-200 p-5 lg:col-span-2">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                  <Database className="w-4 h-4 text-emerald-500" />
                  最近动作快照
                </h3>
                <Button size="sm" variant="outline" onClick={loadSnapshots} className="border-gray-200 text-gray-600">
                  <RefreshCw className="w-3.5 h-3.5 mr-1" />
                  刷新
                </Button>
              </div>
              {snapshotLoading ? (
                <div className="animate-pulse space-y-2">
                  {[1, 2, 3].map((i) => <div key={i} className="h-12 bg-gray-50 rounded-lg" />)}
                </div>
              ) : snapshots.length === 0 ? (
                <div className="text-center py-6">
                  <Database className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                  <p className="text-sm text-gray-400">暂无动作快照，完成任一分析或验证后会自动保存</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {snapshots.map((item) => (
                    <div key={item.id} className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px]">
                              {item.module_name}
                            </Badge>
                            <span className="text-xs text-gray-500 truncate">{item.action_name}</span>
                          </div>
                          <p className="text-sm font-medium text-gray-900 truncate mt-1">
                            {item.title || item.asin || "未命名快照"}
                          </p>
                        </div>
                        <div className="text-right shrink-0">
                          <p className="text-[10px] text-gray-400">
                            {item.created_at ? new Date(item.created_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : ""}
                          </p>
                          <p className="text-[10px] text-gray-500 mt-1">
                            {item.ai_called ? "智能生成" : "数据保存"} · 只读
                          </p>
                        </div>
                      </div>
                      <details className="mt-2">
                        <summary className="cursor-pointer text-[11px] text-brand-600 hover:text-brand-700">
                          查看快照
                        </summary>
                        <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-white border border-gray-100 p-2 text-[10px] text-gray-600 whitespace-pre-wrap">
                          {JSON.stringify(item.output_snapshot || item.input_snapshot || {}, null, 2)}
                        </pre>
                      </details>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-[11px] text-gray-400 mt-3">
                快照为当时输入、输出和判断依据的只读记录，点击历史查看不会重新生成诊断。
              </p>
            </Card>

            {/* Listing Score Trend Line Chart */}
            <Card className="bg-white border-gray-200 p-5">
              <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-teal-500" />
                Listing 评分趋势
              </h3>
              {timelineLoading ? (
                <div className="animate-pulse h-[300px] bg-gray-50 rounded-lg" />
              ) : chartData.length === 0 ? (
                <div className="text-center py-8 h-[300px] flex flex-col items-center justify-center">
                  <BarChart3 className="w-8 h-8 text-gray-300 mb-2" />
                  <p className="text-sm text-gray-400">
                    暂无评分数据，完成 Listing 诊断后自动生成趋势图
                  </p>
                </div>
              ) : (
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                      data={chartData}
                      margin={{ top: 10, right: 20, left: 0, bottom: 10 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis
                        dataKey="round"
                        tick={{ fontSize: 12, fill: "#6b7280" }}
                        axisLine={{ stroke: "#e5e7eb" }}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tick={{ fontSize: 12, fill: "#6b7280" }}
                        axisLine={{ stroke: "#e5e7eb" }}
                        label={{
                          value: "评分",
                          angle: -90,
                          position: "insideLeft",
                          style: { fontSize: 12, fill: "#9ca3af" },
                        }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#fff",
                          border: "1px solid #e5e7eb",
                          borderRadius: "8px",
                          fontSize: "12px",
                        }}
                        formatter={(value: number) => [`${value} 分`, "Listing评分"]}
                      />
                      <Line
                        type="monotone"
                        dataKey="score"
                        stroke="#0d9488"
                        strokeWidth={2.5}
                        dot={{
                          fill: "#0d9488",
                          strokeWidth: 2,
                          r: 5,
                          stroke: "#fff",
                        }}
                        activeDot={{
                          r: 7,
                          fill: "#0d9488",
                          stroke: "#fff",
                          strokeWidth: 2,
                        }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
              <p className="text-[11px] text-gray-400 mt-2 text-center">
                每次 Listing 诊断完成后自动记录评分，展示优化提升趋势
              </p>
            </Card>
          </div>

          {/* Current Project Overview */}
          <Card className="bg-white border-gray-200 mb-8">
            <div className="p-4 sm:p-5 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-900">
                当前项目总览
              </h2>
              <Button
                size="sm"
                variant="outline"
                className="border-gray-200 text-gray-600 hover:bg-gray-50 bg-transparent"
                onClick={() => navigate("/asin-manager")}
              >
                <Package className="w-3.5 h-3.5 mr-1" /> 管理商品
              </Button>
            </div>
            {loading ? (
              <div className="p-8 text-center text-gray-400">
                <div className="animate-pulse space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-12 bg-gray-50 rounded-lg" />
                  ))}
                </div>
              </div>
            ) : products.length === 0 ? (
              <div className="p-8 text-center">
                <Package className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500 text-sm mb-3">
                  还没有添加任何商品
                </p>
                <Button
                  size="sm"
                  className="bg-brand-600 hover:bg-brand-500 text-white"
                  onClick={() => navigate("/asin-manager")}
                >
                  添加第一个ASIN
                  <ArrowRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              </div>
            ) : (
              <div className="divide-y divide-gray-50">
                {products.slice(0, 5).map((product) => {
                  const stageInfo = getProductStageInfo(product, healthReports);
                  // Find 6D score for this product
                  const fiveDScore = fiveDItems.find(
                    (i) => i.asin === product.asin
                  );
                  return (
                    <div
                      key={product.id}
                      className="p-3 sm:p-4 flex items-center gap-3 hover:bg-gray-50/50 transition-colors"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {product.title || product.asin}
                        </p>
                        <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                          <span>{product.asin}</span>
                          <Badge
                            variant="outline"
                            className="text-[10px] border-gray-200 text-gray-500"
                          >
                            {stageInfo.stage}
                          </Badge>
                          {fiveDScore && (
                            <span
                              className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                                fiveDScore.qualified
                                  ? "bg-emerald-50 text-emerald-700"
                                  : "bg-amber-50 text-amber-700"
                              }`}
                            >
                              选品分: {fiveDScore.total_score}分
                            </span>
                          )}
                          <span className="text-gray-400">
                            {stageInfo.issue}
                          </span>
                        </div>
                      </div>
                      <div className="hidden sm:block text-xs text-gray-400 max-w-[160px] truncate">
                        建议：{stageInfo.suggestion}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-brand-600 hover:text-brand-700 hover:bg-brand-50 text-xs flex-shrink-0"
                        onClick={() => navigate(stageInfo.action)}
                      >
                        {stageInfo.suggestion}
                        <ArrowRight className="w-3 h-3 ml-1" />
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          {/* Two-column: Suggestions + Verification Feedback */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mb-8">
            {/* System Suggestions */}
            <Card className="bg-white border-gray-200 p-5">
              <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-500" />
                系统建议你优先做这几件事
              </h3>
              {loading ? (
                <div className="animate-pulse space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-10 bg-gray-50 rounded-lg" />
                  ))}
                </div>
              ) : (
                <div className="space-y-3">
                  {suggestions.slice(0, 4).map((s, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-gray-100"
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="w-5 h-5 rounded-full bg-brand-100 text-brand-600 text-[11px] font-bold flex items-center justify-center flex-shrink-0">
                          {i + 1}
                        </span>
                        <span className="text-sm text-gray-700">{s.text}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-brand-600 hover:bg-brand-50 text-xs flex-shrink-0"
                        onClick={() => goTo(s.path)}
                      >
                        {s.action}
                        <ArrowRight className="w-3 h-3 ml-1" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Recent Verification Feedback */}
            <Card className="bg-white border-gray-200 p-5">
              <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <RefreshCw className="w-4 h-4 text-emerald-500" />
                数据回流状态
              </h3>
              {loading ? (
                <div className="animate-pulse space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-10 bg-gray-50 rounded-lg" />
                  ))}
                </div>
              ) : (
                <div className="space-y-3">
                  {feedbackItems.map((item, i) => {
                    const Icon = FEEDBACK_ICONS[item.type] || RefreshCw;
                    const color = FEEDBACK_COLORS[item.type] || "text-gray-600";
                    return (
                      <div
                        key={i}
                        className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 border border-gray-100"
                      >
                        <Icon className={`w-4 h-4 ${color} flex-shrink-0`} />
                        <span className="text-sm text-gray-700">
                          {item.text}
                        </span>
                        <CheckCircle2 className="w-4 h-4 text-emerald-500 ml-auto flex-shrink-0" />
                      </div>
                    );
                  })}
                </div>
              )}
              <p className="text-[11px] text-gray-400 mt-3">
                各模块分析结果已自动汇总，推动下一轮优化决策
              </p>
            </Card>
          </div>

          {/* Optimization Cycle Progress */}
          <Card className="bg-white border-gray-200 p-5 mb-8">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                  <RotateCcw className="w-4 h-4 text-gold-500" />
                  优化循环进度
                </h3>
                <p className="text-xs text-gray-400 mt-1">
                  持续迭代比一次改完更重要
                </p>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold text-gray-900">
                  {loading ? "—" : `第 ${completedRounds}/5 轮`}
                </p>
                <p className="text-xs text-gray-400">转化优化循环</p>
              </div>
            </div>
            <div className="mt-4 w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-brand-500 via-teal-500 to-gold-500 transition-all duration-700"
                style={{
                  width: `${loading ? 0 : Math.min((completedRounds / 5) * 100, 100)}%`,
                }}
              />
            </div>
            <div className="flex justify-between mt-2 text-[10px] text-gray-400">
              {NAV_CYCLE_STEPS.map((step) => (
                <span
                  key={step.id}
                  className={
                    completedRounds >= step.id
                      ? "text-brand-500 font-medium"
                      : ""
                  }
                >
                  {step.label}
                </span>
              ))}
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}
