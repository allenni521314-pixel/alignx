import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, ArrowRight, Star, MessageSquare, DollarSign, Swords, Target, Shield } from "lucide-react";
import { analyzeCompetitor, listCompetitorAnalyses, CompetitorAnalysis as CA } from "@/lib/api";

const DIM_LABELS: Record<string, { icon: React.ComponentType<{ size?: number }>; label: string }> = {
  price_band_position: { icon: DollarSign, label: "价格带位置" },
  review_count_barrier: { icon: MessageSquare, label: "评论壁垒" },
  rating_trust: { icon: Star, label: "评分信任度" },
  main_image_click_power: { icon: Target, label: "主图点击力" },
  differentiation_strength: { icon: Swords, label: "差异化强度" },
  conversion_risk_and_attack_points: { icon: Shield, label: "可攻击点" },
};

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
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">竞品分析</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          输入竞品 ASIN，系统拆解 12 维优劣势，找到可攻击点
        </p>
      </div>

      <div className="apple-card p-6 mb-8">
        <div className="flex gap-3">
          <input
            type="text"
            value={asin}
            onChange={(e) => setAsin(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
            placeholder="输入竞品 ASIN 或 Amazon 链接"
            className="apple-input flex-1"
          />
          <button
            onClick={handleAnalyze}
            disabled={analyzing || !asin.trim()}
            className="apple-btn-primary flex items-center gap-2 px-6"
          >
            {analyzing ? (
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <>
                分析竞品
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </div>
      </div>

      {result && (
        <div className="space-y-4 mb-10">
          {/* Product header */}
          <div className="apple-card p-6">
            <h2 className="text-[20px] font-semibold mb-3">{result.product_title}</h2>
            <div className="flex items-center gap-4 text-[14px] text-[#86868b] mb-4">
              {result.brand && <span>{result.brand}</span>}
              {result.price && <span>{result.price}</span>}
              {result.rating != null && (
                <span className="flex items-center gap-1">
                  <Star size={14} className="text-[#ff9500] fill-[#ff9500]" />
                  {result.rating}
                </span>
              )}
              {result.review_count != null && (
                <span>{result.review_count.toLocaleString()} 条评论</span>
              )}
            </div>

            {/* Strengths / Weaknesses */}
            <div className="grid grid-cols-2 gap-3 mb-4">
              <MiniList
                title="优势"
                color="text-[#34c759]"
                items={result.main_strengths ?? []}
              />
              <MiniList
                title="弱点"
                color="text-[#ff3b30]"
                items={result.main_weaknesses ?? []}
              />
            </div>

            {/* Attack points */}
            {result.attack_points && result.attack_points.length > 0 && (
              <div className="bg-[#f5f5f7] rounded-xl p-4">
                <p className="text-[13px] font-semibold text-[#0071e3] mb-2 flex items-center gap-1.5">
                  <Swords size={14} />
                  可攻击点
                </p>
                <ul className="space-y-1.5">
                  {result.attack_points.map((p, i) => (
                    <li key={i} className="text-[14px] flex items-start gap-2">
                      <span className="text-[#0071e3] mt-1.5">•</span>
                      {p}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* 12-dimension */}
          {result.twelve_dimension_result_json && (
            <div className="apple-card p-6">
              <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-4">
                12 维分析
              </h3>
              <div className="space-y-3">
                {Object.entries(result.twelve_dimension_result_json).map(([key, val]) => {
                  const meta = DIM_LABELS[key];
                  return (
                    <div key={key} className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg bg-[#f5f5f7] flex items-center justify-center shrink-0 mt-0.5">
                        {meta ? (
                          <meta.icon size={16} className="text-[#86868b]" />
                        ) : (
                          <BarChart3 size={16} className="text-[#86868b]" />
                        )}
                      </div>
                      <div>
                        <p className="text-[13px] font-medium text-[#86868b]">
                          {meta?.label ?? key}
                        </p>
                        <p className="text-[15px]">
                          {typeof val === "string" ? val : JSON.stringify(val)}
                        </p>
                      </div>
                    </div>
                  );
                })}
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
                <div>
                  <p className="text-[15px] font-medium">{item.asin}</p>
                  <p className="text-[13px] text-[#86868b] truncate max-w-[300px]">
                    {item.product_title}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[12px] text-[#86868b]">{item.created_at?.slice(0, 10)}</span>
                  <button
                    onClick={async () => {
                      const res = await fetch(`/api/v1/competitor-analysis/${item.id}`);
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

function MiniList({
  title,
  color,
  items,
}: {
  title: string;
  color: string;
  items: string[];
}) {
  return (
    <div className="bg-[#f5f5f7] rounded-xl p-4">
      <p className={`text-[13px] font-semibold mb-2 ${color}`}>{title}</p>
      {items.length > 0 ? (
        <ul className="space-y-1">
          {items.map((item, i) => (
            <li key={i} className="text-[13px] leading-snug">{item}</li>
          ))}
        </ul>
      ) : (
        <p className="text-[13px] text-[#86868b]">—</p>
      )}
    </div>
  );
}
