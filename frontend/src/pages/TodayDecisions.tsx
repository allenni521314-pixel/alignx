import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  ChevronRight, ArrowRight, Upload, Search, HelpCircle, FileText, AlertTriangle, Clock, Zap, Shield,
} from "lucide-react";
import {
  createExecutionRecord, getTodayDecisions, stageReportUpload, updateValidationTask, type DecisionItem,
} from "@/lib/api";

// ── 优先级分组：按 priority_score 分 P0/P1/P2/P3 ──
const PRIORITY_GROUPS = {
  p0: { level: "P0", label: "立即处理", color: "bg-[#ff3b30]", bg: "bg-[#ff3b30]/6", border: "border-[#ff3b30]/20", minScore: 80 },
  p1: { level: "P1", label: "本轮优化", color: "bg-[#ff9500]", bg: "bg-[#ff9500]/6", border: "border-[#ff9500]/20", minScore: 50 },
  p2: { level: "P2", label: "下轮跟进", color: "bg-[#0071e3]", bg: "bg-[#0071e3]/6", border: "border-[#0071e3]/20", minScore: 20 },
  p3: { level: "P3", label: "观察", color: "bg-[#86868b]", bg: "bg-[#86868b]/6", border: "border-[#86868b]/20", minScore: 0 },
} as const;

function groupByPriority(pending: DecisionItem[]) {
  const groups: Record<string, DecisionItem[]> = { p0: [], p1: [], p2: [], p3: [] };
  for (const item of pending) {
    const score = item.priority_score ?? 0;
    if (score >= 80) groups.p0.push(item);
    else if (score >= 50) groups.p1.push(item);
    else if (score >= 20) groups.p2.push(item);
    else groups.p3.push(item);
  }
  return groups;
}

function sourceRoute(source: string): string {
  const map: Record<string, string> = {
    "承接转化": "/conversion-diagnosis",
    "竞品分析": "/competitor-analysis",
    "上架准入": "/prelaunch-check",
    "产品调研": "/market-opportunity",
    "流量策略": "/traffic-strategy",
    "手动创建": "/business-validation",
  };
  return map[source] || "/business-validation";
}

