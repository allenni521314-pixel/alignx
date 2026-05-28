import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Target,
  Eye,
  Swords,
  DollarSign,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Award,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Info,
  ShieldAlert,
  Route,
  Database,
  Copy,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface FiveDScoreResult {
  success: boolean;
  asin: string;
  product_title: string;
  total_score: number;
  qualified: boolean;
  dimension_scores: Record<string, number>;
  detail_scores: Record<string, number>;
  analysis: Record<string, string>;
  suggestions: string[];
  raw_total?: number;
  data_completeness?: number;
  confidence_level?: "high" | "medium" | "low" | string;
  risk_level?: "low" | "medium" | "high" | string;
  decision?: string;
  pool_status?: "opportunity_pool" | "validation_pool" | "derivative_pool" | "rejected_pool" | "not_entered" | string;
  recommended_path?: string;
  one_sentence_reason?: string;
  dimensions?: Array<{
    dimension_name: string;
    dimension_key?: string;
    base_score: number;
    ai_adjustment: number;
    final_score: number;
    confidence: number;
    items: Array<{
      item_name: string;
      rule_score: number;
      ai_adjustment: number;
      final_score: number;
      evidence: string[];
      deduction_reasons: string[];
      suggestion: string;
    }>;
  }>;
  veto_rules?: Array<{
    rule_name: string;
    triggered: boolean;
    reason: string;
    evidence: string[];
  }>;
  next_actions?: string[];
  is_legacy_score?: boolean;
  id?: number;
}

/* ------------------------------------------------------------------ */
/*  Dimension metadata                                                 */
/* ------------------------------------------------------------------ */

const DIMENSIONS = [
  {
    key: "demand",
    label: "需求强度",
    icon: Target,
    color: "text-teal-600",
    bgColor: "bg-teal-50",
    barColor: "bg-teal-500",
    subItems: [
      { key: "pain_clarity", label: "痛点明确度" },
      { key: "usage_frequency", label: "使用频率" },
      { key: "demand_rigidity", label: "需求刚性" },
      { key: "payment_clarity", label: "付费理由清晰度" },
    ],
  },
  {
    key: "search_entry",
    label: "搜索入口",
    icon: Route,
    color: "text-emerald-600",
    bgColor: "bg-emerald-50",
    barColor: "bg-emerald-500",
    subItems: [
      { key: "core_keyword_capacity", label: "核心关键词容量" },
      { key: "long_tail_opportunity", label: "长尾词机会" },
      { key: "organic_entry_access", label: "自然排名可进入性" },
      { key: "ad_entry_tolerance", label: "广告入口承受力" },
    ],
  },
  {
    key: "competition",
    label: "竞争结构",
    icon: Swords,
    color: "text-amber-600",
    bgColor: "bg-amber-50",
    barColor: "bg-amber-500",
    subItems: [
      { key: "top20_review_barrier", label: "Top20评论门槛" },
      { key: "low_review_rank_opportunity", label: "低评论高排名样本" },
      { key: "sponsored_pressure", label: "广告位压力" },
      { key: "homogeneity", label: "同质化程度" },
    ],
  },
  {
    key: "differentiation",
    label: "差异化切口",
    icon: Eye,
    color: "text-sky-600",
    bgColor: "bg-sky-50",
    barColor: "bg-sky-500",
    subItems: [
      { key: "differentiation_anchor", label: "可表达差异点" },
      { key: "competitor_weakness", label: "竞品差评机会" },
      { key: "listing_expression_fit", label: "Listing表达承接" },
      { key: "substitution_difficulty", label: "替代难度" },
    ],
  },
  {
    key: "business",
    label: "商业承受力",
    icon: DollarSign,
    color: "text-gold-600",
    bgColor: "bg-gold-50",
    barColor: "bg-gold-500",
    subItems: [
      { key: "gross_margin", label: "毛利空间" },
      { key: "price_band_match", label: "价格带合理性" },
      { key: "ad_tolerance", label: "广告承受力" },
      { key: "profit_scalability", label: "套装/变体/复购空间" },
    ],
  },
  {
    key: "risk_trend",
    label: "风险与趋势",
    icon: TrendingUp,
    color: "text-rose-600",
    bgColor: "bg-rose-50",
    barColor: "bg-rose-500",
    subItems: [
      { key: "compliance_risk", label: "政策合规风险" },
      { key: "demand_growth", label: "BSR/关键词趋势" },
      { key: "category_lifecycle", label: "类目生命周期" },
      { key: "new_entry_signal", label: "新品进入案例" },
    ],
  },
] as const;

