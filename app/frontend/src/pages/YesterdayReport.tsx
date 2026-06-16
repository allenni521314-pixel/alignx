import { useCallback, useEffect, useMemo, useState } from "react";
import { AppSidebar } from "@/components/AppSidebar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { getAPIBaseURL } from "@/lib/config";
import { getAuthHeaders } from "@/lib/auth-headers";
import { AlertTriangle, ClipboardCheck, RefreshCw } from "lucide-react";

const EMPTY = "暂无";
const UNKNOWN = "数据不足，不能判断";

interface MetricCard {
  label: string;
  value: string;
  previous_day: string;
  seven_day_avg: string;
}

interface KeyChange {
  metric: string;
  yesterday: string;
  previous_day: string;
  seven_day_avg: string;
  change: string;
}

interface CauseJudgment {
  phenomenon: string;
  possible_reason: string;
  evidence: string;
  confidence: string;
}

interface ValidationAction {
  action: string;
  expected_target: string;
  actual_result: string;
  conclusion: string;
  next_action: string;
  target: string;
  executor: string;
  validation_cycle: string;
  execution_id: string;
}

interface PriorityItem {
  action: string;
  target: string;
  expected_impact: string;
  risk_note: string;
  observation_cycle: string;
}

interface RiskWarning {
  risk: string;
  evidence: string;
  status: string;
}

interface YesterdayReportData {
  report_date: string;
  generated_at: string;
  data_mode?: string;
  overview: {
    result_judgment: string;
    metrics: MetricCard[];
  };
  key_changes: KeyChange[];
  cause_judgments: CauseJudgment[];
  validation_actions: ValidationAction[];
  today_priorities: Record<"A类" | "B类" | "C类", PriorityItem[]>;
  risk_warnings: RiskWarning[];
  final_conclusion: {
    largest_problem: string;
    most_important_action: string;
    product_status: string;
  };
  data_coverage: {
    sales_days: number;
    ad_days: number;
    validation_actions: number;
    product_count: number;
  };
}

function valueOrEmpty(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return EMPTY;
  return String(value);
}

function isUnknown(value?: string | number | null) {
  const text = valueOrEmpty(value);
  return text === UNKNOWN || text === EMPTY || text === "待录入" || text === "未设置";
}

function buildEmptyReport(): YesterdayReportData {
  const metrics = [
    "销售额",
    "订单量",
    "广告花费",
    "广告销售额",
    "自然销售额",
    "ACOS",
    "TACOS",
    "CTR",
    "CVR",
    "Sessions",
    "利润/毛利率",
    "库存可售天数",
  ];

  return {
    report_date: EMPTY,
    generated_at: EMPTY,
    data_mode: EMPTY,
    overview: {
      result_judgment: UNKNOWN,
      metrics: metrics.map((label) => ({
        label,
        value: UNKNOWN,
        previous_day: UNKNOWN,
        seven_day_avg: UNKNOWN,
      })),
    },
    key_changes: [],
    cause_judgments: [],
    validation_actions: [],
    today_priorities: {
      A类: [],
      B类: [],
      C类: [],
    },
    risk_warnings: [],
    final_conclusion: {
      largest_problem: UNKNOWN,
      most_important_action: UNKNOWN,
      product_status: UNKNOWN,
    },
    data_coverage: {
      sales_days: 0,
      ad_days: 0,
      validation_actions: 0,
      product_count: 0,
    },
  };
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="text-[15px] font-semibold text-gray-950">{title}</h2>
      <div className="mt-3">{children}</div>
    </Card>
  );
}

function EmptyState() {
  return <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-4 py-6 text-center text-[13px] text-gray-500">{EMPTY}</div>;
}

