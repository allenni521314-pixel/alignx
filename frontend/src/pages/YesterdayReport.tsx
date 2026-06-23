import { useQuery } from "@tanstack/react-query";
import { FileText, TrendingUp, TrendingDown, Target, DollarSign, CheckCircle2, XCircle } from "lucide-react";
import { listValidationTasks, listAsinProfiles } from "@/lib/api";

export default function YesterdayReport() {
  const { data: tasks } = useQuery({ queryKey: ["validation-tasks"], queryFn: () => listValidationTasks() });
  const { data: profiles } = useQuery({ queryKey: ["asin-profiles"], queryFn: () => listAsinProfiles() });

  const profile = profiles?.items?.[0];

  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">昨日战报</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          基于 ASIN 档案、执行记录和效果验证的每日汇总
        </p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-4 gap-3 mb-8">
        <KpiCard icon={CheckCircle2} label="有效验证" value={profile?.effective_count ?? 0} color="text-[#34c759]" />
        <KpiCard icon={XCircle} label="无效验证" value={profile?.ineffective_count ?? 0} color="text-[#ff3b30]" />
        <KpiCard icon={TrendingUp} label="总验证数" value={profile?.total_validation_count ?? 0} color="text-[#0071e3]" />
        <KpiCard icon={DollarSign} label="昨日花费" value="—" color="text-[#ff9500]" />
      </div>

      {/* Main problem */}
      {profile?.current_main_problem && (
        <div className="apple-card p-6 mb-4">
          <div className="flex items-start gap-3">
            <Target size={18} className="text-[#ff3b30] mt-0.5" />
            <div>
              <p className="text-[13px] font-medium text-[#86868b] mb-1">当前主要问题</p>
              <p className="text-[15px]">{profile.current_main_problem}</p>
            </div>
          </div>
        </div>
      )}

      {/* Next recommended action */}
      {profile?.next_recommended_proposition && (
        <div className="apple-card p-6">
          <div className="flex items-start gap-3">
            <TrendingUp size={18} className="text-[#0071e3] mt-0.5" />
            <div>
              <p className="text-[13px] font-medium text-[#86868b] mb-1">下一步建议</p>
              <p className="text-[15px]">{profile.next_recommended_proposition}</p>
            </div>
          </div>
        </div>
      )}

      {!profile && (
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
  value: number | string;
  color: string;
}) {
  return (
    <div className="apple-card p-4 text-center">
      <Icon size={20} className={`mx-auto mb-1.5 ${color}`} />
      <p className="text-[22px] font-bold tracking-tight">{value}</p>
      <p className="text-[11px] text-[#86868b] mt-0.5">{label}</p>
    </div>
  );
}
