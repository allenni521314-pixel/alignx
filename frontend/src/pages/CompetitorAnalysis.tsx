import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, BarChart3 } from "lucide-react";
import { analyzeCompetitor, listCompetitorAnalyses, CompetitorAnalysis as CA } from "@/lib/api";

export default function CompetitorAnalysis() {
  const [asin, setAsin] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<CA | null>(null);

  const { data: history } = useQuery({
    queryKey: ["competitor-analysis-history"],
    queryFn: () => listCompetitorAnalyses(),
  });

  const handleAnalyze = async () => {
    if (!asin.trim()) return;
    setAnalyzing(true);
    try {
      const res = await analyzeCompetitor(asin.trim());
      setResult(res);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">竞品分析</h1>

      <div className="flex gap-3 mb-8">
        <input
          type="text"
          value={asin}
          onChange={(e) => setAsin(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
          placeholder="输入竞品 ASIN 或 Amazon 商品链接"
          className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <button
          onClick={handleAnalyze}
          disabled={analyzing || !asin.trim()}
          className="px-6 py-2.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2"
        >
          <Search size={18} />
          {analyzing ? "分析中..." : "分析竞品"}
        </button>
      </div>

      {result && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="text-brand-600" size={20} />
            <h2 className="text-lg font-semibold">竞品分析结果</h2>
          </div>
          <p className="font-medium mb-2">{result.product_title}</p>
          <p className="text-gray-600 mb-2">品牌：{result.brand ?? "—"} | 价格：{result.price ?? "—"} | 评分：{result.rating ?? "—"}⭐ | 评论：{result.review_count ?? "—"}</p>
          <p className="text-gray-700 mt-4">{result.overall_judgment}</p>
        </div>
      )}

      {history?.items && history.items.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold mb-4">历史记录</h2>
          <div className="space-y-3">
            {history.items.map((item) => (
              <div key={item.id} className="p-3 bg-gray-50 rounded-lg">
                <span className="font-medium">{item.asin}</span>
                <span className="ml-2 text-sm text-gray-500">{item.product_title?.slice(0, 60)}...</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
