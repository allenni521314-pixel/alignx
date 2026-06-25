import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Route, TrendingUp, BarChart3, ArrowDown, Zap,
  Target, Search, Shield, DollarSign, AlertTriangle,
  Plus, ChevronRight, CheckCircle2, Play, Lightbulb,
} from "lucide-react";
import { listAsinProfiles, listValidationTasks, listConversionDiagnoses, API_BASE } from "@/lib/api";

/* ── Lifecycle stage config ── */

const STAGES: Record<string, { label: string; icon: React.ComponentType<{ size?: number }>; color: string; bg: string; strategies: Strategy[] }> = {
  prelaunch: {
    label: "新品", icon: Zap, color: "text-[#0071e3]", bg: "bg-[#0071e3]/[0.04]",
    strategies: [
      { name: "自动广告探索", goal: "获取首批曝光和搜索词数据", budget: "$15-30/天", props: ["P01-003"] },
      { name: "广泛匹配关键词", goal: "覆盖长尾搜索词，发现高转化词", budget: "$10-20/天", props: ["P01-001"] },
      { name: "Coupon 低价切入", goal: "快速积累销量和评论", budget: "Coupon 10-20%", props: ["P04-003"] },
      { name: "Vine 评论计划", goal: "突破0评论壁垒", budget: "免费", props: ["P05-004"] },
    ],
  },
  active: {
    label: "成长", icon: TrendingUp, color: "text-[#34c759]", bg: "bg-[#34c759]/[0.04]",
    strategies: [
      { name: "精准匹配关键词", goal: "抢占高转化搜索词排名", budget: "$30-50/天", props: ["P01-002"] },
      { name: "商品定位广告 SP", goal: "截流竞品页面流量", budget: "$20-40/天", props: ["P01-006"] },
      { name: "品牌广告 SB", goal: "强化品牌认知", budget: "$30-60/天", props: ["P05-005"] },
      { name: "展示型广告 SD", goal: "再营销和受众拓展", budget: "$15-30/天", props: ["P01-006"] },
    ],
  },
  mature: {
    label: "成熟", icon: Shield, color: "text-[#86868b]", bg: "bg-[#f5f5f7]",
    strategies: [
      { name: "ACoS 优化", goal: "降低广告成本提升利润", budget: "优化分配", props: ["P04-001"] },
      { name: "否定关键词", goal: "排除无效点击", budget: "$0", props: ["P01-001"] },
      { name: "品牌防御广告", goal: "保护品牌词不被截流", budget: "$10-20/天", props: ["P05-005"] },
      { name: "捆绑广告", goal: "提升客单价", budget: "$15-25/天", props: ["P04-006"] },
    ],
  },
  declining: {
    label: "衰退", icon: ArrowDown, color: "text-[#ff3b30]", bg: "bg-[#ff3b30]/[0.04]",
    strategies: [
      { name: "清仓促销", goal: "快速出清库存", budget: "Coupon 30-50%", props: ["P04-005"] },
      { name: "降低广告预算", goal: "只保留高ROI广告", budget: "逐步降至$5/天", props: ["P04-002"] },
      { name: "转投新品", goal: "预算转移到新品", budget: "重新分配", props: ["P07-003"] },
    ],
  },
};

type Strategy = { name: string; goal: string; budget: string; props: string[] };

