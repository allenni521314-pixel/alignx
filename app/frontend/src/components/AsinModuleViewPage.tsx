import { useCallback, useEffect, useMemo, useState } from "react";
import { ClipboardCheck, Play, RefreshCw, Upload } from "lucide-react";

import { AppSidebar } from "@/components/AppSidebar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import {
  type AsinBusinessProfile,
  type AsinModuleView,
  type AsinModuleViewType,
  createExecutionLog,
  createValidationTask,
  getAsinModuleView,
  listReportStagingRows,
  listAsinProfiles,
  parseReport,
  type ReportParseSummary,
  resolveReportStagingRows,
  runEffectValidation,
  runIntentDecision,
  uploadReport,
} from "@/lib/asin-business-profile-api";

const EMPTY = "暂无";
const UNSET = "未设置";

export interface AsinModuleColumn {
  key: string;
  label: string;
}

export interface AsinModuleMetric {
  key: string;
  label: string;
}

export interface AsinModuleUploadOption {
  value: string;
  label: string;
}

export interface AsinModuleUploadConfig {
  buttonLabel: string;
  options: AsinModuleUploadOption[];
}

interface AsinModuleViewPageProps {
  title: string;
  viewType: AsinModuleViewType;
  metrics: AsinModuleMetric[];
  columns: AsinModuleColumn[];
  uploadConfig?: AsinModuleUploadConfig;
}

function valueOrEmpty(value: unknown) {
  if (value === null || value === undefined || value === "") return EMPTY;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return EMPTY;
    return String(Number.isInteger(value) ? value : Number(value.toFixed(4)));
  }
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return value.length ? value.map(valueOrEmpty).join("；") : EMPTY;
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).filter(([, item]) => item !== null && item !== undefined && item !== "");
    return entries.length ? entries.map(([key, item]) => `${key}：${valueOrEmpty(item)}`).join("；") : EMPTY;
  }
  return String(value);
}

function formatDate(value: unknown) {
  const text = valueOrEmpty(value);
  if (text === EMPTY) return text;
  return text.replace("T", " ").replace(/\.\d+Z?$/, "");
}

function statusClass(status: string) {
  if (["Success", "已完成", "成功"].includes(status)) return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (["Failed", "失败"].includes(status)) return "border-red-200 bg-red-50 text-red-700";
  if (["Running", "Pending", "Inconclusive", "运行中", "待执行", "无法判断"].includes(status)) return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-gray-200 bg-gray-50 text-gray-600";
}

