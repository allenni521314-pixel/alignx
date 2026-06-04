import { AppSidebar } from "@/components/AppSidebar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type React from "react";
import { useEffect, useState } from "react";
import { getAuthHeaders } from "@/lib/auth-headers";
import { getActionSnapshots, saveActionSnapshot, type ActionSnapshot } from "@/lib/workflow-api";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { useLocation } from "react-router-dom";
import {
  Activity,
  BarChart3,
  Gauge,
  Megaphone,
  Route,
  Target,
  WalletCards,
} from "lucide-react";

interface AdvertisingStrategySchema {
  current_ad_status: {
    product_stage: string;
    product_type: string;
    budget_level: string;
    ad_health_grade: string;
  };
  recommended_ad_path: Array<{ channel: string; ratio: string }>;
  campaign_matrix: Array<{ campaign_type: string; recommendation_grade: string }>;
  placement_strategy: Array<{ placement: string; ratio: string }>;
  bid_strategy: {
    fixed_bid: string;
    dynamic_down: string;
    dynamic_up: string;
    dynamic_up_down: string;
    recommended: string;
  };
  budget_allocation: Array<{ budget_type: string; amount: string; ratio: string }>;
  validation_goal: {
    goal_type: string;
    ctr_target: string;
    cvr_target: string;
    acos_target: string;
    roi_target: string;
    validation_period: string;
  };
  biggest_waste: string;
  next_best_action: string;
  expected_outcome: {
    ctr_lift: string;
    cvr_lift: string;
    acos_improvement: string;
    roi_improvement: string;
  };
}

interface AdvertisingStrategyInput {
  product_stage: string;
  product_type: string;
  budget_level: string;
  ad_validation_result: Record<string, unknown>;
  proof_score: number;
  competition_structure: Record<string, unknown>;
}

const defaultInput: AdvertisingStrategyInput = {
  product_stage: "待录入",
  product_type: "待录入",
  budget_level: "待录入",
  ad_validation_result: {},
  proof_score: 0,
  competition_structure: {},
};

const defaultStrategy: AdvertisingStrategySchema = {
  current_ad_status: {
    product_stage: "待录入",
    product_type: "待录入",
    budget_level: "待录入",
    ad_health_grade: "未设置",
  },
  recommended_ad_path: [
    { channel: "自动广告", ratio: "未设置" },
    { channel: "精准关键词", ratio: "未设置" },
    { channel: "场景关键词", ratio: "未设置" },
    { channel: "竞品ASIN", ratio: "未设置" },
  ],
  campaign_matrix: [
    { campaign_type: "自动广告", recommendation_grade: "未设置" },
    { campaign_type: "精准匹配", recommendation_grade: "未设置" },
    { campaign_type: "词组匹配", recommendation_grade: "未设置" },
    { campaign_type: "广泛匹配", recommendation_grade: "未设置" },
    { campaign_type: "ASIN投放", recommendation_grade: "未设置" },
    { campaign_type: "品类投放", recommendation_grade: "未设置" },
    { campaign_type: "品牌广告", recommendation_grade: "未设置" },
    { campaign_type: "展示广告", recommendation_grade: "未设置" },
  ],
  placement_strategy: [
    { placement: "首页顶部", ratio: "未设置" },
    { placement: "搜索中部", ratio: "未设置" },
    { placement: "搜索底部", ratio: "未设置" },
    { placement: "竞品详情页", ratio: "未设置" },
    { placement: "关联商品页", ratio: "未设置" },
  ],
  bid_strategy: {
    fixed_bid: "未设置",
    dynamic_down: "未设置",
    dynamic_up: "未设置",
    dynamic_up_down: "未设置",
    recommended: "未设置",
  },
  budget_allocation: [
    { budget_type: "测试预算", amount: "未设置", ratio: "未设置" },
    { budget_type: "验证预算", amount: "未设置", ratio: "未设置" },
    { budget_type: "放量预算", amount: "未设置", ratio: "未设置" },
    { budget_type: "防守预算", amount: "未设置", ratio: "未设置" },
  ],
  validation_goal: {
    goal_type: "未设置",
    ctr_target: "未设置",
    cvr_target: "未设置",
    acos_target: "未设置",
    roi_target: "未设置",
    validation_period: "未设置",
  },
  biggest_waste: "暂无",
  next_best_action: "暂无",
  expected_outcome: {
    ctr_lift: "未设置",
    cvr_lift: "未设置",
    acos_improvement: "未设置",
    roi_improvement: "未设置",
  },
};

const validationGoals = ["需求验证", "卖点验证", "Listing验证", "ROI验证"];

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <Card className="border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <Icon className="h-4 w-4 text-brand-700" />
        <h2 className="text-sm font-bold text-gray-950">{title}</h2>
      </div>
      {children}
    </Card>
  );
}

