import { useQuery } from "@tanstack/react-query";
import { listValidationTasks, listAsinProfiles } from "@/lib/api";
import { FileText } from "lucide-react";

export default function YesterdayReport() {
  const { data: tasks } = useQuery({ queryKey: ["validation-tasks"], queryFn: () => listValidationTasks() });
  const { data: profiles } = useQuery({ queryKey: ["asin-profiles"], queryFn: () => listAsinProfiles() });

  return (
    <div className="max-w-4xl">
      <div className="flex items-center gap-3 mb-6">
        <FileText className="text-brand-600" size={24} />
        <h1 className="text-2xl font-bold">昨日战报</h1>
      </div>
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <p className="text-gray-500">数据来自 ASIN 档案 + 执行记录 + 效果验证 + 广告报表</p>
        <p className="text-sm text-gray-400 mt-2">验证任务：{tasks?.total ?? 0} | ASIN 档案：{profiles?.total ?? 0}</p>
      </div>
    </div>
  );
}
