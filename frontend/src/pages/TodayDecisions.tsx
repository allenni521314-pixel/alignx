import { useQuery } from "@tanstack/react-query";
import { Zap, Lightbulb, ArrowRight } from "lucide-react";
import { listAsinProfiles, listValidationTasks } from "@/lib/api";

export default function TodayDecisions() {
  const { data: profiles } = useQuery({ queryKey: ["asin-profiles"], queryFn: () => listAsinProfiles() });
  const { data: tasks } = useQuery({ queryKey: ["validation-tasks"], queryFn: () => listValidationTasks() });

  const profile = profiles?.items?.[0];

  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">今日决策</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          基于昨日验证结果，今天该做什么
        </p>
      </div>

      {profile ? (
        <div className="space-y-4">
          {/* Recommendation */}
          <div className="apple-card p-6 bg-gradient-to-br from-[#0071e3]/[0.04] to-white">
            <div className="flex items-center gap-2 mb-3">
              <Lightbulb size={20} className="text-[#ff9500]" />
              <h2 className="text-[17px] font-semibold">今日建议</h2>
            </div>
            <p className="text-[17px] font-medium mb-2">
              {profile.next_recommended_proposition ?? "暂无建议"}
            </p>
            {profile.current_main_problem && (
              <p className="text-[14px] text-[#86868b]">
                当前问题：{profile.current_main_problem}
              </p>
            )}
          </div>

          {/* Learning summary */}
          {profile.asin_learning_summary && (
            <div className="apple-card p-6">
              <h3 className="text-[13px] font-semibold text-[#86868b] mb-3">经验沉淀</h3>
              <p className="text-[15px] leading-relaxed">{profile.asin_learning_summary}</p>
            </div>
          )}

          {/* Stats */}
          <div className="apple-card p-6">
            <h3 className="text-[13px] font-semibold text-[#86868b] mb-3">验证统计</h3>
            <div className="flex gap-6">
              <Stat label="有效" value={profile.effective_count} color="text-[#34c759]" />
              <Stat label="无效" value={profile.ineffective_count} color="text-[#ff3b30]" />
              <Stat label="干扰" value={profile.interfered_count} color="text-[#ff9500]" />
              <Stat label="数据不足" value={profile.insufficient_data_count} color="text-[#86868b]" />
            </div>
          </div>

          {tasks?.items && tasks.items.length > 0 && (
            <div className="apple-card p-6">
              <h3 className="text-[13px] font-semibold text-[#86868b] mb-3">进行中的验证</h3>
              {tasks.items.slice(0, 5).map((t) => (
                <div key={t.id} className="flex items-center justify-between py-2 border-b border-[#d2d2d7]/20 last:border-0">
                  <span className="text-[14px]">{t.proposition_name ?? t.proposition_code}</span>
                  <span className="text-[12px] text-[#86868b]">{t.execution_status}</span>
                </div>
              ))}
            </div>
          )}
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

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <p className={`text-[24px] font-bold ${color}`}>{value}</p>
      <p className="text-[12px] text-[#86868b]">{label}</p>
    </div>
  );
}
