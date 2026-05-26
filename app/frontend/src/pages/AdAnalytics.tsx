import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AppSidebar } from "@/components/AppSidebar";
import { PageHeader } from "@/components/PageHeader";
import { NextStepActions } from "@/components/NextStepActions";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { client } from "@/lib/api";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { getAuthHeaders } from "@/lib/auth-headers";
import { saveActionSnapshot, upsertAdValidationFeedbackRound } from "@/lib/workflow-api";
import { getApiErrorMessage } from "@/lib/api-retry";
import { toast } from "sonner";
import {
  BarChart3,
  Plus,
  X,
  Save,
  TrendingUp,
  DollarSign,
  MousePointerClick,
  Eye,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ResponsiveContainer } from "recharts";

interface Product {
  id: number;
  asin: string;
  title: string;
}

interface AdRecord {
  id: number;
  product_id: number;
  hypothesis_id?: string;
  keyword_group_id?: string;
  optimization_round?: number;
  ad_group_name: string;
  keyword: string;
  match_type: string;
  impressions: number;
  clicks: number;
  spend: number;
  orders: number;
  sales: number;
  date: string;
}

interface ValidationGroup {
  hypothesis_id: string;
  keyword_group_id: string;
  optimization_round: number;
  keywords: string[];
  impressions: number;
  clicks: number;
  spend: number;
  orders: number;
  sales: number;
  ctr: string;
  cvr: string;
  acos: string;
  record_count: number;
  assigned: boolean;
}

function inferValidationHitStatus(level: string) {
  if (level === "测试成立") return "已命中";
  if (level === "数据不足") return "待验证";
  if (level === "点击成立，转化未成立") return "部分命中";
  return "未命中";
}

function inferValidationFailureReason(metrics: { impressions?: number; clicks?: number; ctr?: string | number; cvr?: string | number; acos?: string | number }, level: string) {
  const impressions = Number(metrics.impressions || 0);
  const clicks = Number(metrics.clicks || 0);
  const ctr = Number(metrics.ctr || 0);
  const cvr = Number(metrics.cvr || 0);
  const acos = Number(metrics.acos || 0);
  if (level === "测试成立") return "none";
  if (clicks < 100) return "sample_not_enough";
  if (impressions >= 1000 && ctr < 0.25) return "image_click_gap";
  if (ctr < 0.4) return "keyword_mismatch";
  if (cvr < 8) return "detail_trust_gap";
  if (acos > 35) return "price_promise_gap";
  return "needs_manual_review";
}

const emptyAd = {
  hypothesis_id: "",
  keyword_group_id: "",
  optimization_round: 1,
  ad_group_name: "",
  keyword: "",
  match_type: "exact",
  impressions: 0,
  clicks: 0,
  spend: 0,
  orders: 0,
  sales: 0,
  date: new Date().toISOString().split("T")[0],
};

const demoProduct: Product = {
  id: 1,
  asin: "DEMOAMZ001",
  title: "DEMO AlignX Odor Control Cat Litter Box",
};

const demoAdRecords: AdRecord[] = [
  {
    id: 1,
    product_id: 1,
    ad_group_name: "DEMO Odor Test - Exact",
    keyword: "cat litter box odor eliminator",
    match_type: "exact",
    impressions: 5200,
    clicks: 62,
    spend: 48.2,
    orders: 7,
    sales: 279.93,
    date: "2026-05-13",
  },
  {
    id: 2,
    product_id: 1,
    ad_group_name: "DEMO Odor Test - Phrase",
    keyword: "ammonia odor remover",
    match_type: "phrase",
    impressions: 4100,
    clicks: 54,
    spend: 39.6,
    orders: 6,
    sales: 239.94,
    date: "2026-05-14",
  },
  {
    id: 3,
    product_id: 1,
    ad_group_name: "DEMO Odor Test - Phrase",
    keyword: "cat litter deodorizer",
    match_type: "phrase",
    impressions: 3600,
    clicks: 41,
    spend: 34.1,
    orders: 3,
    sales: 119.97,
    date: "2026-05-15",
  },
];

