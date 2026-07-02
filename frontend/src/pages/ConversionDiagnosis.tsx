import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowDownToLine, ArrowRight, AlertTriangle, Gauge } from "lucide-react";
import {
  diagnoseConversion,
  getConversionDiagnosis,
  listConversionDiagnoses,
  ConversionDiagnosis as CD,
} from "@/lib/api";
import { label, FUNNEL_STAGE_LABELS as FUNNEL_MAP, POSITION_LABELS as POS_MAP, IMPACT_METRIC_LABELS, KEYWORD_TYPE_LABELS, labelMetrics } from "@/lib/label-maps";

type HeatmapItem = Record<string, unknown> | NonNullable<CD["position_diagnoses_json"]>[number];

const AD_METRIC_LABELS: Record<string, string> = {
  CTR: "点击率",
  CVR: "转化率",
  ACOS: "ACOS",
  TACOS: "TACOS",
  CPC: "CPC",
  "加购率": "加购率",
  "订单量": "订单量",
  "退货率": "退货率",
  "自然排名": "自然排名",
  "广告相关性": "广告相关性",
};

const STATUS_COLOR: Record<string, string> = {
  "通过": "bg-[#34c759]/[0.06] border-[#34c759]/20",
  "需修改": "bg-[#ff9500]/[0.06] border-[#ff9500]/20",
  "严重影响转化": "bg-[#ff3b30]/[0.06] border-[#ff3b30]/20",
  "缺失": "bg-[#86868b]/[0.06] border-[#86868b]/20",
};

const STATUS_DOT: Record<string, string> = {
  "通过": "bg-[#34c759]",
  "需修改": "bg-[#ff9500]",
  "严重影响转化": "bg-[#ff3b30]",
  "缺失": "bg-[#86868b]",
};

const HEAT_STATUS_LABEL: Record<string, string> = {
  covered: "已覆盖",
  weak: "弱覆盖",
  missing: "缺失",
  wrong_position: "错误位置",
  blocked_by_rule: "平台规则禁止",
  not_priority: "当前不优先",
};

const RISK_COLOR: Record<string, string> = {
  high: "text-[#ff3b30]",
  medium: "text-[#ff9500]",
  low: "text-[#34c759]",
 };

const FUNNEL_LABELS: Record<string, string> = {
  demand_trigger: "需求触发",
  search_intent: "搜索意图",
  search_match: "搜索匹配",
  click_decision: "点击判断",
  first_screen_confirmation: "首屏确认",
  value_understanding: "卖点理解",
  trust_building: "信任证明",
  objection_handling: "疑虑消除",
  purchase_confirmation: "购买确认",
};

const FUNNEL_STAGE_LABELS = [
  "需求触发",
  "搜索意图",
  "搜索匹配",
  "点击判断",
  "首屏确认",
  "卖点理解",
  "信任证明",
  "疑虑消除",
  "购买确认",
];

const STAGE_ORDER = ["search_match", "click_decision", "first_screen_confirmation", "value_understanding", "trust_building", "objection_handling"];

const STAGE_COLORS: Record<string, { bg: string; border: string; dot: string }> = {
  covered: { bg: "bg-[#34c759]/[0.06]", border: "border-[#34c759]/30", dot: "bg-[#34c759]" },
  weak: { bg: "bg-[#ff9500]/[0.06]", border: "border-[#ff9500]/30", dot: "bg-[#ff9500]" },
  missing: { bg: "bg-[#ff3b30]/[0.06]", border: "border-[#ff3b30]/30", dot: "bg-[#ff3b30]" },
  blocked_by_rule: { bg: "bg-[#ff3b30]/[0.08]", border: "border-[#ff3b30]/40", dot: "bg-[#ff3b30]" },
  not_priority: { bg: "bg-[#86868b]/[0.04]", border: "border-[#86868b]/20", dot: "bg-[#86868b]" },
};

