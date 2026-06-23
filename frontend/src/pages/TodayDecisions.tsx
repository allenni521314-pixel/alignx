import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Zap, Lightbulb, AlertTriangle, TrendingUp, CheckCircle2, Play, ChevronRight } from "lucide-react";
import { getTodayDecisions, getYesterdayReport } from "@/lib/api";

export default function TodayDecisions() {
  const { data: report, isLoading } = useQuery({ queryKey: ["today-decisions"], queryFn: getTodayDecisions });
  const { data: yesterday } = useQuery({ queryKey: ["yesterday-report"], queryFn: getYesterdayReport });

  if (isLoading) {
    return (
      <div className="max-w-[800px] mx-auto py-8">
        <div className="apple-card p-16 text-center">
          <div className="w-8 h-8 border-2 border-[#0071e3]/20 border-t-[#0071e3] rounded-full animate-spin mx-auto mb-3" />
          <p className="text-[15px] text-[#86868b]">分析昨日数据中...</p>
        </div>
      </div>
    );
  }

  const decisions = report?.decisions ?? [];
  const urgent = decisions.filter((d) => d.priority >= 4);
  const inProgress = decisions.filter((d) => d.priority < 4 && d.priority >= 2);
  const suggested = decisions.filter((d) => d.priority < 2);
  const ys = yesterday?.summary;

  if (isLoading) {
    return (
      <div className="max-w-[800px] mx-auto py-8">
        <div className="apple-card p-16 text-center">
          <div className="w-8 h-8 border-2 border-[#0071e3]/20 border-t-[#0071e3] rounded-full animate-spin mx-auto mb-3" />
          <p className="text-[15px] text-[#86868b]">分析昨日数据中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[800px] mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">今日决策</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          基于昨日验证结果，今天该做什么
        </p>
      </div>

      {!report ? (
        <div className="apple-card p-16 text-center">
          <Zap size={32} className="text-[#d2d2d7] mx-auto mb-3" />
          <p className="text-[15px] text-[#86868b]">暂无决策数据</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Global Recommendation */}
          <div className="apple-card p-5 bg-gradient-to-br from-[#0071e3]/[0.03] to-white">
            <div className="flex items-center gap-2 mb-2">
              <Lightbulb size={18} className="text-[#ff9500]" />
              <h2 className="text-[15px] font-semibold">全局建议</h2>
            </div>
            <p className="text-[16px] font-medium leading-relaxed">{report.global_recommendation}</p>
            <div className="flex items-center gap-4 mt-3 text-[12px] text-[#86868b]">
              <span>{report.total_decisions} 项决策</span>
              {report.urgent_count > 0 && <span className="text-[#ff3b30] font-medium">{report.urgent_count} 项紧急</span>}
            </div>
          </div>

          {/* Yesterday Summary */}
          {ys && (
            <div className="grid grid-cols-4 gap-3">
              <MiniStat label="昨日动作" value={ys.total_executions} />
              <MiniStat label="改动位置" value={ys.changed_positions} />
              <MiniStat label="有效" value={yesterday?.validation_stats?.effective ?? 0} color="text-[#34c759]" />
              <MiniStat label="无效" value={yesterday?.validation_stats?.ineffective ?? 0} color="text-[#ff3b30]" />
            </div>
          )}

          {/* 🔴 Urgent */}
          {urgent.length > 0 && (
            <Section title="紧急" icon={AlertTriangle} color="text-[#ff3b30]" bg="bg-[#ff3b30]/[0.04]" border="border-[#ff3b30]/20">
              {urgent.map((d, i) => (
                <DecisionCard key={i} decision={d} urgent />
              ))}
            </Section>
          )}

          {/* 🟡 In Progress */}
          {inProgress.length > 0 && (
            <Section title="进行中" icon={Play} color="text-[#ff9500]" bg="bg-[#ff9500]/[0.04]" border="border-[#ff9500]/20">
              {inProgress.map((d, i) => (
                <DecisionCard key={i} decision={d} />
              ))}
            </Section>
          )}

          {/* 🔵 Suggested */}
          {suggested.length > 0 && (
            <Section title="建议" icon={TrendingUp} color="text-[#0071e3]" bg="bg-[#0071e3]/[0.04]" border="border-[#0071e3]/20">
              {suggested.map((d, i) => (
                <DecisionCard key={i} decision={d} />
              ))}
            </Section>
          )}

          {/* Empty state */}
          {decisions.length === 0 && (
            <div className="apple-card p-12 text-center">
              <CheckCircle2 size={28} className="text-[#d2d2d7] mx-auto mb-2" />
              <p className="text-[15px] text-[#86868b]">今日无待办决策</p>
              <p className="text-[13px] text-[#86868b]/60 mt-1">所有验证任务已处理完毕</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Sub-components ── */

function Section({
  title, icon: Icon, color, bg, border, children,
}: {
  title: string; icon: React.ComponentType<{ size?: number }>; color: string; bg: string; border: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <div className={`w-7 h-7 rounded-lg ${bg} flex items-center justify-center`}>
          <Icon size={14} className={color} />
        </div>
        <h2 className="text-[15px] font-semibold">{title}</h2>
      </div>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function DecisionCard({
  decision: d, urgent,
}: {
  decision: { asin: string; product_title?: string | null; current_problem?: string | null; recommended_action?: string | null; priority: number; reasoning: string; active_tasks?: Array<{ proposition: string; status: string }> };
  urgent?: boolean;
}) {
  const [showResult, setShowResult] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  return (
    <div className={`apple-card p-4 ${urgent ? "border-[#ff3b30]/30 bg-[#ff3b30]/[0.01]" : ""}`}>
      <div className="flex items-start justify-between mb-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[15px] font-semibold">{d.asin}</span>
            <Pill level={d.priority} />
          </div>
          {d.product_title && (
            <p className="text-[12px] text-[#86868b] mt-0.5 truncate max-w-[400px]">{d.product_title}</p>
          )}
        </div>
        {urgent && <AlertTriangle size={16} className="text-[#ff3b30] shrink-0" />}
      </div>

      {d.current_problem && (
        <p className="text-[13px] text-[#86868b] mb-2">{d.current_problem}</p>
      )}

      {d.recommended_action && (
        <div className="bg-[#0071e3]/[0.03] rounded-lg p-3 mb-2">
          <p className="text-[12px] font-medium text-[#0071e3] mb-0.5">建议动作</p>
          <p className="text-[13px]">{d.recommended_action}</p>
        </div>
      )}

      <p className="text-[12px] text-[#86868b] mb-2">{d.reasoning}</p>

      {d.active_tasks && d.active_tasks.length > 0 && (
        <div className="flex gap-1.5 flex-wrap mb-2">
          {d.active_tasks.map((t, j) => (
            <span key={j} className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
              t.status === "running" ? "bg-[#0071e3]/8 text-[#0071e3]" : "bg-[#f5f5f7] text-[#86868b]"
            }`}>
              {t.proposition}
            </span>
          ))}
        </div>
      )}

      <div className="flex gap-2 mt-2">
        <button
          onClick={() => setShowResult(!showResult)}
          className="apple-btn-primary text-[12px] px-3 py-1 flex items-center gap-1"
        >
          <CheckCircle2 size={12} />
          录入验证结果
        </button>
        <button
          onClick={() => navigate("/business-validation")}
          className="apple-btn-secondary text-[12px] px-3 py-1 flex items-center gap-1"
        >
          查看验证管道 <ChevronRight size={12} />
        </button>
      </div>

      {showResult && (
        <div className="mt-3 p-4 bg-[#f5f5f7] rounded-xl space-y-3">
          <p className="text-[13px] font-medium">录入验证结果</p>
          <div className="flex gap-2 flex-wrap">
            {[
              { v: "effective", l: "✅ 有效", c: "border-[#34c759] bg-[#34c759]/[0.04]" },
              { v: "ineffective", l: "❌ 无效", c: "border-[#ff3b30] bg-[#ff3b30]/[0.04]" },
              { v: "interfered", l: "⚠️ 受干扰", c: "border-[#ff9500] bg-[#ff9500]/[0.04]" },
              { v: "insufficient_data", l: "📊 数据不足", c: "border-[#86868b] bg-[#f5f5f7]" },
            ].map((opt) => (
              <button
                key={opt.v}
                onClick={async () => {
                  await fetch("/api/v1/validation-results", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      validation_task_id: d.active_tasks?.[0]?.proposition || "",
                      asin: d.asin,
                      final_result_status: opt.v,
                    }),
                  });
                  setShowResult(false);
                  queryClient.invalidateQueries({ queryKey: ["today-decisions"] });
                  queryClient.invalidateQueries({ queryKey: ["yesterday-report"] });
                }}
                className={`px-3 py-1.5 rounded-full text-[13px] border transition-colors ${opt.c}`}
              >
                {opt.l}
              </button>
            ))}
          </div>
          <button onClick={() => setShowResult(false)} className="text-[12px] text-[#86868b]">取消</button>
        </div>
      )}
    </div>
  );
}

function Pill({ level }: { level: number }) {
  const map: Record<number, { label: string; cls: string }> = {
    1: { label: "低", cls: "bg-[#f5f5f7] text-[#86868b]" },
    2: { label: "中低", cls: "bg-[#34c759]/8 text-[#34c759]" },
    3: { label: "中", cls: "bg-[#0071e3]/8 text-[#0071e3]" },
    4: { label: "高", cls: "bg-[#ff9500]/8 text-[#ff9500]" },
    5: { label: "紧急", cls: "bg-[#ff3b30]/8 text-[#ff3b30]" },
  };
  const m = map[level] ?? map[1];
  return <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${m.cls}`}>{m.label}</span>;
}

function MiniStat({ label, value, color = "text-[#86868b]" }: { label: string; value: number | string; color?: string }) {
  return (
    <div className="apple-card p-3 text-center">
      <p className={`text-[22px] font-bold ${color}`}>{value}</p>
      <p className="text-[10px] text-[#86868b] mt-0.5">{label}</p>
    </div>
  );
}
