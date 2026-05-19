import { useState } from "react";
import { AppSidebar } from "@/components/AppSidebar";
import { PageHeader } from "@/components/PageHeader";
import { NextStepActions } from "@/components/NextStepActions";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getAuthHeaders } from "@/lib/auth-headers";
import { saveActionSnapshot } from "@/lib/workflow-api";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { toast } from "sonner";
import axios from "axios";
import {
  ArrowRightLeft,
  BarChart3,
  CheckCircle2,
  Loader2,
  Trophy,
} from "lucide-react";

interface VariantForm {
  label: string;
  asin: string;
  title: string;
  bullets: string;
  description: string;
  conversion: string;
}

interface ABResult {
  winner?: string;
  win_margin?: number;
  confidence_score?: number;
  dimension_comparison?: Record<string, { A?: number; B?: number; delta?: number; winner?: string }>;
  key_strengths?: { variant_a?: string[]; variant_b?: string[] };
  key_weaknesses?: { variant_a?: string[]; variant_b?: string[] };
  predicted_conversion_impact?: Record<string, number>;
  recommendations?: string[];
  text_report?: string;
}

const demoVariantA: VariantForm = {
  label: "A 原版本",
  asin: "DEMOAMZ001",
  title: "Large Enclosed Cat Litter Box with Filter for Indoor Cats",
  bullets:
    "Extra large enclosed cat litter box for indoor cats\nCarbon filter helps reduce everyday litter smell\nEasy pull-out tray for quick cleaning\nHigh wall design helps reduce tracking\nModern white design fits home corners",
  description: "Original listing focuses on enclosed size and basic filter function.",
  conversion: "7.4",
};

const demoVariantB: VariantForm = {
  label: "B 除味强化版",
  asin: "DEMOAMZ001",
  title: "Odor Control Cat Litter Box with Activated Carbon Filter, Extra Large Enclosed Design for Indoor Cats",
  bullets:
    "Targets ammonia odor with replaceable activated carbon filter\nExtra large enclosed design gives adult cats room to turn\nPull-out tray and scoop slot simplify daily cleaning\nHigh splash guard and sealed entrance reduce litter tracking\nBuilt for apartments, bedrooms, and multi-cat odor control",
  description: "New version strengthens odor control, ammonia risk explanation, and apartment use scenarios.",
  conversion: "10.2",
};

const demoABResult: ABResult = {
  winner: "B",
  win_margin: 12.5,
  confidence_score: 76,
  dimension_comparison: {
    "点击相关性": { A: 72, B: 86, delta: 14, winner: "B" },
    "需求承接": { A: 68, B: 88, delta: 20, winner: "B" },
    "信任解释": { A: 70, B: 81, delta: 11, winner: "B" },
    "转化链条": { A: 73, B: 84, delta: 11, winner: "B" },
  },
  recommendations: [
    "保留B版本标题前半段的 Odor Control 和 Activated Carbon Filter。",
    "广告测试优先使用 cat litter box odor eliminator、ammonia odor remover、cat litter deodorizer。",
    "若CTR提升但CVR未提升，下一轮补充滤芯更换周期和清洁成本说明。",
  ],
  text_report:
    "DEMOAMZ001 当前A/B结论：B版本对评论高频需求「氨气除味」「公寓使用」「清洁便利」承接更完整，适合进入小预算广告验证。验证重点看CTR、CVR和ACOS是否同步改善。",
};

function toVariantPayload(v: VariantForm) {
  return {
    asin: v.asin.trim(),
    title: v.title.trim(),
    bullets: v.bullets.trim(),
    description: v.description.trim(),
  };
}

