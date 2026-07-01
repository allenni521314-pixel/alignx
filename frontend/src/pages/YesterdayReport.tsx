import { useQuery } from "@tanstack/react-query";
import {
  TrendingUp, DollarSign, Target, CheckCircle2, XCircle, BarChart3,
} from "lucide-react";
import { getYesterdayReport } from "@/lib/api";

export default function YesterdayReport() {
  const { data: report, isLoading } = useQuery({
    queryKey: ["yesterday-report"],
    queryFn: () => getYesterdayReport(),
  });

  const ys = report?.summary;

  if (isLoading) {
    return (
      <div className="max-w-[680px] mx-auto py-12">
        <div className="apple-card p-16 text-center">
          <div className="w-8 h-8 border-2 border-[#0F2A24]/20 border-t-[#0F2A24] rounded-full animate-spin mx-auto" />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[680px] mx-auto py-12">
      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-[36px] font-bold tracking-[-0.025em] mb-2">昨日战报</h1>
        <p className="text-[17px] text-[#86868b]">验证结果 / 广告数据</p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        <KpiCard icon={TrendingUp} label="总动作" value={ys?.total_executions ?? 0} color="text-[#0F2A24]" />
        <KpiCard icon={DollarSign} label="总花费" value={`$${ys?.total_cost ?? 0}`} color="text-[#ff9500]" />
        <KpiCard icon={DollarSign} label="广告花费" value={`$${ys?.ad_spend ?? 0}`} color="text-[#ff3b30]" />
        <KpiCard icon={Target} label="改动位置" value={ys?.changed_positions ?? 0} color="text-[#86868b]" />
        <KpiCard icon={CheckCircle2} label="活跃 ASIN" value={ys?.active_asins ?? 0} color="text-[#34c759]" />
      </div>

      {/* ASIN Detail */}
      {(report?.profile_summaries?.length ?? 0) > 0 && (
        <div className="apple-card mb-6">
          <div className="p-5 border-b border-[#d2d2d7]/20">
            <h3 className="flex items-center gap-2 text-[15px] font-semibold"><BarChart3 size={16} className="text-[#0F2A24]" />ASIN 明细</h3>
          </div>
          {(report?.profile_summaries ?? []).map((a: any, i: number) => {
            const ctr = a.clicks && a.impressions ? ((a.clicks / a.impressions) * 100).toFixed(2) : "—";
            const cpc = a.clicks && a.ad_spend ? `$${(a.ad_spend / a.clicks).toFixed(2)}` : "$—";
            const acos = a.sales && a.ad_spend ? `${((a.ad_spend / a.sales) * 100).toFixed(1)}%` : "—";
            const cvr = a.clicks && a.orders ? `${((a.orders / a.clicks) * 100).toFixed(2)}%` : "—";
            const roas = a.sales && a.ad_spend ? (a.sales / a.ad_spend).toFixed(1) : "—";
            return (
              <div key={i} className="px-5 py-4 border-b border-[#d2d2d7]/10 last:border-0">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-[14px] font-semibold">{a.asin}</span>
                  {a.current_problem && <span className="text-[12px] px-1.5 py-0.5 rounded-full bg-[#ff3b30]/10 text-[#ff3b30]">{a.current_problem}</span>}
                </div>
                <div className="grid grid-cols-5 gap-x-4 gap-y-2">
                  <Metric label="Impressions" value={Number(a.impressions).toLocaleString()} />
                  <Metric label="Clicks" value={Number(a.clicks).toLocaleString()} />
                  <Metric label="CTR" value={ctr} />
                  <Metric label="CPC" value={cpc} />
                  <Metric label="Spend" value={`$${a.ad_spend}`} color="text-[#ff3b30]" />
                  <Metric label="Orders" value={String(a.orders)} />
                  <Metric label="Sales" value={`$${a.sales}`} />
                  <Metric label="ACoS" value={acos} />
                  <Metric label="CVR" value={cvr} />
                  <Metric label="ROAS" value={roas} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Ad spend detail */}
      {(report?.recent_ads?.length ?? 0) > 0 && (
        <div className="apple-card mb-6">
          <div className="p-5 border-b border-[#d2d2d7]/20">
            <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide">广告花费明细</h3>
          </div>
          {(report?.recent_ads ?? []).map((a: any, i: number) => (
            <div key={i} className="flex items-center justify-between px-5 py-3 border-b border-[#d2d2d7]/10 last:border-0 text-[14px]">
              <div>
                <span className="font-medium">{a.asin}</span>
                <span className="text-[#86868b] ml-2">{a.campaign_name || a.action_summary}</span>
              </div>
              <div className="flex items-center gap-4 text-[13px] text-[#86868b]">
                <span>{a.date?.slice(0, 10) || a.created_at?.slice(0, 10)}</span>
                <span className="text-[#ff3b30] font-medium">${a.cost_amount}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Validation stats */}
      {(report?.profile_summaries?.length ?? 0) > 0 && (
        <div className="grid grid-cols-2 gap-3">
          {(report?.profile_summaries ?? []).map((a: any, i: number) => (
            <div key={i} className="apple-card p-4">
              <p className="text-[14px] font-semibold mb-3">{a.asin}</p>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1">
                  <CheckCircle2 size={14} className="text-[#34c759]" />
                  <span className="text-[14px] font-medium">{a.effective} 有效</span>
                </div>
                <div className="flex items-center gap-1">
                  <XCircle size={14} className="text-[#ff3b30]" />
                  <span className="text-[14px] font-medium">{a.ineffective} 无效</span>
                </div>
                <span className="text-[13px] text-[#86868b]">{a.total_validations} 次验证</span>
              </div>
            </div>
          ))}
        </div>
      )}

    </div>
  );
}

function KpiCard({ icon: Icon, label, value, color }: { icon: React.ComponentType<{ size?: number; className?: string }>; label: string; value: string | number; color: string }) {
  return (
    <div className="apple-card p-4 text-center">
      <Icon size={18} className={`mx-auto mb-1.5 ${color}`} />
      <p className="text-[20px] font-bold">{value}</p>
      <p className="text-[11px] text-[#86868b] mt-0.5">{label}</p>
    </div>
  );
}

function Metric({ label, value, color = "text-[#1d1d1f]" }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <p className="text-[11px] text-[#86868b]">{label}</p>
      <p className={`text-[13px] font-semibold ${color}`}>{value}</p>
    </div>
  );
}
