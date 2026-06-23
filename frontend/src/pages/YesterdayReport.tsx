import { useQuery } from "@tanstack/react-query";
import { FileText, CheckCircle2, XCircle, AlertTriangle, DollarSign, Target, TrendingUp } from "lucide-react";
import { getYesterdayReport } from "@/lib/api";

export default function YesterdayReport() {
  const { data: report, isLoading } = useQuery({
    queryKey: ["yesterday-report"],
    queryFn: getYesterdayReport,
  });

  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">昨日战报</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          基于 ASIN 档案、执行记录和效果验证的每日汇总
        </p>
      </div>

      {isLoading ? (
        <div className="apple-card p-16 text-center">
          <div className="w-8 h-8 border-2 border-[#0071e3]/20 border-t-[#0071e3] rounded-full animate-spin mx-auto mb-3" />
          <p className="text-[15px] text-[#86868b]">生成战报中...</p>
        </div>
      ) : report ? (
        <div className="space-y-4">
          {/* Summary KPI cards */}
          <div className="grid grid-cols-5 gap-3">
            <KpiCard icon={TrendingUp} label="总动作" value={report.summary.total_executions} color="text-[#0071e3]" />
            <KpiCard icon={DollarSign} label="总花费" value={`$${report.summary.total_cost}`} color="text-[#ff9500]" />
            <KpiCard icon={Target} label="改动位置" value={report.summary.changed_positions} color="text-[#86868b]" />
            <KpiCard icon={CheckCircle2} label="活跃ASIN" value={report.summary.active_asins} color="text-[#34c759]" />
            <KpiCard icon={AlertTriangle} label="待处理" value={report.summary.pending_tasks} color="text-[#ff3b30]" />
          </div>

          {/* Validation stats */}
          <div className="apple-card p-6">
            <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">验证统计</h3>
            <div className="flex gap-8">
              <Stat label="有效" value={report.validation_stats.effective} color="text-[#34c759]" />
              <Stat label="无效" value={report.validation_stats.ineffective} color="text-[#ff3b30]" />
              <Stat label="受干扰" value={report.validation_stats.interfered} color="text-[#ff9500]" />
              <Stat label="数据不足" value={report.validation_stats.insufficient_data} color="text-[#86868b]" />
            </div>
          </div>

          {/* Active problems */}
          {report.active_problems.length > 0 && (
            <div className="apple-card p-6">
              <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">
                活跃问题
              </h3>
              <div className="space-y-3">
                {report.active_problems.map((p, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 bg-[#ff3b30]/[0.03] rounded-xl">
                    <AlertTriangle size={16} className="text-[#ff3b30] mt-0.5 shrink-0" />
                    <div>
                      <p className="text-[14px] font-medium">{p.asin}</p>
                      <p className="text-[14px] text-[#86868b]">{p.problem}</p>
                      {p.next_action && (
                        <p className="text-[13px] text-[#0071e3] mt-1">{p.next_action}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="apple-card p-16 text-center">
          <FileText size={32} className="text-[#d2d2d7] mx-auto mb-3" />
          <p className="text-[15px] text-[#86868b]">暂无数据</p>
          <p className="text-[13px] text-[#86868b]/60 mt-1">完成验证后自动生成战报</p>
        </div>
      )}
    </div>
  );
}

function KpiCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div className="apple-card p-3 text-center">
      <Icon size={18} className={`mx-auto mb-1 ${color}`} />
      <p className="text-[20px] font-bold tracking-tight">{value}</p>
      <p className="text-[10px] text-[#86868b] mt-0.5">{label}</p>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <p className={`text-[28px] font-bold ${color}`}>{value}</p>
      <p className="text-[13px] text-[#86868b]">{label}</p>
    </div>
  );
}
