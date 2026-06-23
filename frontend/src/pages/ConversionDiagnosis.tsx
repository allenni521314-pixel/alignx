import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, ArrowDownToLine } from "lucide-react";
import { diagnoseConversion, listConversionDiagnoses, ConversionDiagnosis as CD } from "@/lib/api";

export default function ConversionDiagnosis() {
  const [asin, setAsin] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<CD | null>(null);

  const { data: history } = useQuery({
    queryKey: ["conversion-diagnosis-history"],
    queryFn: () => listConversionDiagnoses(),
  });

  const handleDiagnose = async () => {
    if (!asin.trim()) return;
    setAnalyzing(true);
    try {
      const res = await diagnoseConversion(asin.trim());
      setResult(res);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">承接转化</h1>

      <div className="flex gap-3 mb-8">
        <input
          type="text"
          value={asin}
          onChange={(e) => setAsin(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleDiagnose()}
          placeholder="输入在售 ASIN 或 Amazon 商品链接"
          className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <button
          onClick={handleDiagnose}
          disabled={analyzing || !asin.trim()}
          className="px-6 py-2.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center gap-2"
        >
          <Search size={18} />
          {analyzing ? "诊断中..." : "诊断转化"}
        </button>
      </div>

      {result && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <ArrowDownToLine className="text-brand-600" size={20} />
            <h2 className="text-lg font-semibold">转化诊断结果</h2>
          </div>
          <p className="font-medium">{result.product_title}</p>
          <p className="text-gray-600 mt-2">{result.overall_conclusion}</p>
          {result.biggest_breakpoint && (
            <p className="mt-2 text-orange-600">最大断点：{result.biggest_breakpoint}</p>
          )}
          {result.priority_action && (
            <p className="mt-2 text-brand-600">优先动作：{result.priority_action}</p>
          )}
          {result.impacted_ad_metrics && (
            <div className="mt-3 flex gap-2 flex-wrap">
              {result.impacted_ad_metrics.map((m) => (
                <span key={m} className="px-2 py-1 bg-amber-50 text-amber-700 rounded text-xs">{m}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {history?.items && history.items.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold mb-4">历史记录</h2>
          {history.items.map((item) => (
            <div key={item.id} className="p-3 bg-gray-50 rounded-lg mb-2">
              <span className="font-medium">{item.asin}</span>
              <span className="ml-3 text-sm text-gray-500">{item.product_title?.slice(0, 60)}...</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
