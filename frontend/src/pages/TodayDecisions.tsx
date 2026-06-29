import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ChevronRight, ArrowRight } from "lucide-react";
import {
  createExecutionRecord,
  getTodayDecisions,
  updateValidationTask,
  type DecisionItem,
} from "@/lib/api";

export default function TodayDecisions() {
  const { data: report, isLoading } = useQuery({
    queryKey: ["today-decisions"],
    queryFn: getTodayDecisions,
  });

  if (isLoading) {
    return (
      <div className="max-w-[680px] mx-auto py-12">
        <div className="apple-card p-16 text-center">
          <div className="w-8 h-8 border-2 border-[#0F2A24]/20 border-t-[#0F2A24] rounded-full animate-spin mx-auto" />
        </div>
      </div>
    );
  }

  const pending = report?.pending ?? [];
  const hasPending = pending.length > 0;
  const focus = hasPending ? pending[0] : null;
  const queue = pending.slice(1);

  return (
    <div className="max-w-[680px] mx-auto py-12">
      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-[36px] font-bold tracking-[-0.025em] mb-2">
          今天先做这件事
        </h1>
        <p className="text-[17px] text-[#86868b]">
          最低成本验证一个假设，明天再看结果
        </p>
      </div>

      {!hasPending ? (
        <EmptyState />
      ) : (
        <div className="space-y-6">
          {/* Main focus card */}
          <FocusCard item={focus!} />

          {/* Queue */}
          {queue.length > 0 && (
            <div>
              <p className="text-[13px] text-[#86868b] mb-2">
                后面还有 {queue.length} 个假设排队
              </p>
              <div className="space-y-2">
                {queue.map((item, i) => (
                  <QueueItem key={item.id} item={item} index={i + 2} />
                ))}
              </div>
            </div>
          )}

          {/* Running section */}
          {(report?.running ?? []).length > 0 && (
            <div className="mt-10">
              <p className="text-[13px] font-medium text-[#86868b] mb-2">
                测试中 · {(report?.running ?? []).length} 个
              </p>
              <div className="space-y-2">
                {(report?.running ?? []).map((item) => (
                  <QueueItem key={item.id} item={item} index={0} running />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Focus card ── */

function FocusCard({ item }: { item: DecisionItem }) {
  const queryClient = useQueryClient();
  const [starting, setStarting] = useState(false);
  const [done, setDone] = useState(false);
  const cost = item.estimated_cost != null ? `$${item.estimated_cost}` : "—";
  const blocked = item.budget_gate?.blocked;

  const handleStart = async () => {
    if (blocked) return;
    setStarting(true);
    try {
      await updateValidationTask(item.id, {
        execution_status: "running",
        audit_source: "today_decisions",
      });
      await createExecutionRecord({
        validation_task_id: item.id,
        asin: item.asin,
        action_summary: item.hypothesis,
        cost_amount: item.estimated_cost || 0,
        cost_type: "ad_spend",
        changed_position: "listing",
      });
      setDone(true);
      queryClient.invalidateQueries({ queryKey: ["today-decisions"] });
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="bg-white rounded-[20px] border border-[#d2d2d7] overflow-hidden">
      {/* Red header bar */}
      <div className="bg-gradient-to-r from-[#ff3b30] to-[#ff6b5e] px-6 py-2.5 flex items-center justify-between">
        <span className="text-[11px] font-bold text-white bg-white/20 px-3 py-1 rounded-full">
          建议优先
        </span>
        <span className="text-[12px] text-white/80">2026.06.25</span>
      </div>

      <div className="p-8">
        {/* Hypothesis */}
        <h2 className="text-[22px] font-bold leading-snug mb-4 tracking-[-0.015em]">
          {item.hypothesis}
        </h2>

        {/* Why */}
        <div className="space-y-2 mb-6">
          <p className="text-[14px] leading-relaxed text-[#86868b]">
            <strong className="text-[#1d1d1f]">为什么：</strong>
            基于{item.source}分析结果，系统判断这是当前成本最低、预期收益最明确的验证方向。
          </p>
          <p className="text-[14px] leading-relaxed text-[#86868b]">
            <strong className="text-[#1d1d1f]">历史信号：</strong>
            {item.history_signal || "暂无"}
          </p>
          <p className="text-[14px] leading-relaxed text-[#86868b]">
            <strong className="text-[#1d1d1f]">预算闸门：</strong>
            {item.budget_gate?.status || "未设置"}
            {item.budget_gate?.limit != null ? ` · 上限 $${item.budget_gate.limit}` : ""}
          </p>
          {item.product_title && (
            <p className="text-[14px] leading-relaxed text-[#86868b]">
              <strong className="text-[#1d1d1f]">来自：</strong>
              {item.source} · {item.asin} {item.product_title}
            </p>
          )}
        </div>

        {/* Metrics */}
        <div className="bg-[#fbfaf7] rounded-xl p-5 grid grid-cols-3 gap-4 mb-8">
          <div className="text-center">
            <div className="text-[20px] font-bold text-[#ff3b30] tracking-[-0.02em]">{cost}</div>
            <div className="text-[11px] text-[#86868b] mt-1">验证成本</div>
          </div>
          <div className="text-center">
            <div className="text-[20px] font-bold tracking-[-0.02em]">
              {item.validation_period || "3天"}
            </div>
            <div className="text-[11px] text-[#86868b] mt-1">测试周期</div>
          </div>
          <div className="text-center">
            <div className="text-[20px] font-bold text-[#34c759] tracking-[-0.02em]">—</div>
            <div className="text-[11px] text-[#86868b] mt-1">预期提升</div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          {done ? (
            <div className="flex-1 py-3.5 rounded-full text-[15px] font-medium bg-[#34c759]/[0.08] text-[#34c759] text-center">
              ✅ 已启动验证 · 3天后回来看结果
            </div>
          ) : (
            <>
              <button className="flex-1 py-3.5 rounded-full text-[15px] font-medium bg-[#fbfaf7] text-[#1d1d1f] hover:bg-[#e8e8ed] transition-colors active:scale-[0.97]">
                不做了
              </button>
              <button
                onClick={handleStart}
                disabled={starting || blocked}
                className="flex-1 py-3.5 rounded-full text-[15px] font-medium bg-[#0F2A24] text-white hover:bg-[#173a32] shadow-sm shadow-[#0F2A24]/25 transition-colors active:scale-[0.97] flex items-center justify-center gap-2 disabled:opacity-60"
              >
                {starting ? (
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <ArrowRight size={16} />
                )}
                {blocked ? "超过预算" : starting ? "启动中..." : "开始验证"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Queue item ── */

function QueueItem({ item, index, running }: { item: DecisionItem; index: number; running?: boolean }) {
  const cost = item.estimated_cost != null ? `$${item.estimated_cost}` : "—";

  return (
    <div className="apple-card p-4 flex items-center gap-4 hover:bg-[#fbfaf7] transition-colors cursor-pointer">
      <div className="w-7 h-7 rounded-full bg-[#fbfaf7] flex items-center justify-center shrink-0">
        {running ? (
          <span className="w-2 h-2 rounded-full bg-[#ff9500] animate-pulse" />
        ) : (
          <span className="text-[12px] font-semibold text-[#86868b]">{index}</span>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[14px] font-semibold truncate">{item.hypothesis}</p>
        {item.product_title && (
          <p className="text-[12px] text-[#86868b] truncate mt-0.5">{item.asin} · {item.product_title}</p>
        )}
      </div>
      {item.next_step && (
        <span className="text-[11px] px-2 py-0.5 rounded-full bg-[#34c759]/10 text-[#34c759] shrink-0">{item.next_step}</span>
      )}
      {item.history_signal && !item.next_step && (
        <span className="text-[12px] text-[#86868b] shrink-0">{item.history_signal}</span>
      )}
      <span className="text-[13px] font-semibold text-[#ff3b30] shrink-0">{cost}</span>
      <ChevronRight size={14} className="text-[#d2d2d7] shrink-0" />
    </div>
  );
}

/* ── Empty state ── */

function EmptyState() {
  const navigate = useNavigate();
  return (
    <div className="apple-card p-16 text-center">
      <div className="w-12 h-12 rounded-full bg-[#fbfaf7] flex items-center justify-center mx-auto mb-4">
        <ChevronRight size={20} className="text-[#d2d2d7]" />
      </div>
      <h3 className="text-[17px] font-semibold mb-1">还没有假设</h3>
      <p className="text-[14px] text-[#86868b] max-w-[300px] mx-auto leading-relaxed mb-4">
        去做一次产品调研或竞品分析，系统会自动生成待验证的假设
      </p>
      <button
        onClick={() => navigate("/market-opportunity")}
        className="text-[14px] font-medium text-[#0F2A24] hover:underline"
      >
        去产品调研 →
      </button>
    </div>
  );
}
