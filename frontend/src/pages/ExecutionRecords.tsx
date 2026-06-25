import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ListChecks, DollarSign, Edit3, Clock, Upload, FileText, CheckCircle2 } from "lucide-react";
import { listValidationTasks, API_BASE } from "@/lib/api";

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
    const headers = rows[0].toLowerCase().split(/[,\t]/);

    // Try to find relevant columns
    const asinIdx = headers.findIndex((h) => h.includes("asin") || h.includes("product"));
    const spendIdx = headers.findIndex((h) => h.includes("spend") || h.includes("cost") || h.includes("花费"));
    const dateIdx = headers.findIndex((h) => h.includes("date") || h.includes("日期"));
    const campaignIdx = headers.findIndex((h) => h.includes("campaign") || h.includes("广告活动"));
    const impressionsIdx = headers.findIndex((h) => h.includes("impression") || h.includes("曝光"));
    const clicksIdx = headers.findIndex((h) => h.includes("click") || h.includes("点击"));
    const ordersIdx = headers.findIndex((h) => h.includes("order") || h.includes("订单"));
    const salesIdx = headers.findIndex((h) => h.includes("sales") || h.includes("销售额"));
    const ctrIdx = headers.findIndex((h) => h.includes("ctr"));
    const cpcIdx = headers.findIndex((h) => h.includes("cpc"));

    let created = 0;
    for (let i = 1; i < rows.length; i++) {
      const cols = rows[i].split(/[,\t]/);
      const asin = asinIdx >= 0 ? cols[asinIdx]?.trim() : "";
      const spend = spendIdx >= 0 ? parseFloat(cols[spendIdx]) || 0 : 0;
      if (!asin || !spend) continue;

      // Build ad metrics
      const metrics: Record<string, string> = {
        type: "ad_metrics",
        campaign: campaignIdx >= 0 ? cols[campaignIdx]?.trim() || "" : "",
      };
      if (impressionsIdx >= 0) metrics.impressions = cols[impressionsIdx]?.trim() || "0";
      if (clicksIdx >= 0) metrics.clicks = cols[clicksIdx]?.trim() || "0";
      if (ordersIdx >= 0) metrics.orders = cols[ordersIdx]?.trim() || "0";
      if (salesIdx >= 0) metrics.sales = cols[salesIdx]?.trim() || "0";
      if (ctrIdx >= 0) metrics.ctr = cols[ctrIdx]?.trim() || "0";
      if (cpcIdx >= 0) metrics.cpc = cols[cpcIdx]?.trim() || "0";

      await fetch(`${API_BASE}/execution-records`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          asin,
          validation_task_id: "",
          action_summary: campaignIdx >= 0 ? cols[campaignIdx]?.trim() || "广告投放" : "广告投放",
          cost_amount: spend,
          cost_type: "ad_spend",
          evidence_note: JSON.stringify(metrics),
        }),
      });
      created++;
    }

    setUploading(false);
    queryClient.invalidateQueries({ queryKey: ["validation-tasks"] });
    showToast(`导入完成：${created} 条广告记录`);
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">执行记录</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          记录每一次改动：做了什么、花了多少钱、绑定哪个验证任务
        </p>
      </div>

      {/* Upload Ad Report */}
      <div className="apple-card p-6 mb-8">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-[#0071e3]/[0.06] flex items-center justify-center shrink-0">
            <Upload size={20} className="text-[#0071e3]" />
          </div>
          <div className="flex-1">
            <h2 className="text-[15px] font-semibold mb-1">上传广告报表</h2>
            <p className="text-[13px] text-[#86868b] mb-3">
              从 Amazon Advertising Console 下载广告报表 CSV，自动解析花费并关联到 ASIN
            </p>
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
            <p className="text-[11px] text-[#86868b] mt-2">
              支持 Amazon Sponsored Products / Sponsored Brands 报表格式。自动识别 ASIN、花费、日期列。
            </p>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
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

      {/* Empty state */}
      <div className="apple-card p-16 text-center">
        <ListChecks size={32} className="text-[#d2d2d7] mx-auto mb-3" />
        <p className="text-[15px] text-[#86868b]">暂无执行记录</p>
        <p className="text-[13px] text-[#86868b]/60 mt-1">上传广告报表或创建验证任务后，记录自动生成</p>
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
