import { useQuery } from "@tanstack/react-query";
import { listValidationTasks } from "@/lib/api";
import { Play, DollarSign } from "lucide-react";

export default function ExecutionRecords() {
  const { data: tasks } = useQuery({ queryKey: ["validation-tasks"], queryFn: () => listValidationTasks() });

  return (
    <div className="max-w-4xl">
      <div className="flex items-center gap-3 mb-6">
        <Play className="text-brand-600" size={24} />
        <h1 className="text-2xl font-bold">执行记录</h1>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-sm text-gray-500">昨日动作</p>
          <p className="text-2xl font-bold">{tasks?.total ?? 0}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-sm text-gray-500 flex items-center gap-1"><DollarSign size={14} /> 昨日花费</p>
          <p className="text-2xl font-bold">—</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-sm text-gray-500">改动位置</p>
          <p className="text-2xl font-bold">—</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
        执行记录详情 — Phase 4 实现
      </div>
    </div>
  );
}