function Field({ label, value = "待录入" }: { label: string; value?: string }) {
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2.5">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-gray-900">{value || "待录入"}</p>
    </div>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-500">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm font-semibold text-gray-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function AdvertisingStrategy() {
  const location = useLocation();
  const { loading: authLoading } = useRequireAuth();
  const [strategy, setStrategy] = useState<AdvertisingStrategySchema>(defaultStrategy);
  const [input, setInput] = useState<AdvertisingStrategyInput>(defaultInput);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "failed">("loading");
  const [upstreamState, setUpstreamState] = useState<"idle" | "loading" | "ready" | "empty" | "failed">("idle");
  const [upstreamSnapshot, setUpstreamSnapshot] = useState<ActionSnapshot | null>(null);
  const [evaluateState, setEvaluateState] = useState<"idle" | "running" | "done" | "failed">("idle");

  const evaluateStrategy = async (
    payload: AdvertisingStrategyInput = input,
    sourceSnapshot: ActionSnapshot | null = upstreamSnapshot,
  ) => {
    setEvaluateState("running");
    try {
      const res = await fetch("/api/v1/advertising-strategy/evaluate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeaders(),
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("生成失败");
      const data = await res.json();
      setStrategy({ ...defaultStrategy, ...data });
      const search = new URLSearchParams(location.search);
      const productId = Number(search.get("product_id") || 0);
      await saveActionSnapshot({
        module_key: "advertising_strategy",
        module_name: "广告策略",
        action_key: "generate_ad_strategy",
        action_name: "广告策略",
        product_id: productId || null,
        asin: sourceSnapshot?.asin || "",
        title: sourceSnapshot?.title || "",
        input_snapshot: payload,
        output_snapshot: data,
        data_source: "ad_validation",
        confidence: sourceSnapshot?.confidence || "",
        ai_called: false,
        source_record_table: "action_snapshots",
        source_record_id: sourceSnapshot?.id || null,
      });
      setEvaluateState("done");
    } catch {
      setEvaluateState("failed");
    }
  };

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    const loadSchema = async () => {
      setLoadState("loading");
      try {
        const res = await fetch("/api/v1/advertising-strategy/schema", {
          headers: getAuthHeaders(),
        });
        if (!res.ok) throw new Error("加载失败");
        const data = await res.json();
        if (!cancelled) {
          setStrategy({ ...defaultStrategy, ...data });
          setLoadState("ready");
        }
      } catch {
        if (!cancelled) {
          setStrategy(defaultStrategy);
          setLoadState("failed");
        }
      }
    };
    void loadSchema();
    return () => {
      cancelled = true;
    };
  }, [authLoading]);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    const loadUpstream = async () => {
      setUpstreamState("loading");
      try {
        const search = new URLSearchParams(location.search);
        const productId = Number(search.get("product_id") || 0);
        const snapshots = await getActionSnapshots({
          module_key: "ad_analytics",
          action_key: "validate_ad_effect",
          product_id: productId || undefined,
          limit: 1,
        });
        const snapshot = snapshots[0] || null;
        if (cancelled) return;
        setUpstreamSnapshot(snapshot);
        if (!snapshot) {
          setUpstreamState("empty");
          return;
        }
        const nextInput = {
          ...defaultInput,
          ad_validation_result: {
            input_snapshot: snapshot.input_snapshot || {},
            output_snapshot: snapshot.output_snapshot || {},
          },
          proof_score: 0,
          competition_structure: {},
        };
        setInput(nextInput);
        setUpstreamState("ready");
        await evaluateStrategy(nextInput, snapshot);
      } catch {
        if (!cancelled) setUpstreamState("failed");
      }
    };
    void loadUpstream();
    return () => {
      cancelled = true;
    };
  }, [authLoading, location.search]);

  if (authLoading) return null;

  const updateInput = (key: keyof AdvertisingStrategyInput, value: string) => {
    setInput((current) => ({ ...current, [key]: value }));
  };

  const statusItems = [
    ["产品阶段", strategy.current_ad_status.product_stage],
    ["产品类型", strategy.current_ad_status.product_type],
    ["预算等级", strategy.current_ad_status.budget_level],
    ["当前广告健康度", strategy.current_ad_status.ad_health_grade],
  ];

  return (
    <div className="flex h-screen bg-[#f5f5f7] text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto bg-[#f5f5f7]">
        <div className="mx-auto max-w-7xl p-4 pt-14 md:p-6">
          <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="flex items-center gap-2 text-xl font-bold sm:text-2xl">
                <Megaphone className="h-5 w-5 text-amber-600 sm:h-6 sm:w-6" />
                广告策略中心
              </h1>
            </div>
            <span className="text-xs font-medium text-gray-500">
              {evaluateState === "running"
                ? "正在生成"
                : evaluateState === "failed"
                  ? "生成失败"
                  : evaluateState === "done"
                    ? "已生成"
                    : loadState === "loading"
                      ? "正在加载"
                      : loadState === "failed"
                        ? "加载失败"
                        : "已加载"}
            </span>
          </div>

          <Card className="mb-4 border-gray-200 bg-white p-4 shadow-sm">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_1fr_1fr_auto] md:items-end">
              <SelectField
                label="产品阶段"
                value={input.product_stage}
                options={["待录入", "新品", "成长", "成熟", "衰退"]}
                onChange={(value) => updateInput("product_stage", value)}
              />
              <SelectField
                label="产品类型"
                value={input.product_type}
                options={["待录入", "标品", "半标品", "非标品"]}
                onChange={(value) => updateInput("product_type", value)}
              />
              <SelectField
                label="预算等级"
                value={input.budget_level}
                options={["待录入", "低", "中", "高"]}
                onChange={(value) => updateInput("budget_level", value)}
              />
              <Button
                type="button"
                onClick={() => evaluateStrategy()}
                disabled={evaluateState === "running"}
                className="h-10 bg-brand-700 px-5 text-sm font-semibold text-white hover:bg-brand-800"
              >
                生成策略
              </Button>
            </div>
          </Card>

          <Card className="mb-4 border-gray-200 bg-white p-4 shadow-sm">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Field
                label="广告验证结果"
                value={
                  upstreamState === "loading"
                    ? "正在加载"
                    : upstreamState === "ready"
                      ? "已同步"
                      : upstreamState === "failed"
                        ? "加载失败"
                        : "暂无"
                }
              />
              <Field label="Proof Score" value={input.proof_score ? String(input.proof_score) : "未设置"} />
              <Field
                label="竞争结构"
                value={Object.keys(input.competition_structure || {}).length ? "已同步" : "未设置"}
              />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                className="border-gray-200 bg-white text-sm"
                onClick={() => window.location.reload()}
              >
                同步上游数据
              </Button>
              <span className="text-xs font-medium text-gray-400">
                {upstreamSnapshot?.created_at || "暂无"}
              </span>
            </div>
          </Card>

          <Section title="Current Ad Status" icon={Activity}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {statusItems.map(([label, value]) => (
                <Field key={label} label={label} value={value} />
              ))}
            </div>
          </Section>

          <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Section title="Recommended Ad Path" icon={Route}>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {strategy.recommended_ad_path.map((item) => (
                  <Field key={item.channel} label={item.channel} value={item.ratio} />
                ))}
              </div>
            </Section>

            <Section title="Campaign Matrix" icon={BarChart3}>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {strategy.campaign_matrix.map((item) => (
                  <Field key={item.campaign_type} label={item.campaign_type} value={item.recommendation_grade} />
                ))}
              </div>
            </Section>

            <Section title="Placement Strategy" icon={Target}>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {strategy.placement_strategy.map((item) => (
                  <Field key={item.placement} label={item.placement} value={item.ratio} />
                ))}
              </div>
            </Section>

            <Section title="Bid Strategy" icon={Gauge}>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <Field label="固定竞价" value={strategy.bid_strategy.fixed_bid} />
                <Field label="动态降低" value={strategy.bid_strategy.dynamic_down} />
                <Field label="动态提高" value={strategy.bid_strategy.dynamic_up} />
                <Field label="动态升降" value={strategy.bid_strategy.dynamic_up_down} />
              </div>
            </Section>

            <Section title="Budget Allocation" icon={WalletCards}>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {strategy.budget_allocation.map((item) => (
                  <div key={item.budget_type} className="grid grid-cols-2 gap-2">
                    <Field label={item.budget_type} value={item.amount} />
                    <Field label="比例" value={item.ratio} />
                  </div>
                ))}
              </div>
            </Section>

            <Section title="Validation Goal" icon={Target}>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {validationGoals.map((item) => (
                  <Field key={item} label={item} value={strategy.validation_goal.goal_type === item ? item : "未设置"} />
                ))}
                <Field label="CTR目标" value={strategy.validation_goal.ctr_target} />
                <Field label="CVR目标" value={strategy.validation_goal.cvr_target} />
                <Field label="ACOS目标" value={strategy.validation_goal.acos_target} />
                <Field label="ROI目标" value={strategy.validation_goal.roi_target} />
                <Field label="验证周期" value={strategy.validation_goal.validation_period} />
              </div>
            </Section>

            <Section title="Biggest Waste" icon={Activity}>
              <Field label="最大浪费点" value={strategy.biggest_waste} />
            </Section>

            <Section title="Next Best Action" icon={Target}>
              <Field label="最佳动作" value={strategy.next_best_action} />
            </Section>

            <Section title="Expected Outcome" icon={BarChart3}>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <Field label="预计CTR提升" value={strategy.expected_outcome.ctr_lift} />
                <Field label="预计CVR提升" value={strategy.expected_outcome.cvr_lift} />
                <Field label="预计ACOS改善" value={strategy.expected_outcome.acos_improvement} />
                <Field label="预计ROI改善" value={strategy.expected_outcome.roi_improvement} />
              </div>
            </Section>
          </div>

          <Card className="mt-4 border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <Field label="策略快照" value={evaluateState === "done" ? "已保存" : "暂无"} />
                <Field label="下一步" value="数据回流" />
              </div>
              <Button asChild className="h-10 bg-brand-700 px-5 text-sm font-semibold text-white hover:bg-brand-800">
                <a href="/optimization-suggestions?view=data-feedback">进入数据回流</a>
              </Button>
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}
