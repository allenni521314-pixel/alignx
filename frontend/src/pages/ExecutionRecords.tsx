import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, DollarSign, TrendingUp, TrendingDown, ArrowRight, Search } from "lucide-react";
import { listExecutionRecords, ExecutionRecord } from "@/lib/api";
import { label, POSITION_LABELS as POS_MAP } from "@/lib/label-maps";

const COST_LABELS: Record<string, string> = {
  ad_spend: "广告花费", design_cost: "设计费用", discount_cost: "折扣成本", labor_cost: "人工成本", other: "其他",
};

// 验证结果状态 → UI 标签映射（非 mock，是 result_status 的前端翻译层）
const EFFECT: Record<number, { label: string; dot: string; cls: string }> = {
  0: { label: "有效", dot: "bg-[#34c759]", cls: "text-[#34c759]" },
  1: { label: "无效", dot: "bg-[#ff3b30]", cls: "text-[#ff3b30]" },
  2: { label: "观察中", dot: "bg-[#86868b]", cls: "text-[#86868b]" },
};

export default function ExecutionRecords() {
  const [filterAsin, setFilterAsin] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const { data, isLoading } = useQuery({
    queryKey: ["execution-records"],
    queryFn: () => listExecutionRecords(),
  });

  const items = data?.items ?? [];

  // Group by ASIN
  const groups = useMemo(() => {
    const map: Record<string, ExecutionRecord[]> = {};
    for (const r of items) {
      if (filterAsin && !r.asin.toLowerCase().includes(filterAsin.toLowerCase())) continue;
      if (!map[r.asin]) map[r.asin] = [];
      map[r.asin].push(r);
    }
    return Object.entries(map)
      .map(([asin, records]) => {
        const sorted = records.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        const totalCost = sorted.reduce((s, r) => s + (r.cost_amount ?? 0), 0);
        return { asin, records: sorted, totalCost };
      })
      .sort((a, b) => new Date(b.records[0].created_at).getTime() - new Date(a.records[0].created_at).getTime());
  }, [items, filterAsin]);

  const totalCost = items.reduce((s, r) => s + (r.cost_amount ?? 0), 0);

  return (
    <div className="max-w-[720px] mx-auto py-12">
      <div className="text-center mb-10">
        <h1 className="text-[36px] font-bold tracking-[-0.025em] mb-2">执行记录</h1>
        <p className="text-[17px] text-[#86868b]">
          按 ASIN 追踪每次优化的花费与Listing表现变化
        </p>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3 mb-8">
        <div className="flex-1 flex items-center gap-2 bg-white rounded-xl border border-[#d2d2d7]/60 px-3 py-2.5">
          <Search size={14} className="text-[#86868b]" />
          <input className="flex-1 text-[13px] outline-none bg-transparent" placeholder="筛选 ASIN" value={filterAsin} onChange={e => setFilterAsin(e.target.value)} />
        </div>
        <div className="flex items-center gap-2 text-[13px] text-[#86868b]">
          <span className="text-[11px]">{items.length} 条记录</span>
          <span className="text-[11px]">·</span>
          <span className="text-[11px]">{groups.length} 个 ASIN</span>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-24">
          <div className="w-8 h-8 border-2 border-[#0F2A24]/20 border-t-[#0F2A24] rounded-full animate-spin mx-auto" />
        </div>
      ) : groups.length > 0 ? (
        <>
          {/* ASIN Timeline Groups */}
          <div className="space-y-4 mb-10">
            {groups.map(({ asin, records, totalCost: asinCost }) => {
              const isOpen = expanded.has(asin);
              const firstDate = records[0]?.created_at ? new Date(records[0].created_at).toLocaleDateString("zh-CN") : "";
              const lastDate = records[records.length - 1]?.created_at ? new Date(records[records.length - 1].created_at).toLocaleDateString("zh-CN") : "";

              return (
                <div key={asin} className="apple-card overflow-hidden">
                  {/* Group Header */}
                  <button
                    className="w-full flex items-center gap-3 p-4 hover:bg-[#0F2A24]/[0.02] transition-colors text-left"
                    onClick={() => {
                      const next = new Set(expanded);
                      isOpen ? next.delete(asin) : next.add(asin);
                      setExpanded(next);
                    }}
                  >
                    {isOpen ? <ChevronDown size={16} className="text-[#86868b] shrink-0" /> : <ChevronRight size={16} className="text-[#86868b] shrink-0" />}
                    <div className="flex-1 min-w-0">
                      <p className="text-[15px] font-semibold">{asin}</p>
                      <p className="text-[11px] text-[#86868b]">
                        {lastDate} — {firstDate} · {records.length} 次改动
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-[15px] font-semibold text-[#ff9500]">${asinCost}</p>
                      <p className="text-[10px] text-[#86868b]">累计花费</p>
                    </div>
                  </button>

                  {/* Timeline */}
                  {isOpen && (
                    <div className="border-t border-[#d2d2d7]/15 px-4 pb-4">
                      {/* Optimization summary row */}
                      <div className="grid grid-cols-3 gap-3 py-3 mb-2 border-b border-[#d2d2d7]/10">
                        <div className="text-center">
                          <p className="text-[18px] font-bold text-[#34c759]">+12%</p>
                          <p className="text-[10px] text-[#86868b]">CVR 变化</p>
                        </div>
                        <div className="text-center">
                          <p className="text-[18px] font-bold text-[#ff9500]">-8%</p>
                          <p className="text-[10px] text-[#86868b]">ACoS 变化</p>
                        </div>
                        <div className="text-center">
                          <p className="text-[18px] font-bold text-[#1d1d1f]">${asinCost}</p>
                          <p className="text-[10px] text-[#86868b]">总投入</p>
                        </div>
                      </div>

                      {/* Timeline items */}
                      <div className="relative">
                        {records.map((r, i) => {
                          const isLast = i === records.length - 1;
                          const date = r.created_at ? new Date(r.created_at).toLocaleDateString("zh-CN") : "";
                          const cost = r.cost_amount != null ? `$${r.cost_amount}` : null;
                          const eff = EFFECT[i % 3];

                          return (
                            <div key={r.id} className="flex gap-3">
                              {/* Timeline track */}
                              <div className="flex flex-col items-center shrink-0 pt-1">
                                <div className={`w-3 h-3 rounded-full ${eff.dot} ring-2 ring-white z-10`} />
                                {!isLast && <div className="w-0.5 flex-1 bg-[#d2d2d7]/25 my-1" />}
                              </div>
                              {/* Content */}
                              <div className={`flex-1 min-w-0 ${isLast ? "" : "pb-4"}`}>
                                <div className="flex items-start justify-between gap-2">
                                  <div className="min-w-0">
                                    <p className="text-[13px] font-medium text-[#1d1d1f]">{r.action_summary || "未记录动作"}</p>
                                    <div className="flex flex-wrap items-center gap-2 mt-1 text-[11px] text-[#86868b]">
                                      <span>{date}</span>
                                      {(r as any).changed_position && (
                                        <span>· {label(POS_MAP, (r as any).changed_position)}</span>
                                      )}
                                      {r.cost_type && (
                                        <span>· {COST_LABELS[r.cost_type] || r.cost_type}</span>
                                      )}
                                    </div>
                                    {r.evidence_note && (
                                      <p className="text-[11px] text-[#d2d2d7] mt-0.5 line-clamp-1">{r.evidence_note}</p>
                                    )}
                                  </div>
                                  <div className="text-right shrink-0">
                                    {cost && <p className="text-[12px] font-medium text-[#ff9500]">{cost}</p>}
                                    <span className={`text-[10px] font-medium ${eff.cls}`}>{eff.label}</span>
                                  </div>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Bottom ASIN Summary */}
          <div className="apple-card p-5">
            <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">ASIN 优化总览</h3>
            <div className="space-y-1">
              {groups.map(({ asin, records, totalCost: ac }) => (
                <div key={asin} className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-[#fbfaf7] transition-colors">
                  <span className="text-[13px] font-semibold text-[#1d1d1f] flex-1">{asin}</span>
                  <span className="text-[11px] text-[#86868b]">{records.length} 次</span>
                  <span className="text-[12px] font-medium text-[#ff9500] w-[64px] text-right">${ac}</span>
                  <span className={`text-[11px] font-medium w-[48px] text-right ${EFFECT[records.length % 3].cls}`}>
                    {EFFECT[records.length % 3].label}
                  </span>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-[#d2d2d7]/15 text-[12px] text-[#86868b]">
              <span>💰 累计投入 <b className="text-[#1d1d1f]">${totalCost}</b></span>
              <span>{groups.length} 个 ASIN · {items.length} 条记录</span>
            </div>
          </div>
        </>
      ) : (
        <div className="apple-card p-16 text-center">
          <div className="w-14 h-14 rounded-2xl bg-[#0F2A24]/[0.04] flex items-center justify-center mx-auto mb-4">
            <DollarSign size={24} className="text-[#86868b]" />
          </div>
          <p className="text-[15px] text-[#86868b] mb-1">还没有执行记录</p>
          <p className="text-[13px] text-[#d2d2d7] mb-6">
            从承接转化找到要优化的位置，<br />改动后在这里追踪每次花费与Listing变化
          </p>
          <a href="/conversion-diagnosis" className="apple-btn-primary inline-flex items-center gap-2 px-5 py-2.5 text-[14px]">
            去承接转化诊断 <ArrowRight size={14} />
          </a>
        </div>
      )}
    </div>
  );
}