function safeNum(value: string) {
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

const DIMENSION_LABELS: Record<string, string> = {
  state_gap_coverage: "需求承接",
  mechanism_clarity: "机制清晰",
  side_effect_transparency: "风险解释",
  causal_honesty: "表达可信",
};

function scoreVariant(v: VariantForm) {
  const text = `${v.title}\n${v.bullets}\n${v.description}`.toLowerCase();
  const count = (words: string[]) => words.reduce((sum, word) => sum + (text.includes(word) ? 1 : 0), 0);
  const demand = count(["odor", "smell", "ammonia", "filter", "clean", "tracking", "apartment", "multi-cat", "room", "easy"]);
  const mechanism = count(["activated carbon", "replaceable", "sealed", "pull-out", "scoop", "guard", "because", "with", "reduce", "targets"]);
  const risk = count(["ammonia", "risk", "tracking", "sealed", "splash", "odor", "replaceable", "daily", "cleaning"]);
  const trust = count(["real", "tested", "replaceable", "carbon", "sealed", "adult", "extra large", "daily"]);
  const cvr = safeNum(v.conversion);
  const cvrBoost = cvr ? Math.min(12, Math.max(0, cvr - 5) * 2) : 0;
  return {
    state_gap_coverage: Math.min(95, 55 + demand * 4 + cvrBoost),
    mechanism_clarity: Math.min(95, 55 + mechanism * 4 + cvrBoost * 0.6),
    side_effect_transparency: Math.min(95, 52 + risk * 4 + cvrBoost * 0.4),
    causal_honesty: Math.min(95, 58 + trust * 3 + cvrBoost * 0.5),
  };
}

function buildLocalABResult(a: VariantForm, b: VariantForm, reason = "后端AI对比暂不可用，已使用本地规则兜底。"): ABResult {
  const scoresA = scoreVariant(a);
  const scoresB = scoreVariant(b);
  const dimension_comparison = Object.fromEntries(
    Object.keys(DIMENSION_LABELS).map((key) => {
      const A = Math.round(scoresA[key as keyof typeof scoresA]);
      const B = Math.round(scoresB[key as keyof typeof scoresB]);
      return [
        DIMENSION_LABELS[key],
        { A, B, delta: B - A, winner: Math.abs(B - A) < 3 ? "tie" : B > A ? "B" : "A" },
      ];
    })
  );
  const avgA = Object.values(scoresA).reduce((sum, v) => sum + v, 0) / 4;
  const avgB = Object.values(scoresB).reduce((sum, v) => sum + v, 0) / 4;
  const winner = Math.abs(avgB - avgA) < 3 ? "tie" : avgB > avgA ? "B" : "A";
  const cvrA = safeNum(a.conversion);
  const cvrB = safeNum(b.conversion);
  const historicalDelta = cvrA && cvrB ? cvrB - cvrA : avgB - avgA;
  const winnerText = winner === "tie" ? "两版接近" : `${winner}版本`;
  return {
    winner,
    win_margin: Math.abs(avgB - avgA),
    confidence_score: cvrA && cvrB ? 78 : 66,
    dimension_comparison,
    predicted_conversion_impact: {
      variant_a_impact_pct: Number(((avgA - 50) / 8).toFixed(1)),
      variant_b_impact_pct: Number(((avgB - 50) / 8).toFixed(1)),
      delta_pct: Number(historicalDelta.toFixed(1)),
    },
    recommendations: [
      `当前建议选择：${winnerText}，但必须进入小预算广告验证。`,
      "验证优先看CTR、CVR、ACOS是否同向改善，避免只看点击不看转化。",
      "若CTR提升但CVR不升，说明主图/标题吸引成立，但详情页承接或价格信任不足。",
    ],
    text_report: `${reason}\n\nA均分：${avgA.toFixed(1)}，B均分：${avgB.toFixed(1)}。${winner === "tie" ? "两版差距较小，建议真实流量验证。" : `${winner}版本在需求承接、因果解释或历史CVR上更强。`} 下一步进入执行记录，建立广告验证任务。`,
  };
}

export default function ABTestComparison() {
  const { loading: authLoading } = useRequireAuth();
  const [variantA, setVariantA] = useState<VariantForm>(demoVariantA);
  const [variantB, setVariantB] = useState<VariantForm>(demoVariantB);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ABResult | null>(demoABResult);

  if (authLoading) return null;

  const updateA = (key: keyof VariantForm, value: string) => {
    setVariantA((prev) => ({ ...prev, [key]: value }));
  };

  const updateB = (key: keyof VariantForm, value: string) => {
    setVariantB((prev) => ({ ...prev, [key]: value }));
  };

  const runComparison = async () => {
    if (!variantA.title.trim() && !variantA.bullets.trim()) {
      toast.error("请填写A版本标题或五点");
      return;
    }
    if (!variantB.title.trim() && !variantB.bullets.trim()) {
      toast.error("请填写B版本标题或五点");
      return;
    }

    setLoading(true);
    setResult(null);
    try {
      const res = await axios.post(
        "/api/v1/causal/ab-comparison",
        {
          variant_a: toVariantPayload(variantA),
          variant_b: toVariantPayload(variantB),
          variant_a_label: variantA.label || "A",
          variant_b_label: variantB.label || "B",
          historical_conversion_a: safeNum(variantA.conversion),
          historical_conversion_b: safeNum(variantB.conversion),
        },
        { headers: getAuthHeaders(), timeout: 180000 }
      );
      setResult(res.data);
      saveActionSnapshot({
        module_key: "ab_test",
        module_name: "A/B测试",
        action_key: "compare_ab_versions",
        action_name: "A/B测试结果对比",
        asin: variantA.asin || variantB.asin,
        title: `${variantA.label} vs ${variantB.label}`,
        input_snapshot: { variant_a: variantA, variant_b: variantB },
        output_snapshot: res.data,
        data_source: "ai_ab_comparison",
        confidence: String(res.data?.confidence_score || ""),
        ai_called: true,
        source_record_table: "action_snapshots",
      }).catch(() => {});
      toast.success("A/B测试对比完成");
    } catch (e) {
      const reason = axios.isAxiosError(e)
        ? e.code === "ECONNABORTED"
          ? "后端A/B对比超过180秒，已使用本地规则兜底。"
          : e.response?.data?.detail || "后端A/B对比不可用，已使用本地规则兜底。"
        : "后端A/B对比不可用，已使用本地规则兜底。";
      const fallback = buildLocalABResult(variantA, variantB, reason);
      setResult(fallback);
      saveActionSnapshot({
        module_key: "ab_test",
        module_name: "A/B测试",
        action_key: "compare_ab_versions",
        action_name: "A/B测试结果对比",
        asin: variantA.asin || variantB.asin,
        title: `${variantA.label} vs ${variantB.label}`,
        input_snapshot: { variant_a: variantA, variant_b: variantB },
        output_snapshot: fallback,
        data_source: "local_fallback",
        confidence: String(fallback.confidence_score || ""),
        ai_called: false,
        source_record_table: "action_snapshots",
      }).catch(() => {});
      toast.warning("已生成本地兜底A/B对比结果");
    } finally {
      setLoading(false);
    }
  };

  const winnerLabel =
    result?.winner === "A"
      ? variantA.label
      : result?.winner === "B"
        ? variantB.label
        : "两版接近";

  return (
    <div className="flex h-screen bg-white text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="p-4 sm:p-6 max-w-7xl mx-auto pt-14 md:pt-6">
          <div className="mb-6 sm:mb-8">
            <h1 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
              <ArrowRightLeft className="w-5 h-5 sm:w-6 sm:h-6 text-amber-600" />
              A/B 测试与结果对比
            </h1>
            <p className="text-gray-500 mt-1 text-sm">
              对比两个Listing版本，判断哪个更适合进入广告验证
            </p>
          </div>

          <PageHeader
            objective="制定A/B测试并对比两个Listing版本的预期转化表现"
            inputSource="A/B两个Listing版本、历史CVR、标题、五点、描述"
            process="比较因果转化链条、状态差距覆盖、机制清晰度和副作用透明度"
            outputTarget="胜出版本、维度差距、预测转化影响、测试建议"
            action="将胜出版本进入广告执行记录"
            feedback="真实广告结果回流到效果验证和复盘优化"
            tone="amber"
          />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
            {[
              { title: "A版本", form: variantA, update: updateA },
              { title: "B版本", form: variantB, update: updateB },
            ].map((item) => (
              <Card key={item.title} className="bg-white border-gray-200 p-4 sm:p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-gray-900">{item.title}</h2>
                  <Input
                    value={item.form.label}
                    onChange={(e) => item.update("label", e.target.value)}
                    className="w-36 h-8 bg-gray-50 border-gray-200 text-xs"
                  />
                </div>
                <Input
                  value={item.form.asin}
                  onChange={(e) => item.update("asin", e.target.value)}
                  placeholder="ASIN（可选）"
                  className="bg-gray-50 border-gray-200"
                />
                <Input
                  value={item.form.title}
                  onChange={(e) => item.update("title", e.target.value)}
                  placeholder="标题"
                  className="bg-gray-50 border-gray-200"
                />
                <Textarea
                  value={item.form.bullets}
                  onChange={(e) => item.update("bullets", e.target.value)}
                  placeholder="五点描述，每条一行"
                  className="bg-gray-50 border-gray-200 min-h-[120px]"
                />
                <Textarea
                  value={item.form.description}
                  onChange={(e) => item.update("description", e.target.value)}
                  placeholder="描述 / A+摘要"
                  className="bg-gray-50 border-gray-200 min-h-[80px]"
                />
                <Input
                  value={item.form.conversion}
                  onChange={(e) => item.update("conversion", e.target.value)}
                  placeholder="历史CVR，可选，例如 8.5"
                  className="bg-gray-50 border-gray-200"
                />
              </Card>
            ))}
          </div>

          <Button
            onClick={runComparison}
            disabled={loading}
            className="bg-amber-600 hover:bg-amber-500 text-white mb-6"
          >
            {loading ? (
              <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> 对比中...</>
            ) : (
              <><BarChart3 className="w-4 h-4 mr-1.5" /> 生成A/B结果对比</>
            )}
          </Button>

          {result && (
            <div className="space-y-4">
              <Card className="bg-white border-gray-200 p-5">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center">
                      <Trophy className="w-5 h-5 text-amber-600" />
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">胜出结论</p>
                      <h2 className="text-lg font-bold text-gray-900">{winnerLabel}</h2>
                    </div>
                  </div>
                  <div className="flex gap-2 text-sm">
                    <span className="px-3 py-1.5 rounded-lg bg-gray-50 border border-gray-200">
                      优势 {Math.round(result.win_margin || 0)}分
                    </span>
                    <span className="px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700">
                      置信度 {Math.round(result.confidence_score || 0)}%
                    </span>
                  </div>
                </div>
              </Card>

              {result.dimension_comparison && (
                <Card className="bg-white border-gray-200 p-5">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">维度结果对比</h3>
                  <div className="space-y-2">
                    {Object.entries(result.dimension_comparison).map(([key, val]) => (
                      <div key={key} className="grid grid-cols-4 gap-2 text-xs items-center bg-gray-50 rounded-lg p-2">
                        <span className="font-medium text-gray-700">{key}</span>
                        <span>A: {Math.round(Number(val.A || 0))}</span>
                        <span>B: {Math.round(Number(val.B || 0))}</span>
                        <span className="text-amber-700">胜出: {val.winner || "-"}</span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {result.recommendations && result.recommendations.length > 0 && (
                <Card className="bg-white border-gray-200 p-5">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">测试建议</h3>
                  <ul className="space-y-2">
                    {result.recommendations.map((rec, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {result.text_report && (
                <Card className="bg-white border-gray-200 p-5">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">完整对比报告</h3>
                  <pre className="whitespace-pre-wrap text-xs sm:text-sm text-gray-600 leading-relaxed font-sans">
                    {result.text_report}
                  </pre>
                </Card>
              )}
            </div>
          )}

          <NextStepActions
            actions={[
              { label: "进入执行记录", path: "/ad-analytics?view=records", variant: "default" },
            ]}
          />
        </div>
      </main>
    </div>
  );
}
