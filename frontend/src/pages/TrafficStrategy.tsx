import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  TrendingUp, ArrowDown, Zap, Shield, Target,
  CheckCircle2, AlertTriangle,
  BarChart3,
} from "lucide-react";
import {
  applyLifecycle as applyLifecycleRequest,
  getLifecycle,
  listAsinProfiles,
  type LifecycleData,
} from "@/lib/api";

const STAGE_ICONS: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  new_product: Zap,
  growth: TrendingUp,
  maturity: Shield,
  decline: ArrowDown,
};

const STAGE_COLORS: Record<string, { color: string; bg: string }> = {
  new_product: { color: "text-[#0071e3]", bg: "bg-[#0071e3]/[0.04]" },
  growth: { color: "text-[#34c759]", bg: "bg-[#34c759]/[0.04]" },
  maturity: { color: "text-[#86868b]", bg: "bg-[#f5f5f7]" },
  decline: { color: "text-[#ff3b30]", bg: "bg-[#ff3b30]/[0.04]" },
};

export default function TrafficStrategy() {
  const queryClient = useQueryClient();
  const [selectedAsin, setSelectedAsin] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [guide, setGuide] = useState<{ asin: string; strategy: Record<string, string> } | null>(null);

  const { data: profiles } = useQuery({ queryKey: ["asin-profiles"], queryFn: listAsinProfiles });
  const asinList = profiles?.items ?? [];

  // Fetch lifecycle for selected ASIN
  const { data: lifecycle, isLoading: lcLoading } = useQuery<LifecycleData>({
    queryKey: ["lifecycle", selectedAsin],
    queryFn: () => getLifecycle(selectedAsin!),
    enabled: !!selectedAsin,
  });

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  };

  const applyLifecycle = async (asin: string) => {
    await applyLifecycleRequest(asin);
    queryClient.invalidateQueries({ queryKey: ["lifecycle", asin] });
    queryClient.invalidateQueries({ queryKey: ["asin-profiles"] });
    showToast("生命周期已更新");
  };

  const strategy = lifecycle?.ad_strategy;
  const metrics = lifecycle?.metrics;

  return (
    <div className="max-w-[680px] mx-auto py-12">
      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-[36px] font-bold tracking-[-0.025em] mb-2">执行测试</h1>
        <p className="text-[17px] text-[#86868b]">生命周期</p>
      </div>

      {/* Transition Alert */}
      {lifecycle?.transition_alert && (
        <div className="bg-white rounded-[20px] border border-[#ff9500]/30 p-5 mb-8 flex items-start gap-3">
          <AlertTriangle size={20} className="text-[#ff9500] shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-[14px] font-semibold text-[#ff9500]">阶段切换提醒</p>
            <p className="text-[14px] text-[#1d1d1f] mt-1">{lifecycle.transition_alert}</p>
            <button
              onClick={() => applyLifecycle(lifecycle.asin)}
              className="mt-3 apple-btn-primary text-[13px] px-4 py-2 flex items-center gap-1.5"
            >
              <CheckCircle2 size={14} /> 确认切换
            </button>
          </div>
        </div>
      )}

      {/* ASIN Selector */}
      <div className="bg-white rounded-[20px] border border-[#d2d2d7] p-5 mb-8">
        <p className="text-[13px] font-medium text-[#86868b] mb-3">选择 ASIN 查看策略</p>
        <div className="flex flex-wrap gap-2">
          {asinList.length === 0 && (
            <p className="text-[14px] text-[#86868b]">暂无 ASIN，先完成承接转化诊断</p>
          )}
          {asinList.map((a) => {
            const isActive = selectedAsin === a.asin;
            const stage = a.lifecycle_stage || "new_product";
            const colors = STAGE_COLORS[stage] || STAGE_COLORS.new_product;
            const Icon = STAGE_ICONS[stage] || Zap;
            return (
              <button
                key={a.asin}
                onClick={() => setSelectedAsin(isActive ? null : a.asin)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] transition-colors ${
                  isActive ? "bg-[#0071e3] text-white" : `${colors.bg} ${colors.color} hover:opacity-80`
                }`}
              >
                <Icon size={13} />
                {a.asin}
              </button>
            );
          })}
        </div>
      </div>

      {/* Loading */}
      {lcLoading && selectedAsin && (
        <div className="bg-white rounded-[20px] border border-[#d2d2d7] p-16 text-center">
          <div className="w-8 h-8 border-2 border-[#0071e3]/20 border-t-[#0071e3] rounded-full animate-spin mx-auto" />
        </div>
      )}

      {/* Lifecycle Stage Bar */}
      {lifecycle && (
        <div className="space-y-6">
          <KeywordGroupsCard asin={lifecycle.asin} groups={lifecycle.keyword_groups ?? []} />

          {/* Stage indicator */}
          <div className="bg-white rounded-[20px] border border-[#d2d2d7] p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-[12px] text-[#86868b] uppercase tracking-wide">当前阶段</p>
                <div className="flex items-center gap-2 mt-1">
                  {(() => {
                    const Icon = STAGE_ICONS[lifecycle.current_stage] || Zap;
                    const colors = STAGE_COLORS[lifecycle.current_stage] || STAGE_COLORS.new_product;
                    return <Icon size={22} className={colors.color} />;
                  })()}
                  <span className="text-[22px] font-bold">{lifecycle.stage_label}</span>
                </div>
              </div>
              <div className="text-right text-[13px] text-[#86868b]">
                <p>活跃 {lifecycle.days_active} 天</p>
                <p>{lifecycle.metrics.weeks_active} 周数据</p>
              </div>
            </div>

            {/* 4-stage progress bar */}
            <div className="flex items-center gap-0">
              {["new_product", "growth", "maturity", "decline"].map((stage, i) => {
                const isActive = lifecycle.current_stage === stage;
                const isPast = ["new_product", "growth", "maturity", "decline"].indexOf(lifecycle.current_stage) > i;
                const Icon = STAGE_ICONS[stage] || Zap;
                const colors = STAGE_COLORS[stage] || STAGE_COLORS.new_product;
                return (
                  <div key={stage} className="flex items-center flex-1">
                    <div className={`flex flex-col items-center ${isActive || isPast ? colors.color : "text-[#d2d2d7]"}`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                        isActive ? colors.bg + " ring-2 ring-offset-1 " + colors.color.replace("text-", "ring-") :
                        isPast ? colors.bg : "bg-[#f5f5f7]"
                      }`}>
                        <Icon size={14} />
                      </div>
                      <span className="text-[10px] mt-1 font-medium">
                        {stage === "new_product" ? "新品" : stage === "growth" ? "成长" : stage === "maturity" ? "成熟" : "衰退"}
                      </span>
                    </div>
                    {i < 3 && (
                      <div className={`flex-1 h-0.5 mx-1 rounded ${isPast ? colors.bg.replace("0.04", "0.20") : "bg-[#e8e8ed]"}`} />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Metrics snapshot */}
          {metrics && (
            <div className="grid grid-cols-4 gap-3">
              <MetricCard label="总订单" value={metrics.total_orders} />
              <MetricCard label="总花费" value={`$${metrics.total_spend}`} color="text-[#ff9500]" />
              <MetricCard label="ACoS" value={metrics.acos != null ? `${metrics.acos}%` : "—"} />
              <MetricCard
                label="周增长"
                value={metrics.weekly_order_growth_pct != null ? `${metrics.weekly_order_growth_pct > 0 ? "+" : ""}${metrics.weekly_order_growth_pct}%` : "—"}
                color={metrics.weekly_order_growth_pct != null && metrics.weekly_order_growth_pct > 0 ? "text-[#34c759]" : "text-[#ff3b30]"}
              />
            </div>
          )}

          {/* Ad Strategy */}
          {strategy && Object.keys(strategy).length > 0 && (
            <div className="bg-white rounded-[20px] border border-[#d2d2d7] p-6">
              <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">
                广告策略
              </h3>
              <div className="space-y-3">
                {Object.entries(strategy).map(([key, val]) => (
                  <div key={key} className="flex items-start gap-3 p-3 bg-[#f5f5f7] rounded-xl">
                    <Target size={16} className={STAGE_COLORS[lifecycle.current_stage]?.color || "text-[#0071e3]"} />
                    <div>
                      <p className="text-[12px] text-[#86868b]">
                        {key === "budget" ? "预算" :
                         key === "acos_target" ? "ACoS 目标" :
                         key === "keyword_strategy" ? "关键词策略" :
                         key === "bid_strategy" ? "出价策略" :
                         key === "focus" ? "核心目标" : key}
                      </p>
                      <p className="text-[14px] font-medium">{val}</p>
                    </div>
                  </div>
                ))}
              </div>

              <button
                onClick={() => setGuide({ asin: lifecycle.asin, strategy })}
                className="mt-5 apple-btn-primary w-full text-[14px] py-3 flex items-center justify-center gap-2"
              >
                <Target size={16} />
                查看字段
              </button>
            </div>
          )}

        </div>
      )}

      {/* Empty state */}
      {!selectedAsin && (
        <div className="bg-white rounded-[20px] border border-[#d2d2d7] p-16 text-center">
          <BarChart3 size={32} className="text-[#d2d2d7] mx-auto mb-3" />
          <p className="text-[15px] text-[#86868b]">选择一个 ASIN 查看生命周期和广告策略</p>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-[#1d1d1f] text-white px-5 py-3 rounded-xl text-[14px] shadow-lg z-50">
          <CheckCircle2 size={14} className="inline mr-2" />
          {toast}
        </div>
      )}

      {/* Setup Guide Modal */}
      {guide && (
        <SetupGuide
          asin={guide.asin}
          strategy={guide.strategy}
          stage={lifecycle?.stage_label || ""}
          onClose={() => setGuide(null)}
        />
      )}
    </div>
  );
}

function MetricCard({ label, value, color = "text-[#1d1d1f]" }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="bg-white rounded-[16px] border border-[#d2d2d7] p-4 text-center">
      <p className={`text-[20px] font-bold ${color}`}>{value}</p>
      <p className="text-[11px] text-[#86868b] mt-0.5">{label}</p>
    </div>
  );
}

function KeywordGroupsCard({
  asin,
  groups,
}: {
  asin: string;
  groups: LifecycleData["keyword_groups"];
}) {
  return (
    <div className="bg-white rounded-[20px] border border-[#d2d2d7] p-6">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide">
          ASIN 关键词列表
        </h3>
        <span className="text-[13px] font-semibold text-[#1d1d1f]">{asin}</span>
      </div>

      {groups.length === 0 ? (
        <p className="text-[13px] text-[#86868b]">暂无</p>
      ) : (
        <div className="space-y-4">
          {groups.map((group) => (
            <div key={group.group_name} className="p-4 bg-[#f5f5f7] rounded-xl">
              <div className="flex items-center justify-between gap-3 mb-3">
                <p className="text-[13px] font-semibold">{group.group_name}</p>
                <span className="text-[11px] text-[#86868b]">
                  {group.source_record_id ? group.source_type : "暂无"}
                </span>
              </div>
              {group.keywords.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {group.keywords.map((keyword) => (
                    <span
                      key={`${group.group_name}-${keyword}`}
                      className="px-2.5 py-1 rounded-full bg-white border border-[#d2d2d7]/60 text-[12px] text-[#1d1d1f]"
                    >
                      {keyword}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-[13px] text-[#86868b]">暂无</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SetupGuide({
  asin, strategy, stage, onClose,
}: {
  asin: string;
  strategy: Record<string, string>;
  stage: string;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/30 z-40 flex items-center justify-center" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl max-w-[480px] w-full mx-4" onClick={(e) => e.stopPropagation()}>
        <div className="p-5 border-b border-[#d2d2d7]/20">
          <div className="flex items-center gap-3 mb-1">
            <Target size={18} className="text-[#0071e3]" />
            <h2 className="text-[17px] font-semibold">{stage} · 广告字段</h2>
          </div>
          <p className="text-[13px] text-[#86868b]">ASIN: {asin}</p>
        </div>

        <div className="p-5 space-y-4">
          {Object.entries(strategy).map(([key, val]) => (
            <div key={key} className="flex items-center justify-between bg-[#f5f5f7] rounded-xl p-3">
              <span className="text-[13px] text-[#86868b]">
                {key === "budget" ? "预算" :
                 key === "acos_target" ? "ACoS 目标" :
                 key === "keyword_strategy" ? "关键词" :
                 key === "bid_strategy" ? "出价" :
                 key === "focus" ? "目标" : key}
              </span>
              <span className="text-[14px] font-semibold">{val}</span>
            </div>
          ))}
        </div>

        <div className="p-5 border-t border-[#d2d2d7]/20 flex gap-2 justify-end">
          <button onClick={onClose} className="apple-btn-secondary text-[14px] px-5 py-2">关闭</button>
        </div>
      </div>
    </div>
  );
}
