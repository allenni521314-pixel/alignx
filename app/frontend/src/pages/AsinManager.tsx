import { useEffect, useState, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { AppSidebar } from "@/components/AppSidebar";
import { PageHeader } from "@/components/PageHeader";
import { NextStepActions } from "@/components/NextStepActions";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { client } from "@/lib/api";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { getApiErrorMessage } from "@/lib/api-retry";
import axios from "axios";
import { getAuthHeaders } from "@/lib/auth-headers";
import { toast } from "sonner";
import {
  Package,
  Pencil,
  Trash2,
  Save,
  X,
  Star,
  Search,
  Loader2,
  CloudDownload,
  History,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Clock,
  ExternalLink,
  Award,
  Sparkles,
  ShieldCheck,
  AlertTriangle,
} from "lucide-react";
import {
  FiveDimensionScoreCard,
  FiveDScoreButton,
  type FiveDScoreResult,
} from "@/components/FiveDimensionScore";
import { getActionSnapshots, saveActionSnapshot, type ActionSnapshot } from "@/lib/workflow-api";

const MARKETPLACE_OPTIONS = [
  { value: "US", label: "🇺🇸 美国站", domain: "www.amazon.com", currency: "$" },
  { value: "JP", label: "🇯🇵 日本站", domain: "www.amazon.co.jp", currency: "¥" },
  { value: "DE", label: "🇩🇪 德国站", domain: "www.amazon.de", currency: "€" },
  { value: "UK", label: "🇬🇧 英国站", domain: "www.amazon.co.uk", currency: "£" },
  { value: "CA", label: "🇨🇦 加拿大站", domain: "www.amazon.ca", currency: "C$" },
] as const;

const MARKETPLACE_BY_VALUE = MARKETPLACE_OPTIONS.reduce(
  (map, item) => ({ ...map, [item.value]: item }),
  {} as Record<string, (typeof MARKETPLACE_OPTIONS)[number]>
);

const getAmazonProductUrl = (asin: string, marketplace = "US") => {
  const site = MARKETPLACE_BY_VALUE[marketplace] || MARKETPLACE_BY_VALUE.US;
  return `https://${site.domain}/dp/${asin}`;
};

const getLongRunningApiBase = () => {
  if (import.meta.env.VITE_API_BASE_URL) return import.meta.env.VITE_API_BASE_URL;
  if (typeof window !== "undefined" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
    return "https://alignxagent-api.onrender.com";
  }
  return "";
};

const isPublicDeployment = () =>
  typeof window !== "undefined" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Product {
  id: number;
  asin: string;
  marketplace?: string;
  title: string;
  bullet_points: string;
  a_plus_content: string;
  search_keywords: string;
  price: number;
  review_count: number;
  rating: number;
  category: string;
  created_at?: string;
}

interface KeywordSalesValidationReport {
  keyword_sales_score: number;
  traffic_quality_level: string;
  sales_source_judgment: string;
  keyword_rank_summary: {
    core_keywords_checked?: number;
    organic_top20_count?: number;
    organic_top50_count?: number;
    sponsored_keyword_count?: number;
    avg_organic_position?: number | null;
    rank_data_note?: string;
  };
  organic_rank_strength: number;
  ad_dependency_risk: number;
  suspicious_signals: string[];
  opportunity_keywords: string[];
  risk_keywords: string[];
  final_recommendation: string;
  rank_snapshots: Array<{
    keyword: string;
    search_page?: number;
    organic_position?: number | null;
    sponsored_position?: number | null;
    overall_position?: number | null;
    is_organic?: boolean;
    is_sponsored?: boolean;
  }>;
}

const emptyProduct = {
  asin: "",
  title: "",
  bullet_points: "",
  a_plus_content: "",
  search_keywords: "",
  price: 0,
  review_count: 0,
  rating: 0,
  category: "",
};

const isOpportunityScore = (score?: FiveDScoreResult) => {
  if (!score) return false;
  if (score.pool_status) return score.pool_status === "opportunity_pool";
  return Boolean(score.qualified);
};

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function AsinManager() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyProduct);
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [deleting, setDeleting] = useState(false);

  // Tab state: "library" = ASIN库, "pool" = ASIN机会池
  const [searchParams, setSearchParams] = useSearchParams();
  const urlTab = searchParams.get("tab");
  const [activeTab, setActiveTabState] = useState<"library" | "pool">(
    urlTab === "pool" ? "pool" : "library"
  );

  // Sync tab state with URL params
  const setActiveTab = useCallback((tab: "library" | "pool") => {
    setActiveTabState(tab);
    if (tab === "pool") {
      setSearchParams({ tab: "pool" }, { replace: true });
    } else {
      setSearchParams({}, { replace: true });
    }
  }, [setSearchParams]);

  // React to URL changes (e.g., sidebar navigation)
  useEffect(() => {
    const t = searchParams.get("tab");
    if (t === "pool" && activeTab !== "pool") {
      setActiveTabState("pool");
    } else if (t !== "pool" && activeTab === "pool") {
      setActiveTabState("library");
    }
  }, [searchParams, activeTab]);

  // Auto-import state
  const [showAutoImport, setShowAutoImport] = useState(true);
  const [autoImportAsin, setAutoImportAsin] = useState("");
  const [autoImportMarketplace, setAutoImportMarketplace] = useState("US");
  const [autoImportLoading, setAutoImportLoading] = useState(false);
  const [autoImportProgress, setAutoImportProgress] = useState(0);
  const [autoImportElapsed, setAutoImportElapsed] = useState(0);
  const [autoImportMessage, setAutoImportMessage] = useState("");
  const [batchImportText, setBatchImportText] = useState("");
  const [batchImportLoading, setBatchImportLoading] = useState(false);
  const [batchImportCurrent, setBatchImportCurrent] = useState("");
  const [importMode, setImportMode] = useState<"single" | "batch">("single");
  const [autoFetch, setAutoFetch] = useState(true);

  // Fetch history state
  const [showHistory, setShowHistory] = useState(false);
  const [fetchHistoryItems, setFetchHistoryItems] = useState<ActionSnapshot[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    if (!autoImportLoading && !batchImportLoading) return;
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      setAutoImportElapsed(elapsed);
      setAutoImportProgress((current) => Math.max(current, Math.min(92, Math.round((elapsed / 60) * 92))));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [autoImportLoading, batchImportLoading]);

  // Refresh single product
  const [refreshingId, setRefreshingId] = useState<number | null>(null);

  // 6D Scoring state
  const [scoringAsin, setScoringAsin] = useState<string | null>(null);
  const [scoreResults, setScoreResults] = useState<Record<string, FiveDScoreResult>>({});
  const [expandedScoreAsin, setExpandedScoreAsin] = useState<string | null>(null);
  const [asinMarketplaceMap, setAsinMarketplaceMap] = useState<Record<string, string>>({});
  const [keywordValidationResults, setKeywordValidationResults] = useState<Record<string, KeywordSalesValidationReport>>({});
  const [validatingKeywordAsin, setValidatingKeywordAsin] = useState<string | null>(null);
  const [expandedKeywordAsin, setExpandedKeywordAsin] = useState<string | null>(null);

  const { loading: authLoading } = useRequireAuth();

  const getProductMarketplace = useCallback(
    (product: Product) =>
      product.marketplace ||
      asinMarketplaceMap[product.asin] ||
      "US",
    [asinMarketplaceMap]
  );

  useEffect(() => {
    if (!authLoading) {
      loadProducts();
      loadExistingScores();
    }
  }, [authLoading]);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/entities/products?limit=100", {
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "加载ASIN失败");
      const items = data?.items || [];
      setProducts(items);
      loadKeywordValidationHistory(items).catch(() => {});
    } catch (e) {
      console.error(e);
      toast.error(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  // Load existing 6D scores from history
  const loadExistingScores = useCallback(async () => {
    try {
      const res = await axios.get("/api/v1/asin-analysis/six-dimension-history?limit=200", {
        headers: getAuthHeaders(),
      });
      const items = res.data?.items || [];
      const map: Record<string, FiveDScoreResult> = {};
      for (const item of items) {
        // Keep only the latest score per ASIN
        if (!map[item.asin]) {
          map[item.asin] = {
            success: true,
            asin: item.asin,
            product_title: item.product_title || "",
            total_score: item.total_score || 0,
            qualified: item.qualified || false,
            dimension_scores: item.dimension_scores || {},
            detail_scores: item.detail_scores || {},
            analysis: item.analysis || {},
            suggestions: item.suggestions || [],
            raw_total: item.raw_total || 0,
            data_completeness: item.data_completeness || 0,
            confidence_level: item.confidence_level || "low",
            risk_level: item.risk_level || "medium",
            decision: item.decision || "",
            pool_status: item.pool_status || "",
            recommended_path: item.recommended_path || "",
            one_sentence_reason: item.one_sentence_reason || "",
            dimensions: item.dimensions || [],
            veto_rules: item.veto_rules || [],
            next_actions: item.next_actions || [],
            is_legacy_score: item.is_legacy_score || false,
            id: item.id,
          };
        }
      }
      setScoreResults(map);
    } catch {
      // Silently fail - scores are optional
    }
  }, []);

  const loadKeywordValidationHistory = useCallback(async (productList: Product[]) => {
    if (!productList.length) return;
    const results = await Promise.allSettled(
      productList.slice(0, 60).map(async (product) => {
        const res = await axios.get(`${getLongRunningApiBase()}/api/v1/asin-selection/${product.asin}/keyword-sales-history`, {
          headers: getAuthHeaders(),
          timeout: 30000,
        });
        const latest = res.data?.items?.[0]?.report;
        return latest ? [product.asin, latest] as const : null;
      })
    );
    const map: Record<string, KeywordSalesValidationReport> = {};
    for (const item of results) {
      if (item.status === "fulfilled" && item.value) {
        map[item.value[0]] = item.value[1] as KeywordSalesValidationReport;
      }
    }
    if (Object.keys(map).length) {
      setKeywordValidationResults((prev) => ({ ...prev, ...map }));
    }
  }, []);

  const loadMarketplaceSnapshots = useCallback(async () => {
    try {
      const items = await getActionSnapshots({ module_key: "asin_selection", limit: 300 });
      const map: Record<string, string> = {};
      for (const item of items || []) {
        const input = (item.input_snapshot || {}) as Record<string, unknown>;
        const output = (item.output_snapshot || {}) as Record<string, unknown>;
        const asin = String(item.asin || input.asin || output.asin || "").toUpperCase();
        const marketplace = String(input.marketplace || output.marketplace || "").toUpperCase();
        if (asin && marketplace && MARKETPLACE_BY_VALUE[marketplace] && !map[asin]) {
          map[asin] = marketplace;
        }
      }
      setAsinMarketplaceMap(map);
    } catch {
      // Marketplace history only improves links and refresh routing.
    }
  }, []);

  useEffect(() => {
    if (!authLoading) {
      loadMarketplaceSnapshots();
    }
  }, [authLoading, loadMarketplaceSnapshots]);

  // Filter products by search and tab
  const filteredProducts = products
    .filter((p) => {
      const q = searchQuery.toLowerCase();
      const matchesSearch =
        !searchQuery ||
        p.asin.toLowerCase().includes(q) ||
        p.title.toLowerCase().includes(q) ||
        (p.category || "").toLowerCase().includes(q);

      if (!matchesSearch) return false;

      // "全部ASIN" shows the complete decision set; "机会池" follows score + risk + veto routing.
      const score = scoreResults[p.asin];
      if (activeTab === "pool") {
        return isOpportunityScore(score);
      }
      return true;
    })
    .sort((a, b) => {
      // In pool tab, sort by score descending (highest first, closer to 100 = better opportunity)
      if (activeTab === "pool") {
        const scoreA = scoreResults[a.asin]?.total_score ?? 0;
        const scoreB = scoreResults[b.asin]?.total_score ?? 0;
        return scoreB - scoreA;
      }
      return 0; // library tab keeps original order (by created_at desc)
    });

  const poolCount = products.filter((p) => {
    const score = scoreResults[p.asin];
    return isOpportunityScore(score);
  }).length;

  const libraryCount = products.length;

  /* ---- 6D Scoring ---- */
  const handleFiveDScore = async (product: Product) => {
    const marketplace = getProductMarketplace(product);
    setScoringAsin(product.asin);
    try {
      const res = await axios.post(
        "/api/v1/asin-analysis/six-dimension-score",
        {
          asin: product.asin,
          marketplace,
          product_title: product.title,
          product_data: {
            title: product.title,
            category: product.category,
            price: product.price,
            rating: product.rating,
            review_count: product.review_count,
            bullet_points: product.bullet_points,
            a_plus_content: product.a_plus_content,
            description_summary: product.a_plus_content,
            search_keywords: product.search_keywords,
          },
        },
        { headers: getAuthHeaders(), timeout: 120000 }
      );

      if (res.data?.success) {
        const result: FiveDScoreResult = res.data;
        setScoreResults((prev) => ({ ...prev, [product.asin]: result }));
        setExpandedScoreAsin(product.asin);
        saveActionSnapshot({
          module_key: "asin_selection",
          module_name: "6维选品",
          action_key: "six_dimension_score",
          action_name: "ASIN 6维选品评分",
          product_id: product.id,
          asin: product.asin,
          title: product.title,
          input_snapshot: { ...product, marketplace },
          output_snapshot: result,
          data_source: "asin_library",
          confidence: result.confidence_level === "high" ? "high" : result.confidence_level === "medium" ? "medium" : "low",
          ai_called: false,
          source_record_table: "asin_analyses",
        }).catch(() => {});
        toast.success(
          `${product.asin} 6维决策完成: ${result.total_score}分 · ${result.decision || "已生成"} · ${result.pool_status === "opportunity_pool" ? "进入机会池" : "未进机会池"}`
        );
      } else {
        toast.error("评分失败，请重试");
      }
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? e.response?.data?.detail || "评分请求失败"
        : e instanceof Error
          ? e.message
          : "评分失败";
      toast.error(msg);
    } finally {
      setScoringAsin(null);
    }
  };

  const saveProductToLibrary = async (productData: Omit<Product, "id" | "created_at" | "marketplace">) => {
    const query = encodeURIComponent(JSON.stringify({ asin: productData.asin }));
    const existingRes = await fetch(`/api/v1/entities/products?query=${query}&limit=1`, {
      headers: getAuthHeaders(),
    });
    const existingData = await existingRes.json().catch(() => ({}));
    const existing = existingData?.items?.[0];
    if (existing?.id) {
      const updateRes = await fetch(`/api/v1/entities/products/${existing.id}`, {
        method: "PUT",
        headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(productData),
      });
      const updated = await updateRes.json().catch(() => ({}));
      if (!updateRes.ok) throw new Error(updated?.detail || "更新ASIN库失败");
      return { product: updated as Product, mode: "updated" as const };
    }
    const createRes = await fetch("/api/v1/entities/products", {
      method: "POST",
      headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(productData),
    });
    const created = await createRes.json().catch(() => ({}));
    if (!createRes.ok) throw new Error(created?.detail || "保存ASIN库失败");
    return { product: created as Product, mode: "created" as const };
  };

  const handleKeywordSalesValidation = async (product: Product) => {
    const marketplace = getProductMarketplace(product);
    setValidatingKeywordAsin(product.asin);
    try {
      const targetKeywords = (product.search_keywords || "")
        .split(/[,，;\n]+/)
        .map((kw) => kw.trim())
        .filter(Boolean)
        .slice(0, 10);
      const res = await axios.post(
        `${getLongRunningApiBase()}/api/v1/asin-selection/keyword-sales-validation`,
        {
          asin: product.asin,
          marketplace,
          category: product.category || "",
          target_keywords: targetKeywords,
          days_range: 30,
        },
        { headers: getAuthHeaders(), timeout: 180000 }
      );
      setKeywordValidationResults((prev) => ({ ...prev, [product.asin]: res.data }));
      setExpandedKeywordAsin(product.asin);
      toast.success(`${product.asin} 关键词销量验证完成：${Math.round(res.data.keyword_sales_score || 0)}分`);
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? e.response?.data?.detail || "关键词销量验证失败"
        : e instanceof Error
          ? e.message
          : "关键词销量验证失败";
      toast.error(msg);
    } finally {
      setValidatingKeywordAsin(null);
    }
  };

  const validateImportedProduct = async (productData: Omit<Product, "id" | "created_at" | "marketplace">, marketplace: string) => {
    const targetKeywords = (productData.search_keywords || "")
      .split(/[,，;\n]+/)
      .map((kw) => kw.trim())
      .filter(Boolean)
      .slice(0, 10);
    const res = await axios.post(
      `${getLongRunningApiBase()}/api/v1/asin-selection/keyword-sales-validation`,
      {
        asin: productData.asin,
        marketplace,
        category: productData.category || "",
        target_keywords: targetKeywords,
        days_range: 30,
      },
      { headers: getAuthHeaders(), timeout: 180000 }
    );
    setKeywordValidationResults((prev) => ({ ...prev, [productData.asin]: res.data }));
    setExpandedKeywordAsin(productData.asin);
    return res.data as KeywordSalesValidationReport;
  };

  /* ---- CRUD ---- */
  const handleSubmit = async () => {
    if (!form.asin.trim()) {
      toast.error("ASIN为必填项");
      return;
    }
    if (!form.title.trim()) {
      toast.error("产品标题为必填项");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...form,
        price: Number(form.price),
        review_count: Number(form.review_count),
        rating: Number(form.rating),
      };
      if (editingId) {
        await client.entities.products.update({
          id: String(editingId),
          data: payload,
        });
        toast.success("产品已更新");
      } else {
        await client.entities.products.create({ data: payload });
        toast.success("产品已添加到ASIN库");
      }
      setShowForm(false);
      setShowAutoImport(true);
      setEditingId(null);
      setForm(emptyProduct);
      await loadProducts();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "操作失败");
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (product: Product) => {
    setForm({
      asin: product.asin,
      title: product.title,
      bullet_points: product.bullet_points || "",
      a_plus_content: product.a_plus_content || "",
      search_keywords: product.search_keywords || "",
      price: product.price || 0,
      review_count: product.review_count || 0,
      rating: product.rating || 0,
      category: product.category || "",
    });
    setEditingId(product.id);
    setShowForm(true);
    setShowAutoImport(false);
  };

  const handleDelete = async (id: number) => {
    try {
      await client.entities.products.delete({ id: String(id) });
      toast.success("产品已从ASIN库移除");
      setSelectedIds((prev) => {
        const n = new Set(prev);
        n.delete(id);
        return n;
      });
      await loadProducts();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "删除失败");
    }
  };

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    try {
      await Promise.all(
        Array.from(selectedIds).map((id) =>
          client.entities.products.delete({ id: String(id) })
        )
      );
      toast.success(`已从ASIN库移除 ${selectedIds.size} 个产品`);
      setSelectedIds(new Set());
      await loadProducts();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "批量删除失败");
    } finally {
      setDeleting(false);
    }
  };

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredProducts.length)
      setSelectedIds(new Set());
    else setSelectedIds(new Set(filteredProducts.map((p) => p.id)));
  };

  const handleCancel = () => {
    setShowForm(false);
    setShowAutoImport(true);
    setEditingId(null);
    setForm(emptyProduct);
  };

  /* ---- Server-side ASIN fetch and analysis ---- */
  const fetchAsinViaAI = async (
    asin: string,
    marketplace: string
  ): Promise<{
    status: string;
    data?: {
      asin: string;
      title: string;
      bullet_points: string;
      a_plus_content: string;
      search_keywords: string;
      price: number;
      review_count: number;
      rating: number;
      category: string;
    };
    error?: string;
    source?: string;
  }> => {
    const apiBase = getLongRunningApiBase();
    const res = await axios.post(
      `${apiBase}/api/v1/asin-analysis/analyze`,
      { asin, marketplace },
      { headers: getAuthHeaders(), timeout: 240000 }
    );
    const d = res.data;
    const pd = d.product_data || {};
    const source = d.data_source || pd._data_source || "server_analysis";
    return {
      status: "success",
      source,
      data: {
        asin: d.asin || asin,
        title: pd.title || d.product_title || "",
        bullet_points: Array.isArray(pd.bullet_points)
          ? pd.bullet_points.join("\n")
          : pd.bullet_points || "",
        a_plus_content: pd.description_summary || "",
        search_keywords: Array.isArray(pd.main_keywords)
          ? pd.main_keywords.join(", ")
          : pd.main_keywords || "",
        price: parseFloat(String(pd.price).replace(/[^0-9.]/g, "")) || 0,
        review_count:
          parseInt(String(pd.review_count).replace(/[^0-9]/g, "")) || 0,
        rating: parseFloat(String(pd.rating)) || 0,
        category: pd.category || "",
      },
    };
  };

  /* ---- Smart fetch: Browser Proxy → Server Scrape → AI (three phases) ---- */
  const smartFetchAsin = async (
    asin: string,
    marketplace: string
  ): Promise<{
    status: string;
    data?: {
      asin: string;
      title: string;
      bullet_points: string;
      a_plus_content: string;
      search_keywords: string;
      price: number;
      review_count: number;
      rating: number;
      category: string;
    };
    error?: string;
    source?: string;
  }> => {
    if (isPublicDeployment()) {
      setAutoImportMessage("公网服务器正在抓取Amazon页面并生成分析结果，通常需要 10-40 秒");
      setAutoImportProgress(35);
      try {
        const serverResult = await fetchAsinViaAI(asin, marketplace);
        setAutoImportProgress(100);
        return {
          ...serverResult,
          source: serverResult.source === "ai_estimated_low_confidence" ? "AI低置信度兜底" : "服务器真实抓取",
        };
      } catch (e: unknown) {
        const msg = axios.isAxiosError(e)
          ? e.code === "ECONNABORTED"
            ? "公网服务器分析超时，请稍后重试。"
            : e.response?.data?.detail || "服务器抓取分析失败"
          : e instanceof Error
            ? e.message
            : "请求失败";
        return { status: "failed", error: msg };
      }
    }

    // Phase 1: Browser proxy fetch. This is the primary path for AlignX:
    // the user only enters an ASIN/link, and the local browser environment assists extraction.
    setAutoImportMessage("Phase 1/3：本地浏览器代理抓取Amazon页面，通常需要 20-30 秒");
    setAutoImportProgress(22);
    try {
      const proxyRes = await axios.post(
        "/api/v1/asin-analysis/proxy-fetch",
        { asin, marketplace },
        { headers: getAuthHeaders(), timeout: 75000 }
      );
      if (proxyRes.data?.success && proxyRes.data?.html) {
        const html = proxyRes.data.html;
        try {
          const parseRes = await axios.post(
            "/api/v1/asin-analysis/parse-html-analyze",
            { asin, marketplace, html },
            { headers: getAuthHeaders(), timeout: 120000 }
          );
          const d = parseRes.data;
          if (d?.success && d.product_data) {
            const pd = d.product_data || {};
            setAutoImportProgress(100);
            return {
              status: "success",
              data: {
                asin: d.asin || asin,
                title: pd.title || d.product_title || "",
                bullet_points: Array.isArray(pd.bullet_points)
                  ? pd.bullet_points.join("\n")
                  : pd.bullet_points || "",
                a_plus_content: pd.description_summary || "",
                search_keywords: Array.isArray(pd.main_keywords)
                  ? pd.main_keywords.join(", ")
                  : pd.main_keywords || "",
                price: parseFloat(String(pd.price).replace(/[^0-9.]/g, "")) || 0,
                review_count:
                  parseInt(String(pd.review_count).replace(/[^0-9]/g, "")) || 0,
                rating: parseFloat(String(pd.rating)) || 0,
                category: pd.category || "",
              },
              source: "浏览器代理",
            };
          }
        } catch {
          // fall through
        }
      }
    } catch (e: unknown) {
      if (axios.isAxiosError(e) && e.code === "ECONNABORTED") {
        toast.warning("浏览器代理抓取超过75秒，已切换到服务器补充抓取和AI兜底。");
      }
      // fall through
    }

    // Phase 2 + 3: Backend server scrape first, then AI fallback when real data is unavailable.
    setAutoImportMessage("Phase 2/3：服务器补充抓取；失败后进入AI低置信度兜底");
    setAutoImportProgress(62);
    try {
      const aiResult = await fetchAsinViaAI(asin, marketplace);
      setAutoImportProgress(100);
      return { ...aiResult, source: aiResult.source === "ai_estimated_low_confidence" ? "AI低置信度兜底" : "服务器真实抓取" };
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? e.code === "ECONNABORTED"
          ? "分析超过180秒，请稍后重试；如果连续失败，说明Amazon页面抓取或模型响应过慢。"
          : e.response?.data?.detail || "AI分析失败"
        : e instanceof Error
          ? e.message
          : "请求失败";
      return { status: "failed", error: msg };
    }
  };

  /* ---- Auto Import (Single) ---- */
  const handleSingleAutoImport = async () => {
    const asin = autoImportAsin.trim().toUpperCase();
    if (!asin) {
      toast.error("请输入ASIN");
      return;
    }
    setAutoImportLoading(true);
    setAutoImportProgress(3);
    setAutoImportElapsed(0);
    setAutoImportMessage("准备开始抓取分析，预计 60 秒内完成");
    try {
      const result = await smartFetchAsin(asin, autoImportMarketplace);
      if (result.status === "success" && result.data) {
        const productData = {
          asin: result.data.asin || asin,
          title: result.data.title || "",
          bullet_points: result.data.bullet_points || "",
          a_plus_content: result.data.a_plus_content || "",
          search_keywords: result.data.search_keywords || "",
          price: result.data.price || 0,
          review_count: result.data.review_count || 0,
          rating: result.data.rating || 0,
          category: result.data.category || "",
        };

        const sourceLabel =
          result.source === "浏览器代理" ? "浏览器代理抓取" : "AI智能分析";
        const snapshotProductData = { ...productData, marketplace: autoImportMarketplace };

        if (autoFetch) {
          try {
            const saved = await saveProductToLibrary(productData);
            setAsinMarketplaceMap((prev) => ({
              ...prev,
              [productData.asin || asin]: autoImportMarketplace,
            }));
            saveActionSnapshot({
              module_key: "asin_selection",
              module_name: "6维选品",
              action_key: "fetch_asin_product",
              action_name: "ASIN抓取并保存",
              asin,
              title: productData.title,
              input_snapshot: { asin, marketplace: autoImportMarketplace },
              output_snapshot: snapshotProductData,
              data_source: sourceLabel,
              confidence: result.source === "浏览器代理" ? "high" : "low",
              ai_called: result.source !== "浏览器代理",
              source_record_table: "products",
            }).catch(() => {});
            toast.success(`已通过${sourceLabel}${saved.mode === "updated" ? "更新" : "保存"} ${asin} 到ASIN库`);
            setAutoImportAsin("");
            await loadProducts();
          } catch {
            toast.error("保存失败，可能ASIN已存在");
          }
        } else {
          setForm(productData);
          setAsinMarketplaceMap((prev) => ({
            ...prev,
            [productData.asin || asin]: autoImportMarketplace,
          }));
          setShowForm(true);
          setShowAutoImport(false);
          setAutoImportAsin("");
          toast.success(`已通过${sourceLabel}抓取 ${asin} 数据，请确认后保存`);
        }
      } else {
        toast.error(result.error || "抓取失败，请检查ASIN是否正确");
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "请求失败");
    } finally {
      setAutoImportLoading(false);
      setAutoImportProgress(0);
      setAutoImportElapsed(0);
      setAutoImportMessage("");
    }
  };

  const handleSingleAutoImportAndValidate = async () => {
    const asin = autoImportAsin.trim().toUpperCase();
    if (!asin) {
      toast.error("请输入ASIN");
      return;
    }
    setAutoImportLoading(true);
    setAutoImportProgress(3);
    setAutoImportElapsed(0);
    setAutoImportMessage("准备抓取、保存并验证关键词销量");
    try {
      const result = await smartFetchAsin(asin, autoImportMarketplace);
      if (result.status !== "success" || !result.data) {
        toast.error(result.error || "抓取失败，请检查ASIN是否正确");
        return;
      }
      const productData = {
        asin: result.data.asin || asin,
        title: result.data.title || "",
        bullet_points: result.data.bullet_points || "",
        a_plus_content: result.data.a_plus_content || "",
        search_keywords: result.data.search_keywords || "",
        price: result.data.price || 0,
        review_count: result.data.review_count || 0,
        rating: result.data.rating || 0,
        category: result.data.category || "",
      };
      setAutoImportMessage("产品数据已保存，正在验证关键词销量结构");
      setAutoImportProgress(86);
      const saved = await saveProductToLibrary(productData);
      setAsinMarketplaceMap((prev) => ({ ...prev, [productData.asin]: autoImportMarketplace }));
      const report = await validateImportedProduct(productData, autoImportMarketplace);
      saveActionSnapshot({
        module_key: "asin_selection",
        module_name: "关键词销量验证",
        action_key: "fetch_save_keyword_sales_validation",
        action_name: "ASIN抓取保存并验证关键词销量",
        product_id: saved.product.id,
        asin: productData.asin,
        title: productData.title,
        input_snapshot: { asin, marketplace: autoImportMarketplace },
        output_snapshot: { product: productData, keyword_sales_validation: report },
        data_source: result.source || "server_analysis",
        confidence: report.keyword_sales_score >= 65 ? "medium" : "low",
        ai_called: false,
        source_record_table: "asin_keyword_sales_validation_reports",
      }).catch(() => {});
      setAutoImportAsin("");
      await loadProducts();
      toast.success(`${productData.asin} 已${saved.mode === "updated" ? "更新" : "保存"}，关键词销量验证 ${Math.round(report.keyword_sales_score)} 分`);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "抓取保存并验证失败");
    } finally {
      setAutoImportLoading(false);
      setAutoImportProgress(0);
      setAutoImportElapsed(0);
      setAutoImportMessage("");
    }
  };

  /* ---- Auto Import (Batch) ---- */
  const handleBatchAutoImport = async () => {
    const asins = batchImportText
      .split(/[\n,;]+/)
      .map((a) => a.trim().toUpperCase())
      .filter(Boolean);
    if (asins.length === 0) {
      toast.error("请输入至少一个ASIN");
      return;
    }
    if (asins.length > 20) {
      toast.error("单次最多支持20个ASIN");
      return;
    }
    setBatchImportLoading(true);
    setAutoImportProgress(3);
    setAutoImportElapsed(0);
    setAutoImportMessage("准备批量抓取分析，单个 ASIN 通常约 60 秒");
    let savedCount = 0;
    const failedAsins: string[] = [];
    try {
      for (const asin of asins) {
        const currentIndex = savedCount + failedAsins.length + 1;
        setBatchImportCurrent(asin);
        setAutoImportMessage(`正在分析 ${asin}（${currentIndex}/${asins.length}）`);
        setAutoImportProgress(Math.max(5, Math.round(((currentIndex - 1) / asins.length) * 100)));
        try {
          const result = await smartFetchAsin(asin, autoImportMarketplace);
          if (result.status === "success" && result.data) {
            const importedAsin = result.data.asin || asin;
            const productData = {
              asin: importedAsin,
              title: result.data.title || asin,
              bullet_points: result.data.bullet_points || "",
              a_plus_content: result.data.a_plus_content || "",
              search_keywords: result.data.search_keywords || "",
              price: result.data.price || 0,
              review_count: result.data.review_count || 0,
              rating: result.data.rating || 0,
              category: result.data.category || "",
            };
            try {
              await saveProductToLibrary(productData);
              setAsinMarketplaceMap((prev) => ({
                ...prev,
                [importedAsin]: autoImportMarketplace,
              }));
              saveActionSnapshot({
                module_key: "asin_selection",
                module_name: "6维选品",
                action_key: "batch_fetch_asin_product",
                action_name: "批量ASIN抓取并保存",
                asin,
                title: result.data.title || asin,
                input_snapshot: { asin, marketplace: autoImportMarketplace },
                output_snapshot: { ...productData, marketplace: autoImportMarketplace },
                data_source: result.source || "",
                confidence: result.source === "浏览器代理" ? "high" : "low",
                ai_called: result.source !== "浏览器代理",
                source_record_table: "products",
              }).catch(() => {});
              savedCount++;
            } catch {
              /* skip duplicates */
            }
          } else {
            failedAsins.push(asin);
          }
        } catch {
          failedAsins.push(asin);
        }
      }
      toast.success(`批量导入完成：已保存 ${savedCount}/${asins.length} 个产品`);
      if (failedAsins.length > 0) {
        toast.error(`失败的ASIN: ${failedAsins.join(", ")}`);
      }
      setBatchImportText("");
      await loadProducts();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "批量导入失败");
    } finally {
      setBatchImportLoading(false);
      setBatchImportCurrent("");
      setAutoImportProgress(0);
      setAutoImportElapsed(0);
      setAutoImportMessage("");
    }
  };

  /* ---- Refresh single product data ---- */
  const handleRefreshProduct = async (product: Product) => {
    const marketplace = getProductMarketplace(product);
    setRefreshingId(product.id);
    try {
      const result = await smartFetchAsin(product.asin, marketplace);
      if (result.status === "success" && result.data) {
        await client.entities.products.update({
          id: String(product.id),
          data: {
            title: result.data.title || product.title,
            bullet_points: result.data.bullet_points || product.bullet_points,
            a_plus_content: result.data.a_plus_content || product.a_plus_content,
            search_keywords: result.data.search_keywords || product.search_keywords,
            price: result.data.price || product.price,
            review_count: result.data.review_count || product.review_count,
            rating: result.data.rating || product.rating,
            category: result.data.category || product.category,
          },
        });
        const sourceLabel =
          result.source === "浏览器代理" ? "浏览器代理" : "AI分析";
        saveActionSnapshot({
          module_key: "asin_selection",
          module_name: "6维选品",
          action_key: "refresh_asin_product",
          action_name: "刷新ASIN产品数据",
          product_id: product.id,
          asin: product.asin,
          title: result.data.title || product.title,
          input_snapshot: { ...product, marketplace },
          output_snapshot: { ...result.data, marketplace },
          data_source: sourceLabel,
          confidence: result.source === "浏览器代理" ? "high" : "low",
          ai_called: result.source !== "浏览器代理",
          source_record_table: "products",
          source_record_id: product.id,
        }).catch(() => {});
        setAsinMarketplaceMap((prev) => ({ ...prev, [product.asin]: marketplace }));
        toast.success(`${product.asin} 数据已通过${sourceLabel}刷新`);
        await loadProducts();
      } else {
        toast.error(result.error || "刷新失败");
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "刷新失败");
    } finally {
      setRefreshingId(null);
    }
  };

  /* ---- Fetch History ---- */
  const loadFetchHistory = async () => {
    setHistoryLoading(true);
    try {
      const items = await getActionSnapshots({ module_key: "asin_selection", limit: 30 });
      setFetchHistoryItems(items || []);
    } catch {
      /* ignore */
    } finally {
      setHistoryLoading(false);
    }
  };

  const toggleHistory = () => {
    if (!showHistory) loadFetchHistory();
    setShowHistory(!showHistory);
  };

  return (
    <div className="flex h-screen bg-white text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="p-4 sm:p-6 max-w-5xl mx-auto pt-14 md:pt-6">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 sm:mb-8 gap-3">
            <div>
              <h1 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
                <Package className="w-6 h-6 text-brand-600" />
                ASIN库
              </h1>
              <p className="text-gray-500 mt-1 text-sm">
                集中管理你的Amazon产品 · 按总分、风险和一票否决规则分流机会池 · 各诊断工具可直接引用
              </p>
            </div>
          </div>

          <PageHeader
            objective="集中管理你的Amazon产品ASIN，用6维规则引擎判断能不能做、风险在哪里、下一步去哪"
            inputSource="单个ASIN抓取 / 批量ASIN抓取"
            process="真实数据先打底，规则引擎评分，AI只做语义修正，风险规则优先否决"
            outputTarget="决策结论 · 机会池状态 · 一票否决 · 动态下一步动作"
            action="按可进入、小预算测试、改良后进入、淘汰避坑等路径分流"
            feedback="上线后的广告验证和复盘结果回流到下一轮选品判断"
            tone="blue"
          />

          {/* Tabs: ASIN库 / ASIN机会池 */}
          <div className="flex gap-1 mb-4 bg-gray-50 rounded-lg p-1 w-fit">
            <button
              onClick={() => setActiveTab("library")}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all flex items-center gap-1.5 ${
                activeTab === "library"
                  ? "bg-white text-red-600 shadow-sm"
                  : "text-red-400 hover:text-red-600 hover:bg-gray-100"
              }`}
            >
              <Package className="w-3.5 h-3.5" />
              全部ASIN
              <span className="text-[10px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded-full ml-0.5">
                {libraryCount}
              </span>
            </button>
            <button
              onClick={() => setActiveTab("pool")}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all flex items-center gap-1.5 ${
                activeTab === "pool"
                  ? "bg-white text-green-600 shadow-sm"
                  : "text-green-400 hover:text-green-600 hover:bg-gray-100"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              ASIN机会池
              <span className="text-[10px] bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full ml-0.5">
                {poolCount}
              </span>
            </button>
          </div>

          {/* Auto Import Panel */}
          {showAutoImport && !showForm && (
            <Card className="bg-white border-amber-500/20 p-4 sm:p-6 mb-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold flex items-center gap-2">
                  <CloudDownload className="w-5 h-5 text-amber-600" />
                  自动抓取Amazon产品数据
                </h2>
              </div>

              {/* Import mode tabs */}
              <div className="flex gap-1 mb-4 bg-gray-50 rounded-lg p-1 w-fit">
                <button
                  onClick={() => setImportMode("single")}
                  className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                    importMode === "single"
                      ? "bg-amber-600/80 text-gray-900"
                      : "text-gray-500 hover:text-gray-900 hover:bg-gray-100"
                  }`}
                >
                  单个ASIN抓取
                </button>
                <button
                  onClick={() => setImportMode("batch")}
                  className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                    importMode === "batch"
                      ? "bg-amber-600/80 text-gray-900"
                      : "text-gray-500 hover:text-gray-900 hover:bg-gray-100"
                  }`}
                >
                  批量ASIN抓取
                </button>
              </div>

              {/* Marketplace selector + Auto-fetch toggle */}
              <div className="flex items-end gap-4 mb-4">
                <div>
                  <Label className="text-gray-500 text-sm">站点</Label>
                  <Select
                    value={autoImportMarketplace}
                    onValueChange={setAutoImportMarketplace}
                  >
                    <SelectTrigger className="mt-1 bg-gray-50 border-gray-200 text-gray-900 w-[200px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-white border-gray-200">
                      {MARKETPLACE_OPTIONS.map((m) => (
                        <SelectItem
                          key={m.value}
                          value={m.value}
                          className="text-gray-900 hover:bg-brand-50"
                        >
                          {m.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {importMode === "single" && (
                  <label className="flex items-center gap-2 cursor-pointer pb-2">
                    <input
                      type="checkbox"
                      checked={autoFetch}
                      onChange={(e) => setAutoFetch(e.target.checked)}
                      className="w-4 h-4 rounded border-gray-200 bg-gray-50 text-amber-500 focus:ring-amber-500"
                    />
                    <span className="text-sm text-gray-500">
                      自动保存到ASIN库
                    </span>
                  </label>
                )}
              </div>

              {importMode === "single" ? (
                <div className="space-y-3">
                <div className="flex gap-3 items-end">
                  <div className="flex-1">
                    <Label className="text-gray-500 text-sm">ASIN</Label>
                    <Input
                      value={autoImportAsin}
                      onChange={(e) => setAutoImportAsin(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !autoImportLoading)
                          handleSingleAutoImport();
                      }}
                      placeholder="输入ASIN，如 B0XXXXXXXXX"
                      className="mt-1 bg-gray-50 border-gray-200 text-gray-900"
                    />
                  </div>
                  <Button
                    onClick={handleSingleAutoImport}
                    disabled={autoImportLoading || !autoImportAsin.trim()}
                    className="bg-amber-600 hover:bg-amber-500 text-white"
                  >
                    {autoImportLoading ? (
                      <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                    ) : (
                      <CloudDownload className="w-4 h-4 mr-1" />
                    )}
                    {autoImportLoading
                      ? "正在抓取真实数据..."
                      : "开始抓取真实数据"}
                  </Button>
                </div>
                <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-3 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-emerald-800 flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4" />
                      关键词销量验证
                    </p>
                    <p className="text-xs text-gray-600 mt-1">
                      抓取成功后自动保存到 ASIN 库，并交叉验证 BSR、评论、自然排名、广告位与促销信号。
                    </p>
                  </div>
                  <Button
                    onClick={handleSingleAutoImportAndValidate}
                    disabled={autoImportLoading || !autoImportAsin.trim()}
                    className="bg-emerald-700 hover:bg-emerald-600 text-white shrink-0"
                  >
                    {autoImportLoading ? (
                      <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                    ) : (
                      <ShieldCheck className="w-4 h-4 mr-1" />
                    )}
                    抓取保存并验证
                  </Button>
                </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div>
                    <Label className="text-gray-500 text-sm">
                      批量ASIN（每行一个，或用逗号分隔，最多20个）
                    </Label>
                    <Textarea
                      value={batchImportText}
                      onChange={(e) => setBatchImportText(e.target.value)}
                      placeholder={"B0XXXXXXXXX\nB0YYYYYYYYY\nB0ZZZZZZZZZ"}
                      rows={5}
                      className="mt-1 bg-gray-50 border-gray-200 text-gray-900 font-mono text-xs resize-none"
                    />
                  </div>
                  <Button
                    onClick={handleBatchAutoImport}
                    disabled={batchImportLoading || !batchImportText.trim()}
                    className="bg-amber-600 hover:bg-amber-500 text-white"
                  >
                    {batchImportLoading ? (
                      <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                    ) : (
                      <CloudDownload className="w-4 h-4 mr-1" />
                    )}
                    {batchImportLoading
                      ? "正在批量抓取真实数据..."
                      : `开始批量抓取真实数据 (${batchImportText.split(/[\n,;]+/).filter((a) => a.trim()).length} 个)`}
                  </Button>
                </div>
              )}

              {(autoImportLoading || batchImportLoading) && (
                <div className="mt-4 rounded-lg border border-amber-100 bg-amber-50 px-3 py-3">
                  <div className="flex items-center justify-between gap-3 text-xs text-amber-700">
                    <span className="flex items-center gap-1.5">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      {autoImportMessage || "正在抓取并分析 ASIN 数据"}
                      {batchImportCurrent ? ` · 当前 ${batchImportCurrent}` : ""}
                    </span>
                    <span className="shrink-0">{autoImportElapsed}s / 60s</span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-white">
                    <div
                      className="h-full rounded-full bg-amber-600 transition-all duration-500"
                      style={{ width: `${autoImportProgress}%` }}
                    />
                  </div>
                  <p className="mt-2 text-[11px] text-gray-600">
                    抓取链路按本地浏览器代理、服务器补充抓取、AI 低置信度兜底依次尝试；低置信度结果会保留来源标记，建议核实关键字段。
                  </p>
                </div>
              )}

              <p className="text-[10px] text-gray-600 mt-3">
                三阶段智能抓取：① 本地浏览器代理抓取Amazon页面 → ② 服务器补充抓取 → ③ AI低置信度兜底。
              </p>
            </Card>
          )}

          {/* Form */}
          {showForm && (
            <Card className="bg-white border-gray-200 p-4 sm:p-6 mb-6 sm:mb-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold">
                  {editingId ? "编辑产品" : "添加新产品"}
                </h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCancel}
                  className="text-gray-500 hover:text-gray-900"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label className="text-gray-600">ASIN *</Label>
                  <Input
                    value={form.asin}
                    onChange={(e) => setForm({ ...form, asin: e.target.value })}
                    placeholder="B0XXXXXXXXX"
                    className="bg-gray-50 border-gray-200 text-gray-900 mt-1"
                  />
                </div>
                <div>
                  <Label className="text-gray-600">类目</Label>
                  <Input
                    value={form.category}
                    onChange={(e) =>
                      setForm({ ...form, category: e.target.value })
                    }
                    placeholder="如：Electronics"
                    className="bg-gray-50 border-gray-200 text-gray-900 mt-1"
                  />
                </div>
                <div className="md:col-span-2">
                  <Label className="text-gray-600">产品标题 *</Label>
                  <Input
                    value={form.title}
                    onChange={(e) =>
                      setForm({ ...form, title: e.target.value })
                    }
                    placeholder="输入产品标题"
                    className="bg-gray-50 border-gray-200 text-gray-900 mt-1"
                  />
                </div>
                <div className="md:col-span-2">
                  <Label className="text-gray-600">五点描述 (Bullet Points)</Label>
                  <Textarea
                    value={form.bullet_points}
                    onChange={(e) =>
                      setForm({ ...form, bullet_points: e.target.value })
                    }
                    placeholder="每行一个卖点"
                    rows={4}
                    className="bg-gray-50 border-gray-200 text-gray-900 mt-1"
                  />
                </div>
                <div className="md:col-span-2">
                  <Label className="text-gray-600">A+ 内容描述</Label>
                  <Textarea
                    value={form.a_plus_content}
                    onChange={(e) =>
                      setForm({ ...form, a_plus_content: e.target.value })
                    }
                    placeholder="描述A+页面内容"
                    rows={3}
                    className="bg-gray-50 border-gray-200 text-gray-900 mt-1"
                  />
                </div>
                <div className="md:col-span-2">
                  <Label className="text-gray-600">搜索关键词</Label>
                  <Textarea
                    value={form.search_keywords}
                    onChange={(e) =>
                      setForm({ ...form, search_keywords: e.target.value })
                    }
                    placeholder="关键词用逗号分隔"
                    rows={2}
                    className="bg-gray-50 border-gray-200 text-gray-900 mt-1"
                  />
                </div>
                <div>
                  <Label className="text-gray-600">价格 (USD)</Label>
                  <Input
                    type="number"
                    value={form.price}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        price: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="bg-gray-50 border-gray-200 text-gray-900 mt-1"
                  />
                </div>
                <div>
                  <Label className="text-gray-600">评价数量</Label>
                  <Input
                    type="number"
                    value={form.review_count}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        review_count: parseInt(e.target.value) || 0,
                      })
                    }
                    className="bg-gray-50 border-gray-200 text-gray-900 mt-1"
                  />
                </div>
                <div>
                  <Label className="text-gray-600">评分 (1-5)</Label>
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    max="5"
                    value={form.rating}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        rating: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="bg-gray-50 border-gray-200 text-gray-900 mt-1"
                  />
                </div>
              </div>
              <div className="flex gap-3 mt-6">
                <Button
                  onClick={handleSubmit}
                  disabled={saving}
                  className="bg-brand-600 hover:bg-brand-500 text-white"
                >
                  <Save className="w-4 h-4 mr-1" />{" "}
                  {saving
                    ? "保存中..."
                    : editingId
                      ? "更新产品"
                      : "添加到ASIN库"}
                </Button>
                <Button
                  variant="ghost"
                  onClick={handleCancel}
                  className="text-gray-500 hover:text-gray-900"
                >
                  取消
                </Button>
              </div>
            </Card>
          )}

          {/* Search, Batch Actions, History Toggle */}
          {!showForm && products.length > 0 && (
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 mb-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="搜索 ASIN、标题或类目..."
                  className="bg-gray-50 border-gray-200 text-gray-900 pl-10"
                />
              </div>
              <div className="flex gap-2">
                {selectedIds.size > 0 && (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleBatchDelete}
                    disabled={deleting}
                    className="bg-red-600 hover:bg-red-500 text-white"
                  >
                    <Trash2 className="w-4 h-4 mr-1" />{" "}
                    {deleting
                      ? "删除中..."
                      : `删除选中 (${selectedIds.size})`}
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={toggleHistory}
                  className="border-gray-200 text-gray-600 hover:text-gray-900 hover:bg-gray-100 bg-transparent"
                >
                  <History className="w-4 h-4 mr-1" /> 抓取历史
                  {showHistory ? (
                    <ChevronUp className="w-3 h-3 ml-1" />
                  ) : (
                    <ChevronDown className="w-3 h-3 ml-1" />
                  )}
                </Button>
              </div>
            </div>
          )}

          {/* Fetch History */}
          {showHistory && (
            <Card className="bg-white border-gray-200 p-4 mb-4">
              <h3 className="text-sm font-semibold text-gray-600 mb-3 flex items-center gap-2">
                <History className="w-4 h-4 text-gray-500" /> 最近抓取记录
              </h3>
              {historyLoading ? (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="w-4 h-4 animate-spin text-gray-500" />
                </div>
              ) : fetchHistoryItems.length === 0 ? (
                <p className="text-xs text-gray-600 text-center py-4">
                  暂无抓取记录
                </p>
              ) : (
                <div className="space-y-1.5 max-h-60 overflow-y-auto">
                  {fetchHistoryItems.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-50 border border-gray-100 text-xs"
                    >
                      <div className="flex items-center gap-3">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                        <span className="font-mono text-brand-600">
                          {item.asin}
                        </span>
                        <span className="text-gray-600">
                          {item.action_name}
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-gray-600 max-w-[200px] truncate">
                          {item.data_source || item.module_name}
                        </span>
                        <span className="text-gray-600">
                          {new Date(item.created_at).toLocaleString("zh-CN", {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* Stats bar */}
          {!showForm && products.length > 0 && (
            <div className="flex items-center gap-4 mb-4 px-2">
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <Package className="w-3.5 h-3.5" />
                <span>共 {products.length} 个产品</span>
              </div>
              {poolCount > 0 && (
                <div className="flex items-center gap-1.5 text-xs text-emerald-600">
                  <Award className="w-3.5 h-3.5" />
                  <span>{poolCount} 个在机会池</span>
                </div>
              )}
              {searchQuery && (
                <div className="text-xs text-gray-500">
                  匹配 {filteredProducts.length} 个
                </div>
              )}
            </div>
          )}

          {/* Product List */}
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-20 bg-gray-50 rounded-xl animate-pulse"
                />
              ))}
            </div>
          ) : products.length === 0 && !showForm ? (
            <Card className="bg-white border-gray-200 p-8 sm:p-12 text-center">
              <Package className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-600 mb-2">
                ASIN库为空
              </h3>
              <p className="text-gray-500 mb-6 text-sm">
                请在上方输入 ASIN 或 Amazon 商品链接，系统会自动抓取并保存到 ASIN 库。
              </p>
            </Card>
          ) : filteredProducts.length === 0 ? (
            <Card className="bg-white border-gray-200 p-8 text-center">
              {activeTab === "pool" ? (
                <>
                  <Sparkles className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                  <h3 className="text-base font-semibold text-gray-600 mb-1">
                    机会池暂无产品
                  </h3>
                  <p className="text-gray-500 text-sm mb-4">
                    对ASIN库中的产品进行6维决策，只有总分、风险和一票否决同时达标才会进入机会池
                  </p>
                  <Button
                    variant="outline"
                    onClick={() => setActiveTab("library")}
                    className="border-gray-200 text-gray-600 bg-transparent"
                  >
                    返回ASIN库
                  </Button>
                </>
              ) : (
                <div className="text-center py-4 text-gray-500 text-sm">
                  没有找到匹配的产品
                </div>
              )}
            </Card>
          ) : (
            <div className="space-y-2 sm:space-y-3">
              {filteredProducts.length > 0 && (
                <div className="flex items-center gap-2 px-2 text-xs text-gray-500">
                  <Checkbox
                    checked={
                      selectedIds.size === filteredProducts.length &&
                      filteredProducts.length > 0
                    }
                    onCheckedChange={toggleSelectAll}
                    className="border-gray-200"
                  />
                  <span>全选 ({filteredProducts.length})</span>
                </div>
              )}
              {filteredProducts.map((product) => {
                const scoreResult = scoreResults[product.asin];
                const isScoring = scoringAsin === product.asin;
                const isExpanded = expandedScoreAsin === product.asin;
                const keywordReport = keywordValidationResults[product.asin];
                const isKeywordValidating = validatingKeywordAsin === product.asin;
                const isKeywordExpanded = expandedKeywordAsin === product.asin;
                const marketplace = getProductMarketplace(product);
                const marketplaceMeta = MARKETPLACE_BY_VALUE[marketplace] || MARKETPLACE_BY_VALUE.US;

                return (
                  <div key={product.id} className="space-y-0">
                    <Card
                      className="bg-white border-gray-200 p-3 sm:p-4 hover:border-gray-300 transition-colors"
                    >
                      <div className="flex items-start gap-3 sm:gap-4">
                        <Checkbox
                          checked={selectedIds.has(product.id)}
                          onCheckedChange={() => toggleSelect(product.id)}
                          className="border-gray-200 mt-2"
                        />
                        <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-lg bg-brand-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                          <Package className="w-4 h-4 sm:w-5 sm:h-5 text-brand-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className="text-xs font-mono text-brand-600 bg-brand-50 px-2 py-0.5 rounded">
                              {product.asin}
                            </span>
                            {product.category && (
                              <span className="text-xs text-gray-500">
                                {product.category}
                              </span>
                            )}
                            <a
                              href={getAmazonProductUrl(product.asin, marketplace)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-gray-600 hover:text-brand-600 transition-colors"
                              title={`在 ${marketplaceMeta.label} 查看：${marketplaceMeta.domain}`}
                            >
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                          <p className="font-medium text-sm truncate">
                            {product.title}
                          </p>
                          <div className="flex items-center gap-3 sm:gap-4 mt-2 text-xs text-gray-500 flex-wrap">
                            {product.price > 0 && (
                              <span className="text-emerald-600">
                                {marketplaceMeta.currency}
                                {product.price}
                              </span>
                            )}
                            {product.rating > 0 && (
                              <span className="flex items-center gap-1 text-amber-600">
                                <Star className="w-3 h-3" /> {product.rating}
                              </span>
                            )}
                            {product.review_count > 0 && (
                              <span>{product.review_count} 评价</span>
                            )}
                            {product.created_at && (
                              <span className="flex items-center gap-1 text-gray-600">
                                <Clock className="w-3 h-3" />
                                {new Date(product.created_at).toLocaleDateString(
                                  "zh-CN"
                                )}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex gap-1 sm:gap-2 flex-shrink-0 items-center">
                          {/* 6D Score Button */}
                          <FiveDScoreButton
                            loading={isScoring}
                            score={scoreResult?.total_score}
                            onClick={() => {
                              if (scoreResult) {
                                setExpandedScoreAsin(isExpanded ? null : product.asin);
                              } else {
                                handleFiveDScore(product);
                              }
                            }}
                          />
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              if (keywordReport) {
                                setExpandedKeywordAsin(isKeywordExpanded ? null : product.asin);
                              } else {
                                handleKeywordSalesValidation(product);
                              }
                            }}
                            disabled={isKeywordValidating}
                            className="text-gray-500 hover:text-emerald-700 h-8 px-2"
                            title="关键词销量验证"
                          >
                            {isKeywordValidating ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <ShieldCheck className="w-4 h-4" />
                            )}
                            {keywordReport && (
                              <span className="ml-1 text-xs font-semibold">{Math.round(keywordReport.keyword_sales_score)}</span>
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRefreshProduct(product)}
                            disabled={refreshingId === product.id}
                            className="text-gray-500 hover:text-amber-600 h-8 w-8 p-0"
                            title="刷新数据"
                          >
                            {refreshingId === product.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <RefreshCw className="w-4 h-4" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEdit(product)}
                            className="text-gray-500 hover:text-brand-600 h-8 w-8 p-0"
                            title="编辑"
                          >
                            <Pencil className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(product.id)}
                            className="text-gray-500 hover:text-red-600 h-8 w-8 p-0"
                            title="删除"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    </Card>

                    {/* Expanded 6D Score Card */}
                    {isExpanded && scoreResult && (
                      <div className="ml-12 mt-1 mb-2">
                        <FiveDimensionScoreCard result={scoreResult} />
                        {/* Re-score button */}
                        <div className="mt-2 flex justify-end">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleFiveDScore(product)}
                            disabled={isScoring}
                            className="text-xs text-gray-500 hover:text-brand-600"
                          >
                            {isScoring ? (
                              <Loader2 className="w-3 h-3 animate-spin mr-1" />
                            ) : (
                              <RefreshCw className="w-3 h-3 mr-1" />
                            )}
                            重新评分
                          </Button>
                        </div>
                      </div>
                    )}

                    {isKeywordExpanded && keywordReport && (
                      <div className="ml-12 mt-1 mb-2">
                        <Card className="bg-white border-emerald-100 p-4">
                          <div className="flex items-start justify-between gap-3 mb-4">
                            <div>
                              <div className="flex items-center gap-2">
                                <ShieldCheck className="w-4 h-4 text-emerald-700" />
                                <h3 className="font-bold text-gray-900">关键词销量验证</h3>
                              </div>
                              <p className="text-xs text-gray-500 mt-1">销量来源风险雷达：交叉查看 BSR、评论、自然排名、广告位与促销信号。</p>
                            </div>
                            <div className="text-right">
                              <div className="text-2xl font-bold text-emerald-700">{Math.round(keywordReport.keyword_sales_score)}</div>
                              <div className="text-xs text-gray-500">健康分</div>
                            </div>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                            <div className="rounded-lg bg-emerald-50 border border-emerald-100 p-3">
                              <p className="text-xs text-gray-500">自然流量强度</p>
                              <p className="text-lg font-bold text-emerald-700">{keywordReport.organic_rank_strength}</p>
                            </div>
                            <div className="rounded-lg bg-amber-50 border border-amber-100 p-3">
                              <p className="text-xs text-gray-500">广告依赖风险</p>
                              <p className="text-lg font-bold text-amber-700">{keywordReport.ad_dependency_risk}</p>
                            </div>
                            <div className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                              <p className="text-xs text-gray-500">系统判断</p>
                              <p className="text-sm font-semibold text-gray-800">{keywordReport.sales_source_judgment}</p>
                            </div>
                          </div>

                          <div className="rounded-lg border border-gray-100 overflow-hidden mb-4">
                            <div className="grid grid-cols-5 bg-gray-50 text-xs font-semibold text-gray-500 px-3 py-2">
                              <span className="col-span-2">关键词</span>
                              <span>自然位</span>
                              <span>广告位</span>
                              <span>页码</span>
                            </div>
                            {keywordReport.rank_snapshots.slice(0, 8).map((row) => (
                              <div key={row.keyword} className="grid grid-cols-5 px-3 py-2 text-xs border-t border-gray-100">
                                <span className="col-span-2 font-medium text-gray-700">{row.keyword}</span>
                                <span className={row.organic_position ? "text-emerald-700" : "text-gray-400"}>{row.organic_position || "未进前48"}</span>
                                <span className={row.sponsored_position ? "text-amber-700" : "text-gray-400"}>{row.sponsored_position || "-"}</span>
                                <span className="text-gray-500">{row.search_page || "-"}</span>
                              </div>
                            ))}
                          </div>

                          {keywordReport.suspicious_signals.length > 0 && (
                            <div className="rounded-lg bg-red-50 border border-red-100 p-3 mb-3">
                              <div className="flex items-center gap-2 text-sm font-semibold text-red-700 mb-2">
                                <AlertTriangle className="w-4 h-4" />
                                异常信号
                              </div>
                              <ul className="space-y-1 text-xs text-red-700">
                                {keywordReport.suspicious_signals.map((signal) => <li key={signal}>• {signal}</li>)}
                              </ul>
                            </div>
                          )}

                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                            <div>
                              <p className="font-semibold text-gray-700 mb-2">机会关键词</p>
                              <div className="flex flex-wrap gap-1.5">
                                {keywordReport.opportunity_keywords.map((kw) => <span key={kw} className="rounded bg-emerald-50 px-2 py-1 text-emerald-700">{kw}</span>)}
                              </div>
                            </div>
                            <div>
                              <p className="font-semibold text-gray-700 mb-2">风险关键词</p>
                              <div className="flex flex-wrap gap-1.5">
                                {keywordReport.risk_keywords.map((kw) => <span key={kw} className="rounded bg-amber-50 px-2 py-1 text-amber-700">{kw}</span>)}
                              </div>
                            </div>
                          </div>
                          <p className="text-xs text-gray-500 mt-3">{keywordReport.final_recommendation}</p>
                        </Card>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <NextStepActions
            actions={[
              { label: "进入上新检测", path: "/listing-launch-check", variant: "default" },
            ]}
          />
        </div>
      </main>
    </div>
  );
}
