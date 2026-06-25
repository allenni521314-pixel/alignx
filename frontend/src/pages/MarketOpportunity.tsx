import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Globe, ArrowRight, TrendingUp, Shield, AlertTriangle, Target, CheckSquare, Square, BarChart3 } from "lucide-react";
import { analyzeMarketOpportunity, listMarketOpportunities, MarketOpportunity as MO, API_BASE } from "@/lib/api";

export default function MarketOpportunity() {
  const [keyword, setKeyword] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<MO | null>(null);
  const [selectedAsins, setSelectedAsins] = useState<string[]>([]);
  const [comparing, setComparing] = useState(false);
  const [comparison, setComparison] = useState<any[] | null>(null);

  const { data: history } = useQuery({
    queryKey: ["market-opportunity-history"],
    queryFn: () => listMarketOpportunities(),
  });

  const toggleAsin = (asin: string) => {
    setSelectedAsins(prev => 
      prev.includes(asin) ? prev.filter(a => a !== asin) : 
      prev.length >= 5 ? prev : [...prev, asin]
    );
  };

  const handleCompare = async () => {
    if (selectedAsins.length < 2) return;
    setComparing(true);
    const results = await Promise.all(
      selectedAsins.map(async (asin) => {
        const r = await fetch(`${API_BASE}/competitor-analysis/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ asin }),
        });
        return r.json();
      })
    );
    setComparison(results);
    setComparing(false);
  };
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
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide">
                  产品分类统计
                </h3>
                {selectedAsins.length >= 2 && (
                  <button onClick={handleCompare} disabled={comparing} className="apple-btn-primary flex items-center gap-1 text-[13px] px-4 py-2">
                    <BarChart3 size={14} />
                    {comparing ? "分析中..." : `对比选中 (${selectedAsins.length})`}
                  </button>
                )}
              </div>
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
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {cat.key_players.slice(0, 5).map((asin: string) => {
                          const checked = selectedAsins.includes(asin);
                          return (
                            <span
                              key={asin}
                              onClick={(e) => { e.stopPropagation(); toggleAsin(asin); }}
                              className={`text-[12px] px-2 py-1 rounded-full cursor-pointer transition-colors font-mono ${
                                checked ? "bg-[#0071e3] text-white" : "bg-white text-[#0071e3] border border-[#0071e3]/20 hover:bg-[#0071e3]/[0.06]"
                              }`}
                            >
                              {checked ? "✓ " : "+ "}{asin}
                            </span>
                          );
                        })}
                      </div>
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

          {/* Top20 ASIN comparison */}
          {((result.seven_layer_result_json as any)?.top20_asins?.length > 0) && (
            <div className="apple-card p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide">
                  Top 20 竞品列表（勾选 2-5 个对比）
                </h3>
                <button
                  onClick={handleCompare}
                  disabled={selectedAsins.length < 2 || comparing}
                  className="apple-btn-primary flex items-center gap-1 text-[13px] px-4 py-2"
                >
                  <BarChart3 size={14} />
                  {comparing ? "分析中..." : `对比选中 (${selectedAsins.length})`}
                </button>
              </div>

              {/* Price band summary */}
              {(() => {
                const asins = (result.seven_layer_result_json as any).top20_asins || [];
                const priced = asins.filter((a: any) => a.price && !isNaN(parseFloat(String(a.price).replace('$',''))));
                const priceVals = priced.map((a: any) => parseFloat(String(a.price).replace('$','')));
                if (priceVals.length === 0) return null;
                const min = Math.min(...priceVals);
                const max = Math.max(...priceVals);
                const lowCut = min + (max - min) / 3;
                const highCut = min + 2 * (max - min) / 3;
                const getBand = (p: number) => p < lowCut ? "low" : p >= highCut ? "high" : "mid";
                const bands = { low: priced.filter((a: any) => getBand(parseFloat(String(a.price).replace('$',''))) === "low"),
                                mid: priced.filter((a: any) => getBand(parseFloat(String(a.price).replace('$',''))) === "mid"),
                                high: priced.filter((a: any) => getBand(parseFloat(String(a.price).replace('$',''))) === "high") };
                return (
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <div className="bg-[#34c759]/[0.04] rounded-xl p-3 text-center">
                      <p className="text-[11px] text-[#86868b]">低价带</p>
                      <p className="text-[15px] font-bold">≤${lowCut.toFixed(0)}</p>
                      <p className="text-[12px] text-[#34c759]">{bands.low.length} 个</p>
                    </div>
                    <div className="bg-[#ff9500]/[0.04] rounded-xl p-3 text-center">
                      <p className="text-[11px] text-[#86868b]">中价带</p>
                      <p className="text-[15px] font-bold">${lowCut.toFixed(0)}-${highCut.toFixed(0)}</p>
                      <p className="text-[12px] text-[#ff9500]">{bands.mid.length} 个</p>
                    </div>
                    <div className="bg-[#ff3b30]/[0.04] rounded-xl p-3 text-center">
                      <p className="text-[11px] text-[#86868b]">高价带</p>
                      <p className="text-[15px] font-bold">≥${highCut.toFixed(0)}</p>
                      <p className="text-[12px] text-[#ff3b30]">{bands.high.length} 个</p>
                    </div>
                  </div>
                );
              })()}

              <div className="space-y-1 max-h-[400px] overflow-y-auto">
                {((result.seven_layer_result_json as any).top20_asins).map((a: any) => {
                  const checked = selectedAsins.includes(a.asin);
                  const priceColor = !a.price ? "text-[#86868b]" : "text-[#1d1d1f]";
                  return (
                    <div
                      key={a.asin}
                      onClick={() => toggleAsin(a.asin)}
                      className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors ${
                        checked ? "bg-[#0071e3]/[0.06] border border-[#0071e3]/20" : "hover:bg-[#f5f5f7]"
                      }`}
                    >
                      {checked ? <CheckSquare size={16} className="text-[#0071e3] shrink-0" /> : <Square size={16} className="text-[#d2d2d7] shrink-0" />}
                      <span className="text-[12px] font-mono text-[#86868b] w-[100px] shrink-0">{a.asin}</span>
                      <span className="text-[13px] flex-1 truncate">{a.title}</span>
                      <span className={`text-[14px] font-bold shrink-0 w-[70px] text-right ${priceColor}`}>{a.price || "$—"}</span>
                      <span className="text-[12px] text-[#ff9500] shrink-0 w-[45px]">{a.rating ? `⭐${a.rating}` : ""}</span>
                      <span className="text-[12px] text-[#86868b] shrink-0 w-[55px] text-right">{a.review_count ? `${a.review_count}评` : ""}</span>
                    </div>
                  );
                })}
              </div>

              {/* Comparison Table */}
              {comparison && comparison.length > 0 && (
                <div className="mt-6 border-t border-[#d2d2d7]/20 pt-4">
                  <h4 className="text-[13px] font-semibold mb-3">对比结果</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-[13px]">
                      <thead>
                        <tr className="border-b border-[#d2d2d7]/20 text-left text-[#86868b]">
                          <th className="py-2 pr-3">指标</th>
                          {comparison.map((c: any, i: number) => (
                            <th key={i} className="py-2 pr-3 font-mono text-[12px]">{c.asin?.slice(0, 10)}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {["price", "rating", "review_count", "overall_judgment", "main_strengths", "attack_points"].map(field => (
                          <tr key={field} className="border-b border-[#d2d2d7]/10">
                            <td className="py-2 pr-3 text-[#86868b]">
                              {field === "price" ? "价格" : field === "rating" ? "评分" : field === "review_count" ? "评论" : field === "overall_judgment" ? "综合判断" : field === "main_strengths" ? "优势" : "可攻击点"}
                            </td>
                            {comparison.map((c: any, i: number) => (
                              <td key={i} className="py-2 pr-3">
                                {Array.isArray(c[field])
                                  ? c[field]?.slice(0, 2).map((s: string, j: number) => <p key={j} className="text-[12px]">· {s}</p>)
                                  : <span className="text-[12px]">{c[field] || "—"}</span>}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
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
                      const res = await fetch(`${API_BASE}/market-opportunity/${item.id}`);
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
