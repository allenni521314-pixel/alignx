import { useMemo, useState, type ComponentType, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Play,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import {
  createValidationResult,
  listAsinProfiles,
  listExecutionRecords,
  listValidationResults,
  listValidationTasks,
  type AsinProfile,
  type ExecutionRecord,
  type ValidationResult,
  type ValidationTask,
} from "@/lib/api";
import { IMPACT_METRIC_LABELS, POSITION_LABELS, label } from "@/lib/label-maps";

type SummaryStatus = "running" | "pending" | "effective" | "ineffective" | "interfered" | "insufficient_data";

type AsinValidationSummary = {
  asin: string;
  profile?: AsinProfile;
  tasks: ValidationTask[];
  executions: ExecutionRecord[];
  results: ValidationResult[];
  status: SummaryStatus;
  latestExecution?: ExecutionRecord;
  latestResult?: ValidationResult;
  effectiveResults: ValidationResult[];
};

const RESULT_LABELS: Record<string, string> = {
  effective: "有效",
  ineffective: "无效",
  interfered: "受干扰",
  insufficient_data: "数据不足",
};

const EXECUTION_LABELS: Record<string, string> = {
  pending: "待执行",
  running: "进行中",
  completed: "已完成",
};

const METRIC_LABELS: Record<string, string> = {
  impressions: "曝光",
  clicks: "点击",
  orders: "订单",
  spend: "广告花费",
  sales: "销售额",
  ctr: "CTR",
  cvr: "CVR",
  acos: "ACoS",
  cpc: "CPC",
};

const COST_LABELS: Record<string, string> = {
  ad_spend: "广告花费",
  design_cost: "设计费用",
  discount_cost: "折扣成本",
  labor_cost: "人工成本",
  other: "其他",
};

export default function BusinessValidation() {
  const queryClient = useQueryClient();
  const [expandedAsin, setExpandedAsin] = useState<string | null>(null);
  const [expandedTask, setExpandedTask] = useState<string | null>(null);
  const [showResultForm, setShowResultForm] = useState<string | null>(null);

  const { data: tasks, isLoading: tasksLoading } = useQuery({
    queryKey: ["validation-tasks"],
    queryFn: () => listValidationTasks(),
  });
  const { data: profiles, isLoading: profilesLoading } = useQuery({
    queryKey: ["asin-profiles"],
    queryFn: () => listAsinProfiles(),
  });
  const { data: executions, isLoading: executionsLoading } = useQuery({
    queryKey: ["execution-records", "all"],
    queryFn: () => listExecutionRecords(undefined, 200),
  });
  const { data: results, isLoading: resultsLoading } = useQuery({
    queryKey: ["validation-results"],
    queryFn: () => listValidationResults(200),
  });

  const taskList = tasks?.items ?? [];
  const executionList = executions?.items ?? [];
  const resultList = results?.items ?? [];
  const profileMap = useMemo(
    () => new Map((profiles?.items ?? []).map((profile) => [profile.asin, profile])),
    [profiles?.items],
  );

  const summaries = useMemo(() => {
    const asinSet = new Set<string>();

    executionList.forEach((record) => {
      if (record.asin && record.validation_task_id) asinSet.add(record.asin);
    });
    resultList.forEach((result) => {
      if (result.asin && result.validation_task_id) asinSet.add(result.asin);
    });
    taskList.forEach((task) => {
      if (task.execution_status !== "pending" || task.result_status) asinSet.add(task.asin);
    });

    return Array.from(asinSet).map<AsinValidationSummary>((asin) => {
      const asinTasks = taskList.filter((task) => task.asin === asin);
      const asinExecutions = executionList
        .filter((record) => record.asin === asin)
        .sort((a, b) => toTime(b.executed_at || b.created_at) - toTime(a.executed_at || a.created_at));
      const asinResults = resultList
        .filter((result) => result.asin === asin)
        .sort((a, b) => toTime(b.created_at) - toTime(a.created_at));
      const latestResult = asinResults[0];
      const latestExecution = asinExecutions[0];

      let status: SummaryStatus = "pending";
      if (latestResult?.final_result_status && latestResult.final_result_status in RESULT_LABELS) {
        status = latestResult.final_result_status as SummaryStatus;
      } else if (asinTasks.some((task) => task.execution_status === "running")) {
        status = "running";
      } else if (asinExecutions.length > 0) {
        status = "pending";
      } else if (asinTasks.some((task) => task.execution_status === "completed")) {
        status = "pending";
      }

      return {
        asin,
        profile: profileMap.get(asin),
        tasks: asinTasks.sort((a, b) => toTime(b.created_at) - toTime(a.created_at)),
        executions: asinExecutions,
        results: asinResults,
        status,
        latestExecution,
        latestResult,
        effectiveResults: asinResults.filter((result) => result.final_result_status === "effective"),
      };
    }).sort((a, b) => {
      const aTime = toTime(a.latestResult?.created_at || a.latestExecution?.created_at || a.tasks[0]?.created_at);
      const bTime = toTime(b.latestResult?.created_at || b.latestExecution?.created_at || b.tasks[0]?.created_at);
      return bTime - aTime;
    });
  }, [executionList, profileMap, resultList, taskList]);

  const running = summaries.filter((item) => item.status === "running").length;
  const pending = summaries.filter((item) => item.status === "pending" || item.status === "interfered" || item.status === "insufficient_data").length;
  const effective = summaries.filter((item) => item.status === "effective").length;
  const ineffective = summaries.filter((item) => item.status === "ineffective").length;
  const isLoading = tasksLoading || profilesLoading || executionsLoading || resultsLoading;

  return (
    <div className="max-w-[720px] mx-auto py-10">
      <div className="mb-8">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">效果验证</h1>
        <p className="text-[17px] text-[#86868b]">执行记录与验证结果汇总</p>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-8">
        <KpiCard icon={Play} label="进行中" value={running} color="text-[#0F2A24]" bg="bg-[#0F2A24]/[0.06]" />
        <KpiCard icon={Clock} label="待验证" value={pending} color="text-[#86868b]" bg="bg-[#fbfaf7]" />
        <KpiCard icon={CheckCircle2} label="有效" value={effective} color="text-[#34c759]" bg="bg-[#34c759]/[0.06]" />
        <KpiCard icon={XCircle} label="无效" value={ineffective} color="text-[#ff3b30]" bg="bg-[#ff3b30]/[0.06]" />
      </div>

      {isLoading ? (
        <EmptyCard title="加载中" detail="暂无" />
      ) : summaries.length > 0 ? (
        <div className="space-y-4">
          {summaries.map((summary) => {
            const isExpanded = expandedAsin === summary.asin;
            return (
              <div key={summary.asin} className="apple-card overflow-hidden">
                <button
                  type="button"
                  className="w-full p-5 text-left flex items-start justify-between gap-4 border-b border-[#d2d2d7]/20"
                  onClick={() => setExpandedAsin(isExpanded ? null : summary.asin)}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <ShieldCheck size={18} className="text-[#0F2A24]" />
                      <span className="text-[17px] font-semibold">{summary.asin}</span>
                      <StatusBadge status={summary.status} />
                    </div>
                    <p className="text-[13px] text-[#86868b] truncate max-w-[460px]">
                      {summary.profile?.product_title || "暂无"}
                    </p>
                  </div>
                  <div className="flex items-center gap-4 text-[13px] text-[#86868b] shrink-0">
                    <span>{summary.executions.length} 执行记录</span>
                    <span>{summary.results.length} 验证结果</span>
                    {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </div>
                </button>

                <div className="p-5 space-y-5">
                  <div className="grid grid-cols-2 gap-3">
                    <InfoBlock title="最近执行" value={summary.latestExecution?.action_summary || "暂无"} detail={formatDate(summary.latestExecution?.executed_at || summary.latestExecution?.created_at)} />
                    <InfoBlock title="最新结果" value={summary.latestResult?.final_result_status ? RESULT_LABELS[summary.latestResult.final_result_status] : "暂无"} detail={summary.latestResult?.attribution_conclusion || summary.latestResult?.notes || "暂无"} />
                  </div>

                  <div>
                    <div className="flex items-center gap-1.5 mb-2">
                      {summary.effectiveResults.length > 0 && (
                        <span className="w-1.5 h-1.5 rounded-full bg-[#b8860a]" />
                      )}
                      <p className="text-[13px] font-medium text-[#86868b]">成功结果</p>
                    </div>
                    {summary.effectiveResults.length > 0 ? (
                      <div className="space-y-2">
                        {summary.effectiveResults.slice(0, 2).map((result) => (
                          <ResultCard
                            key={result.id}
                            result={result}
                            task={summary.tasks.find((task) => task.id === result.validation_task_id)}
                            highlight
                          />
                        ))}
                      </div>
                    ) : (
                      <p className="text-[14px] text-[#86868b] bg-[#fbfaf7] rounded-xl px-4 py-3">暂无</p>
                    )}
                  </div>

                  {isExpanded && (
                    <div className="space-y-4 pt-2 border-t border-[#d2d2d7]/20">
                      <Section title="执行记录">
                        {summary.executions.length > 0 ? (
                          summary.executions.map((record) => (
                            <ExecutionRow key={record.id} record={record} />
                          ))
                        ) : (
                          <p className="text-[13px] text-[#86868b]">暂无</p>
                        )}
                      </Section>

                      <Section title="验证结果">
                        {summary.results.length > 0 ? (
                          summary.results.map((result) => (
                            <ResultCard
                              key={result.id}
                              result={result}
                              task={summary.tasks.find((task) => task.id === result.validation_task_id)}
                            />
                          ))
                        ) : (
                          <p className="text-[13px] text-[#86868b]">暂无</p>
                        )}
                      </Section>

                      <Section title="验证任务">
                        {summary.tasks.length > 0 ? (
                          <div className="space-y-2">
                            {summary.tasks.map((task) => {
                              const isTaskExpanded = expandedTask === task.id;
                              return (
                                <div key={task.id} className="rounded-xl border border-[#d2d2d7]/40 bg-white">
                                  <button
                                    type="button"
                                    className="w-full px-4 py-3 flex items-center justify-between gap-3 text-left"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      setExpandedTask(isTaskExpanded ? null : task.id);
                                    }}
                                  >
                                    <div className="min-w-0">
                                      <div className="flex items-center gap-2">
                                        <StatusDot status={task.execution_status} />
                                        <span className="text-[14px] font-medium truncate">
                                          {task.proposition_name || "验证任务"}
                                        </span>
                                      </div>
                                      <p className="text-[12px] text-[#86868b] truncate mt-1">
                                        {task.hypothesis_text || "暂无"}
                                      </p>
                                    </div>
                                    <span className="text-[12px] text-[#86868b] shrink-0">
                                      {EXECUTION_LABELS[task.execution_status] || task.execution_status || "暂无"}
                                    </span>
                                  </button>

                                  {isTaskExpanded && (
                                    <div className="px-4 pb-4 space-y-2">
                                      <TaskField label="依据" value={formatObject(task.evidence_snapshot)} />
                                      <TaskField label="控制变量" value={task.controlled_variable} />
                                      <TaskField label="成功标准" value={task.success_criteria} />
                                      <TaskField label="失败标准" value={task.failure_criteria} />
                                      <div className="pt-2">
                                        <ActionBtn
                                          label="录入结果"
                                          onClick={() => setShowResultForm(showResultForm === task.id ? null : task.id)}
                                        />
                                      </div>
                                      {showResultForm === task.id && (
                                        <ResultForm
                                          task={task}
                                          onClose={() => setShowResultForm(null)}
                                          onSuccess={() => {
                                            setShowResultForm(null);
                                            queryClient.invalidateQueries({ queryKey: ["validation-tasks"] });
                                            queryClient.invalidateQueries({ queryKey: ["asin-profiles"] });
                                            queryClient.invalidateQueries({ queryKey: ["validation-results"] });
                                          }}
                                        />
                                      )}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <p className="text-[13px] text-[#86868b]">暂无</p>
                        )}
                      </Section>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <EmptyCard title="暂无执行记录" detail="暂无" />
      )}
    </div>
  );
}

function KpiCard({
  icon: Icon, label, value, color, bg,
}: {
  icon: ComponentType<{ size?: number; className?: string }>;
  label: string; value: number; color: string; bg: string;
}) {
  return (
    <div className={`apple-card p-4 text-center ${bg}`}>
      <Icon size={20} className={`mx-auto mb-1.5 ${color}`} />
      <p className="text-[24px] font-bold tracking-tight">{value}</p>
      <p className="text-[11px] text-[#86868b] mt-0.5">{label}</p>
    </div>
  );
}

function EmptyCard({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="apple-card p-16 text-center">
      <ShieldCheck size={32} className="text-[#d2d2d7] mx-auto mb-3" />
      <p className="text-[15px] text-[#86868b]">{title}</p>
      <p className="text-[13px] text-[#86868b]/60 mt-1">{detail}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: SummaryStatus }) {
  const styles: Record<SummaryStatus, string> = {
    running: "bg-[#0F2A24]/10 text-[#0F2A24]",
    pending: "bg-[#fbfaf7] text-[#86868b]",
    effective: "bg-[#34c759]/10 text-[#34c759]",
    ineffective: "bg-[#ff3b30]/10 text-[#ff3b30]",
    interfered: "bg-[#ff9500]/10 text-[#ff9500]",
    insufficient_data: "bg-[#86868b]/10 text-[#86868b]",
  };
  const labels: Record<SummaryStatus, string> = {
    running: "进行中",
    pending: "待验证",
    effective: "有效",
    ineffective: "无效",
    interfered: "受干扰",
    insufficient_data: "数据不足",
  };

  return (
    <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${styles[status]}`}>
      {labels[status]}
    </span>
  );
}

function InfoBlock({ title, value, detail }: { title: string; value: string; detail?: string }) {
  return (
    <div className="rounded-xl bg-[#fbfaf7] p-4 min-w-0">
      <p className="text-[12px] text-[#86868b] mb-1">{title}</p>
      <p className="text-[14px] font-medium truncate">{value || "暂无"}</p>
      <p className="text-[12px] text-[#86868b] mt-1 truncate">{detail || "暂无"}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-[13px] font-medium text-[#86868b] mb-2">{title}</p>
      {children}
    </div>
  );
}

function ExecutionRow({ record }: { record: ExecutionRecord }) {
  const meta = formatExecutionMeta(record);
  const evidence = formatEvidence(record.evidence_note);

  return (
    <div className="rounded-xl border border-[#d2d2d7]/40 bg-white px-4 py-3 mb-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[14px] font-medium truncate">{record.action_summary || "暂无"}</p>
          <p className="text-[12px] text-[#86868b] mt-1">
            {formatChangedField(record.changed_position, POSITION_LABELS)} · {formatChangedField(record.changed_variable, IMPACT_METRIC_LABELS)}
          </p>
        </div>
        <p className="text-[12px] text-[#86868b] shrink-0">{formatDate(record.executed_at || record.created_at)}</p>
      </div>
      {meta && <p className="text-[12px] text-[#86868b] mt-2">{meta}</p>}
      {evidence && <p className="text-[12px] text-[#86868b] mt-1">{evidence}</p>}
    </div>
  );
}

function ResultCard({ result, task, highlight }: { result: ValidationResult; task?: ValidationTask; highlight?: boolean }) {
  const [toast, setToast] = useState<string | null>(null);
  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 2500); };

  return (
    <div className={`rounded-xl px-4 py-3 ${highlight ? "border border-[#b8860a]/30 bg-[#fdf3dc]/25" : "border border-[#d2d2d7]/40 bg-white"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[14px] font-medium">
              {RESULT_LABELS[result.final_result_status || ""] || "暂无"}
            </span>
            {task?.proposition_name && (
              <span className="text-[12px] text-[#86868b] truncate">{task.proposition_name}</span>
            )}
          </div>
          <p className="text-[13px] text-[#86868b] truncate">
            {result.attribution_conclusion || result.notes || "暂无"}
          </p>
        </div>
        <p className="text-[12px] text-[#86868b] shrink-0">{formatDate(result.created_at)}</p>
      </div>

      <div className="grid grid-cols-2 gap-2 mt-3">
        <MetricSnapshot title="验证前" data={result.baseline_metrics_json} />
        <MetricSnapshot title="验证后" data={result.result_metrics_json} />
      </div>
      {(result.sample_days || result.sample_clicks || result.sample_orders) && (
        <p className="text-[12px] text-[#86868b] mt-2">
          样本：{result.sample_days ?? "暂无"} 天 · {result.sample_clicks ?? "暂无"} 点击 · {result.sample_orders ?? "暂无"} 订单
        </p>
      )}
      {highlight && (
        <div className="mt-3 pt-3 border-t border-[#b8860a]/15 flex justify-end">
          <button
            type="button"
            onClick={() => showToast("放大投入：待接入")}
            className="apple-btn-amber text-[12px] px-3 py-1.5"
          >
            放大投入
          </button>
        </div>
      )}
      {toast && <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-[#1d1d1f] text-white px-5 py-3 rounded-xl text-[14px] shadow-lg z-50">{toast}</div>}
    </div>
  );
}

function MetricSnapshot({ title, data }: { title: string; data: Record<string, number> | null }) {
  const entries = Object.entries(data ?? {});
  if (entries.length === 0) {
    return (
      <div className="rounded-lg bg-[#fbfaf7] px-3 py-2">
        <p className="text-[11px] text-[#86868b] mb-1">{title}</p>
        <p className="text-[12px] text-[#86868b]">暂无</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-[#fbfaf7] px-3 py-2">
      <p className="text-[11px] text-[#86868b] mb-1">{title}</p>
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {entries.slice(0, 4).map(([key, value]) => (
          <span key={key} className="text-[12px]">
            <span className="text-[#86868b]">{METRIC_LABELS[key] || key}：</span>
            <span className="font-medium">{formatMetricValue(key, value)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function TaskField({ label, value }: { label: string; value?: string | null }) {
  return (
    <p className="text-[13px] text-[#86868b]">
      {label}：{value || "暂无"}
    </p>
  );
}

function ActionBtn({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      className="apple-btn-secondary text-[12px] px-3 py-1.5"
    >
      {label}
    </button>
  );
}

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running: "bg-[#0F2A24]",
    pending: "bg-[#d2d2d7]",
    completed: "bg-[#34c759]",
  };
  return <div className={`w-2 h-2 rounded-full ${colors[status] ?? "bg-[#86868b]"}`} />;
}

function ResultForm({
  task, onClose, onSuccess,
}: {
  task: { id: string; asin: string };
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [status, setStatus] = useState("effective");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await createValidationResult({
        validation_task_id: task.id,
        asin: task.asin,
        final_result_status: status,
        notes,
      });
      onSuccess();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mt-3 p-4 bg-white rounded-xl border border-[#d2d2d7]/30 space-y-3">
      <p className="text-[14px] font-medium">录入验证结果</p>
      <div className="flex flex-wrap gap-2">
        {[
          { v: "effective", l: "有效", c: "border-[#34c759] bg-[#34c759]/[0.04]" },
          { v: "ineffective", l: "无效", c: "border-[#ff3b30] bg-[#ff3b30]/[0.04]" },
          { v: "interfered", l: "受干扰", c: "border-[#ff9500] bg-[#ff9500]/[0.04]" },
          { v: "insufficient_data", l: "数据不足", c: "border-[#86868b] bg-[#fbfaf7]" },
        ].map((opt) => (
          <button
            key={opt.v}
            type="button"
            onClick={() => setStatus(opt.v)}
            className={`px-3 py-1.5 rounded-full text-[13px] border transition-colors ${
              status === opt.v ? `${opt.c} font-medium` : "border-[#d2d2d7] text-[#86868b]"
            }`}
          >
            {opt.l}
          </button>
        ))}
      </div>
      <textarea
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
        placeholder="备注（可选）"
        className="apple-input"
        rows={2}
      />
      <div className="flex gap-2">
        <button type="button" onClick={handleSubmit} disabled={submitting} className="apple-btn-primary text-[13px] px-4 py-1.5">
          {submitting ? "提交中..." : "提交结果"}
        </button>
        <button type="button" onClick={onClose} className="apple-btn-secondary text-[13px] px-4 py-1.5">取消</button>
      </div>
    </div>
  );
}

function toTime(value?: string | null) {
  if (!value) return 0;
  const time = new Date(value).getTime();
  return Number.isFinite(time) ? time : 0;
}

function formatDate(value?: string | null) {
  if (!value) return "暂无";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "暂无";
  return date.toISOString().slice(0, 10);
}

function formatObject(value: Record<string, unknown> | null) {
  if (!value) return "暂无";
  return formatEvidenceObject(value) || "暂无";
}

function formatMetricValue(key: string, value: number) {
  if (key === "ctr" || key === "cvr" || key === "acos") return `${(value * 100).toFixed(2)}%`;
  if (key === "spend" || key === "sales" || key === "cpc") return `$${Number(value).toFixed(2)}`;
  return String(value);
}

function formatChangedField(value: string | null, map: Record<string, string>) {
  if (!value) return "暂无";
  return label(map, value);
}

function formatExecutionMeta(record: ExecutionRecord) {
  const parts: string[] = [];
  if (record.cost_type) parts.push(label(COST_LABELS, record.cost_type));
  if (record.cost_amount != null) parts.push(formatCostAmount(record.cost_amount));
  return parts.join(" · ");
}

function formatCostAmount(value: number) {
  return `$${Number(value).toFixed(2)}`;
}

function formatEvidence(value: string | null) {
  if (!value) return "";
  const trimmed = value.trim();
  if (!trimmed) return "";
  try {
    const parsed = JSON.parse(trimmed) as Record<string, unknown>;
    return formatEvidenceObject(parsed);
  } catch {
    return trimmed;
  }
}

function formatEvidenceObject(value: Record<string, unknown>) {
  const parts: string[] = [];
  const metrics = ["impressions", "clicks", "orders", "sales", "spend", "ctr", "cvr", "acos", "cpc"];

  for (const key of metrics) {
    const raw = value[key];
    if (typeof raw === "number" && Number.isFinite(raw)) {
      parts.push(`${METRIC_LABELS[key] || key} ${formatMetricValue(key, raw)}`);
    }
  }

  if (typeof value.report_date === "string" && value.report_date) {
    parts.push(`报表日期 ${value.report_date}`);
  }

  if (typeof value.source_type === "string" && value.source_type) {
    parts.push(`来源 ${formatSourceType(value.source_type)}`);
  }

  return parts.join(" · ");
}

function formatSourceType(value: string) {
  const sourceLabels: Record<string, string> = {
    uploaded_report: "上传报表",
    browser_extension: "浏览器插件",
    manual: "手动录入",
  };
  return sourceLabels[value] || value;
}
