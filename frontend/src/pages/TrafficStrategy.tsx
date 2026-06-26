import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDown,
  CheckCircle2,
  ChevronRight,
  Play,
  Route,
  Shield,
  Target,
  TrendingUp,
  Zap,
} from "lucide-react";
import {
  createExecutionRecord,
  createValidationTask,
  getLifecycle,
  listAsinProfiles,
  listConversionDiagnoses,
  listValidationTasks,
  type AsinProfile,
  type LifecycleData,
} from "@/lib/api";

type Strategy = {
  name: string;
  goal: string;
  budget: string;
  props: string[];
  changedVariable: string;
};

type StageConfig = {
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  color: string;
  bg: string;
  strategies: Strategy[];
};

const STAGES: Record<string, StageConfig> = {
  new_product: {
    label: "新品",
    icon: Zap,
    color: "text-[#0071e3]",
    bg: "bg-[#0071e3]/[0.04]",
    strategies: [
      { name: "自动广告探索", goal: "曝光和搜索词数据", budget: "$15-30/天", props: ["P01-003"], changedVariable: "广告关键词" },
      { name: "广泛匹配关键词", goal: "长尾搜索词", budget: "$10-20/天", props: ["P01-001"], changedVariable: "广告关键词" },
    ],
  },
  growth: {
    label: "成长",
    icon: TrendingUp,
    color: "text-[#34c759]",
    bg: "bg-[#34c759]/[0.04]",
    strategies: [
      { name: "精准匹配关键词", goal: "高转化搜索词排名", budget: "$30-50/天", props: ["P01-002"], changedVariable: "广告关键词" },
      { name: "商品定位广告 SP", goal: "竞品页面流量", budget: "$20-40/天", props: ["P01-006"], changedVariable: "广告投放对象" },
    ],
  },
  maturity: {
    label: "成熟",
    icon: Shield,
    color: "text-[#86868b]",
    bg: "bg-[#f5f5f7]",
    strategies: [
      { name: "ACoS 优化", goal: "广告成本", budget: "优化分配", props: ["P04-001"], changedVariable: "广告预算" },
      { name: "否定关键词", goal: "无效点击", budget: "$0", props: ["P01-001"], changedVariable: "否定关键词" },
    ],
  },
  decline: {
    label: "衰退",
    icon: ArrowDown,
    color: "text-[#ff3b30]",
    bg: "bg-[#ff3b30]/[0.04]",
    strategies: [
      { name: "降低广告预算", goal: "保留高 ROI 广告", budget: "逐步降低", props: ["P04-002"], changedVariable: "广告预算" },
    ],
  },
};

type KeywordSetup = {
  asin: string;
  strategy: Strategy;
};

