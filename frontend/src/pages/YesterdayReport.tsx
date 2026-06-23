import { useQuery } from "@tanstack/react-query";
import { FileText, DollarSign, Target, CheckCircle2, XCircle, AlertTriangle, TrendingUp } from "lucide-react";
import { getYesterdayReport } from "@/lib/api";

export default function YesterdayReport() {
  const { data: report, isLoading } = useQuery({
    queryKey: ["yesterday-report"],
    queryFn: getYesterdayReport,
  });

  if (isLoading) {
    return (
      <div className="max-w-[760px] mx-auto py-8">
        <div className="apple-card p-16 text-center">
          <div className="w-8 h-8 border-2 border-[#0071e3]/20 border-t-[#0071e3] rounded-full animate-spin mx-auto mb-3" />
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="max-w-[760px] mx-auto py-8">
        <div className="apple-card p-16 text-center">
          <FileText size={32} className="text-[#d2d2d7] mx-auto mb-3" />
          <p className="text-[15px] text-[#86868b]">暂无数据</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[760px] mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">昨日战报</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          基于 ASIN 档案、执行记录和效果验证的每日汇总
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        <Kpi icon={TrendingUp} label="总动作" value={report.summary.total_executions} color="text-[#0071e3]" />
        <Kpi icon={DollarSign} label="总花费" value={`$${report.summary.total_cost}`} color="text-[#ff9500]" />
        <Kpi icon={DollarSign} label="广告花费" value={`$${report.summary.ad_spend ?? 0}`} color="text-[#ff3b30]" />
        <Kpi icon={Target} label="改动位置" value={report.summary.changed_positions} color="text-[#86868b]" />
        <Kpi icon={CheckCircle2} label="活跃ASIN" value={report.summary.active_asins} color="text-[#34c759]" />
      </div>

      {/* ASIN Detail List */}
      {report.profile_summaries?.length > 0 && (
        <div className="apple-card mb-6">
          <div className="p-5 border-b border-[#d2d2d7]/20">
            <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide">ASIN 明细</h3>
          </div>
          {report.profile_summaries.map((a, i) => {
            // Calculate derived metrics
            const ctr = a.impressions > 0 ? ((a.clicks / a.impressions) * 100).toFixed(2) : "—";
            const cpc = a.clicks > 0 ? (a.ad_spend / a.clicks).toFixed(2) : "—";
            const acos = a.sales > 0 ? ((a.ad_spend / a.sales) * 100).toFixed(1) : "—";

            return (
            <div key={i} className="border-b border-[#d2d2d7]/10 last:border-0">
              <div className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <p className="text-[14px] font-semibold">{a.asin}</p>
                    {a.current_problem && (
                      <p className="text-[12px] text-[#ff3b30]">{a.current_problem}</p>
                    )}
                  </div>
                </div>

                {/* Metrics grid - Amazon standard order */}
                <div className="grid grid-cols-5 gap-x-4 gap-y-3">
                  <AdMetric label="Impressions" value={Number(a.impressions).toLocaleString()} />
                  <AdMetric label="Clicks" value={Number(a.clicks).toLocaleString()} />
                  <AdMetric label="CTR" value={`${ctr}%`} />
                  <AdMetric label="CPC" value={`$${cpc}`} />
                  <AdMetric label="Spend" value={`$${a.ad_spend.toFixed(2)}`} color="text-[#ff3b30]" />
                  <AdMetric label="Orders" value={String(a.orders)} />
                  <AdMetric label="Sales" value={`$${a.sales.toFixed(2)}`} />
                  <AdMetric label="ACoS" value={acos !== "—" ? `${acos}%` : "—"} color={parseFloat(acos as string) > 30 ? "text-[#ff3b30]" : "text-[#34c759]"} />
                  <AdMetric label="CVR" value={a.clicks > 0 ? `${((a.orders / a.clicks) * 100).toFixed(2)}%` : "—"} />
                  <AdMetric label="ROAS" value={a.ad_spend > 0 && a.sales > 0 ? `${(a.sales / a.ad_spend).toFixed(2)}` : "—"} color={a.ad_spend > 0 && a.sales > 0 && (a.sales / a.ad_spend) > 3 ? "text-[#34c759]" : "text-[#ff3b30]"} />
                </div>
              </div>
            </div>
          )})}
          </div>
      )}

      {/* Recent Ads */}
      {report.recent_ads?.length > 0 && (
        <div className="apple-card mb-6">
          <div className="p-5 border-b border-[#d2d2d7]/20">
            <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide">广告花费明细</h3>
          </div>
          {report.recent_ads.map((ad, i) => (
            <div key={i} className="p-4 flex items-center justify-between border-b border-[#d2d2d7]/10 last:border-0">
              <div>
                <span className="text-[14px] font-medium">{ad.asin}</span>
                <span className="text-[13px] text-[#86868b] ml-2">{ad.summary}</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-[12px] text-[#86868b]">{ad.date}</span>
                <span className="text-[14px] font-semibold text-[#ff3b30]">${ad.cost}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Validation Stats */}
      <div className="apple-card p-6 mb-6">
        <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">验证统计</h3>
        <div className="flex gap-8">
          <Stat label="有效" value={report.validation_stats.effective} color="text-[#34c759]" />
          <Stat label="无效" value={report.validation_stats.ineffective} color="text-[#ff3b30]" />
          <Stat label="受干扰" value={report.validation_stats.interfered} color="text-[#ff9500]" />
          <Stat label="数据不足" value={report.validation_stats.insufficient_data} color="text-[#86868b]" />
        </div>
      </div>

      {/* Active Problems */}
      {report.active_problems.length > 0 && (
        <div className="apple-card p-6">
          <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">活跃问题</h3>
          {report.active_problems.map((p, i) => (
            <div key={i} className="flex items-start gap-3 p-3 bg-[#ff3b30]/[0.03] rounded-xl mb-2 last:mb-0">
              <AlertTriangle size={16} className="text-[#ff3b30] mt-0.5 shrink-0" />
              <div>
                <p className="text-[14px] font-medium">{p.asin}</p>
                <p className="text-[14px] text-[#86868b]">{p.problem}</p>
                {p.next_action && <p className="text-[13px] text-[#0071e3] mt-1">{p.next_action}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Kpi({ icon: Icon, label, value, color }: { icon: React.ComponentType<{ size?: number; className?: string }>; label: string; value: string | number; color: string }) {
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

function AdMetric({ label, value, color = "text-[#1d1d1f]" }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <p className="text-[11px] text-[#86868b]">{label}</p>
      <p className={`text-[14px] font-semibold ${color}`}>{value}</p>
    </div>
  );
}
