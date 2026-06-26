import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, TrendingUp, AlertTriangle, Target, Search, Globe, ChevronRight } from "lucide-react";
import { analyzeMarketOpportunity, getMarketOpportunity, listMarketOpportunities, MarketOpportunity as MO } from "@/lib/api";
import { useNavigate } from "react-router-dom";

export default function ProductResearch() {
  const navigate = useNavigate();
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
    <div className="max-w-[680px] mx-auto py-12">
      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-[36px] font-bold tracking-[-0.025em] mb-2">产品调研</h1>
        <p className="text-[17px] text-[#86868b]">关键词</p>
      </div>

      {/* Input */}
      <div className="bg-white rounded-[20px] border border-[#d2d2d7] p-8 mb-8">
        <div className="flex items-center gap-3 mb-3">
          <Search size={20} className="text-[#86868b]" />
          <p className="text-[15px] font-semibold">搜索市场机会</p>
        </div>
        <div className="flex gap-3">
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
            placeholder="输入精准产品关键词"
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
          <div className="bg-white rounded-[20px] border border-[#d2d2d7] p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[20px] font-semibold">
                {result.market_entry_conclusion ?? "分析完成"}
              </h2>
              {result.opportunity_score != null && (
                <span className="text-[28px] font-bold text-[#0071e3]">
                  {result.opportunity_score}
                  <span className="text-sm font-normal text-[#86868b] ml-1">分</span>
                </span>
              )}
            </div>

            {result.best_opportunity_category && (
              <div className="bg-[#0071e3]/[0.04] rounded-xl p-4 mb-4">
                <p className="text-[13px] font-medium text-[#0071e3] mb-1">最佳切入机会</p>
                <p className="text-[14px]">{result.best_opportunity_category}</p>
              </div>
            )}

            <div className="grid grid-cols-3 gap-4 mb-4">
              <MiniCard icon={TrendingUp} label="竞争强度" value={result.top20_competition_strength ?? "—"} />
              <MiniCard icon={Target} label="进入建议" value={result.entry_level ?? "—"} />
              <MiniCard icon={AlertTriangle} label="主要风险" value={result.main_risk ?? "—"} />
            </div>

            {result.price_band_judgment && (
              <div className="bg-[#f5f5f7] rounded-xl p-4">
                <p className="text-[13px] text-[#86868b] font-medium mb-1">价格带判断</p>
                <p className="text-[15px]">{result.price_band_judgment}</p>
              </div>
            )}

            {result.next_action && (
              <div className="mt-4 pt-4 border-t border-[#d2d2d7]/20">
                <p className="text-[14px] font-medium text-[#0071e3] mb-2">{result.next_action}</p>
                <button
                  onClick={() => navigate("/competitor-analysis")}
                  className="apple-btn-primary flex items-center gap-2"
                >
                  竞品分析
                  <ChevronRight size={16} />
                </button>
              </div>
            )}
          </div>

          {/* Product categories */}
          {((result.product_categories?.length ?? 0) > 0) && (
            <div className="bg-white rounded-[20px] border border-[#d2d2d7] p-6">
              <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">
                产品分类统计
              </h3>
              <div className="space-y-3">
                {(result.product_categories ?? []).map((cat, i) => (
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
                    {cat.common_weaknesses?.length > 0 && (
                      <p className="text-[12px] text-[#ff3b30]">
                        共性弱点：{cat.common_weaknesses.join("；")}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 7-layer */}
          {result.seven_layer_result_json && (
            <div className="bg-white rounded-[20px] border border-[#d2d2d7] p-6">
              <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">
                7 层分析
              </h3>
              <div className="space-y-3">
                {Object.entries(result.seven_layer_result_json)
                  .filter(([key]) => !["product_categories", "best_opportunity_category", "top20_asins"].includes(key))
                  .map(([key, val]) => (
                    <div key={key} className="flex gap-3">
                      <div className="w-1.5 h-1.5 rounded-full bg-[#0071e3] mt-2 shrink-0" />
                      <div>
                        <p className="text-[13px] font-medium text-[#86868b]">{key}</p>
                        <p className="text-[15px]">{typeof val === "string" ? val : ""}</p>
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
          <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">历史记录</h3>
          <div className="space-y-2">
            {history.items.slice(0, 5).map((item) => (
              <div
                key={item.id}
                className="bg-white rounded-[16px] border border-[#d2d2d7] p-4 flex items-center justify-between hover:bg-[#f5f5f7] transition-colors cursor-pointer"
                onClick={async () => {
                  const data = await getMarketOpportunity(item.id);
                  setResult(data);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              >
                <div className="flex items-center gap-3">
                  <Globe size={18} className="text-[#86868b]" />
                  <div>
                    <p className="text-[15px] font-medium">{item.keyword}</p>
                    <p className="text-[13px] text-[#86868b]">{item.entry_level ?? "—"}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[12px] text-[#86868b]">{item.created_at?.slice(0, 10)}</span>
                  <span className="text-[12px] text-[#0071e3]">回看</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state when no results and no history */}
      {!result && (!history?.items || history.items.length === 0) && (
        <div className="bg-white rounded-[20px] border border-[#d2d2d7] p-16 text-center">
          <Search size={32} className="text-[#d2d2d7] mx-auto mb-3" />
          <p className="text-[15px] text-[#86868b]">暂无</p>
        </div>
      )}
    </div>
  );
}

function MiniCard({
  icon: Icon, label, value,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string; value: string;
}) {
  return (
    <div className="bg-[#f5f5f7] rounded-xl p-3">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon size={14} className="text-[#86868b]" />
        <span className="text-[12px] text-[#86868b] font-medium">{label}</span>
      </div>
      <p className="text-[14px] font-medium">{value}</p>
    </div>
  );
}
