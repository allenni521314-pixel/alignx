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
  Microscope,
} from "lucide-react";
import {
  FiveDimensionScoreCard,
  FiveDScoreButton,
  type FiveDScoreResult,
} from "@/components/FiveDimensionScore";
import { getActionSnapshots, saveActionSnapshot, type ActionSnapshot } from "@/lib/workflow-api";
import {
  finishModuleTask,
  removeModuleTask,
  upsertModuleTask,
} from "@/lib/module-task-store";

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

const productFetchSourceLabel = (source?: string) => {
  if (source === "server_proxy_fetch") return "服务器页面采集";
  if (source === "local_browser_capture") return "本地浏览器页面采集";
  if (source === "ai_estimated_low_confidence" || source === "低置信度补充分析") return "低置信度预检";
  if (source?.includes("scrape") || source === "scraped") return "服务器页面采集";
  return "商品信息提取";
};

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
    rank_data_source?: string;
    rank_data_note?: string;
    ad_risk_note?: string;
    ad_risk_level?: string;
    inventory_blocker?: boolean;
    inventory_note?: string;
    stock_status?: string;
    availability?: string;
  };
  organic_rank_strength: number;
  ad_dependency_risk: number;
  product_snapshot?: {
    availability?: string;
    stock_status?: string;
  };
  suspicious_signals: string[];
  opportunity_keywords: string[];
  risk_keywords: string[];
  final_recommendation: string;
  keyword_intent_scores?: Array<Record<string, unknown>>;
  market_validation_assist?: {
    entry_strategy?: string;
    six_dimension_calibration?: Array<{
      dimension: string;
      signal: string;
      impact: string;
      reason: string;
    }>;
    validation_actions?: string[];
    keyword_expansion?: string[];
    risk_followups?: string[];
  };
  rank_snapshots: Array<{
    keyword: string;
    search_page?: number;
    organic_position?: number | null;
    sponsored_position?: number | null;
    overall_position?: number | null;
    is_organic?: boolean;
    is_sponsored?: boolean;
    rank_type?: string;
  }>;
}

function normalizeKeywordSalesReport(report: KeywordSalesValidationReport): KeywordSalesValidationReport {
  const rankSnapshots = Array.isArray(report.rank_snapshots) ? report.rank_snapshots : [];
  const sponsoredCount = rankSnapshots.filter((row) => row?.is_sponsored).length;
  const rankSource = report.keyword_rank_summary?.rank_data_source || "";
  const hasRealSearchSnapshot =
    rankSource === "scrapling_top40_search" ||
    rankSnapshots.some((row) => String(row?.rank_type || "").startsWith("scrapling_top40"));

  if ((Number(report.ad_dependency_risk) || 0) > 0 || sponsoredCount > 0) {
    return report;
  }

  const organicStrength = Number(report.organic_rank_strength) || 0;
  const evidenceFloor = hasRealSearchSnapshot && organicStrength >= 75 ? 20 : hasRealSearchSnapshot ? 28 : 35;
  return {
    ...report,
    ad_dependency_risk: evidenceFloor,
    keyword_rank_summary: {
      ...(report.keyword_rank_summary || {}),
      ad_risk_level:
        evidenceFloor <= 20 ? "优秀自然流量结构" : evidenceFloor <= 35 ? "健康可控" : "需要观察",
      ad_risk_note:
        hasRealSearchSnapshot && organicStrength >= 75
          ? "未抓到Sponsored广告位时，系统按优秀卖家的低风险下限20%处理；这代表低广告依赖风险，不代表广告依赖为0。"
          : "当前广告位证据不足，系统不把缺失广告位当成0风险；建议用不同时段/账号复查Sponsored位置。",
    },
  };
}

interface ScraplingTop40Item {
  searchRank: number;
  asin: string;
  title?: string;
  price?: number | null;
  url?: string;
  priceText?: string;
  searchPrice?: number | null;
  searchPriceText?: string;
  detailPrice?: number | null;
  detailPriceText?: string;
  priceSource?: string;
  priceStatus?: string;
  rating?: number | null;
  reviewCount?: number | null;
  isSponsored?: boolean;
  status?: string;
  error?: string;
}

interface Top40AnalysisRow extends ScraplingTop40Item {
  segment?: "top20" | "mid20";
  priceBand?: string;
  priceBandLabel?: string;
  opportunityScore?: number;
  opportunityTag?: string;
  analysisReason?: string;
  aiTag?: string;
  aiReason?: string;
}

interface Top40MarketAnalysis {
  keyword: string;
  marketplace: string;
  status: string;
  analysisSource: "ai" | "rules";
  headline: string;
  executiveSummary: string[];
  marketOpportunity: string;
  entryStrategy: string[];
  riskWarnings: string[];
  summary: {
    totalListings: number;
    top20Count: number;
    mid20Count: number;
    medianPrice?: number | null;
    medianReviews?: number | null;
    sponsoredCount: number;
    sponsoredRatio: number;
    top20MedianReviews?: number | null;
    mid20LowReviewCount?: number;
  };
  priceBands: Array<{
    band: string;
    label: string;
    count: number;
    minPrice?: number | null;
    maxPrice?: number | null;
    medianReviews?: number | null;
    sponsoredCount: number;
    avgOpportunityScore: number;
    opportunityLevel: string;
  }>;
  recommendedPriceBand?: {
    label?: string;
    minPrice?: number | null;
    maxPrice?: number | null;
    avgOpportunityScore?: number;
  };
  tableRows: Top40AnalysisRow[];
  opportunityAsins: Top40AnalysisRow[];
}

interface ScraplingTop40BatchResult {
  marketplace: string;
  keyword: string;
  batchIndex: number;
  rankRange: string;
  capturedAt: string;
  status: "ok" | "partial" | "blocked" | "error";
  rules: string[];
  items: ScraplingTop40Item[];
  errors: string[];
  dataSource: string;
  analysisNote: string;
  usage?: Top40Usage;
}

interface Top40Usage {
  usedRuns: number;
  remainingRuns: number;
  dailyRunLimit: number;
  minIntervalHours: number;
  latestRunStartedAt?: string | null;
  nextAllowedAt?: string | null;
  windowHours: number;
}

interface AsinDiagnosisTaskResponse {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed" | string;
  result_payload?: Record<string, unknown>;
  error_message?: string;
}

const ASIN_DIAGNOSIS_TASK_KEY = "alignx_active_asin_diagnosis_task_id";
const ASIN_DIAGNOSIS_TASK_CONTEXT_KEY = "alignx_active_asin_diagnosis_task_context";
const ASIN_TASK_POLL_INTERVAL_MS = 2000;
const ASIN_TASK_TIMEOUT_MS = 60 * 1000;
const TOP40_TASK_TIMEOUT_SECONDS = 300;
const ASIN_TASK_TIMEOUT_MESSAGE = "ASIN抓取分析超过60秒，已停止等待。请稍后重试，或改用本地浏览器采集。";

interface AsinFetchProductData {
  asin: string;
  title: string;
  bullet_points: string;
  a_plus_content: string;
  search_keywords: string;
  price: number;
  review_count: number;
  rating: number;
  category: string;
}

interface AsinFetchResult {
  status: string;
  data?: AsinFetchProductData;
  error?: string;
  source?: string;
}

interface ActiveAsinTaskContext {
  taskId: string;
  moduleTaskId: string;
  asin: string;
  marketplace: string;
  intent: "single_import" | "single_import_validate" | "batch_import" | "refresh_product" | "background_fetch";
  autoFetch?: boolean;
  productId?: number;
  startedAt: string;
}

interface LocalBrowserCapture {
  html?: string;
  asin?: string;
  marketplace?: string;
  title?: string;
  price?: string;
  rating?: string;
  reviewCount?: string;
  bsrRank?: string;
  imageCount?: number;
  bullets?: string[];
  reviews?: Array<Record<string, unknown>>;
  destination?: string;
}

const asinModuleTaskId = (taskId: string) => `asin-diagnosis:${taskId}`;

const parseTaskStartedAt = (startedAt?: string) => {
  const time = startedAt ? new Date(startedAt).getTime() : 0;
  return Number.isFinite(time) && time > 0 ? time : Date.now();
};

const getAsinTaskAgeMs = (startedAt?: string) => Math.max(0, Date.now() - parseTaskStartedAt(startedAt));

const isAxiosTimeout = (error: unknown) =>
  axios.isAxiosError(error) && (error.code === "ECONNABORTED" || /timeout/i.test(error.message || ""));

const readActiveAsinTaskContext = (): ActiveAsinTaskContext | null => {
  try {
    const raw = localStorage.getItem(ASIN_DIAGNOSIS_TASK_CONTEXT_KEY);
    return raw ? (JSON.parse(raw) as ActiveAsinTaskContext) : null;
  } catch {
    localStorage.removeItem(ASIN_DIAGNOSIS_TASK_CONTEXT_KEY);
    return null;
  }
};

const clearActiveAsinTaskStorage = () => {
  localStorage.removeItem(ASIN_DIAGNOSIS_TASK_KEY);
  localStorage.removeItem(ASIN_DIAGNOSIS_TASK_CONTEXT_KEY);
};

const clearFailedAsinModuleTask = (moduleTaskId: string, message: string) => {
  finishModuleTask(moduleTaskId, "failed", message);
  clearActiveAsinTaskStorage();
  window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
};

