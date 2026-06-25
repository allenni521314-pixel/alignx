import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Zap, Search, CheckCircle2, ChevronRight,
} from "lucide-react";
import { getTodayDecisions, API_BASE, type DecisionItem } from "@/lib/api";

export default function TodayDecisions() {
  const { data: report, isLoading } = useQuery({
    queryKey: ["today-decisions"],
    queryFn: getTodayDecisions,
  });

  if (isLoading) {
    return (
      <div className="max-w-[720px] mx-auto py-8">
        <div className="apple-card p-16 text-center">
          <div className="w-8 h-8 border-2 border-[#0071e3]/20 border-t-[#0071e3] rounded-full animate-spin mx-auto" />
        </div>
      </div>
    );
  }

  const summary = report?.summary ?? { pending: 0, running: 0, effective: 0 };
  const hasData = summary.pending > 0 || summary.running > 0 || summary.effective > 0;

  return (
    <div className="max-w-[720px] mx-auto py-8">
      {/* Header */}
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">今日决策</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          {report?.global_recommendation || "先验证，再投入"}
        </p>
      </div>

      {!hasData ? (
        <EmptyState />
      ) : (
        <div className="space-y-4">
          {/* Summary bar */}
          <div className="grid grid-cols-3 gap-3 mb-2">
            <SummaryCard num={summary.pending} label="待验证" color="text-[#ff3b30]" bg="bg-[#ff3b30]/[0.06]" />
            <SummaryCard num={summary.running} label="测试中" color="text-[#ff9500]" bg="bg-[#ff9500]/[0.06]" />
            <SummaryCard num={summary.effective} label="已验证有效" color="text-[#34c759]" bg="bg-[#34c759]/[0.06]" />
          </div>

          {/* 🔴 待验证 */}
          {report.pending.length > 0 && (
            <Zone title="待验证" count={report.pending.length} dotColor="bg-[#ff3b30]">
              {report.pending.map((item) => (
                <DecisionCard key={item.id} item={item} zone="pending" />
              ))}
            </Zone>
          )}

          {/* 🟡 测试中 */}
          {report.running.length > 0 && (
            <Zone title="测试中" count={report.running.length} dotColor="bg-[#ff9500]">
              {report.running.map((item) => (
                <DecisionCard key={item.id} item={item} zone="running" />
              ))}
            </Zone>
          )}

          {/* 🟢 已验证有效 */}
          {report.effective.length > 0 && (
            <Zone title="已验证有效" count={report.effective.length} dotColor="bg-[#34c759]">
              {report.effective.map((item) => (
                <DecisionCard key={item.id} item={item} zone="effective" />
              ))}
            </Zone>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Empty state ── */

function EmptyState() {
  const navigate = useNavigate();
  return (
    <div className="apple-card p-16 text-center">
      <Search size={32} className="text-[#d2d2d7] mx-auto mb-3" />
      <h3 className="text-[17px] font-semibold mb-1">还没有假设</h3>
      <p className="text-[14px] text-[#86868b] max-w-[360px] mx-auto leading-relaxed mb-4">
        去「找机会」做一次产品调研或竞品分析，系统会自动生成待验证的假设
      </p>
      <button
        onClick={() => navigate("/market-opportunity")}
        className="inline-flex items-center gap-2 text-[14px] font-medium text-[#0071e3] hover:underline"
      >
        去产品调研 <ChevronRight size={14} />
      </button>
    </div>
  );
}

/* ── Summary card ── */

function SummaryCard({ num, label, color, bg }: { num: number; label: string; color: string; bg: string }) {
  return (
    <div className={`apple-card p-4 text-center ${bg}`}>
      <div className={`text-[28px] font-bold tracking-[-0.03em] ${color}`}>{num}</div>
      <div className="text-[12px] text-[#86868b] mt-1">{label}</div>
    </div>
  );
}

/* ── Zone ── */

function Zone({
  title, count, dotColor, children,
}: {
  title: string; count: number; dotColor: string; children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className={`w-2 h-2 rounded-full ${dotColor}`} />
        <span className="text-[13px] font-semibold text-[#86868b] uppercase tracking-[0.05em]">
          {title} · {count} 个
        </span>
      </div>
      <div className="space-y-2.5">{children}</div>
    </div>
  );
}

/* ── Decision card ── */

function DecisionCard({ item, zone }: { item: DecisionItem; zone: "pending" | "running" | "effective" }) {
  const [showResult, setShowResult] = useState(false);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const costLabel = item.estimated_cost != null ? `$${item.estimated_cost}` : "—";
  const costColor = item.estimated_cost != null && item.estimated_cost > 0 ? "text-[#ff3b30]" : "text-[#86868b]";

  return (
    <div className="apple-card overflow-hidden">
      <div className="p-5">
        {/* Top row: ASIN + source */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-medium text-[#86868b]">{item.asin}</span>
            {item.product_title && (
              <span className="text-[12px] text-[#86868b]/60 truncate max-w-[240px]">
                · {item.product_title}
              </span>
            )}
          </div>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-[#f5f5f7] text-[#86868b] font-medium">
            {item.source}
          </span>
        </div>

        {/* Hypothesis */}
        <h3 className="text-[16px] font-semibold leading-snug mb-2">{item.hypothesis}</h3>

        {/* Meta row */}
        <div className="flex items-center gap-6 mb-4">
          <MetaItem label="验证成本" value={costLabel} valueColor={costColor} />
          {zone === "running" && item.running_days != null && (
            <MetaItem label="已跑天数" value={`${item.running_days}天`} valueColor="text-[#ff9500]" />
          )}
          {zone === "running" && item.validation_period && (
            <MetaItem label="建议周期" value={item.validation_period} />
          )}
          {zone === "effective" && item.verified_at && (
            <MetaItem label="验证时间" value={item.verified_at} />
          )}
          {zone === "effective" && item.conclusion && (
            <MetaItem label="结论" value={item.conclusion} valueColor="text-[#34c759]" />
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2">
          {zone === "pending" && (
            <>
              <button className="apple-btn-secondary text-[13px] px-4 py-1.5">跳过</button>
              <button className="apple-btn-primary text-[13px] px-4 py-1.5 flex items-center gap-1">
                执行 <ChevronRight size={14} />
              </button>
            </>
          )}
          {zone === "running" && (
            <>
              <button className="apple-btn-secondary text-[13px] px-4 py-1.5">提前终止</button>
              <button
                onClick={() => setShowResult(!showResult)}
                className="apple-btn-primary text-[13px] px-4 py-1.5 flex items-center gap-1"
              >
                <CheckCircle2 size={14} />
                录入结果
              </button>
            </>
          )}
          {zone === "effective" && (
            <button
              onClick={() => navigate("/traffic-strategy")}
              className="px-4 py-1.5 rounded-full text-[13px] font-medium bg-[#34c759] text-white hover:bg-[#2db84e] transition-colors active:scale-[0.97] flex items-center gap-1"
            >
              <Zap size={14} />
              放大
            </button>
          )}
        </div>
      </div>

      {/* Inline result form */}
      {showResult && (
        <div className="border-t border-[#d2d2d7]/20 p-5 bg-[#f5f5f7]">
          <p className="text-[13px] font-medium mb-3">录入验证结果</p>
          <div className="flex gap-2 flex-wrap">
            {[
              { v: "effective", l: "✅ 有效", cls: "border-[#34c759] text-[#34c759] hover:bg-[#34c759]/[0.06]" },
              { v: "ineffective", l: "❌ 无效", cls: "border-[#ff3b30] text-[#ff3b30] hover:bg-[#ff3b30]/[0.06]" },
              { v: "interfered", l: "⚠️ 受干扰", cls: "border-[#ff9500] text-[#ff9500] hover:bg-[#ff9500]/[0.06]" },
              { v: "insufficient_data", l: "📊 数据不足", cls: "border-[#86868b] text-[#86868b] hover:bg-[#f5f5f7]" },
            ].map((opt) => (
              <button
                key={opt.v}
                onClick={async () => {
                  await fetch(`${API_BASE}/validation-results`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      validation_task_id: item.id,
                      asin: item.asin,
                      final_result_status: opt.v,
                    }),
                  });
                  setShowResult(false);
                  queryClient.invalidateQueries({ queryKey: ["today-decisions"] });
                }}
                className={`px-3 py-1.5 rounded-full text-[13px] border transition-colors ${opt.cls}`}
              >
                {opt.l}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Meta item ── */

function MetaItem({ label, value, valueColor = "text-[#1d1d1f]" }: {
  label: string; value: string; valueColor?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] text-[#86868b] uppercase tracking-[0.04em]">{label}</span>
      <span className={`text-[13px] font-semibold ${valueColor}`}>{value}</span>
    </div>
  );
}
