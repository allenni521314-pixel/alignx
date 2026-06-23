import { useQuery } from "@tanstack/react-query";
import { Zap, Lightbulb, AlertTriangle, TrendingUp } from "lucide-react";
import { getTodayDecisions } from "@/lib/api";

export default function TodayDecisions() {
  const { data: report, isLoading } = useQuery({
    queryKey: ["today-decisions"],
    queryFn: getTodayDecisions,
  });

  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">今日决策</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          基于昨日验证结果，今天该做什么
        </p>
      </div>

      {isLoading ? (
        <div className="apple-card p-16 text-center">
          <div className="w-8 h-8 border-2 border-[#0071e3]/20 border-t-[#0071e3] rounded-full animate-spin mx-auto mb-3" />
          <p className="text-[15px] text-[#86868b]">生成决策中...</p>
        </div>
      ) : report ? (
        <div className="space-y-4">
          {/* Global recommendation */}
          <div className="apple-card p-6 bg-gradient-to-br from-[#0071e3]/[0.04] to-white">
            <div className="flex items-center gap-2 mb-2">
              <Lightbulb size={20} className="text-[#ff9500]" />
              <h2 className="text-[17px] font-semibold">全局建议</h2>
            </div>
            <p className="text-[16px] font-medium">{report.global_recommendation}</p>
            <div className="flex gap-4 mt-3">
              <span className="text-[13px] text-[#86868b]">
                {report.total_decisions} 项决策
              </span>
              {report.urgent_count > 0 && (
                <span className="text-[13px] text-[#ff3b30] font-medium">
                  {report.urgent_count} 项紧急
                </span>
              )}
            </div>
          </div>

          {/* Per-ASIN decisions */}
          {report.decisions.map((d, i) => (
            <div
              key={i}
              className={`apple-card p-5 ${
                d.priority >= 4 ? "border-[#ff3b30]/30 bg-[#ff3b30]/[0.02]" : ""
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[15px] font-semibold">{d.asin}</span>
                    {d.priority >= 4 && (
                      <AlertTriangle size={14} className="text-[#ff3b30]" />
                    )}
                    <PriorityBadge level={d.priority} />
                  </div>
                  {d.product_title && (
                    <p className="text-[13px] text-[#86868b] mt-0.5">{d.product_title}</p>
                  )}
                </div>
              </div>

              {d.current_problem && (
                <p className="text-[14px] text-[#86868b] mb-2">{d.current_problem}</p>
              )}

              {d.recommended_action && (
                <div className="bg-[#0071e3]/[0.04] rounded-lg p-3 mb-2">
                  <p className="text-[13px] font-medium text-[#0071e3]">建议动作</p>
                  <p className="text-[14px]">{d.recommended_action}</p>
                </div>
              )}

              <p className="text-[13px] text-[#86868b] leading-relaxed">{d.reasoning}</p>

              {d.active_tasks && d.active_tasks.length > 0 && (
                <div className="mt-3 flex gap-2 flex-wrap">
                  {d.active_tasks.map((t, j) => (
                    <span
                      key={j}
                      className={`px-2 py-1 rounded-full text-[11px] font-medium ${
                        t.status === "running"
                          ? "bg-[#0071e3]/10 text-[#0071e3]"
                          : "bg-[#f5f5f7] text-[#86868b]"
                      }`}
                    >
                      {t.proposition}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="apple-card p-16 text-center">
          <Zap size={32} className="text-[#d2d2d7] mx-auto mb-3" />
          <p className="text-[15px] text-[#86868b]">暂无决策数据</p>
          <p className="text-[13px] text-[#86868b]/60 mt-1">验证闭环完成后自动生成</p>
        </div>
      )}
    </div>
  );
}

function PriorityBadge({ level }: { level: number }) {
  const colors: Record<number, string> = {
    1: "bg-[#f5f5f7] text-[#86868b]",
    2: "bg-[#34c759]/10 text-[#34c759]",
    3: "bg-[#0071e3]/10 text-[#0071e3]",
    4: "bg-[#ff9500]/10 text-[#ff9500]",
    5: "bg-[#ff3b30]/10 text-[#ff3b30]",
  };
  const labels: Record<number, string> = {
    1: "低", 2: "中低", 3: "中", 4: "高", 5: "紧急",
  };
  return (
    <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${colors[level] ?? colors[1]}`}>
      {labels[level] ?? level}
    </span>
  );
}