export default function ConversionDiagnosis() {
  const [asin, setAsin] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<CD | null>(null);
  const [error, setError] = useState("");

  const { data: history } = useQuery({
    queryKey: ["conversion-diagnosis-history"],
    queryFn: () => listConversionDiagnoses(),
  });

  const handleDiagnose = async () => {
    if (!asin.trim()) return;
    setAnalyzing(true);
    setError("");
    try {
      const res = await diagnoseConversion(asin.trim());
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "请求失败");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">承接转化</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          诊断在售 Listing，找到哪个位置卡住了转化，影响哪个广告指标
        </p>
      </div>

      <div className="apple-card p-6 mb-8">
        <div className="flex gap-3">
          <input
            type="text"
            value={asin}
            onChange={(e) => setAsin(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleDiagnose()}
            placeholder="输入在售 ASIN 或 Amazon 链接"
            className="apple-input flex-1"
          />
          <button
            onClick={handleDiagnose}
            disabled={analyzing || !asin.trim()}
            className="apple-btn-primary flex items-center gap-2 px-6"
          >
            {analyzing ? (
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <>
                诊断转化
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </div>
        {error && (
          <p className="mt-3 text-[13px] text-[#ff3b30]">{error}</p>
        )}
      </div>

      {result && (
        <div className="space-y-4 mb-10">
          {result.ai_readability_score_json ? (
            <UnifiedListingDiagnosis result={result} />
          ) : (
            <>
          {/* Summary */}
          <div className="apple-card p-6">
            <h2 className="text-[20px] font-semibold mb-1">{result.product_title}</h2>
            <p className="text-[15px] text-[#86868b] mb-4">{result.overall_conclusion}</p>

            {result.biggest_breakpoint && (
              <div className="bg-[#ff3b30]/[0.04] rounded-xl p-4 mb-3 flex items-start gap-3">
                <AlertTriangle size={18} className="text-[#ff3b30] shrink-0 mt-0.5" />
                <div>
                  <p className="text-[13px] font-medium text-[#ff3b30]">最大断点</p>
                  <p className="text-[15px]">{result.biggest_breakpoint}</p>
                </div>
              </div>
            )}

            {result.priority_action && (
              <div className="bg-[#0F2A24]/[0.04] rounded-xl p-4 flex items-start gap-3">
                <Gauge size={18} className="text-[#0F2A24] shrink-0 mt-0.5" />
                <div>
                  <p className="text-[13px] font-medium text-[#0F2A24]">优先动作</p>
                  <p className="text-[15px]">{result.priority_action}</p>
                </div>
              </div>
            )}
          </div>

          {/* Impacted ad metrics */}
          {result.impacted_ad_metrics && result.impacted_ad_metrics.length > 0 && (
            <div className="apple-card p-6">
              <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">
                受影响的广告指标
              </h3>
              <div className="flex flex-wrap gap-2">
                {result.impacted_ad_metrics.map((m) => (
                  <span
                    key={m}
                    className="px-3 py-1.5 bg-[#fbfaf7] rounded-full text-[13px] font-medium text-[#1d1d1f]"
                  >
                    {AD_METRIC_LABELS[m] ?? m}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Position-by-position diagnoses */}
          {result.position_diagnoses_json && result.position_diagnoses_json.length > 0 && (
            <div className="apple-card p-6">
              <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">
                逐位置诊断
              </h3>
              <div className="space-y-3">
                {result.position_diagnoses_json.map((d, i) => (
                  <div
                    key={i}
                    className={`rounded-xl p-4 border ${STATUS_COLOR[d.status] ?? "border-[#d2d2d7]/20"}`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <div className={`w-2 h-2 rounded-full ${STATUS_DOT[d.status] ?? "bg-[#86868b]"}`} />
                      <span className="text-[14px] font-semibold">{d.position_name}</span>
                      <span className="text-[12px] text-[#86868b] ml-auto">{d.status}</span>
                      {d.priority != null && (
                        <span className="text-[11px] text-[#86868b] bg-[#fbfaf7] px-1.5 py-0.5 rounded-full">
                          P{d.priority}
                        </span>
                      )}
                    </div>
                    {d.issue && <p className="text-[14px] mb-1.5">{d.issue}</p>}
                    {d.evidence && (
                      <p className="text-[13px] text-[#86868b] mb-1.5">{d.evidence}</p>
                    )}
                    {(d.buyerLanguageProblem || d.positionProblem || d.reason) && (
                      <div className="mt-3 space-y-2">
                        <FieldBlock
                          label="为什么有问题"
                          value={d.reason || d.buyerLanguageProblem || d.positionProblem || "暂无"}
                        />
                        <FieldBlock
                          label="命中的人性驱动力"
                          value={[
                            d.humanDriver?.primaryDriverType,
                            d.humanDriver?.primaryDriver,
                            ...(d.humanDriver?.gainDrivers ?? []),
                            ...(d.humanDriver?.avoidanceDrivers ?? []),
                          ].filter(Boolean).join(" / ") || "暂无"}
                        />
                        <FieldBlock
                          label="主心智价值点"
                          value={d.mentalValuePoint?.buyerMemorySentence || d.mentalValuePoint?.primaryValuePoint || "暂无"}
                        />
                      </div>
                    )}
                    {d.recommendation && (
                      <p className="text-[13px] text-[#0F2A24] bg-[#0F2A24]/[0.04] rounded-lg p-2 mt-2">
                        {d.recommendation}
                      </p>
                    )}
                    {(d.complianceRisk?.riskLevel || d.rejectedPhrases?.length) && (
                      <FieldBlock
                        label="风险提示"
                        value={[
                          d.complianceRisk?.riskLevel,
                          ...(d.rejectedPhrases ?? []),
                          ...(d.complianceRisk?.saferAlternatives ?? []),
                        ].filter(Boolean).join(" / ") || "暂无"}
                      />
                    )}
                    {d.placementAdvice && (
                      <FieldBlock label="位置建议" value={d.placementAdvice} />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
            </>
          )}
        </div>
      )}

      {history?.items && history.items.length > 0 && (
        <div>
          <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">
            历史记录
          </h3>
          <div className="space-y-2">
            {history.items.map((item) => (
              <div key={item.id} className="apple-card p-4 flex items-center justify-between hover:bg-[#fbfaf7] transition-colors">
                <div className="flex items-center gap-3">
                  <ArrowDownToLine size={18} className="text-[#86868b]" />
                  <div>
                    <p className="text-[15px] font-medium">{item.asin}</p>
                    <p className="text-[13px] text-[#86868b] truncate max-w-[250px]">{item.product_title}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[12px] text-[#86868b]">{item.created_at?.slice(0, 10)}</span>
                  <button
                    onClick={async () => {
                      const data = await getConversionDiagnosis(item.id);
                      setResult(data);
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                    className="apple-btn-secondary text-[12px] px-3 py-1"
                  >
                    回看
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function UnifiedListingDiagnosis({ result }: { result: CD }) {
  const data = result.ai_readability_score_json;
  if (!data) return null;
  const heatmap = data.position_gap_heatmap || result.position_diagnoses_json || [];
  const topActions = data.top_actions || [];
  const keywordRows = data.keyword_position_mapping || [];
  const plan = data.validation_plan || {};
  const funnelRows = normalizeFunnelRows(data.funnel_diagnosis || []);

  return (
    <>
      <div className="apple-card p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-[20px] font-semibold mb-1">{result.product_title || result.asin}</h2>
            <p className="text-[15px] text-[#86868b]">{result.overall_conclusion}</p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-[12px] text-[#86868b]">健康分</p>
            <p className="text-[24px] font-semibold text-[#0F2A24]">{data.overall_health_score ?? 0}</p>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
          <MetricCard label="当前主断点" value={funnelLabel(data.primary_bottleneck)} />
          <MetricCard label="次级断点" value={funnelLabel(data.secondary_bottleneck)} />
          <MetricCard label="置信度" value={`${data.confidence ?? 0}/100`} />
          <MetricCard label="证据强度" value={`${data.evidence_strength ?? 0}/100`} />
        </div>
        <p className="text-[12px] text-[#86868b] mt-4">{data.prediction_policy === "No uplift percentage shown without historical validation samples." ? "暂无历史验证数据，效果提升预测需完成首次广告验证后生成。" : (data.prediction_policy || "暂无")}</p>
      </div>

      {/* Funnel Chart */}
      <FunnelChart rows={funnelRows} />

      {/* Listing Heatmap */}
      <ListingHeatmap heatmap={heatmap} />

      {/* Position Diagnosis Cards */}
      <div className="apple-card p-6">
        <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">区位诊断</h3>
        <div className="space-y-3">
          {heatmap.map((item, index) => (
            <PositionDiagnosisCard key={`${item.position_id || item.position_name}-${index}`} item={item} />
          ))}
        </div>
      </div>

      <div className="apple-card p-6">
        <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">Top20 证据</h3>
        {keywordRows.length ? (
          <div className="space-y-2">
            <div className="grid grid-cols-4 gap-3 px-3 text-[11px] text-[#86868b] font-medium">
              <span>关键词</span>
              <span>类型</span>
              <span>建议位置</span>
              <span>匹配度</span>
            </div>
            {keywordRows.map((row, index) => (
              <div key={index} className="grid grid-cols-4 gap-3 rounded-xl bg-[#fbfaf7] p-3 text-[13px]">
                <span>{asText(row.keyword)}</span>
                <span>{label(KEYWORD_TYPE_LABELS, asText(row.keyword_role))}</span>
                <span>{label(POS_MAP, asText(row.recommended_positions))}</span>
                <span>{asText(row.position_consistency_score)}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[14px] text-[#86868b]">暂无</p>
        )}
      </div>

      <div className="apple-card p-6">
        <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">Top3 手术刀动作</h3>
        {topActions.length ? (
          <div className="space-y-3">
            {topActions.slice(0, 3).map((action, index) => (
              <div key={index} className="rounded-xl border border-[#d2d2d7]/70 bg-white/70 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[12px] px-2 py-1 rounded-full bg-[#0F2A24] text-white">Top {asText(action.priority)}</span>
                  <span className="text-[14px] font-semibold">{asText(action.position_name || action.target_position)}</span>
                  <span className="text-[12px] text-[#86868b] ml-auto">{asText(action.target_stage)}</span>
                </div>
                <FieldBlock label="当前问题" value={asText(action.current_problem)} />
                <FieldBlock label="修复建议" value={asText(action.action)} />
                <FieldBlock label="不要改什么" value={asText(action.do_not_change)} />
                <div className="grid grid-cols-3 gap-2 mt-2">
                  <FieldBlock label="影响方向" value={asText(action.expected_impact_direction)} />
                  <FieldBlock label="置信度" value={`${asText(action.confidence)}/100`} />
                  <FieldBlock label="验证指标" value={asText(action.verification_metrics)} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[14px] text-[#86868b]">暂无</p>
        )}
      </div>

      <div className="apple-card p-6">
        <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">最小变量广告验证方案</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <FieldBlock label="本轮变量" value={label(POS_MAP, plan.target_position as string)} />
          <FieldBlock label="对应漏斗层" value={label(FUNNEL_MAP, plan.target_stage as string)} />
          <FieldBlock label="广告词建议" value="暂无" />
          <FieldBlock label="预算建议" value={asText(plan.budget_level)} />
          <FieldBlock label="验证周期" value={`${asText(plan.verification_period_days)} 天`} />
          <FieldBlock label="观察指标" value={labelMetrics(Array.isArray(plan.verification_metrics) ? plan.verification_metrics as string[] : typeof plan.verification_metrics === 'string' ? (plan.verification_metrics as string).split(' / ') : [])} />
          <FieldBlock label="成功条件" value={asText(plan.success_condition)} />
          <FieldBlock label="失败后路径" value={asText(plan.failure_branch)} />
        </div>
      </div>
    </>
  );
}

/* ── Funnel Chart Component ── */

const FUNNEL_STAGE_ORDER = ["需求触发","搜索意图","搜索匹配","点击判断","首屏确认","卖点理解","信任证明","疑虑消除","购买确认"];

function FunnelChart({ rows }: { rows: Array<{ stage: string; risk: string; evidence: string }> }) {
  const total = rows.length;
  const palette = ["#0071e3","#5ac8fa","#34c759","#ff9500","#ff3b30","#af52de","#ff375f","#30b0c7","#ff9f0a"];
  const maxW = 520;
  const minW = 80;
  const step = (maxW - minW) / total;
  return (
    <div className="apple-card p-6">
      <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-5">转化路径分析</h3>
      <div className="flex flex-col items-center" style={{ width: maxW, margin: "0 auto" }}>
        {rows.map((row, i) => {
          const topW = maxW - i * step;
          const bottomW = i < total - 1 ? maxW - (i + 1) * step : minW;
          const riskKey = row.risk.includes("高") ? "高风险" : row.risk.includes("中") ? "中风险" : "低风险";
          const color = palette[i % palette.length];
          const isLast = i === total - 1;
          const leftIndent = (topW - bottomW) / 2;
          const leftPct = topW > 0 ? (leftIndent / topW) * 100 : 0;
          return (
            <div
              key={row.stage}
              className="relative flex items-center justify-center"
              style={{
                width: topW,
                height: 42,
                background: color,
                clipPath: isLast
                  ? "none"
                  : `polygon(0 0, 100% 0, ${100 - leftPct}% 100%, ${leftPct}% 100%)`,
                marginBottom: -2,
              }}
            >
              <span className="text-[13px] font-semibold text-white drop-shadow-sm">{row.stage}</span>
              <span className="absolute right-3 text-[10px] font-bold text-white/70">{riskKey}</span>
            </div>
          );
        })}
        <div
          style={{
            width: 0, height: 0,
            borderLeft: `${minW/2}px solid transparent`,
            borderRight: `${minW/2}px solid transparent`,
            borderTop: `16px solid ${palette[(total-1) % palette.length]}`,
          }}
        />
      </div>
    </div>
  );
}


/* ── Listing Heatmap Matrix ── */

const HEATMAP_STAGES = ["search_match", "click_decision", "first_screen_confirmation", "value_understanding", "trust_building", "objection_handling"];

function ListingHeatmap({ heatmap }: { heatmap: HeatmapItem[] }) {
  const byStage: Record<string, Record<string, { status: string; score: number }>> = {};
  const allPositions: string[] = [];

  for (const item of heatmap) {
    const stage = String(item.funnel_stage || "");
    const pos = String(item.position_name || item.position_id || "");
    const status = String(item.current_status || item.status || "");
    const score = status === "covered" ? 100 : status === "weak" ? 50 : status === "missing" || status === "blocked_by_rule" ? 15 : 30;
    if (!byStage[stage]) byStage[stage] = {};
    byStage[stage][pos] = { status, score };
    if (!allPositions.includes(pos)) allPositions.push(pos);
  }

  // Color: red(15) → orange(50) → green(100)
  const cellColor = (score: number, status: string) => {
    if (!status) return "bg-gray-50";
    if (status === "covered") return "bg-emerald-400";
    if (status === "weak") return "bg-amber-400";
    if (status === "missing" || status === "blocked_by_rule") return "bg-red-400";
    return "bg-gray-300";
  };

  return (
    <div className="apple-card p-6 overflow-x-auto">
      <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">Listing 区位热力图</h3>
      <div className="inline-block">
        {/* Header row */}
        <div className="flex">
          <div className="w-[80px] shrink-0" />
          {allPositions.map(pos => (
            <div key={pos} className="w-[64px] text-center pb-1.5">
              <span className="text-[10px] text-[#86868b] leading-tight block">{label(POS_MAP, pos, pos)}</span>
            </div>
          ))}
        </div>
        {/* Data rows */}
        {HEATMAP_STAGES.map(stage => {
          const cells = byStage[stage] || {};
          return (
            <div key={stage} className="flex items-center">
              <div className="w-[80px] shrink-0 pr-2">
                <span className="text-[10px] font-medium text-[#86868b]">{funnelLabel(stage)}</span>
              </div>
              {allPositions.map(pos => {
                const cell = cells[pos];
                const s = cell?.status || "";
                const sc = cell?.score || 0;
                return (
                  <div key={pos} className="w-[64px] h-[36px] flex items-center justify-center">
                    <div
                      className={`w-[56px] h-[30px] rounded flex items-center justify-center ${cellColor(sc, s)}`}
                      title={s ? `${label(POS_MAP, pos, pos)}: ${HEAT_STATUS_LABEL[s] || s}` : ""}
                    >
                      <span className="text-[10px] font-bold text-white drop-shadow-sm">
                        {s === "covered" ? sc : s === "weak" ? sc : s === "missing" || s === "blocked_by_rule" ? sc : "—"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
      {/* Legend */}
      <div className="flex items-center gap-4 mt-4 pt-3 border-t border-[#d2d2d7]/20">
        {[
          { label: "已覆盖", color: "bg-emerald-400", score: "100" },
          { label: "弱覆盖", color: "bg-amber-400", score: "50" },
          { label: "缺失/禁止", color: "bg-red-400", score: "15" },
          { label: "不适用", color: "bg-gray-300", score: "—" },
        ].map(item => (
          <span key={item.label} className="flex items-center gap-1.5 text-[11px] text-[#86868b]">
            <span className={`w-3 h-3 rounded ${item.color}`} />{item.label}
          </span>
        ))}
      </div>
    </div>
  );
}


function normalizeFunnelRows(rows: Array<Record<string, unknown>>) {
  return FUNNEL_STAGE_LABELS.map((stage) => {
    const row = rows.find((item) => funnelLabel(item.stage || item.funnel_stage) === stage);
    if (row) {
      return {
        stage,
        risk: asText(row.risk_level || row.risk || row.status),
        evidence: asText(row.evidence || row.diagnosis || row.issue || row.reason),
      };
    }
    return {
      stage,
      risk: "low",
      evidence: "当前未检测到明显问题，待更多数据验证。",
    };
  });
}

function riskLabel(risk: string) {
  if (risk === "high" || risk === "高") return "高风险";
  if (risk === "medium" || risk === "中") return "中风险";
  if (risk === "low" || risk === "低") return "低风险";
  return risk === "暂无" ? "暂无" : risk;
}

function riskTextClass(risk: string) {
  if (risk === "high" || risk === "高") return "text-[#ff3b30]";
  if (risk === "medium" || risk === "中") return "text-[#ff9500]";
  if (risk === "low" || risk === "低") return "text-[#34c759]";
  return "text-[#86868b]";
}

function funnelLabel(value: unknown): string {
  const text = asText(value);
  if (text === "暂无") return text;
  return FUNNEL_LABELS[text] || text;
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl bg-[#fbfaf7] p-3">
      <p className="text-[11px] text-[#86868b] mb-1">{label}</p>
      <p className="text-[14px] font-semibold text-[#1d1d1f]">{value}</p>
    </div>
  );
}

function PositionDiagnosisCard({ item }: { item: HeatmapItem }) {
  const status = String(item.current_status || item.status || "");
  const issue = asText(item.reason || item.buyerLanguageProblem || item.positionProblem || item.issue);
  const fix = asText(item.suggestedRewrite || item.recommendation);
  const metrics = item.validationMetrics || item.impacted_ad_metrics || [];
  return (
    <div className={`rounded-xl p-4 border ${heatClass(String(item.current_status || item.status))}`}>
      <div className="flex items-center gap-2 mb-2">
        <div className={`w-2 h-2 rounded-full ${heatDot(String(item.current_status || item.status))}`} />
        <span className="text-[13px] font-semibold">{label(POS_MAP, item.position_name as string, asText(item.position_name))}</span>
        <span className="text-[11px] text-[#86868b]">{funnelLabel(item.funnel_stage)}</span>
        <span className="text-[11px] text-[#86868b] ml-auto">
          {HEAT_STATUS_LABEL[status] || status || "暂无"}
        </span>
      </div>
      <p className="text-[13px] text-[#1d1d1f] mb-2">{issue}</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
        <span className="text-[11px] text-[#86868b]">{asText(item.issue || item.recommendation) ? "建议: " + asText(item.recommendation || item.recommended_fix_type) : ""}</span>
        <span className="text-[11px] text-[#86868b]">影响: {labelMetrics(Array.isArray(item.impacted_ad_metrics) ? item.impacted_ad_metrics as string[] : (typeof item.impact_direction === 'string' ? (item.impact_direction as string).split(' / ') : []))}</span>
      </div>
    </div>
  );
}

function heatClass(status?: string) {
  if (status === "covered" || status === "通过" || status === "已覆盖") return "bg-[#34c759]/[0.04] border-[#34c759]/20";
  if (status === "weak" || status === "需修改" || status === "弱覆盖" || status === "not_priority") return "bg-[#ff9500]/[0.04] border-[#ff9500]/20";
  if (status === "blocked_by_rule" || status === "平台禁止" || status === "平台规则禁止") return "bg-[#ff3b30]/[0.04] border-[#ff3b30]/20";
  return "bg-white/70 border-[#d2d2d7]/60";
}

function heatDot(status?: string) {
  if (status === "covered" || status === "通过" || status === "已覆盖") return "bg-[#34c759]";
  if (status === "weak" || status === "需修改" || status === "弱覆盖" || status === "not_priority") return "bg-[#ff9500]";
  if (status === "blocked_by_rule" || status === "平台禁止" || status === "平台规则禁止") return "bg-[#ff3b30]";
  return "bg-[#86868b]";
}

function asText(value: unknown): string {
  if (value == null || value === "") return "暂无";
  if (Array.isArray(value)) return value.length ? value.join(" / ") : "暂无";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function FieldBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white/70 p-2">
      <p className="text-[11px] text-[#86868b] mb-1">{label}</p>
      <p className="text-[13px] text-[#1d1d1f] leading-relaxed">{value || "暂无"}</p>
    </div>
  );
}
