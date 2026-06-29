import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ListChecks, DollarSign, Edit3, Clock, Upload, FileText, CheckCircle2 } from "lucide-react";
import { listValidationTasks, stageReportUpload } from "@/lib/api";

export default function ExecutionRecords() {
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const { data: tasks } = useQuery({ queryKey: ["validation-tasks"], queryFn: () => listValidationTasks() });

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    const text = await file.text();
    const rows = text.split("\n").filter((r) => r.trim());
    const headers = rows[0].split(/[,\t]/).map((h) => h.trim());
    const parsedRows = rows.slice(1).map((row) => {
      const cols = row.split(/[,\t]/);
      return headers.reduce<Record<string, string>>((acc, header, index) => {
        acc[header || `column_${index + 1}`] = cols[index]?.trim() || "";
        return acc;
      }, {});
    });
    const result = await stageReportUpload({
      report_type: "advertising",
      marketplace: "amazon.com",
      source_filename: file.name,
      rows: parsedRows,
    });

    setUploading(false);
    queryClient.invalidateQueries({ queryKey: ["validation-tasks"] });
    showToast(`待确认：${result.total_rows} 条`);
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  return (
    <div className="max-w-[680px] mx-auto py-12">
      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-[36px] font-bold tracking-[-0.025em] mb-2">执行记录</h1>
        <p className="text-[17px] text-[#86868b]">
          记录每一次改动：做了什么、花了多少钱
        </p>
      </div>

      {/* Upload Ad Report */}
      <div className="apple-card p-6 mb-8">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-[#0F2A24]/[0.06] flex items-center justify-center shrink-0">
            <Upload size={20} className="text-[#0F2A24]" />
          </div>
          <div className="flex-1">
            <h2 className="text-[15px] font-semibold mb-1">上传广告报表</h2>
            <label className="apple-btn-primary inline-flex items-center gap-2 cursor-pointer text-[14px]">
              <FileText size={16} />
              {uploading ? "解析中..." : "选择 CSV 文件"}
              <input
                type="file"
                accept=".csv,.tsv,.txt"
                onChange={handleUpload}
                className="hidden"
                disabled={uploading}
              />
            </label>
            <p className="text-[11px] text-[#86868b] mt-2">CSV / TSV / TXT</p>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-3 mb-8">
        <div className="apple-card p-4 text-center">
          <ListChecks size={20} className="mx-auto mb-1.5 text-[#0F2A24]" />
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

      {/* Empty state */}
      <div className="apple-card p-16 text-center">
        <ListChecks size={32} className="text-[#d2d2d7] mx-auto mb-3" />
        <p className="text-[15px] text-[#86868b]">暂无执行记录</p>
      </div>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-[#1d1d1f] text-white px-5 py-3 rounded-xl text-[14px] shadow-lg z-50">
          <CheckCircle2 size={14} className="inline mr-2" />
          {toast}
        </div>
      )}
    </div>
  );
}
