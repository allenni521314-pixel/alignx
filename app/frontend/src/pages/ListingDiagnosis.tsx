import { useEffect, useRef, useState } from "react";
import { AppSidebar } from "@/components/AppSidebar";
import { PageHeader } from "@/components/PageHeader";
import { NextStepActions } from "@/components/NextStepActions";
import { MarketplaceSelect, MARKETPLACE_OPTIONS } from "@/components/MarketplaceSelect";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Loader2,
  ClipboardCheck,
  Zap,
  MapPin,
  Users,
  Heart,
  Shield,
  Sparkles,
  Target,
  History,
  Search,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Megaphone,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowRight,
  Link,
  Download,
  FileText,
  List,
  Image,
  Star,
  Database,
  BarChart3,
  Award,
  MessageSquare,
  ShoppingCart,
  Globe,
  ClipboardPaste,
  Trash2,
  Eye,
  EyeOff,
  Filter,
  BarChart2,
  Trophy,
  ArrowDown,
  ArrowUp,
} from "lucide-react";
import { toast } from "sonner";
import axios from "axios";
import { getAuthHeaders } from "@/lib/auth-headers";
import { getAllProducts, getCompetitorInsights, updateProductLifecycle, saveTimelineEvent, saveActionSnapshot, type CompetitorInsight, type ActionSnapshot } from "@/lib/workflow-api";
import { client } from "@/lib/api";
import { finishModuleTask, removeModuleTask, upsertModuleTask } from "@/lib/module-task-store";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface ListingInput {
  title: string;
  bullet_points: string;
  description: string;
  a_plus_content: string;
  backend_keywords: string;
  main_image_description: string;
  category: string;
  price: string;
  brand: string;
  marketplace: string;
  asin?: string;
  rating?: string;
  review_count?: string;
  bsr_rank?: string;
  image_count?: string;
  has_video?: boolean;
  has_a_plus?: boolean;
  image_urls?: string[];
  aplus_image_urls?: string[];
}

interface FetchMeta {
  asin?: string;
  source?: string;
  rating?: string;
  review_count?: string;
  bsr_rank?: string;
  bsr_category?: string;
  image_count?: string;
  has_video?: boolean;
  has_a_plus?: boolean;
  review_samples?: Array<Record<string, unknown>>;
  review_intent_assets?: Record<string, unknown>;
  capture_quality?: {
    completeness?: number;
    core_score?: number;
    strategy_score?: number;
    missing_core?: string[];
    missing_strategy?: string[];
    allow_formal_diagnosis?: boolean;
    allow_strategy_diagnosis?: boolean;
    confidence_level?: string;
    rule?: string;
  };
}

const sourceLabel = (source?: string | null) => {
  if (source === "local_browser_capture") return "本地浏览器页面采集";
  if (source === "server_proxy_fetch") return "服务器页面采集";
  if (source === "manual_paste") return "手动粘贴解析";
  if (source === "ai_estimated" || source === "ai_estimated_low_confidence") return "低置信度预检";
  if (source?.includes("scrape") || source === "scraped") return "服务器页面采集";
  if (source === "ai_search") return "搜索验证";
  return source || "未知来源";
};

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

const isPublicDeployment = () =>
  typeof window !== "undefined" &&
  window.location.hostname !== "localhost" &&
  window.location.hostname !== "127.0.0.1";

interface Scores {
  function_expression: number;
  scenario_expression: number;
  identity_fit: number;
  psychology_benefit: number;
  risk_elimination: number;
  differentiation: number;
  product_identity: number;
  compatibility: number;
  subjective_properties: number;
  market_trend: number;
}

interface AdKeyword {
  keyword: string;
  keyword_type?: "attribute" | "relationship" | "state_trigger" | string;
  match_type: string;
  intent: string;
  competition: string;
  priority: string;
}

interface ElementDim {
  function_expression: number;
  scenario_expression: number;
  identity_fit: number;
  psychology_benefit: number;
  risk_elimination: number;
  product_identity: number;
  compatibility: number;
  subjective_properties: number;
  differentiation: number;
  market_trend: number;
}

interface ElementData {
  key: string;
  label: string;
  icon: React.ReactNode;
  dims: ElementDim;
  summary: string;
}

interface MarketEstimates {
  estimated_monthly_sales: number;
  estimated_bsr_rank: number;
}

interface MarketValidation {
  review_score: number;
  rating_score: number;
  sales_tier: string;
  sales_tier_score: number;
  bsr_score: number;
  market_total: number;
  review_count_raw: number;
  rating_raw: number;
  estimated_monthly_sales: number;
  bsr_rank: number;
  analysis: string;
}

interface ComplianceViolation {
  rule_id: string;
  module: string;
  rule_type: string;
  category?: string;
  risk_score: number;
  matched_text?: string;
  message_cn: string;
  suggestion_cn: string;
  source_policy: string;
  source_url?: string;
}

interface ComplianceResult {
  overall_risk_level: string;
  overall_score: number;
  blocked: boolean;
  review_required: boolean;
  violations: ComplianceViolation[];
  rewrite_suggestions?: string[];
  disclaimer_cn?: string;
}