const productDataFromAsinTaskPayload = (
  payload: Record<string, unknown>,
  fallbackAsin: string
): { source: string; data: AsinFetchProductData } => {
  const d = payload as Record<string, any>;
  const pd = d.product_data || {};
  const source = d.data_source || pd._data_source || "server_analysis";
  return {
    source,
    data: {
      asin: d.asin || fallbackAsin,
      title: pd.title || d.product_title || "",
      bullet_points: Array.isArray(pd.bullet_points) ? pd.bullet_points.join("\n") : pd.bullet_points || "",
      a_plus_content: pd.description_summary || "",
      search_keywords: Array.isArray(pd.main_keywords) ? pd.main_keywords.join(", ") : pd.main_keywords || "",
      price: parseFloat(String(pd.price).replace(/[^0-9.]/g, "")) || 0,
      review_count: parseInt(String(pd.review_count).replace(/[^0-9]/g, ""), 10) || 0,
      rating: parseFloat(String(pd.rating)) || 0,
      category: pd.category || "",
    },
  };
};

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
  const isLocalCaptureRoute = searchParams.get("localCapture") === "1";
  const localCaptureAsin = (searchParams.get("asin") || "").trim().toUpperCase();
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
  const [importMode, setImportMode] = useState<"single" | "top40">("single");
  const [autoFetch, setAutoFetch] = useState(true);
  const [scraplingKeyword, setScraplingKeyword] = useState("");
  const [scraplingBatchIndex, setScraplingBatchIndex] = useState(1);
  const [scraplingLoading, setScraplingLoading] = useState(false);
  const [scraplingResult, setScraplingResult] = useState<ScraplingTop40BatchResult | null>(null);
  const [scraplingResults, setScraplingResults] = useState<ScraplingTop40BatchResult[]>([]);
  const [top40Analyzing, setTop40Analyzing] = useState(false);
  const [top40Analysis, setTop40Analysis] = useState<Top40MarketAnalysis | null>(null);
  const [top40Usage, setTop40Usage] = useState<Top40Usage | null>(null);
  const [top40DeepDiveAsin, setTop40DeepDiveAsin] = useState<string | null>(null);
  const [pendingLocalCapture, setPendingLocalCapture] = useState<LocalBrowserCapture | null>(null);

  // Fetch history state
  const [showHistory, setShowHistory] = useState(false);
  const [fetchHistoryItems, setFetchHistoryItems] = useState<ActionSnapshot[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const isTop40Busy = scraplingLoading || top40Analyzing;

  useEffect(() => {
    if (!autoImportLoading && !batchImportLoading && !scraplingLoading && !top40Analyzing) return;
    const startedAt = Date.now();
    const targetSeconds = scraplingLoading || top40Analyzing
      ? TOP40_TASK_TIMEOUT_SECONDS
      : isLocalCaptureRoute
        ? 180
        : ASIN_TASK_TIMEOUT_MS / 1000;
    const timer = window.setInterval(() => {
      const elapsed = Math.min(targetSeconds, Math.floor((Date.now() - startedAt) / 1000));
      setAutoImportElapsed(elapsed);
      setAutoImportProgress((current) => Math.max(current, Math.min(92, Math.round((elapsed / targetSeconds) * 92))));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [autoImportLoading, batchImportLoading, scraplingLoading, top40Analyzing, isLocalCaptureRoute]);

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
  const [outOfStockAsins, setOutOfStockAsins] = useState<Record<string, boolean>>(() => {
    try {
      return JSON.parse(localStorage.getItem("alignx_out_of_stock_asins") || "{}");
    } catch {
      return {};
    }
  });

  const { loading: authLoading } = useRequireAuth();

  const getProductMarketplace = useCallback(
    (product: Product) =>
      product.marketplace ||
      asinMarketplaceMap[product.asin] ||
      "US",
    [asinMarketplaceMap]
  );

  const markOutOfStock = (asin: string, value: boolean) => {
    setOutOfStockAsins((prev) => {
      const next = { ...prev, [asin]: value };
      if (!value) delete next[asin];
      localStorage.setItem("alignx_out_of_stock_asins", JSON.stringify(next));
      return next;
    });
  };

  const top40AnalysisByAsin = useMemo(() => {
    const map: Record<string, Top40AnalysisRow> = {};
    for (const row of top40Analysis?.tableRows || []) {
      if (row.asin) map[row.asin] = row;
    }
    return map;
  }, [top40Analysis]);

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
        return latest ? [product.asin, normalizeKeywordSalesReport(latest)] as const : null;
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

  useEffect(() => {
    if (!expandedKeywordAsin) return;
    window.setTimeout(() => {
      document
        .getElementById(`keyword-validation-report-${expandedKeywordAsin}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 80);
  }, [expandedKeywordAsin, keywordValidationResults]);

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

  const loadTop40Usage = useCallback(async () => {
    try {
      const res = await axios.get(`${getLongRunningApiBase()}/api/v1/asin-selection/scrapling/top40-rules`, {
        headers: getAuthHeaders(),
        timeout: 15000,
      });
      if (res.data?.usage) setTop40Usage(res.data.usage as Top40Usage);
    } catch {
      // Usage only guides the UI; backend still enforces the limit.
    }
  }, []);

  useEffect(() => {
    if (!authLoading) loadTop40Usage();
  }, [authLoading, loadTop40Usage]);

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
    const keywordReport = keywordValidationResults[product.asin];
    const validationKeywords =
      keywordReport?.market_validation_assist?.keyword_expansion?.length
        ? keywordReport.market_validation_assist.keyword_expansion
        : keywordReport?.opportunity_keywords || [];
    const moduleTaskId = `asin-six-dimension:${product.asin}`;
    setScoringAsin(product.asin);
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "asin-manager",
      label: `机会评分 ${product.asin}`,
      status: "running",
      detail: "正在生成选品判断",
      path: "/asin-manager",
    });
    try {
      const res = await axios.post(
        `${getLongRunningApiBase()}/api/v1/asin-analysis/six-dimension-score`,
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
            main_keywords: validationKeywords.length ? validationKeywords : product.search_keywords,
            keyword_sales_validation: keywordReport,
            keyword_rank_snapshots: keywordReport?.rank_snapshots,
            keyword_intent_scores: keywordReport?.keyword_intent_scores,
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
          module_name: "ASIN机会判断",
          action_key: "six_dimension_score",
          action_name: "ASIN机会评分",
          product_id: product.id,
          asin: product.asin,
          title: product.title,
          input_snapshot: { ...product, marketplace, keyword_sales_validation: keywordReport },
          output_snapshot: result,
          data_source: "asin_library",
          confidence: result.confidence_level === "high" ? "high" : result.confidence_level === "medium" ? "medium" : "low",
          ai_called: result.ai_called !== false,
          source_record_table: "asin_analyses",
        }).catch(() => {});
        toast.success(`${product.asin} 机会判断完成: ${result.total_score}分`);
        finishModuleTask(moduleTaskId, "completed", "机会评分完成");
      } else {
        finishModuleTask(moduleTaskId, "failed", "评分失败");
        toast.error("评分失败，请重试");
      }
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? e.response?.data?.detail || "评分请求失败"
        : e instanceof Error
          ? e.message
          : "评分失败";
      finishModuleTask(moduleTaskId, "failed", msg);
      toast.error(msg);
    } finally {
      setScoringAsin(null);
      window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
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

  function readStoredLocalBrowserCapture() {
    const raw = localStorage.getItem("alignx_local_browser_capture");
    if (!raw) return null;
    try {
      const capture = JSON.parse(raw) as LocalBrowserCapture;
      if (capture.destination && capture.destination !== "asin") {
        localStorage.removeItem("alignx_local_browser_capture");
        return null;
      }
      if (!capture.html || !capture.asin) return null;
      return { ...capture, asin: capture.asin.trim().toUpperCase() };
    } catch {
      localStorage.removeItem("alignx_local_browser_capture");
      return null;
    }
  }

  function resolveLocalBrowserCapture() {
    const stored = readStoredLocalBrowserCapture();
    if (stored) return stored;
    if (pendingLocalCapture?.html && pendingLocalCapture.asin) {
      return { ...pendingLocalCapture, asin: pendingLocalCapture.asin.trim().toUpperCase() };
    }
    return null;
  }

  function requestPendingLocalCapture() {
    window.dispatchEvent(new Event("alignx-request-pending-capture"));
  }

  function showMissingLocalCaptureMessage() {
    requestPendingLocalCapture();
    toast.warning("未收到页面数据，请回到 Amazon 商品页重新点击发送。");
    setAutoImportMessage("等待页面数据");
  }

  async function processLocalBrowserCapture(capture: LocalBrowserCapture, options: { validate?: boolean } = {}) {
    if (!capture.html || !capture.asin) {
      showMissingLocalCaptureMessage();
      return null;
    }

    const asin = capture.asin.trim().toUpperCase();
    const mp = capture.marketplace || autoImportMarketplace || "US";
    const moduleTaskId = `asin-local-capture:${asin}`;
    localStorage.removeItem("alignx_local_browser_capture");
    setPendingLocalCapture({ ...capture, asin });
    setAutoImportAsin(asin);
    setAutoImportMarketplace(mp);
    setAutoImportLoading(true);
    setAutoImportElapsed(0);
    setAutoImportProgress(28);
    setAutoImportMessage("正在读取页面内容并保存到ASIN库");
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "asin-manager",
      label: `本地采集分析 ${asin}`,
      status: "running",
      detail: "正在读取当前Amazon页面并保存记录",
      path: "/asin-manager",
    });

    try {
      const res = await axios.post(
        `${getLongRunningApiBase()}/api/v1/asin-analysis/parse-html-analyze`,
        {
          asin,
          marketplace: mp,
          html: capture.html,
          source: "local_browser_capture",
          captured_title: capture.title || "",
          captured_price: capture.price || "",
          captured_rating: capture.rating || "",
          captured_review_count: capture.reviewCount || "",
          captured_bsr_rank: capture.bsrRank || "",
          captured_image_count: capture.imageCount ? String(capture.imageCount) : "",
          captured_bullets: capture.bullets || [],
          captured_reviews: capture.reviews || [],
        },
        { headers: getAuthHeaders(), timeout: 180000 }
      );
      const d = res.data;
      if (!d?.success || !d.product_data) {
        const msg = d?.error || "本地采集解析失败";
        finishModuleTask(moduleTaskId, "failed", msg);
        toast.error(msg);
        return null;
      }

      const pd = d.product_data || {};
      const productData: Omit<Product, "id" | "created_at" | "marketplace"> = {
        asin: d.asin || asin,
        title: pd.title || d.product_title || capture.title || asin,
        bullet_points: Array.isArray(pd.bullet_points) ? pd.bullet_points.join("\n") : pd.bullet_points || "",
        a_plus_content: pd.description_summary || pd.aplus_content || "",
        search_keywords: Array.isArray(pd.main_keywords) ? pd.main_keywords.join(", ") : pd.main_keywords || "",
        price: parseFloat(String(pd.price || capture.price || "").replace(/[^0-9.]/g, "")) || 0,
        review_count: parseInt(String(pd.review_count || capture.reviewCount || "").replace(/[^0-9]/g, ""), 10) || 0,
        rating: parseFloat(String(pd.rating || capture.rating || "")) || 0,
        category: pd.category || "",
      };

      setAutoImportProgress(options.validate ? 74 : 88);
      const saved = await saveProductToLibrary(productData);
      const savedProduct = { ...saved.product, marketplace: mp };
      setAsinMarketplaceMap((prev) => ({ ...prev, [productData.asin]: mp }));
      setProducts((prev) => {
        const existingIndex = prev.findIndex((product) => product.asin === productData.asin);
        if (existingIndex >= 0) {
          const next = [...prev];
          next[existingIndex] = savedProduct;
          return next;
        }
        return [savedProduct, ...prev];
      });

      const shouldStartValidation = Boolean(options.validate);
      setAutoImportMessage(
        shouldStartValidation
          ? "已保存到ASIN库，关键词验证会继续完成"
          : "已保存到ASIN库"
      );
      setAutoImportProgress(94);

      saveActionSnapshot({
        module_key: "asin_selection",
        module_name: "ASIN选品",
        action_key: shouldStartValidation ? "local_capture_save_start_keyword_validation" : "local_browser_capture_import",
        action_name: shouldStartValidation ? "本地页面保存并启动关键词验证" : "本地页面写入ASIN库",
        product_id: saved.product.id,
        asin: productData.asin,
        title: productData.title,
        input_snapshot: { asin, marketplace: mp, destination: capture.destination || "asin" },
        output_snapshot: { product: productData, marketplace: mp, capture_quality: pd.capture_quality, keyword_sales_validation: null },
        data_source: "本地浏览器页面采集",
        confidence: "high",
        ai_called: true,
        source_record_table: "products",
        source_record_id: saved.product.id,
      }).catch(() => {});

      setAutoImportProgress(100);
      setPendingLocalCapture(null);
      finishModuleTask(moduleTaskId, "completed", shouldStartValidation ? "已保存，关键词验证继续进行" : "本地采集写入完成");
      await loadProducts();
      toast.success(
        shouldStartValidation
          ? `${productData.asin} 已${saved.mode === "updated" ? "更新" : "保存"}，关键词验证正在继续`
          : `已用本地浏览器采集${saved.mode === "updated" ? "更新" : "保存"} ${productData.asin}`
      );
      if (shouldStartValidation) {
        startBackgroundKeywordValidation(productData, mp, saved.product.id);
      }
      return { productData, savedProduct, report: null };
    } catch (err) {
      const msg = axios.isAxiosError(err) ? err.response?.data?.detail || err.message : "本地采集分析失败";
      finishModuleTask(moduleTaskId, "failed", msg);
      toast.error(msg);
      return null;
    } finally {
      setAutoImportLoading(false);
      setAutoImportProgress(0);
      setAutoImportElapsed(0);
      setAutoImportMessage("");
      window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
    }
  }

  useEffect(() => {
    if (authLoading) return;
    const consumeLocalBrowserCapture = async () => {
      const capture = readStoredLocalBrowserCapture();
      if (!capture) {
        if (isLocalCaptureRoute) {
          if (localCaptureAsin) setAutoImportAsin(localCaptureAsin);
          requestPendingLocalCapture();
          setAutoImportMessage("等待页面数据");
        }
        return;
      }
      setPendingLocalCapture(capture);
      setAutoImportAsin(capture.asin || localCaptureAsin);
      setAutoImportMarketplace(capture.marketplace || autoImportMarketplace || "US");
      await processLocalBrowserCapture(capture, { validate: true });
    };

    consumeLocalBrowserCapture();
    const onCapture = () => {
      consumeLocalBrowserCapture();
    };
    window.addEventListener("alignx-local-browser-capture", onCapture);
    return () => window.removeEventListener("alignx-local-browser-capture", onCapture);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, isLocalCaptureRoute, localCaptureAsin]);

  const handleTop40DeepDive = async (item: ScraplingTop40Item) => {
    if (!item.asin) {
      toast.error("这条样本缺少ASIN，无法进入单品分析");
      return;
    }

    const marketplace = scraplingResult?.marketplace || autoImportMarketplace || "US";
    const productData: Omit<Product, "id" | "created_at" | "marketplace"> = {
      asin: item.asin,
      title: item.title || item.asin,
      bullet_points: "",
      a_plus_content: "",
      search_keywords: scraplingKeyword.trim(),
      price: Number(item.detailPrice || item.searchPrice || item.price || 0),
      review_count: Number(item.reviewCount || 0),
      rating: Number(item.rating || 0),
      category: `${scraplingKeyword.trim() || "Top40样本"} · Rank ${item.searchRank}`,
    };

    setTop40DeepDiveAsin(item.asin);
    setAutoImportMessage(`正在对 ${item.asin} 做单品深挖`);
    try {
      const saved = await saveProductToLibrary(productData);
      const savedProduct = { ...saved.product, marketplace };
      setAsinMarketplaceMap((prev) => ({ ...prev, [item.asin]: marketplace }));
      setProducts((prev) => {
        const existingIndex = prev.findIndex((product) => product.asin === item.asin);
        if (existingIndex >= 0) {
          const next = [...prev];
          next[existingIndex] = savedProduct;
          return next;
        }
        return [savedProduct, ...prev];
      });
      saveActionSnapshot({
        module_key: "asin_selection",
        module_name: "ASIN选品",
        action_key: "top40_asin_deep_dive",
        action_name: "Top40样本单品深挖",
        product_id: savedProduct.id,
        asin: item.asin,
        title: savedProduct.title,
        input_snapshot: {
          keyword: scraplingKeyword.trim(),
          marketplace,
          searchRank: item.searchRank,
          asin: item.asin,
        },
        output_snapshot: {
          product: savedProduct,
          top40Item: item,
          libraryMode: saved.mode,
        },
        data_source: "top40_market_sample",
        confidence: "medium",
        ai_called: false,
        source_record_table: "products",
        source_record_id: savedProduct.id,
      }).catch(() => {});

      setShowForm(false);
      setActiveTab("library");
      setSearchQuery(item.asin);
      toast.success(`${item.asin} 已进入ASIN库，开始单品评分`);
      await handleFiveDScore(savedProduct);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "单品深挖失败";
      toast.error(msg);
    } finally {
      setTop40DeepDiveAsin(null);
    }
  };

  const handleKeywordSalesValidation = async (product: Product) => {
    const marketplace = getProductMarketplace(product);
    const moduleTaskId = `asin-keyword-validation:${product.asin}`;
    setValidatingKeywordAsin(product.asin);
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "asin-manager",
      label: `关键词销量验证 ${product.asin}`,
      status: "running",
      detail: "搜索快照校验自然位与广告位",
      path: "/asin-manager",
    });
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
          inventory_status: outOfStockAsins[product.asin] ? "out_of_stock" : "",
          is_own_product: Boolean(outOfStockAsins[product.asin]),
        },
        { headers: getAuthHeaders(), timeout: 180000 }
      );
      setKeywordValidationResults((prev) => ({ ...prev, [product.asin]: normalizeKeywordSalesReport(res.data) }));
      setExpandedKeywordAsin(product.asin);
      finishModuleTask(moduleTaskId, "completed", "关键词销量验证完成");
      toast.success(`${product.asin} 关键词销量验证完成：${Math.round(res.data.keyword_sales_score || 0)}分`);
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? e.response?.data?.detail || "关键词销量验证失败"
        : e instanceof Error
          ? e.message
          : "关键词销量验证失败";
      finishModuleTask(moduleTaskId, "failed", msg);
      toast.error(msg);
    } finally {
      setValidatingKeywordAsin(null);
      window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
    }
  };

  const validateImportedProduct = async (
    productData: Omit<Product, "id" | "created_at" | "marketplace">,
    marketplace: string,
    timeoutMs = 180000
  ) => {
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
        inventory_status: outOfStockAsins[productData.asin] ? "out_of_stock" : "",
        is_own_product: Boolean(outOfStockAsins[productData.asin]),
      },
      { headers: getAuthHeaders(), timeout: timeoutMs }
    );
    const normalizedReport = normalizeKeywordSalesReport(res.data);
    setKeywordValidationResults((prev) => ({ ...prev, [productData.asin]: normalizedReport }));
    setExpandedKeywordAsin(productData.asin);
    return normalizedReport;
  };

  const startBackgroundKeywordValidation = (
    productData: Omit<Product, "id" | "created_at" | "marketplace">,
    marketplace: string,
    productId?: number
  ) => {
    const asin = productData.asin;
    setValidatingKeywordAsin(asin);
    validateImportedProduct(productData, marketplace, 120000)
      .then((report) => {
        saveActionSnapshot({
          module_key: "asin_selection",
          module_name: "ASIN选品",
          action_key: "keyword_sales_validation_after_local_capture",
          action_name: "本地页面保存后的关键词验证",
          product_id: productId,
          asin,
          title: productData.title,
          input_snapshot: { asin, marketplace, target_keywords: productData.search_keywords },
          output_snapshot: { keyword_sales_validation: report },
          data_source: "关键词搜索快照",
          confidence: report.keyword_sales_score >= 65 ? "medium" : "low",
          ai_called: true,
          source_record_table: "asin_keyword_sales_validation_reports",
          source_record_id: productId,
        }).catch(() => {});
        toast.success(`${asin} 关键词验证完成：${Math.round(report.keyword_sales_score || 0)}分`);
      })
      .catch(() => {
        toast.warning(`${asin} 关键词验证暂未完成，可稍后点击产品右侧重新验证`);
      })
      .finally(() => {
        setValidatingKeywordAsin((current) => (current === asin ? null : current));
      });
  };

  useEffect(() => {
    if (authLoading) return;
    if (isLocalCaptureRoute) {
      const taskId = localStorage.getItem(ASIN_DIAGNOSIS_TASK_KEY);
      const context = readActiveAsinTaskContext();
      if (taskId) removeModuleTask(context?.moduleTaskId || asinModuleTaskId(taskId));
      clearActiveAsinTaskStorage();
      return;
    }
    const taskId = localStorage.getItem(ASIN_DIAGNOSIS_TASK_KEY);
    if (!taskId) return;

    const storedContext = readActiveAsinTaskContext();
    const context: ActiveAsinTaskContext = storedContext?.taskId === taskId
      ? storedContext
      : {
          taskId,
          moduleTaskId: asinModuleTaskId(taskId),
          asin: autoImportAsin.trim().toUpperCase() || "ASIN",
          marketplace: autoImportMarketplace || "US",
          intent: "background_fetch",
          autoFetch: true,
          startedAt: new Date().toISOString(),
        };

    let cancelled = false;
    const apiBase = getLongRunningApiBase();
    const moduleTaskId = context.moduleTaskId || asinModuleTaskId(taskId);

    const recoverTask = async () => {
      if (getAsinTaskAgeMs(context.startedAt) >= ASIN_TASK_TIMEOUT_MS) {
        clearFailedAsinModuleTask(moduleTaskId, ASIN_TASK_TIMEOUT_MESSAGE);
        toast.error(ASIN_TASK_TIMEOUT_MESSAGE);
        return;
      }

      setAutoImportLoading(true);
      setAutoImportElapsed(0);
      setAutoImportProgress(20);
      setAutoImportMessage(`正在恢复 ${context.asin} 的分析任务`);
      upsertModuleTask({
        id: moduleTaskId,
        moduleKey: "asin-manager",
        label: `ASIN抓取分析 ${context.asin}`,
        status: "running",
        detail: "用户切换页面后继续恢复任务",
        path: "/asin-manager",
        startedAt: context.startedAt,
      });

      try {
        let task: AsinDiagnosisTaskResponse | null = null;
        while (getAsinTaskAgeMs(context.startedAt) < ASIN_TASK_TIMEOUT_MS) {
          if (cancelled) return;
          const remainingMs = ASIN_TASK_TIMEOUT_MS - getAsinTaskAgeMs(context.startedAt);
          try {
            const statusRes = await axios.get<AsinDiagnosisTaskResponse>(
              `${apiBase}/api/v1/diagnosis-tasks/${taskId}`,
              { headers: getAuthHeaders(), timeout: Math.max(3000, Math.min(10000, remainingMs)) }
            );
            task = statusRes.data;
          } catch (err) {
            if (isAxiosTimeout(err)) {
              await new Promise((resolve) => window.setTimeout(resolve, ASIN_TASK_POLL_INTERVAL_MS));
              continue;
            }
            throw err;
          }
          if (task.status === "completed") break;
          if (task.status === "failed") {
            throw new Error(task.error_message || "ASIN分析任务失败");
          }
          const elapsedRatio = Math.min(1, getAsinTaskAgeMs(context.startedAt) / ASIN_TASK_TIMEOUT_MS);
          setAutoImportProgress((current) => Math.min(92, Math.max(current, 20 + Math.round(elapsedRatio * 72))));
          await new Promise((resolve) => window.setTimeout(resolve, ASIN_TASK_POLL_INTERVAL_MS));
        }

        if (cancelled) return;
        if (!task || task.status !== "completed" || !task.result_payload) {
          clearFailedAsinModuleTask(moduleTaskId, ASIN_TASK_TIMEOUT_MESSAGE);
          toast.error(ASIN_TASK_TIMEOUT_MESSAGE);
          return;
        }

        const normalized = productDataFromAsinTaskPayload(task.result_payload, context.asin);
        const productData = normalized.data;
        const sourceLabel = productFetchSourceLabel(normalized.source);
        const isLowConfidence = sourceLabel === "低置信度预检";
        setAutoImportProgress(88);
        setAutoImportMessage(`已恢复 ${productData.asin} 抓取结果，正在写入ASIN库`);

        if (context.intent === "refresh_product" && context.productId) {
          await client.entities.products.update({
            id: String(context.productId),
            data: {
              title: productData.title,
              bullet_points: productData.bullet_points,
              a_plus_content: productData.a_plus_content,
              search_keywords: productData.search_keywords,
              price: productData.price,
              review_count: productData.review_count,
              rating: productData.rating,
              category: productData.category,
            },
          });
          setAsinMarketplaceMap((prev) => ({ ...prev, [productData.asin]: context.marketplace }));
          saveActionSnapshot({
            module_key: "asin_selection",
            module_name: "ASIN机会判断",
            action_key: "recover_refresh_asin_product",
            action_name: "恢复并刷新ASIN产品数据",
            product_id: context.productId,
            asin: productData.asin,
            title: productData.title,
            input_snapshot: context,
            output_snapshot: { ...productData, marketplace: context.marketplace },
            data_source: sourceLabel,
            confidence: isLowConfidence ? "low" : "high",
            ai_called: isLowConfidence,
            source_record_table: "products",
            source_record_id: context.productId,
          }).catch(() => {});
          toast.success(`${productData.asin} 刷新已完成`);
        } else {
          const saved = await saveProductToLibrary(productData);
          const savedProduct = { ...saved.product, marketplace: context.marketplace };
          setAsinMarketplaceMap((prev) => ({ ...prev, [productData.asin]: context.marketplace }));
          setProducts((prev) => {
            const index = prev.findIndex((product) => product.asin === productData.asin);
            if (index >= 0) {
              const next = [...prev];
              next[index] = savedProduct;
              return next;
            }
            return [savedProduct, ...prev];
          });
          saveActionSnapshot({
            module_key: "asin_selection",
            module_name: "ASIN机会判断",
            action_key: "recover_fetch_asin_product",
            action_name: "恢复ASIN抓取并保存",
            product_id: saved.product.id,
            asin: productData.asin,
            title: productData.title,
            input_snapshot: context,
            output_snapshot: { ...productData, marketplace: context.marketplace },
            data_source: sourceLabel,
            confidence: isLowConfidence ? "low" : "high",
            ai_called: isLowConfidence,
            source_record_table: "products",
            source_record_id: saved.product.id,
          }).catch(() => {});

          if (context.intent === "single_import_validate") {
            setAutoImportMessage("抓取已恢复，正在继续关键词销量验证");
            const report = await validateImportedProduct(productData, context.marketplace);
            saveActionSnapshot({
              module_key: "asin_selection",
              module_name: "关键词销量验证",
              action_key: "recover_keyword_sales_validation",
              action_name: "恢复抓取后继续关键词销量验证",
              product_id: saved.product.id,
              asin: productData.asin,
              title: productData.title,
              input_snapshot: context,
              output_snapshot: { product: productData, keyword_sales_validation: report },
              data_source: normalized.source,
              confidence: report.keyword_sales_score >= 65 ? "medium" : "low",
              ai_called: false,
              source_record_table: "asin_keyword_sales_validation_reports",
            }).catch(() => {});
          }
          toast.success(`${productData.asin} 抓取已${saved.mode === "updated" ? "更新" : "保存"}`);
        }

        setAutoImportProgress(100);
        await loadProducts();
        clearActiveAsinTaskStorage();
        finishModuleTask(moduleTaskId, "completed", "ASIN分析任务已恢复完成");
        window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
      } catch (e: unknown) {
        const msg = axios.isAxiosError(e)
          ? e.response?.data?.detail || e.message
          : e instanceof Error
            ? e.message
            : "ASIN分析任务恢复失败";
        if (!cancelled) {
          toast.error(msg);
          clearFailedAsinModuleTask(moduleTaskId, msg);
        }
      } finally {
        if (!cancelled) {
          setAutoImportLoading(false);
          setAutoImportProgress(0);
          setAutoImportElapsed(0);
          setAutoImportMessage("");
        }
      }
    };

    recoverTask();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading]);

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
    marketplace: string,
    context: Partial<Omit<ActiveAsinTaskContext, "taskId" | "moduleTaskId" | "asin" | "marketplace" | "startedAt">> = {}
  ): Promise<AsinFetchResult> => {
    const apiBase = getLongRunningApiBase();
    const taskRes = await axios.post<AsinDiagnosisTaskResponse>(
      `${apiBase}/api/v1/diagnosis-tasks/asin`,
      { asin, marketplace },
      { headers: getAuthHeaders(), timeout: 30000 }
    );
    const moduleTaskId = asinModuleTaskId(taskRes.data.task_id);
    const taskContext: ActiveAsinTaskContext = {
      taskId: taskRes.data.task_id,
      moduleTaskId,
      asin,
      marketplace,
      intent: context.intent || "background_fetch",
      autoFetch: context.autoFetch,
      productId: context.productId,
      startedAt: new Date().toISOString(),
    };
    localStorage.setItem(ASIN_DIAGNOSIS_TASK_KEY, taskRes.data.task_id);
    localStorage.setItem(ASIN_DIAGNOSIS_TASK_CONTEXT_KEY, JSON.stringify(taskContext));
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "asin-manager",
      label: `ASIN抓取分析 ${asin}`,
      status: "running",
      detail: "正在抓取Amazon页面并生成选品判断",
      path: "/asin-manager",
      startedAt: taskContext.startedAt,
    });
    let task = taskRes.data;
    const pollStartedAt = Date.now();
    while (Date.now() - pollStartedAt < ASIN_TASK_TIMEOUT_MS) {
      const remainingMs = ASIN_TASK_TIMEOUT_MS - (Date.now() - pollStartedAt);
      try {
        const statusRes = await axios.get<AsinDiagnosisTaskResponse>(
          `${apiBase}/api/v1/diagnosis-tasks/${taskRes.data.task_id}`,
          { headers: getAuthHeaders(), timeout: Math.max(3000, Math.min(10000, remainingMs)) }
        );
        task = statusRes.data;
      } catch (err) {
        if (isAxiosTimeout(err)) {
          await new Promise((resolve) => window.setTimeout(resolve, ASIN_TASK_POLL_INTERVAL_MS));
          continue;
        }
        throw err;
      }
      if (task.status === "completed") break;
      if (task.status === "failed") {
        const message = task.error_message || "ASIN分析任务失败";
        clearFailedAsinModuleTask(moduleTaskId, message);
        throw new Error(message);
      }
      await new Promise((resolve) => window.setTimeout(resolve, ASIN_TASK_POLL_INTERVAL_MS));
    }
    if (task.status !== "completed" || !task.result_payload) {
      clearFailedAsinModuleTask(moduleTaskId, ASIN_TASK_TIMEOUT_MESSAGE);
      throw new Error(ASIN_TASK_TIMEOUT_MESSAGE);
    }
    finishModuleTask(moduleTaskId, "completed", "ASIN抓取分析已完成");
    window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
    clearActiveAsinTaskStorage();
    const normalized = productDataFromAsinTaskPayload(task.result_payload, asin);
    return {
      status: "success",
      source: normalized.source,
      data: normalized.data,
    };
  };

  /* ---- Smart fetch: Server proxy → Server scrape → AI (three phases) ---- */
  const smartFetchAsin = async (
    asin: string,
    marketplace: string,
    context: Partial<Omit<ActiveAsinTaskContext, "taskId" | "moduleTaskId" | "asin" | "marketplace" | "startedAt">> = {}
  ): Promise<AsinFetchResult> => {
    if (isPublicDeployment()) {
      setAutoImportMessage("正在提取商品信息并生成分析结果，通常需要 10-40 秒");
      setAutoImportProgress(35);
      try {
        const serverResult = await fetchAsinViaAI(asin, marketplace, context);
        setAutoImportProgress(100);
        return serverResult;
      } catch (e: unknown) {
        const msg = axios.isAxiosError(e)
          ? e.code === "ECONNABORTED"
            ? "公网服务器分析超时，请稍后重试。"
            : e.response?.data?.detail || "商品分析失败"
          : e instanceof Error
            ? e.message
            : "请求失败";
        return { status: "failed", error: msg };
      }
    }

    // Phase 1: backend proxy fetch. True local-browser capture is handled by
    // Listing diagnosis manual HTML capture; this source stays medium-confidence.
    setAutoImportMessage("正在提取Amazon商品页面信息，通常需要 20-30 秒");
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
            { asin, marketplace, html, source: "server_proxy_fetch" },
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
              source: "商品页面提取",
            };
          }
        } catch {
          // fall through
        }
      }
    } catch (e: unknown) {
      if (axios.isAxiosError(e) && e.code === "ECONNABORTED") {
        toast.warning("当前ASIN分析耗时较长，系统已切换到补充分析模式。");
      }
      // fall through
    }

    // Phase 2 + 3: Backend server scrape first, then low-confidence mode when real data is unavailable.
    setAutoImportMessage("正在补充商品信息并生成低置信度标记");
    setAutoImportProgress(62);
    try {
      const aiResult = await fetchAsinViaAI(asin, marketplace, context);
      setAutoImportProgress(100);
      return aiResult;
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? e.code === "ECONNABORTED"
          ? "分析超过180秒，请稍后重试；如果连续失败，说明Amazon页面抓取或诊断生成较慢。"
          : e.response?.data?.detail || "商品分析失败"
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
    if (isLocalCaptureRoute) {
      const capture = resolveLocalBrowserCapture();
      if (!capture) {
        showMissingLocalCaptureMessage();
        return;
      }
      await processLocalBrowserCapture(capture, { validate: false });
      return;
    }
    setAutoImportLoading(true);
    setAutoImportProgress(3);
    setAutoImportElapsed(0);
    setAutoImportMessage("准备开始抓取分析，预计 60 秒内完成");
    try {
      const result = await smartFetchAsin(asin, autoImportMarketplace, {
        intent: "single_import",
        autoFetch,
      });
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

        const sourceLabel = productFetchSourceLabel(result.source);
        const isLowConfidence = sourceLabel === "低置信度预检";
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
              module_name: "ASIN机会判断",
              action_key: "fetch_asin_product",
              action_name: "ASIN抓取并保存",
              asin,
              title: productData.title,
              input_snapshot: { asin, marketplace: autoImportMarketplace },
              output_snapshot: snapshotProductData,
              data_source: sourceLabel,
              confidence: isLowConfidence ? "low" : "high",
              ai_called: isLowConfidence,
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
    if (isLocalCaptureRoute) {
      const capture = resolveLocalBrowserCapture();
      if (!capture) {
        showMissingLocalCaptureMessage();
        return;
      }
      await processLocalBrowserCapture(capture, { validate: true });
      return;
    }
    setAutoImportLoading(true);
    setAutoImportProgress(3);
    setAutoImportElapsed(0);
    setAutoImportMessage("准备抓取、保存并验证关键词销量");
    try {
      const result = await smartFetchAsin(asin, autoImportMarketplace, {
        intent: "single_import_validate",
        autoFetch: true,
      });
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
          const result = await smartFetchAsin(asin, autoImportMarketplace, {
            intent: "batch_import",
            autoFetch: true,
          });
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
                module_name: "ASIN机会判断",
                action_key: "batch_fetch_asin_product",
                action_name: "批量ASIN抓取并保存",
                asin,
                title: result.data.title || asin,
                input_snapshot: { asin, marketplace: autoImportMarketplace },
                output_snapshot: { ...productData, marketplace: autoImportMarketplace },
                data_source: productFetchSourceLabel(result.source),
                confidence: productFetchSourceLabel(result.source) === "低置信度预检" ? "low" : "high",
                ai_called: productFetchSourceLabel(result.source) === "低置信度预检",
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

  const handleScraplingTop40Batch = async () => {
    const keyword = scraplingKeyword.trim();
    if (!keyword) {
      toast.error("请输入关键词");
      return;
    }
    const moduleTaskId = `asin-top40-batch:${autoImportMarketplace}:${keyword}:${scraplingBatchIndex}`;
    setScraplingLoading(true);
    setScraplingResult(null);
    setTop40Analysis(null);
    setAutoImportProgress(5);
    setAutoImportElapsed(0);
    setAutoImportMessage(`正在生成Top40竞品快照：第 ${scraplingBatchIndex} 批`);
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "asin-manager",
      label: `Top40快照 ${keyword}`,
      status: "running",
      detail: `正在抓取第 ${scraplingBatchIndex} 批搜索结果`,
      path: "/asin-manager",
    });
    try {
      const res = await axios.post(
        `${getLongRunningApiBase()}/api/v1/asin-selection/scrapling/top40-batch`,
        {
          keyword,
          marketplace: autoImportMarketplace,
          batch_index: scraplingBatchIndex,
          include_details: false,
        },
        { headers: getAuthHeaders(), timeout: 420000 }
      );
      const result = res.data as ScraplingTop40BatchResult;
      if (result.usage) setTop40Usage(result.usage);
      setScraplingResult(result);
      setScraplingResults((prev) => {
        const next = prev.filter((item) => item.batchIndex !== result.batchIndex);
        return [...next, result].sort((a, b) => a.batchIndex - b.batchIndex);
      });
      setAutoImportProgress(100);
      setAutoImportMessage(`正在保存 Rank ${result.rankRange} 快照`);
      await saveActionSnapshot({
        module_key: "asin_selection",
        module_name: "ASIN选品",
        action_key: "scrapling_top40_batch",
        action_name: "Top40竞品快照",
        input_snapshot: {
          keyword,
          marketplace: autoImportMarketplace,
          batch_index: scraplingBatchIndex,
        },
        output_snapshot: result,
        data_source: "scrapling_top40_batch",
        confidence: result.status === "ok" ? "medium" : "low",
        ai_called: false,
        source_record_table: "scrapling_raw_snapshot",
      });
      loadTop40Usage().catch(() => {});
      const okCount = result.items.filter((item) => ["ok", "search_snapshot"].includes(String(item.status))).length;
      finishModuleTask(moduleTaskId, "completed", `Top40快照完成：${okCount}/${result.items.length}`);
      toast.success(`已抓取 Rank ${result.rankRange}: ${okCount}/${result.items.length} 条样本可用`);
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? e.response?.data?.detail || "Top40竞品快照生成失败"
        : e instanceof Error
          ? e.message
          : "Top40竞品快照生成失败";
      finishModuleTask(moduleTaskId, "failed", msg);
      toast.error(msg);
    } finally {
      setScraplingLoading(false);
      setAutoImportProgress(0);
      setAutoImportElapsed(0);
      setAutoImportMessage("");
      window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
    }
  };

  const handleScraplingTop40All = async () => {
    const keyword = scraplingKeyword.trim();
    if (!keyword) {
      toast.error("请输入关键词");
      return;
    }
    const moduleTaskId = `asin-top40-all:${autoImportMarketplace}:${keyword}`;
    setScraplingLoading(true);
    setScraplingResult(null);
    setScraplingResults([]);
    setTop40Analysis(null);
    setAutoImportProgress(3);
    setAutoImportElapsed(0);
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "asin-manager",
      label: `Top40完整抓取 ${keyword}`,
      status: "running",
      detail: "正在抓取4批搜索结果并生成市场快照",
      path: "/asin-manager",
    });
    const collected: ScraplingTop40BatchResult[] = [];
    try {
      for (let batchIndex = 1; batchIndex <= 4; batchIndex += 1) {
        setScraplingBatchIndex(batchIndex);
        setAutoImportMessage(`正在生成Top40竞品快照：第 ${batchIndex}/4 批，预计3-5分钟`);
        setAutoImportProgress(Math.round(((batchIndex - 1) / 4) * 100) + 5);
        const res = await axios.post(
          `${getLongRunningApiBase()}/api/v1/asin-selection/scrapling/top40-batch`,
          {
            keyword,
            marketplace: autoImportMarketplace,
            batch_index: batchIndex,
            include_details: false,
          },
          { headers: getAuthHeaders(), timeout: 420000 }
        );
        const result = res.data as ScraplingTop40BatchResult;
        if (result.usage) setTop40Usage(result.usage);
        collected.push(result);
        setScraplingResult(result);
        setScraplingResults([...collected]);
        setAutoImportMessage(`正在保存Top40竞品快照：第 ${batchIndex}/4 批`);
        await saveActionSnapshot({
          module_key: "asin_selection",
          module_name: "ASIN选品",
          action_key: "scrapling_top40_batch",
          action_name: "Top40竞品快照",
          input_snapshot: {
            keyword,
            marketplace: autoImportMarketplace,
            batch_index: batchIndex,
          },
          output_snapshot: result,
          data_source: "scrapling_top40_batch",
          confidence: result.status === "ok" ? "medium" : "low",
          ai_called: false,
          source_record_table: "scrapling_raw_snapshot",
        });
        if (result.status === "blocked") {
          toast.warning(`第 ${batchIndex} 批遇到访问限制，已停止后续批次`);
          break;
        }
      }
      const itemCount = collected.reduce((sum, item) => sum + item.items.length, 0);
      const okCount = collected.reduce(
        (sum, item) => sum + item.items.filter((row) => ["ok", "search_snapshot"].includes(String(row.status))).length,
        0
      );
      setAutoImportProgress(100);
      loadTop40Usage().catch(() => {});
      finishModuleTask(moduleTaskId, "completed", `Top40抓取完成：${okCount}/${itemCount}`);
      toast.success(`Top40抓取完成：${okCount}/${itemCount} 条样本可用`);
      const capturedItems = collected.flatMap((batch) => batch.items);
      if (capturedItems.length > 0) {
        await runTop40MarketAnalysis(capturedItems, keyword, autoImportMarketplace, {
          resetProgressOnFinish: false,
        });
      }
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? e.response?.data?.detail || "Top40竞品快照生成失败"
        : e instanceof Error
          ? e.message
          : "Top40竞品快照生成失败";
      finishModuleTask(moduleTaskId, "failed", msg);
      toast.error(msg);
    } finally {
      setScraplingLoading(false);
      setAutoImportProgress(0);
      setAutoImportElapsed(0);
      setAutoImportMessage("");
      window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
    }
  };

  const runTop40MarketAnalysis = async (
    items: ScraplingTop40Item[],
    keyword: string,
    marketplace: string,
    options: { resetProgressOnFinish?: boolean } = {}
  ) => {
    if (!keyword || items.length === 0) {
      toast.error("请先完成Top40抓取");
      return;
    }
    const moduleTaskId = `asin-top40-analysis:${marketplace}:${keyword}`;
    setTop40Analyzing(true);
    setAutoImportProgress(8);
    setAutoImportElapsed(0);
    setAutoImportMessage("正在生成Top40市场机会报告");
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "asin-manager",
      label: `Top40机会分析 ${keyword}`,
      status: "running",
      detail: "正在生成市场机会判断",
      path: "/asin-manager",
    });
    try {
      const res = await axios.post(
        `${getLongRunningApiBase()}/api/v1/asin-selection/top40-market-analysis`,
        {
          keyword,
          marketplace,
          items,
        },
        { headers: getAuthHeaders(), timeout: 420000 }
      );
      const analysis = res.data as Top40MarketAnalysis;
      setTop40Analysis(analysis);
      setAutoImportProgress(100);
      saveActionSnapshot({
        module_key: "asin_selection",
        module_name: "ASIN选品",
        action_key: "top40_market_analysis",
        action_name: "Top40竞品价格带机会分析",
        input_snapshot: { keyword, marketplace, item_count: items.length },
        output_snapshot: analysis,
        data_source: analysis.analysisSource || "rules",
        confidence: analysis.analysisSource === "ai" ? "medium" : "low",
        ai_called: analysis.analysisSource === "ai",
        source_record_table: "top40_market_analysis",
      }).catch(() => {});
      finishModuleTask(moduleTaskId, "completed", "Top40市场机会分析完成");
      toast.success(`Top40市场机会分析完成：${analysis.headline}`);
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? e.response?.data?.detail || "Top40市场机会分析失败"
        : e instanceof Error
          ? e.message
          : "Top40市场机会分析失败";
      finishModuleTask(moduleTaskId, "failed", msg);
      toast.error(msg);
    } finally {
      setTop40Analyzing(false);
      if (options.resetProgressOnFinish !== false) {
        setAutoImportProgress(0);
        setAutoImportElapsed(0);
        setAutoImportMessage("");
      }
      window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
    }
  };

  const handleTop40MarketAnalysis = async () => {
    const items = scraplingResults.flatMap((batch) => batch.items);
    await runTop40MarketAnalysis(items, scraplingKeyword.trim(), autoImportMarketplace);
  };

  /* ---- Refresh single product data ---- */
  const handleRefreshProduct = async (product: Product) => {
    const marketplace = getProductMarketplace(product);
    setRefreshingId(product.id);
    try {
      const result = await smartFetchAsin(product.asin, marketplace, {
        intent: "refresh_product",
        autoFetch: true,
        productId: product.id,
      });
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
        const sourceLabel = productFetchSourceLabel(result.source);
        const isLowConfidence = sourceLabel === "低置信度预检";
        saveActionSnapshot({
          module_key: "asin_selection",
          module_name: "ASIN机会判断",
          action_key: "refresh_asin_product",
          action_name: "刷新ASIN产品数据",
          product_id: product.id,
          asin: product.asin,
          title: result.data.title || product.title,
          input_snapshot: { ...product, marketplace },
          output_snapshot: { ...result.data, marketplace },
          data_source: sourceLabel,
          confidence: isLowConfidence ? "low" : "high",
          ai_called: isLowConfidence,
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

  const snapshotInput = (item: ActionSnapshot) =>
    (item.input_snapshot || {}) as Record<string, unknown>;

  const snapshotOutput = (item: ActionSnapshot) =>
    (item.output_snapshot || {}) as Record<string, unknown>;

  const loadTop40SnapshotGroup = async (snapshot: ActionSnapshot) => {
    const input = snapshotInput(snapshot);
    const keyword = String(input.keyword || "").trim();
    const marketplace = String(input.marketplace || autoImportMarketplace || "US").toUpperCase();
    if (!keyword) {
      toast.error("这条历史记录缺少关键词，无法恢复Top40");
      return;
    }
    setHistoryLoading(true);
    try {
      const [batchSnapshots, analysisSnapshots] = await Promise.all([
        getActionSnapshots({ module_key: "asin_selection", action_key: "scrapling_top40_batch", limit: 120 }),
        getActionSnapshots({ module_key: "asin_selection", action_key: "top40_market_analysis", limit: 40 }),
      ]);
      const latestByBatch = new Map<number, ScraplingTop40BatchResult>();
      for (const item of batchSnapshots) {
        const itemInput = snapshotInput(item);
        if (String(itemInput.keyword || "").trim() !== keyword) continue;
        if (String(itemInput.marketplace || "US").toUpperCase() !== marketplace) continue;
        const batchIndex = Number(itemInput.batch_index || snapshotOutput(item).batchIndex || 0);
        if (batchIndex < 1 || batchIndex > 4 || latestByBatch.has(batchIndex)) continue;
        latestByBatch.set(batchIndex, snapshotOutput(item) as unknown as ScraplingTop40BatchResult);
      }
      const restored = Array.from(latestByBatch.values()).sort((a, b) => a.batchIndex - b.batchIndex);
      if (!restored.length) {
        toast.error("没有找到可恢复的Top40批次");
        return;
      }

      const latestAnalysis = analysisSnapshots.find((item) => {
        const itemInput = snapshotInput(item);
        return (
          String(itemInput.keyword || "").trim() === keyword &&
          String(itemInput.marketplace || "US").toUpperCase() === marketplace
        );
      });

      setImportMode("top40");
      setShowAutoImport(true);
      setShowForm(false);
      setScraplingKeyword(keyword);
      setAutoImportMarketplace(marketplace);
      setScraplingResults(restored);
      setScraplingResult(restored[restored.length - 1]);
      setTop40Analysis(latestAnalysis ? (snapshotOutput(latestAnalysis) as unknown as Top40MarketAnalysis) : null);
      toast.success(`已恢复 ${keyword} 的Top40快照：${restored.length}/4 批`);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "恢复Top40快照失败");
    } finally {
      setHistoryLoading(false);
    }
  };

  const getPriceStatusLabel = (item: ScraplingTop40Item) => {
    switch (item.priceStatus) {
      case "detail_price":
        return "详情页价格";
      case "search_price":
        return "搜索页价格";
      case "search_price_fallback":
        return "搜索页价格";
      case "detail_error":
        return item.searchPriceText ? "搜索页价格" : "详情页失败";
      case "detail_parse_failed":
        return item.searchPriceText ? "搜索页价格" : "价格待确认";
      case "blocked":
        return "访问受限";
      case "missing":
        return "价格缺失";
      default:
        return item.priceText || item.searchPriceText ? "已获取" : "价格缺失";
    }
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
                集中管理你的Amazon产品 · 按总分、风险和关键限制分流机会池 · 各诊断工具可直接引用
              </p>
            </div>
          </div>

          <PageHeader
            objective="集中管理你的Amazon产品ASIN，判断能不能做、风险在哪里、下一步去哪"
            inputSource="关键词Top40竞品快照 / 单个ASIN补充抓取"
            process="先保存真实数据，再判断需求、搜索、竞争、差异化、商业和风险信号"
            outputTarget="机会判断 · 关键限制 · 下一步动作"
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
                  ASIN选品抓取
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
                  onClick={() => setImportMode("top40")}
                  className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                    importMode === "top40"
                      ? "bg-amber-600/80 text-gray-900"
                      : "text-gray-500 hover:text-gray-900 hover:bg-gray-100"
                  }`}
                >
                  Top40机会分析
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
                {isLocalCaptureRoute && (
                  <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-3 py-3">
                    <p className="text-sm font-semibold text-emerald-800 flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4" />
                      当前页面导入
                    </p>
                    <p className="text-xs text-gray-600 mt-1">
                      正在使用你刚打开的 Amazon 商品页内容。未收到页面内容时，请回 Amazon 商品页重新点击发送。
                    </p>
                    <p className="text-xs text-emerald-700 mt-1">
                      {pendingLocalCapture?.asin
                        ? `已收到 ${pendingLocalCapture.asin} 的页面内容。`
                        : localCaptureAsin
                          ? `正在等待 ${localCaptureAsin} 的页面内容。`
                          : "正在等待页面内容。"}
                    </p>
                  </div>
                )}
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
                      ? isLocalCaptureRoute
                        ? "正在读取页面..."
                        : "正在抓取真实数据..."
                      : isLocalCaptureRoute
                        ? "使用页面内容分析"
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
                    {!autoImportAsin.trim() && (
                      <p className="text-xs text-emerald-700 mt-1">
                        已保存的 ASIN 请点下方产品卡右侧的“查看验证报告”。
                      </p>
                    )}
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
                    {isLocalCaptureRoute ? "保存并验证" : "抓取保存并验证"}
                  </Button>
                </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-[1fr_180px_auto] gap-3 items-end">
                    <div>
                      <Label className="text-gray-500 text-sm">关键词</Label>
                      <Input
                        value={scraplingKeyword}
                        onChange={(e) => setScraplingKeyword(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && !scraplingLoading)
                            handleScraplingTop40Batch();
                        }}
                        placeholder="iPhone 16 case"
                        className="mt-1 bg-gray-50 border-gray-200 text-gray-900"
                      />
                    </div>
                    <div>
                      <Label className="text-gray-500 text-sm">排名批次</Label>
                      <Select
                        value={String(scraplingBatchIndex)}
                        onValueChange={(value) => setScraplingBatchIndex(Number(value))}
                      >
                        <SelectTrigger className="mt-1 bg-gray-50 border-gray-200 text-gray-900">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-white border-gray-200">
                          <SelectItem value="1">Rank 1-10</SelectItem>
                          <SelectItem value="2">Rank 11-20</SelectItem>
                          <SelectItem value="3">Rank 21-30</SelectItem>
                          <SelectItem value="4">Rank 31-40</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        onClick={handleScraplingTop40All}
                        disabled={isTop40Busy || !scraplingKeyword.trim() || Boolean(top40Usage && top40Usage.remainingRuns < 1)}
                        className="bg-amber-600 hover:bg-amber-500 text-white"
                      >
                        {isTop40Busy ? (
                          <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                        ) : (
                          <Search className="w-4 h-4 mr-1" />
                        )}
                        分析Top40机会
                      </Button>
                      <Button
                        onClick={handleScraplingTop40Batch}
                        disabled={isTop40Busy || !scraplingKeyword.trim() || Boolean(top40Usage && top40Usage.remainingRuns < 1)}
                        variant="outline"
                        className="border-gray-200 text-gray-700"
                      >
                        只分析当前10家
                      </Button>
                    </div>
                  </div>

                  <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-3">
                    <p className="text-xs font-semibold text-gray-800 mb-2">Top40市场机会分析</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5 text-[11px] text-gray-600">
                      <span>基于关键词查看前40个竞品样本</span>
                      <span>拆分Top20与中段20判断进入门槛</span>
                      <span>识别广告位样本，避免误判自然机会</span>
                      <span>按价格带、评分、评论数聚合对比</span>
                      <span>找出低评论高排名的潜在机会ASIN</span>
                      <span>生成推荐切入价带和后续验证动作</span>
                    </div>
                    <div className="mt-3 rounded-md border border-amber-100 bg-white px-3 py-2 text-[11px] text-amber-800">
                      Top40 是关键词样本池，不会自动写入 ASIN库。点击表格里的「加入ASIN库并评分」后，才会保存到 ASIN库并进入机会判断、关键词验证和后续诊断闭环。
                    </div>
                    {top40Usage && (
                      <div className="mt-3 rounded-md border border-amber-100 bg-white px-3 py-2 text-[11px] text-gray-600">
                        24小时额度：已用 {top40Usage.usedRuns}/{top40Usage.dailyRunLimit} 次，
                        剩余 {top40Usage.remainingRuns} 次；两次Top40分析至少间隔 {top40Usage.minIntervalHours} 小时。
                        {top40Usage.nextAllowedAt ? ` 下次可用时间：${new Date(top40Usage.nextAllowedAt).toLocaleString("zh-CN")}` : ""}
                      </div>
                    )}
                  </div>

                  {scraplingResults.length > 0 && (
                    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-3 py-2 border-b border-gray-100">
                        <div>
                          <p className="text-sm font-semibold text-gray-900">
                            {scraplingKeyword.trim()} · Top40市场机会样本
                          </p>
                          <p className="text-xs text-gray-500">
                            {scraplingResults.length}/4 批 · {scraplingResults.reduce((sum, item) => sum + item.items.length, 0)} 个竞品样本
                          </p>
                          <p className="text-[11px] text-amber-700 mt-1">
                            样本池与 ASIN库分开保存；入库后才能在左侧 ASIN库继续评分、诊断和广告验证。
                          </p>
                        </div>
                        <span className="text-xs text-gray-500">
                          {scraplingResult ? new Date(scraplingResult.capturedAt).toLocaleString() : ""}
                        </span>
                      </div>
                      <div className="flex flex-col gap-3 border-b border-gray-100 bg-gray-50 px-3 py-3">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold text-gray-900">
                              第二步：分析价格带、头部门槛和中段机会
                            </p>
                            <p className="text-xs text-gray-500 mt-1">
                              结果会回填到下方表格：价格带、机会分、机会标签、Top20/中段20判断。
                            </p>
                          </div>
                          <Button
                            onClick={handleTop40MarketAnalysis}
                            disabled={top40Analyzing || scraplingResults.flatMap((batch) => batch.items).length === 0}
                            className="bg-emerald-700 hover:bg-emerald-600 text-white shrink-0"
                          >
                            {top40Analyzing ? (
                              <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                            ) : (
                              <Sparkles className="w-4 h-4 mr-1" />
                            )}
                            生成市场机会分析
                          </Button>
                        </div>

                        {top40Analysis && (
                          <div className="grid grid-cols-1 lg:grid-cols-4 gap-3">
                            <div className="rounded-md border border-emerald-100 bg-white px-3 py-3">
                              <p className="text-xs text-gray-500">结论</p>
                              <p className="text-sm font-semibold text-emerald-800 mt-1">{top40Analysis.headline}</p>
                              <p className="text-[11px] text-gray-500 mt-1">{top40Analysis.analysisSource === "ai" ? "智能判断" : "保守判断"}</p>
                            </div>
                            <div className="rounded-md border border-gray-200 bg-white px-3 py-3">
                              <p className="text-xs text-gray-500">中位价格</p>
                              <p className="text-lg font-semibold text-gray-900 mt-1">
                                {top40Analysis.summary.medianPrice ? `$${Number(top40Analysis.summary.medianPrice).toFixed(2)}` : "-"}
                              </p>
                              <p className="text-[11px] text-gray-500 mt-1">Top40样本</p>
                            </div>
                            <div className="rounded-md border border-gray-200 bg-white px-3 py-3">
                              <p className="text-xs text-gray-500">Top20评论门槛</p>
                              <p className="text-lg font-semibold text-gray-900 mt-1">{Math.round(top40Analysis.summary.top20MedianReviews || 0)}</p>
                              <p className="text-[11px] text-gray-500 mt-1">中位评论数</p>
                            </div>
                            <div className="rounded-md border border-gray-200 bg-white px-3 py-3">
                              <p className="text-xs text-gray-500">推荐价格带</p>
                              <p className="text-sm font-semibold text-gray-900 mt-1">
                                {top40Analysis.recommendedPriceBand?.label || "-"}
                              </p>
                              <p className="text-[11px] text-gray-500 mt-1">
                                机会分 {top40Analysis.recommendedPriceBand?.avgOpportunityScore || "-"}
                              </p>
                            </div>
                          </div>
                        )}

                        {top40Analysis?.priceBands?.length ? (
                          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2">
                            {top40Analysis.priceBands.slice(0, 4).map((band) => (
                              <div key={band.band} className="rounded-md border border-gray-200 bg-white px-3 py-2">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="text-xs font-semibold text-gray-800">{band.label}</span>
                                  <span className="text-xs text-emerald-700">{band.avgOpportunityScore}分</span>
                                </div>
                                <p className="text-[11px] text-gray-500 mt-1">
                                  {band.count}家 · {band.minPrice ? `$${Number(band.minPrice).toFixed(0)}` : "-"}-
                                  {band.maxPrice ? `$${Number(band.maxPrice).toFixed(0)}` : "-"} · 评论中位 {Math.round(band.medianReviews || 0)}
                                </p>
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                      <div className="max-h-72 overflow-auto">
                        <table className="w-full text-xs">
                          <thead className="sticky top-0 bg-gray-50 text-gray-500">
                            <tr>
                              <th className="text-left px-3 py-2 font-medium">Rank</th>
                              <th className="text-left px-3 py-2 font-medium">ASIN</th>
                              <th className="text-left px-3 py-2 font-medium">标题</th>
                              <th className="text-left px-3 py-2 font-medium">价格</th>
                              <th className="text-left px-3 py-2 font-medium">价格状态</th>
                              <th className="text-left px-3 py-2 font-medium">评分</th>
                              <th className="text-left px-3 py-2 font-medium">机会</th>
                              <th className="text-left px-3 py-2 font-medium">价格带</th>
                              <th className="text-left px-3 py-2 font-medium">状态</th>
                              <th className="text-left px-3 py-2 font-medium">下一步</th>
                            </tr>
                          </thead>
                          <tbody>
                            {scraplingResults.flatMap((batch) => batch.items).map((item) => {
                              const analysisRow = top40AnalysisByAsin[item.asin] || {};
                              const isInLibrary = products.some((product) => product.asin === item.asin);
                              return (
                                <tr key={`${item.searchRank}-${item.asin}`} className="border-t border-gray-100">
                                  <td className="px-3 py-2 text-gray-700">{item.searchRank}</td>
                                  <td className="px-3 py-2 font-mono text-gray-700">{item.asin}</td>
                                  <td className="px-3 py-2 text-gray-800 min-w-[260px]">
                                    <div className="line-clamp-2">
                                      {item.isSponsored ? "广告位 · " : ""}
                                      {item.title || "-"}
                                    </div>
                                    {(analysisRow.aiReason || analysisRow.analysisReason) && (
                                      <div className="mt-1 text-[11px] text-gray-500 line-clamp-1">
                                        {analysisRow.aiReason || analysisRow.analysisReason}
                                      </div>
                                    )}
                                  </td>
                                  <td className="px-3 py-2 text-gray-700">{item.priceText || item.searchPriceText || "-"}</td>
                                  <td className="px-3 py-2 text-gray-700">
                                    <span className="rounded bg-gray-50 px-2 py-1">
                                      {getPriceStatusLabel(item)}
                                    </span>
                                  </td>
                                  <td className="px-3 py-2 text-gray-700">
                                    {item.rating || "-"} / {item.reviewCount || "-"}
                                  </td>
                                  <td className="px-3 py-2">
                                    {analysisRow.opportunityScore ? (
                                      <span className="rounded bg-emerald-50 px-2 py-1 text-emerald-700 font-semibold">
                                        {analysisRow.opportunityScore} · {analysisRow.aiTag || analysisRow.opportunityTag}
                                      </span>
                                    ) : (
                                      <span className="text-gray-400">待分析</span>
                                    )}
                                  </td>
                                  <td className="px-3 py-2 text-gray-700">{analysisRow.priceBandLabel || "-"}</td>
                                  <td className="px-3 py-2 text-gray-700">
                                    {isInLibrary ? (
                                      <span className="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-1 text-emerald-700 font-medium">
                                        <CheckCircle2 className="w-3.5 h-3.5" />
                                        已入库
                                      </span>
                                    ) : (
                                      <span className="inline-flex items-center gap-1 rounded bg-amber-50 px-2 py-1 text-amber-700 font-medium">
                                        未入库
                                      </span>
                                    )}
                                  </td>
                                  <td className="px-3 py-2">
                                    <Button
                                      size="sm"
                                      variant={isInLibrary ? "outline" : "default"}
                                      className={
                                        isInLibrary
                                          ? "h-8 whitespace-nowrap border-gray-200"
                                          : "h-8 whitespace-nowrap bg-emerald-700 hover:bg-emerald-600 text-white"
                                      }
                                      onClick={() => handleTop40DeepDive(item)}
                                      disabled={top40DeepDiveAsin === item.asin || scoringAsin === item.asin}
                                    >
                                      {top40DeepDiveAsin === item.asin || scoringAsin === item.asin ? (
                                        <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                                      ) : (
                                        <Microscope className="w-3.5 h-3.5 mr-1" />
                                      )}
                                      {isInLibrary ? "重新评分" : "加入ASIN库并评分"}
                                    </Button>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {(autoImportLoading || batchImportLoading || scraplingLoading || top40Analyzing) && (
                <div className="mt-4 rounded-lg border border-amber-100 bg-amber-50 px-3 py-3">
                  <div className="flex items-center justify-between gap-3 text-xs text-amber-700">
                    <span className="flex items-center gap-1.5">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      {autoImportMessage || "正在抓取并分析 ASIN 数据"}
                      {batchImportCurrent ? ` · 当前 ${batchImportCurrent}` : ""}
                    </span>
                    <span className="shrink-0">
                      {isLocalCaptureRoute
                        ? "正在处理"
                        : `${autoImportElapsed}s / ${isTop40Busy ? `${TOP40_TASK_TIMEOUT_SECONDS}s` : `${ASIN_TASK_TIMEOUT_MS / 1000}s`}`}
                    </span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-white">
                    <div
                      className="h-full rounded-full bg-amber-600 transition-all duration-500"
                      style={{ width: `${autoImportProgress}%` }}
                    />
                  </div>
                  <p className="mt-2 text-[11px] text-gray-600">
                    系统会优先提取可核实字段，信息不足时保留低置信度标记，建议核实价格、评论和标题等关键字段。
                  </p>
                </div>
              )}

              <p className="text-[10px] text-gray-600 mt-3">
                ASIN分析会自动保存商品字段、评分和来源标记，低置信度结果建议人工复核后再决策。
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
                          {item.action_key === "scrapling_top40_batch"
                            ? `Top40 · ${String(snapshotInput(item).keyword || "-")}`
                            : item.asin}
                        </span>
                        <span className="text-gray-600">
                          {item.action_name}
                        </span>
                        {item.action_key === "scrapling_top40_batch" && (
                          <span className="rounded bg-amber-50 px-2 py-0.5 text-amber-700">
                            Batch {String(snapshotInput(item).batch_index || snapshotOutput(item).batchIndex || "-")}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-gray-600 max-w-[200px] truncate">
                          {item.action_key === "scrapling_top40_batch"
                            ? "Top40竞品快照"
                            : item.action_key === "top40_market_analysis"
                              ? "市场机会分析"
                              : item.data_source || item.module_name}
                        </span>
                        <span className="text-gray-600">
                          {new Date(item.created_at).toLocaleString("zh-CN", {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                        {item.action_key === "scrapling_top40_batch" && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => loadTop40SnapshotGroup(item)}
                            className="h-7 border-gray-200 bg-white text-gray-700"
                          >
                            载入Top40
                          </Button>
                        )}
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
                    对ASIN库中的产品进行机会判断，只有证据、风险和进入门槛同时达标才会进入机会池
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
                            variant={keywordReport ? "outline" : "ghost"}
                            size="sm"
                            onClick={() => {
                              if (keywordReport) {
                                setExpandedKeywordAsin(isKeywordExpanded ? null : product.asin);
                              } else {
                                handleKeywordSalesValidation(product);
                              }
                            }}
                            disabled={isKeywordValidating}
                            className={
                              keywordReport
                                ? "border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 h-8 px-3"
                                : "text-gray-500 hover:text-emerald-700 h-8 px-2"
                            }
                            title={keywordReport ? "查看关键词销量验证报告" : "开始关键词销量验证"}
                          >
                            {isKeywordValidating ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <ShieldCheck className="w-4 h-4" />
                            )}
                            {keywordReport && (
                              <span className="ml-1.5 text-xs font-semibold">
                                {isKeywordExpanded ? "收起报告" : `查看验证报告 · ${Math.round(keywordReport.keyword_sales_score)}分`}
                              </span>
                            )}
                            {!keywordReport && !isKeywordValidating && (
                              <span className="hidden sm:inline ml-1.5 text-xs font-semibold">关键词验证</span>
                            )}
                          </Button>
                          {keywordReport && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleKeywordSalesValidation(product)}
                              disabled={isKeywordValidating}
                              className="text-gray-500 hover:text-emerald-700 h-8 px-2"
                              title="重新抓取并验证关键词销量"
                            >
                              {isKeywordValidating ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                              <span className="hidden sm:inline ml-1.5 text-xs font-semibold">重新验证</span>
                            </Button>
                          )}
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
                      <div id={`keyword-validation-report-${product.asin}`} className="ml-12 mt-1 mb-2 scroll-mt-24">
                        <Card className="bg-white border-emerald-100 p-4">
                          <div className="flex items-start justify-between gap-3 mb-4">
                            <div>
                              <div className="flex items-center gap-2">
                                <ShieldCheck className="w-4 h-4 text-emerald-700" />
                                <h3 className="font-bold text-gray-900">关键词销量验证</h3>
                              </div>
                              <p className="text-xs text-gray-500 mt-1">销量来源风险雷达：交叉查看库存可售、BSR、评论、自然排名、广告位与促销信号。</p>
	                              <p className="text-[11px] text-gray-400 mt-1">
	                                数据来源：{keywordReport.keyword_rank_summary?.rank_data_source === "scrapling_top40_search" ? "核心词Top40搜索快照" : "系统估算快照"}
	                              </p>
                              <label className="mt-2 inline-flex items-center gap-2 text-xs text-red-700">
                                <Checkbox
                                  checked={Boolean(outOfStockAsins[product.asin])}
                                  onCheckedChange={(checked) => {
                                    markOutOfStock(product.asin, checked === true);
                                    if (checked === true) toast.info("已标记为自有无库存，请点击重新验证");
                                  }}
                                />
                                自有ASIN当前库存为0/不可售
                              </label>
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
                              <p className="text-lg font-bold text-amber-700">
                                {keywordReport.keyword_rank_summary?.inventory_blocker ? "暂不判断" : `${keywordReport.ad_dependency_risk}%`}
                              </p>
                              <p className="text-[11px] text-amber-700 mt-0.5">
                                {keywordReport.keyword_rank_summary?.ad_risk_level || (keywordReport.ad_dependency_risk <= 20 ? "优秀自然流量结构" : keywordReport.ad_dependency_risk <= 35 ? "健康可控" : "需要观察")}
                              </p>
                            </div>
                            <div className="rounded-lg bg-gray-50 border border-gray-100 p-3">
                              <p className="text-xs text-gray-500">系统判断</p>
                              <p className="text-sm font-semibold text-gray-800">{keywordReport.sales_source_judgment}</p>
                            </div>
                          </div>

                          {keywordReport.market_validation_assist && (
                            <div className="rounded-lg bg-slate-50 border border-slate-100 p-3 mb-4">
                              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                                <div>
                                  <p className="text-sm font-semibold text-gray-800">选品验证建议</p>
                                  {keywordReport.market_validation_assist.entry_strategy && (
                                    <p className="text-xs text-gray-600 mt-1 leading-5">{keywordReport.market_validation_assist.entry_strategy}</p>
                                  )}
                                  {(keywordReport.market_validation_assist.validation_actions || []).length > 0 && (
                                    <ul className="mt-2 space-y-1 text-xs text-gray-600">
                                      {(keywordReport.market_validation_assist.validation_actions || []).slice(0, 4).map((action) => (
                                        <li key={action}>• {action}</li>
                                      ))}
                                    </ul>
                                  )}
                                </div>
                                {(keywordReport.market_validation_assist.six_dimension_calibration || []).length > 0 && (
                                  <div>
                                    <p className="text-sm font-semibold text-gray-800">6维校准信号</p>
                                    <div className="mt-2 space-y-2">
                                      {(keywordReport.market_validation_assist.six_dimension_calibration || []).slice(0, 4).map((item) => (
                                        <div key={`${item.dimension}-${item.signal}`} className="rounded-md bg-white border border-gray-100 px-2.5 py-2">
                                          <div className="flex items-center justify-between gap-2">
                                            <span className="text-xs font-semibold text-gray-700">{item.dimension}</span>
                                            <span className={`text-[11px] font-semibold ${
                                              item.impact.includes("扣") || item.impact.includes("复查") ? "text-amber-700" : item.impact.includes("暂缓") ? "text-red-700" : "text-emerald-700"
                                            }`}>
                                              {item.impact}
                                            </span>
                                          </div>
                                          <p className="text-xs text-gray-600 mt-1">{item.signal}：{item.reason}</p>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          )}

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
                                <span className={row.organic_position ? "text-emerald-700" : "text-gray-400"}>{row.organic_position || "未进Top40"}</span>
                                <span className={row.sponsored_position ? "text-amber-700" : "text-gray-400"}>{row.sponsored_position || "-"}</span>
                                <span className="text-gray-500">{row.search_page || "-"}</span>
                              </div>
                            ))}
                          </div>

                          {keywordReport.keyword_rank_summary?.rank_data_note && (
                            <p className="text-[11px] text-gray-500 mb-3">{keywordReport.keyword_rank_summary.rank_data_note}</p>
                          )}
                          {keywordReport.keyword_rank_summary?.ad_risk_note && (
                            <p className="text-[11px] text-amber-700 mb-3">{keywordReport.keyword_rank_summary.ad_risk_note}</p>
                          )}
                          {keywordReport.keyword_rank_summary?.inventory_blocker && (
                            <div className="rounded-lg bg-red-50 border border-red-100 p-3 mb-3">
                              <div className="flex items-center gap-2 text-sm font-semibold text-red-700 mb-1">
                                <AlertTriangle className="w-4 h-4" />
                                库存阻断：当前不做销量来源判断
                              </div>
                              <p className="text-xs text-red-700 leading-5">
                                {keywordReport.keyword_rank_summary.inventory_note || "该ASIN当前无库存或不可售，请补库存并确认页面可售后重新验证。"}
                              </p>
                              {(keywordReport.keyword_rank_summary.availability || keywordReport.product_snapshot?.availability) && (
                                <p className="text-[11px] text-red-600 mt-2">
                                  页面可售状态：{keywordReport.keyword_rank_summary.availability || keywordReport.product_snapshot?.availability}
                                </p>
                              )}
                            </div>
                          )}

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
            currentStep="ASIN选品"
            actions={[
              { label: "进入上新检测", path: "/listing-launch-check", variant: "default" },
            ]}
          />
        </div>
      </main>
    </div>
  );
}
