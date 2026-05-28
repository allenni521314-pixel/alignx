import { useEffect, useState } from "react";
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
  RefreshCw,
  Target,
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
  model_used?: string;
  judgment_source?: string;
  data_source?: string;
  fallback_reason?: string;
}

interface ListingDiagnosisDetail {
  id: number;
  listing_title: string;
  marketplace?: string;
  input_data?: {
    title?: string;
    bullet_points?: string;
    description?: string;
    a_plus_content?: string;
    backend_keywords?: string;
    asin?: string;
    price?: string;
    marketplace?: string;
  };
  scores?: Record<string, number>;
  diagnosis_report?: {
    suggestions?: {
      title_rewrite?: string;
      bullet_points_optimization?: string[];
      backend_keywords_addition?: string[];
      image_suggestions?: string[];
      a_plus_suggestions?: string;
    };
    keyword_coverage?: {
      missing_categories?: Record<string, string[]>;
    };
    ad_keywords?: {
      high_conversion?: Array<{ keyword?: string; keyword_type?: string; intent?: string }>;
      traffic?: Array<{ keyword?: string; keyword_type?: string; intent?: string }>;
      long_tail?: Array<{ keyword?: string; keyword_type?: string; intent?: string }>;
    };
    overall_summary?: string;
    ad_validation_plan?: Record<string, unknown>;
  };
}

interface ABTestPlan {
  source: string;
  variable: string;
  hypothesis: string;
  metrics: string[];
  evidence: string[];
}

const emptyVariantA: VariantForm = {
  label: "A 原诊断版本",
  asin: "",
  title: "",
  bullets: "",
  description: "",
  conversion: "",
};

const emptyVariantB: VariantForm = {
  label: "B 单变量优化版",
  asin: "",
  title: "",
  bullets: "",
  description: "",
  conversion: "",
};

const emptyPlan: ABTestPlan = {
  source: "未连接诊断",
  variable: "待生成",
  hypothesis: "先从上一轮本品诊断生成单变量测试，再进入广告验证。",
  metrics: ["CTR", "CVR", "CPC", "ACOS", "关键词订单"],
  evidence: [],
};

const TEST_VARIABLE_OPTIONS = [
  "使用场景表达",
  "功能机制表达",
  "状态触发词与风险消除承接",
  "差异化承诺",
  "产品身份清晰度",
  "目标人群身份表达",
  "兼容/搭配对象表达",
  "心理利益表达",
  "主观属性可信表达",
  "趋势词与市场入口",
  "自定义变量",
];

const getLongRunningApiBase = () => {
  if (import.meta.env.VITE_API_BASE_URL) return import.meta.env.VITE_API_BASE_URL;
  if (
    typeof window !== "undefined" &&
    window.location.hostname !== "localhost" &&
    window.location.hostname !== "127.0.0.1"
  ) {
    return "https://alignxagent-api.onrender.com";
  }
  return "";
};

const SCORE_LABELS: Record<string, string> = {
  function_expression: "功能表达",
  scenario_expression: "场景表达",
  identity_fit: "身份适配",
  psychology_benefit: "心理利益",
  risk_elimination: "风险消除",
  product_identity: "产品身份",
  compatibility: "兼容搭配",
  subjective_properties: "主观属性",
  differentiation: "差异化",
  market_trend: "市场趋势",
};

function normalizeBullets(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).filter(Boolean).join("\n");
  return String(value || "");
}

function pickWeakestDimension(scores?: Record<string, number>) {
  const entries = Object.entries(scores || {}).filter(([, value]) => Number.isFinite(Number(value)));
  if (!entries.length) return "risk_elimination";
  return entries.sort((a, b) => Number(a[1]) - Number(b[1]))[0][0];
}

function keywordCandidates(report?: ListingDiagnosisDetail["diagnosis_report"]) {
  const buckets = [
    ...(report?.ad_keywords?.high_conversion || []),
    ...(report?.ad_keywords?.long_tail || []),
    ...(report?.ad_keywords?.traffic || []),
  ];
  return buckets
    .filter((item) => ["relationship", "state_trigger"].includes(String(item.keyword_type || "")))
    .map((item) => String(item.keyword || "").trim())
    .filter(Boolean)
    .slice(0, 5);
}

