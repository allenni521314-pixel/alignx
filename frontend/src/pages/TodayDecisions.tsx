import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  ChevronRight,
  ArrowRight,
  Upload,
  Search,
  HelpCircle,
  FileText,
} from "lucide-react";
import {
  createExecutionRecord,
  getTodayDecisions,
  stageReportUpload,
  updateValidationTask,
  type DecisionItem,
} from "@/lib/api";

export default function TodayDecisions() {
  const { data: report, isLoading } = useQuery({
    queryKey: ["today-decisions"],
    queryFn: getTodayDecisions,
  });

  const pending = report?.pending ?? [];
  const hasPending = pending.length > 0;
  const focus = hasPending ? pending[0] : null;
  const queue = pending.slice(1);

  return (
    <div className="max-w-[680px] mx-auto py-12">
      {/* Header */}
      <div className="text-center mb-10">
        <h1 className="text-[36px] font-bold tracking-[-0.025em] mb-2">
          今天先做这件事
        </h1>
        <p className="text-[17px] text-[#86868b]">
          最低成本验证一个假设，明天再看结果
        </p>
      </div>

      {isLoading ? (
        <div className="apple-card p-16 text-center">
          <div className="w-8 h-8 border-2 border-[#0F2A24]/20 border-t-[#0F2A24] rounded-full animate-spin mx-auto" />
        </div>
      ) : (
        <div className="space-y-5">
          {/* Card 1: 报表上传 */}
          <ReportUploadCard />

          {/* Card 2: 市场机会调研 */}
          <MarketResearchCard />

          {/* Card 3: 今日优先动作（有数据时才显示） */}
          {hasPending && (
            <div className="space-y-5">
              <FocusCard item={focus!} />
              {queue.length > 0 && (
                <div>
                  <p className="text-[13px] text-[#86868b] mb-2">
                    后面还有 {queue.length} 个假设排队
                  </p>
                  <div className="space-y-2">
                    {queue.map((item, i) => (
                      <QueueItem key={item.id} item={item} index={i + 2} />
                    ))}
                  </div>
                </div>
              )}
              {(report?.running ?? []).length > 0 && (
                <div>
                  <p className="text-[13px] font-medium text-[#86868b] mb-2">
                    测试中 · {(report?.running ?? []).length} 个
                  </p>
                  <div className="space-y-2">
                    {(report?.running ?? []).map((item) => (
                      <QueueItem key={item.id} item={item} index={0} running />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Card 4: 使用引导 */}
          <OnboardingGuide />
        </div>
      )}
    </div>
  );
}

/* ── Card 1: 报表上传 + 多源诊断 ── */

function ReportUploadCard() {
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const uploadFile = async (file: File) => {
    setUploading(true);
    try {
      const text = await file.text();
      const rows = text.split("\n").filter((r) => r.trim());
      const headers = rows[0]?.split(/[,\t]/).map((h) => h.trim()) ?? [];
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

      queryClient.invalidateQueries({ queryKey: ["today-decisions"] });
      queryClient.invalidateQueries({ queryKey: ["yesterday-report"] });
      showToast(`待确认：${result.total_rows} 条`);
    } catch (error) {
      showToast(error instanceof Error ? error.message : "上传失败");
    } finally {
      setUploading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    uploadFile(file);
    e.target.value = "";
  };

  const handleDrop = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (!file || uploading) return;
    uploadFile(file);
  };

  const handleBrowserCapture = () => {
    showToast("浏览器抓取：待接入");
  };

  return (
    <div className="apple-card p-6">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-[#ff9500]/10 flex items-center justify-center">
          <Upload size={16} className="text-[#ff9500]" />
        </div>
        <h3 className="text-[15px] font-semibold">广告报表入口</h3>
        <span className="text-[11px] text-[#86868b] ml-auto">今日决策</span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={`min-h-[132px] rounded-2xl border border-dashed p-5 cursor-pointer transition-colors ${
            dragging ? "border-[#0F2A24] bg-[#0F2A24]/[0.04]" : "border-[#d2d2d7] hover:bg-[#fbfaf7]"
          }`}
        >
          <FileText size={22} className="text-[#0F2A24] mb-3" />
          <p className="text-[15px] font-semibold mb-1">手动上传</p>
          <p className="text-[13px] text-[#86868b] mb-3">Amazon 广告报表</p>
          <p className="text-[12px] text-[#86868b]">{uploading ? "解析中..." : "CSV / TSV / TXT"}</p>
          <input
            type="file"
            accept=".csv,.tsv,.txt"
            onChange={handleFileChange}
            disabled={uploading}
            className="hidden"
          />
        </label>

        <button
          type="button"
          onClick={handleBrowserCapture}
          className="min-h-[132px] rounded-2xl border border-[#d2d2d7] p-5 text-left hover:bg-[#fbfaf7] transition-colors"
        >
          <Search size={22} className="text-[#0F2A24] mb-3" />
          <p className="text-[15px] font-semibold mb-1">浏览器抓取</p>
          <p className="text-[13px] text-[#86868b] mb-3">插件抓取</p>
          <p className="text-[12px] text-[#86868b]">待接入</p>
        </button>
      </div>

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-[#1d1d1f] text-white px-5 py-3 rounded-xl text-[14px] shadow-lg z-50">
          {toast}
        </div>
      )}
    </div>
  );
}

/* ── Card 2: 市场机会调研 ── */

function MarketResearchCard() {
  const navigate = useNavigate();
  return (
    <div className="apple-card p-6">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-[#0F2A24]/10 flex items-center justify-center">
          <Search size={16} className="text-[#0F2A24]" />
        </div>
        <h3 className="text-[15px] font-semibold">市场机会调研</h3>
        <span className="text-[11px] text-[#86868b] ml-auto">选品</span>
      </div>

      <p className="text-[14px] text-[#86868b] mb-4 leading-relaxed">
        输入精准产品词，获取 Top 20 竞品数据，系统自动按产品形态分类并给出市场机会判断。
      </p>

      <button
        onClick={() => navigate("/market-opportunity")}
        className="apple-btn-primary w-full py-3 flex items-center justify-center gap-2 text-[15px]"
      >
        <Search size={16} />
        去产品调研
        <ArrowRight size={14} />
      </button>
    </div>
  );
}

/* ── Card 4: 使用引导 ── */

function OnboardingGuide() {
  const steps = [
    {
      step: "上传数据",
      desc: "上传 ASIN 30天广告报表",
      page: "今日决策",
    },
    {
      step: "诊断问题",
      desc: "系统诊断 Listing 问题 / 广告错配",
      page: "承接转化",
    },
    {
      step: "跑测试",
      desc: "最小成本验证一个假设",
      page: "广告测试",
    },
    {
      step: "看结果",
      desc: "前一天优化有没有效果",
      page: "昨日战报",
    },
    {
      step: "回流决策",
      desc: "有效→放大投入，无效→换个假设",
      page: "今日决策",
    },
  ];

  return (
    <div className="apple-card p-6">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-[#86868b]/10 flex items-center justify-center">
          <HelpCircle size={16} className="text-[#86868b]" />
        </div>
        <h3 className="text-[15px] font-semibold">怎么用 AlignX</h3>
      </div>

      <div className="space-y-1">
        {steps.map((s, i) => (
          <div key={i} className="flex items-center gap-3 py-2">
            <span className="w-6 h-6 rounded-full bg-[#fbfaf7] flex items-center justify-center text-[12px] font-semibold text-[#0F2A24] shrink-0">
              {i + 1}
            </span>
            <div className="flex-1 min-w-0">
              <span className="text-[14px] font-medium">{s.step}</span>
              <span className="text-[13px] text-[#86868b] ml-2">{s.desc}</span>
            </div>
            <span className="text-[11px] text-[#86868b] shrink-0">{s.page}</span>
            {i < steps.length - 1 && (
              <ChevronRight size={14} className="text-[#d2d2d7] shrink-0" />
            )}
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-[#d2d2d7]/20">
        <p className="text-[13px] text-[#86868b] leading-relaxed">
          <strong className="text-[#1d1d1f]">系统能做的：</strong>
          Listing 优化、广告错配诊断
        </p>
        <p className="text-[13px] text-[#86868b] leading-relaxed mt-0.5">
          <strong className="text-[#1d1d1f]">需要你自己判断的：</strong>
          价格、库存、市场行情
        </p>
      </div>
    </div>
  );
}

/* ── Focus card ── */

function FocusCard({ item }: { item: DecisionItem }) {
  const queryClient = useQueryClient();
  const [starting, setStarting] = useState(false);
  const [done, setDone] = useState(false);
  const cost = item.estimated_cost != null ? `$${item.estimated_cost}` : "—";
  const blocked = item.budget_gate?.blocked;

  const handleStart = async () => {
    if (blocked) return;
    setStarting(true);
    try {
      await updateValidationTask(item.id, {
        execution_status: "running",
        audit_source: "today_decisions",
      });
      await createExecutionRecord({
        validation_task_id: item.id,
        asin: item.asin,
        action_summary: item.hypothesis,
        cost_amount: item.estimated_cost || 0,
        cost_type: "ad_spend",
        changed_position: "listing",
      });
      setDone(true);
      queryClient.invalidateQueries({ queryKey: ["today-decisions"] });
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="bg-white rounded-[20px] border border-[#d2d2d7] overflow-hidden">
      <div className="bg-gradient-to-r from-[#ff3b30] to-[#ff6b5e] px-6 py-2.5 flex items-center justify-between">
        <span className="text-[11px] font-bold text-white bg-white/20 px-3 py-1 rounded-full">
          建议优先
        </span>
        <span className="text-[12px] text-white/80">今日</span>
      </div>

      <div className="p-8">
        <h2 className="text-[22px] font-bold leading-snug mb-4 tracking-[-0.015em]">
          {item.hypothesis}
        </h2>

        <div className="space-y-2 mb-6">
          <p className="text-[14px] leading-relaxed text-[#86868b]">
            <strong className="text-[#1d1d1f]">为什么：</strong>
            基于{item.source}分析结果，系统判断这是当前成本最低、预期收益最明确的验证方向。
          </p>
          <p className="text-[14px] leading-relaxed text-[#86868b]">
            <strong className="text-[#1d1d1f]">历史信号：</strong>
            {item.history_signal || "暂无"}
          </p>
          <p className="text-[14px] leading-relaxed text-[#86868b]">
            <strong className="text-[#1d1d1f]">预算闸门：</strong>
            {item.budget_gate?.status || "未设置"}
            {item.budget_gate?.limit != null ? ` · 上限 $${item.budget_gate.limit}` : ""}
          </p>
          {item.product_title && (
            <p className="text-[14px] leading-relaxed text-[#86868b]">
              <strong className="text-[#1d1d1f]">来自：</strong>
              {item.source} · {item.asin} {item.product_title}
            </p>
          )}
        </div>

        <div className="bg-[#fbfaf7] rounded-xl p-5 grid grid-cols-3 gap-4 mb-8">
          <div className="text-center">
            <div className="text-[20px] font-bold text-[#ff3b30] tracking-[-0.02em]">{cost}</div>
            <div className="text-[11px] text-[#86868b] mt-1">验证成本</div>
          </div>
          <div className="text-center">
            <div className="text-[20px] font-bold tracking-[-0.02em]">
              {item.validation_period || "3天"}
            </div>
            <div className="text-[11px] text-[#86868b] mt-1">测试周期</div>
          </div>
          <div className="text-center">
            <div className="text-[20px] font-bold text-[#34c759] tracking-[-0.02em]">—</div>
            <div className="text-[11px] text-[#86868b] mt-1">预期提升</div>
          </div>
        </div>

        <div className="flex gap-3">
          {done ? (
            <div className="flex-1 py-3.5 rounded-full text-[15px] font-medium bg-[#34c759]/[0.08] text-[#34c759] text-center">
              ✅ 已启动验证 · 回来看结果
            </div>
          ) : (
            <>
              <button className="flex-1 py-3.5 rounded-full text-[15px] font-medium bg-[#fbfaf7] text-[#1d1d1f] hover:bg-[#e8e8ed] transition-colors active:scale-[0.97]">
                不做了
              </button>
              <button
                onClick={handleStart}
                disabled={starting || blocked}
                className="flex-1 py-3.5 rounded-full text-[15px] font-medium bg-[#0F2A24] text-white hover:bg-[#173a32] shadow-sm shadow-[#0F2A24]/25 transition-colors active:scale-[0.97] flex items-center justify-center gap-2 disabled:opacity-60"
              >
                {starting ? (
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <ArrowRight size={16} />
                )}
                {blocked ? "超过预算" : starting ? "启动中…" : "开始验证"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Queue item ── */

function QueueItem({ item, index, running }: { item: DecisionItem; index: number; running?: boolean }) {
  const cost = item.estimated_cost != null ? `$${item.estimated_cost}` : "—";

  return (
    <div className="apple-card p-4 flex items-center gap-4 hover:bg-[#fbfaf7] transition-colors cursor-pointer">
      <div className="w-7 h-7 rounded-full bg-[#fbfaf7] flex items-center justify-center shrink-0">
        {running ? (
          <span className="w-2 h-2 rounded-full bg-[#ff9500] animate-pulse" />
        ) : (
          <span className="text-[12px] font-semibold text-[#86868b]">{index}</span>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[14px] font-semibold truncate">{item.hypothesis}</p>
        {item.product_title && (
          <p className="text-[12px] text-[#86868b] truncate mt-0.5">{item.asin} · {item.product_title}</p>
        )}
      </div>
      {item.next_step && (
        <span className="text-[11px] px-2 py-0.5 rounded-full bg-[#34c759]/10 text-[#34c759] shrink-0">{item.next_step}</span>
      )}
      {item.history_signal && !item.next_step && (
        <span className="text-[12px] text-[#86868b] shrink-0">{item.history_signal}</span>
      )}
      <span className="text-[13px] font-semibold text-[#ff3b30] shrink-0">{cost}</span>
      <ChevronRight size={14} className="text-[#d2d2d7] shrink-0" />
    </div>
  );
}