const poolLabels: Record<string, string> = {
  opportunity_pool: "机会池",
  validation_pool: "验证池",
  derivative_pool: "周边/延伸池",
  rejected_pool: "淘汰池",
  not_entered: "未入池",
};

const confidenceLabels: Record<string, string> = {
  high: "高置信",
  medium: "中置信",
  low: "低置信",
};

const riskLabels: Record<string, string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
};

const getTone = (value?: string) => {
  if (value === "high" || value === "rejected_pool" || value === "高风险禁止进入") {
    return "bg-red-50 text-red-700 border-red-200";
  }
  if (value === "medium" || value === "validation_pool" || value === "需改良后进入" || value === "可小预算测试") {
    return "bg-amber-50 text-amber-700 border-amber-200";
  }
  if (value === "low" || value === "opportunity_pool" || value === "可进入") {
    return "bg-emerald-50 text-emerald-700 border-emerald-200";
  }
  return "bg-gray-50 text-gray-700 border-gray-200";
};

const getDimensionKey = (name: string) => {
  const found = DIMENSIONS.find((dim) => dim.label === name || dim.key === name);
  return found?.key || name;
};

/* ------------------------------------------------------------------ */
/*  Radar Chart (SVG)                                                  */
/* ------------------------------------------------------------------ */

function RadarChart({
  scores,
}: {
  scores: Record<string, number>;
}) {
  const cx = 120;
  const cy = 120;
  const maxR = 90;
  const levels = [4, 8, 12, 16, 20];
  const dims = ["demand", "search_entry", "competition", "differentiation", "business", "risk_trend"] as const;
  const labels = ["需求", "搜索", "竞争", "差异", "商业", "风险"];

  const angleStep = (2 * Math.PI) / dims.length;
  const startAngle = -Math.PI / 2;

  const getPoint = (dimIndex: number, value: number) => {
    const angle = startAngle + dimIndex * angleStep;
    const r = (value / 20) * maxR;
    return {
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    };
  };

  // Grid lines
  const gridPaths = levels.map((level) => {
    const points = dims.map((_, i) => getPoint(i, level));
    return points.map((p, i) => (i === 0 ? `M${p.x},${p.y}` : `L${p.x},${p.y}`)).join(" ") + "Z";
  });

  // Data polygon
  const dataPoints = dims.map((d, i) => getPoint(i, scores[d] || 0));
  const dataPath =
    dataPoints.map((p, i) => (i === 0 ? `M${p.x},${p.y}` : `L${p.x},${p.y}`)).join(" ") + "Z";

  // Axis lines
  const axisLines = dims.map((_, i) => {
    const end = getPoint(i, 20);
    return { x1: cx, y1: cy, x2: end.x, y2: end.y };
  });

  // Labels
  const labelPoints = dims.map((_, i) => {
    const p = getPoint(i, 23);
    return p;
  });

  return (
    <svg viewBox="0 0 240 240" className="w-full max-w-[240px] mx-auto">
      {/* Grid */}
      {gridPaths.map((d, i) => (
        <path key={i} d={d} fill="none" stroke="#e5e7eb" strokeWidth="0.5" />
      ))}
      {/* Axes */}
      {axisLines.map((line, i) => (
        <line key={i} {...line} stroke="#d1d5db" strokeWidth="0.5" />
      ))}
      {/* Data */}
      <path d={dataPath} fill="rgba(99,102,241,0.15)" stroke="#0f2a24" strokeWidth="2" />
      {dataPoints.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="3" fill="#0f2a24" />
      ))}
      {/* Labels */}
      {labelPoints.map((p, i) => (
        <text
          key={i}
          x={p.x}
          y={p.y}
          textAnchor="middle"
          dominantBaseline="middle"
          className="fill-gray-600 text-[10px] font-medium"
        >
          {labels[i]}
        </text>
      ))}
      {/* Score labels */}
      {dataPoints.map((p, i) => (
        <text
          key={`s${i}`}
          x={p.x}
          y={p.y - 10}
          textAnchor="middle"
          className="fill-brand-600 text-[9px] font-bold"
        >
          {scores[dims[i]] || 0}
        </text>
      ))}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Score Badge                                                        */