export default function TrafficStrategy() {
  const queryClient = useQueryClient();
  const [activeStage, setActiveStage] = useState<string | null>("active");
  const [toast, setToast] = useState<string | null>(null);
  const [guide, setGuide] = useState<{ asin: string; strategy: Strategy } | null>(null);

  const { data: profiles } = useQuery({ queryKey: ["asin-profiles"], queryFn: listAsinProfiles });
  const { data: diagnoses } = useQuery({ queryKey: ["conversion-diagnoses"], queryFn: () => listConversionDiagnoses(1) });
  const { data: tasks } = useQuery({ queryKey: ["validation-tasks"], queryFn: () => listValidationTasks() });

  const asinList = profiles?.items ?? [];
  const taskList = tasks?.items ?? [];
  const diagList = diagnoses?.items ?? [];

  // Group ASINs by lifecycle
  const byStage: Record<string, typeof asinList> = {};
  asinList.forEach((a) => {
    const s = a.lifecycle_stage || "active";
    if (!byStage[s]) byStage[s] = [];
    byStage[s].push(a);
  });

  // Task count per ASIN
  const taskCounts = new Map<string, number>();
  taskList.forEach((t) => taskCounts.set(t.asin, (taskCounts.get(t.asin) || 0) + 1));

  // Build recommendations from diagnoses
  const recommendations = diagList
    .filter((d) => d.biggest_breakpoint || d.priority_action)
    .slice(0, 3);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  };

  const createTask = async (asin: string, strategy: Strategy) => {
    await fetch(`${API_BASE}/validation-tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        asin,
        proposition_code: strategy.props[0],
        proposition_name: strategy.name,
        source_module: "traffic_strategy",
        hypothesis_text: `执行"${strategy.name}"：${strategy.goal}`,
        validation_period: "14d",
      }),
    });
    queryClient.invalidateQueries({ queryKey: ["validation-tasks"] });
    showToast(`已为 ${asin} 创建：${strategy.name}`);
  };

  const currentStage = activeStage ? STAGES[activeStage] : null;
  const currentAsins = activeStage ? (byStage[activeStage] || []) : [];

  return (
    <div className="max-w-[840px] mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">执行测试</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          基于 ASIN 诊断推荐广告动作，一键创建验证任务
        </p>
      </div>

      {/* Recommendations from diagnoses */}
      {recommendations.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb size={16} className="text-[#ff9500]" />
            <h2 className="text-[14px] font-semibold text-[#86868b] uppercase tracking-wide">诊断建议</h2>
          </div>
          <div className="space-y-2">
            {recommendations.map((d, i) => (
              <div key={i} className="apple-card p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-[#ff9500]/[0.08] flex items-center justify-center">
                    <AlertTriangle size={16} className="text-[#ff9500]" />
                  </div>
                  <div>
                    <p className="text-[14px] font-medium">{d.asin}</p>
                    <p className="text-[13px] text-[#86868b]">
                      {d.biggest_breakpoint && `断点：${d.biggest_breakpoint}`}
                      {d.biggest_breakpoint && d.priority_action && " → "}
                      {d.priority_action?.slice(0, 60)}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => {
                    const stage = currentStage;
                    if (stage) createTask(d.asin, stage.strategies[0]);
                  }}
                  className="apple-btn-primary text-[12px] px-3 py-1.5 flex items-center gap-1 shrink-0"
                >
                  <Play size={12} />
                  执行建议
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Lifecycle stage tabs */}
      <div className="flex gap-2 mb-6">
        {Object.entries(STAGES).map(([key, stage]) => {
          const Icon = stage.icon;
          const count = (byStage[key] || []).length;
          const isActive = activeStage === key;
          return (
            <button
              key={key}
              onClick={() => setActiveStage(isActive ? null : key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-[14px] font-medium transition-colors ${
                isActive
                  ? `${stage.bg} ${stage.color}`
                  : "bg-[#f5f5f7] text-[#86868b] hover:bg-[#e8e8ed]"
              }`}
            >
              <Icon size={16} />
              {stage.label}期
              {count > 0 && (
                <span className={`text-[11px] px-1.5 py-0.5 rounded-full ${isActive ? "bg-white/60" : "bg-white"}`}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Strategy action cards */}
      {currentStage && (
        <div className="space-y-3">
          {currentStage.strategies.map((s, i) => (
            <div key={i} className="apple-card p-4 flex items-center gap-4 hover:shadow-sm transition-shadow">
              <div className={`w-9 h-9 rounded-xl ${currentStage.bg} flex items-center justify-center shrink-0`}>
                <Target size={16} className={currentStage.color} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[14px] font-semibold">{s.name}</p>
                <p className="text-[13px] text-[#86868b]">{s.goal}</p>
              </div>
              <div className="text-right shrink-0 hidden sm:block">
                <p className="text-[13px] text-[#ff9500] font-medium">{s.budget}</p>
                <p className="text-[11px] text-[#86868b]">{s.props.length} 命题</p>
              </div>
              <div className="flex items-center gap-2">
                {currentAsins.length > 0 ? (
                  currentAsins.slice(0, 2).map((a) => (
                    <button
                      key={a.asin}
                      onClick={() => setGuide({ asin: a.asin, strategy: s })}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-full text-[12px] bg-[#0071e3] text-white hover:bg-[#0077ed] transition-colors"
                    >
                      设置
                      <ChevronRight size={12} />
                    </button>
                  ))
                ) : (
                  <span className="text-[12px] text-[#86868b]">无 ASIN</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Active ASIN list */}
      {currentAsins.length > 0 && (
        <div className="mt-6">
          <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">
            {currentStage?.label}期 ASIN
          </h3>
          <div className="space-y-2">
            {currentAsins.map((a) => (
              <div key={a.asin} className="apple-card p-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-7 h-7 rounded-lg ${currentStage?.bg} flex items-center justify-center`}>
                    {currentStage && <currentStage.icon size={14} className={currentStage?.color} />}
                  </div>
                  <div>
                    <span className="text-[14px] font-medium">{a.asin}</span>
                    {a.product_title && (
                      <p className="text-[12px] text-[#86868b] truncate max-w-[280px]">{a.product_title}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3 text-[13px] text-[#86868b]">
                  <span>{taskCounts.get(a.asin) || 0} 任务</span>
                  <span>{a.total_validation_count || 0} 验证</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {asinList.length === 0 && (
        <div className="apple-card p-16 text-center">
          <Route size={32} className="text-[#d2d2d7] mx-auto mb-3" />
          <p className="text-[15px] text-[#86868b]">暂无 ASIN 数据</p>
          <p className="text-[13px] text-[#86868b]/60 mt-1">先完成承接转化诊断后自动关联</p>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-[#1d1d1f] text-white px-5 py-3 rounded-xl text-[14px] shadow-lg z-50 animate-bounce">
          <CheckCircle2 size={14} className="inline mr-2" />
          {toast}
        </div>
      )}

      {/* Setup Guide Modal */}
      {guide && (
        <SetupGuide
          guide={guide}
          onClose={() => setGuide(null)}
          onConfirm={(asin, s) => {
            createTask(asin, s);
            setGuide(null);
          }}
        />
      )}
    </div>
  );
}

/* ── Setup Guide Modal ── */

function SetupGuide({
  guide, onClose, onConfirm,
}: {
  guide: { asin: string; strategy: Strategy };
  onClose: () => void;
  onConfirm: (asin: string, s: Strategy) => void;
}) {
  const { asin, strategy: s } = guide;

  // Mock keyword generation based on strategy type
  const getKeywords = () => {
    const base = [asin.toLowerCase()];
    if (s.name.includes("精准")) return [...base, "best " + asin, asin + " review", "buy " + asin];
    if (s.name.includes("商品定位")) return ["Competitor ASINs: B0XXX, B0YYY", "Category: Pet Supplies"];
    if (s.name.includes("品牌")) return ["Brand: YourBrand", "Brand + category keywords"];
    if (s.name.includes("展示型")) return ["Viewed similar products", "Purchased similar products"];
    return ["Auto-generated keywords"];
  };

  const getSteps = () => [
    "打开 Amazon Advertising Console → Campaign Manager",
    `点击「创建广告活动」→ 选择「${s.name.includes("品牌") ? "品牌推广" : s.name.includes("展示") ? "展示型推广" : "商品推广"}」`,
    `设置每日预算：${s.budget}`,
    `添加关键词：${getKeywords().join("、")}`,
    `关联 ASIN：${asin}`,
    "启动广告活动",
  ];

  return (
    <div className="fixed inset-0 bg-black/30 z-40 flex items-center justify-center" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl max-w-[480px] w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="p-5 border-b border-[#d2d2d7]/20">
          <div className="flex items-center gap-3 mb-1">
            <Target size={18} className="text-[#0071e3]" />
            <h2 className="text-[17px] font-semibold">{s.name}</h2>
          </div>
          <p className="text-[13px] text-[#86868b]">{s.goal}</p>
        </div>

        {/* Content */}
        <div className="p-5 space-y-4">
          {/* Budget */}
          <div className="flex items-center justify-between bg-[#f5f5f7] rounded-xl p-3">
            <span className="text-[13px] text-[#86868b]">建议预算</span>
            <span className="text-[15px] font-semibold text-[#ff9500]">{s.budget}</span>
          </div>

          {/* Keywords */}
          <div>
            <p className="text-[13px] font-medium mb-2">推荐关键词</p>
            <div className="flex flex-wrap gap-1.5">
              {getKeywords().map((kw, i) => (
                <span key={i} className="px-2 py-1 bg-[#0071e3]/[0.06] text-[#0071e3] rounded-lg text-[12px]">
                  {kw}
                </span>
              ))}
            </div>
          </div>

          {/* Steps */}
          <div>
            <p className="text-[13px] font-medium mb-2">操作步骤</p>
            <div className="space-y-2">
              {getSteps().map((step, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="w-5 h-5 rounded-full bg-[#f5f5f7] text-[11px] font-medium flex items-center justify-center shrink-0 mt-0.5">
                    {i + 1}
                  </span>
                  <p className="text-[13px] text-[#86868b]">{step}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Tip */}
          <div className="bg-[#ff9500]/[0.06] rounded-xl p-3 flex items-start gap-2">
            <Lightbulb size={14} className="text-[#ff9500] shrink-0 mt-0.5" />
            <p className="text-[12px] text-[#86868b]">
              广告上线后回到 AlignX「经营验证」页面录入结果，系统会自动判断策略是否有效
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-5 border-t border-[#d2d2d7]/20 flex gap-2 justify-end">
          <button onClick={onClose} className="apple-btn-secondary text-[14px] px-5 py-2">关闭</button>
          <button
            onClick={() => onConfirm(asin, s)}
            className="apple-btn-primary text-[14px] px-5 py-2 flex items-center gap-1.5"
          >
            <CheckCircle2 size={16} />
            已设置，创建验证任务
          </button>
        </div>
      </div>
    </div>
  );
}