function StatusValue({ value }: { value: unknown }) {
  const text = valueOrEmpty(value);
  if (text === EMPTY) return <span>{EMPTY}</span>;
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${statusClass(text)}`}>{text}</span>;
}

function MetricGrid({ metrics, values }: { metrics: AsinModuleMetric[]; values: Record<string, unknown> }) {
  if (!metrics.length) return null;
  return (
    <Card className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="text-[15px] font-semibold text-gray-950">指标</h2>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <div key={metric.key} className="min-h-[76px] rounded-lg border border-gray-100 bg-gray-50 px-3 py-2.5">
            <div className="text-xs font-medium text-gray-500">{metric.label}</div>
            <div className="mt-2 break-words text-[15px] font-semibold text-gray-950">{valueOrEmpty(values[metric.key])}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function RecordsTable({ columns, records }: { columns: AsinModuleColumn[]; records: Array<Record<string, unknown>> }) {
  return (
    <Card className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="text-[15px] font-semibold text-gray-950">记录</h2>
      <div className="mt-3 overflow-x-auto">
        {records.length ? (
          <table className="w-full min-w-[920px] border-collapse text-left text-[13px]">
            <thead>
              <tr className="border-b border-gray-200 text-xs text-gray-500">
                {columns.map((column) => (
                  <th key={column.key} className="whitespace-nowrap px-3 py-2 font-semibold">
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((record, index) => (
                <tr key={`${valueOrEmpty(record.id)}-${index}`} className="border-b border-gray-100 align-top last:border-0">
                  {columns.map((column) => (
                    <td key={column.key} className="max-w-[320px] px-3 py-3 text-gray-700">
                      {column.key === "status" ? <StatusValue value={record[column.key]} /> : valueOrEmpty(record[column.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-center text-sm text-gray-500">
            {EMPTY}
          </div>
        )}
      </div>
    </Card>
  );
}

function UploadPanel({
  config,
  selectedProfile,
  onParsed,
}: {
  config: AsinModuleUploadConfig;
  selectedProfile: AsinBusinessProfile | null;
  onParsed: () => Promise<void>;
}) {
  const [reportType, setReportType] = useState(config.options[0]?.value || "");
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [summary, setSummary] = useState<ReportParseSummary | null>(null);
  const [pendingRows, setPendingRows] = useState(0);
  const [resolveAsin, setResolveAsin] = useState("");
  const [busy, setBusy] = useState(false);

  const loadPendingRows = useCallback(async (reportId: string) => {
    const unresolved = await listReportStagingRows({ report_id: reportId, match_status: "Unresolved", limit: 1 });
    const ambiguous = await listReportStagingRows({ report_id: reportId, match_status: "Ambiguous", limit: 1 });
    setPendingRows((unresolved.total || 0) + (ambiguous.total || 0));
  }, []);

  const submit = useCallback(async () => {
    if (!file || !reportType) return;
    setBusy(true);
    try {
      const upload = await uploadReport({
        file,
        report_type: reportType,
        store_id: selectedProfile?.store_id || "default",
        marketplace: selectedProfile?.marketplace || "US",
        date_range_start: dateStart || undefined,
        date_range_end: dateEnd || undefined,
      });
      const parsed = await parseReport(upload.report_id);
      setSummary(parsed);
      await loadPendingRows(upload.report_id);
      await onParsed();
    } finally {
      setBusy(false);
    }
  }, [dateEnd, dateStart, file, loadPendingRows, onParsed, reportType, selectedProfile?.marketplace, selectedProfile?.store_id]);

  const resolveRows = useCallback(async (action: "bind_existing" | "create_profile" | "ignore") => {
    if (!summary?.report_id) return;
    if (action !== "ignore" && !resolveAsin.trim()) return;
    setBusy(true);
    try {
      const resolved = await resolveReportStagingRows({
        report_id: summary.report_id,
        action,
        asin: resolveAsin.trim() || undefined,
      });
      setSummary(resolved);
      await loadPendingRows(summary.report_id);
      await onParsed();
    } finally {
      setBusy(false);
    }
  }, [loadPendingRows, onParsed, resolveAsin, summary?.report_id]);

  return (
    <Card className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 space-y-1 text-xs font-medium leading-5 text-gray-500">
        <p>上传报表后，系统会按 ASIN 生成昨日战报和今日决策，让优化建议更精准。</p>
        <p>需上传：{config.options.map((option) => option.label).join("、")}。接入 Amazon API 后无需上传。</p>
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[180px_160px_160px_1fr_160px]">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-gray-500">报表类型</span>
          <select
            value={reportType}
            onChange={(event) => setReportType(event.target.value)}
            className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm font-semibold text-gray-900 outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
          >
            {config.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-gray-500">开始日期</span>
          <input
            type="date"
            value={dateStart}
            onChange={(event) => setDateStart(event.target.value)}
            className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm font-semibold text-gray-900 outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-gray-500">结束日期</span>
          <input
            type="date"
            value={dateEnd}
            onChange={(event) => setDateEnd(event.target.value)}
            className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm font-semibold text-gray-900 outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-gray-500">文件</span>
          <input
            type="file"
            accept=".csv,.xlsx,.xlsm"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
            className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-semibold text-gray-900 outline-none file:mr-3 file:rounded-md file:border-0 file:bg-gray-100 file:px-2 file:py-1 file:text-xs file:font-semibold file:text-gray-700 focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
          />
        </label>
        <div className="flex items-end">
          <Button onClick={submit} disabled={busy || !file} className="h-10 w-full gap-2 bg-brand-800 text-white hover:bg-brand-900">
            <Upload className="h-4 w-4" />
            {config.buttonLabel}
          </Button>
        </div>
      </div>
      {summary ? (
        <div className="mt-3 space-y-3">
          <div className="grid grid-cols-2 gap-2 text-xs font-semibold text-gray-700 md:grid-cols-5">
            <div>总行数：{summary.total_rows}</div>
            <div>已匹配 ASIN 行数：{summary.matched_asin_rows}</div>
            <div>未匹配行数：{summary.unmatched_rows}</div>
            <div>多重匹配行数：{summary.ambiguous_rows}</div>
            <div>可写入 ASIN档案的行数：{summary.writable_rows}</div>
          </div>
          {pendingRows ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
              <div className="text-xs font-semibold text-amber-800">发现 {pendingRows} 行数据无法匹配 ASIN</div>
              <div className="mt-1 text-xs font-semibold text-amber-800">部分数据无法对应到 ASIN，需确认后才能进入经营档案。</div>
              <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-[1fr_auto_auto_auto]">
                <input
                  value={resolveAsin}
                  onChange={(event) => setResolveAsin(event.target.value)}
                  placeholder="ASIN"
                  className="h-9 rounded-lg border border-amber-200 bg-white px-3 text-sm font-semibold text-gray-900 outline-none focus:border-amber-500"
                />
                <Button type="button" variant="outline" disabled={busy || !resolveAsin.trim()} onClick={() => resolveRows("bind_existing")} className="h-9">
                  绑定到已有 ASIN
                </Button>
                <Button type="button" variant="outline" disabled={busy || !resolveAsin.trim()} onClick={() => resolveRows("create_profile")} className="h-9">
                  新建 ASIN档案
                </Button>
                <Button type="button" variant="outline" disabled={busy} onClick={() => resolveRows("ignore")} className="h-9">
                  忽略该数据
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}

function OperationPanel({
  viewType,
  selectedProfile,
  onDone,
}: {
  viewType: AsinModuleViewType;
  selectedProfile: AsinBusinessProfile | null;
  onDone: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [intentName, setIntentName] = useState("");
  const [intentDescription, setIntentDescription] = useState("");
  const [evidenceText, setEvidenceText] = useState("");
  const [problem, setProblem] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [actionPlan, setActionPlan] = useState("");
  const [targetMetric, setTargetMetric] = useState("cvr");
  const [validationId, setValidationId] = useState("");
  const [intentDecisionId, setIntentDecisionId] = useState("");
  const [actionType, setActionType] = useState("");
  const [beforeValue, setBeforeValue] = useState("");
  const [afterValue, setAfterValue] = useState("");
  const [resultStart, setResultStart] = useState("");
  const [resultEnd, setResultEnd] = useState("");

  const profilePayload = {
    asin: selectedProfile?.asin || "",
    store_id: selectedProfile?.store_id || "default",
    marketplace: selectedProfile?.marketplace || "US",
  };

  const finish = useCallback(async (nextMessage: string) => {
    setMessage(nextMessage);
    await onDone();
  }, [onDone]);

  const submitIntentDecision = useCallback(async () => {
    if (!selectedProfile || !intentName.trim()) return;
    setBusy(true);
    setMessage("");
    try {
      await runIntentDecision({
        ...profilePayload,
        intent_name: intentName.trim(),
        intent_description: intentDescription.trim() || undefined,
        listing_snapshot: {
          title: selectedProfile.product_name || undefined,
          price: selectedProfile.current_price || undefined,
        },
        evidences: evidenceText.trim()
          ? [{ source_type: "Manual", evidence_text: evidenceText.trim(), strength_score: 60 }]
          : [],
      });
      setIntentName("");
      setIntentDescription("");
      setEvidenceText("");
      await finish("已生成判断");
    } catch {
      setMessage("操作失败");
    } finally {
      setBusy(false);
    }
  }, [evidenceText, finish, intentDescription, intentName, profilePayload, selectedProfile]);

  const submitValidationTask = useCallback(async () => {
    if (!selectedProfile || !problem.trim() || !actionPlan.trim()) return;
    setBusy(true);
    setMessage("");
    try {
      await createValidationTask({
        ...profilePayload,
        intent_decision_id: intentDecisionId.trim() || undefined,
        validation_type: viewType === "traffic-strategy" ? "Traffic" : "Listing",
        problem: problem.trim(),
        hypothesis: hypothesis.trim() || undefined,
        action_plan: actionPlan.trim(),
        target_metric: targetMetric.trim() || "cvr",
        status: "Pending",
      });
      setProblem("");
      setHypothesis("");
      setActionPlan("");
      setIntentDecisionId("");
      await finish("已创建验证任务");
    } catch {
      setMessage("操作失败");
    } finally {
      setBusy(false);
    }
  }, [actionPlan, finish, hypothesis, intentDecisionId, problem, profilePayload, selectedProfile, targetMetric, viewType]);

  const submitExecutionLog = useCallback(async () => {
    if (!selectedProfile || !validationId.trim() || !actionType.trim()) return;
    setBusy(true);
    setMessage("");
    try {
      await createExecutionLog({
        ...profilePayload,
        validation_id: validationId.trim(),
        intent_decision_id: intentDecisionId.trim() || undefined,
        action_type: actionType.trim(),
        before_value: beforeValue.trim() || undefined,
        after_value: afterValue.trim() || undefined,
        source: "Manual",
      });
      setValidationId("");
      setIntentDecisionId("");
      setActionType("");
      setBeforeValue("");
      setAfterValue("");
      await finish("已记录执行动作");
    } catch {
      setMessage("操作失败");
    } finally {
      setBusy(false);
    }
  }, [actionType, afterValue, beforeValue, finish, intentDecisionId, profilePayload, selectedProfile, validationId]);

  const submitEffectValidation = useCallback(async () => {
    if (!validationId.trim()) return;
    setBusy(true);
    setMessage("");
    try {
      await runEffectValidation({
        validation_id: validationId.trim(),
        result_start_date: resultStart || undefined,
        result_end_date: resultEnd || undefined,
        minimum_sample_ready: true,
      });
      setValidationId("");
      setResultStart("");
      setResultEnd("");
      await finish("已完成效果验证");
    } catch {
      setMessage("操作失败");
    } finally {
      setBusy(false);
    }
  }, [finish, resultEnd, resultStart, validationId]);

  if (viewType === "yesterday-report") return null;

  if (viewType === "traffic-strategy") {
    return (
      <Card className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="text-[15px] font-semibold text-gray-950">生成流量策略</h2>
        <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-[220px_1fr_1fr_150px]">
          <input value={intentName} onChange={(event) => setIntentName(event.target.value)} placeholder="购买意图" className="h-10 rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
          <input value={intentDescription} onChange={(event) => setIntentDescription(event.target.value)} placeholder="意图描述" className="h-10 rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
          <input value={evidenceText} onChange={(event) => setEvidenceText(event.target.value)} placeholder="证据" className="h-10 rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
          <Button onClick={submitIntentDecision} disabled={busy || !selectedProfile || !intentName.trim()} className="h-10 gap-2 bg-brand-800 text-white hover:bg-brand-900">
            <Play className="h-4 w-4" />
            生成策略
          </Button>
        </div>
        {message ? <div className="mt-3 text-xs font-semibold text-gray-600">{message}</div> : null}
      </Card>
    );
  }

  if (viewType === "today-decision") {
    return (
      <Card className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="text-[15px] font-semibold text-gray-950">创建验证任务</h2>
        <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-[1fr_1fr_1fr_140px_160px]">
          <input value={problem} onChange={(event) => setProblem(event.target.value)} placeholder="问题" className="h-10 rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
          <input value={hypothesis} onChange={(event) => setHypothesis(event.target.value)} placeholder="假设" className="h-10 rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
          <input value={actionPlan} onChange={(event) => setActionPlan(event.target.value)} placeholder="动作" className="h-10 rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
          <input value={targetMetric} onChange={(event) => setTargetMetric(event.target.value)} placeholder="目标指标" className="h-10 rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
          <Button onClick={submitValidationTask} disabled={busy || !selectedProfile || !problem.trim() || !actionPlan.trim()} className="h-10 gap-2 bg-brand-800 text-white hover:bg-brand-900">
            <ClipboardCheck className="h-4 w-4" />
            创建任务
          </Button>
        </div>
        <input value={intentDecisionId} onChange={(event) => setIntentDecisionId(event.target.value)} placeholder="意图决策ID" className="mt-3 h-10 w-full rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
        {message ? <div className="mt-3 text-xs font-semibold text-gray-600">{message}</div> : null}
      </Card>
    );
  }

  if (viewType === "execution-records") {
    return (
      <Card className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="text-[15px] font-semibold text-gray-950">记录今日执行动作</h2>
        <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-[180px_180px_1fr_1fr_150px]">
          <input value={validationId} onChange={(event) => setValidationId(event.target.value)} placeholder="验证ID" className="h-10 rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
          <input value={actionType} onChange={(event) => setActionType(event.target.value)} placeholder="动作类型" className="h-10 rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
          <input value={beforeValue} onChange={(event) => setBeforeValue(event.target.value)} placeholder="修改前" className="h-10 rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
          <input value={afterValue} onChange={(event) => setAfterValue(event.target.value)} placeholder="修改后" className="h-10 rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
          <Button onClick={submitExecutionLog} disabled={busy || !selectedProfile || !validationId.trim() || !actionType.trim()} className="h-10 gap-2 bg-brand-800 text-white hover:bg-brand-900">
            <ClipboardCheck className="h-4 w-4" />
            记录动作
          </Button>
        </div>
        <input value={intentDecisionId} onChange={(event) => setIntentDecisionId(event.target.value)} placeholder="意图决策ID" className="mt-3 h-10 w-full rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
        {message ? <div className="mt-3 text-xs font-semibold text-gray-600">{message}</div> : null}
      </Card>
    );
  }

  if (viewType === "effect-validation") {
    return (
      <Card className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="text-[15px] font-semibold text-gray-950">运行效果验证</h2>
        <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-[1fr_180px_180px_160px]">
          <input value={validationId} onChange={(event) => setValidationId(event.target.value)} placeholder="验证ID" className="h-10 rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
          <input type="date" value={resultStart} onChange={(event) => setResultStart(event.target.value)} className="h-10 rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
          <input type="date" value={resultEnd} onChange={(event) => setResultEnd(event.target.value)} className="h-10 rounded-lg border border-gray-200 px-3 text-sm font-semibold outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100" />
          <Button onClick={submitEffectValidation} disabled={busy || !validationId.trim()} className="h-10 gap-2 bg-brand-800 text-white hover:bg-brand-900">
            <Play className="h-4 w-4" />
            运行验证
          </Button>
        </div>
        {message ? <div className="mt-3 text-xs font-semibold text-gray-600">{message}</div> : null}
      </Card>
    );
  }

  return null;
}

export function AsinModuleViewPage({ title, viewType, metrics, columns, uploadConfig }: AsinModuleViewPageProps) {
  const { loading: authLoading } = useRequireAuth();
  const [profiles, setProfiles] = useState<AsinBusinessProfile[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [view, setView] = useState<AsinModuleView | null>(null);
  const [loading, setLoading] = useState(true);

  const selectedProfile = useMemo(
    () => profiles.find((profile) => `${profile.store_id}::${profile.marketplace}::${profile.asin}` === selectedKey) || profiles[0] || null,
    [profiles, selectedKey],
  );

  const loadView = useCallback(async (profile: AsinBusinessProfile | null) => {
    setLoading(true);
    try {
      const data = await getAsinModuleView({
        view_type: viewType,
        asin: profile?.asin,
        store_id: profile?.store_id,
        marketplace: profile?.marketplace,
      });
      setView(data);
    } catch {
      setView(null);
    } finally {
      setLoading(false);
    }
  }, [viewType]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const profileData = await listAsinProfiles({ limit: 100 });
      setProfiles(profileData.items);
      const nextProfile = profileData.items[0] || null;
      setSelectedKey(nextProfile ? `${nextProfile.store_id}::${nextProfile.marketplace}::${nextProfile.asin}` : "");
      await loadView(nextProfile);
    } catch {
      setProfiles([]);
      setView(null);
      setLoading(false);
    }
  }, [loadView]);

  useEffect(() => {
    if (!authLoading) void loadData();
  }, [authLoading, loadData]);

  useEffect(() => {
    if (!authLoading && selectedProfile) void loadView(selectedProfile);
  }, [authLoading, selectedProfile, loadView]);

  if (authLoading) return null;

  const summary = view?.summary || {};
  const records = view?.records || [];
  const mergedMetrics = { ...(view?.metrics || {}), ...summary };

  return (
    <div className="flex h-screen bg-[#f5f5f7] text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto bg-[#f5f5f7]">
        <div className="w-full max-w-none px-4 py-5 pt-14 sm:px-6 md:pt-6">
          <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h1 className="text-[24px] font-semibold tracking-normal text-gray-950">{title}</h1>
            <Button variant="outline" onClick={loadData} disabled={loading} className="h-9 gap-2 px-4 text-[13px]">
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              刷新
            </Button>
          </div>

          <Card className="mb-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_180px_180px]">
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-gray-500">ASIN</span>
                <select
                  value={selectedKey}
                  onChange={(event) => setSelectedKey(event.target.value)}
                  className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm font-semibold text-gray-900 outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
                >
                  {profiles.length ? profiles.map((profile) => (
                    <option key={`${profile.store_id}::${profile.marketplace}::${profile.asin}`} value={`${profile.store_id}::${profile.marketplace}::${profile.asin}`}>
                      {profile.asin} · {profile.product_name || UNSET}
                    </option>
                  )) : <option value="">{EMPTY}</option>}
                </select>
              </label>
              <div>
                <div className="text-xs font-medium text-gray-500">站点</div>
                <div className="mt-1 flex h-10 items-center rounded-lg border border-gray-100 bg-gray-50 px-3 text-sm font-semibold text-gray-900">
                  {valueOrEmpty(selectedProfile?.marketplace)}
                </div>
              </div>
              <div>
                <div className="text-xs font-medium text-gray-500">店铺</div>
                <div className="mt-1 flex h-10 items-center rounded-lg border border-gray-100 bg-gray-50 px-3 text-sm font-semibold text-gray-900">
                  {valueOrEmpty(selectedProfile?.store_id)}
                </div>
              </div>
            </div>
          </Card>

          <div className="space-y-4">
            {uploadConfig ? (
              <UploadPanel config={uploadConfig} selectedProfile={selectedProfile} onParsed={loadData} />
            ) : null}
            <OperationPanel viewType={viewType} selectedProfile={selectedProfile} onDone={loadData} />
            <Card className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
              <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.4fr_1fr_1fr_160px]">
                <div>
                  <div className="text-xs font-medium text-gray-500">判断结论</div>
                  <div className="mt-2 text-[16px] font-semibold leading-7 text-brand-800">
                    {valueOrEmpty(summary.conclusion)}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium text-gray-500">当前最大问题</div>
                  <div className="mt-2 text-sm font-semibold leading-6 text-gray-950">
                    {valueOrEmpty(summary.current_primary_problem)}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium text-gray-500">优先动作</div>
                  <div className="mt-2 text-sm font-semibold leading-6 text-gray-950">
                    {valueOrEmpty(summary.priority_actions || summary.recommended_action)}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium text-gray-500">生成时间</div>
                  <div className="mt-2 text-sm font-semibold text-gray-950">
                    {formatDate(summary.created_at)}
                  </div>
                </div>
              </div>
            </Card>

            <MetricGrid metrics={metrics} values={mergedMetrics} />
            <RecordsTable columns={columns} records={records} />
          </div>
        </div>
      </main>
    </div>
  );
}
