import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  BarChart3, ArrowRight, Star, MessageSquare, DollarSign,
  Swords, Target, Shield, Zap, ChevronRight, History,
} from "lucide-react";
import {
  analyzeCompetitor,
  createValidationTask,
  getCompetitorAnalysis,
  listCompetitorAnalyses,
  CompetitorAnalysis as CA,
} from "@/lib/api";

const DIM_LABELS: Record<string, { icon: React.ComponentType<{ size?: number; className?: string }>; label: string }> = {
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
  const [error, setError] = useState("");
  const [creatingHypothesis, setCreatingHypothesis] = useState(false);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data: history } = useQuery({
    queryKey: ["competitor-analysis-history"],
    queryFn: () => listCompetitorAnalyses(),
  });

  const handleAnalyze = async () => {
    if (!asin.trim()) return;
    setAnalyzing(true);
    setError("");
    try {
      const res = await analyzeCompetitor(asin.trim());
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "请求失败");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleCreateHypothesis = async () => {
    if (!result?.attack_points?.length) return;
    setCreatingHypothesis(true);
    try {
      const hypothesis = `针对竞品 ${result.asin} 的弱点：${result.attack_points.slice(0, 2).join("；")}`;
      await createValidationTask({
        asin: result.asin,
        proposition_code: "P06-001",
        proposition_name: `竞品弱点攻击：${result.attack_points[0]}`,
        hypothesis_text: hypothesis,
        source_module: "competitor_analysis",
        source_record_id: result.id,
      });
      queryClient.invalidateQueries({ queryKey: ["validation-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["today-decisions"] });
      navigate("/today-decisions");
    } finally {
      setCreatingHypothesis(false);
    }
  };

  return (
    <div className="max-w-[720px] mx-auto py-8">
      {/* Header */}
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">竞品分析</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          输入竞品 ASIN，系统抓取 Listing 并做 12 维分析，找到你可以攻击的弱点
        </p>
      </div>

      {/* Input */}
      <div className="apple-card p-6 mb-8">
        <div className="flex gap-3">
          <input
            type="text"
            value={asin}
            onChange={(e) => setAsin(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
            placeholder="输入竞品 ASIN，如 B0CSYZ367S"
            className="apple-input flex-1"
          />
          <button
            onClick={handleAnalyze}
            disabled={analyzing || !asin.trim()}
            className="apple-btn-primary flex items-center gap-2 px-6"
          >
            {analyzing ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                分析中
              </>
            ) : (
              <>
                分析竞品 <ArrowRight size={16} />
              </>
            )}
          </button>
        </div>
        {error && (
          <p className="mt-3 text-[13px] text-[#ff3b30]">{error}</p>
        )}
      </div>

      {/* Result */}
      {result && (
        <div className="space-y-4 mb-10">
          {/* Product header card */}
          <div className="apple-card p-6">
            <h2 className="text-[18px] font-semibold mb-3 leading-snug">{result.product_title}</h2>
            <div className="flex items-center gap-4 text-[14px] text-[#86868b] mb-5">
              {result.brand && <span className="font-medium">{result.brand}</span>}
              {result.price && <span>{result.price}</span>}
              {result.rating != null && (
                <span className="flex items-center gap-1">
                  <Star size={14} className="text-[#ff9500] fill-[#ff9500]" />
                  {result.rating}
                </span>
              )}
              {result.review_count != null && (
                <span>{result.review_count.toLocaleString()} 评论</span>
              )}
            </div>

            {result.overall_judgment && (
              <div className="bg-[#fbfaf7] rounded-xl p-4 mb-4">
                <p className="text-[13px] font-semibold text-[#86868b] mb-1">综合判断</p>
                <p className="text-[15px] leading-relaxed">{result.overall_judgment}</p>
              </div>
            )}

            {/* Strengths + Weaknesses */}
            <div className="grid grid-cols-2 gap-3 mb-4">
              <MiniList title="优势" color="text-[#34c759]" icon={Star} items={result.main_strengths ?? []} />
              <MiniList title="弱点" color="text-[#ff3b30]" icon={Swords} items={result.main_weaknesses ?? []} />
            </div>

            {/* Attack points + CTA */}
            {result.attack_points && result.attack_points.length > 0 && (
              <div className="bg-[#0F2A24]/[0.04] rounded-xl p-5 border border-[#0F2A24]/10">
                <p className="text-[13px] font-semibold text-[#0F2A24] mb-3 flex items-center gap-1.5">
                  <Target size={14} />
                  你可以攻击的弱点
                </p>
                <ul className="space-y-1.5 mb-4">
                  {result.attack_points.map((p, i) => (
                    <li key={i} className="text-[14px] flex items-start gap-2">
                      <span className="text-[#0F2A24] mt-1 shrink-0">•</span>
                      <span className="leading-relaxed">{p}</span>
                    </li>
                  ))}
                </ul>
                <button
                  onClick={handleCreateHypothesis}
                  disabled={creatingHypothesis}
                  className="apple-btn-primary flex items-center gap-2"
                >
                  {creatingHypothesis ? (
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <Zap size={14} />
                  )}
                  {creatingHypothesis ? "生成中..." : "生成验证假设 → 去执行"}
                </button>
                <p className="text-[11px] text-[#86868b] mt-2">
                  基于以上弱点自动创建一个待验证假设，跳转到今日决策
                </p>
              </div>
            )}
          </div>

          {/* 12-dimension analysis */}
          {result.twelve_dimension_result_json && (
            <div className="apple-card p-6">
              <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-5">
                12 维详细分析
              </h3>
              <div className="space-y-4">
                {Object.entries(result.twelve_dimension_result_json).map(([key, val]) => {
                  const meta = DIM_LABELS[key];
                  const text = Array.isArray(val)
                    ? val.join("；")
                    : typeof val === "string"
                    ? val
                    : JSON.stringify(val);
                  return (
                    <div key={key} className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg bg-[#fbfaf7] flex items-center justify-center shrink-0 mt-0.5">
                        {meta ? (
                          <meta.icon size={16} className="text-[#86868b]" />
                        ) : (
                          <BarChart3 size={16} className="text-[#86868b]" />
                        )}
                      </div>
                      <div className="min-w-0">
                        <p className="text-[13px] font-medium text-[#86868b] mb-0.5">
                          {meta?.label ?? key}
                        </p>
                        <p className="text-[14px] leading-relaxed break-words">{text || "—"}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!result && (!history?.items || history.items.length === 0) && (
        <div className="apple-card p-16 text-center">
          <Target size={32} className="text-[#d2d2d7] mx-auto mb-3" />
          <h3 className="text-[17px] font-semibold mb-1">分析你的第一个竞品</h3>
          <p className="text-[14px] text-[#86868b] max-w-[320px] mx-auto leading-relaxed">
            输入竞品 ASIN，系统会抓取 Listing 数据并做 12 维分析，找出你可以攻击的弱点
          </p>
        </div>
      )}

      {/* History */}
      {history?.items && history.items.length > 0 && (
        <div>
          <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3 flex items-center gap-2">
            <History size={14} />
            历史分析
          </h3>
          <div className="space-y-2">
            {history.items.map((item) => (
              <div
                key={item.id}
                className="apple-card p-4 flex items-center justify-between hover:bg-[#fbfaf7] transition-colors cursor-pointer"
                onClick={async () => {
                  const data = await getCompetitorAnalysis(item.id);
                  setResult(data);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-[14px] font-semibold">{item.asin}</span>
                    {item.overall_judgment && (
                      <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-[#fbfaf7] text-[#86868b] truncate max-w-[180px]">
                        {item.overall_judgment.slice(0, 30)}...
                      </span>
                    )}
                  </div>
                  <p className="text-[12px] text-[#86868b] truncate">{item.product_title}</p>
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-3">
                  <span className="text-[11px] text-[#86868b]">{item.created_at?.slice(0, 10)}</span>
                  <ChevronRight size={14} className="text-[#d2d2d7]" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── MiniList sub-component ── */

function MiniList({
  title,
  color,
  icon: Icon,
  items,
}: {
  title: string;
  color: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  items: string[];
}) {
  return (
    <div className="bg-[#fbfaf7] rounded-xl p-4">
      <p className={`text-[13px] font-semibold mb-2 flex items-center gap-1.5 ${color}`}>
        <Icon size={13} />
        {title}
      </p>
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
