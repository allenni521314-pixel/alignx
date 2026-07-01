import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Globe, ArrowRight, TrendingUp, AlertTriangle, Target } from "lucide-react";
import {
  analyzeMarketOpportunity,
  getMarketOpportunity,
  listMarketOpportunities,
  MarketOpportunity as MO,
} from "@/lib/api";

export default function MarketOpportunity() {
  const [keyword, setKeyword] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<MO | null>(null);
  const [error, setError] = useState("");

  const { data: history } = useQuery({
    queryKey: ["market-opportunity-history"],
    queryFn: () => listMarketOpportunities(),
  });

  const handleAnalyze = async () => {
    if (!keyword.trim()) return;
    setAnalyzing(true);
    setError("");
    try {
      const res = await analyzeMarketOpportunity(keyword.trim());
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "分析失败");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="max-w-[720px] mx-auto py-8">
      {/* Hero */}
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">
          产品机会
        </h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          输入产品名称搜索 Top 20 样本，判断这个关键词市场值不值得做。
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
            placeholder="输入产品关键词"
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
        {error && (
          <p className="mt-3 text-[14px] text-[#ff3b30]">{error}</p>
        )}
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
                <span className="text-[28px] font-bold text-[#0F2A24]">
                  {result.opportunity_score}
                  <span className="text-sm font-normal text-[#86868b] ml-1">分</span>
                </span>
              )}
            </div>

            {(result.best_opportunity_category || (result.seven_layer_result_json as any)?.best_opportunity_category) && (
              <div className="bg-[#0F2A24]/[0.04] rounded-xl p-4 mb-4">
                <p className="text-[13px] font-medium text-[#0F2A24] mb-1">最佳切入机会</p>
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
              <div className="bg-[#fbfaf7] rounded-xl p-4">
                <p className="text-[14px] text-[#86868b] font-medium mb-1">价格带判断</p>
                <p className="text-[15px]">{result.price_band_judgment}</p>
              </div>
            )}
          </div>

          <Top20Evidence result={result} />
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
                className="apple-card p-4 flex items-center justify-between hover:bg-[#fbfaf7] transition-colors"
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
                      const data = await getMarketOpportunity(item.id);
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
    <div className="bg-[#fbfaf7] rounded-xl p-3">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon size={14} className="text-[#86868b]" />
        <span className="text-[12px] text-[#86868b] font-medium">{label}</span>
      </div>
      <p className="text-[14px] font-medium leading-tight">{value}</p>
    </div>
  );
}