export default function YesterdayReport() {
  const { loading: authLoading } = useRequireAuth();
  const [data, setData] = useState<YesterdayReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadReport = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${getAPIBaseURL()}/api/v1/yesterday-report`, {
        headers: getAuthHeaders(),
      });
      if (!response.ok) throw new Error("加载失败");
      setData(await response.json());
    } catch {
      setData(buildEmptyReport());
      setError("");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading) void loadReport();
  }, [authLoading, loadReport]);

  const priorityGroups = useMemo(() => ["A类", "B类", "C类"] as const, []);

  return (
    <div className="flex h-screen bg-background text-foreground">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto bg-[#f5f5f7]">
        <div className="mx-auto max-w-6xl px-4 py-5 pt-14 sm:px-6 md:pt-6">
          <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white text-brand-700 ring-1 ring-gray-200">
                <ClipboardCheck className="h-4 w-4" />
              </div>
              <div>
                <h1 className="text-[22px] font-semibold tracking-normal text-gray-950">昨日战报</h1>
                <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[13px] text-gray-500">
                  <span>{data?.report_date || EMPTY}</span>
                  {data?.data_mode && <Badge variant="outline" className="h-5 rounded-md px-1.5 text-[11px]">{data.data_mode}</Badge>}
                </div>
              </div>
            </div>
            <Button variant="outline" onClick={loadReport} disabled={loading} className="h-9 gap-2 px-4 text-[13px]">
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              刷新
            </Button>
          </div>

          {error && (
            <Card className="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-[13px] text-red-700">
              {error}
            </Card>
          )}

          {loading && !data ? (
            <Card className="rounded-xl border border-gray-200 bg-white p-6 text-center text-[13px] text-gray-500">加载中</Card>
          ) : data ? (
            <div className="space-y-4">
              <Card className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                <div className="grid gap-3 md:grid-cols-5">
                  <div>
                    <p className="text-[13px] font-medium text-gray-500">昨日结果</p>
                    <p className={`mt-1.5 text-[17px] font-semibold ${isUnknown(data.overview.result_judgment) ? "text-gray-500" : "text-brand-700"}`}>
                      {data.overview.result_judgment}
                    </p>
                  </div>
                  <div>
                    <p className="text-[13px] font-medium text-gray-500">销售数据</p>
                    <p className="mt-1.5 text-[17px] font-semibold text-gray-950">{data.data_coverage.sales_days}</p>
                  </div>
                  <div>
                    <p className="text-[13px] font-medium text-gray-500">广告数据</p>
                    <p className="mt-1.5 text-[17px] font-semibold text-gray-950">{data.data_coverage.ad_days}</p>
                  </div>
                  <div>
                    <p className="text-[13px] font-medium text-gray-500">验证动作</p>
                    <p className="mt-1.5 text-[17px] font-semibold text-gray-950">{data.data_coverage.validation_actions}</p>
                  </div>
                  <div>
                    <p className="text-[13px] font-medium text-gray-500">商品</p>
                    <p className="mt-1.5 text-[17px] font-semibold text-gray-950">{data.data_coverage.product_count}</p>
                  </div>
                </div>
              </Card>

              <Section title="一、昨日经营概览">
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {data.overview.metrics.map((metric) => (
                    <div key={metric.label} className="rounded-lg border border-gray-200 bg-[#FFFCF7] p-3">
                      <p className="notranslate text-[13px] font-medium text-gray-500" translate="no">{metric.label}</p>
                      {!isUnknown(metric.value) && (
                        <p className="mt-1.5 text-[17px] font-semibold text-gray-950">{metric.value}</p>
                      )}
                      <div className="mt-2 grid grid-cols-2 gap-2 text-xs leading-5 text-gray-500">
                        <span>前一日：{metric.previous_day}</span>
                        <span>近7日：{metric.seven_day_avg}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </Section>

              <Section title="二、关键变化">
                {data.key_changes.length ? (
                  <div className="space-y-2">
                    {data.key_changes.map((item) => (
                      <div key={item.metric} className="grid gap-3 rounded-lg border border-gray-200 p-3 text-[13px] leading-6 text-gray-600 md:grid-cols-5">
                        <strong className="notranslate font-semibold text-gray-950" translate="no">{item.metric}</strong>
                        <span>昨日：{item.yesterday}</span>
                        <span>前一日：{item.previous_day}</span>
                        <span>近7日：{item.seven_day_avg}</span>
                        <span>变化：{item.change}</span>
                      </div>
                    ))}
                  </div>
                ) : <EmptyState />}
              </Section>

              <Section title="三、原因判断">
                {data.cause_judgments.length ? (
                  <div className="space-y-3">
                    {data.cause_judgments.map((item, index) => (
                      <div key={`${item.phenomenon}-${index}`} className="rounded-lg border border-gray-200 p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <strong className="text-[13px] font-semibold text-gray-950">{item.phenomenon}</strong>
                          <Badge variant="outline">{item.confidence}</Badge>
                        </div>
                        <div className="mt-2 grid gap-2 text-[13px] leading-6 text-gray-600 md:grid-cols-2">
                          <p>可能原因：{item.possible_reason}</p>
                          <p>证据：{item.evidence}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : <EmptyState />}
              </Section>

              <Section title="四、昨日验证动作结果">
                {data.validation_actions.length ? (
                  <div className="space-y-3">
                    {data.validation_actions.map((item) => (
                      <div key={item.execution_id} className="rounded-lg border border-gray-200 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <strong className="text-[13px] font-semibold text-gray-950">{item.execution_id}</strong>
                          <Badge variant="outline">{item.conclusion}</Badge>
                        </div>
                        <div className="mt-2 grid gap-2 text-[13px] leading-6 text-gray-600 md:grid-cols-2">
                          <p>验证动作：{item.action}</p>
                          <p>预期目标：{item.expected_target}</p>
                          <p>实际结果：{item.actual_result}</p>
                          <p>下一步动作：{item.next_action}</p>
                          <p>执行对象：{item.target}</p>
                          <p>验证周期：{item.validation_cycle}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : <EmptyState />}
              </Section>

              <Section title="五、今日优先决策">
                <div className="grid gap-3 lg:grid-cols-3">
                  {priorityGroups.map((group) => (
                    <div key={group} className="rounded-lg border border-gray-200 p-3">
                      <h3 className="text-[13px] font-semibold text-gray-950">{group}</h3>
                      <div className="mt-2 space-y-3">
                        {(data.today_priorities[group] || []).map((item, index) => (
                          <div key={`${group}-${index}`} className="space-y-1 text-[13px] leading-6 text-gray-600">
                            <p>操作动作：{item.action}</p>
                            <p>作用对象：{item.target}</p>
                            <p>预期影响：{item.expected_impact}</p>
                            <p>风险提示：{item.risk_note}</p>
                            <p>观察周期：{item.observation_cycle}</p>
                          </div>
                        ))}
                        {!data.today_priorities[group]?.length && <p className="text-[13px] text-gray-500">{EMPTY}</p>}
                      </div>
                    </div>
                  ))}
                </div>
              </Section>

              <Section title="六、风险预警">
                {data.risk_warnings.length ? (
                  <div className="space-y-2">
                    {data.risk_warnings.map((item, index) => (
                      <div key={`${item.risk}-${index}`} className="flex flex-col gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-[13px] leading-6 text-amber-900 sm:flex-row sm:items-center sm:justify-between">
                        <span className="inline-flex items-center gap-2 font-semibold"><AlertTriangle className="h-3.5 w-3.5" />{item.risk}</span>
                        <span>{item.evidence}</span>
                        <Badge variant="outline" className="w-fit border-amber-300 bg-white text-amber-800">{item.status}</Badge>
                      </div>
                    ))}
                  </div>
                ) : <EmptyState />}
              </Section>

              <Section title="七、最终结论">
                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-lg border border-gray-200 p-3">
                    <p className="text-[13px] font-medium text-gray-500">昨天最大的问题</p>
                    <p className="mt-1.5 text-[15px] font-semibold text-gray-950">{data.final_conclusion.largest_problem}</p>
                  </div>
                  <div className="rounded-lg border border-gray-200 p-3">
                    <p className="text-[13px] font-medium text-gray-500">今天最重要的动作</p>
                    <p className="mt-1.5 text-[15px] font-semibold text-gray-950">{data.final_conclusion.most_important_action}</p>
                  </div>
                  <div className="rounded-lg border border-gray-200 p-3">
                    <p className="text-[13px] font-medium text-gray-500">当前商品状态</p>
                    <p className="mt-1.5 text-[15px] font-semibold text-gray-950">{data.final_conclusion.product_status}</p>
                  </div>
                </div>
              </Section>
            </div>
          ) : (
            <EmptyState />
          )}
        </div>
      </main>
    </div>
  );
}