export default function TrafficStrategy() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeStage, setActiveStage] = useState("growth");
  const [keywordSetup, setKeywordSetup] = useState<KeywordSetup | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const { data: profiles } = useQuery({ queryKey: ["asin-profiles"], queryFn: listAsinProfiles });
  const { data: diagnoses } = useQuery({ queryKey: ["conversion-diagnoses"], queryFn: () => listConversionDiagnoses(1) });
  const { data: tasks } = useQuery({ queryKey: ["validation-tasks"], queryFn: () => listValidationTasks() });

  const asinList = profiles?.items ?? [];
  const taskList = tasks?.items ?? [];
  const diagList = diagnoses?.items ?? [];

  const byStage = asinList.reduce<Record<string, AsinProfile[]>>((acc, item) => {
    const stage = item.lifecycle_stage || "growth";
    if (!acc[stage]) acc[stage] = [];
    acc[stage].push(item);
    return acc;
  }, {});

  const taskCounts = taskList.reduce<Map<string, number>>((acc, item) => {
    acc.set(item.asin, (acc.get(item.asin) || 0) + 1);
    return acc;
  }, new Map<string, number>());

  const recommendations = diagList
    .filter((item) => item.biggest_breakpoint || item.priority_action)
    .slice(0, 3);

  const currentStage = STAGES[activeStage] ?? STAGES.growth;
  const currentAsins = byStage[activeStage] ?? [];

  const showToast = (message: string) => {
    setToast(message);
    setTimeout(() => setToast(null), 2500);
  };

  const openKeywordSetup = (asin: string, strategy: Strategy) => {
    setKeywordSetup({ asin, strategy });
  };

  return (
    <div className="max-w-[840px] mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">广告测试</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">基于 ASIN 诊断推荐广告动作，一键创建验证任务</p>
      </div>

      {recommendations.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-3">
            <Zap size={16} className="text-[#ff9500]" />
            <h2 className="text-[14px] font-semibold text-[#86868b] uppercase tracking-wide">诊断建议</h2>
          </div>
          <div className="space-y-2">
            {recommendations.map((item) => (
              <div key={item.id} className="apple-card p-4 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-[#ff9500]/[0.08] flex items-center justify-center shrink-0">
                    <AlertTriangle size={16} className="text-[#ff9500]" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-[14px] font-medium">{item.asin}</p>
                    <p className="text-[13px] text-[#86868b] truncate">
                      {item.biggest_breakpoint || item.priority_action || "待录入"}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => openKeywordSetup(item.asin, STAGES.growth.strategies[0])}
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

      <div className="flex flex-wrap gap-2 mb-6">
        {Object.entries(STAGES).map(([key, stage]) => {
          const Icon = stage.icon;
          const count = (byStage[key] || []).length;
          const isActive = activeStage === key;
          return (
            <button
              key={key}
              onClick={() => setActiveStage(key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-[14px] font-medium transition-colors ${
                isActive ? `${stage.bg} ${stage.color}` : "bg-[#f5f5f7] text-[#86868b] hover:bg-[#e8e8ed]"
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

      <div className="space-y-3">
        {currentStage.strategies.map((strategy) => (
          <div key={strategy.name} className="apple-card p-4 flex items-center gap-4 hover:shadow-sm transition-shadow">
            <div className={`w-9 h-9 rounded-xl ${currentStage.bg} flex items-center justify-center shrink-0`}>
              <Target size={16} className={currentStage.color} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[14px] font-semibold">{strategy.name}</p>
              <p className="text-[13px] text-[#86868b]">{strategy.goal}</p>
            </div>
            <div className="text-right shrink-0 hidden sm:block">
              <p className="text-[13px] text-[#ff9500] font-medium">{strategy.budget}</p>
              <p className="text-[11px] text-[#86868b]">{strategy.props.length} 命题</p>
            </div>
            <div className="flex items-center gap-2">
              {currentAsins.length > 0 ? (
                currentAsins.slice(0, 3).map((item) => (
                  <button
                    key={`${strategy.name}-${item.asin}`}
                    onClick={() => openKeywordSetup(item.asin, strategy)}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-full text-[12px] bg-[#0071e3] text-white hover:bg-[#0077ed] transition-colors"
                  >
                    {item.asin}
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

      {currentAsins.length > 0 && (
        <div className="mt-6">
          <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">
            {currentStage.label}期 ASIN
          </h3>
          <div className="space-y-2">
            {currentAsins.map((item) => (
              <div key={item.asin} className="apple-card p-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`w-7 h-7 rounded-lg ${currentStage.bg} flex items-center justify-center shrink-0`}>
                    <currentStage.icon size={14} className={currentStage.color} />
                  </div>
                  <div className="min-w-0">
                    <span className="text-[14px] font-medium">{item.asin}</span>
                    {item.product_title && (
                      <p className="text-[12px] text-[#86868b] truncate max-w-[360px]">{item.product_title}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3 text-[13px] text-[#86868b] shrink-0">
                  <span>{taskCounts.get(item.asin) || 0} 任务</span>
                  <span>{item.total_validation_count || 0} 验证</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {asinList.length === 0 && (
        <div className="apple-card p-16 text-center mt-6">
          <Route size={32} className="text-[#d2d2d7] mx-auto mb-3" />
          <p className="text-[15px] text-[#86868b]">暂无 ASIN 数据</p>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-[#1d1d1f] text-white px-5 py-3 rounded-xl text-[14px] shadow-lg z-50">
          <CheckCircle2 size={14} className="inline mr-2" />
          {toast}
        </div>
      )}

      {keywordSetup && (
        <KeywordSetupModal
          setup={keywordSetup}
          onClose={() => setKeywordSetup(null)}
          onDone={(taskId) => {
            queryClient.invalidateQueries({ queryKey: ["validation-tasks"] });
            setKeywordSetup(null);
            showToast("已进入广告执行");
            navigate(`/execution-records?validation_task_id=${taskId}`);
          }}
        />
      )}
    </div>
  );
}

function KeywordSetupModal({
  setup,
  onClose,
  onDone,
}: {
  setup: KeywordSetup;
  onClose: () => void;
  onDone: (taskId: string) => void;
}) {
  const [extraKeywords, setExtraKeywords] = useState("");
  const [selectedKeywords, setSelectedKeywords] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const { data, isLoading } = useQuery<LifecycleData>({
    queryKey: ["lifecycle", setup.asin],
    queryFn: () => getLifecycle(setup.asin),
  });

  const sourceKeywords = uniqueKeywords(
    (data?.keyword_groups ?? []).flatMap((group) => group.keywords ?? []),
  );
  const manualKeywords = uniqueKeywords(extraKeywords.split(/[\n,，]/).map((item) => item.trim()));
  const keywords = uniqueKeywords([...selectedKeywords, ...manualKeywords]);

  const toggleKeyword = (keyword: string) => {
    setSelectedKeywords((current) =>
      current.includes(keyword) ? current.filter((item) => item !== keyword) : [...current, keyword],
    );
  };

  const enterAdExecution = async () => {
    if (keywords.length === 0) return;
    setSubmitting(true);
    try {
      const task = await createValidationTask({
        asin: setup.asin,
        proposition_code: setup.strategy.props[0],
        proposition_name: setup.strategy.name,
        source_module: "traffic_strategy",
        hypothesis_text: `${setup.strategy.name}：${setup.strategy.goal}`,
        controlled_variable: setup.strategy.changedVariable,
        validation_period: "14d",
        evidence_snapshot: {
          asin: setup.asin,
          strategy_name: setup.strategy.name,
          keywords,
          keyword_source: "lifecycle.keyword_groups",
        },
      });
      await createExecutionRecord({
        validation_task_id: task.id,
        asin: setup.asin,
        action_summary: setup.strategy.name,
        changed_variable: setup.strategy.changedVariable,
        changed_position: "广告关键词",
        change_detail: keywords.join(", "),
        evidence_note: "keywords",
      });
      onDone(task.id);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/30 z-40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl max-w-[680px] w-full" onClick={(event) => event.stopPropagation()}>
        <div className="p-5 border-b border-[#d2d2d7]/20">
          <div className="flex items-center gap-3 mb-1">
            <Target size={18} className="text-[#0071e3]" />
            <h2 className="text-[17px] font-semibold">{setup.strategy.name}</h2>
          </div>
          <p className="text-[13px] text-[#86868b]">{setup.asin}</p>
        </div>

        <div className="p-5 space-y-5">
          <div>
            <p className="text-[13px] font-semibold text-[#86868b] mb-3">ASIN 关键词列表</p>
            {isLoading ? (
              <p className="text-[13px] text-[#86868b]">加载中</p>
            ) : sourceKeywords.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {sourceKeywords.map((keyword) => {
                  const active = selectedKeywords.includes(keyword);
                  return (
                    <button
                      key={keyword}
                      onClick={() => toggleKeyword(keyword)}
                      className={`px-3 py-1.5 rounded-full border text-[12px] transition-colors ${
                        active
                          ? "bg-[#0071e3] border-[#0071e3] text-white"
                          : "bg-white border-[#d2d2d7] text-[#1d1d1f]"
                      }`}
                    >
                      {keyword}
                    </button>
                  );
                })}
              </div>
            ) : (
              <p className="text-[13px] text-[#86868b]">暂无</p>
            )}
          </div>

          <div>
            <label className="block text-[13px] font-semibold text-[#86868b] mb-2">补齐关键词</label>
            <textarea
              value={extraKeywords}
              onChange={(event) => setExtraKeywords(event.target.value)}
              className="apple-input min-h-[88px] resize-none"
              placeholder="待录入"
            />
          </div>

          <div className="bg-[#f5f5f7] rounded-xl p-4">
            <p className="text-[12px] text-[#86868b] mb-2">已选择关键词</p>
            {keywords.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {keywords.map((keyword) => (
                  <span key={keyword} className="px-2.5 py-1 rounded-full bg-white text-[12px] text-[#1d1d1f]">
                    {keyword}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-[13px] text-[#86868b]">暂无</p>
            )}
          </div>
        </div>

        <div className="p-5 border-t border-[#d2d2d7]/20 flex gap-2 justify-end">
          <button onClick={onClose} className="apple-btn-secondary text-[14px] px-5 py-2">关闭</button>
          <button
            onClick={enterAdExecution}
            disabled={submitting || keywords.length === 0}
            className="apple-btn-primary text-[14px] px-5 py-2 disabled:opacity-50"
          >
            {submitting ? "处理中" : "进入广告执行"}
          </button>
        </div>
      </div>
    </div>
  );
}

function uniqueKeywords(items: string[]) {
  return Array.from(new Set(items.map((item) => item.trim()).filter(Boolean)));
}
