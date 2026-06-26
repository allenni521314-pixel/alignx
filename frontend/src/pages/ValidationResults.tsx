import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  TrendingUp, TrendingDown, AlertTriangle, HelpCircle,
  CheckCircle2, ChevronDown, ChevronUp, Plus,
} from "lucide-react";
import {
  createValidationResult,
  listValidationResults,
  listValidationTasks,
  type ValidationResult,
} from "@/lib/api";

const STATUS_CFG: Record<string, { icon: React.ComponentType<{ size?: number; className?: string }>; color: string; label: string; bg: string }> = {
  effective:     { icon: TrendingUp,    color: "text-[#34c759]", label: "有效", bg: "bg-[#34c759]/[0.06]" },
  ineffective:   { icon: TrendingDown,  color: "text-[#ff3b30]", label: "无效", bg: "bg-[#ff3b30]/[0.06]" },
  interfered:    { icon: AlertTriangle, color: "text-[#ff9500]", label: "受干扰", bg: "bg-[#ff9500]/[0.06]" },
  insufficient_data:  { icon: HelpCircle,    color: "text-[#86868b]", label: "数据不足", bg: "bg-[#f5f5f7]" },
};

export default function ValidationResults() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery<{ items: ValidationResult[]; total: number }>({
    queryKey: ["validation-results"],
    queryFn: () => listValidationResults(50),
  });
  const { data: tasks } = useQuery({
    queryKey: ["validation-tasks"],
    queryFn: () => listValidationTasks(),
  });

  const [expanded, setExpanded] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState({ validation_task_id: "", asin: "", status: "effective", notes: "", attribution: "" });
  const [submitting, setSubmitting] = useState(false);

  const results = data?.items ?? [];
  const taskList = tasks?.items ?? [];
  const counts = {
    effective: results.filter((r) => r.final_result_status === "effective").length,
    ineffective: results.filter((r) => r.final_result_status === "ineffective").length,
    interfered: results.filter((r) => r.final_result_status === "interfered").length,
    insufficient_data: results.filter((r) => r.final_result_status === "insufficient_data").length,
  };

  const handleSubmit = async () => {
    if (!form.validation_task_id || !form.asin.trim()) return;
    setSubmitting(true);
    try {
      await createValidationResult({
        validation_task_id: form.validation_task_id,
        asin: form.asin,
        final_result_status: form.status,
        notes: form.notes,
        attribution_conclusion: form.attribution,
      });
      queryClient.invalidateQueries({ queryKey: ["validation-results"] });
      setFormOpen(false);
      setForm({ validation_task_id: "", asin: "", status: "effective", notes: "", attribution: "" });
    } catch {} finally { setSubmitting(false); }
  };

  if (isLoading) return <div className="max-w-[800px] mx-auto py-8"><div className="apple-card p-16 text-center"><div className="w-8 h-8 border-2 border-[#0071e3]/20 border-t-[#0071e3] rounded-full animate-spin mx-auto" /></div></div>;

  return (
    <div className="max-w-[680px] mx-auto py-12">
      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-[36px] font-bold tracking-[-0.025em] mb-2">效果验证</h1>
        <p className="text-[17px] text-[#86868b]">验证结果</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-3 mb-8">
        {Object.entries(STATUS_CFG).map(([k, { icon: Icon, color, label, bg }]) => (
          <div key={k} className={`apple-card p-4 text-center ${bg}`}>
            <Icon size={20} className={`mx-auto mb-1.5 ${color}`} />
            <p className="text-[22px] font-bold">{counts[k as keyof typeof counts]}</p>
            <p className="text-[11px] text-[#86868b] mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => setFormOpen(!formOpen)} className="apple-btn-primary flex items-center gap-2 px-4 py-2 text-[14px]">
          <Plus size={16} /> 录入验证结果
        </button>
      </div>

      {/* Entry Form */}
      {formOpen && (
        <div className="apple-card p-5 mb-6 space-y-3">
          <h3 className="text-[15px] font-semibold">录入验证结果</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[12px] text-[#86868b] block mb-1">验证任务</label>
              <select
                value={form.validation_task_id}
                onChange={(e) => {
                  const task = taskList.find((item) => item.id === e.target.value);
                  setForm({ ...form, validation_task_id: e.target.value, asin: task?.asin ?? "" });
                }}
                className="apple-input"
              >
                <option value="">待录入</option>
                {taskList.map((task) => (
                  <option key={task.id} value={task.id}>
                    {task.asin} · {task.proposition_name || task.proposition_code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[12px] text-[#86868b] block mb-1">结果</label>
              <select value={form.status} onChange={e => setForm({ ...form, status: e.target.value })} className="apple-input">
                <option value="effective">有效</option>
                <option value="ineffective">无效</option>
                <option value="interfered">受干扰</option>
                <option value="insufficient_data">数据不足</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-[12px] text-[#86868b] block mb-1">ASIN</label>
            <input value={form.asin} readOnly placeholder="待录入" className="apple-input" />
          </div>
          <div>
            <label className="text-[12px] text-[#86868b] block mb-1">备注</label>
            <input value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} className="apple-input" />
          </div>
          <div>
            <label className="text-[12px] text-[#86868b] block mb-1">归因结论</label>
            <input value={form.attribution} onChange={e => setForm({ ...form, attribution: e.target.value })} className="apple-input" placeholder="待录入" />
          </div>
          <div className="flex gap-2">
            <button onClick={handleSubmit} disabled={submitting || !form.validation_task_id || !form.asin.trim()} className="apple-btn-primary px-5 py-2 text-[14px]">
              {submitting ? "提交中..." : "提交"}
            </button>
            <button onClick={() => setFormOpen(false)} className="apple-btn-secondary px-5 py-2 text-[14px]">取消</button>
          </div>
        </div>
      )}

      {/* Results List */}
      {results.length === 0 ? (
        <div className="apple-card p-16 text-center">
          <CheckCircle2 size={32} className="text-[#d2d2d7] mx-auto mb-3" />
          <p className="text-[15px] text-[#86868b]">暂无验证结果</p>
        </div>
      ) : (
        <div className="space-y-3">
          {results.map((r) => {
            const cfg = STATUS_CFG[r.final_result_status] ?? STATUS_CFG.insufficient_data;
            const Icon = cfg.icon;
            const open = expanded === r.id;

            return (
              <div key={r.id} className={`apple-card border-l-4 ${r.final_result_status === "effective" ? "border-l-[#34c759]" : r.final_result_status === "ineffective" ? "border-l-[#ff3b30]" : r.final_result_status === "interfered" ? "border-l-[#ff9500]" : "border-l-[#86868b]"}`}>
                <div className="p-4 flex items-center gap-3 cursor-pointer" onClick={() => setExpanded(open ? null : r.id)}>
                  <Icon size={18} className={cfg.color} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[14px] font-semibold">{r.asin}</span>
                      <span className={`text-[12px] px-1.5 py-0.5 rounded-full ${cfg.bg} ${cfg.color}`}>{cfg.label}</span>
                      {r.next_step && (
                        <span className={`text-[11px] px-1.5 py-0.5 rounded-full ${
                          r.final_result_status === "effective" ? "bg-[#34c759]/10 text-[#34c759]" :
                          r.final_result_status === "ineffective" ? "bg-[#ff3b30]/10 text-[#ff3b30]" :
                          "bg-[#f5f5f7] text-[#86868b]"
                        }`}>{r.next_step}</span>
                      )}
                    </div>
                    <p className="text-[13px] text-[#86868b] truncate">{r.attribution_conclusion || "暂无"}</p>
                  </div>
                  <span className="text-[12px] text-[#86868b]/60">{new Date(r.created_at).toLocaleDateString("zh-CN")}</span>
                  {open ? <ChevronUp size={16} className="text-[#86868b]" /> : <ChevronDown size={16} className="text-[#86868b]" />}
                </div>

                {open && (
                  <div className="px-4 pb-4 border-t border-[#d2d2d7]/20 pt-3">
                    <p className="text-[14px]">{r.notes || "暂无"}</p>
                    {r.attribution_conclusion && (
                      <div className="mt-3 p-3 bg-[#f5f5f7] rounded-lg">
                        <p className="text-[12px] text-[#86868b] mb-1">归因结论</p>
                        <p className="text-[14px]">{r.attribution_conclusion}</p>
                      </div>
                    )}
                    {r.baseline_metrics_json && r.result_metrics_json && (
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        {Object.keys(r.baseline_metrics_json).map((k) => {
                          const before = r.baseline_metrics_json?.[k] ?? 0;
                          const after = r.result_metrics_json?.[k] ?? 0;
                          const change = after - before;
                          const pct = before ? ((change / before) * 100).toFixed(1) : "—";
                          return (
                            <div key={k} className="flex items-center justify-between p-2 rounded-lg bg-[#f5f5f7]">
                              <span className="text-[12px]">{k}</span>
                              <span className={`text-[12px] font-medium ${change > 0 ? "text-[#34c759]" : change < 0 ? "text-[#ff3b30]" : "text-[#86868b]"}`}>
                                {before} → {after} ({pct}%)
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