interface DiagnosisResult {
  scores: Scores;
  analysis: Record<string, unknown>;
  suggestions: {
    title_rewrite?: string;
    bullet_points_optimization?: string[];
    backend_keywords_addition?: string[];
    image_suggestions?: string[];
    a_plus_suggestions?: string;
  };
  keyword_coverage: {
    covered_categories?: Record<string, string[]>;
    missing_categories?: Record<string, string[]>;
    coverage_score?: number;
    coverage_summary?: string;
  };
  ad_keywords: {
    high_conversion?: AdKeyword[];
    traffic?: AdKeyword[];
    long_tail?: AdKeyword[];
    negative?: string[];
    ad_summary?: string;
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  elements?: Record<string, Record<string, any>>;
  market_estimates?: MarketEstimates;
  overall_summary: string;
  analyzed_product_name?: string;
  product_mismatch?: boolean;
  product_mismatch_detail?: string;
  id?: number;
  listing_title?: string;
  marketplace?: string;
  data_integrity?: DataIntegrity;
  diagnosis_confidence?: Record<string, ConfidenceItem>;
  causal_diagnosis?: Record<string, any>;
  causal_scores?: Record<string, number>;
  judgment_system?: Record<string, any>;
  ad_validation_plan?: Record<string, any>;
  ad_validation_readiness_gate?: Record<string, any>;
  decision_outputs?: Record<string, any>[];
  amazon_compliance?: ComplianceResult;
 trace?: {
    diagnosis_id?: number;
    cache_hit?: string;
    ai_called?: boolean;
    diagnosis_meta?: {
      schema_version?: string;
      rules_version?: string;
      cache_policy?: string;
      content_fingerprint_short?: string;
    };
    content_fingerprint?: string;
    content_fingerprint_short?: string;
    generated_at?: string;
    frontend_version?: string;
  };
}

interface DiagnosisTaskResponse {
  task_id: string;
  task_type: string;
  status: "pending" | "running" | "completed" | "failed" | string;
  progress_percent?: number;
  result_payload?: DiagnosisResult;
  error_message?: string;
}

const LISTING_DIAGNOSIS_TASK_KEY = "alignx_active_listing_diagnosis_task_id";
const LISTING_DIAGNOSIS_TASK_CONTEXT_KEY = "alignx_active_listing_diagnosis_task_context";

interface ConfidenceItem {
  score: number;
  level: "high" | "medium" | "low" | string;
  label: string;
  reason: string;
}

interface IntegrityCheck {
  key: string;
  label: string;
  weight: number;
  passed: boolean;
  severity: string;
  reason: string;
  recommendation: string;
}

interface DataIntegrity {
  score: number;
  level: "high" | "medium" | "low" | string;
  label: string;
  summary: string;
  source_coverage: Record<string, number>;
  failed_checks: IntegrityCheck[];
  recommendations: string[];
  conclusion_confidence: Record<string, ConfidenceItem>;
}

interface HistoryItem {
  id: number;
  asin?: string;
  listing_title: string;
  marketplace: string;
  scores: Scores;
  created_at: string;
}

type DiagnosisPhase = "idle" | "fetching" | "fetch_success" | "fetch_failed" | "analyzing" | "analyzed" | "error";
type ProductStage = "new_launch" | "mature_listing";

interface PriorityIssue {
  position: string;
  judgement: string;
  impact: "高" | "中" | "低";
  priority: "P0 立即优化" | "P1 建议优化" | "P2 暂不处理";
  action: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const EMPTY_LISTING: ListingInput = {
  title: "",
  bullet_points: "",
  description: "",
  a_plus_content: "",
  backend_keywords: "",
  main_image_description: "",
  category: "",
  price: "",
  brand: "",
  marketplace: "US",
};

const DIMENSIONS: { key: keyof Scores; label: string; labelEn: string; icon: React.ReactNode; color: string; bgColor: string; stroke: string }[] = [
  { key: "function_expression", label: "功能表达", labelEn: "Function", icon: <Zap className="w-4 h-4" />, color: "text-teal-600", bgColor: "bg-teal-500", stroke: "#60A5FA" },
  { key: "scenario_expression", label: "场景表达", labelEn: "Scenario", icon: <MapPin className="w-4 h-4" />, color: "text-emerald-600", bgColor: "bg-emerald-500", stroke: "#34D399" },
  { key: "identity_fit", label: "身份适配", labelEn: "Identity", icon: <Users className="w-4 h-4" />, color: "text-gold-600", bgColor: "bg-gold-500", stroke: "#C084FC" },
  { key: "psychology_benefit", label: "心理利益", labelEn: "Psychology", icon: <Heart className="w-4 h-4" />, color: "text-pink-600", bgColor: "bg-pink-500", stroke: "#F472B6" },
  { key: "risk_elimination", label: "风险消除", labelEn: "Risk", icon: <Shield className="w-4 h-4" />, color: "text-red-600", bgColor: "bg-red-500", stroke: "#F87171" },
  { key: "differentiation", label: "差异化", labelEn: "Differentiation", icon: <Sparkles className="w-4 h-4" />, color: "text-amber-600", bgColor: "bg-amber-500", stroke: "#FBBF24" },
  { key: "product_identity", label: "产品身份", labelEn: "Product ID", icon: <Award className="w-4 h-4" />, color: "text-teal-600", bgColor: "bg-teal-500", stroke: "#22D3EE" },
  { key: "compatibility", label: "兼容搭配", labelEn: "Compatibility", icon: <Globe className="w-4 h-4" />, color: "text-lime-400", bgColor: "bg-lime-500", stroke: "#A3E635" },
  { key: "subjective_properties", label: "主观属性", labelEn: "Subjective", icon: <Star className="w-4 h-4" />, color: "text-rose-400", bgColor: "bg-rose-500", stroke: "#FB7185" },
  { key: "market_trend", label: "市场趋势", labelEn: "Trend", icon: <TrendingUp className="w-4 h-4" />, color: "text-teal-600", bgColor: "bg-teal-500", stroke: "#2DD4BF" },
];

const ELEMENT_META = [
  { key: "title", label: "产品标题", icon: <FileText className="w-4 h-4" /> },
  { key: "bullets", label: "五点描述", icon: <List className="w-4 h-4" /> },
  { key: "images", label: "图片描述", icon: <Image className="w-4 h-4" /> },
  { key: "aplus", label: "A+内容", icon: <Star className="w-4 h-4" /> },
  { key: "backend", label: "Search Terms", icon: <Database className="w-4 h-4" /> },
];

const MODULE_ATTRIBUTION_ORDER: (keyof Scores)[] = [
  "product_identity",
  "function_expression",
  "scenario_expression",
  "compatibility",
  "identity_fit",
  "subjective_properties",
  "psychology_benefit",
  "risk_elimination",
  "differentiation",
  "market_trend",
];

const HEATMAP_DIM_KEYS: { key: keyof ElementDim; label: string; color: string }[] = MODULE_ATTRIBUTION_ORDER.map((key) => {
  const dim = DIMENSIONS.find((item) => item.key === key)!;
  return {
    key: dim.key as keyof ElementDim,
    label: dim.label,
    color: dim.color,
  };
});

type ListingRulerLayer = "买家需求" | "Amazon识别" | "Listing证明" | "市场验证";

const DIMENSION_RULER_META: Record<keyof Scores, {
  layer: ListingRulerLayer;
  intentScale: string;
  platformScale: string;
  ownAction: string;
  impact: string;
}> = {
  function_expression: {
    layer: "买家需求",
    intentScale: "任务对象清晰度 / 决策属性优先级",
    platformScale: "证据可回答性",
    ownAction: "把功能从参数改成用户任务、结果和可验证证据",
    impact: "CTR / CVR / ACOS",
  },
  scenario_expression: {
    layer: "Amazon识别",
    intentScale: "使用场景约束",
    platformScale: "查询意图匹配 / 关系图谱完整度",
    ownAction: "补清使用地点、搭配对象、使用时机和不适用边界",
    impact: "CTR / CPC / 广告词相关性",
  },
  identity_fit: {
    layer: "买家需求",
    intentScale: "任务对象清晰度 / 使用场景约束",
    platformScale: "关系图谱完整度",
    ownAction: "明确谁在什么条件下使用，避免泛人群表达",
    impact: "CTR / CVR / 无效点击率",
  },
  psychology_benefit: {
    layer: "买家需求",
    intentScale: "购买触发强度 / 反购买风险",
    platformScale: "证据可回答性",
    ownAction: "把安心、省事、舒适等心理收益绑定到真实痛点",
    impact: "CVR / 详情页停留 / Review",
  },
  risk_elimination: {
    layer: "买家需求",
    intentScale: "反购买风险",
    platformScale: "证据可回答性",
    ownAction: "补退货、差评、误用、适配失败的证据链",
    impact: "CVR / 退货 / 差评",
  },
  differentiation: {
    layer: "Listing证明",
    intentScale: "决策属性优先级",
    platformScale: "证据可回答性",
    ownAction: "只保留用户会买单的差异，并用图片/五点/A+证明",
    impact: "CTR / CVR / CPC",
  },
  product_identity: {
    layer: "Amazon识别",
    intentScale: "任务对象清晰度",
    platformScale: "类目身份锚定 / 结构化属性完整度",
    ownAction: "校准产品类型、子类目、核心对象和属性词",
    impact: "自然排名 / 广告匹配 / Amazon识别",
  },
  compatibility: {
    layer: "Amazon识别",
    intentScale: "使用场景约束",
    platformScale: "结构化属性完整度 / 关系图谱完整度",
    ownAction: "补 used_with、compatible with、适配/不适配边界",
    impact: "CVR / 退货 / 长尾广告词",
  },
  subjective_properties: {
    layer: "Listing证明",
    intentScale: "购买触发强度 / 决策属性优先级",
    platformScale: "证据可回答性",
    ownAction: "把质感、美观、安静、易用等主观词落到证据",
    impact: "CTR / CVR / Review",
  },
  market_trend: {
    layer: "市场验证",
    intentScale: "购买触发强度",
    platformScale: "查询意图变化",
    ownAction: "只用于发现需求变化，不替代Listing承接主判断",
    impact: "流量机会 / 测试优先级",
  },
};

const TWO_RULER_DIMENSIONS: Record<string, (keyof Scores)[]> = {
  intent: ["function_expression", "scenario_expression", "identity_fit", "psychology_benefit", "risk_elimination", "subjective_properties"],
  platform: ["product_identity", "compatibility", "scenario_expression", "identity_fit", "function_expression"],
  carrier: ["differentiation", "risk_elimination", "subjective_properties", "function_expression", "compatibility"],
  validation: ["market_trend"],
};

/* ------------------------------------------------------------------ */
/*  Marketplace Domain Map                                             */
/* ------------------------------------------------------------------ */

const MARKETPLACE_DOMAINS_MAP: Record<string, string> = {
  US: "www.amazon.com", UK: "www.amazon.co.uk", DE: "www.amazon.de",
  JP: "www.amazon.co.jp", CA: "www.amazon.ca", FR: "www.amazon.fr",
  IT: "www.amazon.it", ES: "www.amazon.es", AU: "www.amazon.com.au",
};

function extractAsinFromUrl(url: string): string {
  const patterns = [/\/dp\/([A-Z0-9]{10})/i, /\/gp\/product\/([A-Z0-9]{10})/i, /\/product\/([A-Z0-9]{10})/i];
  for (const p of patterns) {
    const m = url.match(p);
    if (m) return m[1].toUpperCase();
  }
  // Also accept bare ASIN input (10 alphanumeric chars)
  const trimmed = url.trim();
  if (/^[A-Z0-9]{10}$/i.test(trimmed)) return trimmed.toUpperCase();
  const bare = url.match(/\b([A-Z0-9]{10})\b/);
  if (bare && bare[1].startsWith("B0")) return bare[1];
  return "";
}

function detectMarketplaceFromUrl(url: string): string {
  const map: Record<string, string> = {
    "amazon.com": "US", "amazon.co.jp": "JP", "amazon.de": "DE",
    "amazon.co.uk": "UK", "amazon.fr": "FR", "amazon.it": "IT",
    "amazon.es": "ES", "amazon.ca": "CA", "amazon.com.au": "AU",
  };
  const lower = url.toLowerCase();
  for (const [domain, mp] of Object.entries(map)) {
    if (lower.includes(domain)) return mp;
  }
  return "";
}

function splitBullets(text?: string): string[] {
  if (!text) return [];
  return text
    .split(/\n|；|;/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function hasMeaningfulListingData(listing: ListingInput): boolean {
  return Boolean(listing.title?.trim() || listing.bullet_points?.trim() || listing.description?.trim());
}

function getListingImageCount(listing: ListingInput, fetchMeta?: { image_count?: string } | null): number {
  const raw = fetchMeta?.image_count || listing.image_count || "";
  const parsed = parseInt(String(raw).replace(/[^0-9]/g, ""), 10);
  return Number.isFinite(parsed) ? parsed : 0;
}

function scoreImpact(score: number): "高" | "中" | "低" {
  if (score < 62) return "高";
  if (score < 78) return "中";
  return "低";
}

function scorePriority(score: number): PriorityIssue["priority"] {
  if (score < 62) return "P0 立即优化";
  if (score < 78) return "P1 建议优化";
  return "P2 暂不处理";
}

function buildPriorityIssues(result: DiagnosisResult | null): PriorityIssue[] {
  if (!result?.scores) return [];
  const s = result.scores;
  const rows: Array<{ position: string; score: number; judgement: string; action: string }> = [
    {
      position: "主图",
      score: Math.round(((s.product_identity || 0) + (s.differentiation || 0)) / 2),
      judgement: "判断主图是否能一眼说明产品身份、核心功能和差异化。",
      action: "优先强化主体清晰度、核心差异点和点击承接，不要堆文字。",
    },
    {
      position: "副图",
      score: Math.round(((s.scenario_expression || 0) + (s.risk_elimination || 0) + (s.compatibility || 0)) / 3),
      judgement: "判断副图是否按场景、功能、尺寸、对比、信任和步骤承接转化。",
      action: "补齐缺失图片类型，并按购买决策顺序重新排列副图。",
    },
    {
      position: "标题",
      score: Math.round(((s.product_identity || 0) + (s.function_expression || 0) + (s.scenario_expression || 0)) / 3),
      judgement: "判断标题是否覆盖核心搜索词、产品身份和关键使用场景。",
      action: result.suggestions?.title_rewrite || "把核心关键词前置，保留品牌、属性、规格和适用场景。",
    },
    {
      position: "五点描述",
      score: Math.round(((s.function_expression || 0) + (s.psychology_benefit || 0) + (s.risk_elimination || 0)) / 3),
      judgement: "判断五点是否按买家痛点和购买理由排序，而不是只堆参数。",
      action: "前两条先解决最大犹豫点，再补功能、场景、信任和风险消除。",
    },
    {
      position: "A+ 内容",
      score: Math.round(((s.psychology_benefit || 0) + (s.differentiation || 0) + (s.risk_elimination || 0)) / 3),
      judgement: "判断A+是否承接品牌信任、差异化证明和场景教育。",
      action: typeof result.suggestions?.a_plus_suggestions === "string" ? result.suggestions.a_plus_suggestions : "增加品牌信任、对比证明、场景教育和风险消除模块。",
    },
    {
      position: "价格",
      score: s.market_trend || 0,
      judgement: "判断价格承诺强度是否能被内容、评分和评论支撑。",
      action: "先优化内容承诺和信任证明，再决定是否需要价格测试。",
    },
    {
      position: "评分 / 评论",
      score: s.risk_elimination || 0,
      judgement: "判断评分、评论数和差评风险是否足以支撑下单信任。",
      action: "把保修、认证、安全、售后和真实评价证据补到副图、五点和A+。",
    },
    {
      position: "关键词匹配",
      score: result.keyword_coverage?.coverage_score || s.product_identity || 0,
      judgement: "判断标题、五点、A+和Search Terms是否覆盖真实购买意图。",
      action: "补关系词和状态触发词，广告验证优先测试高意图词。",
    },
    {
      position: "信任证明",
      score: Math.round(((s.risk_elimination || 0) + (s.psychology_benefit || 0)) / 2),
      judgement: "判断Listing是否解释了安全、耐用、售后、认证和真实使用依据。",
      action: "把信任证明放到副图、五点后半段和A+承接模块。",
    },
    {
      position: "场景表达",
      score: s.scenario_expression || 0,
      judgement: "判断表达是否对齐买家的使用场景和触发状态。",
      action: "用具体场景词替代泛泛卖点，并进入广告验证观察CTR/CVR。",
    },
  ];

  return rows
    .map((row) => ({
      position: row.position,
      judgement: row.judgement,
      impact: scoreImpact(row.score),
      priority: scorePriority(row.score),
      action: row.action,
    }))
    .sort((a, b) => {
      const rank = { "P0 立即优化": 0, "P1 建议优化": 1, "P2 暂不处理": 2 };
      return rank[a.priority] - rank[b.priority];
    });
}

function extractTitleSignals(title: string) {
  const lower = String(title || "").toLowerCase();
  const tokens = lower
    .replace(/[^a-z0-9\s+-]/g, " ")
    .split(/\s+/)
    .filter((word) => word.length > 2);
  const stop = new Set(["with", "for", "and", "the", "this", "that", "from", "plus", "edition", "black", "white"]);
  const identity = tokens.filter((word) => !stop.has(word)).slice(0, 5);
  const attributes = [
    ...(lower.match(/\b\d+(\.\d+)?\s?(mah|w|db|inch|inches|oz|lb|ml|l|pack|pcs|piece|pieces)\b/g) || []),
    ...tokens.filter((word) => /(usb|waterproof|quiet|portable|compact|wireless|rechargeable|adjustable|foldable|mini|slim|carbon|filter|compatible)/.test(word)),
  ];
  const scenarios = tokens.filter((word) => /(bedroom|office|travel|outdoor|indoor|apartment|camping|beach|pool|kitchen|bathroom|desk|car|kids|cats|dogs|pet)/.test(word));
  const painStates = tokens.filter((word) => /(odor|smell|ammonia|noise|pain|leak|mess|tracking|dust|safe|sleep|stress|comfort|relief)/.test(word));
  const unique = (items: string[]) => Array.from(new Set(items.map((item) => item.trim()).filter(Boolean))).slice(0, 8);
  return {
    identity: unique(identity),
    attributes: unique(attributes),
    scenarios: unique(scenarios),
    painStates: unique(painStates),
  };
}

function adMetricRead(module: string) {
  const map: Record<string, { metrics: string[]; hypothesis: string; success: string; failure: string }> = {
    title: {
      metrics: ["曝光相关性", "CTR", "CPC", "搜索词精准度"],
      hypothesis: "标题补清产品身份、核心属性和场景关系后，广告进入的搜索词会更准，CTR提升且CPC不恶化。",
      success: "曝光足够后CTR提升，搜索词更集中在目标品类/场景词。",
      failure: "CTR不升或搜索词发散，说明标题语义或广告词池仍错配。",
    },
    main_image: {
      metrics: ["CTR", "CPC", "点击质量"],
      hypothesis: "主图一眼表达产品身份和差异后，同一广告词的CTR会提升。",
      success: "曝光>=1000且点击>=100后CTR提升，CPC不明显上升。",
      failure: "低CTR优先归因为主图点击力或首屏差异不足。",
    },
    secondary_images: {
      metrics: ["CVR", "跳出风险", "ACOS"],
      hypothesis: "副图补齐功能、尺寸、场景、对比和风险证据后，点击后的CVR会提升。",
      success: "CTR稳定时CVR提升、ACOS下降或订单增加。",
      failure: "CTR高CVR低，说明副图/详情页承接不足。",
    },
    bullets: {
      metrics: ["CVR", "订单转化", "ACOS"],
      hypothesis: "五点按购买理由重写后，点击用户更容易被说服下单。",
      success: "同词组CVR提升，订单增加，ACOS下降。",
      failure: "点击成立但转化不升，说明购买理由、价格或评论信任不足。",
    },
    a_plus: {
      metrics: ["CVR", "信任承接", "ACOS"],
      hypothesis: "A+补齐品牌、技术、对比和FAQ信任后，中后段转化更稳。",
      success: "CVR提升且高意图词ACOS下降。",
      failure: "CVR不变，说明A+未解决核心犹豫或用户未进入深度阅读。",
    },
    reviews: {
      metrics: ["CVR", "广告承诺可信度", "退货/差评风险"],
      hypothesis: "把评论痛点转成图片/五点/A+回应后，广告承诺更可信。",
      success: "高意图词CVR提升，差评相关疑虑减少。",
      failure: "CVR不升且评论信任弱，说明承诺强度超过真实证据。",
    },
  };
  return map[module] || map.title;
}

function buildListingHypotheses(result: DiagnosisResult, listing: ListingInput) {
  const titleSignals = extractTitleSignals(listing.title || result.listing_title || result.analyzed_product_name || "");
  const validationItems = Array.isArray(result.ad_validation_plan?.validation_items)
    ? result.ad_validation_plan?.validation_items
    : [];
  const issueByPosition = new Map(buildPriorityIssues(result).map((item) => [item.position, item]));
  const rows = [
    { key: "title", module: "标题", issue: issueByPosition.get("标题") },
    { key: "main_image", module: "主图", issue: issueByPosition.get("主图") },
    { key: "secondary_images", module: "附图", issue: issueByPosition.get("副图") },
    { key: "bullets", module: "五点描述", issue: issueByPosition.get("五点描述") },
    { key: "a_plus", module: "A+图文", issue: issueByPosition.get("A+ 内容") },
    { key: "reviews", module: "评论反馈", issue: issueByPosition.get("评分 / 评论") },
  ];
  const keywordPool = [
    ...(result.ad_keywords?.high_conversion || []),
    ...(result.ad_keywords?.long_tail || []),
    ...(result.ad_keywords?.traffic || []),
  ]
    .map((item) => normalizeAmazonAdKeyword(item.keyword))
    .filter(Boolean);
  return rows.map((row, index) => {
    const read = adMetricRead(row.key);
    const validation = validationItems[index] || validationItems.find((item: any) => String(item.id || "").includes(String(index + 1))) || {};
    const keywords = (
      validation.ad_action?.keywords ||
      validation.ad_test_keywords ||
      keywordPool.slice(index, index + 3) ||
      []
    ).map((kw: string) => normalizeAmazonAdKeyword(kw)).filter(Boolean).slice(0, 4);
    return {
      ...row,
      metrics: read.metrics,
      hypothesis: validation.hypothesis || read.hypothesis,
      success: validation.decision_rules?.[0] || read.success,
      failure: validation.decision_rules?.[2] || read.failure,
      action: validation.suggested_listing_action || row.issue?.action || "补齐该模块和标题语义骨架的一致性，再进入广告验证。",
      priority: row.issue?.priority || "P1 建议优化",
      impact: row.issue?.impact || "中",
      keywords,
      titleSignals,
    };
  });
}

/** Parse plain text pasted from Amazon page into listing fields */
function parseManualPasteText(text: string): {
  title: string;
  brand: string;
  price: string;
  rating: string;
  review_count: string;
  bullet_points: string[];
} {
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  let title = "";
  let brand = "";
  let price = "";
  let rating = "";
  let reviewCount = "";
  const bullets: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Brand detection: "Visit the X Store" or "Brand: X"
    if (!brand && (/^Visit the .+ Store$/i.test(line) || /^Brand:\s*.+/i.test(line))) {
      brand = line.replace(/^Visit the\s+/i, "").replace(/\s+Store$/i, "").replace(/^Brand:\s*/i, "").trim();
      continue;
    }

    // Price detection
    if (!price && /^[$€£¥]\s*[\d,.]+/.test(line)) {
      price = line.match(/[$€£¥]\s*[\d,.]+/)?.[0] || "";
      continue;
    }

    // Rating detection: "4.5 out of 5 stars"
    if (!rating && /[\d.]+\s+out of\s+5\s+stars?/i.test(line)) {
      rating = line.match(/([\d.]+)\s+out of/)?.[1] || "";
      continue;
    }

    // Review count: "1,234 ratings" or "1234 global ratings"
    if (!reviewCount && /[\d,]+\s+(ratings?|reviews?|global ratings?)/i.test(line)) {
      reviewCount = line.match(/([\d,]+)/)?.[1]?.replace(/,/g, "") || "";
      continue;
    }

    // Title: usually the longest line near the top (before bullets)
    if (!title && line.length > 30 && i < 15 && !line.startsWith("›") && !line.startsWith("About this item")) {
      title = line;
      continue;
    }

    // Bullet points: lines after "About this item" or long descriptive lines
    if (line === "About this item") {
      // Collect following lines as bullets
      for (let j = i + 1; j < lines.length && bullets.length < 7; j++) {
        const bl = lines[j];
        if (bl.length > 15 && !bl.startsWith("›") && !/^[$€£¥]/.test(bl)) {
          bullets.push(bl);
        }
        if (bl.length < 5 || /^(Product information|Technical Details|Customers also)/i.test(bl)) break;
      }
      break;
    }
  }

  // If no bullets found via "About this item", try finding long lines
  if (bullets.length === 0) {
    for (const line of lines) {
      if (line.length > 40 && !line.includes("›") && line !== title && bullets.length < 5) {
        bullets.push(line);
      }
    }
  }

  return { title, brand, price, rating, review_count: reviewCount, bullet_points: bullets };
}

const KW_CATEGORY_LABELS: Record<string, string> = {
  core_category: "核心品类词",
  function: "功能词",
  scenario: "场景词",
  audience: "人群词",
  pain_point: "痛点词",
  scenario_problem: "场景问题词",
  long_tail: "长尾需求词",
};

const PRIORITY_COLORS: Record<string, string> = {
  P0: "bg-red-100 text-red-600 border-red-200",
  P1: "bg-amber-100 text-amber-600 border-amber-200",
  P2: "bg-teal-100 text-teal-600 border-teal-200",
};

const COMPETITION_COLORS: Record<string, string> = {
  high: "text-red-600",
  medium: "text-amber-600",
  low: "text-emerald-600",
};

const KEYWORD_TYPE_LABELS: Record<string, string> = {
  attribute: "属性词",
  relationship: "关系词",
  state_trigger: "状态触发词",
};

const KEYWORD_TYPE_BADGES: Record<string, string> = {
  attribute: "bg-gray-100 text-gray-600 border-gray-200",
  relationship: "bg-teal-100 text-teal-600 border-teal-200",
  state_trigger: "bg-gold-100 text-gold-600 border-gold-200",
};

function keywordTypeForUi(keyword: string): "attribute" | "relationship" | "state_trigger" {
  const lower = (keyword || "").toLowerCase();
  if (/(odor|smell|ammonia|pain|relief|anxiety|safe|comfort|leak|tracking|mess|stress|sleep|noise|spill|dust)/.test(lower)) {
    return "state_trigger";
  }
  if (/(for|with|without|under|near|compatible|replacement|indoor|outdoor|apartment|bedroom|travel|kids|women|men|cats|dogs|office)/.test(lower)) {
    return "relationship";
  }
  return "attribute";
}

function normalizeAmazonAdKeyword(keyword: string): string {
  let text = String(keyword || "").trim().toLowerCase();
  if (!text) return "";
  if (/[\u4e00-\u9fff]/.test(text)) {
    const rules: Array<[RegExp, string]> = [
      [/旅行箱.*充电宝|旅行.*充电宝/, "travel power bank"],
      [/适合.*小钱包.*充电器|小钱包.*充电器/, "compact charger for small purse"],
      [/双装.*移动电源.*礼品|移动电源.*礼品/, "power bank gift set"],
      [/口袋型.*超薄.*电池组|超薄.*电池组|口袋型.*电池/, "slim pocket power bank"],
      [/usb\\s*c.*移动电源.*iphone.*三星|移动电源.*iphone.*三星/i, "usb c power bank for iphone and samsung"],
      [/slimmest.*10000mah.*移动电源|10000mah.*移动电源/, "slimmest 10000mah power bank"],
      [/轻型.*飞机.*手机充电器|飞机.*手机充电器/, "lightweight phone charger for flights"],
      [/便携式.*充电器|充电宝|移动电源|手机充电器/, "portable phone power bank"],
      [/泳池.*夹式.*蓝牙|夹式.*蓝牙.*泳池/, "clip on bluetooth speaker for pool"],
      [/夹式.*蓝牙|蓝牙.*夹式/, "clip on bluetooth speaker"],
      [/便携式.*防水.*扬声器.*调频|防水.*扬声器.*调频|fm.*防水.*扬声器/i, "portable waterproof speaker with fm radio"],
      [/迷你.*户外.*音箱.*背带|户外.*音箱.*背带/, "mini outdoor speaker with carrying strap"],
      [/适用于.*海滩.*tws|海滩.*tws.*无线.*扬声器|tws.*海滩/i, "tws speaker for beach trips"],
      [/旅行.*徒步.*淋浴.*音箱|淋浴.*音箱.*旅行|淋浴.*音箱.*徒步/, "shower speaker for hiking and travel"],
      [/沙滩.*专用.*tws|沙滩.*tws.*无线.*音箱/, "tws speaker for beach trips"],
      [/防水.*蓝牙.*音箱|蓝牙.*音箱.*防水/, "waterproof bluetooth speaker"],
      [/防水.*扬声器|扬声器.*防水/, "waterproof speaker"],
      [/便携式.*蓝牙.*音箱|蓝牙.*音箱.*便携式/, "portable bluetooth speaker"],
      [/海滩|沙滩/, "bluetooth speaker for beach trips"],
      [/露营|户外/, "portable speaker for camping"],
      [/泳池|池边/, "poolside bluetooth speaker"],
      [/调频|收音机|fm/i, "bluetooth speaker with fm radio"],
      [/背带|挂绳|肩带/, "portable speaker with carrying strap"],
      [/夹式|夹子/, "clip on speaker"],
      [/淋浴/, "shower speaker"],
      [/徒步/, "speaker for hiking"],
      [/tws/i, "tws bluetooth speaker"],
      [/led|灯|彩灯|灯光|炫彩/, "bluetooth speaker with led lights"],
      [/礼物|送礼|生日/, "bluetooth speaker gift"],
      [/儿童|孩子|男孩|女孩|青少年/, "speaker gift for kids"],
      [/卧室|房间/, "bedroom bluetooth speaker"],
      [/派对|聚会/, "party speaker with lights"],
      [/猫砂.*臭|除臭|异味/, "cat litter box odor control"],
      [/氨气/, "ammonia odor control"],
      [/猫砂.*公寓|公寓.*猫/, "litter box for apartment cats"],
      [/防外溅|追踪|带砂/, "reduce litter tracking"],
    ];
    const converted = rules.find(([pattern]) => pattern.test(text))?.[1];
    if (converted) return converted;
    const englishOnly = text.replace(/[\u4e00-\u9fff]+/g, " ");
    text = englishOnly;
  }
  const replacements: Record<string, string> = {
    odour: "odor",
    colour: "color",
    favourite: "favorite",
    travelling: "traveling",
    jewellery: "jewelry",
  };
  Object.entries(replacements).forEach(([from, to]) => {
    text = text.replace(new RegExp(`\\b${from}\\b`, "g"), to);
  });
  text = text.replace(/[^a-z0-9 +&/-]/g, " ").replace(/\s+/g, " ").trim();
  const normalized = text.split(" ").slice(0, 8).join(" ");
  return /[a-z]/.test(normalized) ? normalized : "";
}

function deriveAmericanAdKeywords(title: string, group: "high_conversion" | "traffic" | "long_tail"): AdKeyword[] {
  const text = String(title || "").toLowerCase();
  const out: AdKeyword[] = [];
  const push = (keyword: string, keyword_type: AdKeyword["keyword_type"], priority: "P0" | "P1" | "P2", competition: "high" | "medium" | "low") => {
    out.push({
      keyword,
      keyword_type,
      match_type: keyword_type === "attribute" ? "exact" : "phrase",
      intent: keyword_type === "attribute" ? "基础品类覆盖" : "验证关系词/状态触发词是否带来精准点击和转化",
      competition,
      priority,
    });
  };

  if (/bluetooth|speaker|boombox|wireless speaker/.test(text)) {
    if (group === "high_conversion") {
      push("waterproof bluetooth speaker for beach", "relationship", "P0", "medium");
      push("portable speaker for camping", "relationship", "P0", "medium");
      push("bluetooth speaker with led lights gift", "relationship", "P0", "medium");
    } else if (group === "traffic") {
      push("portable bluetooth speaker", "attribute", "P2", "high");
      push("waterproof speaker", "attribute", "P2", "high");
    } else {
      push("small speaker for poolside music", "state_trigger", "P1", "low");
      push("outdoor party bluetooth speaker lights", "state_trigger", "P1", "medium");
    }
  } else if (/cat|litter/.test(text)) {
    if (group === "high_conversion") {
      push("cat litter box odor control", "state_trigger", "P0", "medium");
      push("litter box for apartment cats", "relationship", "P0", "medium");
    } else if (group === "traffic") {
      push("cat litter box", "attribute", "P2", "high");
    } else {
      push("reduce litter tracking enclosed box", "state_trigger", "P1", "low");
    }
  }

  return out;
}

function sanitizeAdKeywordList(
  keywords: AdKeyword[] | undefined,
  title: string,
  group: "high_conversion" | "traffic" | "long_tail"
): AdKeyword[] {
  const clean = (keywords || [])
    .map((kw) => {
      const keyword = normalizeAmazonAdKeyword(kw.keyword);
      if (!keyword) return null;
      return {
        ...kw,
        keyword,
        keyword_type: kw.keyword_type || keywordTypeForUi(keyword),
        intent: /[\u4e00-\u9fff]/.test(String(kw.intent || "")) ? "Validate search intent and conversion fit" : kw.intent,
      } as AdKeyword;
    })
    .filter(Boolean) as AdKeyword[];
  return clean.length > 0 ? clean : deriveAmericanAdKeywords(title, group);
}

const CONFIDENCE_LABELS: Record<string, string> = {
  review_alignment: "评论需求对齐",
  platform_semantic_alignment: "平台语义对齐",
  causal_conversion_alignment: "因果转化对齐",
};

/* ------------------------------------------------------------------ */
/*  Market Validation Scoring Logic                                    */
/* ------------------------------------------------------------------ */

function getSalesTier(monthlySales: number): { tier: string; label: string; multiplier: number } {
  if (monthlySales >= 5000) return { tier: "S", label: "爆款 (5000+)", multiplier: 1.0 };
  if (monthlySales >= 500) return { tier: "A", label: "热销 (500-5000)", multiplier: 0.75 };
  if (monthlySales >= 50) return { tier: "B", label: "稳定 (50-500)", multiplier: 0.50 };
  return { tier: "C", label: "新品/低销 (<50)", multiplier: 0.25 };
}

function calcReviewScore(reviewCount: number): number {
  if (reviewCount <= 0) return 0;
  const logVal = Math.log10(reviewCount + 1);
  return Math.min(100, Math.round(logVal * 20));
}

function calcRatingScore(rating: number): number {
  if (rating <= 0) return 0;
  return Math.min(100, Math.round(Math.max(0, (rating - 1) / 4 * 100)));
}

function calcBsrScore(bsrRank: number): number {
  if (bsrRank <= 0) return 0;
  if (bsrRank <= 100) return 100;
  if (bsrRank <= 500) return 90;
  if (bsrRank <= 1000) return 80;
  if (bsrRank <= 5000) return 65;
  if (bsrRank <= 10000) return 50;
  if (bsrRank <= 50000) return 35;
  if (bsrRank <= 100000) return 20;
  return 10;
}

function calcMarketValidation(data: {
  review_count: number;
  rating: number;
  estimated_monthly_sales: number;
  bsr_rank: number;
}): MarketValidation {
  const reviewScore = calcReviewScore(data.review_count);
  const ratingScore = calcRatingScore(data.rating);
  const salesTierInfo = getSalesTier(data.estimated_monthly_sales);
  const salesTierScore = salesTierInfo.multiplier * 100;
  const bsrScore = calcBsrScore(data.bsr_rank);
  const marketTotal = Math.round(
    reviewScore * 0.25 + ratingScore * 0.20 + salesTierScore * 0.35 + bsrScore * 0.20
  );

  let analysis = "";
  if (marketTotal >= 80) analysis = "市场表现优秀，产品已获得充分的市场验证。";
  else if (marketTotal >= 60) analysis = "市场表现良好，仍有提升空间。";
  else if (marketTotal >= 40) analysis = "市场表现一般，需关注评价积累和销量提升。";
  else analysis = "市场验证不足，建议优先积累初始销量和评价。";

  return {
    review_score: reviewScore,
    rating_score: ratingScore,
    sales_tier: salesTierInfo.label,
    sales_tier_score: salesTierScore,
    bsr_score: bsrScore,
    market_total: marketTotal,
    review_count_raw: data.review_count,
    rating_raw: data.rating,
    estimated_monthly_sales: data.estimated_monthly_sales,
    bsr_rank: data.bsr_rank,
    analysis,
  };
}

function parseMetricInt(value?: string | number | null): number {
  if (value === undefined || value === null) return 0;
  const match = String(value).replace(/,/g, "").match(/\d+/);
  return match ? Number(match[0]) || 0 : 0;
}

function parseMetricFloat(value?: string | number | null): number {
  if (value === undefined || value === null) return 0;
  const match = String(value).replace(/,/g, "").match(/\d+(?:\.\d+)?/);
  return match ? Number(match[0]) || 0 : 0;
}

function deriveMarketValidationFromEvidence(
  listing: ListingInput,
  meta?: FetchMeta | null,
  estimates?: MarketEstimates
): MarketValidation {
  const reviewCount = parseMetricInt(meta?.review_count || listing.review_count);
  const rating = parseMetricFloat(meta?.rating || listing.rating);
  const bsrRank = parseMetricInt(meta?.bsr_rank || listing.bsr_rank);
  const hasRealMarketEvidence = reviewCount > 0 || rating > 0 || bsrRank > 0;

  if (hasRealMarketEvidence) {
    const estimatedSales = reviewCount > 0 ? Math.round(reviewCount * 0.15) : 0;
    return calcMarketValidation({
      review_count: reviewCount,
      rating,
      estimated_monthly_sales: estimatedSales,
      bsr_rank: bsrRank,
    });
  }

  const estimatedSales = Number(estimates?.estimated_monthly_sales || 0);
  const estimatedBsr = Number(estimates?.estimated_bsr_rank || 0);
  if (estimatedSales > 0 || estimatedBsr > 0) {
    return calcMarketValidation({
      review_count: estimatedSales > 0 ? Math.round(estimatedSales * 3) : 0,
      rating,
      estimated_monthly_sales: estimatedSales,
      bsr_rank: estimatedBsr,
    });
  }

  return calcMarketValidation({
    review_count: 0,
    rating: 0,
    estimated_monthly_sales: 0,
    bsr_rank: 0,
  });
}

function buildManualCaptureQuality(parsed: {
  title?: string;
  price?: string;
  rating?: string;
  review_count?: string;
  bullet_points?: string[];
}): FetchMeta["capture_quality"] {
  const missingCore: string[] = [];
  const missingStrategy: string[] = [];
  const bulletCount = (parsed.bullet_points || []).filter((item) => String(item).trim()).length;

  if (!parsed.title?.trim()) missingCore.push("标题");
  missingCore.push("主图/图片");
  if (bulletCount < 3) missingCore.push("五点描述不足3条");
  else if (bulletCount < 5) missingStrategy.push("五点描述不足5条");

  if (!hasRequiredPrice(parsed.price || "")) missingStrategy.push("价格");
  if (!parsed.rating?.trim()) missingStrategy.push("评分");
  if (!parsed.review_count?.trim()) missingStrategy.push("评论数");
  missingStrategy.push("BSR排名", "低星评论", "评分分布", "A+内容", "库存/可售状态");

  const coreTotal = 3;
  const coreScore = Math.max(0, Math.round(((coreTotal - missingCore.length) / coreTotal) * 100));
  const strategyTotal = 8;
  const strategyScore = Math.max(0, Math.round(((strategyTotal - missingStrategy.length) / strategyTotal) * 100));
  const completeness = Math.round(coreScore * 0.7 + strategyScore * 0.3);
  const allowFormalDiagnosis = missingCore.length === 0 && Boolean(parsed.title?.trim());

  return {
    source_confidence: "medium",
    completeness,
    core_score: coreScore,
    strategy_score: strategyScore,
    missing_core: missingCore,
    missing_strategy: missingStrategy,
    allow_formal_diagnosis: allowFormalDiagnosis,
    allow_strategy_diagnosis: allowFormalDiagnosis && strategyScore >= 60,
    confidence_level: allowFormalDiagnosis ? "medium" : "low",
    rule: "承接诊断只卡Listing证据；市场数据缺失不得自动猜测，会降低置信度。",
  };
}

function hasRequiredText(value?: string | number | null): boolean {
  const text = String(value ?? "").trim();
  if (!text || ["-", "—", "N/A", "n/a", "NA", "待确认", "未提供", "未知"].includes(text)) return false;
  return true;
}

function hasRequiredPrice(value?: string | null): boolean {
  const text = String(value ?? "").trim();
  return hasRequiredText(text) && /\d/.test(text);
}

function normalizeListingStandardLabel(value: string): string {
  if (["标题", "产品标题", "标题关键词"].includes(value)) return "标题关键词";
  if (["主图/图片", "主图", "图片", "主图/副图"].includes(value)) return "主图/副图";
  if (["五点描述不足3条", "五点描述", "五点"].includes(value)) return "五点";
  if (["Search Terms", "后台Search Terms", "后台关键词"].includes(value)) return "后台关键词";
  return value;
}

function resolveFormalGateMissing(listing: ListingInput, meta?: FetchMeta | null): string[] {
  const listingCoreLabels = new Set(["标题关键词", "主图/副图", "五点"]);
  const missing = new Set<string>(
    (meta?.capture_quality?.missing_core || [])
      .map(normalizeListingStandardLabel)
      .filter((item) => listingCoreLabels.has(item))
  );
  const imageCount = getListingImageCount(listing, meta);
  const bulletCount = splitBullets(listing.bullet_points).length;

  const sync = (label: string, present: boolean) => {
    if (present) missing.delete(label);
    else missing.add(label);
  };

  sync("标题关键词", hasRequiredText(listing.title));
  sync("主图/副图", imageCount > 0 || Boolean(listing.image_urls?.length));
  if (bulletCount < 3) missing.add("五点");
  else missing.delete("五点");

  return Array.from(missing).filter(Boolean);
}

function resolveListingStandardMissing(listing: ListingInput, meta?: FetchMeta | null): string[] {
  const missing = new Set<string>(resolveFormalGateMissing(listing, meta));
  if (!(listing.has_a_plus || meta?.has_a_plus || hasRequiredText(listing.a_plus_content))) {
    missing.add("A+");
  }
  if (!hasRequiredText(listing.backend_keywords)) {
    missing.add("后台关键词");
  }
  return Array.from(missing).filter(Boolean);
}

function resolveMarketEvidenceMissing(listing: ListingInput, meta?: FetchMeta | null): string[] {
  const missing: string[] = [];
  const rating = meta?.rating || listing.rating;
  const reviewCount = meta?.review_count || listing.review_count;
  const bsrRank = meta?.bsr_rank || listing.bsr_rank;
  if (!hasRequiredPrice(listing.price)) missing.push("价格");
  if (!hasRequiredText(rating)) missing.push("评分");
  if (!hasRequiredText(reviewCount)) missing.push("评论数");
  if (!hasRequiredText(bsrRank)) missing.push("BSR排名");
  return missing;
}

function isNewLaunchListing(listing: ListingInput, meta?: FetchMeta | null): boolean {
  const reviewCount = meta?.review_count || listing.review_count;
  const bsrRank = meta?.bsr_rank || listing.bsr_rank;
  const missingReviews = !hasRequiredText(reviewCount) || parseMetricInt(reviewCount) === 0;
  const missingSales = !hasRequiredText(bsrRank) || parseMetricInt(bsrRank) === 0;
  return missingReviews && missingSales;
}

function resolveProductStage(listing: ListingInput, meta?: FetchMeta | null, override?: ProductStage | null): ProductStage {
  if (override) return override;
  return isNewLaunchListing(listing, meta) ? "new_launch" : "mature_listing";
}

function diagnosisModeForStage(stage: ProductStage): "new_launch_readiness" | "listing_conversion_readiness" {
  return stage === "new_launch" ? "new_launch_readiness" : "listing_conversion_readiness";
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function getAvgScore(scores: Scores): number {
  const vals = Object.values(scores).filter((v) => typeof v === "number" && !isNaN(v));
  if (vals.length === 0) return 0;
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
}

/**
 * Normalize backend element attribution keys to the 10 diagnosis dimensions.
 * Aliases keep older saved diagnoses readable.
 */
function normalizeElementDims(ed: Record<string, unknown>): ElementDim {
  return {
    function_expression: Number(ed.function_expression ?? ed.functional) || 0,
    scenario_expression: Number(ed.scenario_expression ?? ed.scenario) || 0,
    identity_fit: Number(ed.identity_fit ?? ed.persona) || 0,
    psychology_benefit: Number(ed.psychology_benefit ?? ed.motivation) || 0,
    risk_elimination: Number(ed.risk_elimination) || 0,
    product_identity: Number(ed.product_identity ?? ed.product_id) || 0,
    compatibility: Number(ed.compatibility ?? ed.compat) || 0,
    subjective_properties: Number(ed.subjective_properties ?? ed.subjective) || 0,
    differentiation: Number(ed.differentiation ?? ed.competitive) || 0,
    market_trend: Number(ed.market_trend ?? ed.market) || 0,
  };
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-600";
  if (score >= 60) return "text-amber-600";
  return "text-red-600";
}

function scoreBgColor(score: number): string {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-amber-500";
  return "bg-red-500";
}

function averageScoresByKeys(scores: Scores, keys: (keyof Scores)[]): number {
  const values = keys.map((key) => Number(scores[key]) || 0).filter((value) => value > 0);
  if (values.length === 0) return 0;
  return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);
}

function getTwoRulerScoreCards(scores: Scores, marketScore?: number) {
  const validationScore = typeof marketScore === "number" && marketScore > 0
    ? Math.round((averageScoresByKeys(scores, TWO_RULER_DIMENSIONS.validation) + marketScore) / 2)
    : averageScoresByKeys(scores, TWO_RULER_DIMENSIONS.validation);
  return [
    {
      key: "intent",
      title: "需求承接",
      score: averageScoresByKeys(scores, TWO_RULER_DIMENSIONS.intent),
      desc: "用户真实任务、购买触发、场景约束、决策属性和反购买风险。",
    },
    {
      key: "platform",
      title: "Amazon识别",
      score: averageScoresByKeys(scores, TWO_RULER_DIMENSIONS.platform),
      desc: "Amazon能否识别类目身份、查询意图、结构化属性和关系图谱。",
    },
    {
      key: "carrier",
      title: "Listing承接",
      score: averageScoresByKeys(scores, TWO_RULER_DIMENSIONS.carrier),
      desc: "标题、图片、五点、A+、评论是否证明同一件事。",
    },
    {
      key: "validation",
      title: "验证参考",
      score: validationScore,
      desc: "市场趋势、关键词和广告数据只做验证，不替代承接判断。",
    },
  ];
}

function TwoRulerSummary({ scores, marketScore }: { scores: Scores; marketScore?: number }) {
  const cards = getTwoRulerScoreCards(scores, marketScore);
  return (
    <Card className="bg-white border-brand-100">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Shield className="w-4 h-4 text-brand-600" />
          Listing承接诊断
        </CardTitle>
        <p className="text-xs text-gray-500">
          先看买家需求和Amazon识别，再反查标题、图片、五点、A+与广告验证是否形成闭环。
        </p>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          {cards.map((card) => (
            <div key={card.key} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-gray-900">{card.title}</p>
                <span className={`text-lg font-bold ${scoreColor(card.score)}`}>{card.score}</span>
              </div>
              <div className="mt-2 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                <div className={`h-full rounded-full ${scoreBgColor(card.score)}`} style={{ width: `${card.score}%` }} />
              </div>
              <p className="mt-2 text-xs text-gray-500 leading-relaxed">{card.desc}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function getGradeColor(g: string): string {
  return g === "A" ? "#10B981" : g === "B" ? "#3B82F6" : g === "C" ? "#F59E0B" : "#EF4444";
}

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success("已复制");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      toast.success("已复制");
      setTimeout(() => setCopied(false), 2000);
    }
  };
  return (
    <button onClick={handleCopy} className="text-gray-500 hover:text-gray-900 transition-colors p-1">
      {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  Radar Chart (from HealthReport)                                    */
/* ------------------------------------------------------------------ */

function RadarChart({ scores, size = 220 }: { scores: { label: string; value: number; color: string }[]; size?: number }) {
  const cx = size / 2, cy = size / 2, r = size * 0.32;  // 🟢 减小图表半径，给标签留出更多空间
  const n = scores.length;
  const levels = [20, 40, 60, 80, 100];
  const pt = (i: number, v: number) => {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    return { x: cx + (v / 100) * r * Math.cos(a), y: cy + (v / 100) * r * Math.sin(a) };
  };
  const lbl = (i: number) => {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    const labelDistance = r + 28;  // 🟢 增加标签距离，避免重叠
    return { 
      x: cx + labelDistance * Math.cos(a), 
      y: cy + labelDistance * Math.sin(a),
      anchor: Math.abs(a) < 0.1 || Math.abs(Math.abs(a) - Math.PI) < 0.1 
        ? "middle" 
        : Math.cos(a) > 0 ? "start" : "end"
    };
  };
  const poly = scores.map((s, i) => { const p2 = pt(i, s.value); return `${p2.x},${p2.y}`; }).join(" ");

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* 背景网格 */}
      {levels.map((l) => (<polygon key={l} points={Array.from({ length: n }, (_, i) => { const p2 = pt(i, l); return `${p2.x},${p2.y}`; }).join(" ")} fill="none" stroke="rgba(100,100,120,0.15)" strokeWidth="1" />))}
      {/* 轴线 */}
      {scores.map((_, i) => { const p2 = pt(i, 100); return <line key={i} x1={cx} y1={cy} x2={p2.x} y2={p2.y} stroke="rgba(100,100,120,0.15)" strokeWidth="1" />; })}
      {/* 数据多边形 */}
      <polygon points={poly} fill="rgba(99,102,241,0.15)" stroke="#0f2a24" strokeWidth="2" />
      {/* 数据点 */}
      {scores.map((s, i) => { const p2 = pt(i, s.value); return <circle key={i} cx={p2.x} cy={p2.y} r="4" fill={s.color} />; })}
      {/* 🟢 维度标签（修复：确保所有10个维度都有标注） */}
      {scores.map((s, i) => { 
        const p2 = lbl(i); 
        return (
          <g key={i}>
            <text 
              x={p2.x} 
              y={p2.y} 
              textAnchor={p2.anchor} 
              dominantBaseline="middle" 
              fill="#374151"  // 深色文字
              fontSize="10" 
              fontWeight="700"
            >
              {s.label}
            </text>
            {/* 标签旁边显示分数 */}
            <text 
              x={p2.x} 
              y={p2.y + 14} 
              textAnchor={p2.anchor} 
              dominantBaseline="middle" 
              fill={s.color} 
              fontSize="9" 
              fontWeight="600"
            >
              {s.value}
            </text>
          </g>
        ); 
      })}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Heatmap Cell                                                       */
/* ------------------------------------------------------------------ */

function HeatmapCell({ value }: { value: number }) {
  const bg = value >= 80 ? "bg-emerald-500/60" : value >= 60 ? "bg-teal-500/50" : value >= 40 ? "bg-amber-500/50" : value >= 20 ? "bg-orange-500/50" : "bg-red-500/50";
  return (
    <div className={`w-full h-8 rounded flex items-center justify-center text-[10px] font-bold ${bg} text-gray-900`}>
      {value}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Market Validation Panel                                            */
/* ------------------------------------------------------------------ */

function MarketValidationPanel({ mv }: { mv: MarketValidation }) {
  const factors = [
    { label: "评论数", icon: <MessageSquare className="w-3.5 h-3.5" />, score: mv.review_score, detail: `${mv.review_count_raw.toLocaleString()} 条`, weight: "25%", color: "text-teal-600", bg: "bg-teal-500" },
    { label: "评分", icon: <Star className="w-3.5 h-3.5" />, score: mv.rating_score, detail: `${mv.rating_raw.toFixed(1)} / 5.0`, weight: "20%", color: "text-yellow-600", bg: "bg-yellow-500" },
    { label: "销量级别", icon: <ShoppingCart className="w-3.5 h-3.5" />, score: mv.sales_tier_score, detail: mv.sales_tier, weight: "35%", color: "text-emerald-600", bg: "bg-emerald-500" },
    { label: "BSR排名", icon: <Award className="w-3.5 h-3.5" />, score: mv.bsr_score, detail: mv.bsr_rank > 0 ? `#${mv.bsr_rank.toLocaleString()}` : "未知", weight: "20%", color: "text-orange-600", bg: "bg-orange-500" },
  ];
  const tierColor = mv.market_total >= 80 ? "text-emerald-600" : mv.market_total >= 60 ? "text-teal-600" : mv.market_total >= 40 ? "text-amber-600" : "text-red-600";
  const tierBg = mv.market_total >= 80 ? "from-emerald-600" : mv.market_total >= 60 ? "from-teal-600" : mv.market_total >= 40 ? "from-amber-600" : "from-red-600";

  return (
    <Card className="bg-gray-50 border-gray-200 p-5">
      <div className="flex items-center gap-2 mb-4">
        <BarChart3 className="w-4 h-4 text-brand-600" />
        <p className="text-sm font-semibold text-gray-600">市场验证指标</p>
        <span className="text-[10px] text-gray-600 ml-auto">权重 35%</span>
      </div>
      <div className={`bg-gradient-to-r ${tierBg} to-transparent/10 rounded-lg p-3 mb-4`}>
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-900/80">市场验证总分</span>
          <span className={`text-2xl font-bold ${tierColor}`}>{mv.market_total}</span>
        </div>
        <div className="w-full h-1.5 bg-brand-50 rounded-full mt-2 overflow-hidden">
          <div className={`h-full rounded-full transition-all duration-1000 ${mv.market_total >= 80 ? "bg-emerald-400" : mv.market_total >= 60 ? "bg-teal-400" : mv.market_total >= 40 ? "bg-amber-400" : "bg-red-400"}`} style={{ width: `${mv.market_total}%` }} />
        </div>
      </div>
      <div className="space-y-3">
        {factors.map((f) => (
          <div key={f.label}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className={`flex items-center gap-1.5 ${f.color}`}>
                {f.icon} {f.label}
                <span className="text-gray-600">({f.weight})</span>
              </span>
              <div className="flex items-center gap-2">
                <span className="text-gray-500 text-[10px]">{f.detail}</span>
                <span className="font-semibold text-gray-900 w-7 text-right">{f.score}</span>
              </div>
            </div>
            <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div className={`h-full rounded-full transition-all duration-700 ${f.bg}`} style={{ width: `${f.score}%`, opacity: 0.7 }} />
            </div>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-gray-500 mt-3 leading-relaxed">{mv.analysis}</p>
    </Card>
  );
}

function PrecisionConfidencePanel({ integrity }: { integrity?: DataIntegrity }) {
  if (!integrity) return null;
  const levelColor = integrity.level === "high" ? "text-emerald-600" : integrity.level === "medium" ? "text-amber-600" : "text-red-600";
  const levelBg = integrity.level === "high" ? "bg-emerald-100 border-emerald-200" : integrity.level === "medium" ? "bg-amber-100 border-amber-200" : "bg-red-100 border-red-200";
  const sourceLabels: Record<string, string> = {
    listing: "Listing",
    review: "评论",
    competitor: "竞品",
    advertising: "广告",
  };
  const confidence = integrity.conclusion_confidence || {};

  return (
    <Card className="bg-gray-50 border-gray-200">
      <CardContent className="pt-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="w-4 h-4 text-brand-600" />
              <h3 className="text-lg font-bold text-gray-900">数据完整性与判断置信度</h3>
              <Badge className={`${levelBg} ${levelColor} border`}>置信度 {integrity.label}</Badge>
            </div>
            <p className="text-sm text-gray-500 leading-relaxed">{integrity.summary}</p>
          </div>
          <div className="shrink-0 text-right">
            <p className={`text-3xl font-bold ${levelColor}`}>{integrity.score}</p>
            <p className="text-xs text-gray-500">完整性 / 100</p>
          </div>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-5">
          {Object.entries(integrity.source_coverage || {}).map(([key, value]) => (
            <div key={key} className="rounded-lg border border-gray-100 bg-white p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-500">{sourceLabels[key] || key}</span>
                <span className={`text-xs font-bold ${scoreColor(value)}`}>{value}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                <div className={`h-full rounded-full ${scoreBgColor(value)}`} style={{ width: `${value}%` }} />
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mt-4">
          {Object.entries(confidence).map(([key, item]) => (
            <div key={key} className="rounded-lg border border-gray-100 bg-white p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-gray-700">{CONFIDENCE_LABELS[key] || key}</span>
                <Badge variant="outline" className={item.level === "high" ? "text-emerald-600 border-emerald-200" : item.level === "medium" ? "text-amber-600 border-amber-200" : "text-red-600 border-red-200"}>
                  {item.label}
                </Badge>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${scoreBgColor(item.score)}`} style={{ width: `${item.score}%` }} />
                </div>
                <span className={`text-xs font-bold ${scoreColor(item.score)}`}>{item.score}</span>
              </div>
              <p className="text-[11px] text-gray-500 mt-2 leading-relaxed">{item.reason}</p>
            </div>
          ))}
        </div>

        {integrity.failed_checks?.length > 0 && (
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
            <p className="text-xs font-semibold text-amber-700 mb-2">优先补齐的数据</p>
            <div className="flex flex-wrap gap-2">
              {integrity.failed_checks.slice(0, 6).map((check) => (
                <Badge key={check.key} variant="outline" className="bg-white text-amber-700 border-amber-200">
                  {check.label}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AmazonCompliancePanel({ compliance }: { compliance?: ComplianceResult }) {
  const violations = compliance?.violations || [];
  if (!compliance || violations.length === 0) return null;

  const tone = compliance.blocked
    ? {
        card: "bg-red-50 border-red-200",
        icon: "text-red-600",
        badge: "border-red-200 text-red-700 bg-white",
      }
    : {
        card: "bg-amber-50 border-amber-200",
        icon: "text-amber-600",
        badge: "border-amber-200 text-amber-700 bg-white",
      };

  return (
    <Card className={tone.card}>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className={`w-5 h-5 ${tone.icon} mt-0.5`} />
            <div>
              <h3 className="text-lg font-bold text-gray-900">上架前合规检查</h3>
              <p className="text-xs text-gray-600 mt-1">
                {compliance.disclaimer_cn || "系统检测到该内容可能存在亚马逊合规风险，建议修改后再发布。"}
              </p>
            </div>
          </div>
          <Badge variant="outline" className={tone.badge}>
            {compliance.overall_risk_level} · {compliance.overall_score}
          </Badge>
        </div>
        <div className="space-y-3">
          {violations.slice(0, 5).map((item) => (
            <div key={`${item.rule_id}-${item.module}`} className="rounded-lg border border-white bg-white p-3">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <Badge variant="outline" className="text-xs">{item.module}</Badge>
                <Badge variant="outline" className="text-xs">{item.rule_type}</Badge>
                <span className="text-xs font-semibold text-gray-500">{item.risk_score}/100</span>
                <span className="text-xs text-gray-400">{item.rule_id}</span>
              </div>
              <p className="text-sm font-semibold text-gray-800">{item.message_cn}</p>
              <p className="text-xs text-gray-600 mt-1">{item.suggestion_cn}</p>
              {item.source_policy && (
                <p className="text-[11px] text-gray-400 mt-2">依据：{item.source_policy}</p>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function BackendJudgmentPanel({ result }: { result: DiagnosisResult }) {
  const judgment = result.judgment_system || {};
  const judgmentSections = (judgment.sections || {}) as Record<string, any>;
  const decisionOutputs = Array.isArray(result.decision_outputs)
    ? result.decision_outputs
    : Array.isArray(judgmentSections.decision_outputs)
      ? judgmentSections.decision_outputs
      : [];
  const advertisingDecision = decisionOutputs.find((item: any) => item?.domain === "advertising_validation") as any;
  const validationGate = result.ad_validation_readiness_gate || advertisingDecision?.validation_gate || {};
  const alignment = (judgment.alignment_scores || {}) as Record<string, number>;
  const causal = result.causal_diagnosis || {};
  const keywordCausality = (causal.keyword_causality || {}) as Record<string, any>;
  const items = [
    { key: "review_alignment", label: "购买理由", score: alignment.review_alignment ?? result.diagnosis_confidence?.review_alignment?.score },
    { key: "platform_semantic_alignment", label: "Amazon识别", score: alignment.platform_semantic_alignment ?? result.diagnosis_confidence?.platform_semantic_alignment?.score },
    { key: "causal_conversion_alignment", label: "页面承接", score: alignment.causal_conversion_alignment ?? result.diagnosis_confidence?.causal_conversion_alignment?.score ?? result.causal_scores?.overall_causal_score },
    { key: "keyword_validation_readiness", label: "验证准备", score: keywordCausality.readiness_score ?? result.causal_scores?.keyword_validation_readiness },
  ].filter((item) => item.score !== undefined);

  if (items.length === 0 && !causal.summary && decisionOutputs.length === 0) return null;

  return (
    <Card className="bg-brand-50 border-brand-100">
      <CardContent className="pt-6">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-brand-600" />
              <h3 className="text-lg font-bold text-gray-900">诊断判断</h3>
            </div>
          </div>
          <Badge variant="outline" className="border-brand-200 text-brand-600">已计算</Badge>
        </div>
        {decisionOutputs.length > 0 && (
          <div className="mb-4 rounded-xl border border-brand-100 bg-white p-4">
            <div className="flex items-start justify-between gap-3 mb-3">
              <div>
                <p className="text-sm font-bold text-gray-900">决策输出</p>
              </div>
            </div>
            {validationGate?.gate && (
              <div className="mb-3 rounded-lg border border-amber-100 bg-amber-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-xs font-semibold text-amber-800">广告验证准入</p>
                    <p className="mt-1 text-sm font-bold text-gray-900">{formatAnalysisText(validationGate.status)}</p>
                  </div>
                  <Badge variant="outline" className="border-amber-200 bg-white text-amber-700">
                    {validationGate.product_stage === "new_launch" ? "新品门槛" : "成熟品门槛"} · {Math.round(Number(validationGate.listing_conversion_score || 0))}/{validationGate.threshold}
                  </Badge>
                </div>
                <p className="mt-2 text-xs text-gray-600 leading-relaxed">{formatAnalysisText(validationGate.budget_policy)}</p>
                {Array.isArray(validationGate.blocking_reasons) && validationGate.blocking_reasons.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {validationGate.blocking_reasons.map((reason: string) => (
                      <Badge key={reason} variant="outline" className="border-red-200 bg-white text-red-700 text-[10px]">
                        {reason}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            )}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {decisionOutputs.slice(0, 6).map((item: any, idx: number) => {
                const seller = getSellerFacingDecision(item);
                const confidence = Math.round(Number(seller.confidence || item.confidence_score || item.score || 0));
                return (
                  <div key={`${item.domain || idx}`} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold text-brand-700">{formatAnalysisText(seller.title)}</p>
                        <p className="mt-1 text-sm font-bold text-gray-900">{formatAnalysisText(seller.judgment)}</p>
                      </div>
                      <span className={`text-sm font-bold ${scoreColor(confidence)}`}>{confidence}%</span>
                    </div>
                    {seller.basis && (
                      <p className="mt-2 text-xs text-gray-600 leading-relaxed">
                        <span className="font-semibold text-gray-900">原因：</span>{formatAnalysisText(seller.basis)}
                      </p>
                    )}
                    <p className="mt-2 text-xs text-gray-600 leading-relaxed">
                      <span className="font-semibold text-gray-900">动作：</span>{formatAnalysisText(seller.action)}
                    </p>
                    <p className="mt-1 text-[11px] text-gray-500 leading-relaxed">
                      <span className="font-semibold">风险：</span>{formatAnalysisText(seller.risk)}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        )}
        {items.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {items.map((item) => {
              const score = Math.round(Number(item.score || 0));
              return (
                <div key={item.key} className="rounded-lg border border-white bg-white p-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-gray-700">{item.label}</span>
                    <span className={`font-bold ${scoreColor(score)}`}>{score}</span>
                  </div>
                  <div className="mt-2 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                    <div className={`h-full rounded-full ${scoreBgColor(score)}`} style={{ width: `${score}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {causal.summary && <p className="mt-3 text-xs text-gray-600 leading-relaxed">{String(causal.summary)}</p>}
      </CardContent>
    </Card>
  );
}

function ListingHypothesisLoopPanel({ result, listing }: { result: DiagnosisResult; listing: ListingInput }) {
  const rows = buildListingHypotheses(result, listing);
  const signals = rows[0]?.titleSignals || extractTitleSignals(listing.title || result.listing_title || "");
  const signalBlocks = [
    { label: "产品身份", values: signals.identity },
    { label: "属性", values: signals.attributes },
    { label: "用途/场景", values: signals.scenarios },
    { label: "状态触发", values: signals.painStates },
  ];

  return (
    <Card className="bg-white border-brand-100">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-brand-600" />
          诊断假设验证闭环
        </CardTitle>
        <p className="text-xs text-gray-500">
          先从标题识别产品身份、属性、用途和场景，再判断各模块影响哪些广告指标，最后用真实投放验证。
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {signalBlocks.map((block) => (
            <div key={block.label} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p className="text-[11px] font-semibold text-gray-500">{block.label}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(block.values.length ? block.values : ["待补齐"]).map((value) => (
                  <Badge key={value} variant="outline" className="border-brand-100 bg-white text-brand-700 text-[10px]">
                    {value}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {rows.map((row) => (
            <div key={row.key} className="rounded-xl border border-gray-100 bg-gray-50 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h4 className="font-semibold text-gray-900">{row.module}</h4>
                  <p className="mt-1 text-xs text-gray-500">{row.issue?.judgement || "检查该模块是否承接标题语义和购买理由。"}</p>
                </div>
                <Badge className={row.priority.startsWith("P0") ? "bg-red-600 text-white" : row.priority.startsWith("P1") ? "bg-amber-500 text-white" : "bg-gray-100 text-gray-600"}>
                  {row.priority}
                </Badge>
              </div>

              <div className="mt-3 flex flex-wrap gap-1.5">
                {row.metrics.map((metric) => (
                  <Badge key={metric} variant="outline" className="bg-white border-teal-100 text-teal-700 text-[10px]">
                    {metric}
                  </Badge>
                ))}
              </div>

              <div className="mt-3 space-y-3 text-sm">
                <div>
                  <p className="text-[11px] text-gray-500 mb-1">修改动作</p>
                  <p className="text-gray-700 leading-relaxed">{row.action}</p>
                </div>
                <div className="rounded-lg border border-brand-100 bg-white p-3">
                  <p className="text-[11px] font-semibold text-brand-700 mb-1">广告验证假设</p>
                  <p className="text-gray-700 leading-relaxed">{row.hypothesis}</p>
                  {row.keywords.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {row.keywords.map((kw) => (
                        <Badge key={kw} variant="outline" className="text-[10px] border-gray-200 text-gray-600">
                          {kw}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <div className="rounded-lg bg-emerald-50 border border-emerald-100 p-3">
                    <p className="text-[11px] font-semibold text-emerald-700">命中标准</p>
                    <p className="mt-1 text-xs text-gray-600 leading-relaxed">{row.success}</p>
                  </div>
                  <div className="rounded-lg bg-amber-50 border border-amber-100 p-3">
                    <p className="text-[11px] font-semibold text-amber-700">未命中归因</p>
                    <p className="mt-1 text-xs text-gray-600 leading-relaxed">{row.failure}</p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function DiagnosisTraceBar({ result }: { result: DiagnosisResult }) {
  const trace = result.trace;
  if (!trace) return null;
  const mode = trace.ai_called ? "最新判断" : trace.cache_hit ? "命中缓存" : "历史结果";
  const generatedAt = trace.generated_at ? new Date(trace.generated_at).toLocaleString() : "";
  const meta = trace.diagnosis_meta || {};
  const fingerprint = meta.content_fingerprint_short || trace.content_fingerprint_short;

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-[11px] text-gray-500">
      <span className="font-semibold text-gray-700">判断来源</span>
      <Badge variant="outline" className="bg-white border-brand-100 text-brand-700 text-[10px]">
        {mode}
      </Badge>
      {trace.diagnosis_id !== undefined && (
        <span>ID #{trace.diagnosis_id || "未保存"}</span>
      )}
      {meta.schema_version && (
        <span>版本 {meta.schema_version}</span>
      )}
      {meta.rules_version && (
        <span>标准 {meta.rules_version}</span>
      )}
      {meta.cache_policy && (
        <span>缓存 {meta.cache_policy === "exact_content_only" ? "仅同内容命中" : meta.cache_policy}</span>
      )}
      {fingerprint && (
        <span>指纹 {fingerprint}</span>
      )}
      {trace.frontend_version && (
        <span>前端 {trace.frontend_version}</span>
      )}
      {generatedAt && <span>{generatedAt}</span>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Listing Input Form                                                 */
/* ------------------------------------------------------------------ */

function ListingForm({
  listing,
  onChange,
  label,
  compact = false,
}: {
  listing: ListingInput;
  onChange: (l: ListingInput) => void;
  label?: string;
  compact?: boolean;
}) {
  const update = (field: keyof ListingInput, value: string) => {
    onChange({ ...listing, [field]: value });
  };

  return (
    <div className="space-y-3">
      {label && <h3 className="text-sm font-medium text-gray-600 mb-2">{label}</h3>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="md:col-span-2">
          <label className="text-xs text-gray-500 mb-1 block">标题 *</label>
          <Input
            placeholder="输入产品标题"
            value={listing.title}
            onChange={(e) => update("title", e.target.value)}
            className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-600"
          />
        </div>
        <div className="md:col-span-2">
          <label className="text-xs text-gray-500 mb-1 block">五点描述</label>
          <Textarea
            placeholder="输入五点描述（每条一行或用分号分隔）"
            value={listing.bullet_points}
            onChange={(e) => update("bullet_points", e.target.value)}
            className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-600 min-h-[80px]"
          />
        </div>
        {!compact && (
          <>
            <div className="md:col-span-2">
              <label className="text-xs text-gray-500 mb-1 block">A+ 内容描述</label>
              <Textarea
                placeholder="描述A+内容的主要信息（可选）"
                value={listing.a_plus_content}
                onChange={(e) => update("a_plus_content", e.target.value)}
                className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-600 min-h-[60px]"
              />
            </div>
            <div className="md:col-span-2">
              <label className="text-xs text-gray-500 mb-1 block">后台关键词</label>
              <Input
                placeholder="输入后台Search Terms（可选）"
                value={listing.backend_keywords}
                onChange={(e) => update("backend_keywords", e.target.value)}
                className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-600"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">主图描述</label>
              <Input
                placeholder="描述主图内容（可选）"
                value={listing.main_image_description}
                onChange={(e) => update("main_image_description", e.target.value)}
                className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-600"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">类目</label>
              <Input
                placeholder="产品类目（可选）"
                value={listing.category}
                onChange={(e) => update("category", e.target.value)}
                className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-600"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">价格</label>
              <Input
                placeholder="如 $29.99"
                value={listing.price}
                onChange={(e) => update("price", e.target.value)}
                className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-600"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">品牌</label>
              <Input
                placeholder="品牌名（可选）"
                value={listing.brand}
                onChange={(e) => update("brand", e.target.value)}
                className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-600"
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Score Bar Component                                                */
/* ------------------------------------------------------------------ */

const INTERNAL_REASONING_KEYS = new Set([
  "human_nature",
  "human_nature_graph",
  "human_nature_layer",
  "human_nature_mapping",
  "root_layer",
  "evolution_layer",
  "human_motivation_layer",
  "motivation_layer",
  "level_0",
  "level_1",
  "level_2",
  "level_3",
  "level_4",
  "level_5",
  "level_6",
  "level_7",
  "level_8",
  "level_9",
]);

const INTERNAL_REASONING_PATTERNS = [
  /人性根层映射[:：]?/g,
  /人性根层[:：]?/g,
  /人性驱动力[:：]?/g,
  /趋利\s*[\/／]?\s*避害[:：]?/g,
  /趋利[:：]?/g,
  /避害[:：]?/g,
  /Seek\s*Gain/gi,
  /Avoid\s*Loss/gi,
  /Human\s*Nature\s*Root\s*Layer/gi,
  /Level\s*[0-9][:：]?/gi,
  /13个人性节点[:：]?/g,
  /进化层[:：]?/g,
  /根层[:：]?/g,
  /后台动作顺序[:：]?/g,
  /后台判断[:：]?/g,
  /内部方法论[:：]?/g,
];

function sanitizeFrontendText(text: string): string {
  const parts = text
    .split(/[；;\n]+/)
    .map((part) => part.trim())
    .filter((part) => part && !INTERNAL_REASONING_PATTERNS.some((pattern) => {
      pattern.lastIndex = 0;
      return pattern.test(part);
    }));
  let cleaned = parts.join("；");
  INTERNAL_REASONING_PATTERNS.forEach((pattern) => {
    pattern.lastIndex = 0;
    cleaned = cleaned.replace(pattern, "");
  });
  return cleaned.replace(/^[：:；;\s]+|[：:；;\s]+$/g, "").replace(/；{2,}/g, "；").trim();
}

function getSellerFacingDecision(item: Record<string, any>) {
  if (item?.seller_facing_output && typeof item.seller_facing_output === "object") {
    return item.seller_facing_output;
  }
  const score = Math.round(Number(item?.confidence_score || item?.score || 0));
  const domain = item?.domain;
  const fallback: Record<string, any> = {
    user_intent: {
      title: "买家购买判断",
      judgment: score >= 80 ? "购买理由清楚" : score >= 60 ? "购买理由还不够清楚" : "买家为什么买还没讲清楚",
      basis: "当前证据不足，无法稳定判断买家购买理由。",
      action: "先补清目标买家、使用场景和最大顾虑，再进入下一步验证。",
      risk: "购买理由不清楚时，后续关键词和广告容易跑偏。",
    },
    platform_matching: {
      title: "Amazon识别判断",
      judgment: score >= 80 ? "Amazon识别较清楚" : score >= 60 ? "Amazon识别还不稳定" : "Amazon可能识别不准这个产品",
      basis: "标题、五点或后台词里的产品身份和场景信息不足。",
      action: "补齐产品身份、类目锚点、属性词、关系词和场景问题词。",
      risk: "识别不准会带来低曝光、错匹配和更高点击成本。",
    },
    listing_conversion: {
      title: "Listing承接判断",
      judgment: score >= 80 ? "页面承接较好" : score >= 60 ? "页面承接还要优化" : "页面没有接住流量",
      basis: "标题、图片、五点或A+没有充分证明买家的购买理由。",
      action: "先改最影响转化的承接模块，再做小预算验证。",
      risk: "只改表述不补证据，可能点击提升但转化不升。",
    },
    advertising_validation: {
      title: "广告验证判断",
      judgment: item?.current_judgment || "等待验证",
      basis: "当前验证证据不足。",
      action: item?.recommended_action || "先做小预算验证。",
      risk: item?.risk_warning || "验证不足时加预算会放大误判。",
    },
    capital_allocation: {
      title: "投入优先级",
      judgment: score >= 65 ? "可以优先投入高置信改动" : "先补证据，再投入资源",
      basis: `当前综合置信度为${score}分。`,
      action: "预算、时间和人力先投向最能验证核心判断的动作。",
      risk: "证据不足时加大投入，会把错误判断变成沉没成本。",
    },
    learning_feedback: {
      title: "复盘结论",
      judgment: "等待验证结果回流",
      basis: "当前还没有足够结果判断这次动作是否命中。",
      action: "验证后记录命中、未命中、样本不足和下一轮动作。",
      risk: "没有归因的结果进入复盘，会让下一轮判断变偏。",
    },
  };
  return {
    title: "运营判断",
    judgment: item?.current_judgment || "待判断",
    basis: Array.isArray(item?.judgment_basis) ? item.judgment_basis[0] : item?.judgment_basis || "",
    action: item?.recommended_action || "暂无",
    risk: item?.risk_warning || "暂无",
    confidence: score,
    ...(fallback[domain] || {}),
  };
}

function formatAnalysisText(value: unknown): string {
  if (!value) return "";
  if (typeof value === "string") {
    return sanitizeFrontendText(value);
  }
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    return value.map(formatAnalysisText).filter(Boolean).join("；");
  }
  if (typeof value === "object") {
    const labels: Record<string, string> = {
      user_need_mapping: "用户需求",
      platform_mapping: "Amazon识别",
      evidence: "当前证据",
      deduction_reason: "扣分原因",
      problem_type: "问题类型",
      impact_metrics: "影响指标",
      next_action: "下一步动作",
      summary: "总结",
    };
    return Object.entries(value as Record<string, unknown>)
      .filter(([key]) => !INTERNAL_REASONING_KEYS.has(key))
      .map(([key, item]) => {
        const text = formatAnalysisText(item);
        return text ? `${labels[key] || key}：${text}` : "";
      })
      .filter(Boolean)
      .join("；");
  }
  return "";
}

function normalizeStringList(value: unknown): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value.map(formatAnalysisText).filter(Boolean);
  const text = formatAnalysisText(value);
  return text ? [text] : [];
}

function normalizeStringRecord(value: unknown): Record<string, string[]> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, normalizeStringList(item)])
  );
}

function normalizeDiagnosisResultForUi(result: DiagnosisResult): DiagnosisResult {
  const suggestions = result.suggestions || {};
  const keywordCoverage = result.keyword_coverage || {};
  const elements = Object.fromEntries(
    Object.entries(result.elements || {}).map(([key, item]) => {
      const value = item && typeof item === "object" ? { ...item } : {};
      return [key, { ...value, summary: formatAnalysisText((value as Record<string, unknown>).summary) }];
    })
  );
  return {
    ...result,
    analysis: Object.fromEntries(
      Object.entries(result.analysis || {}).map(([key, value]) => [key, formatAnalysisText(value)])
    ),
    suggestions: {
      ...suggestions,
      title_rewrite: formatAnalysisText(suggestions.title_rewrite),
      bullet_points_optimization: normalizeStringList(suggestions.bullet_points_optimization),
      backend_keywords_addition: normalizeStringList(suggestions.backend_keywords_addition),
      image_suggestions: normalizeStringList(suggestions.image_suggestions),
      a_plus_suggestions: formatAnalysisText(suggestions.a_plus_suggestions),
    },
    keyword_coverage: {
      ...keywordCoverage,
      covered_categories: normalizeStringRecord(keywordCoverage.covered_categories),
      missing_categories: normalizeStringRecord(keywordCoverage.missing_categories),
      coverage_summary: formatAnalysisText(keywordCoverage.coverage_summary),
    },
    elements,
    overall_summary: formatAnalysisText(result.overall_summary),
    analyzed_product_name: formatAnalysisText(result.analyzed_product_name),
    product_mismatch_detail: formatAnalysisText(result.product_mismatch_detail),
    ad_validation_readiness_gate: result.ad_validation_readiness_gate,
  };
}

function ScoreBar({ dim, score, analysis }: { dim: typeof DIMENSIONS[0]; score: number; analysis?: unknown }) {
  const [expanded, setExpanded] = useState(false);
  const rulerMeta = DIMENSION_RULER_META[dim.key];
  const analysisText = formatAnalysisText(analysis);
  return (
    <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={dim.color}>{dim.icon}</span>
          <span className="text-sm font-medium text-gray-600">{dim.label}</span>
          <span className="text-[10px] text-gray-600">{dim.labelEn}</span>
          <Badge variant="outline" className="hidden sm:inline-flex text-[10px] border-brand-100 bg-white text-brand-700">
            {rulerMeta.layer}
          </Badge>
        </div>
        <span className={`text-lg font-bold ${scoreColor(score)}`}>{score}</span>
      </div>
      <div className="mb-2 rounded-lg bg-white border border-gray-100 p-2 text-[11px] text-gray-500 leading-relaxed">
        <span className="font-semibold text-gray-700">需求</span> {rulerMeta.intentScale}
        <span className="mx-2 text-gray-300">|</span>
        <span className="font-semibold text-gray-700">平台</span> {rulerMeta.platformScale}
      </div>
      <div className="w-full h-2 bg-gray-50 rounded-full overflow-hidden mb-2">
        <div
          className={`h-full rounded-full transition-all duration-700 ${scoreBgColor(score)}`}
          style={{ width: `${score}%` }}
        />
      </div>
      {analysisText && (
        <button onClick={() => setExpanded(!expanded)} className="text-xs text-gray-500 hover:text-gray-600 flex items-center gap-1 mt-1">
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          {expanded ? "收起分析" : "查看分析"}
        </button>
      )}
      {expanded && analysisText && (
        <div className="text-xs text-gray-500 leading-relaxed mt-2 pl-2 border-l-2 border-gray-200 space-y-2">
          <p>{analysisText}</p>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function ListingDiagnosis() {
  const { loading: authLoading } = useRequireAuth();

  const [activeTab, setActiveTab] = useState("diagnose");
  const [marketplace, setMarketplace] = useState("US");

  // URL fetch
  const [fetchUrl, setFetchUrl] = useState("");
  const [fetching, setFetching] = useState(false);
  const [fetchSource, setFetchSource] = useState<string | null>(null);
  const [fetchMeta, setFetchMeta] = useState<FetchMeta | null>(null);
  const [fetchProgress, setFetchProgress] = useState("");
  const [fetchProgressValue, setFetchProgressValue] = useState(0);
  const [fetchElapsed, setFetchElapsed] = useState(0);
  const [selectedListingAsin, setSelectedListingAsin] = useState("");
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [diagnosisPhase, setDiagnosisPhase] = useState<DiagnosisPhase>("idle");
  const [showAdvancedEditor, setShowAdvancedEditor] = useState(false);
  const [localCaptureImporting, setLocalCaptureImporting] = useState(false);

  // Manual paste mode
  const [showManualPaste, setShowManualPaste] = useState(false);
  const [manualPasteText, setManualPasteText] = useState("");

  // Diagnose tab
  const [listing, setListing] = useState<ListingInput>({ ...EMPTY_LISTING });
  const [productStageOverride, setProductStageOverride] = useState<ProductStage | null>(null);
  const [diagnosing, setDiagnosing] = useState(false);
  const [diagResult, setDiagResult] = useState<DiagnosisResult | null>(null);
  const [resultTab, setResultTab] = useState("overview");
  const resultSectionRef = useRef<HTMLDivElement | null>(null);

  const scrollToResultSection = () => {
    window.setTimeout(() => {
      resultSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
  };

  // History tab
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyStats, setHistoryStats] = useState<{
    total_count: number;
    overall_avg: number;
    dimension_avgs: Record<string, number>;
    max_avg: number;
    min_avg: number;
  } | null>(null);
  const [historySearch, setHistorySearch] = useState("");
  const [historyMpFilter, setHistoryMpFilter] = useState("");
  const [historyDetailLoading, setHistoryDetailLoading] = useState<number | null>(null);
  const [historyViewId, setHistoryViewId] = useState<number | null>(null);
  const [historyDiagResult, setHistoryDiagResult] = useState<DiagnosisResult | null>(null);
  const [historyResultTab, setHistoryResultTab] = useState("overview");
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [latestDiagnosis, setLatestDiagnosis] = useState<HistoryItem | null>(null);

  // Element heatmap expand
  const [expandedEl, setExpandedEl] = useState<string | null>(null);

  // Market validation (computed from diagnosis result)
  const [marketValidation, setMarketValidation] = useState<MarketValidation | null>(null);

  useEffect(() => {
    if (!fetching) return;
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      setFetchElapsed(elapsed);
      setFetchProgressValue((current) => Math.max(current, Math.min(92, Math.round((elapsed / 60) * 92))));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [fetching]);

  // Scrape stats
  const [scrapeStats, setScrapeStats] = useState<{
    total_attempts: number;
    total_success: number;
    success_rate: number;
    method_stats: Record<string, { total: number; success: number; rate: number }>;
    recent_logs: Array<{
      id: number;
      asin: string;
      marketplace: string;
      scrape_method: string;
      success: boolean;
      data_source: string;
      error_message: string;
      created_at: string | null;
    }>;
  } | null>(null);
  const [scrapeStatsExpanded, setScrapeStatsExpanded] = useState(false);

  useEffect(() => {
    axios
      .get("/api/v1/listing-diagnosis/history?limit=1", { headers: getAuthHeaders() })
      .then((res) => setLatestDiagnosis((res.data.items || [])[0] || null))
      .catch(() => setLatestDiagnosis(null));
  }, []);

  const pollDiagnosisTask = async (taskId: string): Promise<DiagnosisTaskResponse> => {
    for (let attempt = 0; attempt < 180; attempt += 1) {
      const res = await axios.get<DiagnosisTaskResponse>(
        `${getLongRunningApiBase()}/api/v1/diagnosis-tasks/${taskId}`,
        { headers: getAuthHeaders(), timeout: 30000 }
      );
      const task = res.data;
      if (task.status === "completed") return task;
      if (task.status === "failed") {
        throw new Error(task.error_message || "诊断任务失败");
      }
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
    }
    throw new Error("诊断任务仍在运行，请稍后从最新诊断查看");
  };

  const applyDiagnosisResult = async (
    result: DiagnosisResult,
    activeListing: ListingInput,
    activeFetchMeta: FetchMeta | null,
    diagPayload: Record<string, unknown>
  ) => {
    const uiResult = normalizeDiagnosisResultForUi(result);
    setDiagResult(uiResult);
    setResultTab("overview");
    setDiagnosisPhase("analyzed");

    setMarketValidation(deriveMarketValidationFromEvidence(activeListing, activeFetchMeta, uiResult.market_estimates));

    toast.success("诊断完成！");
    const scores = uiResult.scores || {};
    const activeAsin = activeFetchMeta?.asin || selectedListingAsin || activeListing.asin || "";
    const activeTitle = activeListing.title || "";
    let workflowProductId = selectedProductId && selectedProductId > 0 ? selectedProductId : null;
    if (!workflowProductId && (activeAsin || activeTitle)) {
      const products = await getAllProducts(100);
      const titleKey = activeTitle.toLowerCase().replace(/\s+/g, " ").trim().slice(0, 120);
      const matched = products.find((product: { id?: number; asin?: string; title?: string }) =>
        (activeAsin && product.asin === activeAsin) ||
        (titleKey && (product.title || "").toLowerCase().replace(/\s+/g, " ").trim().slice(0, 120) === titleKey)
      );
      workflowProductId = matched?.id || null;
    }
    if (workflowProductId) {
      updateProductLifecycle(workflowProductId, "strategy").catch(() => {});
    }
    const totalScore = Object.values(scores).reduce((s: number, v) => s + (Number(v) || 0), 0);
    const avgScore = Math.round(totalScore / Math.max(Object.keys(scores).length, 1));
    if (workflowProductId) {
      saveTimelineEvent({
        product_id: workflowProductId,
        step_name: "Listing诊断",
        action_timestamp: new Date().toISOString(),
        listing_score: avgScore,
        score_details: JSON.stringify(scores),
        optimization_round: 1,
      }).catch(() => {});
    }
    saveActionSnapshot({
      module_key: "listing_diagnosis",
      module_name: "本品诊断",
      action_key: "diagnose_listing",
      action_name: "本品Listing诊断",
      product_id: workflowProductId,
      asin: activeAsin,
      title: activeListing.title,
      input_snapshot: diagPayload,
      output_snapshot: result,
      data_source: activeFetchMeta?.source || fetchSource || "listing_diagnosis_task",
      confidence: result.diagnosis_confidence?.overall?.level || "",
      ai_called: true,
      source_record_table: "listing_diagnoses",
      source_record_id: result.id || null,
    }).catch(() => {});
    loadHistory(historySearch, historyMpFilter).catch(() => {});
  };

  useEffect(() => {
    const taskId = localStorage.getItem(LISTING_DIAGNOSIS_TASK_KEY);
    if (!taskId) return;
    let savedContext: { listing?: ListingInput; fetchMeta?: FetchMeta | null; diagPayload?: Record<string, unknown> } = {};
    try {
      savedContext = JSON.parse(localStorage.getItem(LISTING_DIAGNOSIS_TASK_CONTEXT_KEY) || "{}");
    } catch {
      savedContext = {};
    }
    let cancelled = false;
    setDiagnosing(true);
    setDiagnosisPhase("analyzing");
    const moduleTaskId = `listing-diagnosis:${taskId}`;
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "listing-diagnosis",
      label: "本品Listing诊断",
      status: "running",
      detail: "正在恢复诊断任务",
      path: "/listing-diagnosis",
    });
    pollDiagnosisTask(taskId)
      .then((task) => {
        if (cancelled) return;
        localStorage.removeItem(LISTING_DIAGNOSIS_TASK_KEY);
        localStorage.removeItem(LISTING_DIAGNOSIS_TASK_CONTEXT_KEY);
        if (task.result_payload) {
          const restoredListing = cleanListing(savedContext.listing || listing);
          const restoredMeta = savedContext.fetchMeta || fetchMeta;
          const formalGateMissing = resolveFormalGateMissing(restoredListing, restoredMeta);
          setListing(restoredListing);
          setFetchMeta(restoredMeta || null);
          if (formalGateMissing.length > 0) {
            setDiagnosisPhase("fetch_success");
            setShowAdvancedEditor(false);
            toast.warning(`诊断结果已拦截：缺失 ${formalGateMissing.slice(0, 5).join("、")}，未恢复为正式报告。`);
            return;
          }
          applyDiagnosisResult(
            task.result_payload,
            restoredListing,
            restoredMeta || null,
            savedContext.diagPayload || { listing: restoredListing }
          );
          toast.success("诊断已完成，结果已恢复");
          finishModuleTask(moduleTaskId, "completed", "本品诊断已恢复完成");
        }
      })
      .catch((err) => {
        if (cancelled) return;
        localStorage.removeItem(LISTING_DIAGNOSIS_TASK_KEY);
        localStorage.removeItem(LISTING_DIAGNOSIS_TASK_CONTEXT_KEY);
        const msg = err instanceof Error ? err.message : "诊断状态恢复失败";
        finishModuleTask(moduleTaskId, "failed", msg);
        toast.error(msg);
        setDiagnosisPhase("error");
      })
      .finally(() => {
        if (!cancelled) {
          setDiagnosing(false);
          window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Update marketplace on listing
  const updateListingMarketplace = (mp: string) => {
    setMarketplace(mp);
    setListing((prev) => ({ ...prev, marketplace: mp }));
  };

  // Clean "[未确认]" and similar markers from a string
  const cleanField = (val: string): string => {
    if (!val) return "";
    return val
      .split("\u0000").join(" ")
      .replace(/\uFFFC/g, " ")
      .replace(/\uFE0F/g, " ")
      .replace(/\[?\s*(?:🖼️\s*)?(?:图片|image|img)\s*[:：][^\]\n]{0,120}\]?/gi, " ")
      .replace(/\[未确认\]\s*/g, "")
      .replace(/\[unknown\]\s*/gi, "")
      .replace(/\[unconfirmed\]\s*/gi, "")
      .replace(/\s+/g, " ")
      .trim();
  };

  const cleanMultilineField = (val: string): string => {
    if (!val) return "";
    return val
      .split("\u0000").join(" ")
      .replace(/\uFFFC/g, " ")
      .replace(/\uFE0F/g, " ")
      .replace(/\[?\s*(?:🖼️\s*)?(?:图片|image|img)\s*[:：][^\]\n]{0,120}\]?/gi, " ")
      .replace(/\[未确认\]\s*/g, "")
      .replace(/\[unknown\]\s*/gi, "")
      .replace(/\[unconfirmed\]\s*/gi, "")
      .split(/\n|；|;/)
      .map((item) => item.replace(/\s+/g, " ").trim())
      .filter(Boolean)
      .join("\n");
  };

  // Clean all fields in a listing object
  const cleanListing = (l: ListingInput): ListingInput => ({
    ...l,
    title: cleanField(l.title),
    bullet_points: cleanMultilineField(l.bullet_points),
    description: cleanField(l.description),
    a_plus_content: cleanField(l.a_plus_content).slice(0, 900),
    backend_keywords: cleanField(l.backend_keywords),
    main_image_description: cleanField(l.main_image_description),
    category: cleanField(l.category),
    price: cleanField(l.price),
    brand: cleanField(l.brand),
  });

  /** Save fetched listing to database immediately */
  const saveFetchedListing = async (cleaned: ListingInput, source: string, asin: string, rating: string, reviewCount: string, bsrRank: string) => {
    try {
      if (!cleaned.title || cleaned.title.length < 3) return;
      await axios.post(
        "/api/v1/listing-diagnosis/save-fetched",
        {
          listing: cleaned,
          source,
          asin,
          rating,
          review_count: reviewCount,
          bsr_rank: bsrRank,
        },
        { headers: getAuthHeaders() }
      );
    } catch {
      // Silent fail - saving is best-effort, don't interrupt user flow
    }
  };

  /** Log a scrape attempt to the backend */
  const logScrapeAttempt = async (asin: string, mp: string, method: string, success: boolean, dataSource: string, errorMsg = "") => {
    try {
      await axios.post(
        "/api/v1/listing-diagnosis/scrape-log",
        { asin, marketplace: mp, scrape_method: method, success, data_source: dataSource, error_message: errorMsg },
        { headers: getAuthHeaders() }
      );
    } catch {
      // Silent fail
    }
  };

  /** Load scrape statistics */
  const loadScrapeStats = async () => {
    try {
      const res = await axios.get("/api/v1/listing-diagnosis/scrape-stats", { headers: getAuthHeaders() });
      setScrapeStats(res.data);
    } catch {
      // Silent fail
    }
  };

  /** Apply fetched data to the form (shared by all fetch modes) */
  const applyFetchResult = (data: {
    listing?: ListingInput;
    asin?: string;
    source?: string;
    rating?: string;
    review_count?: string;
    bsr_rank?: string;
    bsr_category?: string;
    image_count?: string;
    has_video?: boolean;
    has_a_plus?: boolean;
    review_samples?: Array<Record<string, unknown>>;
    review_intent_assets?: Record<string, unknown>;
    capture_quality?: FetchMeta["capture_quality"];
  }): { listing: ListingInput; meta: FetchMeta } | null => {
    if (!data.listing) return null;
    const cleaned = cleanListing({
      ...data.listing,
      rating: data.rating || data.listing.rating || "",
      review_count: data.review_count || data.listing.review_count || "",
      bsr_rank: data.bsr_rank || data.listing.bsr_rank || "",
      image_count: data.image_count || data.listing.image_count || "",
      has_video: data.has_video || data.listing.has_video || false,
      has_a_plus: data.has_a_plus || data.listing.has_a_plus || false,
      marketplace: data.listing.marketplace || marketplace,
    });

    setListing(cleaned);
    setProductStageOverride(null);
    setDiagnosisPhase(cleaned.title && cleaned.title.length >= 3 ? "fetch_success" : "fetch_failed");
    if (!cleaned.title || cleaned.title.length < 3) {
      setShowAdvancedEditor(false);
    }
    if (data.listing.marketplace && data.listing.marketplace !== marketplace) {
      setMarketplace(data.listing.marketplace);
    }

    const source = data.source || "unknown";
    setSelectedListingAsin(data.asin || data.listing.asin || "");
    setFetchSource(source);
    const meta: FetchMeta = {
      asin: data.asin || data.listing.asin || "",
      source,
      rating: data.rating || "",
      review_count: data.review_count || "",
      bsr_rank: data.bsr_rank || "",
      bsr_category: data.bsr_category || "",
      image_count: data.image_count || "",
      has_video: data.has_video || false,
      has_a_plus: data.has_a_plus || false,
      review_samples: data.review_samples || [],
      review_intent_assets: data.review_intent_assets || {},
      capture_quality: data.capture_quality,
    };
    setFetchMeta(meta);

    // Update market validation with the same evidence that will be sent to diagnosis.
    const isReliable = ["local_browser_capture", "server_proxy_fetch", "scraped", "amazon_scrape", "amazon_scrape_httpx", "amazon_scrape_mobile", "amazon_scrape_browser", "amazon_scrape_uc", "ai_search"].includes(source);
    setMarketValidation(isReliable ? deriveMarketValidationFromEvidence(cleaned, meta) : null);

    // Local browser capture should be visible first, then saved as a real
    // diagnosis after analysis. Do not create a raw history row just from
    // receiving the plugin payload.
    if (source !== "local_browser_capture") {
      saveFetchedListing(
        cleaned,
        source,
        data.asin || "",
        data.rating || "",
        data.review_count || "",
        data.bsr_rank || "",
      );
    }

    // Toast
    if (!cleaned.title || cleaned.title.length < 3) {
      toast.warning("未能获取到该ASIN的产品标题，请手动填写产品信息后再进行诊断", { duration: 6000 });
    } else if (source === "local_browser_capture") {
      toast.success(`🌐 已从本地浏览器页面解析 ASIN: ${data.asin}，完整度 ${data.capture_quality?.completeness ?? "待确认"}%`, { duration: 5000 });
    } else if (source === "server_proxy_fetch") {
      toast.success(`已采集 ASIN: ${data.asin}，并自动保存`, { duration: 5000 });
    } else if (source === "manual_paste") {
      toast.success(`📋 已从粘贴内容解析出产品数据，已自动保存`, { duration: 5000 });
    } else if (["scraped", "amazon_scrape", "amazon_scrape_httpx", "amazon_scrape_mobile", "amazon_scrape_browser", "amazon_scrape_uc"].includes(source)) {
      toast.success(`✅ 已从Amazon真实页面抓取 ASIN: ${data.asin} 的Listing数据，已自动保存`, { duration: 5000 });
    } else if (source === "ai_search") {
      toast.success(`已完成 ASIN: ${data.asin} 的搜索验证，并自动保存`, { duration: 5000 });
    } else if (source === "ai_estimated") {
      toast.warning(`ASIN: ${data.asin} 的数据为低置信度预检，建议核实`, { duration: 6000 });
    } else if (source === "ai_empty") {
      toast.warning("系统未能获取到产品信息，请手动填写后再进行诊断", { duration: 6000 });
    } else {
      toast.success(`已抓取 ASIN: ${data.asin || "unknown"} 的Listing信息，已自动保存`);
    }

    return { listing: cleaned, meta };
  };

  const handleFetchUrl = async () => {
    const url = fetchUrl.trim();
    if (!url) {
      toast.error("请输入ASIN或Amazon产品链接");
      return;
    }
    setFetching(true);
    setDiagnosisPhase("fetching");
    setFetchSource(null);
    setFetchMeta(null);
    setFetchProgress("");
    setFetchProgressValue(3);
    setFetchElapsed(0);
    setShowManualPaste(false);
    setDiagResult(null);
    setResultTab("overview");
    setMarketValidation(null);

    const asin = extractAsinFromUrl(url);
    const detectedMp = detectMarketplaceFromUrl(url) || marketplace;

    if (!asin || asin.length !== 10) {
      toast.error("无法识别有效的ASIN，请输入10位ASIN（如B0XXXXXXXXX）或完整的Amazon产品链接");
      setFetching(false);
      setDiagnosisPhase("error");
      return;
    }

    try {
      const domain = MARKETPLACE_DOMAINS_MAP[detectedMp] || "www.amazon.com";
      const amazonUrl = `https://${domain}/dp/${asin}`;

      if (isPublicDeployment()) {
        setFetchProgress("公网服务器正在抓取Amazon页面并生成Listing诊断，通常需要 10-40 秒");
        setFetchProgressValue(48);
        try {
          const apiBase = getLongRunningApiBase();
          const res = await axios.post(
            `${apiBase}/api/v1/listing-diagnosis/fetch-url`,
            { url: amazonUrl, marketplace: detectedMp },
            { headers: getAuthHeaders(), timeout: 240000 }
          );
          const data = res.data;
          if (data?.listing?.title && data.listing.title.length >= 3) {
            setFetchProgress("已抓取 Listing，正在生成诊断报告");
            setFetchProgressValue(88);
            const applied = applyFetchResult(data);
            logScrapeAttempt(asin, detectedMp, "server_scrape", true, data.source || "server_scrape");
            if (applied?.listing.title) {
              await handleDiagnose(applied.listing, applied.meta);
            }
            return;
          }

          setDiagnosisPhase("fetch_failed");
          setShowAdvancedEditor(false);
          logScrapeAttempt(asin, detectedMp, "server_scrape", false, data?.source || "failed", "No valid title returned");
          toast.error("服务器没有返回有效标题，请检查ASIN或稍后重试");
          return;
        } catch (publicErr) {
          const errMsg = axios.isAxiosError(publicErr)
            ? publicErr.response?.data?.detail || publicErr.message || "unknown"
            : "unknown";
          logScrapeAttempt(asin, detectedMp, "server_scrape", false, "failed", errMsg);
          setDiagnosisPhase("fetch_failed");
          setShowAdvancedEditor(false);
          toast.error("公网服务器抓取失败，请稍后重试");
          return;
        }
      }

      // ---- Phase 1: Backend proxy-fetch → get HTML → send to /parse-html ----
      setFetchProgress("正在尝试采集Amazon页面，若受限会自动切换备用方式");
      setFetchProgressValue(12);
      let phase1Success = false;

      try {
        const proxyRes = await axios.post(
          "/api/v1/asin-analysis/proxy-fetch",
          { asin, marketplace: detectedMp },
          { headers: getAuthHeaders(), timeout: 30000 }
        );

        if (proxyRes.data?.success && proxyRes.data?.html) {
          const html = proxyRes.data.html;
          setFetchProgress("Phase 2/3：已获取页面 HTML，正在解析 Listing 字段");
          setFetchProgressValue(48);
          try {
            const parseRes = await axios.post(
              "/api/v1/listing-diagnosis/parse-html",
              { html, marketplace: detectedMp, asin, source: "server_proxy_fetch" },
              { headers: getAuthHeaders(), timeout: 60000 }
            );
            if (parseRes.data.success && parseRes.data.listing?.title) {
              const applied = applyFetchResult(parseRes.data);
              phase1Success = true;
              logScrapeAttempt(asin, detectedMp, "server_proxy_fetch", true, "server_proxy_fetch");
              if (applied?.listing.title) {
                setFetchProgress("Phase 3/3：已抓取 Listing，正在生成诊断报告");
                setFetchProgressValue(88);
                await handleDiagnose(applied.listing, applied.meta);
              }
            }
          } catch {
            // Parse failed, continue to Phase 2
          }
        }
        if (!phase1Success) {
          logScrapeAttempt(asin, detectedMp, "server_proxy_fetch", false, "failed", "Server proxy HTML invalid or parse failed");
        }
      } catch {
        // Server proxy failed entirely, continue to Phase 2
        logScrapeAttempt(asin, detectedMp, "server_proxy_fetch", false, "failed", "Server proxy request failed");
      }

      if (phase1Success) return;

      // ---- Phase 2: Same Amazon retrieval stack, then this page runs its own reverse diagnosis rules ----
      setFetchProgress("页面采集受限，正在补充搜索验证");
      setFetchProgressValue(68);
      try {
        const res = await axios.post(
          "/api/v1/listing-diagnosis/fetch-url",
          { url: amazonUrl, marketplace: detectedMp },
          { headers: getAuthHeaders(), timeout: 180000 }
        );
        const data = res.data;

        if (data.listing) {
          const source = data.source || "unknown";

          // Keep AI-estimated data low-confidence; it only feeds the reverse diagnosis after user-visible confirmation.
          if (source === "ai_estimated" || source === "ai_empty") {
            setFetchSource(source);
            logScrapeAttempt(asin, detectedMp, "server_scrape", false, source, source === "ai_empty" ? "No data found" : "low confidence only");
            if (source === "ai_empty") {
              setDiagnosisPhase("fetch_failed");
              setShowAdvancedEditor(false);
              toast.error("无法获取该ASIN的产品数据，请检查ASIN或稍后重试。");
            } else {
              toast.warning("服务器返回了低置信度预检数据，建议后续用完整采集结果复核。");
              const applied = applyFetchResult(data);
              if (applied?.listing.title) {
                await handleDiagnose(applied.listing, applied.meta);
              }
            }
            return;
          }

          // Real scraped data - apply it
          if (data.listing.title && data.listing.title.length >= 3) {
            setFetchProgress("Phase 3/3：已抓取 Listing，正在生成诊断报告");
            setFetchProgressValue(88);
            const applied = applyFetchResult(data);
            logScrapeAttempt(asin, detectedMp, "server_scrape", true, source);
            if (applied?.listing.title) {
              await handleDiagnose(applied.listing, applied.meta);
            }
            return;
          }
        }

        // If we get here, server returned data but no valid title
        setDiagnosisPhase("fetch_failed");
        setShowAdvancedEditor(false);
        toast.error("无法获取该ASIN的产品信息，请检查ASIN或稍后重试");
        logScrapeAttempt(asin, detectedMp, "server_scrape", false, "failed", "No valid title returned");
      } catch (serverErr) {
        const errMsg = axios.isAxiosError(serverErr)
          ? (serverErr.code === "ECONNABORTED" ? "timeout" : serverErr.response?.data?.detail || serverErr.message || "unknown")
          : "unknown";
        logScrapeAttempt(asin, detectedMp, "server_scrape", false, "failed", errMsg);
        if (axios.isAxiosError(serverErr)) {
          if (serverErr.code === "ECONNABORTED" || serverErr.message?.includes("timeout")) {
            toast.error("服务器抓取或诊断生成超过180秒，请稍后重试");
          } else if (serverErr.response?.status === 400) {
            toast.error(serverErr.response?.data?.detail || "请求参数错误");
          } else {
            toast.error("服务器抓取失败，请稍后重试");
          }
        } else {
          toast.error("抓取失败，请稍后重试");
        }
        setDiagnosisPhase("fetch_failed");
        setShowAdvancedEditor(false);
      }
    } catch (err: unknown) {
      // Top-level catch - prevent any unhandled errors
      try {
        const msg = axios.isAxiosError(err)
          ? err.response?.data?.detail || "抓取失败"
          : "抓取失败";
        toast.error(msg);
      } catch {
        toast.error("抓取失败，请稍后重试");
      }
      setDiagnosisPhase("fetch_failed");
      setShowAdvancedEditor(false);
    } finally {
      setFetching(false);
      setFetchProgress("");
      setFetchProgressValue(0);
      setFetchElapsed(0);
    }
  };

  /** Handle manual paste text parsing */
  const handleManualPaste = async () => {
    const text = manualPasteText.trim();
    if (!text) {
      toast.error("请粘贴Amazon产品页面的内容");
      return;
    }

    const asin = extractAsinFromUrl(fetchUrl) || "";
    const looksLikeHtml = /<html|<body|id=["']productTitle|data-asin=|a-section/i.test(text);
    if (looksLikeHtml && asin) {
      try {
        const parseRes = await axios.post(
          "/api/v1/listing-diagnosis/parse-html",
          { html: text, marketplace, asin, source: "local_browser_capture" },
          { headers: getAuthHeaders(), timeout: 60000 }
        );
        if (parseRes.data?.success && parseRes.data.listing?.title) {
          applyFetchResult(parseRes.data);
          logScrapeAttempt(asin, marketplace, "local_browser_capture", true, "local_browser_capture");
          setShowManualPaste(false);
          setManualPasteText("");
          return;
        }
        toast.error(parseRes.data?.error || "无法从本地浏览器HTML解析产品信息");
      } catch {
        toast.error("本地浏览器HTML解析失败，请改为粘贴页面可见文本");
      }
      return;
    }

    const parsed = parseManualPasteText(text);

    if (!parsed.title && parsed.bullet_points.length === 0) {
      toast.error("无法从粘贴内容中解析出产品信息，请确保复制了完整的产品页面内容");
      return;
    }

    const listingData: ListingInput = {
      title: parsed.title,
      bullet_points: parsed.bullet_points.join("\n"),
      description: "",
      a_plus_content: "",
      backend_keywords: "",
      main_image_description: "",
      category: "",
      price: parsed.price,
      brand: parsed.brand,
      marketplace,
    };

    applyFetchResult({
      listing: listingData,
      asin,
      source: "manual_paste",
      rating: parsed.rating,
      review_count: parsed.review_count,
      capture_quality: buildManualCaptureQuality(parsed),
    });
    logScrapeAttempt(asin || "unknown", marketplace, "manual_paste", true, "manual_paste");

    setShowManualPaste(false);
    setManualPasteText("");
  };

  const consumeLocalBrowserCapture = async () => {
    if (authLoading || localCaptureImporting) return;
    const raw = localStorage.getItem("alignx_local_browser_capture");
    if (!raw) return;

    let capture: {
      html?: string;
      asin?: string;
      marketplace?: string;
      url?: string;
      source?: string;
      title?: string;
      price?: string;
      rating?: string;
      reviewCount?: string;
      bsrRank?: string;
      imageCount?: number;
      bullets?: string[];
      reviews?: Array<Record<string, unknown>>;
      destination?: string;
    };
    try {
      capture = JSON.parse(raw);
    } catch {
      localStorage.removeItem("alignx_local_browser_capture");
      return;
    }
    if (capture.destination && capture.destination !== "listing") return;

    if (!capture?.html || !capture?.asin) {
      toast.error("本地浏览器采集数据不完整，请回到Amazon页面重新采集");
      localStorage.removeItem("alignx_local_browser_capture");
      return;
    }

    setLocalCaptureImporting(true);
    setFetching(true);
    setDiagnosisPhase("fetching");
    setFetchProgress("正在解析本地浏览器采集的Amazon页面...");
    setFetchProgressValue(35);
    try {
      const parseRes = await axios.post(
        "/api/v1/listing-diagnosis/parse-html",
        {
          html: capture.html,
          marketplace: capture.marketplace || marketplace,
          asin: capture.asin,
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
        { headers: getAuthHeaders(), timeout: 90000 }
      );
      if (parseRes.data?.success && parseRes.data.listing?.title) {
        const capturedBullets = (capture.bullets || []).map((item) => String(item).trim()).filter(Boolean).slice(0, 5);
        const parsedBulletCount = splitBullets(parseRes.data.listing.bullet_points).length;
        if (capturedBullets.length > parsedBulletCount) {
          parseRes.data.listing = {
            ...parseRes.data.listing,
            bullet_points: capturedBullets.join("\n"),
          };
        }
        setFetchUrl(capture.url || capture.asin || "");
        setMarketplace(parseRes.data.listing.marketplace || capture.marketplace || marketplace);
        const applied = applyFetchResult(parseRes.data);
        const missing = applied ? resolveFormalGateMissing(applied.listing, applied.meta) : [];
        if (applied && missing.length > 0) {
          localStorage.removeItem(LISTING_DIAGNOSIS_TASK_KEY);
          localStorage.removeItem(LISTING_DIAGNOSIS_TASK_CONTEXT_KEY);
        }
        logScrapeAttempt(capture.asin, capture.marketplace || marketplace, "local_browser_capture", true, "local_browser_capture");
        localStorage.removeItem("alignx_local_browser_capture");
        if (applied && missing.length === 0) {
          toast.success("已接收Chrome插件采集的本地页面，正在自动生成本品诊断");
          setFetching(false);
          setFetchProgress("");
          setFetchProgressValue(0);
          setFetchElapsed(0);
          await handleDiagnose(applied.listing, applied.meta);
        } else {
          toast.warning(`已接收Chrome插件采集的本地页面，请补齐/确认字段后生成诊断${missing.length ? `：${missing.slice(0, 5).join("、")}` : ""}`);
        }
      } else {
        toast.error(parseRes.data?.error || "本地浏览器采集解析失败");
      }
    } catch {
      toast.error("本地浏览器采集解析失败，请确认已登录AlignX后重试");
    } finally {
      setFetching(false);
      setFetchProgress("");
      setFetchProgressValue(0);
      setFetchElapsed(0);
      setLocalCaptureImporting(false);
    }
  };

  useEffect(() => {
    consumeLocalBrowserCapture();
    const onCapture = () => consumeLocalBrowserCapture();
    window.addEventListener("alignx-local-browser-capture", onCapture);
    return () => window.removeEventListener("alignx-local-browser-capture", onCapture);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, localCaptureImporting]);

  const handleDiagnose = async (listingOverride?: ListingInput, fetchMetaOverride?: FetchMeta | null) => {
    const activeListing = listingOverride || listing;
    const activeFetchMeta = fetchMetaOverride === undefined ? fetchMeta : fetchMetaOverride;

    if (!activeListing.title.trim() && !activeListing.bullet_points.trim()) {
      toast.error("请至少输入标题或五点描述");
      return;
    }
    const formalGateMissing = resolveFormalGateMissing(activeListing, activeFetchMeta);
    if (formalGateMissing.length > 0) {
      localStorage.removeItem(LISTING_DIAGNOSIS_TASK_KEY);
      localStorage.removeItem(LISTING_DIAGNOSIS_TASK_CONTEXT_KEY);
      toast.warning(
        `Listing承接证据不完整，不能生成承接诊断。请补齐：${formalGateMissing.slice(0, 5).join("、")}。`,
        { duration: 7000 }
      );
      setDiagnosisPhase("fetch_success");
      setShowAdvancedEditor(false);
      return;
    }
    setDiagnosing(true);
    setDiagnosisPhase("analyzing");
    // Don't clear diagResult here - keep previous result visible until new one arrives
    // This prevents page layout jumps during analysis
    let moduleTaskId: string | null = null;
    try {
      const activeProductStage = resolveProductStage(activeListing, activeFetchMeta, productStageOverride);
      const activeDiagnosisMode = diagnosisModeForStage(activeProductStage);
      // Flow 2: Fetch competitor insights to enrich diagnosis context
      let competitorContext = "";
      try {
        const insights: CompetitorInsight[] = await getCompetitorInsights(0);
        if (insights.length > 0) {
          const recentInsights = insights.slice(0, 5);
          competitorContext = recentInsights.map((ins) => {
            return `竞品ASIN: ${ins.competitor_asin} | 优势: ${ins.strengths || "N/A"} | 劣势: ${ins.weaknesses || "N/A"} | 建议: ${(ins.suggestions || "").substring(0, 500)}`;
          }).join("\n");
        }
      } catch {
        // Non-critical, continue without competitor context
      }

      const diagPayload: Record<string, unknown> = {
        diagnosis_mode: activeDiagnosisMode,
        force_refresh: false,
        listing: {
          ...activeListing,
          asin: activeFetchMeta?.asin || selectedListingAsin || activeListing.asin || "",
          marketplace: activeListing.marketplace || marketplace,
          rating: activeFetchMeta?.rating || activeListing.rating || "",
          review_count: activeFetchMeta?.review_count || activeListing.review_count || "",
          bsr_rank: activeFetchMeta?.bsr_rank || activeListing.bsr_rank || "",
          image_count: activeFetchMeta?.image_count || activeListing.image_count || "",
          has_video: activeFetchMeta?.has_video || activeListing.has_video || false,
          has_a_plus: activeFetchMeta?.has_a_plus || activeListing.has_a_plus || false,
        },
        precision_context: {
          diagnosis_mode: activeDiagnosisMode,
          review_count: activeFetchMeta?.review_count || activeListing.review_count || "",
          rating: activeFetchMeta?.rating || activeListing.rating || "",
          bsr_rank: activeFetchMeta?.bsr_rank || activeListing.bsr_rank || "",
          image_count: activeFetchMeta?.image_count || activeListing.image_count || "",
          has_video: activeFetchMeta?.has_video || activeListing.has_video || false,
          has_a_plus: activeFetchMeta?.has_a_plus || activeListing.has_a_plus || false,
          review_samples: activeFetchMeta?.review_samples || [],
          review_intent_assets: activeFetchMeta?.review_intent_assets || {},
          top_competitor_count: 0,
          ad_clicks: 0,
          ad_orders: 0,
        },
      };
      if (competitorContext) {
        diagPayload.competitor_context = competitorContext;
      }

      const taskRes = await axios.post<DiagnosisTaskResponse>(
        `${getLongRunningApiBase()}/api/v1/diagnosis-tasks/listing`,
        diagPayload,
        { headers: getAuthHeaders(), timeout: 30000 }
      );
      moduleTaskId = `listing-diagnosis:${taskRes.data.task_id}`;
      upsertModuleTask({
        id: moduleTaskId,
        moduleKey: "listing-diagnosis",
        label: "本品Listing诊断",
        status: "running",
        detail: activeProductStage === "new_launch"
          ? "正在生成新品上架承接诊断"
          : "正在生成Listing承接诊断报告",
        path: "/listing-diagnosis",
      });
      localStorage.setItem(LISTING_DIAGNOSIS_TASK_KEY, taskRes.data.task_id);
      localStorage.setItem(
        LISTING_DIAGNOSIS_TASK_CONTEXT_KEY,
        JSON.stringify({ listing: diagPayload.listing, fetchMeta: activeFetchMeta, diagPayload })
      );
      toast.success("诊断任务已启动，可先查看其它页面，完成后会自动恢复");
      const task = await pollDiagnosisTask(taskRes.data.task_id);
      localStorage.removeItem(LISTING_DIAGNOSIS_TASK_KEY);
      localStorage.removeItem(LISTING_DIAGNOSIS_TASK_CONTEXT_KEY);
      if (!task.result_payload) throw new Error("诊断完成但未返回结果，请从历史诊断查看");
      await applyDiagnosisResult(task.result_payload, activeListing, activeFetchMeta, diagPayload);
      finishModuleTask(moduleTaskId, "completed", "本品诊断完成");
    } catch (err: unknown) {
      // Robust error handling - never let errors propagate to cause page navigation
      try {
        const msg = axios.isAxiosError(err)
          ? err.response?.data?.detail || (err.code === "ECONNABORTED" ? "诊断超过180秒，请稍后重试" : "诊断失败，请重试")
          : err instanceof Error
            ? err.message
          : "诊断失败，请重试";
        if (moduleTaskId) finishModuleTask(moduleTaskId, "failed", msg);
        toast.error(msg);
      } catch {
        if (moduleTaskId) finishModuleTask(moduleTaskId, "failed", "诊断失败，请重试");
        toast.error("诊断失败，请重试");
      }
      setDiagnosisPhase("error");
    } finally {
      setDiagnosing(false);
      if (moduleTaskId) window.setTimeout(() => removeModuleTask(moduleTaskId as string), 1200);
    }
  };

  const loadHistory = async (search?: string, mpFilter?: string) => {
    setHistoryLoading(true);
    try {
      const params = new URLSearchParams({ limit: "50" });
      const s = search !== undefined ? search : historySearch;
      const m = mpFilter !== undefined ? mpFilter : historyMpFilter;
      if (s) params.set("search", s);
      if (m) params.set("marketplace_filter", m);
      const res = await axios.get(`/api/v1/listing-diagnosis/history?${params.toString()}`, {
        headers: getAuthHeaders(),
      });
      setHistory(res.data.items || []);
      if (res.data.stats) setHistoryStats(res.data.stats);
    } catch {
      toast.error("加载历史记录失败");
    } finally {
      setHistoryLoading(false);
    }
    // Also load scrape stats
    loadScrapeStats();
  };

  useEffect(() => {
    if (!authLoading) loadHistory("", "");
  }, [authLoading]);

  const loadHistoryDetail = async (id: number) => {
    if (historyViewId === id) {
      // Toggle off
      setHistoryViewId(null);
      setHistoryDiagResult(null);
      return;
    }
    setHistoryDetailLoading(id);
    try {
      const res = await axios.get(`/api/v1/listing-diagnosis/history/${id}`, {
        headers: getAuthHeaders(),
      });
      const data = res.data;
      const report = data.diagnosis_report || {};
      const savedListing = cleanListing({
        ...EMPTY_LISTING,
        ...(data.input_data || {}),
        marketplace: data.marketplace || data.input_data?.marketplace || marketplace,
      });
      const savedMeta: FetchMeta = {
        asin: savedListing.asin || "",
        source: report.trace?.data_source || "history",
        rating: savedListing.rating || "",
        review_count: savedListing.review_count || "",
        bsr_rank: savedListing.bsr_rank || "",
        image_count: savedListing.image_count || "",
        has_video: savedListing.has_video || false,
        has_a_plus: savedListing.has_a_plus || false,
      };
      const result: DiagnosisResult = {
        scores: data.scores,
        analysis: report.analysis || {},
        suggestions: report.suggestions || {},
        keyword_coverage: report.keyword_coverage || data.keyword_report || {},
        ad_keywords: report.ad_keywords || {},
        elements: report.elements || {},
        market_estimates: report.market_estimates || {},
        overall_summary: report.overall_summary || "",
        analyzed_product_name: report.analyzed_product_name || "",
        product_mismatch: report.product_mismatch || false,
        product_mismatch_detail: report.product_mismatch_detail || "",
        id: data.id,
        listing_title: data.listing_title,
        marketplace: data.marketplace,
        causal_diagnosis: report.causal_diagnosis,
        causal_scores: report.causal_scores,
        judgment_system: report.judgment_system,
        ad_validation_plan: report.ad_validation_plan,
        ad_validation_readiness_gate: report.ad_validation_readiness_gate,
        decision_outputs: report.decision_outputs,
      };
      setHistoryDiagResult(normalizeDiagnosisResultForUi(result));
      setHistoryViewId(id);
      setHistoryResultTab("overview");
    } catch {
      toast.error("加载诊断详情失败");
    } finally {
      setHistoryDetailLoading(null);
    }
  };

  const loadDiagnosisAsCurrent = async (id: number) => {
    try {
      const res = await axios.get(`/api/v1/listing-diagnosis/history/${id}`, {
        headers: getAuthHeaders(),
      });
      const data = res.data;
      const report = data.diagnosis_report || {};
      const savedListing = cleanListing({
        ...EMPTY_LISTING,
        ...(data.input_data || {}),
        marketplace: data.marketplace || data.input_data?.marketplace || marketplace,
      });
      const savedMeta: FetchMeta = {
        asin: savedListing.asin || "",
        source: report.trace?.data_source || "history",
        rating: savedListing.rating || "",
        review_count: savedListing.review_count || "",
        bsr_rank: savedListing.bsr_rank || "",
        image_count: savedListing.image_count || "",
        has_video: savedListing.has_video || false,
        has_a_plus: savedListing.has_a_plus || false,
      };
      const result: DiagnosisResult = {
        scores: data.scores,
        analysis: report.analysis || {},
        suggestions: report.suggestions || {},
        keyword_coverage: report.keyword_coverage || data.keyword_report || {},
        ad_keywords: report.ad_keywords || {},
        elements: report.elements || {},
        market_estimates: report.market_estimates || {},
        overall_summary: report.overall_summary || "",
        analyzed_product_name: report.analyzed_product_name || "",
        product_mismatch: report.product_mismatch || false,
        product_mismatch_detail: report.product_mismatch_detail || "",
        id: data.id,
        listing_title: data.listing_title,
        marketplace: data.marketplace,
        data_integrity: report.data_integrity,
        diagnosis_confidence: report.diagnosis_confidence,
        causal_diagnosis: report.causal_diagnosis,
        causal_scores: report.causal_scores,
        judgment_system: report.judgment_system,
        ad_validation_plan: report.ad_validation_plan,
        ad_validation_readiness_gate: report.ad_validation_readiness_gate,
        decision_outputs: report.decision_outputs,
      };
      setListing(savedListing);
      setFetchMeta(savedMeta);
      setSelectedListingAsin(savedMeta.asin || "");
      const uiResult = normalizeDiagnosisResultForUi(result);
      setMarketValidation(deriveMarketValidationFromEvidence(savedListing, savedMeta, uiResult.market_estimates));
      setDiagResult(uiResult);
      setResultTab("overview");
      setActiveTab("diagnose");
      setDiagnosisPhase("analyzed");
      scrollToResultSection();
      toast.success("已打开历史本品诊断");
    } catch {
      toast.error("加载本品诊断失败");
    }
  };

  const loadSnapshotAsCurrentDiagnosis = (snapshot: ActionSnapshot) => {
    const output = snapshot.output_snapshot as DiagnosisResult | undefined;
    if (!output || !output.scores) {
      toast.error("该快照不是完整本品诊断结果，请从诊断历史打开");
      return;
    }
    setSelectedListingAsin(snapshot.asin || (output as { asin?: string }).asin || "");
    setDiagResult(normalizeDiagnosisResultForUi({
      ...output,
      id: output.id || snapshot.source_record_id || snapshot.id,
      listing_title: output.listing_title || snapshot.title || output.analyzed_product_name || "",
    }));
    setResultTab("overview");
    setActiveTab("diagnose");
    setDiagnosisPhase("analyzed");
    toast.success("已打开已保存本品诊断快照");
  };

  const deleteHistoryItem = async (id: number) => {
    if (!confirm("确定要删除这条诊断记录吗？")) return;
    setDeletingId(id);
    try {
      await axios.delete(`/api/v1/listing-diagnosis/history/${id}`, {
        headers: getAuthHeaders(),
      });
      toast.success("已删除");
      if (historyViewId === id) {
        setHistoryViewId(null);
        setHistoryDiagResult(null);
      }
      loadHistory();
    } catch {
      toast.error("删除失败");
    } finally {
      setDeletingId(null);
    }
  };

  // Build element data from diagnosis result
  const buildElements = (): ElementData[] => {
    if (!diagResult?.elements) return [];
    return ELEMENT_META.map((em) => {
      const ed = diagResult.elements?.[em.key] || {};
      return {
        key: em.key,
        label: em.label,
        icon: em.icon,
        dims: normalizeElementDims(ed as Record<string, unknown>),
        summary: (ed as Record<string, unknown>).summary as string || "",
      };
    });
  };

  // Build radar chart data
  const buildRadarScores = () => {
    if (!diagResult?.scores) return [];
    return DIMENSIONS.map((d) => ({
      label: d.label,
      value: diagResult.scores[d.key] || 0,
      color: d.stroke,
    }));
  };

  // Compute content score (avg of the 10 diagnosis dimensions)
  const contentScore = diagResult ? getAvgScore(diagResult.scores) : 0;
  // Compute final weighted total: content 65% + market 35%
  const weightedTotal = marketValidation
    ? Math.round(contentScore * 0.65 + marketValidation.market_total * 0.35)
    : contentScore;
  const grade = weightedTotal >= 80 ? "A" : weightedTotal >= 60 ? "B" : weightedTotal >= 40 ? "C" : "D";

  // Export report
  const handleExport = () => {
    if (!diagResult) return;
    const elements = buildElements();
    const lines = [
      `AlignX Listing诊断报告`, `${"=".repeat(50)}`, ``,
      `产品: ${listing.title}`, `站点: ${marketplace}`, ``,
      `综合评分: ${weightedTotal}/100 (${grade}级)`,
      ...(marketValidation ? [
        `  ├ 内容质量分: ${contentScore}/100 (权重65%)`,
        `  └ 市场验证分: ${marketValidation.market_total}/100 (权重35%)`,
      ] : [`  内容评分: ${contentScore}/100`]),
      ``,
      `--- Listing承接诊断 ---`,
      ...getTwoRulerScoreCards(diagResult.scores, marketValidation?.market_total).map(card => `${card.title}: ${card.score}/100 - ${card.desc}`),
      ``,
      `--- 10维诊断维度 ---`,
      ...DIMENSIONS.map(d => {
        const meta = DIMENSION_RULER_META[d.key];
        return `${d.label}: ${diagResult.scores[d.key] || 0}/100 | ${meta.layer} | 需求:${meta.intentScale} | 平台:${meta.platformScale} | ${formatAnalysisText(diagResult.analysis?.[d.key])}`;
      }),
      ``,
      ...(elements.length > 0 ? [
        `--- 模块级10维贡献 ---`,
        ...elements.map(e => `[${e.label}] ${e.summary}\n  功能表达:${e.dims.function_expression} 场景表达:${e.dims.scenario_expression} 身份适配:${e.dims.identity_fit} 心理利益:${e.dims.psychology_benefit} 风险消除:${e.dims.risk_elimination} 产品身份:${e.dims.product_identity} 兼容搭配:${e.dims.compatibility} 主观属性:${e.dims.subjective_properties} 差异化:${e.dims.differentiation} 市场趋势:${e.dims.market_trend}`),
        ``,
      ] : []),
      `--- 优化建议 ---`,
      ...(diagResult.suggestions?.title_rewrite ? [`标题优化: ${diagResult.suggestions.title_rewrite}`] : []),
      ...(diagResult.suggestions?.bullet_points_optimization?.map((bp, i) => `五点${i + 1}: ${bp}`) || []),
      ``, `--- 总体分析 ---`, diagResult.overall_summary,
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `listing-diagnosis-${Date.now()}.txt`; a.click();
    URL.revokeObjectURL(url);
    toast.success("报告已导出");
  };

  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-brand-600" />
      </div>
    );
  }

  const radarScores = buildRadarScores();
  const elementsData = buildElements();
  const formalGateMissing = resolveFormalGateMissing(listing, fetchMeta);
  const listingStandardMissing = resolveListingStandardMissing(listing, fetchMeta);
  const marketEvidenceMissing = resolveMarketEvidenceMissing(listing, fetchMeta);
  const productStage = resolveProductStage(listing, fetchMeta, productStageOverride);
  const isNewLaunchMode = productStage === "new_launch";
  const canGenerateFormalDiagnosis = !diagnosing && formalGateMissing.length === 0;
  const formalGateActionText = formalGateMissing.length > 0
    ? "补齐承接字段后再判断"
    : isNewLaunchMode
      ? "判断新品上架承接"
      : "判断成熟品承接";
  const updateListingCoreField = (field: keyof ListingInput, value: string) => {
    setListing((prev) => cleanListing({ ...prev, [field]: value }));
  };
  const updateMetaField = (field: keyof FetchMeta, value: string) => {
    setFetchMeta((prev) => ({ ...(prev || {}), [field]: value }));
  };

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto bg-[#f5f5f7]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-8 pt-14 md:pt-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-3">
            <div>
              <h1 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
                <ClipboardCheck className="w-5 h-5 sm:w-6 sm:h-6 text-brand-600" />
                Listing承接诊断
              </h1>
              <p className="text-gray-500 mt-1 text-sm">
                输入ASIN，判断标题、主图、五点、A+与广告承接优先级。
              </p>
            </div>
            {diagResult && (
              <Button variant="outline" size="sm" onClick={handleExport} className="border-gray-200 text-gray-600 hover:text-gray-900 hover:bg-gray-100 bg-transparent">
                <Download className="w-4 h-4 mr-1.5" /> 导出报告
              </Button>
            )}
          </div>

          <PageHeader
            objective="定位Listing承接优先级，避免无效广告承接"
            inputSource="站点、ASIN/Amazon链接、标题、主图/副图、五点、A+、价格、评分、评论、关键词"
            process="按买家需求、Amazon识别和转化承接定位点击/CVR问题"
            outputTarget="优先模块、预算保护动作、广告验证词组和失败回流规则"
            action="执行P0改动，并进入广告验证"
            feedback="保留改动快照，用广告数据判断放量或继续优化"
            tone="indigo"
          />

          <div className="mb-4 rounded-2xl border border-gray-200/70 bg-white/80 p-4 shadow-sm">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-[180px_1fr] sm:items-center">
              <div>
                <p className="text-sm font-semibold text-gray-950">站点选择</p>
                <p className="mt-0.5 text-xs text-gray-500">先确定站点，再抓取 Listing 数据。</p>
              </div>
              <MarketplaceSelect
                value={marketplace}
                onChange={updateListingMarketplace}
                triggerClassName="h-11 w-full rounded-xl border-gray-200 bg-gray-50 sm:max-w-[220px]"
              />
            </div>
          </div>

          <Card className="bg-white border-gray-200 mb-6 rounded-2xl">
            <CardContent className="p-5">
              <div className="flex flex-col lg:flex-row lg:items-end gap-3">
                <div className="flex-1">
                  <label className="text-xs text-gray-500 mb-1.5 block">ASIN 或 Amazon 商品链接</label>
                  <Input
                    placeholder="请输入 ASIN 或 Amazon 商品链接，例如 B0XXXXXXXX"
                    value={fetchUrl}
                    onChange={(e) => setFetchUrl(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !fetching) handleFetchUrl(); }}
                    className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-500 h-11"
                  />
                </div>
                <div className="flex flex-col sm:flex-row gap-2 lg:pb-0">
                  <Button
                    onClick={handleFetchUrl}
                    disabled={fetching}
                    className="bg-brand-600 hover:bg-brand-700 text-white h-11 px-6"
                  >
                    {fetching ? (
                      <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" />分析中</>
                    ) : (
                      <><Zap className="w-4 h-4 mr-1.5" />开始分析</>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    className="h-11 border-gray-200 text-gray-600 bg-white"
                    disabled={!latestDiagnosis}
                    onClick={() => latestDiagnosis && loadDiagnosisAsCurrent(latestDiagnosis.id)}
                  >
                    <History className="w-4 h-4 mr-1.5" />
                    最新结果
                  </Button>
                </div>
              </div>

              {fetching && (
                <div className="mt-4 rounded-lg border border-brand-100 bg-brand-50 px-3 py-3">
                  <div className="flex items-center justify-between text-xs text-brand-700">
                    <span className="flex items-center gap-1.5">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      {fetchProgress || "正在抓取 Listing 数据，预计 60 秒左右"}
                    </span>
                    <span>{fetchElapsed}s / 180s</span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-white">
                    <div className="h-full rounded-full bg-brand-600 transition-all duration-500" style={{ width: `${fetchProgressValue}%` }} />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="mb-6 rounded-2xl border-gray-200/70 bg-white/85 shadow-sm">
            <CardContent className="p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-gray-950">历史分析列表</h2>
                  <p className="mt-0.5 text-xs text-gray-500">查看已保存承接诊断，打开历史不会重新抓取。</p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => loadHistory(historySearch, historyMpFilter)}
                  className="h-9 rounded-xl border-gray-200 bg-white text-gray-600 hover:bg-gray-100"
                >
                  <History className="mr-1.5 h-3.5 w-3.5" />
                  刷新
                </Button>
              </div>
              {historyLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                </div>
              ) : history.length === 0 ? (
                <div className="rounded-xl bg-gray-50 px-4 py-8 text-center text-sm text-gray-500">
                  暂无诊断历史
                </div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {history.slice(0, 6).map((item) => {
                    const isCurrentHistory = diagResult?.id === item.id;
                    return (
                    <div
                      key={item.id}
                      className={`flex w-full items-center justify-between gap-4 py-3 ${isCurrentHistory ? "rounded-xl bg-brand-50 px-3" : ""}`}
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-semibold text-gray-900">{item.asin || "ASIN待补"}</span>
                          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-500">{item.marketplace || "US"}</span>
                        </div>
                        <p className="mt-1 truncate text-sm text-gray-600">{item.listing_title || "已保存承接诊断"}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-3">
                        <span className="text-xs text-gray-500">
                          {item.created_at ? new Date(item.created_at).toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : ""}
                        </span>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => loadDiagnosisAsCurrent(item.id)}
                          className={`h-8 rounded-xl px-3 text-xs font-semibold ${isCurrentHistory ? "border-brand-200 bg-brand-100 text-brand-700" : "border-gray-200 bg-white text-gray-700 hover:bg-gray-100"}`}
                        >
                          {isCurrentHistory ? "已打开" : "回看诊断"}
                        </Button>
                      </div>
                    </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          <Tabs value={activeTab} onValueChange={setActiveTab}>

            {/* ==================== DIAGNOSE TAB ==================== */}
            <TabsContent value="diagnose" className="space-y-6">
              {false && diagnosisPhase === "idle" && !hasMeaningfulListingData(listing) && !diagResult && (
                <Card className="border-brand-100 bg-brand-50">
                  <CardContent className="p-5">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-xl bg-white text-brand-600 flex items-center justify-center shrink-0">
                        <Zap className="w-5 h-5" />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm text-gray-600 leading-relaxed max-w-4xl">
	                          输入ASIN后，AlignX会定位标题、主图、副图、五点、A+、价格、评分、评论和关键词的承接优先级。
                        </p>
                        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                          {[
	                            "定位转化阻碍：主图 / 标题 / 价格 / 关键词 / 信任不足",
	                            "确认 Listing 是否承接买家搜索意图",
	                            "输出优先项，避免泛泛建议",
	                            "改动后验证转化变化",
                          ].map((item) => (
                            <div key={item} className="rounded-lg border border-brand-100 bg-white px-3 py-2 text-xs text-gray-700">
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 inline mr-1.5" />
                              {item}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {diagnosisPhase === "fetch_failed" && (
                <Card className="border-amber-100 bg-amber-50">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5" />
                      <div>
	                        <h3 className="text-sm font-semibold text-gray-900">Listing字段不完整，请补充核心字段。</h3>
	                        <p className="text-xs text-gray-600 mt-1">补充标题和五点后仍可生成判断，但置信度低于真实页面抓取。</p>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => setShowAdvancedEditor(true)}
                          className="mt-3 border-amber-200 bg-white text-amber-700 hover:bg-amber-50"
                        >
                          补齐核心字段
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {(diagnosisPhase === "fetch_success" || diagnosisPhase === "analyzing" || diagnosisPhase === "analyzed" || hasMeaningfulListingData(listing) || (diagnosisPhase === "fetch_failed" && showAdvancedEditor)) && (
                <Card className="bg-white border-gray-200">
                  <CardHeader className="pb-3">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                      <div>
                        <CardTitle className="text-base flex items-center gap-2">
                          <CheckCircle2 className="w-5 h-5 text-emerald-600" />
	                          判定条件
                        </CardTitle>
                      </div>
                      {fetchSource && (
                        <Badge variant="outline" className="w-fit border-emerald-200 bg-emerald-50 text-emerald-700">
                          数据来源：{sourceLabel(fetchSource)}
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="rounded-xl border border-gray-200 bg-gray-50/70 p-3">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-semibold text-gray-950">产品阶段</p>
                            {!productStageOverride && (
                              <Badge variant="outline" className="border-gray-200 bg-white text-gray-500">系统识别</Badge>
                            )}
                          </div>
                          <p className="mt-1 text-xs text-gray-500">
                            {isNewLaunchMode
                              ? "新品上架：先判断Listing是否具备首轮验证条件。"
                              : "成熟在售：先判断Listing是否接住现有流量。"}
                          </p>
                        </div>
                        <div className="grid grid-cols-2 gap-2 sm:w-[260px]">
                          <Button
                            type="button"
                            variant={productStage === "new_launch" ? "default" : "outline"}
                            onClick={() => setProductStageOverride("new_launch")}
                            className={`h-9 rounded-xl text-sm ${productStage === "new_launch" ? "bg-brand-600 text-white hover:bg-brand-700" : "border-gray-200 bg-white text-gray-600"}`}
                          >
                            新品上架
                          </Button>
                          <Button
                            type="button"
                            variant={productStage === "mature_listing" ? "default" : "outline"}
                            onClick={() => setProductStageOverride("mature_listing")}
                            className={`h-9 rounded-xl text-sm ${productStage === "mature_listing" ? "bg-brand-600 text-white hover:bg-brand-700" : "border-gray-200 bg-white text-gray-600"}`}
                          >
                            成熟在售
                          </Button>
                        </div>
                      </div>
                    </div>
                    {showAdvancedEditor && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                      <div className="lg:col-span-2 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
                        <label className="text-[11px] text-gray-500">标题关键词</label>
                        <Input
                          value={listing.title}
                          onChange={(e) => updateListingCoreField("title", e.target.value)}
                          placeholder="粘贴 Amazon 产品标题"
                          className="mt-1 h-9 bg-white border-gray-200 text-sm"
                        />
                      </div>
                      <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
                        <label className="text-[11px] text-gray-500">品牌</label>
                        <Input value={listing.brand} onChange={(e) => updateListingCoreField("brand", e.target.value)} placeholder="待确认" className="mt-1 h-9 bg-white border-gray-200 text-sm" />
                      </div>
                      <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
                        <label className="text-[11px] text-gray-500">类目</label>
                        <Input value={listing.category} onChange={(e) => updateListingCoreField("category", e.target.value)} placeholder="待确认" className="mt-1 h-9 bg-white border-gray-200 text-sm" />
                      </div>
                      <div className={`rounded-lg border px-3 py-2 ${formalGateMissing.includes("价格") ? "border-amber-200 bg-amber-50" : "border-gray-100 bg-gray-50"}`}>
                        <label className="text-[11px] text-gray-500">价格 *</label>
                        <Input value={listing.price} onChange={(e) => updateListingCoreField("price", e.target.value)} placeholder="如 $39.99" className="mt-1 h-9 bg-white border-gray-200 text-sm" />
                      </div>
                      <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
                        <label className="text-[11px] text-gray-500">评分</label>
                        <Input
                          value={fetchMeta?.rating || listing.rating || ""}
                          onChange={(e) => {
                            updateMetaField("rating", e.target.value);
                            updateListingCoreField("rating", e.target.value);
                          }}
                          placeholder="如 4.4"
                          className="mt-1 h-9 bg-white border-gray-200 text-sm"
                        />
                      </div>
                      <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
                        <label className="text-[11px] text-gray-500">评论数</label>
                        <Input
                          value={fetchMeta?.review_count || listing.review_count || ""}
                          onChange={(e) => {
                            updateMetaField("review_count", e.target.value);
                            updateListingCoreField("review_count", e.target.value);
                          }}
                          placeholder="如 88"
                          className="mt-1 h-9 bg-white border-gray-200 text-sm"
                        />
                      </div>
                      <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
                        <label className="text-[11px] text-gray-500">BSR</label>
                        <Input
                          value={fetchMeta?.bsr_rank || listing.bsr_rank || ""}
                          onChange={(e) => {
                            updateMetaField("bsr_rank", e.target.value);
                            updateListingCoreField("bsr_rank", e.target.value);
                          }}
                          placeholder="如 #10693"
                          className="mt-1 h-9 bg-white border-gray-200 text-sm"
                        />
                      </div>
                      <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
                        <label className="text-[11px] text-gray-500">图片总数</label>
                        <Input
                          value={fetchMeta?.image_count || listing.image_count || ""}
                          onChange={(e) => {
                            updateMetaField("image_count", e.target.value);
                            updateListingCoreField("image_count", e.target.value);
                          }}
                          placeholder="如 7"
                          className="mt-1 h-9 bg-white border-gray-200 text-sm"
                        />
                        <p className="mt-1 text-[10px] text-gray-500">主图/副图证据：主图1张，副图 {Math.max(getListingImageCount(listing, fetchMeta) - 1, 0)} 张</p>
                      </div>
                      <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
                        <label className="text-[11px] text-gray-500">A+</label>
                        <Select value={listing.has_a_plus || fetchMeta?.has_a_plus ? "yes" : "unknown"} onValueChange={(value) => {
                          const yes = value === "yes";
                          setListing((prev) => ({ ...prev, has_a_plus: yes }));
                          setFetchMeta((prev) => ({ ...(prev || {}), has_a_plus: yes }));
                        }}>
                          <SelectTrigger className="mt-1 h-9 bg-white border-gray-200 text-sm"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="yes">有</SelectItem>
                            <SelectItem value="unknown">无/待确认</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
                        <label className="text-[11px] text-gray-500">视频</label>
                        <Select value={listing.has_video || fetchMeta?.has_video ? "yes" : "unknown"} onValueChange={(value) => {
                          const yes = value === "yes";
                          setListing((prev) => ({ ...prev, has_video: yes }));
                          setFetchMeta((prev) => ({ ...(prev || {}), has_video: yes }));
                        }}>
                          <SelectTrigger className="mt-1 h-9 bg-white border-gray-200 text-sm"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="yes">有</SelectItem>
                            <SelectItem value="unknown">无/待确认</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className={`md:col-span-2 lg:col-span-4 rounded-lg border px-3 py-2 ${formalGateMissing.includes("五点") ? "border-amber-200 bg-amber-50" : "border-gray-100 bg-gray-50"}`}>
                        <label className="text-[11px] text-gray-500">五点 · 当前 {splitBullets(listing.bullet_points).length}/5</label>
                        <Textarea
                          value={listing.bullet_points}
                          onChange={(e) => updateListingCoreField("bullet_points", e.target.value)}
                          placeholder="粘贴五点描述，每条一行"
                          className="mt-1 min-h-[128px] bg-white border-gray-200 text-sm"
                        />
                      </div>
                    </div>
                    )}
                    {fetchMeta?.capture_quality && (
                      <div className={`rounded-lg border p-3 ${formalGateMissing.length === 0 ? "border-emerald-100 bg-emerald-50" : "border-amber-100 bg-amber-50"}`}>
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold text-gray-900">核心字段状态</p>
                            <p className="text-xs text-gray-600 mt-1">{fetchMeta.capture_quality.rule}</p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <Badge variant="outline">完整度 {fetchMeta.capture_quality.completeness ?? 0}%</Badge>
                            <Badge variant={formalGateMissing.length === 0 ? "default" : "secondary"}>
                              {formalGateMissing.length === 0
	                                ? isNewLaunchMode ? "新品承接可判定" : marketEvidenceMissing.length > 0 ? "承接可判定" : "可正式判定"
                                : "仅低置信预检"}
                            </Badge>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => setShowAdvancedEditor((prev) => !prev)}
                              className="h-7 border-amber-200 bg-white text-amber-700 hover:bg-amber-50"
                            >
                              {showAdvancedEditor ? "收起字段" : formalGateMissing.length > 0 ? "补齐缺失字段" : "复核字段"}
                            </Button>
                          </div>
                        </div>
                        {Boolean(listingStandardMissing.length || marketEvidenceMissing.length || fetchMeta.capture_quality.missing_strategy?.length) && (
                          <div className="mt-2 space-y-1 text-xs text-gray-600">
                            {formalGateMissing.length > 0 && (
                              <p>硬性承接字段需补齐：<span className="font-semibold">{formalGateMissing.join("、")}</span></p>
                            )}
                            {listingStandardMissing.filter((item) => !formalGateMissing.includes(item)).length > 0 && (
                              <p>五项标准待补：<span className="font-semibold">{listingStandardMissing.filter((item) => !formalGateMissing.includes(item)).join("、")}</span></p>
                            )}
                            {marketEvidenceMissing.length > 0 && (
                              <p>
                                {isNewLaunchMode ? "新品上架信号" : "市场证据缺失（不阻断新品承接诊断）"}：
                                <span className="font-semibold">{marketEvidenceMissing.join("、")}</span>
                              </p>
                            )}
                            {Boolean(fetchMeta.capture_quality.missing_strategy?.length) && (
                              <p>策略级证据待补：{(fetchMeta.capture_quality.missing_strategy || []).filter((item) => !marketEvidenceMissing.includes(item)).join("、") || "无"}</p>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                    {formalGateMissing.length > 0 && !fetchMeta?.capture_quality && (
                      <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
	                        当前无法输出决策结论。请先补齐：
                        <span className="font-semibold"> {formalGateMissing.join("、")} </span>
                      </div>
                    )}
                    {formalGateMissing.length === 0 && marketEvidenceMissing.length > 0 && !fetchMeta?.capture_quality && (
                      <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
	                        {isNewLaunchMode ? "已识别为新品上架，可判断Listing承接；" : "可判断成熟品承接；"}
                        缺失的市场证据会降低置信度：
                        <span className="font-semibold"> {marketEvidenceMissing.join("、")} </span>
                      </div>
                    )}
                    {showAdvancedEditor && (
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">后台关键词（Search Terms）</label>
                      <Input
                        value={listing.backend_keywords}
                        onChange={(e) => setListing((prev) => ({ ...prev, backend_keywords: e.target.value }))}
                        placeholder="补充 Search Terms，确认是否漏掉购买意图"
                        className="bg-gray-50 border-gray-200"
                      />
                    </div>
                    )}
                    <div className="flex flex-col sm:flex-row gap-2">
                      {diagResult ? (
                        <Button
                          disabled
                          className="bg-emerald-600 text-white min-w-[180px] opacity-100 disabled:opacity-100"
                        >
                          <CheckCircle2 className="w-4 h-4 mr-2" />
                          已生成运营动作
                        </Button>
                      ) : (
                        <Button
                          onClick={() => handleDiagnose()}
                          disabled={!canGenerateFormalDiagnosis}
                          className={`text-white min-w-[180px] ${canGenerateFormalDiagnosis ? "bg-brand-600 hover:bg-brand-700" : "bg-gray-300 cursor-not-allowed"}`}
                        >
                          {diagnosing ? (
                            <><Loader2 className="w-4 h-4 mr-2 animate-spin" />生成中...</>
                          ) : (
                            <><Zap className="w-4 h-4 mr-2" />{formalGateActionText}</>
                          )}
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        onClick={() => setShowAdvancedEditor(!showAdvancedEditor)}
                        className="border-gray-200 text-gray-600 bg-white"
                      >
                        {showAdvancedEditor ? <EyeOff className="w-4 h-4 mr-1.5" /> : <Eye className="w-4 h-4 mr-1.5" />}
                        {showAdvancedEditor ? "收起字段" : "补齐/复核字段"}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => setShowManualPaste(!showManualPaste)}
                        className="border-gray-200 text-gray-600 bg-white"
                      >
                        <ClipboardPaste className="w-4 h-4 mr-1.5" />
                        {showManualPaste ? "收起文本" : "粘贴页面文本"}
                      </Button>
                      {diagnosing && (
                        <span className="text-sm text-brand-600 flex items-center gap-2 sm:ml-2">
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
	                          正在生成承接判断，最多等待180秒...
                        </span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {showManualPaste && (
                <Card className="bg-white border-gray-200">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <ClipboardPaste className="w-4 h-4 text-brand-600" />
                      手动补页面内容
                    </CardTitle>
                    <p className="text-xs text-gray-500">仅在服务器抓取字段缺失时使用，解析后仍按同一套完整性规则判断。</p>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Textarea
                      placeholder="粘贴 Amazon 商品页 HTML 或页面可见文本。系统只提取证据字段，不自动猜空字段。"
                      value={manualPasteText}
                      onChange={(e) => setManualPasteText(e.target.value)}
                      className="bg-white border-gold-100 min-h-[160px] text-xs"
                    />
                    <Button onClick={handleManualPaste} disabled={!manualPasteText.trim()} className="bg-gold-600 hover:bg-gold-700 text-white">
                      <ClipboardPaste className="w-4 h-4 mr-1.5" />
                      解析页面内容
                    </Button>
                  </CardContent>
                </Card>
              )}

              {/* Diagnosis Results */}
              {diagResult && (
                <div ref={resultSectionRef} className="scroll-mt-6 space-y-6">
                  {/* Product Mismatch Warning */}
                  {diagResult.product_mismatch && (
                    <div className="flex items-start gap-3 p-3 rounded-lg bg-red-500/15 border border-red-200">
                      <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-bold text-red-600">⚠️ 产品名称不匹配警告</p>
                        <p className="text-xs text-red-600/80 mt-0.5">
                          {diagResult.product_mismatch_detail ||
                            `诊断识别的产品名称「${diagResult.analyzed_product_name}」与您输入的产品「${listing.title}」不一致。分析结果可能不准确，建议重新运行诊断。`}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Result Sub-tabs */}
                  <Tabs value={resultTab} onValueChange={setResultTab}>
                    <TabsList className="bg-gray-50 border border-gray-200 flex-wrap">
                      <TabsTrigger value="overview" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600 text-xs sm:text-sm">
                        决策结论
                      </TabsTrigger>
                      <TabsTrigger value="scores" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600 text-xs sm:text-sm">
                        承接评分
                      </TabsTrigger>
                      <TabsTrigger value="heatmap" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600 text-xs sm:text-sm">
                        问题归因
                      </TabsTrigger>
                      <TabsTrigger value="keywords" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600 text-xs sm:text-sm">
                        补哪些词
                      </TabsTrigger>
                      <TabsTrigger value="suggestions" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600 text-xs sm:text-sm">
                        优化动作
                      </TabsTrigger>
                      <TabsTrigger value="hypotheses" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600 text-xs sm:text-sm">
                        验证假设
                      </TabsTrigger>
                      <TabsTrigger value="adkeywords" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600 text-xs sm:text-sm">
                        验证词组
                      </TabsTrigger>
                    </TabsList>

                    {/* ===== OVERVIEW TAB ===== */}
                    <TabsContent value="overview" className="mt-4 space-y-6">
                      <BackendJudgmentPanel result={diagResult} />
                      <PrecisionConfidencePanel integrity={diagResult.data_integrity} />
                      <DiagnosisTraceBar result={diagResult} />
                    </TabsContent>

                    <TabsContent value="hypotheses" className="mt-4">
                      <ListingHypothesisLoopPanel result={diagResult} listing={listing} />
                    </TabsContent>

                    {/* ===== 10 Dimension Scores ===== */}
                    <TabsContent value="scores" className="mt-4">
                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
                        <Card className="bg-gray-50 border-gray-200 p-5 flex flex-col items-center justify-center">
                          <p className="text-sm text-gray-500 mb-3">综合评分</p>
                          <div className="relative w-28 h-28">
                            <svg className="w-28 h-28 -rotate-90" viewBox="0 0 120 120">
                              <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="10" />
                              <circle cx="60" cy="60" r="50" fill="none" stroke={getGradeColor(grade)} strokeWidth="10" strokeDasharray={`${(weightedTotal / 100) * 314} 314`} strokeLinecap="round" className="transition-all duration-1000" />
                            </svg>
                            <div className="absolute inset-0 flex flex-col items-center justify-center">
                              <span className="text-2xl font-bold">{weightedTotal}</span>
                              <span className="text-xs text-gray-500">/100</span>
                            </div>
                          </div>
                          <p className="text-lg font-bold mt-2" style={{ color: getGradeColor(grade) }}>等级 {grade}</p>
                          <div className="w-full mt-4 space-y-2">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-brand-600">内容质量 (65%)</span>
                              <span className="font-semibold">{contentScore}</span>
                            </div>
                            <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                              <div className={`h-full rounded-full transition-all duration-700 ${scoreBgColor(contentScore)}`} style={{ width: `${contentScore}%` }} />
                            </div>
                            {marketValidation && (
                              <>
                                <div className="flex items-center justify-between text-xs">
                                  <span className="text-teal-600">市场验证 (35%)</span>
                                  <span className="font-semibold">{marketValidation.market_total}</span>
                                </div>
                                <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                  <div className={`h-full rounded-full transition-all duration-700 ${scoreBgColor(marketValidation.market_total)}`} style={{ width: `${marketValidation.market_total}%` }} />
                                </div>
                                <p className="text-[10px] text-gray-600 text-center mt-1">
                                  {weightedTotal} = {contentScore}×0.65 + {marketValidation.market_total}×0.35
                                </p>
                              </>
                            )}
                          </div>
                        </Card>

                        {radarScores.length > 0 && (
                          <Card className="bg-gray-50 border-gray-200 p-5 flex items-center justify-center">
                            <RadarChart scores={radarScores} size={220} />
                          </Card>
                        )}

                        {marketValidation ? (
                          <MarketValidationPanel mv={marketValidation} />
                        ) : (
                          <Card className="bg-gray-50 border-gray-200 p-5">
                            <div className="flex items-center gap-2 mb-3">
                              <BarChart3 className="w-4 h-4 text-brand-600" />
                              <p className="text-sm font-semibold text-gray-600">市场验证</p>
                            </div>
                            <p className="text-xs text-gray-500">市场验证数据将在诊断完成后自动生成。如需更精确的数据，请在输入中填写价格、评分等信息。</p>
                          </Card>
                        )}
                      </div>

                      <div className="mb-4">
                        <TwoRulerSummary scores={diagResult.scores} marketScore={marketValidation?.market_total} />
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {DIMENSIONS.map((dim) => (
                          <ScoreBar
                            key={dim.key}
                            dim={dim}
                            score={diagResult.scores[dim.key] || 0}
                            analysis={diagResult.analysis?.[dim.key]}
                          />
                        ))}
                      </div>
                    </TabsContent>

                    {/* ===== Module Attribution Heatmap ===== */}
                    <TabsContent value="heatmap" className="mt-4">
                      <div className="mb-4">
                        <PriorityIssueTable rows={buildPriorityIssues(diagResult)} />
                      </div>
                      {elementsData.length > 0 ? (
                        <Card className="bg-gray-50 border-gray-200 p-5">
                          <div className="mb-4">
                            <h3 className="text-sm font-semibold text-gray-700">Listing模块问题图</h3>
                            <p className="mt-1 text-xs text-gray-500 leading-relaxed">
                              行分用于定位标题、五点、图片、A+或Search Terms哪个模块拖后腿；列分会汇总到最终承接分。价格、评论、BSR和广告数据属于验证参考，不和单个模块行分直接对比。
                            </p>
                          </div>
                          <div className="overflow-x-auto">
                            <table className="w-full min-w-[600px]">
                              <thead>
                                <tr>
                                  <th className="text-left text-xs text-gray-500 pb-2 pr-3 w-24">要素</th>
                                  {HEATMAP_DIM_KEYS.map(m => (
                                    <th key={m.key} className={`text-center text-[10px] pb-2 px-1 ${m.color}`}>{m.label}</th>
                                  ))}
                                  <th className="text-center text-xs text-gray-500 pb-2 px-1">平均</th>
                                </tr>
                              </thead>
                              <tbody>
                                {elementsData.map(el => {
                                  const vals = HEATMAP_DIM_KEYS.map(d => el.dims[d.key]).filter(v => typeof v === "number" && !isNaN(v));
                                  const avg = vals.length > 0 ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : 0;
                                  return (
                                    <tr key={el.key}>
                                      <td className="py-1 pr-3">
                                        <button className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-gray-900" onClick={() => setExpandedEl(expandedEl === el.key ? null : el.key)}>
                                          {el.icon} {el.label}
                                          {expandedEl === el.key ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                                        </button>
                                      </td>
                                      {HEATMAP_DIM_KEYS.map((d) => (
                                        <td key={d.key} className="px-1 py-1"><HeatmapCell value={el.dims[d.key]} /></td>
                                      ))}
                                      <td className="px-1 py-1"><HeatmapCell value={avg} /></td>
                                    </tr>
                                  );
                                })}
                                <tr className="border-t border-gray-200">
                                  <td className="py-2 pr-3">
                                    <span className="text-xs font-semibold text-gray-700">最终承接分</span>
                                  </td>
                                  {HEATMAP_DIM_KEYS.map((d) => (
                                    <td key={d.key} className="px-1 py-2">
                                      <HeatmapCell value={Number(diagResult.scores[d.key as keyof Scores]) || 0} />
                                    </td>
                                  ))}
                                  <td className="px-1 py-2">
                                    <HeatmapCell value={getAvgScore(diagResult.scores)} />
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                          {expandedEl && elementsData.find(e => e.key === expandedEl) && (
                            <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-100 text-xs text-gray-500 animate-in fade-in duration-200">
                              <p className="text-gray-600 font-medium mb-1">{elementsData.find(e => e.key === expandedEl)!.label} 分析:</p>
                              <p>{elementsData.find(e => e.key === expandedEl)!.summary}</p>
                            </div>
                          )}
                          <div className="flex items-center gap-3 mt-3 text-[10px] text-gray-600">
                            <span>色阶: </span>
                            <span className="px-2 py-0.5 rounded bg-red-500/50 text-gray-900">0-19</span>
                            <span className="px-2 py-0.5 rounded bg-orange-500/50 text-gray-900">20-39</span>
                            <span className="px-2 py-0.5 rounded bg-amber-500/50 text-gray-900">40-59</span>
                            <span className="px-2 py-0.5 rounded bg-teal-500/50 text-gray-900">60-79</span>
                            <span className="px-2 py-0.5 rounded bg-emerald-500/60 text-gray-900">80-100</span>
                          </div>
                          <p className="mt-2 text-[11px] text-gray-500 leading-relaxed">
                            若模块行分较高但验证参考较低，通常是价格、评论、BSR、销量或广告数据不足；若Search Terms行分偏低，说明关系词、状态词证据不足，会影响Amazon识别和广告匹配。
                          </p>
                        </Card>
                      ) : (
                        <Card className="bg-gray-50 border-gray-200 p-8 text-center">
                          <p className="text-gray-500 text-sm">暂无模块问题数据</p>
                        </Card>
                      )}
                    </TabsContent>

                    {/* ===== Keyword Coverage ===== */}
                    <TabsContent value="keywords" className="mt-4 space-y-4">
                      {diagResult.keyword_coverage && (
                        <>
                          <Card className="bg-gray-50 border-gray-200">
                            <CardHeader className="pb-2">
                              <CardTitle className="text-base flex items-center justify-between">
                                <span className="flex items-center gap-2">
                                  <Search className="w-4 h-4 text-brand-600" />
                                  购买意图覆盖
                                </span>
                                <span className={`text-2xl font-bold ${scoreColor(diagResult.keyword_coverage.coverage_score || 0)}`}>
                                  {diagResult.keyword_coverage.coverage_score || 0}%
                                </span>
                              </CardTitle>
                            </CardHeader>
                            <CardContent>
                              <p className="text-sm text-gray-500">{diagResult.keyword_coverage.coverage_summary}</p>
                            </CardContent>
                          </Card>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <Card className="bg-gray-50 border-emerald-500/20">
                              <CardHeader className="pb-2">
                                <CardTitle className="text-sm flex items-center gap-2 text-emerald-600">
                                  <CheckCircle2 className="w-4 h-4" /> 已覆盖意图词
                                </CardTitle>
                              </CardHeader>
                              <CardContent className="space-y-3">
                                {diagResult.keyword_coverage.covered_categories &&
                                  Object.entries(diagResult.keyword_coverage.covered_categories).map(([cat, words]) => (
                                    words && words.length > 0 && (
                                      <div key={cat}>
                                        <span className="text-xs text-gray-500">{KW_CATEGORY_LABELS[cat] || cat}</span>
                                        <div className="flex flex-wrap gap-1 mt-1">
                                          {words.map((w, i) => (
                                            <Badge key={i} variant="secondary" className="text-[10px] bg-emerald-50 text-emerald-600 border-emerald-500/20">
                                              {w}
                                            </Badge>
                                          ))}
                                        </div>
                                      </div>
                                    )
                                  ))}
                              </CardContent>
                            </Card>

                            <Card className="bg-gray-50 border-red-500/20">
                              <CardHeader className="pb-2">
                                <CardTitle className="text-sm flex items-center gap-2 text-red-600">
                                  <XCircle className="w-4 h-4" /> 还要补的词
                                </CardTitle>
                              </CardHeader>
                              <CardContent className="space-y-3">
                                {diagResult.keyword_coverage.missing_categories &&
                                  Object.entries(diagResult.keyword_coverage.missing_categories).map(([cat, words]) => (
                                    words && words.length > 0 && (
                                      <div key={cat}>
                                        <span className="text-xs text-gray-500">{KW_CATEGORY_LABELS[cat] || cat}</span>
                                        <div className="flex flex-wrap gap-1 mt-1">
                                          {words.map((w, i) => (
                                            <Badge key={i} variant="secondary" className="text-[10px] bg-red-50 text-red-600 border-red-500/20">
                                              {w}
                                            </Badge>
                                          ))}
                                        </div>
                                      </div>
                                    )
                                  ))}
                              </CardContent>
                            </Card>
                          </div>
                        </>
                      )}
                    </TabsContent>

                    {/* ===== Optimization Suggestions ===== */}
                    <TabsContent value="suggestions" className="mt-4 space-y-4">
                      <ModuleDiagnosisCards result={diagResult} listing={listing} />

                      {diagResult.suggestions && (
                        <>
                          {diagResult.suggestions.title_rewrite && (
                            <Card className="bg-gray-50 border-gray-200">
                              <CardHeader className="pb-2">
                                <CardTitle className="text-sm flex items-center justify-between">
                                  <span className="flex items-center gap-2">
                                    <ArrowRight className="w-4 h-4 text-brand-600" />
                                    标题直接这样改
                                  </span>
                                  <CopyBtn text={diagResult.suggestions.title_rewrite} />
                                </CardTitle>
                              </CardHeader>
                              <CardContent>
                                <p className="text-sm text-emerald-600 bg-emerald-500/5 rounded-lg p-3 border border-emerald-500/10 font-medium">
                                  {diagResult.suggestions.title_rewrite}
                                </p>
                              </CardContent>
                            </Card>
                          )}

                          {diagResult.suggestions.bullet_points_optimization && diagResult.suggestions.bullet_points_optimization.length > 0 && (
                            <Card className="bg-gray-50 border-gray-200">
                              <CardHeader className="pb-2">
                                <CardTitle className="text-sm flex items-center justify-between">
                                  <span className="flex items-center gap-2">
                                    <ArrowRight className="w-4 h-4 text-brand-600" />
                                    五点按这个顺序改
                                  </span>
                                  <CopyBtn text={diagResult.suggestions.bullet_points_optimization.join("\n")} />
                                </CardTitle>
                              </CardHeader>
                              <CardContent className="space-y-2">
                                {diagResult.suggestions.bullet_points_optimization.map((bp, i) => (
                                  <div key={i} className="flex gap-2 items-start text-sm">
                                    <span className="text-brand-600 font-bold flex-shrink-0 mt-0.5">{i + 1}.</span>
                                    <span className="text-gray-600">{bp}</span>
                                  </div>
                                ))}
                              </CardContent>
                            </Card>
                          )}

                          {diagResult.suggestions.backend_keywords_addition && diagResult.suggestions.backend_keywords_addition.length > 0 && (
                            <Card className="bg-gray-50 border-gray-200">
                              <CardHeader className="pb-2">
                                <CardTitle className="text-sm flex items-center justify-between">
                                  <span className="flex items-center gap-2">
                                    <ArrowRight className="w-4 h-4 text-brand-600" />
                                    Search Terms补这些词
                                  </span>
                                  <CopyBtn text={diagResult.suggestions.backend_keywords_addition.join(", ")} />
                                </CardTitle>
                              </CardHeader>
                              <CardContent>
                                <div className="flex flex-wrap gap-2">
                                  {diagResult.suggestions.backend_keywords_addition.map((kw, i) => (
                                    <Badge key={i} variant="outline" className="text-xs text-brand-600 border-brand-200">
                                      {kw}
                                    </Badge>
                                  ))}
                                </div>
                              </CardContent>
                            </Card>
                          )}

                          {(diagResult.suggestions.image_suggestions || diagResult.suggestions.a_plus_suggestions) && (
                            <Card className="bg-gray-50 border-gray-200">
                              <CardHeader className="pb-2">
                                <CardTitle className="text-sm flex items-center gap-2">
                                  <ArrowRight className="w-4 h-4 text-brand-600" />
                                  图片与A+先补这些证据
                                </CardTitle>
                              </CardHeader>
                              <CardContent className="space-y-3">
                                {diagResult.suggestions.image_suggestions?.map((s, i) => (
                                  <p key={i} className="text-sm text-gray-500 flex gap-2">
                                    <span className="text-brand-600">📷</span> {s}
                                  </p>
                                ))}
                                {diagResult.suggestions.a_plus_suggestions && (
                                  <p className="text-sm text-gray-500 flex gap-2">
                                    <span className="text-gold-600">✨</span> {diagResult.suggestions.a_plus_suggestions}
                                  </p>
                                )}
                              </CardContent>
                            </Card>
                          )}
                        </>
                      )}
                    </TabsContent>

                    {/* ===== Ad Keywords ===== */}
                    <TabsContent value="adkeywords" className="mt-4 space-y-4">
                      {diagResult.ad_keywords && (
                        <>
                          {diagResult.ad_keywords.ad_summary && (
                            <Card className="bg-gray-50 border-gray-200">
                              <CardContent className="pt-4">
                                <div className="flex items-center gap-2 mb-2">
                                  <Megaphone className="w-4 h-4 text-brand-600" />
                                  <span className="text-sm font-medium text-gray-600">广告验证词组</span>
                                </div>
                                <p className="text-sm text-gray-500">{diagResult.ad_keywords.ad_summary}</p>
                              </CardContent>
                            </Card>
                          )}

                          <AdKeywordSection title="转化验证词" subtitle="验证CVR" keywords={sanitizeAdKeywordList(diagResult.ad_keywords.high_conversion, listing.title || diagResult.listing_title, "high_conversion")} accentColor="emerald" />
                          <AdKeywordSection title="流量验证词" subtitle="控制预算" keywords={sanitizeAdKeywordList(diagResult.ad_keywords.traffic, listing.title || diagResult.listing_title, "traffic")} accentColor="blue" />
                          <AdKeywordSection title="长尾验证词" subtitle="观察CVR" keywords={sanitizeAdKeywordList(diagResult.ad_keywords.long_tail, listing.title || diagResult.listing_title, "long_tail")} accentColor="purple" />

                          {diagResult.ad_keywords.negative && diagResult.ad_keywords.negative.length > 0 && (
                            <Card className="bg-gray-50 border-red-500/20">
                              <CardHeader className="pb-2">
                                <CardTitle className="text-sm flex items-center gap-2 text-red-600">
                                  <AlertTriangle className="w-4 h-4" /> 先否掉这些词
                                </CardTitle>
                              </CardHeader>
                              <CardContent>
                                <div className="flex flex-wrap gap-2">
                                  {diagResult.ad_keywords.negative.map((kw, i) => (
                                    <Badge key={i} variant="outline" className="text-xs text-red-600 border-red-200">
                                      {kw}
                                    </Badge>
                                  ))}
                                </div>
                              </CardContent>
                            </Card>
                          )}
                        </>
                      )}
                    </TabsContent>
                  </Tabs>
                </div>
              )}
            </TabsContent>

            {/* ==================== HISTORY TAB ==================== */}
            <TabsContent value="history" className="space-y-4">
              <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                历史记录为已保存诊断快照，查看详情只读取已保存数据，不会重新抓取页面或重新生成诊断。
              </div>
              {/* Stats Panel */}
              {historyStats && historyStats.total_count > 0 && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <Card className="bg-gray-50 border-gray-200 p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <BarChart2 className="w-3.5 h-3.5 text-brand-600" />
                      <span className="text-[10px] text-gray-500">总诊断次数</span>
                    </div>
                    <p className="text-xl font-bold text-gray-900">{historyStats.total_count}</p>
                  </Card>
                  <Card className="bg-gray-50 border-gray-200 p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <TrendingUp className="w-3.5 h-3.5 text-teal-600" />
                      <span className="text-[10px] text-gray-500">平均分</span>
                    </div>
                    <p className={`text-xl font-bold ${scoreColor(historyStats.overall_avg)}`}>
                      {historyStats.overall_avg}
                    </p>
                  </Card>
                  <Card className="bg-gray-50 border-gray-200 p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <Trophy className="w-3.5 h-3.5 text-emerald-600" />
                      <span className="text-[10px] text-gray-500">最高均分</span>
                    </div>
                    <p className={`text-xl font-bold ${scoreColor(historyStats.max_avg)}`}>
                      {historyStats.max_avg}
                    </p>
                  </Card>
                  <Card className="bg-gray-50 border-gray-200 p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <ArrowDown className="w-3.5 h-3.5 text-red-600" />
                      <span className="text-[10px] text-gray-500">最低均分</span>
                    </div>
                    <p className={`text-xl font-bold ${scoreColor(historyStats.min_avg)}`}>
                      {historyStats.min_avg}
                    </p>
                  </Card>
                </div>
              )}

              {/* Scrape Statistics Panel */}
              {scrapeStats && scrapeStats.total_attempts > 0 && (
                <Card className="bg-gray-50 border-gray-200">
                  <button
                    className="w-full flex items-center justify-between p-4 text-left"
                    onClick={() => setScrapeStatsExpanded(!scrapeStatsExpanded)}
                  >
                    <div className="flex items-center gap-2">
                      <BarChart2 className="w-4 h-4 text-amber-600" />
                      <span className="text-sm font-medium text-gray-600">数据抓取统计</span>
                      <Badge variant="secondary" className="text-[10px]">
                        成功率 {scrapeStats.success_rate}%
                      </Badge>
                    </div>
                    <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${scrapeStatsExpanded ? "rotate-180" : ""}`} />
                  </button>
                  {scrapeStatsExpanded && (
                    <div className="px-4 pb-4 space-y-4">
                      {/* Summary cards */}
                      <div className="grid grid-cols-3 gap-3">
                        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
                          <p className="text-[10px] text-gray-500 mb-1">总抓取次数</p>
                          <p className="text-lg font-bold text-gray-900">{scrapeStats.total_attempts}</p>
                        </div>
                        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
                          <p className="text-[10px] text-gray-500 mb-1">成功次数</p>
                          <p className="text-lg font-bold text-emerald-600">{scrapeStats.total_success}</p>
                        </div>
                        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
                          <p className="text-[10px] text-gray-500 mb-1">成功率</p>
                          <p className={`text-lg font-bold ${scrapeStats.success_rate >= 70 ? "text-emerald-600" : scrapeStats.success_rate >= 40 ? "text-amber-600" : "text-red-600"}`}>
                            {scrapeStats.success_rate}%
                          </p>
                        </div>
                      </div>

                      {/* Method breakdown */}
                      {Object.keys(scrapeStats.method_stats).length > 0 && (
                        <div>
                          <p className="text-xs text-gray-500 mb-2">按抓取方式</p>
                          <div className="space-y-2">
                            {Object.entries(scrapeStats.method_stats).map(([method, stats]) => (
                              <div key={method} className="flex items-center gap-3">
                                <span className="text-xs text-gray-500 w-28 truncate">{
                                  method === "local_browser_capture" ? "🌐 本地浏览器" :
                                  method === "server_proxy_fetch" || method === "cors_proxy" || method === "backend_proxy" || method === "browser_proxy" ? "🛰️ 服务器代理" :
                                  method === "server_scrape" ? "🔍 服务器抓取" :
                                  method === "manual_paste" ? "📋 手动粘贴" : method
                                }</span>
                                <div className="flex-1 h-2 bg-gray-50 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full transition-all ${stats.rate >= 70 ? "bg-emerald-500" : stats.rate >= 40 ? "bg-amber-500" : "bg-red-500"}`}
                                    style={{ width: `${stats.rate}%` }}
                                  />
                                </div>
                                <span className="text-xs text-gray-500 w-24 text-right">
                                  {stats.success}/{stats.total} ({stats.rate}%)
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Recent logs */}
                      {scrapeStats.recent_logs && scrapeStats.recent_logs.length > 0 && (
                        <div>
                          <p className="text-xs text-gray-500 mb-2">最近抓取记录</p>
                          <div className="space-y-1 max-h-48 overflow-y-auto">
                            {scrapeStats.recent_logs.map((log) => (
                              <div key={log.id} className="flex items-center gap-2 text-xs py-1.5 px-2 rounded bg-gray-50">
                                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${log.success ? "bg-emerald-400" : "bg-red-400"}`} />
                                <span className="text-gray-500 w-20 truncate font-mono">{log.asin}</span>
                                <Badge variant="outline" className="text-[9px] px-1 py-0 h-4 border-gray-200 text-gray-500">{log.marketplace}</Badge>
                                <span className="text-gray-500 truncate flex-1">{
                                  log.scrape_method === "local_browser_capture" ? "本地浏览器" :
                                  log.scrape_method === "server_proxy_fetch" || log.scrape_method === "cors_proxy" || log.scrape_method === "backend_proxy" || log.scrape_method === "browser_proxy" ? "服务器代理" :
                                  log.scrape_method === "server_scrape" ? "服务器抓取" :
                                  log.scrape_method === "manual_paste" ? "手动粘贴" : log.scrape_method
                                }</span>
                                {log.error_message && (
                                  <span className="text-red-600/70 truncate max-w-[120px]" title={log.error_message}>{log.error_message}</span>
                                )}
                                <span className="text-gray-600 text-[10px] flex-shrink-0">
                                  {log.created_at ? new Date(log.created_at).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : ""}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </Card>
              )}

              {/* Search & Filter */}
              <div className="flex flex-col sm:flex-row gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                  <Input
                    placeholder="搜索产品标题..."
                    value={historySearch}
                    onChange={(e) => setHistorySearch(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") loadHistory(historySearch, historyMpFilter); }}
                    className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-600 pl-9"
                  />
                </div>
                <Select value={historyMpFilter} onValueChange={(v) => { const val = v === "ALL" ? "" : v; setHistoryMpFilter(val); loadHistory(historySearch, val); }}>
                  <SelectTrigger className="w-full sm:w-[160px] bg-gray-50 border-gray-200 text-gray-600">
                    <Filter className="w-3.5 h-3.5 mr-1.5 text-gray-500" />
                    <SelectValue placeholder="全部站点" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ALL">全部站点</SelectItem>
                    {MARKETPLACE_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => loadHistory(historySearch, historyMpFilter)}
                  className="border-gray-200 text-gray-600 hover:text-gray-900 hover:bg-gray-100 bg-transparent h-10"
                >
                  <Search className="w-4 h-4 mr-1" /> 搜索
                </Button>
              </div>

              {historyLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin text-brand-600" />
                </div>
              ) : history.length === 0 ? (
                <Card className="bg-gray-50 border-gray-200">
                  <CardContent className="py-12 text-center text-gray-500">
                    <History className="w-10 h-10 mx-auto mb-3 opacity-40" />
                    <p>{historySearch || historyMpFilter ? "未找到匹配的诊断记录" : "暂无诊断历史"}</p>
                    {(historySearch || historyMpFilter) && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="mt-2 text-brand-600 hover:text-brand-600"
                        onClick={() => { setHistorySearch(""); setHistoryMpFilter(""); loadHistory("", ""); }}
                      >
                        清除筛选
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ) : (
                <div className="grid gap-3">
                  {history.map((item) => {
                    const isViewing = historyViewId === item.id;
                    const isLoadingDetail = historyDetailLoading === item.id;
                    const isDeleting = deletingId === item.id;
                    return (
                      <div key={item.id}>
                        <Card className={`bg-gray-50 border-gray-200 transition-all ${isViewing ? "border-brand-200 bg-brand-500/[0.03]" : "hover:bg-gray-100"}`}>
                          <CardContent className="py-4">
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                              <div
                                className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer"
                                onClick={() => loadHistoryDetail(item.id)}
                              >
                                <Badge variant="secondary" className="text-xs flex-shrink-0">
                                  {item.marketplace}
                                </Badge>
                                <span className="text-sm text-gray-600 truncate">
                                  {item.listing_title || "—"}
                                </span>
                                {isLoadingDetail && <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-600 flex-shrink-0" />}
                              </div>
                              <div className="flex items-center gap-3 flex-shrink-0">
                                <span className={`text-sm font-semibold ${scoreColor(getAvgScore(item.scores))}`}>
                                  均分: {getAvgScore(item.scores)}
                                </span>
                                <span className="text-xs text-gray-500">
                                  {item.created_at ? new Date(item.created_at).toLocaleString("zh-CN") : ""}
                                </span>
                                <button
                                  onClick={() => loadHistoryDetail(item.id)}
                                  className={`p-1.5 rounded-md transition-colors ${isViewing ? "bg-brand-100 text-brand-600" : "text-gray-500 hover:text-brand-600 hover:bg-gray-100"}`}
                                  title={isViewing ? "收起详情" : "查看详情"}
                                >
                                  {isViewing ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                </button>
                                <button
                                  onClick={() => deleteHistoryItem(item.id)}
                                  disabled={isDeleting}
                                  className="p-1.5 rounded-md text-gray-500 hover:text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
                                  title="删除"
                                >
                                  {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                                </button>
                              </div>
                            </div>
                            <div className="grid grid-cols-6 gap-2 mt-3">
                              {DIMENSIONS.map((dim) => {
                                const s = item.scores[dim.key] || 0;
                                return (
                                  <div key={dim.key} className="text-center">
                                    <div className="text-[10px] text-gray-600 mb-1">{dim.label}</div>
                                    <div className={`text-xs font-bold ${scoreColor(s)}`}>{s}</div>
                                  </div>
                                );
                              })}
                            </div>
                          </CardContent>
                        </Card>

                        {/* Expanded Detail View */}
                        {isViewing && historyDiagResult && (
                          <div className="mt-2 ml-2 mr-2 mb-4 animate-in fade-in slide-in-from-top-2 duration-300">
                            <HistoryDetailView
                              result={historyDiagResult}
                              resultTab={historyResultTab}
                              setResultTab={setHistoryResultTab}
                              expandedEl={expandedEl}
                              setExpandedEl={setExpandedEl}
                            />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </TabsContent>
          </Tabs>

          <NextStepActions
            currentStep="本品诊断"
            actions={[
              { label: "生成A/B测试", path: "/ab-test-comparison", variant: "default" },
            ]}
          />
        </div>
      </main>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Listing Diagnosis Decision Panels                                  */
/* ------------------------------------------------------------------ */

function PriorityIssueTable({ rows }: { rows: PriorityIssue[] }) {
  const impactClass: Record<PriorityIssue["impact"], string> = {
    高: "bg-red-50 text-red-700 border-red-200",
    中: "bg-amber-50 text-amber-700 border-amber-200",
    低: "bg-emerald-50 text-emerald-700 border-emerald-200",
  };
  const priorityClass: Record<PriorityIssue["priority"], string> = {
    "P0 立即优化": "bg-red-600 text-white",
    "P1 建议优化": "bg-amber-500 text-white",
    "P2 暂不处理": "bg-gray-100 text-gray-600",
  };

  return (
    <Card className="bg-white border-gray-200">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Target className="w-5 h-5 text-brand-600" />
          优先清单
        </CardTitle>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full min-w-[820px] text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
              <th className="py-3 pr-3">问题位置</th>
              <th className="py-3 pr-3">为什么影响转化</th>
              <th className="py-3 pr-3">指标影响</th>
              <th className="py-3 pr-3">优先级</th>
              <th className="py-3">优化动作</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.position} className="border-b border-gray-50 last:border-0">
                <td className="py-3 pr-3 font-semibold text-gray-900">{row.position}</td>
                <td className="py-3 pr-3 text-gray-600">{row.judgement}</td>
                <td className="py-3 pr-3">
                  <Badge variant="outline" className={impactClass[row.impact]}>{row.impact}</Badge>
                </td>
                <td className="py-3 pr-3">
                  <Badge className={priorityClass[row.priority]}>{row.priority}</Badge>
                </td>
                <td className="py-3 text-gray-700">{row.action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function ModuleDiagnosisCards({ result, listing }: { result: DiagnosisResult; listing: ListingInput }) {
  const bullets = splitBullets(listing.bullet_points);
  const coveredKeywords = Object.values(result.keyword_coverage?.covered_categories || {}).flat().slice(0, 8);
  const missingKeywords = Object.values(result.keyword_coverage?.missing_categories || {}).flat().slice(0, 8);
  const adKeywords = [
    ...(result.ad_keywords?.high_conversion || []),
    ...(result.ad_keywords?.long_tail || []),
    ...(result.ad_keywords?.traffic || []),
  ].map((item) => normalizeAmazonAdKeyword(item.keyword)).filter(Boolean).slice(0, 8);

  const modules = [
    {
      title: "标题优化",
      icon: <FileText className="w-4 h-4 text-brand-600" />,
      current: formatAnalysisText(result.analysis?.product_identity || result.analysis?.function_expression) || "检查核心关键词是否前置、品牌词是否合理、卖点表达是否清晰。",
      suggestion: formatAnalysisText(result.suggestions?.title_rewrite) || "按品牌 + 核心关键词 + 关键属性 + 规格/数量 + 适用场景重写，避免堆砌关键词。",
      example: formatAnalysisText(result.suggestions?.title_rewrite) || listing.title || "等待生成优化后标题示例。",
    },
    {
      title: "主图点击优化",
      icon: <Image className="w-4 h-4 text-emerald-600" />,
      current: formatAnalysisText(result.analysis?.product_identity) || "检查产品主体、白底合规、占比、核心功能表达和竞品差异。",
      suggestion: "主图只负责点击：真实商品、主体清晰、无干扰文字，核心差异用视觉而不是大段文案表达。",
      example: "改版方向：提高产品占比，突出核心形态或关键差异，避免道具、边框、水印和夸张场景。",
    },
    {
      title: "副图证据补强",
      icon: <Image className="w-4 h-4 text-teal-600" />,
      current: formatAnalysisText(result.analysis?.scenario_expression) || "检查副图是否覆盖核心场景、功能解释、对比图、尺寸图、使用步骤和信任证明。",
      suggestion: "建议顺序：核心卖点图 → 场景图 → 尺寸/结构图 → 对比图 → 风险消除/信任图 → 使用步骤图。",
      example: "缺失类型优先补：场景图、尺寸图、对比图、信任证明图。",
    },
    {
      title: "五点顾虑消除",
      icon: <List className="w-4 h-4 text-amber-600" />,
      current: formatAnalysisText(result.analysis?.function_expression) || `当前识别 ${bullets.length} 条五点，重点检查是否按痛点、功能、场景、信任和差异化排序。`,
      suggestion: formatAnalysisText(result.suggestions?.bullet_points_optimization?.[0]) || "每条五点只讲一个购买理由，前两条解决最大犹豫点，后面补场景、信任和风险消除。",
      example: formatAnalysisText(result.suggestions?.bullet_points_optimization?.slice(0, 3)) || "等待生成优化后五点示例。",
    },
    {
      title: "A+信任补强",
      icon: <Star className="w-4 h-4 text-gold-600" />,
      current: formatAnalysisText(result.analysis?.psychology_benefit) || "检查A+是否讲清品牌信任、场景图、对比图、差异化和主图/五点承接。",
      suggestion: formatAnalysisText(result.suggestions?.a_plus_suggestions) || "A+按品牌信任、技术/材质解释、场景教育、对比证明、售后风险消除组织。",
      example: "建议模块：品牌信任 → 核心差异 → 使用场景 → 对比证据 → FAQ/售后承诺。",
    },
    {
      title: "关键词意图补充",
      icon: <Search className="w-4 h-4 text-teal-600" />,
      current: result.keyword_coverage?.coverage_summary || "检查标题、五点、A+和Search Terms是否表达一致，是否覆盖用户真实购买意图。",
      suggestion: missingKeywords.length ? `建议补充：${missingKeywords.join(", ")}` : "继续保持核心词覆盖，并优先测试关系词和状态触发词。",
      example: `已覆盖：${coveredKeywords.join(", ") || "待识别"}；广告验证词：${adKeywords.join(", ") || "待生成"}`,
    },
    {
      title: "价格信任判断",
      icon: <Shield className="w-4 h-4 text-red-600" />,
      current: formatAnalysisText(result.analysis?.risk_elimination) || "检查价格是否被评分、评论、保修、认证、安全和售后信息支撑。",
      suggestion: "不要先盲目降价。先补强信任证明和承诺证据，再用广告验证价格与转化的关系。",
      example: "优先补充：保修、安全、材质、认证、兼容性、真实使用反馈。",
    },
  ];

  return (
    <Card className="bg-white border-gray-200">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-brand-600" />
          模块优化动作
        </CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {modules.map((module) => (
          <div key={module.title} className="rounded-xl border border-gray-100 bg-gray-50 p-4">
            <h4 className="font-semibold text-gray-900 flex items-center gap-2">
              {module.icon}
              {module.title}
            </h4>
            <div className="mt-3 space-y-3 text-sm">
              <div>
                <p className="text-[11px] text-gray-500 mb-1">当前问题</p>
                <p className="text-gray-700 leading-relaxed">{module.current}</p>
              </div>
              <div>
                <p className="text-[11px] text-gray-500 mb-1">执行动作</p>
                <p className="text-gray-700 leading-relaxed">{module.suggestion}</p>
              </div>
              <div className="rounded-lg bg-white border border-gray-100 p-3">
                <p className="text-[11px] text-gray-500 mb-1">示例 / 下一步</p>
                <p className="text-gray-700 leading-relaxed">{module.example}</p>
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  History Detail View                                                 */
/* ------------------------------------------------------------------ */

function HistoryDetailView({
  result,
  resultTab,
  setResultTab,
  expandedEl,
  setExpandedEl,
}: {
  result: DiagnosisResult;
  resultTab: string;
  setResultTab: (t: string) => void;
  expandedEl: string | null;
  setExpandedEl: (e: string | null) => void;
}) {
  const radarScores = DIMENSIONS.map((d) => ({
    label: d.label,
    value: result.scores[d.key] || 0,
    color: d.stroke,
  }));

  const elementsData: ElementData[] = ELEMENT_META.map((em) => {
    const ed = result.elements?.[em.key] || {};
    return {
      key: em.key,
      label: em.label,
      icon: em.icon,
      dims: normalizeElementDims(ed as Record<string, unknown>),
      summary: (ed as Record<string, unknown>).summary as string || "",
    };
  });

  const avg = getAvgScore(result.scores);
  const g = avg >= 80 ? "A" : avg >= 60 ? "B" : avg >= 40 ? "C" : "D";
  const historyListing: ListingInput = {
    title: result.listing_title || result.analyzed_product_name || "",
    bullet_points: "",
    description: "",
    a_plus_content: "",
    backend_keywords: "",
    main_image_description: "",
    category: "",
    price: "",
    brand: "",
    marketplace: result.marketplace || "US",
  };

  return (
    <div className="space-y-4 p-4 rounded-xl bg-gray-50 border border-gray-200">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="relative w-14 h-14">
          <svg className="w-14 h-14 -rotate-90" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="10" />
            <circle cx="60" cy="60" r="50" fill="none" stroke={getGradeColor(g)} strokeWidth="10" strokeDasharray={`${(avg / 100) * 314} 314`} strokeLinecap="round" />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-sm font-bold">{avg}</span>
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-900 truncate">{result.listing_title || result.analyzed_product_name || "—"}</p>
          <p className="text-xs text-gray-500">{result.marketplace || ""} · 等级 {g}</p>
        </div>
      </div>

      {/* Sub-tabs */}
      <Tabs value={resultTab} onValueChange={setResultTab}>
        <TabsList className="bg-gray-50 border border-gray-200 flex-wrap">
          <TabsTrigger value="overview" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600 text-xs">决策结论</TabsTrigger>
          <TabsTrigger value="scores" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600 text-xs">承接评分</TabsTrigger>
          <TabsTrigger value="heatmap" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600 text-xs">问题归因</TabsTrigger>
          <TabsTrigger value="keywords" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600 text-xs">补哪些词</TabsTrigger>
          <TabsTrigger value="suggestions" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600 text-xs">优化动作</TabsTrigger>
          <TabsTrigger value="hypotheses" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600 text-xs">验证假设</TabsTrigger>
          <TabsTrigger value="adkeywords" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600 text-xs">验证词组</TabsTrigger>
        </TabsList>

        {/* Overview */}
        <TabsContent value="overview" className="mt-3 space-y-4">
          <BackendJudgmentPanel result={result} />
          <PrecisionConfidencePanel integrity={result.data_integrity} />
        </TabsContent>

        {/* Scores */}
        <TabsContent value="scores" className="mt-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
            {radarScores.length > 0 && (
              <div className="flex items-center justify-center">
                <RadarChart scores={radarScores} size={200} />
              </div>
            )}
            <div className="space-y-2">
              {DIMENSIONS.map((dim) => {
                const s = result.scores[dim.key] || 0;
                return (
                  <div key={dim.key} className="flex items-center gap-2">
                    <span className={`${dim.color} w-16 text-xs`}>{dim.label}</span>
                    <div className="flex-1 h-1.5 bg-gray-50 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${scoreBgColor(s)}`} style={{ width: `${s}%` }} />
                    </div>
                    <span className={`text-xs font-bold w-8 text-right ${scoreColor(s)}`}>{s}</span>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="mb-3">
            <TwoRulerSummary scores={result.scores} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {DIMENSIONS.map((dim) => (
              <ScoreBar key={dim.key} dim={dim} score={result.scores[dim.key] || 0} analysis={result.analysis?.[dim.key]} />
            ))}
          </div>
        </TabsContent>

        {/* Heatmap */}
        <TabsContent value="heatmap" className="mt-3">
          <div className="mb-3">
            <PriorityIssueTable rows={buildPriorityIssues(result)} />
          </div>
          {elementsData.some((e) => Object.values(e.dims).some((v) => v > 0)) ? (
            <div>
              <div className="mb-3 rounded-lg border border-brand-100 bg-brand-50 p-3">
                <p className="text-xs font-semibold text-brand-700">读图方式</p>
                <p className="mt-1 text-xs text-gray-500 leading-relaxed">
                  行分看单个Listing模块的贡献；最终维度分看系统汇总后的承接判断。验证参考来自价格、评论、BSR和广告数据，低分不等于标题或五点一定差。
                </p>
              </div>
              <div className="overflow-x-auto">
              <table className="w-full min-w-[500px]">
                <thead>
                  <tr>
                    <th className="text-left text-xs text-gray-500 pb-2 pr-3 w-20">要素</th>
                    {HEATMAP_DIM_KEYS.map((m) => (
                      <th key={m.key} className={`text-center text-[10px] pb-2 px-1 ${m.color}`}>{m.label}</th>
                    ))}
                    <th className="text-center text-xs text-gray-500 pb-2 px-1">均</th>
                  </tr>
                </thead>
                <tbody>
                  {elementsData.map((el) => {
                    const vals = HEATMAP_DIM_KEYS.map((d) => el.dims[d.key]).filter(v => typeof v === "number" && !isNaN(v));
                    const elAvg = vals.length > 0 ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : 0;
                    return (
                      <tr key={el.key}>
                        <td className="py-1 pr-3">
                          <button className="flex items-center gap-1 text-xs text-gray-600 hover:text-gray-900" onClick={() => setExpandedEl(expandedEl === el.key ? null : el.key)}>
                            {el.icon} {el.label}
                          </button>
                        </td>
                        {HEATMAP_DIM_KEYS.map((d) => (
                          <td key={d.key} className="px-1 py-1"><HeatmapCell value={el.dims[d.key]} /></td>
                        ))}
                        <td className="px-1 py-1"><HeatmapCell value={elAvg} /></td>
                      </tr>
                    );
                  })}
                  <tr className="border-t border-gray-200">
                    <td className="py-2 pr-3">
                      <span className="text-xs font-semibold text-gray-700">最终维度分</span>
                    </td>
                    {HEATMAP_DIM_KEYS.map((d) => (
                      <td key={d.key} className="px-1 py-2">
                        <HeatmapCell value={Number(result.scores[d.key as keyof Scores]) || 0} />
                      </td>
                    ))}
                    <td className="px-1 py-2">
                      <HeatmapCell value={getAvgScore(result.scores)} />
                    </td>
                  </tr>
                </tbody>
              </table>
              </div>
              {expandedEl && elementsData.find((e) => e.key === expandedEl) && (
                <p className="mt-2 text-xs text-gray-500 p-2 bg-gray-50 rounded border border-gray-100">
                  {elementsData.find((e) => e.key === expandedEl)!.summary}
                </p>
              )}
            </div>
          ) : (
            <p className="text-xs text-gray-500 text-center py-6">暂无热力图数据</p>
          )}
        </TabsContent>

        {/* Keywords */}
        <TabsContent value="keywords" className="mt-3 space-y-3">
          {result.keyword_coverage?.coverage_score !== undefined && (
            <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-gray-100">
              <span className="text-xs text-gray-500 flex items-center gap-1.5"><Search className="w-3.5 h-3.5 text-brand-600" /> 关键词覆盖率</span>
              <span className={`text-lg font-bold ${scoreColor(result.keyword_coverage.coverage_score || 0)}`}>{result.keyword_coverage.coverage_score}%</span>
            </div>
          )}
          {result.keyword_coverage?.coverage_summary && (
            <p className="text-xs text-gray-500">{result.keyword_coverage.coverage_summary}</p>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {result.keyword_coverage?.covered_categories && (
              <div className="space-y-2">
                <p className="text-xs text-emerald-600 font-medium flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> 已覆盖</p>
                {Object.entries(result.keyword_coverage.covered_categories).map(([cat, words]) => (
                  words && words.length > 0 && (
                    <div key={cat}>
                      <span className="text-[10px] text-gray-600">{KW_CATEGORY_LABELS[cat] || cat}</span>
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {words.map((w, i) => <Badge key={i} variant="secondary" className="text-[9px] bg-emerald-50 text-emerald-600 border-emerald-500/20">{w}</Badge>)}
                      </div>
                    </div>
                  )
                ))}
              </div>
            )}
            {result.keyword_coverage?.missing_categories && (
              <div className="space-y-2">
                <p className="text-xs text-red-600 font-medium flex items-center gap-1"><XCircle className="w-3.5 h-3.5" /> 缺失</p>
                {Object.entries(result.keyword_coverage.missing_categories).map(([cat, words]) => (
                  words && words.length > 0 && (
                    <div key={cat}>
                      <span className="text-[10px] text-gray-600">{KW_CATEGORY_LABELS[cat] || cat}</span>
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {words.map((w, i) => <Badge key={i} variant="secondary" className="text-[9px] bg-red-50 text-red-600 border-red-500/20">{w}</Badge>)}
                      </div>
                    </div>
                  )
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        {/* Suggestions */}
        <TabsContent value="suggestions" className="mt-3 space-y-3">
          {result.suggestions?.title_rewrite && (
            <div className="p-3 rounded-lg bg-gray-50 border border-gray-100">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-500">标题直接这样改</span>
                <CopyBtn text={result.suggestions.title_rewrite} />
              </div>
              <p className="text-xs text-emerald-600 font-medium">{result.suggestions.title_rewrite}</p>
            </div>
          )}
          {result.suggestions?.bullet_points_optimization && result.suggestions.bullet_points_optimization.length > 0 && (
            <div className="p-3 rounded-lg bg-gray-50 border border-gray-100">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-500">五点按这个顺序改</span>
                <CopyBtn text={result.suggestions.bullet_points_optimization.join("\n")} />
              </div>
              {result.suggestions.bullet_points_optimization.map((bp, i) => (
                <p key={i} className="text-xs text-gray-600 mb-1"><span className="text-brand-600 font-bold">{i + 1}.</span> {bp}</p>
              ))}
            </div>
          )}
          {result.suggestions?.backend_keywords_addition && result.suggestions.backend_keywords_addition.length > 0 && (
            <div className="p-3 rounded-lg bg-gray-50 border border-gray-100">
              <span className="text-xs text-gray-500 block mb-2">Search Terms补这些词</span>
              <div className="flex flex-wrap gap-1">
                {result.suggestions.backend_keywords_addition.map((kw, i) => (
                  <Badge key={i} variant="outline" className="text-[10px] text-brand-600 border-brand-200">{kw}</Badge>
                ))}
              </div>
            </div>
          )}
          {result.suggestions?.a_plus_suggestions && (
            <div className="p-3 rounded-lg bg-gray-50 border border-gray-100">
              <span className="text-xs text-gray-500 block mb-1">A+先补这些证据</span>
              <p className="text-xs text-gray-600">{result.suggestions.a_plus_suggestions}</p>
            </div>
          )}
        </TabsContent>

        <TabsContent value="hypotheses" className="mt-3">
          <ListingHypothesisLoopPanel result={result} listing={historyListing} />
        </TabsContent>

        {/* Ad Keywords */}
        <TabsContent value="adkeywords" className="mt-3 space-y-3">
          {result.ad_keywords?.ad_summary && (
            <p className="text-xs text-gray-500 p-3 rounded-lg bg-gray-50 border border-gray-100">{result.ad_keywords.ad_summary}</p>
          )}
          {sanitizeAdKeywordList(result.ad_keywords?.high_conversion, result.listing_title || result.analyzed_product_name || "", "high_conversion").length > 0 && (
            <div>
              <p className="text-xs text-emerald-600 font-medium mb-1">🎯 高转化</p>
              <div className="flex flex-wrap gap-1">
                {sanitizeAdKeywordList(result.ad_keywords?.high_conversion, result.listing_title || result.analyzed_product_name || "", "high_conversion").map((kw, i) => (
                  <Badge key={i} variant="secondary" className="text-[10px] bg-emerald-50 text-emerald-600 border-emerald-500/20">
                    {kw.keyword} <span className="text-gray-500 ml-1">{kw.match_type}</span>
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {sanitizeAdKeywordList(result.ad_keywords?.traffic, result.listing_title || result.analyzed_product_name || "", "traffic").length > 0 && (
            <div>
              <p className="text-xs text-teal-600 font-medium mb-1">📈 流量词</p>
              <div className="flex flex-wrap gap-1">
                {sanitizeAdKeywordList(result.ad_keywords?.traffic, result.listing_title || result.analyzed_product_name || "", "traffic").map((kw, i) => (
                  <Badge key={i} variant="secondary" className="text-[10px] bg-teal-50 text-teal-600 border-teal-500/20">
                    {kw.keyword} <span className="text-gray-500 ml-1">{kw.match_type}</span>
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {sanitizeAdKeywordList(result.ad_keywords?.long_tail, result.listing_title || result.analyzed_product_name || "", "long_tail").length > 0 && (
            <div>
              <p className="text-xs text-gold-600 font-medium mb-1">🔍 长尾词</p>
              <div className="flex flex-wrap gap-1">
                {sanitizeAdKeywordList(result.ad_keywords?.long_tail, result.listing_title || result.analyzed_product_name || "", "long_tail").map((kw, i) => (
                  <Badge key={i} variant="secondary" className="text-[10px] bg-gold-50 text-gold-600 border-gold-500/20">
                    {kw.keyword} <span className="text-gray-500 ml-1">{kw.match_type}</span>
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {result.ad_keywords?.negative && result.ad_keywords.negative.length > 0 && (
            <div>
              <p className="text-xs text-red-600 font-medium mb-1">🚫 否定词</p>
              <div className="flex flex-wrap gap-1">
                {result.ad_keywords.negative.map((kw, i) => (
                  <Badge key={i} variant="outline" className="text-[10px] text-red-600 border-red-200">{kw}</Badge>
                ))}
              </div>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Ad Keyword Section                                                 */
/* ------------------------------------------------------------------ */

function AdKeywordSection({
  title,
  subtitle,
  keywords,
  accentColor,
}: {
  title: string;
  subtitle: string;
  keywords?: AdKeyword[];
  accentColor: string;
}) {
  if (!keywords || keywords.length === 0) return null;

  const borderClass = `border-${accentColor}-500/20`;

  return (
    <Card className={`bg-gray-50 ${borderClass}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">
          {title}
          <span className="text-[10px] text-gray-500 ml-2 font-normal">{subtitle}</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {keywords.map((kw, i) => (
            <div key={i} className="flex items-start justify-between gap-2 bg-gray-50 rounded-lg p-2.5 hover:bg-gray-100 transition-colors">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm text-gray-900 font-medium">{kw.keyword}</span>
                  <Badge variant="outline" className="text-[9px] border-gray-200 text-gray-500">
                    {kw.match_type}
                  </Badge>
                  {kw.priority && (
                    <Badge variant="outline" className={`text-[9px] ${PRIORITY_COLORS[kw.priority] || ""}`}>
                      {kw.priority}
                    </Badge>
                  )}
                  {kw.keyword_type && (
                    <Badge variant="outline" className={`text-[9px] ${KEYWORD_TYPE_BADGES[kw.keyword_type] || "bg-gray-100 text-gray-600 border-gray-200"}`}>
                      {KEYWORD_TYPE_LABELS[kw.keyword_type] || kw.keyword_type}
                    </Badge>
                  )}
                  {kw.competition && (
                    <span className={`text-[9px] ${COMPETITION_COLORS[kw.competition] || "text-gray-500"}`}>
                      竞争:{kw.competition}
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-1">{kw.intent}</p>
              </div>
              <CopyBtn text={kw.keyword} />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
