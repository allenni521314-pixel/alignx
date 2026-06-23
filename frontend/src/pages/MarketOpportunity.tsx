import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Globe, ArrowRight, TrendingUp, Shield, AlertTriangle, Target } from "lucide-react";
import { analyzeMarketOpportunity, listMarketOpportunities, MarketOpportunity as MO } from "@/lib/api";

export default function MarketOpportunity() {
  const [keyword, setKeyword] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<MO | null>(null);

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
          产品调研
        </h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          输入精准关键词搜索 Top 20 竞品，系统自动按产品形态分类并做 7 层分析。越精准的词分类越准
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
            placeholder="输入精准产品关键词，如 photocatalyst pet odor eliminator 比 pet odor eliminator 结果更准"
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

            {(result.best_opportunity_category || (result.seven_layer_result_json as any)?.best_opportunity_category) && (
              <div className="bg-[#0071e3]/[0.04] rounded-xl p-4 mb-4">
                <p className="text-[13px] font-medium text-[#0071e3] mb-1">最佳切入机会</p>
                <p className="text-[14px]">{result.best_opportunity_category || (result.seven_layer_result_json as any)?.best_opportunity_category}</p>
              </div>
            )}

            {/* Indicators */}
            <div className="grid grid-cols-3 gap-4 mb-4">
              <Indicator icon={TrendingUp} label="竞争强度" value={result.top20_competition_strength ?? "—"} />
              <Indicator icon={Target} label="进入建议" value={result.entry_level ?? "—"} />
              <Indicator icon={AlertTriangle} label="主要风险" value={result.main_risk ?? "—"} />
            </div>

            {result.price_band_judgment && (
              <div className="bg-[#f5f5f7] rounded-xl p-4">
                <p className="text-[14px] text-[#86868b] font-medium mb-1">价格带判断</p>
                <p className="text-[15px]">{result.price_band_judgment}</p>
              </div>
            )}
          </div>

          {/* Product Category Breakdown */}
          {(result.product_categories?.length > 0 ||
            (result.seven_layer_result_json && (result.seven_layer_result_json as any).product_categories?.length > 0)) && (
            (() => {
              const cats = result.product_categories || (result.seven_layer_result_json as any)?.product_categories || [];
              return (
            <div className="apple-card p-6">
              <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">
                产品分类统计
              </h3>
              <div className="space-y-3">
                {cats.map((cat: any, i: number) => (
                  <div key={i} className="bg-[#f5f5f7] rounded-xl p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[15px] font-semibold">{cat.category_name}</span>
                      <span className={`text-[12px] font-medium px-2 py-0.5 rounded-full ${
                        cat.competition_level === "低" ? "bg-[#34c759]/10 text-[#34c759]" :
                        cat.competition_level === "中" ? "bg-[#ff9500]/10 text-[#ff9500]" :
                        "bg-[#ff3b30]/10 text-[#ff3b30]"
                      }`}>
                        竞争{cat.competition_level}
                      </span>
                    </div>
                    <div className="grid grid-cols-4 gap-3 text-[13px] text-[#86868b] mb-2">
                      <span>{cat.asin_count} 个ASIN</span>
                      <span>{cat.avg_price}</span>
                      <span>⭐ {cat.avg_rating}</span>
                      <span>{cat.avg_reviews} 评</span>
                    </div>
                    {cat.key_players?.length > 0 && (
                      <p className="text-[12px] text-[#86868b] mb-1">
                        代表：{cat.key_players.slice(0, 3).join("、")}
                      </p>
                    )}
                    {cat.common_weaknesses?.length > 0 && (
                      <p className="text-[12px] text-[#ff3b30]">
                        共性弱点：{cat.common_weaknesses.join("；")}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
              );
            })()
          )}

          {/* 7-layer result */}
          {result.seven_layer_result_json && (
            <div className="apple-card p-6">
              <h3 className="text-[15px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">
                7 层分析
              </h3>
              <div className="space-y-3">
                {Object.entries(result.seven_layer_result_json)
                  .filter(([key]) => !["product_categories", "best_opportunity_category"].includes(key))
                  .map(([key, val]) => (
                  <div key={key} className="flex gap-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-[#0071e3] mt-2 shrink-0" />
                    <div>
                      <p className="text-[13px] font-medium text-[#86868b]">{key}</p>
                      <p className="text-[15px]">
                        {typeof val === "string" ? val : ""}
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
                className="apple-card p-4 flex items-center justify-between hover:bg-[#f5f5f7] transition-colors"
              >
                <div className="flex items-center gap-3">
                  <Globe size={18} className="text-[#86868b]" />
                  <div>
                    <p className="text-[15px] font-medium">{item.keyword}</p>
                    <p className="text-[13px] text-[#86868b]">{item.entry_level ?? "—"}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[12px] text-[#86868b]">
                    {item.created_at?.slice(0, 10)}
                  </span>
                  <button
                    onClick={async () => {
                      const res = await fetch(`/api/v1/market-opportunity/${item.id}`);
                      const data = await res.json();
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