function Top20Evidence({ result }: { result: MO }) {
  const json = (result.seven_layer_result_json || {}) as Record<string, any>;
  const top20 = Array.isArray(json.top20_asins) ? json.top20_asins : [];
  const categories = result.product_categories || json.product_categories || [];
  const phrases = extractTitlePhrases(top20);
  const headPhrases = extractTitlePhrases(top20.slice(0, 5));
  const tailPhrases = extractTitlePhrases(top20.slice(15, 20));
  const reviewTerms = extractReviewTerms(top20, json);

  return (
    <div className="apple-card p-6">
      <h3 className="text-[15px] font-semibold text-[#1d1d1f] mb-4">
        关键词 & Top20 证据
      </h3>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <EvidenceBlock label="核心关键词" items={[result.keyword]} />
        <EvidenceBlock label="长尾关键词" items={phrases.slice(0, 8)} />
        <EvidenceBlock label="优先验证关键词" items={headPhrases.slice(0, 8)} />
        <EvidenceBlock label="评论词提取" items={reviewTerms.slice(0, 8)} />
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <EvidenceBlock label="Top1-5 高频词" items={headPhrases.slice(0, 8)} />
        <EvidenceBlock label="Top16-20 高频词" items={tailPhrases.slice(0, 8)} />
      </div>

      {categories.length > 0 && (
        <div className="mb-4">
          <p className="text-[13px] font-medium text-[#86868b] mb-2">市场承接方式</p>
          <div className="space-y-2">
            {categories.slice(0, 5).map((cat: any, i: number) => (
              <div key={i} className="rounded-xl bg-[#fbfaf7] p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[14px] font-semibold">{cat.category_name || "暂无"}</span>
                  <span className="text-[12px] text-[#86868b]">{cat.asin_count ?? "暂无"} 个ASIN</span>
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-[12px] text-[#86868b]">
                  <span>{cat.avg_price || "暂无"}</span>
                  <span>{cat.avg_rating != null ? `评分 ${cat.avg_rating}` : "暂无"}</span>
                  <span>{cat.avg_reviews != null ? `${cat.avg_reviews} 评` : "暂无"}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {top20.length > 0 ? (
        <div>
          <p className="text-[13px] font-medium text-[#86868b] mb-2">Top20 ASIN 样本</p>
          <div className="space-y-1 max-h-[360px] overflow-y-auto">
            {top20.map((item: any, index: number) => (
              <div key={`${item.asin || index}`} className="grid grid-cols-[36px_96px_1fr_72px_56px] gap-2 items-center rounded-lg p-2 hover:bg-[#fbfaf7]">
                <span className="text-[12px] text-[#86868b]">#{index + 1}</span>
                <span className="text-[12px] font-mono text-[#86868b] truncate">{item.asin || "暂无"}</span>
                <span className="text-[13px] truncate">{item.title || "暂无"}</span>
                <span className="text-[13px] font-semibold text-right">{item.price || "暂无"}</span>
                <span className="text-[12px] text-[#86868b] text-right">{item.rating || "暂无"}</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <p className="text-[14px] text-[#86868b]">暂无</p>
      )}
    </div>
  );
}

function EvidenceBlock({ label, items }: { label: string; items: string[] }) {
  const cleanItems = Array.from(new Set(items.map((item) => item.trim()).filter(Boolean)));
  return (
    <div className="rounded-xl bg-[#fbfaf7] p-3 min-h-[86px]">
      <p className="text-[12px] font-medium text-[#86868b] mb-2">{label}</p>
      {cleanItems.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {cleanItems.map((item) => (
            <span key={item} className="rounded-full border border-[#d2d2d7]/70 bg-white px-2 py-1 text-[12px] text-[#1d1d1f]">
              {item}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-[13px] text-[#86868b]">暂无</p>
      )}
    </div>
  );
}

function extractTitlePhrases(items: any[]) {
  const stop = new Set([
    "and", "with", "for", "the", "a", "an", "of", "to", "in", "on", "by", "or", "as", "at",
    "from", "is", "are", "be", "this", "that", "these", "those", "your", "you", "our", "it",
    "pack", "pcs", "set", "new", "best",
  ]);
  const counts = new Map<string, number>();
  for (const item of items) {
    const words = String(item?.title || "")
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, " ")
      .split(/\s+/)
      .map((word) => word.trim())
      .filter((word) => word.length > 2 && !stop.has(word));
    for (let size = 1; size <= 3; size += 1) {
      for (let i = 0; i <= words.length - size; i += 1) {
        const phrase = words.slice(i, i + size).join(" ");
        if (phrase.length < 4) continue;
        counts.set(phrase, (counts.get(phrase) || 0) + 1);
      }
    }
  }
  return Array.from(counts.entries())
    .filter(([, count]) => count > 1)
    .sort((a, b) => b[1] - a[1] || a[0].length - b[0].length)
    .map(([phrase]) => phrase)
    .slice(0, 24);
}

function extractReviewTerms(top20: any[], json: Record<string, any>) {
  const source = [
    json.review_keywords,
    json.review_terms,
    json.review_snippets,
    json.customer_reviews,
    ...top20.map((item) => item.review_keywords || item.review_terms || item.review_snippets || item.customer_reviews),
  ].flat().filter(Boolean);
  if (source.length === 0) return [];
  return extractTitlePhrases(source.map((value) => ({ title: String(value) })));
}