function buildAutoABFromDiagnosis(detail: ListingDiagnosisDetail): { a: VariantForm; b: VariantForm; plan: ABTestPlan } {
  const input = detail.input_data || {};
  const report = detail.diagnosis_report || {};
  const weakest = pickWeakestDimension(detail.scores);
  const weakestLabel = SCORE_LABELS[weakest] || "诊断低分项";
  const keywords = keywordCandidates(report);
  const title = input.title || detail.listing_title || "";
  const originalBullets = normalizeBullets(input.bullet_points);
  const optimizedBullets = normalizeBullets(report.suggestions?.bullet_points_optimization);
  const fallbackKeyword = keywords[0] || "odor control";

  const variableByDimension: Record<string, string> = {
    risk_elimination: "状态触发词与风险消除承接",
    scenario_expression: "使用场景表达",
    function_expression: "功能机制表达",
    differentiation: "差异化承诺",
    compatibility: "兼容/搭配对象表达",
    product_identity: "产品身份清晰度",
    psychology_benefit: "心理利益表达",
    identity_fit: "目标人群身份表达",
    subjective_properties: "主观属性可信表达",
    market_trend: "趋势词与市场入口",
  };
  const variable = variableByDimension[weakest] || `${weakestLabel}补强`;

  const bTitle = report.suggestions?.title_rewrite?.trim()
    || (title.toLowerCase().includes(fallbackKeyword.toLowerCase()) ? title : `${fallbackKeyword.replace(/\b\w/g, (m) => m.toUpperCase())} - ${title}`.slice(0, 190));

  const bBullets = optimizedBullets || [
    `${fallbackKeyword.replace(/\b\w/g, (m) => m.toUpperCase())}: clarify the exact user problem this product solves`,
    "Explain the mechanism with concrete material, structure, compatibility, or use condition",
    "Connect the benefit to a real scenario instead of a generic feature claim",
    "Remove ambiguity that could create wasted clicks, returns, or low conversion",
    "Keep this round focused on one test variable so ad results can be attributed",
  ].join("\n");

  const source = `来自最近本品诊断 #${detail.id}`;
  const evidence = [
    `${weakestLabel}分数最低，适合作为本轮单变量优化入口`,
    report.overall_summary || "",
    keywords.length ? `优先测试关系/状态词：${keywords.join(", ")}` : "",
  ].filter(Boolean);

  return {
    a: {
      label: "A 原诊断版本",
      asin: input.asin || "当前ASIN",
      title,
      bullets: originalBullets,
      description: input.a_plus_content || input.description || "A版保留上一轮本品诊断输入内容。",
      conversion: "",
    },
    b: {
      label: `B ${variable}`,
      asin: input.asin || "当前ASIN",
      title: bTitle,
      bullets: bBullets,
      description: `本轮只测试：${variable}。不同时改价格、图片数量、评价承诺或多个卖点，避免归因混乱。`,
      conversion: "",
    },
    plan: {
      source,
      variable,
      hypothesis: `如果B版补强「${variable}」成立，广告应表现为CTR或CVR提升，同时CPC/ACOS不恶化；若只提升CTR不提升CVR，说明承接页或价格/信任不足。`,
      metrics: ["CTR", "CVR", "CPC", "ACOS", "关键词订单", "无效点击率"],
      evidence,
    },
  };
}

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
    model_used: "frontend_local_rules",
    judgment_source: "frontend_local_fallback",
    data_source: "frontend_local_fallback",
    fallback_reason: reason,
  };
}

