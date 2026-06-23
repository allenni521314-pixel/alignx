import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, TrendingUp } from "lucide-react";
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
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">市场机会</h1>

      {/* Input */}
      <div className="flex gap-3 mb-8">
        <input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
          placeholder="输入产品关键词，如 pet odor eliminator"
          className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <button
          onClick={handleAnalyze}
          disabled={analyzing || !keyword.trim()}
          className="px-6 py-2.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2"
        >
          <Search size={18} />
          {analyzing ? "分析中..." : "分析市场"}
        </button>
      </div>

      {/* Result */}
      {result && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="text-brand-600" size={20} />
            <h2 className="text-lg font-semibold">市场分析结果</h2>
          </div>
          <p className="text-gray-600 mb-2">
            机会评分：{result.opportunity_score ?? "—"} | 进入等级：{result.entry_level ?? "—"}
          </p>
          <p className="text-gray-600">{result.market_entry_conclusion}</p>
        </div>
      )}

      {/* History */}
      {history?.items && history.items.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold mb-4">历史记录</h2>
          <div className="space-y-3">
            {history.items.map((item) => (
              <div key={item.id} className="p-3 bg-gray-50 rounded-lg">
                <span className="font-medium">{item.keyword}</span>
                <span className="ml-3 text-sm text-gray-500">
                  {item.entry_level ?? "—"} · {item.created_at}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
