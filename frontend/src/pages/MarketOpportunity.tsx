import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Globe, ArrowRight, TrendingUp, Shield, AlertTriangle, Target } from "lucide-react";
import { analyzeMarketOpportunity, listMarketOpportunities, MarketOpportunity } from "@/lib/api";

export default function MarketOpportunity() {
  const [keyword, setKeyword] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<MarketOpportunity | null>(null);

  const { data: history } = useQuery({
    queryKey: ["market-opportunity-history"],
    queryFn: () => listMarketOpportunities(),
  });

  const handleAnalyze = async () => {
    if (!keyword.trim()) return;
    setAnalyzing(true);
    try {
      const res = await analyzeMarketOpportunity(keyword.trim());
      setResult(res);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="max-w-[720px] mx-auto py-8">
      {/* Hero */}
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">
          市场机会
        </h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          输入关键词，系统扫描 Top 20 竞品，给出 7 层市场判断
        </p>
      </div>

      {/* Input */}
      <div className="apple-card p-6 mb-8">
        <div className="flex gap-3">
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
            placeholder="输入产品关键词，如 pet odor eliminator..."
            className="apple-input flex-1"
          />
          <button
            onClick={handleAnalyze}
            disabled={analyzing || !keyword.trim()}
            className="apple-btn-primary flex items-center gap-2 px-6"
          >
            {analyzing ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                分析中
              </>
            ) : (
              <>
                开始分析
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </div>
      </div>

      {/* Result */}
      {result && (
        <div className="space-y-4 mb-10">
          {/* Score card */}
          <div className="apple-card p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[20px] font-semibold tracking-tight">
                {result.market_entry_conclusion ?? "分析完成"}
              </h2>
              {result.opportunity_score != null && (
                <span className="text-[28px] font-bold text-[#0071e3]">
                  {result.opportunity_score}
                  <span className="text-sm font-normal text-[#86868b] ml-1">分</span>
                </span>
              )}
            </div>

            {/* Indicators */}
            <div className="grid grid-cols-3 gap-4 mb-4">
              <Indicator
                icon={TrendingUp}
                label="竞争强度"
                value={result.top20_competition_strength ?? "—"}
              />
              <Indicator
                icon={Target}
                label="进入建议"
                value={result.entry_level ?? "—"}
              />
              <Indicator
                icon={AlertTriangle}
                label="主要风险"
                value={result.main_risk ?? "—"}
              />
            </div>

            {result.price_band_judgment && (
              <div className="bg-[#f5f5f7] rounded-xl p-4">
                <p className="text-[14px] text-[#86868b] font-medium mb-1">价格带判断</p>
                <p className="text-[15px]">{result.price_band_judgment}</p>
              </div>
            )}
          </div>

          {/* 7-layer result */}
          {result.seven_layer_result_json && (
            <div className="apple-card p-6">
              <h3 className="text-[15px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">
                7 层分析
              </h3>
              <div className="space-y-3">
                {Object.entries(result.seven_layer_result_json).map(([key, val]) => (
                  <div key={key} className="flex gap-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-[#0071e3] mt-2 shrink-0" />
                    <div>
                      <p className="text-[13px] font-medium text-[#86868b]">{key}</p>
                      <p className="text-[15px]">
                        {typeof val === "string" ? val : JSON.stringify(val)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* History */}
      {history?.items && history.items.length > 0 && (
        <div>
          <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">
            历史记录
          </h3>
          <div className="space-y-2">
            {history.items.map((item) => (
              <div
                key={item.id}
                className="apple-card p-4 flex items-center justify-between hover:bg-[#f5f5f7] cursor-pointer transition-colors"
              >
                <div className="flex items-center gap-3">
                  <Globe size={18} className="text-[#86868b]" />
                  <div>
                    <p className="text-[15px] font-medium">{item.keyword}</p>
                    <p className="text-[13px] text-[#86868b]">{item.entry_level ?? "—"}</p>
                  </div>
                </div>
                <span className="text-[12px] text-[#86868b]">
                  {item.created_at?.slice(0, 10)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Indicator({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="bg-[#f5f5f7] rounded-xl p-3">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon size={14} className="text-[#86868b]" />
        <span className="text-[12px] text-[#86868b] font-medium">{label}</span>
      </div>
      <p className="text-[14px] font-medium leading-tight">{value}</p>
    </div>
  );
}
