import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowDownToLine, ArrowRight, AlertTriangle, Gauge } from "lucide-react";
import {
  diagnoseConversion,
  getConversionDiagnosis,
  listConversionDiagnoses,
  ConversionDiagnosis as CD,
} from "@/lib/api";

const AD_METRIC_LABELS: Record<string, string> = {
  CTR: "点击率",
  CVR: "转化率",
  ACOS: "ACOS",
  TACOS: "TACOS",
  CPC: "CPC",
  "加购率": "加购率",
  "订单量": "订单量",
  "退货率": "退货率",
  "自然排名": "自然排名",
  "广告相关性": "广告相关性",
};

const STATUS_COLOR: Record<string, string> = {
  "通过": "bg-[#34c759]/[0.06] border-[#34c759]/20",
  "需修改": "bg-[#ff9500]/[0.06] border-[#ff9500]/20",
  "严重影响转化": "bg-[#ff3b30]/[0.06] border-[#ff3b30]/20",
  "缺失": "bg-[#86868b]/[0.06] border-[#86868b]/20",
};

const STATUS_DOT: Record<string, string> = {
  "通过": "bg-[#34c759]",
  "需修改": "bg-[#ff9500]",
  "严重影响转化": "bg-[#ff3b30]",
  "缺失": "bg-[#86868b]",
};

export default function ConversionDiagnosis() {
  const [asin, setAsin] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<CD | null>(null);
  const [error, setError] = useState("");

  const { data: history } = useQuery({
    queryKey: ["conversion-diagnosis-history"],
    queryFn: () => listConversionDiagnoses(),
  });

  const handleDiagnose = async () => {
    if (!asin.trim()) return;
    setAnalyzing(true);
    setError("");
    try {
      const res = await diagnoseConversion(asin.trim());
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "请求失败");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">承接转化</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          诊断在售 Listing，找到哪个位置卡住了转化，影响哪个广告指标
        </p>
      </div>

      <div className="apple-card p-6 mb-8">
        <div className="flex gap-3">
          <input
            type="text"
            value={asin}
            onChange={(e) => setAsin(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleDiagnose()}
            placeholder="输入在售 ASIN 或 Amazon 链接"
            className="apple-input flex-1"
          />
          <button
            onClick={handleDiagnose}
            disabled={analyzing || !asin.trim()}
            className="apple-btn-primary flex items-center gap-2 px-6"
          >
            {analyzing ? (
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <>
                诊断转化
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </div>
        {error && (
          <p className="mt-3 text-[13px] text-[#ff3b30]">{error}</p>
        )}
      </div>

      {result && (
        <div className="space-y-4 mb-10">
          {/* Summary */}
          <div className="apple-card p-6">
            <h2 className="text-[20px] font-semibold mb-1">{result.product_title}</h2>
            <p className="text-[15px] text-[#86868b] mb-4">{result.overall_conclusion}</p>

            {result.biggest_breakpoint && (
              <div className="bg-[#ff3b30]/[0.04] rounded-xl p-4 mb-3 flex items-start gap-3">
                <AlertTriangle size={18} className="text-[#ff3b30] shrink-0 mt-0.5" />
                <div>
                  <p className="text-[13px] font-medium text-[#ff3b30]">最大断点</p>
                  <p className="text-[15px]">{result.biggest_breakpoint}</p>
                </div>
              </div>
            )}

            {result.priority_action && (
              <div className="bg-[#0071e3]/[0.04] rounded-xl p-4 flex items-start gap-3">
                <Gauge size={18} className="text-[#0071e3] shrink-0 mt-0.5" />
                <div>
                  <p className="text-[13px] font-medium text-[#0071e3]">优先动作</p>
                  <p className="text-[15px]">{result.priority_action}</p>
                </div>
              </div>
            )}
          </div>

          {/* Impacted ad metrics */}
          {result.impacted_ad_metrics && result.impacted_ad_metrics.length > 0 && (
            <div className="apple-card p-6">
              <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">
                受影响的广告指标
              </h3>
              <div className="flex flex-wrap gap-2">
                {result.impacted_ad_metrics.map((m) => (
                  <span
                    key={m}
                    className="px-3 py-1.5 bg-[#f5f5f7] rounded-full text-[13px] font-medium text-[#1d1d1f]"
                  >
                    {AD_METRIC_LABELS[m] ?? m}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Position-by-position diagnoses */}
          {result.position_diagnoses_json && result.position_diagnoses_json.length > 0 && (
            <div className="apple-card p-6">
              <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">
                逐位置诊断
              </h3>
              <div className="space-y-3">
                {result.position_diagnoses_json.map((d, i) => (
                  <div
                    key={i}
                    className={`rounded-xl p-4 border ${STATUS_COLOR[d.status] ?? "border-[#d2d2d7]/20"}`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <div className={`w-2 h-2 rounded-full ${STATUS_DOT[d.status] ?? "bg-[#86868b]"}`} />
                      <span className="text-[14px] font-semibold">{d.position_name}</span>
                      <span className="text-[12px] text-[#86868b] ml-auto">{d.status}</span>
                      {d.priority != null && (
                        <span className="text-[11px] text-[#86868b] bg-[#f5f5f7] px-1.5 py-0.5 rounded-full">
                          P{d.priority}
                        </span>
                      )}
                    </div>
                    {d.issue && <p className="text-[14px] mb-1.5">{d.issue}</p>}
                    {d.evidence && (
                      <p className="text-[13px] text-[#86868b] mb-1.5">{d.evidence}</p>
                    )}
                    {d.recommendation && (
                      <p className="text-[13px] text-[#0071e3] bg-[#0071e3]/[0.04] rounded-lg p-2 mt-2">
                        {d.recommendation}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {history?.items && history.items.length > 0 && (
        <div>
          <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">
            历史记录
          </h3>
          <div className="space-y-2">
            {history.items.map((item) => (
              <div key={item.id} className="apple-card p-4 flex items-center justify-between hover:bg-[#f5f5f7] transition-colors">
                <div className="flex items-center gap-3">
                  <ArrowDownToLine size={18} className="text-[#86868b]" />
                  <div>
                    <p className="text-[15px] font-medium">{item.asin}</p>
                    <p className="text-[13px] text-[#86868b] truncate max-w-[250px]">{item.product_title}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[12px] text-[#86868b]">{item.created_at?.slice(0, 10)}</span>
                  <button
                    onClick={async () => {
                      const data = await getConversionDiagnosis(item.id);
                      setResult(data);
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                    className="apple-btn-secondary text-[12px] px-3 py-1"
                  >
                    回看
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
