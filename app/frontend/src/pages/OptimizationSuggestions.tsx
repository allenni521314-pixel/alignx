import { useEffect, useRef, useState } from "react";
import { AppSidebar } from "@/components/AppSidebar";
import { PageHeader } from "@/components/PageHeader";
import { NextStepActions } from "@/components/NextStepActions";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { getAuthHeaders } from "@/lib/auth-headers";
import { saveActionSnapshot } from "@/lib/workflow-api";
import {
  RotateCcw,
  AlertTriangle,
  Lightbulb,
  ArrowRight,
  CheckCircle2,
  Target,
  Database,
  ClipboardCheck,
} from "lucide-react";
import { useLocation } from "react-router-dom";

const mockSuggestions = [
  {
    problem: "除味主需求验证成立",
    reason: "DEMOAMZ001 在 cat litter box odor eliminator 和 ammonia odor remover 两组词上点击与转化同时达标，说明评论高频需求已被Listing承接。",
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
    text: "除味和氨气风险表达能提升 DEMOAMZ001 的点击确认和下单信任。",
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
    owner: "Listing 运营",
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
    owner: "Listing 运营",
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
    owner: "广告投放",
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
    owner: "Listing 运营",
    path: "/competitor-analysis?tab=strategy",
    cta: "进入竞品诊断",
    priority: "P2",
  },
];

export default function OptimizationSuggestions() {
  useRequireAuth();
  const location = useLocation();
  const view = new URLSearchParams(location.search).get("view") || "next-round";
  const savedViewRef = useRef("");
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

  useEffect(() => {
    const key = `${view}-${feedbackStats.rounds}-${feedbackStats.hitRate}-${feedbackStats.learnings}`;
    if (savedViewRef.current === key) return;
    savedViewRef.current = key;
    saveActionSnapshot({
      module_key: "optimization",
      module_name: "复盘优化",
      action_key: view,
      action_name: pageConfig.title,
      title: pageConfig.title,
      input_snapshot: {
        view,
        feedback_stats: feedbackStats,
      },
      output_snapshot: {
        page_config: pageConfig,
        feedback_records: view === "data-feedback" ? feedbackRecords : [],
        review_conclusions: view === "conclusion" ? reviewConclusions : [],
        next_round_actions: view === "next-round" ? nextRoundActions : [],
      },
      data_source: "workflow_records",
      confidence: feedbackStats.hitRate === "样本不足" ? "low" : "medium",
      ai_called: false,
      source_record_table: "action_snapshots",
    }).catch(() => {});
  }, [view, feedbackStats.rounds, feedbackStats.hitRate, feedbackStats.learnings, pageConfig.title]);

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto">
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

          {view === "data-feedback" && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              {[
                { label: "已回流轮次", value: String(feedbackStats.rounds), desc: "来自执行记录与优化时间线" },
                { label: "判断命中率", value: feedbackStats.hitRate, desc: "按广告点击和CVR验证判断是否成立" },
                { label: "可复用经验", value: `${feedbackStats.learnings}条`, desc: "按类目、价格带、关键词沉淀" },
              ].map((item) => (
                <Card key={item.label} className="bg-white border-gray-200 p-5">
                  <p className="text-xs text-gray-500">{item.label}</p>
                  <p className="text-xl font-bold text-gray-900 mt-1">{item.value}</p>
                  <p className="text-xs text-gray-500 mt-2">{item.desc}</p>
                </Card>
              ))}
            </div>
          )}

          {view === "conclusion" && (
            <Card className="bg-white border-gray-200 p-5 mb-6">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">本轮复盘结论</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {reviewConclusions.map((item) => (
                  <div key={item.label} className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                    <p className="text-[11px] font-semibold text-gray-500 mb-1">{item.label}</p>
                    <p className="text-sm text-gray-700">{item.text}</p>
                    <p className="text-xs text-brand-600 mt-2">{item.action}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {view === "data-feedback" && (
            <Card className="bg-white border-gray-200 mb-6 overflow-hidden">
              <div className="p-5 border-b border-gray-100">
                <h2 className="text-sm font-semibold text-gray-900">回流记录</h2>
                <p className="text-xs text-gray-500 mt-1">保存每一轮输入、修改、验证结果和命中状态，供下一次判断校准。</p>
              </div>
              <div className="divide-y divide-gray-100">
                {feedbackRecords.map((record) => (
                  <div key={`${record.source}-${record.item}`} className="p-4 grid lg:grid-cols-[0.9fr_1.1fr_1.1fr_1fr_auto] gap-3 items-start">
                    <div>
                      <p className="text-[11px] text-gray-400">来源</p>
                      <p className="text-sm font-semibold text-gray-900">{record.source}</p>
                      <p className="text-xs text-gray-500 mt-1">{record.item}</p>
                    </div>
                    <div>
                      <p className="text-[11px] text-gray-400">修改前</p>
                      <p className="text-sm text-gray-700">{record.before}</p>
                    </div>
                    <div>
                      <p className="text-[11px] text-gray-400">修改后/校准方向</p>
                      <p className="text-sm text-gray-700">{record.after}</p>
                    </div>
                    <div>
                      <p className="text-[11px] text-gray-400">验证指标</p>
                      <p className="text-sm text-gray-700">{record.metric}</p>
                    </div>
                    <Badge className={record.status === "命中" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-amber-50 text-amber-700 border-amber-200"}>
                      {record.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {view === "next-round" && (
            <div className="space-y-4">
              {nextRoundActions.map((item) => (
                <Card key={item.rank} className="bg-white border-gray-200 p-5">
                  <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div className="w-9 h-9 rounded-lg bg-brand-50 text-brand-700 flex items-center justify-center font-bold text-sm">
                        {item.rank}
                      </div>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-sm font-semibold text-gray-900">{item.title}</h3>
                          <Badge className="bg-red-50 text-red-600 border-red-200">{item.priority}</Badge>
                          <span className="text-[11px] text-gray-400">{item.owner}</span>
                        </div>
                        <p className="text-[11px] font-semibold text-brand-600 mt-2">{item.problemType}</p>
                        <p className="text-sm text-gray-600 mt-2">{item.reason}</p>
                        <p className="text-xs text-gray-500 mt-2">分流依据：{item.decisionBasis}</p>
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
                </Card>
              ))}
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
              {[
                "DEMOAMZ001 已回流至判断系统",
                "除味需求已回流至 Listing 优化建议",
                "广告验证结果已回流至下一轮测试优先级",
              ].map((text, i) => (
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