export default function ABTestComparison() {
  const { loading: authLoading } = useRequireAuth();
  const [variantA, setVariantA] = useState<VariantForm>(emptyVariantA);
  const [variantB, setVariantB] = useState<VariantForm>(emptyVariantB);
  const [loading, setLoading] = useState(false);
  const [loadingDiagnosis, setLoadingDiagnosis] = useState(false);
  const [result, setResult] = useState<ABResult | null>(null);
  const [testPlan, setTestPlan] = useState<ABTestPlan>(emptyPlan);
  const [sourceDiagnosisId, setSourceDiagnosisId] = useState<number | null>(null);

  const loadLatestDiagnosis = async (showToast = false) => {
    setLoadingDiagnosis(true);
    try {
      const historyRes = await axios.get("/api/v1/listing-diagnosis/history?limit=1", { headers: getAuthHeaders() });
      const latest = historyRes.data?.items?.[0];
      if (!latest?.id) {
        if (showToast) toast.warning("还没有本品诊断记录，请先完成一次本品诊断");
        return;
      }
      const detailRes = await axios.get<ListingDiagnosisDetail>(`/api/v1/listing-diagnosis/history/${latest.id}`, {
        headers: getAuthHeaders(),
      });
      const generated = buildAutoABFromDiagnosis(detailRes.data);
      setVariantA(generated.a);
      setVariantB(generated.b);
      setTestPlan(generated.plan);
      setSourceDiagnosisId(detailRes.data.id);
      setResult(null);
      if (showToast) toast.success(`已接入真实本品诊断 #${detailRes.data.id}`);
    } catch (e) {
      toast.error(axios.isAxiosError(e) ? e.response?.data?.detail || "读取最近诊断失败" : "读取最近诊断失败");
    } finally {
      setLoadingDiagnosis(false);
    }
  };

  useEffect(() => {
    void loadLatestDiagnosis(false);
  }, []);

  if (authLoading) return null;

  const updateA = (key: keyof VariantForm, value: string) => {
    setVariantA((prev) => ({ ...prev, [key]: value }));
  };

  const updateB = (key: keyof VariantForm, value: string) => {
    setVariantB((prev) => ({ ...prev, [key]: value }));
  };

  const updateTestVariable = (value: string) => {
    setTestPlan((prev) => ({
      ...prev,
      variable: value,
      hypothesis: `如果B版补强「${value}」成立，广告应表现为CTR或CVR提升，同时CPC/ACOS不恶化；若只提升CTR不提升CVR，说明承接页或价格/信任不足。`,
    }));
    setVariantB((prev) => ({
      ...prev,
      label: value && value !== "待生成" ? `B ${value}` : prev.label,
      description: `本轮只测试：${value}。不同时改价格、主图、A+、评价承诺或多个卖点，避免广告归因混乱。`,
    }));
    setResult(null);
  };

  const updateMetrics = (value: string) => {
    setTestPlan((prev) => ({
      ...prev,
      metrics: value
        .split(/[/,，、\s]+/)
        .map((item) => item.trim())
        .filter(Boolean),
    }));
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
        `${getLongRunningApiBase()}/api/v1/causal/ab-comparison`,
        {
          variant_a: toVariantPayload(variantA),
          variant_b: toVariantPayload(variantB),
          variant_a_label: variantA.label || "A",
          variant_b_label: variantB.label || "B",
          historical_conversion_a: safeNum(variantA.conversion),
          historical_conversion_b: safeNum(variantB.conversion),
          test_plan: testPlan,
          source_diagnosis_id: sourceDiagnosisId,
        },
        { headers: getAuthHeaders(), timeout: 180000 }
      );
      setResult(res.data);
      const source = res.data?.judgment_source || res.data?.data_source || "deepseek_v4_reasoning";
      saveActionSnapshot({
        module_key: "ab_test",
        module_name: "A/B测试",
        action_key: "compare_ab_versions",
        action_name: "A/B测试结果对比",
        asin: variantA.asin || variantB.asin,
        title: `${variantA.label} vs ${variantB.label}`,
        input_snapshot: { variant_a: variantA, variant_b: variantB, test_plan: testPlan, source_diagnosis_id: sourceDiagnosisId },
        output_snapshot: res.data,
        data_source: source,
        confidence: String(res.data?.confidence_score || ""),
        ai_called: source !== "backend_rules_fallback",
        source_record_table: "action_snapshots",
      }).catch(() => {});
      toast.success(source === "backend_rules_fallback" ? "A/B测试已用后台规则兜底" : "AI A/B推理完成");
    } catch (e) {
      const reason = axios.isAxiosError(e)
        ? e.code === "ECONNABORTED"
          ? "后端A/B对比超过180秒，本地兜底仅作临时参考。"
          : e.response?.data?.detail || "后端A/B对比网络失败，本地兜底仅作临时参考。"
        : "后端A/B对比网络失败，本地兜底仅作临时参考。";
      const fallback = buildLocalABResult(variantA, variantB, reason);
      setResult(fallback);
      saveActionSnapshot({
        module_key: "ab_test",
        module_name: "A/B测试",
        action_key: "compare_ab_versions",
        action_name: "A/B测试结果对比",
        asin: variantA.asin || variantB.asin,
        title: `${variantA.label} vs ${variantB.label}`,
        input_snapshot: { variant_a: variantA, variant_b: variantB, test_plan: testPlan, source_diagnosis_id: sourceDiagnosisId },
        output_snapshot: fallback,
        data_source: "local_fallback",
        confidence: String(fallback.confidence_score || ""),
        ai_called: false,
        source_record_table: "action_snapshots",
      }).catch(() => {});
      toast.warning("后端未返回结果，已生成临时本地兜底");
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

  const resultSource = result?.judgment_source || result?.data_source || "";
  const resultSourceLabel =
    resultSource === "deepseek_v4_reasoning"
      ? "AI 推理"
      : resultSource === "backend_rules_fallback"
        ? "后台规则兜底"
        : resultSource === "frontend_local_fallback"
          ? "前端本地兜底"
          : "判断来源待确认";

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
            objective="承接上一轮本品诊断，把低分问题转成单变量A/B测试"
            inputSource={sourceDiagnosisId ? `真实本品诊断 #${sourceDiagnosisId}` : "最近一次本品诊断"}
            process="A版保留原始诊断输入，B版只改一个诊断变量，避免广告归因混乱"
            outputTarget="测试变量、广告验证指标、胜出版本、下一轮优化依据"
            action="将胜出版本进入广告执行记录"
            feedback="真实广告结果回流到效果验证和数据回流"
            tone="amber"
          />

          <Card className="bg-white border-amber-100 p-4 sm:p-5 mb-5">
            <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Target className="w-4 h-4 text-amber-600" />
                  <h2 className="text-sm font-semibold text-gray-900">本轮A/B测试计划</h2>
                  <span className="text-xs rounded-full bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5">
                    {testPlan.source}
                  </span>
                </div>
                <div className="grid md:grid-cols-2 gap-3 text-sm">
                  <div className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                    <label className="text-xs text-gray-500 mb-1 block">本轮只测试一个变量</label>
                    <select
                      value={TEST_VARIABLE_OPTIONS.includes(testPlan.variable) ? testPlan.variable : "自定义变量"}
                      onChange={(e) => updateTestVariable(e.target.value === "自定义变量" ? "" : e.target.value)}
                      className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm font-semibold text-gray-900 outline-none focus:border-amber-400"
                    >
                      {TEST_VARIABLE_OPTIONS.map((item) => (
                        <option key={item} value={item}>{item}</option>
                      ))}
                    </select>
                    <Input
                      value={testPlan.variable}
                      onChange={(e) => updateTestVariable(e.target.value)}
                      placeholder="也可以手动输入本轮测试变量"
                      className="mt-2 bg-white border-gray-200"
                    />
                  </div>
                  <div className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                    <label className="text-xs text-gray-500 mb-1 block">验证指标</label>
                    <Input
                      value={testPlan.metrics.join(" / ")}
                      onChange={(e) => updateMetrics(e.target.value)}
                      placeholder="CTR / CVR / CPC / ACOS / 关键词订单"
                      className="bg-white border-gray-200 font-semibold"
                    />
                  </div>
                </div>
                <Textarea
                  value={testPlan.hypothesis}
                  onChange={(e) => setTestPlan((prev) => ({ ...prev, hypothesis: e.target.value }))}
                  className="bg-gray-50 border-gray-100 min-h-[78px] text-sm text-gray-700 leading-relaxed"
                  placeholder="填写本轮A/B假设：如果B版变量成立，广告指标应该怎样变化？"
                />
                <p className="text-xs text-amber-700">
                  原则：每轮只改一个主要变量；可以自由选择变量，但不要把多个改动混在同一轮测试里。
                </p>
                {testPlan.evidence.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {testPlan.evidence.map((item, idx) => (
                      <span key={idx} className="text-xs rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-100 px-2.5 py-1">
                        {item}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <Button
                variant="outline"
                onClick={() => loadLatestDiagnosis(true)}
                disabled={loadingDiagnosis}
                className="bg-white shrink-0"
              >
                {loadingDiagnosis ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-1.5" />}
                接入最新本品诊断
              </Button>
            </div>
          </Card>

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
                  placeholder={item.title === "B版本" ? "本轮测试变量说明，不要同时改多个变量" : "描述 / A+摘要"}
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
            disabled={loading || loadingDiagnosis || !sourceDiagnosisId}
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
                    <span
                      className={`px-3 py-1.5 rounded-lg border ${
                        resultSource === "deepseek_v4_reasoning"
                          ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                          : resultSource === "backend_rules_fallback"
                            ? "bg-amber-50 border-amber-200 text-amber-700"
                            : "bg-red-50 border-red-200 text-red-700"
                      }`}
                    >
                      {resultSourceLabel}
                    </span>
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
            currentStep="测试计划"
            actions={[
              { label: "进入执行记录", path: "/ad-analytics?view=records", variant: "default" },
            ]}
          />
        </div>
      </main>
    </div>
  );
}
