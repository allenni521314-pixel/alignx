import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AppSidebar } from "@/components/AppSidebar";
import { PageHeader } from "@/components/PageHeader";
import { NextStepActions } from "@/components/NextStepActions";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
  Database,
  Search,
  UploadCloud,
  ClipboardPaste,
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
  asin: "当前ASIN",
  title: "示例：除味猫砂盆广告验证",
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

type ImportMode = "paste" | "upload" | "manual" | null;
type ImportAdRow = typeof emptyAd;

function normalizeHeader(value: string) {
  return value.toLowerCase().replace(/[%$()]/g, "").replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "");
}

function parseNumber(value: string | undefined) {
  const num = Number(String(value || "").replace(/[$,%\s,]/g, ""));
  return Number.isFinite(num) ? num : 0;
}

function parseReportLine(line: string, delimiter: string) {
  if (delimiter === "\t") return line.split("\t").map((cell) => cell.trim());
  const cells: string[] = [];
  let current = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      cells.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  cells.push(current.trim());
  return cells;
}

function parseAdReport(text: string): ImportAdRow[] {
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length < 2) return [];
  const delimiter = lines[0].includes("\t") ? "\t" : ",";
  const headers = parseReportLine(lines[0], delimiter).map(normalizeHeader);
  const pick = (row: string[], names: string[]) => {
    const index = headers.findIndex((header) => names.some((name) => header.includes(name)));
    return index >= 0 ? row[index] : "";
  };
  return lines.slice(1).map((line) => {
    const row = parseReportLine(line, delimiter);
    const adGroup = pick(row, ["adgroup", "广告组", "campaign", "广告活动"]) || "导入广告组";
    const keyword = pick(row, ["customersearchterm", "searchterm", "keyword", "targeting", "搜索词", "关键词"]) || "未识别关键词";
    const date = pick(row, ["date", "startdate", "enddate", "日期"]) || new Date().toISOString().split("T")[0];
    const matchType = (pick(row, ["matchtype", "匹配类型"]) || "exact").toLowerCase();
    return {
      ...emptyAd,
      ad_group_name: adGroup,
      keyword,
      match_type: matchType.includes("broad") || matchType.includes("广泛") ? "broad" : matchType.includes("phrase") || matchType.includes("词组") ? "phrase" : "exact",
      impressions: parseNumber(pick(row, ["impressions", "曝光"])),
      clicks: parseNumber(pick(row, ["clicks", "点击"])),
      spend: parseNumber(pick(row, ["spend", "cost", "花费"])),
      orders: parseNumber(pick(row, ["orders", "purchases", "订单"])),
      sales: parseNumber(pick(row, ["sales", "revenue", "销售额", "销售"])),
      date: /^\d{4}-\d{2}-\d{2}/.test(date) ? date.slice(0, 10) : new Date().toISOString().split("T")[0],
    };
  }).filter((row) => row.keyword && (row.impressions || row.clicks || row.spend || row.orders || row.sales));
}

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
  const [importMode, setImportMode] = useState<ImportMode>(null);
  const [importText, setImportText] = useState("");
  const [importing, setImporting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [asinQuery, setAsinQuery] = useState("");
  const validationSnapshotKeyRef = useRef("");

  const { loading: authLoading } = useRequireAuth();
  const parsedImportRows = parseAdReport(importText);

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

  const productIdsByAsinQuery = asinQuery.trim()
    ? products
      .filter((product) => product.asin.toLowerCase().includes(asinQuery.trim().toLowerCase()))
      .map((product) => product.id)
    : [];
  const filteredAds = adRecords.filter((ad) => {
    const matchesProduct = selectedProductId && selectedProductId !== "all"
      ? ad.product_id === Number(selectedProductId)
      : true;
    const matchesAsinQuery = asinQuery.trim()
      ? productIdsByAsinQuery.includes(ad.product_id)
      : true;
    return matchesProduct && matchesAsinQuery;
  });

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
  const validationHypothesisLabel = validationMetrics.assigned ? validationMetrics.hypothesis_id : "未绑定具体假设";
  const validationKeywordGroupLabel = validationMetrics.assigned ? validationMetrics.keyword_group_id : "全部广告数据";
  const sampleProgress = Math.min(100, Math.round((Number(validationMetrics.clicks || 0) / 100) * 100));

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
        module_name: "广告验证",
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

  const openImportMode = (mode: ImportMode) => {
    setImportMode(mode);
    setShowForm(mode === "manual");
  };

  const handleFileImport = async (file?: File) => {
    if (!file) return;
    const text = await file.text();
    setImportText(text);
    setImportMode("upload");
    setShowForm(false);
    toast.success("文件已读取，请确认解析结果后导入");
  };

  const saveImportedRows = async () => {
    if (!selectedProductId || selectedProductId === "all") {
      toast.error("请先选择一个产品，再导入广告报表");
      return;
    }
    if (parsedImportRows.length === 0) {
      toast.error("未解析到有效广告数据，请检查表头和内容");
      return;
    }
    setImporting(true);
    try {
      await Promise.all(parsedImportRows.map((row) => client.entities.ad_data.create({
        data: {
          product_id: Number(selectedProductId),
          ...row,
          impressions: Number(row.impressions),
          clicks: Number(row.clicks),
          spend: Number(row.spend),
          orders: Number(row.orders),
          sales: Number(row.sales),
          date: row.date + " 00:00:00",
        },
      })));
      saveActionSnapshot({
        module_key: "ad_analytics",
        module_name: "广告验证",
        action_key: "import_ad_report",
        action_name: "导入广告报表",
        product_id: Number(selectedProductId),
        title: `导入 ${parsedImportRows.length} 条广告数据`,
        input_snapshot: { mode: importMode, rows: parsedImportRows.slice(0, 20) },
        output_snapshot: { imported_count: parsedImportRows.length },
        data_source: importMode === "upload" ? "report_upload" : "report_paste",
        confidence: "user_report",
        ai_called: false,
        source_record_table: "ad_data",
      }).catch(() => {});
      toast.success(`已导入 ${parsedImportRows.length} 条广告数据`);
      setImportText("");
      setImportMode(null);
      await loadAdData();
    } catch (e: any) {
      toast.error(e?.message || "导入失败");
    } finally {
      setImporting(false);
    }
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
        summary: `当前验证对象「${validationHypothesisLabel}」点击量为 ${validationClicks}，未达到100次点击的最低判定样本，暂不建议判断测试是否成立。`,
        actions: ["继续跑量到100次点击以上", "保持预算、Listing版本和关键词结构稳定", "不要提前扩大预算或暂停测试"],
      };
    }
    if (cvrNum >= 8 && (acosNum <= 35 || Number(validationMetrics.sales || 0) === 0)) {
      return {
        level: "测试成立",
        color: "text-emerald-700 bg-emerald-50 border-emerald-200",
        icon: CheckCircle2,
        summary: `验证对象「${validationHypothesisLabel}」在「${validationKeywordGroupLabel}」中的转化承接表现较好，可沉淀为有效假设。`,
        actions: ["扩大高转化关键词预算", "保留当前Listing承诺表达", "将结论回流到数据回流模块"],
      };
    }
    if (ctrNum > 0.4 && cvrNum < 5) {
      return {
        level: "点击成立，转化未成立",
        color: "text-teal-700 bg-teal-50 border-teal-200",
        icon: AlertTriangle,
        summary: `验证对象「${validationHypothesisLabel}」点击入口成立，但详情页、价格、评价或承诺可信度没有承接。`,
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
      module_name: "广告验证",
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
                  : "录入每一轮广告执行数据，为后续效果验证提供事实依据"}
              </p>
            </div>
            {isValidationView ? (
              <Button variant="outline" className="border-gray-200 text-gray-600 bg-transparent" onClick={() => goTo("/ad-analytics?view=records")}>
                查看执行记录
              </Button>
            ) : (
              <Button className="bg-brand-600 hover:bg-brand-500 text-white" onClick={() => openImportMode(showForm || importMode ? null : "paste")}>
                {showForm || importMode ? <X className="w-4 h-4 mr-1" /> : <Plus className="w-4 h-4 mr-1" />}
                {showForm || importMode ? "取消" : "录入数据"}
              </Button>
            )}
          </div>

          {isValidationView ? (
            <PageHeader
              objective="验证Listing诊断假设是否带来点击、转化和投入产出改善"
              inputSource="执行记录中的曝光、点击、花费、订单、销售额"
              process="按CTR、CVR、ACOS、ROAS判断诊断假设是否成立"
              outputTarget="效果验证结论、成立/未成立原因、下一步动作"
              action="将验证结论送入数据回流"
              feedback="用真实投放结果校准下一轮诊断和优化判断"
              tone="orange"
            />
          ) : (
            <PageHeader
              objective="保存每一轮广告执行数据"
              inputSource="粘贴/上传Amazon广告报表为主；API授权同步为正式版能力"
              process="结构化记录投放动作和实际指标"
              outputTarget="可追溯的执行记录、关键词表现明细"
              action="进入效果验证判断测试是否成立"
              feedback="为效果验证和数据回流提供真实执行数据"
              tone="cyan"
            />
          )}

          {!isValidationView && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mb-4 sm:mb-6">
              <Card className="bg-emerald-50 border-emerald-100 p-4">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-white border border-emerald-100 flex items-center justify-center">
                    <ClipboardPaste className="w-4 h-4 text-emerald-700" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">推荐：粘贴报表</p>
                    <p className="text-xs text-gray-600 mt-1 leading-relaxed">
                      用户从Amazon广告后台下载报表，复制表格后粘贴到系统，自动解析字段并入库。
                    </p>
                    <Button size="sm" className="mt-3 bg-emerald-700 hover:bg-emerald-600 text-white" onClick={() => openImportMode("paste")}>
                      打开粘贴入口
                    </Button>
                  </div>
                </div>
              </Card>
              <Card className="bg-amber-50 border-amber-100 p-4">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-white border border-amber-100 flex items-center justify-center">
                    <UploadCloud className="w-4 h-4 text-amber-700" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">同样支持：上传文件</p>
                    <p className="text-xs text-gray-600 mt-1 leading-relaxed">
                      支持CSV/Excel广告报表上传，字段映射后进入同一套验证和数据回流逻辑。
                    </p>
                    <label className="inline-flex mt-3">
                      <input
                        type="file"
                        accept=".csv,.txt,.tsv"
                        className="hidden"
                        onChange={(e) => handleFileImport(e.target.files?.[0])}
                      />
                      <span className="inline-flex h-9 items-center rounded-md bg-amber-600 px-3 text-sm font-medium text-white hover:bg-amber-500 cursor-pointer">
                        选择报表文件
                      </span>
                    </label>
                  </div>
                </div>
              </Card>
              <Card className="bg-gray-50 border-gray-200 p-4">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-white border border-gray-100 flex items-center justify-center">
                    <Database className="w-4 h-4 text-gray-600" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">未来：API授权同步</p>
                    <p className="text-xs text-gray-600 mt-1 leading-relaxed">
                      不让AI代替用户登录后台抓数据；接入Amazon Ads API后再做自动同步。
                    </p>
                  </div>
                </div>
              </Card>
            </div>
          )}

          {!isValidationView && importMode && importMode !== "manual" && (
            <Card className="bg-white border-gray-200 p-4 sm:p-6 mb-6">
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-4">
                <div>
                  <h3 className="text-lg font-semibold">
                    {importMode === "upload" ? "上传报表解析" : "粘贴广告报表"}
                  </h3>
                  <p className="text-sm text-gray-500 mt-1">
                    先选择产品，再粘贴 Amazon Ads 报表表格；系统会按表头识别曝光、点击、花费、订单和销售额。
                  </p>
                </div>
                <Button variant="outline" onClick={() => { setImportMode(null); setImportText(""); }}>
                  关闭
                </Button>
              </div>
              <Textarea
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                placeholder={"从Excel或CSV复制后粘贴到这里，第一行需要包含表头，例如：\nAd Group\tKeyword\tMatch Type\tImpressions\tClicks\tSpend\tOrders\tSales\tDate"}
                className="min-h-[180px] bg-gray-50 border-gray-200 font-mono text-xs"
              />
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mt-4">
                <p className="text-sm text-gray-500">
                  已解析 {parsedImportRows.length} 条。{selectedProductId && selectedProductId !== "all" ? "将导入到当前选中产品。" : "请先在上方选择一个产品。"}
                </p>
                <Button onClick={saveImportedRows} disabled={importing || parsedImportRows.length === 0} className="bg-brand-600 hover:bg-brand-500 text-white">
                  <Save className="w-4 h-4 mr-1" /> {importing ? "导入中..." : "导入解析结果"}
                </Button>
              </div>
              {parsedImportRows.length > 0 && (
                <div className="overflow-x-auto mt-4 rounded-lg border border-gray-100">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-50 text-gray-500">
                      <tr>
                        <th className="text-left p-2">广告组</th>
                        <th className="text-left p-2">关键词/搜索词</th>
                        <th className="text-right p-2">曝光</th>
                        <th className="text-right p-2">点击</th>
                        <th className="text-right p-2">花费</th>
                        <th className="text-right p-2">订单</th>
                        <th className="text-right p-2">销售额</th>
                      </tr>
                    </thead>
                    <tbody>
                      {parsedImportRows.slice(0, 8).map((row, idx) => (
                        <tr key={`${row.keyword}-${idx}`} className="border-t border-gray-100">
                          <td className="p-2">{row.ad_group_name}</td>
                          <td className="p-2">{row.keyword}</td>
                          <td className="p-2 text-right">{row.impressions}</td>
                          <td className="p-2 text-right">{row.clicks}</td>
                          <td className="p-2 text-right">${Number(row.spend).toFixed(2)}</td>
                          <td className="p-2 text-right">{row.orders}</td>
                          <td className="p-2 text-right">${Number(row.sales).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}

          {/* Product Filter */}
          <Card className="bg-white border-gray-200 p-3 sm:p-4 mb-4 sm:mb-6">
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr_auto] gap-3 items-end">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">产品范围</label>
                <Select value={selectedProductId} onValueChange={setSelectedProductId}>
                  <SelectTrigger className="bg-gray-50 border-gray-200 text-gray-900">
                    <SelectValue placeholder="全部已同步产品" />
                  </SelectTrigger>
                  <SelectContent className="bg-white border-gray-200">
                    <SelectItem value="all" className="text-gray-900 hover:bg-brand-50">全部已同步产品</SelectItem>
                    {products.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)} className="text-gray-900 hover:bg-brand-50">
                        {p.asin} - {p.title.substring(0, 40)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">手动输入ASIN快速筛选</label>
                <div className="relative">
                  <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <Input
                    value={asinQuery}
                    onChange={(e) => setAsinQuery(e.target.value.trim().toUpperCase())}
                    placeholder="例如 B0XXXXXXXX"
                    className="bg-gray-50 border-gray-200 pl-9"
                  />
                </div>
              </div>
              <div className="text-xs text-gray-500 lg:text-right">
                当前 {filteredAds.length} 条记录 · {products.length} 个产品
              </div>
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
                <div className="flex gap-2">
                  <Button variant="outline" className="bg-white" onClick={() => goTo("/ad-analytics?view=records")}>
                    补录广告数据
                  </Button>
                  <Button asChild className="bg-emerald-600 hover:bg-emerald-500 text-white">
                    <a href="/optimization-suggestions?view=data-feedback">
                      进入数据回流
                    </a>
                  </Button>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-4">
                <div className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                  <p className="text-xs text-gray-500">验证对象</p>
                  <p className="text-sm font-semibold text-gray-900 mt-1">{validationHypothesisLabel}</p>
                  <p className="text-[11px] text-gray-400 mt-1">{validationKeywordGroupLabel}</p>
                </div>
                <div className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-gray-500">样本进度</p>
                    <span className="text-xs font-semibold text-gray-700">{Number(validationMetrics.clicks || 0)}/100 点击</span>
                  </div>
                  <div className="h-2 bg-white rounded-full overflow-hidden mt-2">
                    <div className="h-full bg-amber-500 rounded-full" style={{ width: `${sampleProgress}%` }} />
                  </div>
                </div>
                <div className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                  <p className="text-xs text-gray-500">当前指标</p>
                  <p className="text-sm font-semibold text-gray-900 mt-1">CTR {validationMetrics.ctr}% · CVR {validationMetrics.cvr}%</p>
                  <p className="text-[11px] text-gray-400 mt-1">ACoS {validationMetrics.acos}%</p>
                </div>
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
                  <p className="text-xs text-gray-500 mt-1">优先按“验证假设 + 关键词组 + 轮次”判断，避免多个实验混在一起。</p>
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
                            <p className="font-medium text-gray-900">{group.assigned ? group.hypothesis_id : "未绑定具体假设"}</p>
                            <p className="text-[11px] text-gray-400">第 {group.optimization_round} 轮 · {group.record_count} 条记录</p>
                          </td>
                          <td className="p-3 text-gray-600">
                            <p>{group.assigned ? group.keyword_group_id : "全部广告数据"}</p>
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