export default function TodayDecisions() {
  const { data: report, isLoading } = useQuery({ queryKey: ["today-decisions"], queryFn: getTodayDecisions });
  const pending = report?.pending ?? [];
  const hasPending = pending.length > 0;
  const focus = hasPending ? pending[0] : null;
  const queue = pending.slice(1);

  return (
    <div className="max-w-[680px] mx-auto py-12">
      <div className="text-center mb-10">
        <h1 className="text-[36px] font-bold tracking-[-0.025em] mb-2">今天先做这件事</h1>
        <p className="text-[17px] text-[#86868b]">最低成本验证一个假设，明天再看结果</p>
      </div>

      {isLoading ? (
        <div className="apple-card p-16 text-center">
          <div className="w-8 h-8 border-2 border-[#0F2A24]/20 border-t-[#0F2A24] rounded-full animate-spin mx-auto" />
        </div>
      ) : (
        <div className="space-y-5">
          {/* Card 1: 报表上传 */}
          <ReportUploadCard />

          {/* Card 2: P0-P3 优先级处理 — 用真实 pending 数据 */}
          <PriorityTaskCard pending={pending} />

          {/* Card 3: 今日优先动作 */}
          {hasPending && (
            <div className="space-y-5">
              <FocusCard item={focus!} />
              {queue.length > 0 && (
                <div>
                  <p className="text-[13px] text-[#86868b] mb-2">后面还有 {queue.length} 个假设排队</p>
                  <div className="space-y-2">
                    {queue.map((item, i) => <QueueItem key={item.id} item={item} index={i + 2} />)}
                  </div>
                </div>
              )}
              {(report?.running ?? []).length > 0 && (
                <div>
                  <p className="text-[13px] font-medium text-[#86868b] mb-2">测试中 · {(report?.running ?? []).length} 个</p>
                  <div className="space-y-2">
                    {(report?.running ?? []).map((item) => <QueueItem key={item.id} item={item} index={0} running />)}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Card 4: 使用引导 */}
          <OnboardingGuide />
        </div>
      )}
    </div>
  );
}

/* ── Card 1: 报表上传 ── */
function ReportUploadCard() {
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); };

  const uploadFile = async (file: File) => {
    setUploading(true);
    try {
      const text = await file.text();
      const rows = text.split("\n").filter((r) => r.trim());
      const headers = rows[0]?.split(/[,\t]/).map((h) => h.trim()) ?? [];
      const parsedRows = rows.slice(1).map((row) => {
        const cols = row.split(/[,\t]/);
        return headers.reduce<Record<string, string>>((acc, h, i) => { acc[h || `col_${i+1}`] = cols[i]?.trim() || ""; return acc; }, {});
      });
      const result = await stageReportUpload({ report_type: "advertising", marketplace: "amazon.com", source_filename: file.name, rows: parsedRows });
      queryClient.invalidateQueries({ queryKey: ["today-decisions"] });
      queryClient.invalidateQueries({ queryKey: ["yesterday-report"] });
      showToast(`待确认：${result.total_rows} 条`);
    } catch (error) {
      showToast(error instanceof Error ? error.message : "上传失败");
    } finally { setUploading(false); }
  };

  return (
    <div className="apple-card p-6">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-[#ff9500]/10 flex items-center justify-center"><Upload size={16} className="text-[#ff9500]" /></div>
        <h3 className="text-[15px] font-semibold">广告报表入口</h3>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <label onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files?.[0]; if (f && !uploading) uploadFile(f); }}
          className={`min-h-[132px] rounded-2xl border border-dashed p-5 cursor-pointer transition-colors ${dragging ? "border-[#0F2A24] bg-[#0F2A24]/[0.04]" : "border-[#d2d2d7] hover:bg-[#fbfaf7]"}`}>
          <FileText size={22} className="text-[#0F2A24] mb-3" />
          <p className="text-[15px] font-semibold mb-1">手动上传</p>
          <p className="text-[13px] text-[#86868b] mb-3">Amazon 广告报表</p>
          <p className="text-[12px] text-[#86868b]">{uploading ? "解析中..." : "CSV / TSV / TXT"}</p>
          <input type="file" accept=".csv,.tsv,.txt" onChange={e => { const f = e.target.files?.[0]; if (f) uploadFile(f); e.target.value = ""; }} disabled={uploading} className="hidden" />
        </label>
        <button type="button" onClick={() => showToast("浏览器抓取：待接入")}
          className="min-h-[132px] rounded-2xl border border-[#d2d2d7] p-5 text-left hover:bg-[#fbfaf7] transition-colors">
          <Search size={22} className="text-[#0F2A24] mb-3" />
          <p className="text-[15px] font-semibold mb-1">浏览器抓取</p>
          <p className="text-[13px] text-[#86868b] mb-3">插件抓取</p>
          <p className="text-[12px] text-[#86868b]">待接入</p>
        </button>
      </div>
      {toast && <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-[#1d1d1f] text-white px-5 py-3 rounded-xl text-[14px] shadow-lg z-50">{toast}</div>}
    </div>
  );
}

/* ── Card 2: P0-P3 优先级处理（真实数据版）── */
function PriorityTaskCard({ pending }: { pending: DecisionItem[] }) {
  const navigate = useNavigate();
  const groups = groupByPriority(pending);

  if (pending.length === 0) {
    return (
      <div className="apple-card p-6">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-lg bg-[#0F2A24]/10 flex items-center justify-center"><Zap size={16} className="text-[#0F2A24]" /></div>
          <h3 className="text-[15px] font-semibold">事件处理优先级</h3>
        </div>
        <p className="text-[14px] text-[#86868b] text-center py-8">暂无待处理事件。上传广告报表或完成一次诊断后可生成优先级。</p>
      </div>
    );
  }

  const keys = ["p0", "p1", "p2", "p3"] as const;
  const nonEmpty = keys.filter(k => groups[k].length > 0);

  return (
    <div className="apple-card p-6">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-[#0F2A24]/10 flex items-center justify-center"><Zap size={16} className="text-[#0F2A24]" /></div>
        <h3 className="text-[15px] font-semibold">事件处理优先级</h3>
        <span className="text-[12px] text-[#86868b] ml-auto">{pending.length} 项待处理</span>
      </div>
      <div className="space-y-3">
        {nonEmpty.map((k) => {
          const cfg = PRIORITY_GROUPS[k];
          const items = groups[k];
          return (
            <div key={k} className={`rounded-xl ${cfg.bg} border ${cfg.border} p-4`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`text-[11px] font-bold text-white px-2 py-0.5 rounded-full ${cfg.color}`}>{cfg.level}</span>
                <span className="text-[12px] font-medium text-[#86868b]">{cfg.label}</span>
                <span className="text-[11px] text-[#86868b] ml-auto">{items.length} 项</span>
              </div>
              {items.map((item, i) => (
                <div key={item.id || i} className="flex items-center gap-3 py-2 border-t border-black/5 first:border-0 cursor-pointer hover:opacity-80 transition-opacity"
                  onClick={() => navigate(sourceRoute(item.source))}>
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-medium text-[#1d1d1f] truncate">{item.hypothesis}</p>
                    <p className="text-[11px] text-[#86868b]">{item.asin}{item.product_title ? ` · ${item.product_title}` : ""} · {item.source}</p>
                  </div>
                  <span className="text-[11px] font-semibold text-[#86868b] shrink-0">{item.history_signal || ""}</span>
                  <ChevronRight size={14} className="text-[#d2d2d7] shrink-0" />
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Onboarding Guide ── */
function OnboardingGuide() {
  return (
    <div className="apple-card p-6">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-[#86868b]/10 flex items-center justify-center"><HelpCircle size={16} className="text-[#86868b]" /></div>
        <h3 className="text-[15px] font-semibold">怎么用 AlignX</h3>
      </div>
      <div className="space-y-1">
        {["上传数据","诊断问题","跑测试","看结果","回流决策"].map((s, i) => (
          <div key={i} className="flex items-center gap-3 py-2">
            <span className="w-6 h-6 rounded-full bg-[#fbfaf7] flex items-center justify-center text-[12px] font-semibold text-[#0F2A24] shrink-0">{i+1}</span>
            <span className="text-[14px] font-medium">{s}</span>
            {i < 4 && <ChevronRight size={14} className="text-[#d2d2d7] shrink-0 ml-auto" />}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Focus / Queue ── */
function FocusCard({ item }: { item: DecisionItem }) {
  const queryClient = useQueryClient();
  const [starting, setStarting] = useState(false);
  const [done, setDone] = useState(false);
  const cost = item.estimated_cost != null ? `$${item.estimated_cost}` : "—";
  const blocked = item.budget_gate?.blocked;
  const handleStart = async () => {
    if (blocked) return; setStarting(true);
    try {
      await updateValidationTask(item.id, { execution_status: "running", audit_source: "today_decisions" });
      await createExecutionRecord({ validation_task_id: item.id, asin: item.asin, action_summary: item.hypothesis, cost_amount: item.estimated_cost || 0, cost_type: "ad_spend", changed_position: "listing" });
      setDone(true);
      queryClient.invalidateQueries({ queryKey: ["today-decisions"] });
    } finally { setStarting(false); }
  };
  return (
    <div className="bg-white rounded-[20px] border border-[#d2d2d7] overflow-hidden">
      <div className="bg-gradient-to-r from-[#ff3b30] to-[#ff6b5e] px-6 py-2.5 flex items-center justify-between">
        <span className="text-[11px] font-bold text-white bg-white/20 px-3 py-1 rounded-full">建议优先</span><span className="text-[12px] text-white/80">今日</span>
      </div>
      <div className="p-8">
        <h2 className="text-[22px] font-bold leading-snug mb-4 tracking-[-0.015em]">{item.hypothesis}</h2>
        <div className="space-y-2 mb-6">
          <p className="text-[14px] leading-relaxed text-[#86868b]"><strong className="text-[#1d1d1f]">为什么：</strong>基于{item.source}分析结果，系统判断这是当前成本最低、预期收益最明确的验证方向。</p>
          <p className="text-[14px] leading-relaxed text-[#86868b]"><strong className="text-[#1d1d1f]">历史信号：</strong>{item.history_signal || "暂无"}</p>
        </div>
        <div className="bg-[#fbfaf7] rounded-xl p-5 grid grid-cols-3 gap-4 mb-8">
          <div className="text-center"><div className="text-[20px] font-bold text-[#ff3b30]">{cost}</div><div className="text-[11px] text-[#86868b] mt-1">验证成本</div></div>
          <div className="text-center"><div className="text-[20px] font-bold">{item.validation_period || "3天"}</div><div className="text-[11px] text-[#86868b] mt-1">测试周期</div></div>
          <div className="text-center"><div className="text-[20px] font-bold text-[#34c759]">—</div><div className="text-[11px] text-[#86868b] mt-1">预期提升</div></div>
        </div>
        <div className="flex gap-3">
          {done ? (
            <div className="flex-1 py-3.5 rounded-full text-[15px] font-medium bg-[#34c759]/[0.08] text-[#34c759] text-center">✅ 已启动验证 · 回来看结果</div>
          ) : (
            <>
              <button className="flex-1 py-3.5 rounded-full text-[15px] font-medium bg-[#fbfaf7] text-[#1d1d1f] hover:bg-[#e8e8ed] transition-colors">不做了</button>
              <button onClick={handleStart} disabled={starting || blocked}
                className="flex-1 py-3.5 rounded-full text-[15px] font-medium bg-[#0F2A24] text-white hover:bg-[#173a32] flex items-center justify-center gap-2 disabled:opacity-60">
                {starting ? <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <ArrowRight size={16} />}
                {blocked ? "超过预算" : starting ? "启动中…" : "开始验证"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function QueueItem({ item, index, running }: { item: DecisionItem; index: number; running?: boolean }) {
  const cost = item.estimated_cost != null ? `$${item.estimated_cost}` : "—";
  return (
    <div className="apple-card p-4 flex items-center gap-4 hover:bg-[#fbfaf7] transition-colors cursor-pointer">
      <div className="w-7 h-7 rounded-full bg-[#fbfaf7] flex items-center justify-center shrink-0">
        {running ? <span className="w-2 h-2 rounded-full bg-[#ff9500] animate-pulse" /> : <span className="text-[12px] font-semibold text-[#86868b]">{index}</span>}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[14px] font-semibold truncate">{item.hypothesis}</p>
        {item.product_title && <p className="text-[12px] text-[#86868b] truncate mt-0.5">{item.asin} · {item.product_title}</p>}
      </div>
      <span className="text-[13px] font-semibold text-[#ff3b30] shrink-0">{cost}</span>
      <ChevronRight size={14} className="text-[#d2d2d7] shrink-0" />
    </div>
  );
}
