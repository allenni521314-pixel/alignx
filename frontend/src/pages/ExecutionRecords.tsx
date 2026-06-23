import { useQuery } from "@tanstack/react-query";
import { ListChecks, DollarSign, Edit3, Clock } from "lucide-react";
import { listValidationTasks } from "@/lib/api";

export default function ExecutionRecords() {
  const { data: tasks } = useQuery({ queryKey: ["validation-tasks"], queryFn: () => listValidationTasks() });

  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">执行记录</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          记录每一次改动：做了什么、花了多少钱、绑定哪个验证任务
        </p>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-8">
        <div className="apple-card p-4 text-center">
          <ListChecks size={20} className="mx-auto mb-1.5 text-[#0071e3]" />
          <p className="text-[22px] font-bold">{tasks?.total ?? 0}</p>
          <p className="text-[11px] text-[#86868b] mt-0.5">总记录</p>
        </div>
        <div className="apple-card p-4 text-center">
          <DollarSign size={20} className="mx-auto mb-1.5 text-[#ff9500]" />
          <p className="text-[22px] font-bold">—</p>
          <p className="text-[11px] text-[#86868b] mt-0.5">总花费</p>
        </div>
        <div className="apple-card p-4 text-center">
          <Edit3 size={20} className="mx-auto mb-1.5 text-[#34c759]" />
          <p className="text-[22px] font-bold">—</p>
          <p className="text-[11px] text-[#86868b] mt-0.5">改动位置</p>
        </div>
        <div className="apple-card p-4 text-center">
          <Clock size={20} className="mx-auto mb-1.5 text-[#86868b]" />
          <p className="text-[22px] font-bold">—</p>
          <p className="text-[11px] text-[#86868b] mt-0.5">昨日动作</p>
        </div>
      </div>

      <div className="apple-card p-16 text-center">
        <ListChecks size={32} className="text-[#d2d2d7] mx-auto mb-3" />
        <p className="text-[15px] text-[#86868b]">暂无执行记录</p>
        <p className="text-[13px] text-[#86868b]/60 mt-1">创建验证任务并执行后，记录自动生成</p>
      </div>
    </div>
  );
}