/* ------------------------------------------------------------------ */

export function ScoreBadge({ score, size = "sm" }: { score: number; size?: "sm" | "lg" }) {
  const qualified = score >= 75;
  const cls =
    size === "lg"
      ? "px-3 py-1.5 text-sm font-bold rounded-lg"
      : "px-2 py-0.5 text-xs font-semibold rounded-md";

  return (
    <span
      className={`inline-flex items-center gap-1 ${cls} ${
        qualified
          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
          : "bg-amber-50 text-amber-700 border border-amber-200"
      }`}
    >
      {qualified ? (
        <CheckCircle2 className={size === "lg" ? "w-4 h-4" : "w-3 h-3"} />
      ) : (
        <AlertTriangle className={size === "lg" ? "w-4 h-4" : "w-3 h-3"} />
      )}
      {score}分
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Component: Full Score Card                                    */
/* ------------------------------------------------------------------ */

export function FiveDimensionScoreCard({
  result,
  compact = false,
}: {
  result: FiveDScoreResult;
  compact?: boolean;
}) {
  const [expanded, setExpanded] = useState(!compact);
  const [expandedDim, setExpandedDim] = useState<string | null>("demand");
  const [showAvoidanceReport, setShowAvoidanceReport] = useState(false);
  const [selectedAction, setSelectedAction] = useState<{ action: string; route: string; note: string } | null>(null);

  const toggleDim = (key: string) => {
    setExpandedDim(expandedDim === key ? null : key);
  };

  const scrollToRiskEvidence = () => {
    setExpanded(true);
    setTimeout(() => {
      document.getElementById("asin-risk-evidence")?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 80);
  };

  const buildAvoidanceReport = () => {
    const triggeredVetoes = (result.veto_rules || []).filter((rule) => rule.triggered);
    return [
      `ASIN避坑报告：${result.asin}`,
      `产品：${result.product_title || "-"}`,
      `总分：${result.total_score}`,
      `决策：${result.decision || (result.qualified ? "可继续验证" : "暂不建议进入")}`,
      `一句话原因：${result.one_sentence_reason || "-"}`,
      "",
      "风险证据：",
      ...(triggeredVetoes.length
        ? triggeredVetoes.flatMap((rule) => [
            `- ${rule.rule_name}：${rule.reason}`,
            ...(rule.evidence || []).map((item) => `  证据：${item}`),
          ])
        : ["- 暂无一票否决证据，请结合维度扣分继续人工复核。"]),
      "",
      "维度分析：",
      ...Object.entries(result.analysis || {}).map(([key, value]) => `- ${key}：${value}`),
      "",
      "建议动作：",
      ...(result.next_actions || result.suggestions || []).map((item) => `- ${item}`),
    ].join("\n");
  };

  const showReportInline = () => {
    setShowAvoidanceReport(true);
    setExpanded(true);
    setTimeout(() => {
      document.getElementById("asin-avoidance-report")?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 80);
  };

  const copyAvoidanceReport = async () => {
    await navigator.clipboard?.writeText(buildAvoidanceReport());
  };

  const restartSelection = () => {
    window.location.href = "/asin-manager";
  };

  const goToActionRoute = (action: string, route: string, note: string) => {
    const payload = {
      action,
      asin: result.asin,
      product_title: result.product_title,
      decision,
      pool_status: poolStatus,
      route,
      created_at: new Date().toISOString(),
    };
    localStorage.setItem("alignx_next_action_context", JSON.stringify(payload));
    setSelectedAction({ action, route, note });
    toast.success(note);
    setTimeout(() => {
      window.location.href = route;
    }, 250);
  };

  const handleNextAction = (action: string) => {
    if (action.includes("风险") || action.includes("证据")) {
      scrollToRiskEvidence();
      setSelectedAction({ action, route: "#asin-risk-evidence", note: "已展开风险证据，请先确认一票否决是否真实成立。" });
      return;
    }
    if (action.includes("避坑") || action.includes("报告")) {
      showReportInline();
      setSelectedAction({ action, route: "#asin-avoidance-report", note: "已生成页面内避坑报告，可复制后做人工复核。" });
      return;
    }
    const asinParam = encodeURIComponent(result.asin || "");
    const titleParam = encodeURIComponent(result.product_title || "");
    if (action.includes("Listing") || action.includes("改良") || action.includes("上新")) {
      goToActionRoute(action, `/listing-launch-check?asin=${asinParam}&source=asin-decision`, "已进入Listing/上新检测，继续验证页面承接力。");
      return;
    }
    if (action.includes("广告") || action.includes("测试关键词") || action.includes("验证指标") || action.includes("最小验证")) {
      goToActionRoute(action, `/ab-test-comparison?asin=${asinParam}&source=asin-decision`, "已进入广告验证计划，把选品假设转成可测试指标。");
      return;
    }
    if (action.includes("执行") || action.includes("跟踪")) {
      goToActionRoute(action, `/optimization-suggestions?view=data-feedback&asin=${asinParam}`, "已进入验证回流，用执行记录反哺判断模型。");
      return;
    }
    if (action.includes("竞品") || action.includes("配件") || action.includes("周边")) {
      goToActionRoute(action, `/competitor-analysis?tab=strategy&asin=${asinParam}&angle=adjacent`, "已进入竞品/周边分析，优先找可切入的配件或差评机会。");
      return;
    }
    if (action.includes("替代机会") || action.includes("相邻类目") || action.includes("重新选择") || action.includes("重新选品") || action.includes("选品")) {
      goToActionRoute(action, `/asin-manager?mode=adjacent&asin=${asinParam}&seed=${titleParam}`, "已回到ASIN机会页，按相邻类目/替代机会继续找入口。");
      return;
    }
    goToActionRoute(action, `/asin-manager?next_action=${encodeURIComponent(action)}&asin=${asinParam}`, "已记录下一步动作，返回ASIN决策继续处理。");
  };

  const hasOldPriceItems = Boolean(
    result.dimensions?.some((dim) => {
      const key = dim.dimension_key || getDimensionKey(dim.dimension_name);
      return (
        ["scenario", "profit", "trend", "price_tier", "场景维", "利润维", "趋势维", "价格带维"].includes(key) ||
        dim.items?.some((item) =>
          ["价值支撑", "促销空间", "价格竞争力", "价格带供需结构", "价格带进入门槛", "价格带抗风险能力"].includes(item.item_name)
        )
      );
    }) ||
      (Boolean(result.dimension_scores?.scenario) && !result.dimension_scores?.search_entry)
  );
  const isLegacyScore = Boolean(
    result.is_legacy_score ||
      hasOldPriceItems ||
      !result.dimensions?.length ||
      (!result.data_completeness && result.total_score > 0)
  );
  const displayDimensionScores = Object.fromEntries(
    Object.entries(result.dimension_scores || {}).map(([key, value]) => [key, Math.max(0, Math.min(20, Number(value) || 0))])
  ) as FiveDScoreResult["dimension_scores"];
  const structuredDimensions =
    !isLegacyScore && result.dimensions && result.dimensions.length > 0
      ? result.dimensions
      : DIMENSIONS.map((dim) => ({
          dimension_name: dim.label,
          dimension_key: dim.key,
          base_score: displayDimensionScores[dim.key as keyof typeof displayDimensionScores] || 0,
          ai_adjustment: 0,
          final_score: displayDimensionScores[dim.key as keyof typeof displayDimensionScores] || 0,
          confidence: result.data_completeness || 0,
          items: dim.subItems.map((sub) => ({
            item_name: sub.label,
            rule_score: result.detail_scores[sub.key] || 0,
            ai_adjustment: 0,
            final_score: result.detail_scores[sub.key] || 0,
            evidence: [],
            deduction_reasons: [],
            suggestion: "",
          })),
        }));

  const triggeredVetoes = (result.veto_rules || []).filter((rule) => rule.triggered);
  const completeness = Math.round((result.data_completeness || 0) * 100);
  const completenessText = isLegacyScore && completeness === 0 ? "历史未记录" : `${completeness}%`;
  const completenessWidth = isLegacyScore && completeness === 0 ? 8 : completeness;
  const decision = result.decision || (result.qualified ? "可进入" : "待验证");
  const poolStatus = result.pool_status || (result.qualified ? "opportunity_pool" : "not_entered");

  return (
    <Card className="bg-white border-gray-200 overflow-hidden">
      {/* Header */}
      <div
        className="p-4 flex items-center justify-between cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <div
            className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              result.qualified ? "bg-emerald-50" : "bg-amber-50"
            }`}
          >
            <Award
              className={`w-5 h-5 ${result.qualified ? "text-emerald-600" : "text-amber-600"}`}
            />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm">6维选品决策</span>
              <ScoreBadge score={result.total_score} size="sm" />
              <span className={`text-[10px] px-1.5 py-0.5 rounded border ${getTone(poolStatus)}`}>
                {poolLabels[poolStatus] || poolStatus}
              </span>
            </div>
            {result.product_title && (
              <p className="text-xs text-gray-500 mt-0.5 truncate max-w-[300px]">
                {result.product_title}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">
            {result.total_score}/100
          </span>
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          )}
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="border-t border-gray-100 p-4 space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-2">
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
              <div className="text-[11px] text-gray-500 flex items-center gap-1">
                <Database className="w-3.5 h-3.5" />
                数据完整度
              </div>
              <div className="mt-1 text-lg font-bold text-gray-900">{completenessText}</div>
              <div className="mt-2 h-1.5 bg-white rounded-full overflow-hidden">
                <div className="h-full bg-brand-500 rounded-full" style={{ width: `${completenessWidth}%` }} />
              </div>
            </div>
            <div className={`rounded-lg border p-3 ${getTone(result.confidence_level)}`}>
              <div className="text-[11px] opacity-80">判断置信度</div>
              <div className="mt-1 text-base font-bold">{confidenceLabels[result.confidence_level || ""] || result.confidence_level || "低置信"}</div>
            </div>
            <div className={`rounded-lg border p-3 ${getTone(result.risk_level)}`}>
              <div className="text-[11px] opacity-80">风险等级</div>
              <div className="mt-1 text-base font-bold">{riskLabels[result.risk_level || ""] || result.risk_level || "中风险"}</div>
            </div>
            <div className={`rounded-lg border p-3 ${getTone(decision)}`}>
              <div className="text-[11px] opacity-80">决策结论</div>
              <div className="mt-1 text-base font-bold">{decision}</div>
            </div>
            <div className={`rounded-lg border p-3 ${getTone(poolStatus)}`}>
              <div className="text-[11px] opacity-80">机会池状态</div>
              <div className="mt-1 text-base font-bold">{poolLabels[poolStatus] || poolStatus}</div>
            </div>
          </div>

          {isLegacyScore && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 leading-relaxed">
              <AlertTriangle className="w-3.5 h-3.5 inline mr-1" />
              这是旧链路历史评分，只保留了维度分和摘要，未完整保存数据完整度、一票否决和子项证据。请点击下方“重新评分”，使用新的后台规则引擎重新生成结果。
            </div>
          )}

          {result.one_sentence_reason && (
            <div className="rounded-lg border border-brand-100 bg-brand-50/70 p-3 text-xs text-brand-900 leading-relaxed">
              <Info className="w-3.5 h-3.5 inline mr-1 text-brand-500" />
              {result.one_sentence_reason}
            </div>
          )}

          <div className="rounded-lg border border-teal-100 bg-teal-50/70 px-3 py-2 text-xs text-teal-900 leading-relaxed flex items-start gap-2">
            <Info className="w-3.5 h-3.5 mt-0.5 text-teal-600 flex-shrink-0" />
            <div>
              <span className="font-semibold">维度分析已展开。</span>
              <span className="ml-1">点击右侧任一维度，可查看规则分、AI修正、证据、扣分原因和具体建议。</span>
            </div>
          </div>

          {/* Radar Chart + Summary */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <RadarChart scores={displayDimensionScores} />
            <div className="space-y-3">
              {/* Dimension bars */}
              {structuredDimensions.map((structured) => {
                const dimKey = getDimensionKey(structured.dimension_key || structured.dimension_name);
                const dim = DIMENSIONS.find((d) => d.key === dimKey) || DIMENSIONS[0];
                const score = Math.max(0, Math.min(20, structured.final_score || displayDimensionScores[dim.key as keyof typeof displayDimensionScores] || 0));
                const pct = (score / 20) * 100;
                const Icon = dim.icon;
                return (
                  <div key={dimKey}>
                    <div
                      className={`flex items-center justify-between text-xs mb-1 cursor-pointer rounded px-2 py-1 -mx-1 transition-colors ${
                        expandedDim === dimKey ? "bg-teal-50 ring-1 ring-teal-100" : "hover:bg-gray-50"
                      }`}
                      onClick={() => toggleDim(dimKey)}
                    >
                      <span className={`flex items-center gap-1.5 font-medium ${dim.color}`}>
                        <Icon className="w-3.5 h-3.5" />
                        {structured.dimension_name}
                      </span>
                      <span className="flex items-center gap-2">
                        <span className="hidden sm:inline rounded border border-gray-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-gray-600">
                          {expandedDim === dimKey ? "收起分析" : "查看分析"}
                        </span>
                        <span className="font-semibold text-gray-700">{score}/20</span>
                        {expandedDim === dimKey ? (
                          <ChevronUp className="w-3.5 h-3.5 text-gray-400" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
                        )}
                      </span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${dim.barColor} rounded-full transition-all duration-500`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>

                    {/* Sub-items */}
                    {expandedDim === dimKey && (
                      <div className="mt-2 ml-5 space-y-2 pb-2">
                        <div className="grid grid-cols-3 gap-2 text-[11px] text-gray-500">
                          <span>规则分：{Math.max(0, Math.min(20, structured.base_score || 0))}/20</span>
                          <span>AI修正：{structured.ai_adjustment > 0 ? "+" : ""}{structured.ai_adjustment}</span>
                          <span>置信：{Math.round((structured.confidence || 0) * 100)}%</span>
                        </div>
                        {structured.items.map((sub) => {
                          const subScore = sub.final_score || 0;
                          const subPct = (subScore / 5) * 100;
                          return (
                            <div key={sub.item_name} className="rounded-lg border border-gray-100 bg-gray-50/70 p-2">
                              <div className="flex items-center gap-2 text-[11px]">
                                <span className="text-gray-700 font-medium w-32 truncate">{sub.item_name}</span>
                                <div className="flex-1 h-1.5 bg-white rounded-full overflow-hidden">
                                  <div
                                    className={`h-full ${dim.barColor} rounded-full`}
                                    style={{ width: `${subPct}%` }}
                                  />
                                </div>
                                <span className="text-gray-700 font-semibold w-8 text-right">{subScore}/5</span>
                              </div>
                              <div className="mt-1 grid grid-cols-3 gap-1 text-[10px] text-gray-500">
                                <span>规则 {sub.rule_score}</span>
                                <span>AI {sub.ai_adjustment > 0 ? "+" : ""}{sub.ai_adjustment}</span>
                                <span>最终 {sub.final_score}</span>
                              </div>
                              {sub.evidence.length > 0 && (
                                <div className="mt-1 text-[10px] text-emerald-700">证据：{sub.evidence.join("；")}</div>
                              )}
                              {sub.deduction_reasons.length > 0 && (
                                <div className="mt-1 text-[10px] text-amber-700">扣分：{sub.deduction_reasons.join("；")}</div>
                              )}
                              {sub.suggestion && sub.suggestion !== result.analysis[dimKey] && (
                                <div className="mt-1 text-[10px] text-gray-600">建议：{sub.suggestion}</div>
                              )}
                            </div>
                          );
                        })}
                        {result.analysis[dimKey] && (
                          <div className="mt-2 p-2 bg-gray-50 rounded-lg text-[11px] text-gray-600 leading-relaxed">
                            <Info className="w-3 h-3 inline mr-1 text-gray-400" />
                            {result.analysis[dimKey]}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {triggeredVetoes.length > 0 && (
            <div id="asin-risk-evidence" className="rounded-lg border border-red-200 bg-red-50 p-3">
              <h4 className="text-xs font-semibold text-red-700 mb-2 flex items-center gap-1">
                <ShieldAlert className="w-3.5 h-3.5" />
                一票否决原因
              </h4>
              <div className="space-y-2">
                {triggeredVetoes.map((rule) => (
                  <div key={rule.rule_name} className="text-[11px] text-red-800">
                    <span className="font-semibold">{rule.rule_name}：</span>
                    {rule.reason}
                    {rule.evidence?.length > 0 && (
                      <span className="text-red-600"> 证据：{rule.evidence.join("；")}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {showAvoidanceReport && (
            <div id="asin-avoidance-report" className="rounded-lg border border-amber-200 bg-amber-50 p-3">
              <div className="flex items-start justify-between gap-3 mb-2">
                <h4 className="text-xs font-semibold text-amber-800 flex items-center gap-1">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  ASIN避坑报告
                </h4>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs border-amber-200 bg-white text-amber-800 hover:bg-amber-100"
                  onClick={copyAvoidanceReport}
                >
                  <Copy className="w-3.5 h-3.5 mr-1" />
                  复制
                </Button>
              </div>
              <pre className="whitespace-pre-wrap text-[11px] leading-relaxed text-amber-900 font-sans">
                {buildAvoidanceReport()}
              </pre>
            </div>
          )}

          {selectedAction && (
            <div className="rounded-lg border border-brand-100 bg-brand-50 p-3 text-xs text-brand-900 leading-relaxed">
              <Info className="w-3.5 h-3.5 inline mr-1 text-brand-500" />
              {selectedAction.note}
              <span className="ml-2 text-brand-600">目标：{selectedAction.route}</span>
            </div>
          )}

          {/* Suggestions */}
          {(result.next_actions || result.suggestions || []).length > 0 && (
            <div className="bg-brand-50/50 rounded-lg p-3">
              <h4 className="text-xs font-semibold text-brand-700 mb-2 flex items-center gap-1">
                <Route className="w-3.5 h-3.5" />
                动态下一步动作
              </h4>
              <div className="flex flex-wrap gap-2">
                {(result.next_actions || result.suggestions).map((s, i) => (
                  <Button
                    key={i}
                    size="sm"
                    variant={i === 0 ? "default" : "outline"}
                    className="h-8 text-xs"
                    onClick={() => handleNextAction(s)}
                  >
                    {s}
                  </Button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Inline Score Button (for product list)                             */
/* ------------------------------------------------------------------ */

export function FiveDScoreButton({
  loading,
  score,
  onClick,
}: {
  loading: boolean;
  score?: number | null;
  onClick: () => void;
}) {
  if (loading) {
    return (
      <Button
        variant="ghost"
        size="sm"
        disabled
        className="text-brand-500 h-8 px-2"
      >
        <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
        <span className="text-[11px]">评分中</span>
      </Button>
    );
  }

  if (score !== undefined && score !== null) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={onClick}
        className="h-8 border-brand-200 bg-brand-50 px-3 text-brand-800 hover:bg-brand-100"
        title="查看6维选品分析"
      >
        <Award className="w-3.5 h-3.5 mr-1.5" />
        <span className="hidden sm:inline text-xs font-semibold mr-1.5">查看分析</span>
        <ScoreBadge score={score} />
      </Button>
    );
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={onClick}
      className="text-brand-500 hover:text-brand-700 hover:bg-brand-50 h-8 px-2"
      title="6维评分"
    >
      <Award className="w-3.5 h-3.5 mr-1" />
      <span className="text-[11px]">6维评分</span>
    </Button>
  );
}