export default function AdAnalytics() {
  const navigate = useNavigate();
  const location = useLocation();
  const view = new URLSearchParams(location.search).get("view");
  const isValidationView = view === "validation";
  const [products, setProducts] = useState<Product[]>([demoProduct]);
  const [selectedProductId, setSelectedProductId] = useState<string>("");
  const [adRecords, setAdRecords] = useState<AdRecord[]>(demoAdRecords);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyAd);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const validationSnapshotKeyRef = useRef("");

  const { loading: authLoading } = useRequireAuth();

  const goTo = (path: string) => {
    if (path.includes("?")) {
      window.location.assign(path);
      return;
    }
    navigate(path);
  };

  useEffect(() => {
    if (!authLoading) {
      loadInitialData();
    }
  }, [authLoading]);

  const loadInitialData = async () => {
    try {
      const res = await fetch("/api/v1/entities/products?limit=50", {
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "加载产品失败");
      setProducts((data?.items || []).length > 0 ? data.items : [demoProduct]);
      await loadAdData();
    } catch (e) {
      console.error(e);
      toast.error(getApiErrorMessage(e));
      setProducts([demoProduct]);
      await loadAdData();
    }
  };

  const loadAdData = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/entities/ad_data?limit=200", {
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "加载广告数据失败");
      setAdRecords((data?.items || []).length > 0 ? data.items : demoAdRecords);
    } catch (e) {
      console.error(e);
      toast.error(getApiErrorMessage(e));
      setAdRecords(demoAdRecords);
    } finally { setLoading(false); }
  };

  const filteredAds = selectedProductId && selectedProductId !== "all"
    ? adRecords.filter((a) => a.product_id === Number(selectedProductId))
    : adRecords;

  const totalImpressions = filteredAds.reduce((s, a) => s + (a.impressions || 0), 0);
  const totalClicks = filteredAds.reduce((s, a) => s + (a.clicks || 0), 0);
  const totalSpend = filteredAds.reduce((s, a) => s + (a.spend || 0), 0);
  const totalOrders = filteredAds.reduce((s, a) => s + (a.orders || 0), 0);
  const totalSales = filteredAds.reduce((s, a) => s + (a.sales || 0), 0);
  const ctr = totalImpressions > 0 ? ((totalClicks / totalImpressions) * 100).toFixed(2) : "0.00";
  const cvr = totalClicks > 0 ? ((totalOrders / totalClicks) * 100).toFixed(2) : "0.00";
  const acos = totalSales > 0 ? ((totalSpend / totalSales) * 100).toFixed(2) : "0.00";
  const roas = totalSpend > 0 ? (totalSales / totalSpend).toFixed(2) : "0.00";

  const keywordMap = new Map<string, { impressions: number; clicks: number; spend: number; orders: number; sales: number }>();
  filteredAds.forEach((ad) => {
    const e = keywordMap.get(ad.keyword) || { impressions: 0, clicks: 0, spend: 0, orders: 0, sales: 0 };
    keywordMap.set(ad.keyword, {
      impressions: e.impressions + (ad.impressions || 0),
      clicks: e.clicks + (ad.clicks || 0),
      spend: e.spend + (ad.spend || 0),
      orders: e.orders + (ad.orders || 0),
      sales: e.sales + (ad.sales || 0),
    });
  });
  const keywordRanking = Array.from(keywordMap.entries())
    .map(([kw, data]) => ({
      keyword: kw, ...data,
      ctr: data.impressions > 0 ? ((data.clicks / data.impressions) * 100).toFixed(2) : "0.00",
      cvr: data.clicks > 0 ? ((data.orders / data.clicks) * 100).toFixed(2) : "0.00",
      acos: data.sales > 0 ? ((data.spend / data.sales) * 100).toFixed(2) : "0.00",
    }))
    .sort((a, b) => b.sales - a.sales);

  const validationGroups: ValidationGroup[] = Array.from(
    filteredAds.reduce((map, ad) => {
      const hypothesisId = ad.hypothesis_id || "unassigned";
      const keywordGroupId = ad.keyword_group_id || ad.ad_group_name || "default";
      const round = ad.optimization_round || 1;
      const key = `${hypothesisId}::${keywordGroupId}::${round}`;
      const current = map.get(key) || {
        hypothesis_id: hypothesisId,
        keyword_group_id: keywordGroupId,
        optimization_round: round,
        keywords: new Set<string>(),
        impressions: 0,
        clicks: 0,
        spend: 0,
        orders: 0,
        sales: 0,
        record_count: 0,
        assigned: hypothesisId !== "unassigned",
      };
      current.keywords.add(ad.keyword);
      current.impressions += ad.impressions || 0;
      current.clicks += ad.clicks || 0;
      current.spend += ad.spend || 0;
      current.orders += ad.orders || 0;
      current.sales += ad.sales || 0;
      current.record_count += 1;
      map.set(key, current);
      return map;
    }, new Map<string, {
      hypothesis_id: string;
      keyword_group_id: string;
      optimization_round: number;
      keywords: Set<string>;
      impressions: number;
      clicks: number;
      spend: number;
      orders: number;
      sales: number;
      record_count: number;
      assigned: boolean;
    }>())
      .values()
  )
    .map((group) => ({
      ...group,
      keywords: Array.from(group.keywords),
      ctr: group.impressions > 0 ? ((group.clicks / group.impressions) * 100).toFixed(2) : "0.00",
      cvr: group.clicks > 0 ? ((group.orders / group.clicks) * 100).toFixed(2) : "0.00",
      acos: group.sales > 0 ? ((group.spend / group.sales) * 100).toFixed(2) : "0.00",
    }))
    .sort((a, b) => Number(b.assigned) - Number(a.assigned) || b.clicks - a.clicks || b.sales - a.sales);

  const primaryValidation = validationGroups.find((group) => group.assigned) || validationGroups[0];
  const validationMetrics = primaryValidation || {
    hypothesis_id: "unassigned",
    keyword_group_id: "all",
    optimization_round: 1,
    clicks: totalClicks,
    ctr,
    cvr,
    acos,
    sales: totalSales,
    assigned: false,
  };

  const chartData = keywordRanking.slice(0, 8).map((kw) => ({
    name: kw.keyword.length > 8 ? kw.keyword.substring(0, 8) + "..." : kw.keyword,
    sales: kw.sales,
    spend: kw.spend,
  }));

  // Match type distribution
  const matchTypeMap = new Map<string, number>();
  filteredAds.forEach((ad) => {
    matchTypeMap.set(ad.match_type, (matchTypeMap.get(ad.match_type) || 0) + 1);
  });
  const matchTypeLabels: Record<string, string> = { exact: "精准匹配", phrase: "词组匹配", broad: "广泛匹配" };

  const handleSubmit = async () => {
    if (!selectedProductId || selectedProductId === "all") { toast.error("请先选择一个产品"); return; }
    if (!form.ad_group_name.trim() || !form.keyword.trim()) { toast.error("广告组名称和关键词为必填项"); return; }
    setSaving(true);
    try {
      await client.entities.ad_data.create({
        data: {
          product_id: Number(selectedProductId),
          hypothesis_id: form.hypothesis_id || undefined,
          keyword_group_id: form.keyword_group_id || undefined,
          optimization_round: Number(form.optimization_round) || 1,
          ...form,
          impressions: Number(form.impressions),
          clicks: Number(form.clicks),
          spend: Number(form.spend),
          orders: Number(form.orders),
          sales: Number(form.sales),
          date: form.date + " 00:00:00",
        },
      });
      saveActionSnapshot({
        module_key: "ad_analytics",
        module_name: "广告投放",
        action_key: "save_ad_execution",
        action_name: "广告执行记录",
        product_id: Number(selectedProductId),
        title: form.ad_group_name,
        input_snapshot: form,
        output_snapshot: {
          product_id: Number(selectedProductId),
          ...form,
          hypothesis_id: form.hypothesis_id || undefined,
          keyword_group_id: form.keyword_group_id || undefined,
          optimization_round: Number(form.optimization_round) || 1,
          impressions: Number(form.impressions),
          clicks: Number(form.clicks),
          spend: Number(form.spend),
          orders: Number(form.orders),
          sales: Number(form.sales),
        },
        data_source: "user_input",
        confidence: Number(form.clicks) >= 100 ? "high" : Number(form.clicks) >= 30 ? "medium" : "low",
        ai_called: false,
        source_record_table: "ad_data",
      }).catch(() => {});
      toast.success("广告数据已添加");
      setShowForm(false);
      setForm(emptyAd);
      await loadAdData();
    } catch (e: any) { toast.error(e?.message || "添加失败"); }
    finally { setSaving(false); }
  };

  const kpiCards = [
    { label: "总曝光", value: totalImpressions.toLocaleString(), icon: Eye, color: "text-teal-600" },
    { label: "总点击", value: totalClicks.toLocaleString(), icon: MousePointerClick, color: "text-brand-600" },
    { label: "总花费", value: `$${totalSpend.toFixed(2)}`, icon: DollarSign, color: "text-red-600" },
    { label: "总销售额", value: `$${totalSales.toFixed(2)}`, icon: TrendingUp, color: "text-emerald-600" },
    { label: "CTR", value: `${ctr}%`, icon: MousePointerClick, color: "text-teal-600" },
    { label: "CVR", value: `${cvr}%`, icon: TrendingUp, color: "text-green-600" },
    { label: "ACoS", value: `${acos}%`, icon: BarChart3, color: "text-amber-600" },
    { label: "ROAS", value: roas, icon: DollarSign, color: "text-gold-600" },
  ];

  const validationConclusion = (() => {
    const validationClicks = Number(validationMetrics.clicks || 0);
    const cvrNum = Number(validationMetrics.cvr);
    const acosNum = Number(validationMetrics.acos);
    const ctrNum = Number(validationMetrics.ctr);
    if (validationClicks < 100) {
      return {
        level: "数据不足",
        color: "text-amber-700 bg-amber-50 border-amber-200",
        icon: AlertTriangle,
        summary: `当前主验证假设 ${validationMetrics.hypothesis_id} 点击量不足100，暂不建议判定测试是否成立。`,
        actions: ["继续跑量到100次点击以上", "保持预算和Listing版本稳定", "不要提前扩大或暂停测试"],
      };
    }
    if (cvrNum >= 8 && (acosNum <= 35 || Number(validationMetrics.sales || 0) === 0)) {
      return {
        level: "测试成立",
        color: "text-emerald-700 bg-emerald-50 border-emerald-200",
        icon: CheckCircle2,
        summary: `假设 ${validationMetrics.hypothesis_id} 的关键词组 ${validationMetrics.keyword_group_id} 转化承接表现较好，可沉淀为有效假设。`,
        actions: ["扩大高转化关键词预算", "保留当前Listing承诺表达", "将结论回流到复盘优化"],
      };
    }
    if (ctrNum > 0.4 && cvrNum < 5) {
      return {
        level: "点击成立，转化未成立",
        color: "text-teal-700 bg-teal-50 border-teal-200",
        icon: AlertTriangle,
        summary: `假设 ${validationMetrics.hypothesis_id} 点击入口成立，但详情页、价格、评价或承诺可信度没有承接。`,
        actions: ["回到本品诊断检查详情页承接", "复核价格和评价信任", "保留点击词但调整Listing表达"],
      };
    }
    return {
      level: "测试未成立",
      color: "text-red-700 bg-red-50 border-red-200",
      icon: AlertTriangle,
      summary: "当前点击和转化都不足以支持原诊断假设，需要调整关键词或Listing首屏表达。",
      actions: ["暂停低效关键词", "重做A/B测试计划", "回到Listing诊断复核缺失需求"],
    };
  })();

  useEffect(() => {
    if (!isValidationView || loading) return;
    const key = `${selectedProductId || "all"}-${totalImpressions}-${totalClicks}-${totalSpend}-${totalOrders}-${totalSales}-${validationConclusion.level}`;
    if (validationSnapshotKeyRef.current === key) return;
    validationSnapshotKeyRef.current = key;
    const selectedProduct = products.find((product) => String(product.id) === selectedProductId);
    const hitStatus = inferValidationHitStatus(validationConclusion.level);
    const missReason = inferValidationFailureReason(
      {
        impressions: validationMetrics.impressions || totalImpressions,
        clicks: validationMetrics.clicks || totalClicks,
        ctr: validationMetrics.ctr || ctr,
        cvr: validationMetrics.cvr || cvr,
        acos: validationMetrics.acos || acos,
      },
      validationConclusion.level,
    );
    saveActionSnapshot({
      module_key: "ad_analytics",
      module_name: "广告投放",
      action_key: "validate_ad_effect",
      action_name: "广告效果验证",
      product_id: selectedProductId && selectedProductId !== "all" ? Number(selectedProductId) : null,
      title: `广告效果验证-${validationConclusion.level}`,
      input_snapshot: { selected_product_id: selectedProductId || "all", primary_validation: validationMetrics, records: filteredAds },
      output_snapshot: {
        conclusion: validationConclusion,
        metrics: { totalImpressions, totalClicks, totalSpend, totalOrders, totalSales, ctr, cvr, acos, roas },
        keyword_ranking: keywordRanking,
        hypothesis_validations: validationGroups,
      },
      data_source: "ad_data",
      confidence: totalClicks >= 100 ? "high" : totalClicks >= 30 ? "medium" : "low",
      ai_called: false,
      source_record_table: "ad_data",
    }).catch(() => {});
    if (selectedProductId && selectedProductId !== "all") {
      upsertAdValidationFeedbackRound({
        product_id: Number(selectedProductId),
        asin: selectedProduct?.asin,
        marketplace: "US",
        optimization_round: Number(validationMetrics.optimization_round || 1),
        stage: "ad_validation",
        status: hitStatus === "待验证" ? "running" : "completed",
        diagnosis_issue: `广告假设 ${validationMetrics.hypothesis_id} / ${validationMetrics.keyword_group_id} 验证结果`,
        judgment_basis: {
          source: "ad_analytics_validation_view",
          rule: "按 hypothesis_id + keyword_group_id + optimization_round 聚合广告数据，回流判断命中率。",
          conclusion: validationConclusion.summary,
        },
        suggested_action: validationConclusion.actions[0] || "",
        ad_result: {
          conclusion: validationConclusion,
          primary_validation: validationMetrics,
          validation_groups: validationGroups,
          aggregate_metrics: { totalImpressions, totalClicks, totalSpend, totalOrders, totalSales, ctr, cvr, acos, roas },
        },
        hit_status: hitStatus,
        miss_reason: missReason,
        next_iteration: validationConclusion.actions.join("；"),
        confidence_after: totalClicks >= 100 ? 85 : totalClicks >= 30 ? 65 : 40,
        executed_at: new Date().toISOString(),
      }).catch(() => {});
    }
  }, [
    isValidationView,
    loading,
    selectedProductId,
    products,
    totalImpressions,
    totalClicks,
    totalSpend,
    totalOrders,
    totalSales,
    ctr,
    cvr,
    acos,
    roas,
    validationConclusion.level,
    validationConclusion.summary,
    validationMetrics.hypothesis_id,
    validationMetrics.keyword_group_id,
    validationMetrics.optimization_round,
  ]);

  return (
    <div className="flex h-screen bg-white text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="p-4 sm:p-6 max-w-7xl mx-auto pt-14 md:pt-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 sm:mb-8 gap-3">
            <div>
              <h1 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
                <BarChart3 className="w-5 h-5 sm:w-6 sm:h-6 text-amber-600" />
                {isValidationView ? "广告效果验证" : "广告执行记录"}
              </h1>
              <p className="text-gray-500 mt-1 text-sm">
                {isValidationView
                  ? "判断A/B测试和Listing诊断假设是否被广告数据验证"
                  : "录入和查看每一轮广告投放执行数据"}
              </p>
            </div>
            {isValidationView ? (
              <Button variant="outline" className="border-gray-200 text-gray-600 bg-transparent" onClick={() => goTo("/ad-analytics?view=records")}>
                查看执行记录
              </Button>
            ) : (
              <Button className="bg-brand-600 hover:bg-brand-500 text-white" onClick={() => setShowForm(!showForm)}>
                {showForm ? <X className="w-4 h-4 mr-1" /> : <Plus className="w-4 h-4 mr-1" />}
                {showForm ? "取消" : "录入数据"}
              </Button>
            )}
          </div>

          {isValidationView ? (
            <PageHeader
              objective="验证广告测试计划的点击、转化和投入产出表现"
              inputSource="执行记录中的曝光、点击、花费、订单、销售额"
              process="按CTR、CVR、ACOS、ROAS判断诊断假设是否成立"
              outputTarget="效果验证结论、成立/未成立原因、下一步动作"
              action="将验证结论送入复盘优化"
              feedback="用真实投放结果校准下一轮判断"
              tone="orange"
            />
          ) : (
            <PageHeader
              objective="保存每一轮广告投放执行数据"
              inputSource="Campaign、Ad Group、Keyword、Search Term、CTR、CVR、CPC、ACOS、ROAS、Spend、Orders"
              process="结构化记录投放动作和实际指标"
              outputTarget="可追溯的执行记录、关键词表现明细"
              action="进入效果验证判断测试是否成立"
              feedback="为复盘优化提供真实执行数据"
              tone="cyan"
            />
          )}

          {/* Product Filter */}
          <Card className="bg-white border-gray-200 p-3 sm:p-4 mb-4 sm:mb-6">
            <div className="flex items-center gap-3 sm:gap-4">
              <label className="text-sm text-gray-500 whitespace-nowrap">筛选产品</label>
              <Select value={selectedProductId} onValueChange={setSelectedProductId}>
                <SelectTrigger className="bg-gray-50 border-gray-200 text-gray-900 max-w-md">
                  <SelectValue placeholder="全部产品" />
                </SelectTrigger>
                <SelectContent className="bg-white border-gray-200">
                  <SelectItem value="all" className="text-gray-900 hover:bg-brand-50">全部产品</SelectItem>
                  {products.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)} className="text-gray-900 hover:bg-brand-50">
                      {p.asin} - {p.title.substring(0, 40)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </Card>

          {/* Add Data Form */}
          {!isValidationView && showForm && (
            <Card className="bg-white border-gray-200 p-4 sm:p-6 mb-6">
              <h3 className="text-lg font-semibold mb-4">录入广告数据</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
                <div className="sm:col-span-2">
                  <Label className="text-gray-600 text-xs">广告组名称 *</Label>
                  <Input value={form.ad_group_name} onChange={(e) => setForm({ ...form, ad_group_name: e.target.value })} className="bg-gray-50 border-gray-200 text-gray-900 mt-1" placeholder="如：主推词-精准" />
                </div>
                <div>
                  <Label className="text-gray-600 text-xs">验证假设ID</Label>
                  <Input value={form.hypothesis_id} onChange={(e) => setForm({ ...form, hypothesis_id: e.target.value })} className="bg-gray-50 border-gray-200 text-gray-900 mt-1" placeholder="如 hypothesis-1" />
                </div>
                <div>
                  <Label className="text-gray-600 text-xs">关键词组ID</Label>
                  <Input value={form.keyword_group_id} onChange={(e) => setForm({ ...form, keyword_group_id: e.target.value })} className="bg-gray-50 border-gray-200 text-gray-900 mt-1" placeholder="如 odor-control-p0" />
                </div>
                <div>
                  <Label className="text-gray-600 text-xs">优化轮次</Label>
                  <Input type="number" value={form.optimization_round} onChange={(e) => setForm({ ...form, optimization_round: parseInt(e.target.value) || 1 })} className="bg-gray-50 border-gray-200 text-gray-900 mt-1" />
                </div>
                <div>
                  <Label className="text-gray-600 text-xs">关键词 *</Label>
                  <Input value={form.keyword} onChange={(e) => setForm({ ...form, keyword: e.target.value })} className="bg-gray-50 border-gray-200 text-gray-900 mt-1" />
                </div>
                <div>
                  <Label className="text-gray-600 text-xs">匹配类型</Label>
                  <Select value={form.match_type} onValueChange={(v) => setForm({ ...form, match_type: v })}>
                    <SelectTrigger className="bg-gray-50 border-gray-200 text-gray-900 mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-white border-gray-200">
                      <SelectItem value="exact" className="text-gray-900">精准</SelectItem>
                      <SelectItem value="phrase" className="text-gray-900">词组</SelectItem>
                      <SelectItem value="broad" className="text-gray-900">广泛</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-gray-600 text-xs">曝光量</Label>
                  <Input type="number" value={form.impressions} onChange={(e) => setForm({ ...form, impressions: parseInt(e.target.value) || 0 })} className="bg-gray-50 border-gray-200 text-gray-900 mt-1" />
                </div>
                <div>
                  <Label className="text-gray-600 text-xs">点击量</Label>
                  <Input type="number" value={form.clicks} onChange={(e) => setForm({ ...form, clicks: parseInt(e.target.value) || 0 })} className="bg-gray-50 border-gray-200 text-gray-900 mt-1" />
                </div>
                <div>
                  <Label className="text-gray-600 text-xs">花费 ($)</Label>
                  <Input type="number" step="0.01" value={form.spend} onChange={(e) => setForm({ ...form, spend: parseFloat(e.target.value) || 0 })} className="bg-gray-50 border-gray-200 text-gray-900 mt-1" />
                </div>
                <div>
                  <Label className="text-gray-600 text-xs">订单数</Label>
                  <Input type="number" value={form.orders} onChange={(e) => setForm({ ...form, orders: parseInt(e.target.value) || 0 })} className="bg-gray-50 border-gray-200 text-gray-900 mt-1" />
                </div>
                <div>
                  <Label className="text-gray-600 text-xs">销售额 ($)</Label>
                  <Input type="number" step="0.01" value={form.sales} onChange={(e) => setForm({ ...form, sales: parseFloat(e.target.value) || 0 })} className="bg-gray-50 border-gray-200 text-gray-900 mt-1" />
                </div>
                <div>
                  <Label className="text-gray-600 text-xs">日期</Label>
                  <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className="bg-gray-50 border-gray-200 text-gray-900 mt-1" />
                </div>
              </div>
              <Button onClick={handleSubmit} disabled={saving} className="bg-brand-600 hover:bg-brand-500 text-white mt-4">
                <Save className="w-4 h-4 mr-1" /> {saving ? "保存中..." : "保存数据"}
              </Button>
            </Card>
          )}

          {isValidationView && (
            <Card className="bg-white border-gray-200 p-5 mb-4 sm:mb-6">
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center border ${validationConclusion.color}`}>
                    <validationConclusion.icon className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">验证结论</p>
                    <h2 className="text-lg font-bold text-gray-900 mt-0.5">{validationConclusion.level}</h2>
                    <p className="text-sm text-gray-600 mt-1">{validationConclusion.summary}</p>
                  </div>
                </div>
                <Button asChild className="bg-emerald-600 hover:bg-emerald-500 text-white">
                  <a href="/optimization-suggestions?view=data-feedback">
                    进入数据回流
                  </a>
                </Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
                {validationConclusion.actions.map((action) => (
                  <div key={action} className="rounded-lg bg-gray-50 border border-gray-100 p-3 text-sm text-gray-700">
                    {action}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {isValidationView && validationGroups.length > 0 && (
            <Card className="bg-white border-gray-200 p-5 mb-4 sm:mb-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900">假设级验证结果</h3>
                  <p className="text-xs text-gray-500 mt-1">优先按 hypothesis_id + keyword_group_id + 轮次判断，避免多个实验混在一起。</p>
                </div>
                <span className="text-xs text-gray-400">
                  已绑定 {validationGroups.filter((group) => group.assigned).length} 组
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-500 border-b border-gray-100">
                      <th className="text-left p-3 font-medium">假设</th>
                      <th className="text-left p-3 font-medium">关键词组</th>
                      <th className="text-right p-3 font-medium">点击</th>
                      <th className="text-right p-3 font-medium">CTR</th>
                      <th className="text-right p-3 font-medium">CVR</th>
                      <th className="text-right p-3 font-medium">ACoS</th>
                      <th className="text-left p-3 font-medium">状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {validationGroups.map((group) => {
                      const status = group.clicks < 100
                        ? "待验证"
                        : Number(group.cvr) >= 8 && (Number(group.acos) <= 35 || group.sales === 0)
                          ? "已命中"
                          : "未命中";
                      return (
                        <tr key={`${group.hypothesis_id}-${group.keyword_group_id}-${group.optimization_round}`} className="border-b border-gray-100 hover:bg-gray-50">
                          <td className="p-3">
                            <p className="font-medium text-gray-900">{group.hypothesis_id}</p>
                            <p className="text-[11px] text-gray-400">第 {group.optimization_round} 轮 · {group.record_count} 条记录</p>
                          </td>
                          <td className="p-3 text-gray-600">
                            <p>{group.keyword_group_id}</p>
                            <p className="text-[11px] text-gray-400 truncate max-w-[260px]">{group.keywords.join(", ")}</p>
                          </td>
                          <td className="p-3 text-right text-gray-600">{group.clicks}</td>
                          <td className="p-3 text-right text-teal-600">{group.ctr}%</td>
                          <td className="p-3 text-right text-green-600">{group.cvr}%</td>
                          <td className={`p-3 text-right ${Number(group.acos) > 35 ? "text-red-600" : "text-amber-600"}`}>{group.acos}%</td>
                          <td className="p-3">
                            <span className={`inline-flex px-2 py-1 rounded-full text-xs border ${
                              status === "已命中"
                                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                : status === "待验证"
                                  ? "bg-amber-50 text-amber-700 border-amber-200"
                                  : "bg-red-50 text-red-700 border-red-200"
                            }`}>
                              {status}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-4 mb-4 sm:mb-6">
            {kpiCards.map((kpi) => (
              <Card key={kpi.label} className="bg-white border-gray-200 p-3 sm:p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-gray-500">{kpi.label}</p>
                    <p className={`text-lg sm:text-xl font-bold mt-1 ${kpi.color}`}>{kpi.value}</p>
                  </div>
                  <kpi.icon className={`w-4 h-4 sm:w-5 sm:h-5 ${kpi.color} opacity-50`} />
                </div>
              </Card>
            ))}
          </div>

          {/* Charts Row */}
          {isValidationView && chartData.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6 mb-4 sm:mb-6">
              <Card className="bg-white border-gray-200 p-4 sm:p-5 lg:col-span-2">
                <h3 className="text-sm font-semibold text-gray-600 mb-4">关键词销售额 vs 花费</h3>
                <div className="h-52 sm:h-60">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                      <XAxis dataKey="name" stroke="#6B7280" fontSize={10} tickLine={false} />
                      <YAxis stroke="#6B7280" fontSize={10} tickLine={false} axisLine={false} />
                      <RTooltip contentStyle={{ background: "#ffffff", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px", color: "#fff", fontSize: 12 }} />
                      <Bar dataKey="sales" fill="#0f2a24" radius={[4, 4, 0, 0]} name="销售额($)" />
                      <Bar dataKey="spend" fill="#F59E0B" radius={[4, 4, 0, 0]} name="花费($)" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>

              <Card className="bg-white border-gray-200 p-4 sm:p-5">
                <h3 className="text-sm font-semibold text-gray-600 mb-4">匹配类型分布</h3>
                <div className="space-y-4 mt-6">
                  {Array.from(matchTypeMap.entries()).map(([type, count]) => {
                    const total = filteredAds.length || 1;
                    const pct = ((count / total) * 100).toFixed(1);
                    const colors: Record<string, string> = { exact: "bg-brand-500", phrase: "bg-gold-500", broad: "bg-amber-500" };
                    return (
                      <div key={type}>
                        <div className="flex items-center justify-between text-sm mb-1">
                          <span className="text-gray-500">{matchTypeLabels[type] || type}</span>
                          <span className="text-gray-900 font-medium">{pct}%</span>
                        </div>
                        <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${colors[type] || "bg-gray-500"}`} style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                  {matchTypeMap.size === 0 && <p className="text-gray-500 text-sm text-center py-4">暂无数据</p>}
                </div>
              </Card>
            </div>
          )}

          {/* Keyword Ranking - Desktop Table / Mobile Cards */}
          <Card className="bg-white border-gray-200">
            <div className="p-4 sm:p-5 border-b border-gray-200">
              <h3 className="font-semibold">
                {isValidationView ? "关键词验证结果" : "执行记录明细"}
              </h3>
            </div>
            {keywordRanking.length === 0 ? (
              <div className="p-8 sm:p-12 text-center text-gray-500">暂无广告数据</div>
            ) : (
              <>
                {/* Desktop Table */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-gray-500 border-b border-gray-100">
                        <th className="text-left p-3 font-medium">关键词</th>
                        <th className="text-right p-3 font-medium">曝光</th>
                        <th className="text-right p-3 font-medium">点击</th>
                        <th className="text-right p-3 font-medium">花费</th>
                        <th className="text-right p-3 font-medium">订单</th>
                        <th className="text-right p-3 font-medium">销售额</th>
                        <th className="text-right p-3 font-medium">CTR</th>
                        <th className="text-right p-3 font-medium">CVR</th>
                        <th className="text-right p-3 font-medium">ACoS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {keywordRanking.map((kw) => (
                        <tr key={kw.keyword} className="border-b border-gray-100 hover:bg-gray-50">
                          <td className="p-3 text-gray-900 font-medium">{kw.keyword}</td>
                          <td className="p-3 text-right text-gray-500">{kw.impressions.toLocaleString()}</td>
                          <td className="p-3 text-right text-gray-500">{kw.clicks.toLocaleString()}</td>
                          <td className="p-3 text-right text-red-600">${kw.spend.toFixed(2)}</td>
                          <td className="p-3 text-right text-gray-600">{kw.orders}</td>
                          <td className="p-3 text-right text-emerald-600">${kw.sales.toFixed(2)}</td>
                          <td className="p-3 text-right text-teal-600">{kw.ctr}%</td>
                          <td className="p-3 text-right text-green-600">{kw.cvr}%</td>
                          <td className={`p-3 text-right ${parseFloat(kw.acos) > 30 ? "text-red-600" : "text-amber-600"}`}>{kw.acos}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile Cards */}
                <div className="md:hidden divide-y divide-white/[0.04]">
                  {keywordRanking.map((kw) => (
                    <div key={kw.keyword} className="p-4 space-y-2">
                      <p className="font-medium text-sm text-gray-900">{kw.keyword}</p>
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div><span className="text-gray-500">曝光</span><p className="text-gray-600">{kw.impressions.toLocaleString()}</p></div>
                        <div><span className="text-gray-500">点击</span><p className="text-gray-600">{kw.clicks.toLocaleString()}</p></div>
                        <div><span className="text-gray-500">花费</span><p className="text-red-600">${kw.spend.toFixed(2)}</p></div>
                        <div><span className="text-gray-500">销售额</span><p className="text-emerald-600">${kw.sales.toFixed(2)}</p></div>
                        <div><span className="text-gray-500">CTR</span><p className="text-teal-600">{kw.ctr}%</p></div>
                        <div><span className="text-gray-500">ACoS</span><p className={parseFloat(kw.acos) > 30 ? "text-red-600" : "text-amber-600"}>{kw.acos}%</p></div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </Card>

          <NextStepActions
            actions={[
              isValidationView
                ? { label: "进入数据回流", path: "/optimization-suggestions?view=data-feedback", variant: "default" }
                : { label: "进入效果验证", path: "/ad-analytics?view=validation", variant: "default" },
            ]}
          />
        </div>
      </main>
    </div>
  );
}
