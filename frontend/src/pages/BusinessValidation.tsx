import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldCheck, Plus, Play, CheckCircle2, XCircle,
  Clock, AlertTriangle, DollarSign, Target, ChevronDown, ChevronUp,
} from "lucide-react";
import { listValidationTasks, listAsinProfiles, API_BASE } from "@/lib/api";

export default function BusinessValidation() {
  const queryClient = useQueryClient();
  const [expandedTask, setExpandedTask] = useState<string | null>(null);
  const [showResultForm, setShowResultForm] = useState<string | null>(null);
  const [execRecords, setExecRecords] = useState<any[] | null>(null);
  const [loadingExecs, setLoadingExecs] = useState(false);

  const { data: tasks } = useQuery({
    queryKey: ["validation-tasks"],
    queryFn: () => listValidationTasks(),
  });
  const { data: profiles } = useQuery({
    queryKey: ["asin-profiles"],
    queryFn: () => listAsinProfiles(),
  });

  const taskList = tasks?.items ?? [];

  // Group by ASIN
  const asinGroups: Record<string, typeof taskList> = {};
  taskList.forEach((t) => {
    if (!asinGroups[t.asin]) asinGroups[t.asin] = [];
    asinGroups[t.asin].push(t);
  });

  const running = taskList.filter((t) => t.execution_status === "running").length;
  const pending = taskList.filter((t) => t.execution_status === "pending").length;
  const effective = taskList.filter((t) => t.result_status === "effective").length;
  const ineffective = taskList.filter((t) => t.result_status === "ineffective").length;

  const profileMap = new Map((profiles?.items ?? []).map((p) => [p.asin, p]));

  return (
    <div className="max-w-[800px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">经营验证</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          对每一项经营投入进行「命题-执行-验证」闭环
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-3 mb-8">
        <KpiCard icon={Play} label="进行中" value={running} color="text-[#0071e3]" bg="bg-[#0071e3]/[0.06]" />
        <KpiCard icon={Clock} label="待验证" value={pending} color="text-[#86868b]" bg="bg-[#f5f5f7]" />
        <KpiCard icon={CheckCircle2} label="有效" value={effective} color="text-[#34c759]" bg="bg-[#34c759]/[0.06]" />
        <KpiCard icon={XCircle} label="无效" value={ineffective} color="text-[#ff3b30]" bg="bg-[#ff3b30]/[0.06]" />
      </div>

      {/* ASIN Pipelines */}
      {Object.keys(asinGroups).length > 0 ? (
        <div className="space-y-4">
          {Object.entries(asinGroups).map(([asin, asinTasks]) => {
            const profile = profileMap.get(asin);
            const maxPriority = Math.max(...asinTasks.map(() => 3)); // placeholder
            return (
              <div key={asin} className="apple-card overflow-hidden">
                {/* ASIN Header */}
                <div className="p-5 flex items-center justify-between border-b border-[#d2d2d7]/20">
                  <div className="flex items-center gap-3">
                    <ShieldCheck size={20} className={maxPriority >= 4 ? "text-[#ff3b30]" : "text-[#0071e3]"} />
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[16px] font-semibold">{asin}</span>
                        <PriorityBadge level={maxPriority} />
                      </div>
                      {profile?.product_title && (
                        <p className="text-[13px] text-[#86868b] truncate max-w-[400px]">
                          {profile.product_title}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-[13px] text-[#86868b]">
                    {profile && (
                      <>
                        <span className="text-[#34c759]">{profile.effective_count} 有效</span>
                        <span className="text-[#ff3b30]">{profile.ineffective_count} 无效</span>
                      </>
                    )}
                    <span>{asinTasks.length} 任务</span>
                  </div>
                </div>

                {/* Task List */}
                <div className="divide-y divide-[#d2d2d7]/10">
                  {asinTasks.map((task) => {
                    const isExpanded = expandedTask === task.id;
                    return (
                      <div key={task.id}>
                        <div
                          className="p-4 flex items-center justify-between hover:bg-[#f5f5f7] cursor-pointer transition-colors"
                          onClick={() => setExpandedTask(isExpanded ? null : task.id)}
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <StatusDot status={task.execution_status} />
                              <span className="text-[14px] font-medium">
                                {task.proposition_name || "验证任务"}
                              </span>
                            </div>
                            {task.hypothesis_text && (
                              <p className="text-[13px] text-[#86868b] truncate ml-5">
                                🎯 {task.hypothesis_text}
                              </p>
                            )}
                          </div>
                          <div className="flex items-center gap-4 text-[13px] text-[#86868b] shrink-0">
                            {task.validation_period && <span>⏳ {task.validation_period}</span>}
                            <span className="text-[#0071e3]">{task.execution_status === "running" ? "进行中" : task.execution_status}</span>
                            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                          </div>
                        </div>

                        {/* Expanded Detail */}
                        {isExpanded && (
                          <div className="px-5 pb-4 pt-2 bg-[#f5f5f7] space-y-2">
                            {task.evidence_snapshot && (
                              <p className="text-[13px] text-[#86868b]">
                                依据：{JSON.stringify(task.evidence_snapshot)}
                              </p>
                            )}
                            {task.controlled_variable && (
                              <p className="text-[13px] text-[#86868b]">
                                控制变量：{task.controlled_variable}
                              </p>
                            )}
                            {task.success_criteria && (
                              <p className="text-[13px] text-[#34c759]">
                                成功标准：{task.success_criteria}
                              </p>
                            )}
                            {task.failure_criteria && (
                              <p className="text-[13px] text-[#ff3b30]">
                                失败标准：{task.failure_criteria}
                              </p>
                            )}
                            <div className="flex gap-2 pt-2">
                              <ActionBtn
                                label="执行记录"
                                onClick={async () => {
                                  setLoadingExecs(true);
                                  const res = await fetch(`${API_BASE}/execution-records?validation_task_id=${task.id}`);
                                  const data = await res.json();
                                  setExecRecords(data.items || []);
                                  setLoadingExecs(false);
                                }}
                              />
                              <ActionBtn
                                label="录入结果"
                                primary
                                onClick={() => setShowResultForm(task.id)}
                              />
                            </div>

                            {/* Result Form */}
                            {showResultForm === task.id && (
                              <ResultForm
                                task={task}
                                onClose={() => setShowResultForm(null)}
                                onSuccess={() => {
                                  setShowResultForm(null);
                                  queryClient.invalidateQueries({ queryKey: ["validation-tasks"] });
                                  queryClient.invalidateQueries({ queryKey: ["asin-profiles"] });
                                }}
                              />
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="apple-card p-16 text-center">
          <ShieldCheck size={32} className="text-[#d2d2d7] mx-auto mb-3" />
          <p className="text-[15px] text-[#86868b]">暂无验证任务</p>
          <p className="text-[13px] text-[#86868b]/60 mt-1">从承接转化诊断创建第一个验证任务</p>
        </div>
      )}
    </div>
  );
}

/* ── Sub-components ── */

function KpiCard({
  icon: Icon, label, value, color, bg,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
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

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running: "bg-[#0071e3]",
    pending: "bg-[#d2d2d7]",
    completed: "bg-[#34c759]",
  };
  return <div className={`w-2 h-2 rounded-full ${colors[status] ?? "bg-[#86868b]"}`} />;
}

function PriorityBadge({ level }: { level: number }) {
  const colors: Record<number, string> = {
    1: "bg-[#f5f5f7] text-[#86868b]",
    2: "bg-[#34c759]/10 text-[#34c759]",
    3: "bg-[#0071e3]/10 text-[#0071e3]",
    4: "bg-[#ff9500]/10 text-[#ff9500]",
    5: "bg-[#ff3b30]/10 text-[#ff3b30]",
  };
  return (
    <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${colors[level] ?? colors[1]}`}>
      P{level}
    </span>
  );
}

function ActionBtn({ label, primary, onClick }: { label: string; primary?: boolean; onClick: () => void }) {
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      className={primary
        ? "apple-btn-primary text-[12px] px-3 py-1.5"
        : "apple-btn-secondary text-[12px] px-3 py-1.5"
      }
    >
      {label}
    </button>
  );
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
    await fetch(`${API_BASE}/validation-results`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        validation_task_id: task.id,
        asin: task.asin,
        final_result_status: status,
        notes,
      }),
    });
    setSubmitting(false);
    onSuccess();
  };

  return (
    <div className="mt-3 p-4 bg-white rounded-xl border border-[#d2d2d7]/30 space-y-3">
      <p className="text-[14px] font-medium">录入验证结果</p>
      <div className="flex gap-2">
        {[
          { v: "effective", l: "✅ 有效", c: "border-[#34c759] bg-[#34c759]/[0.04]" },
          { v: "ineffective", l: "❌ 无效", c: "border-[#ff3b30] bg-[#ff3b30]/[0.04]" },
          { v: "interfered", l: "⚠️ 受干扰", c: "border-[#ff9500] bg-[#ff9500]/[0.04]" },
          { v: "insufficient_data", l: "📊 数据不足", c: "border-[#86868b] bg-[#f5f5f7]" },
        ].map((opt) => (
          <button
            key={opt.v}
            onClick={() => setStatus(opt.v)}
            className={`px-3 py-1.5 rounded-full text-[13px] border transition-colors ${
              status === opt.v ? opt.c + " font-medium" : "border-[#d2d2d7] text-[#86868b]"
            }`}
          >
            {opt.l}
          </button>
        ))}
      </div>
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="备注（可选）"
        className="apple-input"
        rows={2}
      />
      <div className="flex gap-2">
        <button onClick={handleSubmit} disabled={submitting} className="apple-btn-primary text-[13px] px-4 py-1.5">
          {submitting ? "提交中..." : "提交结果"}
        </button>
        <button onClick={onClose} className="apple-btn-secondary text-[13px] px-4 py-1.5">取消</button>
      </div>
    </div>
  );
}
