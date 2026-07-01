import { useEffect, useState, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { AppSidebar } from "@/components/AppSidebar";
import { MarketplaceSelect, MARKETPLACE_BY_VALUE } from "@/components/MarketplaceSelect";
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
import { IMPACT_METRIC_LABELS, label } from "@/lib/label-maps";
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
  FileText,
  Image as ImageIcon,
  MessageSquare,
  TrendingUp,
  Video,
} from "lucide-react";
import {
  FiveDimensionScoreCard,
  RadarChart,
  type FiveDScoreResult,
} from "@/components/FiveDimensionScore";
import { getActionSnapshots, saveActionSnapshot, type ActionSnapshot } from "@/lib/workflow-api";
import {
  finishModuleTask,
  removeModuleTask,
  upsertModuleTask,
} from "@/lib/module-task-store";

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
  if (source === "server_proxy_fetch") return "服务器代理兜底抓取";
  if (source === "local_browser_capture") return "本地浏览器页面采集";
  if (source === "ai_estimated_low_confidence" || source === "低置信度补充分析") return "低置信度补充分析";
  if (source?.includes("scrape") || source === "scraped") return "服务器真实抓取";
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
  v5_market_decision?: {
    success_probability?: number;
    demand_strength?: number;
    competition_pressure?: number;
    validation_cost?: string;
    max_risk?: string;
    opportunity_level?: string;
    next_step?: string;
  };
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
  market_evolution_matrix?: {
    horizontal_evolution_index?: number | null;
    meaning_evolution_index?: number | null;
    technology_evolution_index?: number | null;
    current_position?: string;
    recommendation?: string;
  };
  solution_evolution?: {
    generations?: string[];
    solved_problems?: string[];
    unsolved_problems?: string[];
    current_opportunity?: string;
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
    rankSource === "external_amazon_top40_search" ||
    rankSnapshots.some((row) => {
      const rankType = String(row?.rank_type || "");
      return rankType.startsWith("external_amazon_top40");
    });

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

interface AsinDiagnosisTaskResponse {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed" | string;
  result_payload?: Record<string, unknown>;
  error_message?: string;
}

const ASIN_DIAGNOSIS_TASK_KEY = "alignx_active_asin_diagnosis_task_id";
const ASIN_DIAGNOSIS_TASK_CONTEXT_KEY = "alignx_active_asin_diagnosis_task_context";
const KEYWORD_RESEARCH_TASK_CONTEXT_KEY = "alignx_active_keyword_research_task_context";

interface KeywordResearchTaskContext {
  taskId: string;
  keyword: string;
  marketplace: string;
  moduleTaskId: string;
}

const loadKeywordResearchTaskContext = (): KeywordResearchTaskContext | null => {
  try {
    const raw = localStorage.getItem(KEYWORD_RESEARCH_TASK_CONTEXT_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data?.taskId || !data?.keyword) return null;
    return data;
  } catch {
    localStorage.removeItem(KEYWORD_RESEARCH_TASK_CONTEXT_KEY);
    return null;
  }
};

const saveKeywordResearchTaskContext = (context: KeywordResearchTaskContext) => {
  localStorage.setItem(KEYWORD_RESEARCH_TASK_CONTEXT_KEY, JSON.stringify(context));
};

const clearKeywordResearchTaskContext = () => {
  localStorage.removeItem(KEYWORD_RESEARCH_TASK_CONTEXT_KEY);
};

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

interface CompetitorListingModule {
  key: string;
  name: string;
  summary?: string;
  structure_breakdown?: string[];
  strengths?: string[];
  weaknesses?: string[];
  covered_user_intents?: string[];
  keywords?: string[];
  borrowable_actions?: string[];
  do_not_copy?: string[];
  raw_content?: unknown;
}

interface CompetitorListingReport {
  asin: string;
  marketplace: string;
  product_title: string;
  product_data?: Record<string, any>;
  scores?: Record<string, number>;
  analysis_report?: {
    scores?: Record<string, number>;
    analysis?: Record<string, unknown>;
    overall_summary?: string;
    improvement_suggestions?: string[];
    listing_breakdown?: {
      modules?: CompetitorListingModule[];
      rating_histogram?: Record<string, string>;
      low_star_reviews?: Array<Record<string, unknown>>;
    };
    toolbox_enhancements?: {
      competitor?: Record<string, any>;
      listing?: Record<string, any>;
      ppc?: Record<string, any>;
      review?: Record<string, any>;
    };
    amazon_compliance?: Record<string, any>;
  };
  data_source?: string;
  id?: number;
  selection_judgment?: Record<string, any>;
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

const asinModuleTaskId = (taskId: string) => `asin-diagnosis:${taskId}`;

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

const formatIndexValue = (value?: number | null) =>
  typeof value === "number" && Number.isFinite(value) ? String(Math.round(value)) : "待录入";

const formatListValue = (items?: string[]) =>
  Array.isArray(items) && items.filter(Boolean).length ? items.filter(Boolean).join(" / ") : "暂无";

const normalizeTextList = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value
      .flatMap((item) => normalizeTextList(item))
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (value && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    return [obj.keyword, obj.title, obj.body, obj.text, obj.summary]
      .map((item) => String(item || "").trim())
      .filter(Boolean);
  }
  const text = String(value || "").trim();
  return text ? [text] : [];
};

const keywordStopwords = new Set([
  "the",
  "and",
  "with",
  "for",
  "from",
  "this",
  "that",
  "your",
  "you",
  "are",
  "was",
  "were",
  "have",
  "has",
  "had",
  "but",
  "not",
  "very",
  "just",
  "they",
  "them",
  "its",
  "it's",
  "product",
  "item",
  "amazon",
]);

const extractKeywordPhrases = (texts: unknown, limit = 8): string[] => {
  const chunks = normalizeTextList(texts);
  const counts = new Map<string, number>();
  for (const chunk of chunks) {
    const chinese = chunk.match(/[\u4e00-\u9fff]{2,8}/g) || [];
    for (const token of chinese) counts.set(token, (counts.get(token) || 0) + 1);
    const words = chunk
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, " ")
      .split(/\s+/)
      .filter((word) => word.length >= 4 && !keywordStopwords.has(word));
    for (const word of words) counts.set(word, (counts.get(word) || 0) + 1);
    for (let index = 0; index < words.length - 1; index += 1) {
      const phrase = `${words[index]} ${words[index + 1]}`;
      counts.set(phrase, (counts.get(phrase) || 0) + 1);
    }
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1] || b[0].length - a[0].length)
    .map(([keyword]) => keyword)
    .slice(0, limit);
};

const competitorScoreAverage = (scores?: Record<string, number>) => {
  const keys = [
    "functionality",
    "scenario",
    "differentiation",
    "product_identity",
    "compatibility",
    "subjective_properties",
    "risk_elimination",
  ];
  const values = keys.map((key) => Number(scores?.[key] || 0)).filter((value) => value > 0);
  if (!values.length) return 0;
  return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);
};

const getRankSourceJudgment = (report?: KeywordSalesValidationReport | null) => {
  const rows = report?.rank_snapshots || [];
  const organic = rows.filter((row) => Number(row.organic_position || 0) > 0 || row.is_organic).length;
  const sponsored = rows.filter((row) => Number(row.sponsored_position || 0) > 0 || row.is_sponsored).length;
  if (organic === 0 && sponsored === 0) return { label: "暂无", organic, sponsored };
  if (organic >= sponsored) return { label: "自然排名为主", organic, sponsored };
  return { label: "广告排名为主", organic, sponsored };
};

const formatCompetitorPrice = (productData?: Record<string, any>, fallbackPrice?: number) => {
  const raw = String(productData?.price || "").trim();
  if (raw && /[$€£¥₹]/.test(raw)) return raw;
  const value = raw || (fallbackPrice && fallbackPrice > 0 ? String(fallbackPrice) : "");
  if (!value) return "暂无";
  const currency = String(productData?.price_currency || "USD").toUpperCase();
  const symbol: Record<string, string> = { USD: "$", CAD: "$", AUD: "$", GBP: "£", EUR: "€", JPY: "¥", INR: "₹", MXN: "$" };
  return `${symbol[currency] || ""}${value}`;
};

const formatCompetitorRevenue = (value: unknown, productData?: Record<string, any>) => {
  const raw = String(value || "").trim();
  if (!raw) return "暂无";
  if (/[$€£¥₹]/.test(raw)) return raw;
  const currency = String(productData?.price_currency || "USD").toUpperCase();
  const symbol: Record<string, string> = { USD: "$", CAD: "$", AUD: "$", GBP: "£", EUR: "€", JPY: "¥", INR: "₹", MXN: "$" };
  return `${symbol[currency] || ""}${raw}`;
};

const formatCompetitorValue = (value: unknown) => {
  const text = String(value ?? "").trim();
  return text || "暂无";
};

const formatCompetitorBoolean = (value: unknown, count?: unknown) => {
  const hasValue = value === true || String(value || "").toLowerCase() === "true";
  if (!hasValue) return "无";
  const countText = String(count || "").trim();
  return countText ? `有（${countText}张图）` : "有";
};

const formatCompetitorRawContent = (raw: unknown): string => {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.images) || obj.text) {
      const images = Array.isArray(obj.images) ? obj.images : [];
      return [`A+ Images: ${images.length}`, String(obj.text || "")].filter(Boolean).join("\n\n");
    }
    return JSON.stringify(raw, null, 2);
  }
  if (Array.isArray(raw)) {
    return raw.map((item, index) => `${index + 1}. ${typeof item === "string" ? item : JSON.stringify(item)}`).join("\n");
  }
  return String(raw || "暂无");
};

const normalizeCompetitorKeyword = (keyword: string) => {
  let text = String(keyword || "").trim().toLowerCase();
  if (!text || /[\u4e00-\u9fff]/.test(text)) return "";
  const replacements: Record<string, string> = {
    odour: "odor",
    colour: "color",
    flavour: "flavor",
    favourite: "favorite",
    organiser: "organizer",
    travelling: "traveling",
    jewellery: "jewelry",
  };
  Object.entries(replacements).forEach(([from, to]) => {
    text = text.replace(new RegExp(`\\b${from}\\b`, "g"), to);
  });
  const normalized = text.replace(/[^a-z0-9 +&/-]/g, " ").replace(/\s+/g, " ").trim().split(" ").slice(0, 8).join(" ");
  return /[a-z]/.test(normalized) ? normalized : "";
};

const cleanCompetitorKeywordList = (values?: string[], fallback: string[] = []) => {
  const seen = new Set<string>();
  const clean = [...(values || []), ...fallback]
    .map(normalizeCompetitorKeyword)
    .filter((keyword) => keyword && !seen.has(keyword) && seen.add(keyword));
  return clean.slice(0, 6);
};

const sameCompetitorStringList = (a?: string[], b?: string[]) => {
  if (!a?.length || !b?.length || a.length !== b.length) return false;
  return a.every((item, index) => item === b[index]);
};

const competitorModuleDefaultIntents = (key: string): string[] => {
  const map: Record<string, string[]> = {
    title: ["识别产品身份", "确认核心品类", "理解关键属性", "判断适用对象/场景"],
    bullets: ["确认功能效果", "降低购买犹豫", "理解使用场景", "建立信任", "消除售后/风险顾虑"],
    main_image: ["快速识别产品类型", "判断点击吸引力", "降低点击前理解成本"],
    secondary_images: ["理解核心卖点", "想象使用场景", "确认尺寸/材质", "消除购买风险"],
    a_plus: ["建立品牌信任", "理解技术/材质原理", "确认差异化证据", "降低决策风险"],
    video_brand: ["验证使用方法", "看到效果证明", "建立品牌信任"],
    review_validation: ["识别质量风险", "发现使用阻碍", "确认售后疑虑", "提炼真实痛点"],
  };
  return map[key] || ["理解用户需求", "确认购买理由", "降低决策风险"];
};

const competitorModuleStructureNarrative = (key: string, items?: string[]): string[] => {
  const map: Record<string, string[]> = {
    title: ["标题按“品类词/属性词/场景词/状态词”的顺序影响广告匹配质量、曝光相关性和首轮CTR。"],
    bullets: ["五点负责广告点击后的转化承接：功能说明、效果证明、场景承接、信任背书和售后/风险消除会影响CVR与ACOS。"],
    main_image: ["主图负责点击和CPC效率：用户扫一眼是否知道产品差异，决定CTR、点击质量和流量成本。"],
    secondary_images: ["副图承接广告点击后的疑问：功能证明、场景、尺寸、对比、安全、使用步骤会影响CVR和跳出风险。"],
    a_plus: ["A+负责深层信任和品牌溢价：品牌故事、技术/材质原理、差异化证明和对比表影响CVR、ACOS和客单信任。"],
    video_brand: ["视频让用户看到功能如何发生，主要影响详情页停留、CVR和复杂产品的理解成本。"],
    review_validation: ["评论验证广告承诺是否可信：好评支撑卖点，差评暴露痛点，直接影响CVR、ACOS和退货/差评风险。"],
  };
  return map[key] || (items?.length ? [items.join(" → ")] : []);
};

const competitorModuleAdMetricMap = (key: string) => {
  const map: Record<string, {
    metrics: string[];
    funnelRole: string;
    strengthMeaning: string;
    weaknessMeaning: string;
    attackAngle: string;
  }> = {
    title: {
      metrics: ["曝光相关性", "搜索词匹配质量", "CTR", "CPC"],
      funnelRole: "负责把广告带进正确搜索语义池，决定流量准不准。",
      strengthMeaning: "标题词序清晰、关系词/状态词明确时，广告更容易拿到高意图流量。",
      weaknessMeaning: "标题只堆属性词时，容易获得泛曝光，点击和转化都会被稀释。",
      attackAngle: "我方用更具体的场景词、状态触发词和长尾词避开正面价格竞争。",
    },
    main_image: {
      metrics: ["CTR", "CPC", "点击质量"],
      funnelRole: "负责用户第一眼是否愿意点，影响点击率和单次点击成本。",
      strengthMeaning: "主图一眼说明差异时，CTR更容易占优。",
      weaknessMeaning: "主图只展示产品、不展示差异时，广告点击优势弱。",
      attackAngle: "我方主图前置竞品没有讲清的核心差异或使用结果。",
    },
    secondary_images: {
      metrics: ["CVR", "跳出率", "ACOS"],
      funnelRole: "负责把点击后的疑问讲清楚，降低跳出和转化阻力。",
      strengthMeaning: "副图能证明功能、场景、尺寸和风险时，广告点击更容易转订单。",
      weaknessMeaning: "副图缺少证据链时，点击进来后会卡在信任和理解。",
      attackAngle: "我方副图按功能、场景、尺寸、对比、安全、使用步骤补齐证据。",
    },
    bullets: {
      metrics: ["CVR", "订单转化", "ACOS"],
      funnelRole: "负责成交理由，解释用户为什么现在买。",
      strengthMeaning: "五点每点对应一个购买理由时，广告点击后的转化承接更强。",
      weaknessMeaning: "五点堆参数或空泛承诺时，CTR可能有但CVR不稳。",
      attackAngle: "我方五点用痛点、机制、证据、场景、风险消除重写成交逻辑。",
    },
    a_plus: {
      metrics: ["CVR", "品牌信任", "ACOS", "客单承接"],
      funnelRole: "负责深层信任、品牌溢价和复杂决策解释。",
      strengthMeaning: "A+能建立品牌、技术、对比和信任闭环时，广告成本更容易被转化消化。",
      weaknessMeaning: "A+只是装饰图时，对广告转化帮助有限。",
      attackAngle: "我方A+打竞品没讲透的技术原理、对比证据和售后保障。",
    },
    video_brand: {
      metrics: ["CVR", "停留时长", "理解成本"],
      funnelRole: "负责动态证明产品怎么用、效果怎么发生。",
      strengthMeaning: "视频能降低复杂功能理解成本时，转化会更稳。",
      weaknessMeaning: "没有视频或视频只做氛围，会浪费动态证明机会。",
      attackAngle: "我方视频展示真实使用步骤和结果对比。",
    },
    review_validation: {
      metrics: ["CVR", "ACOS", "广告承诺可信度", "退货/差评风险"],
      funnelRole: "负责验证广告承诺是否被真实用户支持。",
      strengthMeaning: "好评支撑核心卖点时，广告承诺可信度高。",
      weaknessMeaning: "差评集中暴露同一痛点时，是竞品转化漏点。",
      attackAngle: "我方广告避开竞品差评雷区，并在图片/五点/A+明确回应。",
    },
  };
  return map[key] || {
    metrics: ["CTR", "CVR", "ACOS"],
    funnelRole: "负责影响广告点击后的理解和转化。",
    strengthMeaning: "强项可转化为我方可验证卖点。",
    weaknessMeaning: "弱项可转化为我方攻击切口。",
    attackAngle: "用广告小预算验证该切口是否成立。",
  };
};

const getCompetitorListingSummary = (
  report?: CompetitorListingReport | null,
  keywordReport?: KeywordSalesValidationReport | null
) => {
  const productData = report?.product_data || {};
  const selection = report?.selection_judgment || {};
  const breakdown = report?.analysis_report?.listing_breakdown;
  const modules = breakdown?.modules || [];
  const reviewModule = modules.find((module) => module.key === "review_validation");
  const lowReviews = (productData.low_star_reviews ||
    breakdown?.low_star_reviews ||
    []) as Array<Record<string, unknown>>;
  const reviewSamples = normalizeTextList(productData.review_samples || productData.reviews || []);
  const positiveSource = [
    productData.five_star_keywords,
    productData.positive_review_keywords,
    productData.positive_keywords,
    report?.analysis_report?.toolbox_enhancements?.review?.keyword_pool,
    reviewSamples,
  ];
  const complaintSource = [
    productData.complaint_keywords,
    productData.low_star_keywords,
    productData.negative_review_keywords,
    report?.analysis_report?.toolbox_enhancements?.review?.low_star_theme_candidates,
    reviewModule?.keywords,
    reviewModule?.weaknesses,
    lowReviews,
  ];
  const positiveKeywords = extractKeywordPhrases(positiveSource, 8);
  const complaintKeywords = extractKeywordPhrases(complaintSource, 8);
  const score = Number(selection.score || 0) || competitorScoreAverage(report?.scores);
  const weaknessCount = modules.reduce((sum, module) => sum + (module.weaknesses?.filter(Boolean).length || 0), 0);
  const rankSource = getRankSourceJudgment(keywordReport);
  const judgment =
    !report
      ? "待录入"
      : selection.next_step?.module
        ? String(selection.next_step.module)
      : score > 0 && (score < 62 || weaknessCount >= 8 || rankSource.label === "广告排名为主")
        ? "可打"
        : score > 0 && score < 76
          ? "可测试"
          : score > 0
            ? "暂缓"
            : "待补证据";
  const basis = [
    ...(Array.isArray(selection.decision_layer) ? selection.decision_layer.slice(0, 1) : []),
    score ? `承接评分 ${score}/100` : "",
    rankSource.label !== "暂无" ? rankSource.label : "",
    weaknessCount ? `弱项 ${weaknessCount}` : "",
    lowReviews.length ? `低分评论 ${lowReviews.length}` : "",
  ].filter(Boolean);
  return {
    score,
    judgment,
    basis: basis.length ? basis.join(" / ") : "暂无",
    rankSource,
    positiveKeywords,
    complaintKeywords,
    modules,
    lowReviews,
    selection,
  };
};

const sixDimensionEvidenceItems = (score?: FiveDScoreResult | null) => {
  if (!score) return [];
  const dimensionScoreLabels: Record<string, string> = {
    demand: "需求强度",
    search_entry: "搜索入口",
    competition: "竞争结构",
    differentiation: "差异化切口",
    business: "商业承受力",
    risk_trend: "风险与趋势",
  };
  if (Array.isArray(score.dimensions) && score.dimensions.length > 0) {
    return score.dimensions.map((dim) => {
      const evidence = dim.items
        ?.flatMap((item) => [
          ...(item.evidence || []),
          ...(item.deduction_reasons || []),
          item.suggestion,
        ])
        .filter(Boolean)
        .slice(0, 3)
        .join(" / ");
      return {
        title: dim.dimension_name || "暂无",
        detail: evidence || "暂无",
      };
    });
  }
  const analysisEntries = Object.entries(score.analysis || {});
  if (analysisEntries.length > 0) {
    return analysisEntries.map(([title, detail]) => {
      const scoreKey = Object.entries(dimensionScoreLabels).find(([, label]) => label === title)?.[0];
      const rawScore = scoreKey ? Number(score.dimension_scores?.[scoreKey] || 0) : 0;
      const detailObject = detail && typeof detail === "object" && !Array.isArray(detail) ? detail as Record<string, unknown> : null;
      return {
        title,
        score: rawScore,
        detail: detailObject ? String(detailObject.basis || "暂无") : String(detail || "暂无"),
        basis: detailObject ? String(detailObject.basis || "暂无") : "",
        opinion: detailObject ? String(detailObject.opinion || "暂无") : "",
      };
    });
  }
  return Object.entries(score.dimension_scores || {}).map(([key, value]) => ({
    title: dimensionScoreLabels[key] || key,
    score: Number(value || 0),
    detail: "暂无",
  }));
};

function CompetitorInfoItem({ label, value }: { label: string; value?: unknown }) {
  return (
    <div>
      <span className="text-muted-foreground">{label}：</span>
      <span className="text-brand-500">{formatCompetitorValue(value)}</span>
    </div>
  );
}

function CompetitorBreakdownSection({
  title,
  items,
  tone = "gray",
  badge = false,
}: {
  title: string;
  items?: string[];
  tone?: "gray" | "green" | "red" | "blue" | "amber";
  badge?: boolean;
}) {
  const seen = new Set<string>();
  const isKeywordSection = title.includes("关键词") || title.includes("语义词");
  const clean = (items || [])
    .map((item) => (isKeywordSection ? normalizeCompetitorKeyword(item) : String(item || "").trim()))
    .filter((item) => item && !seen.has(item) && seen.add(item));
  if (clean.length === 0) return null;
  const toneClass = {
    gray: "text-brand-500 bg-background border-border",
    green: "text-emerald-700 bg-emerald-50 border-emerald-100",
    red: "text-red-700 bg-red-50 border-red-100",
    blue: "text-brand-700 bg-brand-50 border-brand-100",
    amber: "text-amber-700 bg-gold-50 border-amber-100",
  }[tone];
  return (
    <div>
      <h4 className="text-xs font-semibold text-muted-foreground mb-2">{title}</h4>
      {badge ? (
        <div className="flex flex-wrap gap-1.5">
          {clean.map((item, index) => (
            <span key={`${item}-${index}`} className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${toneClass}`}>
              {item}
            </span>
          ))}
        </div>
      ) : (
        <div className="space-y-1.5">
          {clean.map((item, index) => (
            <div key={`${item}-${index}`} className={`rounded-lg border px-3 py-2 text-xs leading-relaxed ${toneClass}`}>
              {item}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CompetitorOriginalEvidencePreview({ raw, moduleName }: { raw: unknown; moduleName: string }) {
  const isImageUrl = (value: unknown): value is string => typeof value === "string" && value.startsWith("http");
  let textBlocks: string[] = [];
  let imageUrls: string[] = [];

  if (typeof raw === "string") {
    textBlocks = raw.trim() ? [raw.trim()] : [];
  } else if (Array.isArray(raw)) {
    imageUrls = raw.filter(isImageUrl);
    textBlocks = raw
      .filter((item) => !isImageUrl(item))
      .map((item, index) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const obj = item as Record<string, unknown>;
          return [obj.rating ? `${obj.rating} star` : "", obj.title, obj.body].filter(Boolean).join(" · ");
        }
        return String(item || "");
      })
      .filter(Boolean)
      .map((item, index) => `${index + 1}. ${item}`);
  } else if (raw && typeof raw === "object") {
    const obj = raw as Record<string, unknown>;
    const text = String(obj.text || "").trim();
    if (text) textBlocks.push(text);
    if (Array.isArray(obj.images)) {
      imageUrls = obj.images.filter(isImageUrl);
    }
  }

  const previewText = textBlocks.join("\n").slice(0, 900);
  const hasEvidence = previewText || imageUrls.length > 0;

  return (
    <div className={`rounded-lg border p-3 ${hasEvidence ? "bg-white border-border" : "bg-gold-50 border-amber-100"}`}>
      <div className="flex items-center justify-between gap-3 mb-2">
        <h4 className="text-xs font-semibold text-muted-foreground">原始内容 / 证据预览</h4>
        {imageUrls.length > 0 && <span className="text-[11px] text-brand-600">{imageUrls.length} 张图片证据</span>}
      </div>
      {imageUrls.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-2">
          {imageUrls.slice(0, 10).map((url, index) => (
            <img key={`${url}-${index}`} src={url} alt={`${moduleName} ${index + 1}`} className="h-16 w-16 rounded-md border border-border object-contain bg-white" />
          ))}
        </div>
      )}
      {previewText ? (
        <pre className="whitespace-pre-wrap text-xs leading-relaxed text-brand-500 max-h-40 overflow-auto">{previewText}</pre>
      ) : (
        <p className="text-xs leading-relaxed text-amber-700">暂无</p>
      )}
    </div>
  );
}

function CompetitorEvidencePanel({
  product,
  productData,
  title,
}: {
  product: Product;
  productData: Record<string, any>;
  title: string;
}) {
  const boughtCount = productData.bought_count || productData.amazon_bought_count;
  const bulletPoints = Array.isArray(productData.bullet_points) ? productData.bullet_points : [];
  const displayKeywords = cleanCompetitorKeywordList(
    Array.isArray(productData.main_keywords) ? productData.main_keywords : [],
    []
  );

  return (
    <div className="rounded-lg border border-border bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <FileText className="h-4 w-4 text-brand-600" />
        <p className="text-sm font-semibold text-foreground">竞品依据</p>
      </div>
      <div className="mb-3">
        <span className="text-sm text-muted-foreground">标题：</span>
        <span className="text-sm text-brand-500">{formatCompetitorValue(productData.title || title || product.title)}</span>
      </div>
      {boughtCount && (
        <div className="mb-3 flex items-center gap-3 rounded-lg border border-amber-500/25 bg-gold-50 px-3 py-2">
          <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-amber-100">
            <TrendingUp className="h-5 w-5 text-gold-600" />
          </div>
          <div>
            <div className="text-xs font-medium text-gold-600/80">Amazon官方购买人数</div>
            <div className="text-base font-bold text-gold-600">{boughtCount}</div>
          </div>
        </div>
      )}
      <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
        <CompetitorInfoItem label="品牌" value={productData.brand} />
        <CompetitorInfoItem label="类目" value={productData.category || product.category} />
        <CompetitorInfoItem label="价格" value={formatCompetitorPrice(productData, product.price)} />
        <CompetitorInfoItem label="评分" value={productData.rating ? `${productData.rating} 星` : product.rating ? `${product.rating} 星` : ""} />
        <CompetitorInfoItem label="评论数" value={productData.review_count || product.review_count} />
        <CompetitorInfoItem label="上架时间" value={productData.date_first_available || productData.launch_date} />
        <CompetitorInfoItem label="BSR排名" value={productData.bsr_rank ? `#${productData.bsr_rank}` : ""} />
        <CompetitorInfoItem label="卖家类型" value={productData.seller_type} />
        <CompetitorInfoItem
          label="BSR预估月销"
          value={productData.estimated_monthly_sales ? `${productData.estimated_monthly_sales}（仅供参考）` : ""}
        />
        <CompetitorInfoItem label="预估月收入" value={formatCompetitorRevenue(productData.estimated_monthly_revenue, productData)} />
        <CompetitorInfoItem label="主图数量" value={productData.image_count} />
        <CompetitorInfoItem label="视频" value={formatCompetitorBoolean(productData.has_video)} />
        <CompetitorInfoItem label="A+" value={formatCompetitorBoolean(productData.has_a_plus, productData.aplus_image_count)} />
      </div>
      {bulletPoints.length > 0 && (
        <details className="mt-3 rounded-lg border border-border bg-background px-3 py-2">
          <summary className="cursor-pointer text-sm font-medium text-brand-500">展开五点描述</summary>
          <ul className="mt-2 space-y-1 text-xs text-brand-500">
            {bulletPoints.map((item: string, index: number) => (
              <li key={`${item}-${index}`} className="flex gap-1">
                <span className="text-brand-600">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
      {displayKeywords.length > 0 && (
        <div className="mt-3">
          <span className="mb-1 block text-sm text-muted-foreground">优先验证关键词：</span>
          <div className="flex flex-wrap gap-1.5">
            {displayKeywords.map((keyword) => (
              <span key={keyword} className="inline-flex rounded-full border border-brand-100 bg-brand-50 px-2 py-0.5 text-xs text-brand-700">
                {keyword}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function CompetitorListingBreakdownPanel({ modules }: { modules: CompetitorListingModule[] }) {
  const iconMap: Record<string, typeof FileText> = {
    title: FileText,
    bullets: FileText,
    main_image: ImageIcon,
    secondary_images: ImageIcon,
    a_plus: ImageIcon,
    video_brand: Video,
    review_validation: MessageSquare,
  };

  if (!modules.length) {
    return (
      <div className="rounded-lg border border-border bg-white p-4">
        <div className="mb-3 flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-brand-600" />
          <p className="text-sm font-semibold text-foreground">竞品广告转化拆解</p>
        </div>
        <p className="text-xs text-muted-foreground">暂无</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-border bg-white p-4">
        <div className="flex items-start gap-3">
          <TrendingUp className="mt-0.5 h-5 w-5 text-brand-600" />
          <div>
            <h3 className="text-sm font-semibold text-foreground">竞品广告转化拆解</h3>
            <p className="mt-1 text-sm leading-relaxed text-brand-500">
              按标题、主图、副图、五点、A+和评论拆解其对广告漏斗的影响：标题看流量准不准，主图看点不点击，副图/五点/A+看转不转化，评论看广告承诺能不能被信任。
            </p>
          </div>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {modules.map((module) => {
          const Icon = iconMap[module.key] || FileText;
          const adRead = competitorModuleAdMetricMap(module.key);
          const displayIntents = sameCompetitorStringList(module.covered_user_intents, module.keywords)
            ? competitorModuleDefaultIntents(module.key)
            : module.covered_user_intents;
          const displayKeywords = cleanCompetitorKeywordList(module.keywords, [],);
          const displayStructure = competitorModuleStructureNarrative(module.key, module.structure_breakdown);
          const rawObject = module.raw_content && typeof module.raw_content === "object" && !Array.isArray(module.raw_content)
            ? module.raw_content as Record<string, unknown>
            : null;
          const imageUrlsFromObject = rawObject && Array.isArray(rawObject.images)
            ? rawObject.images.filter((item): item is string => typeof item === "string" && item.startsWith("http"))
            : [];
          const imageUrls = imageUrlsFromObject.length > 0 ? imageUrlsFromObject : Array.isArray(module.raw_content)
            ? module.raw_content.filter((item): item is string => typeof item === "string" && item.startsWith("http"))
            : [];

          return (
            <div key={module.key} className="rounded-lg border border-border bg-background p-4">
              <div className="mb-3">
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-brand-600" />
                  <p className="text-sm font-semibold text-foreground">{module.name || "待录入"}</p>
                </div>
                {module.summary && <p className="mt-2 text-sm leading-relaxed text-brand-500">{module.summary}</p>}
              </div>
              <div className="space-y-4">
                <div className="rounded-lg border border-brand-100 bg-brand-50 p-3">
                  <div className="mb-2 flex flex-wrap gap-1.5">
                    {adRead.metrics.map((metric) => (
                      <span key={metric} className="rounded-full border border-brand-200 bg-white px-2 py-0.5 text-[11px] font-medium text-brand-700">
                        {label(IMPACT_METRIC_LABELS, metric)}
                      </span>
                    ))}
                  </div>
                  <p className="text-xs leading-relaxed text-brand-600">{adRead.funnelRole}</p>
                </div>
                {imageUrls.length > 0 && (
                  <div className="flex gap-2 overflow-x-auto pb-1">
                    {imageUrls.slice(0, 8).map((url, index) => (
                      <img key={`${url}-${index}`} src={url} alt={`${module.name} ${index + 1}`} className="h-20 w-20 rounded-lg border border-border object-contain bg-white" />
                    ))}
                  </div>
                )}
                <CompetitorOriginalEvidencePreview raw={module.raw_content} moduleName={module.name} />
                <CompetitorBreakdownSection title="广告指标判断" items={[adRead.strengthMeaning, adRead.weaknessMeaning]} tone="blue" />
                <CompetitorBreakdownSection title="结构拆解" items={displayStructure} />
                <CompetitorBreakdownSection title="强项判断" items={module.strengths} tone="green" />
                <CompetitorBreakdownSection title="弱项判断" items={module.weaknesses} tone="red" />
                <CompetitorBreakdownSection title="覆盖的买家需求" items={displayIntents} badge />
                <CompetitorBreakdownSection title="对应关键词/语义词" items={displayKeywords} badge />
                <CompetitorBreakdownSection title="我方广告打法" items={[adRead.attackAngle, ...(module.borrowable_actions || [])]} tone="blue" />
                <CompetitorBreakdownSection title="不建议模仿点" items={module.do_not_copy} tone="amber" />
                <details className="rounded-lg border border-border bg-white p-3">
                  <summary className="cursor-pointer text-sm font-medium text-brand-500">展开查看原始内容</summary>
                  <pre className="mt-3 max-h-60 overflow-auto whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">
                    {formatCompetitorRawContent(module.raw_content)}
                  </pre>
                </details>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

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
  const [opportunityKeyword, setOpportunityKeyword] = useState("");
  const [selectionAnalyzing, setSelectionAnalyzing] = useState(false);
  const [selectionAnalyzingTarget, setSelectionAnalyzingTarget] = useState("");
  const [selectionSummary, setSelectionSummary] = useState("");
  const [selectionResult, setSelectionResult] = useState<Record<string, any> | null>(null);
  const [selectionResultAsin, setSelectionResultAsin] = useState("");
  const [autoImportMarketplace, setAutoImportMarketplace] = useState("US");
  const [autoImportLoading, setAutoImportLoading] = useState(false);
  const [autoImportProgress, setAutoImportProgress] = useState(0);
  const [autoImportElapsed, setAutoImportElapsed] = useState(0);
  const [autoImportMessage, setAutoImportMessage] = useState("");
  const [autoImportSubMessage, setAutoImportSubMessage] = useState("");
  const [analysisSourceLabel, setAnalysisSourceLabel] = useState("待录入");
  const [batchImportText, setBatchImportText] = useState("");
  const [batchImportLoading, setBatchImportLoading] = useState(false);
  const [batchImportCurrent, setBatchImportCurrent] = useState("");
  const [autoFetch, setAutoFetch] = useState(true);

  // Fetch history state
  const [showHistory, setShowHistory] = useState(true);
  const [fetchHistoryItems, setFetchHistoryItems] = useState<ActionSnapshot[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const selectionHistoryItems = useMemo(
    () =>
      fetchHistoryItems.filter((item) => {
        const input = (item.input_snapshot || {}) as Record<string, unknown>;
        const output = (item.output_snapshot || {}) as Record<string, unknown>;
        const keyword = String(input.keyword || output.keyword || "").trim();
        const asin = String(input.asin || item.asin || "").trim();
        if (item.action_key === "selection_analysis") return Boolean(keyword) && !asin;
        return false;
      }),
    [fetchHistoryItems]
  );

  useEffect(() => {
    if (!autoImportLoading && !batchImportLoading && !selectionAnalyzing) return;
    const startedAt = Date.now();
    const targetSeconds = selectionAnalyzing ? 300 : 60;
    const timer = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      setAutoImportElapsed(elapsed);
      setAutoImportProgress((current) => Math.max(current, Math.min(92, Math.round((elapsed / targetSeconds) * 92))));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [autoImportLoading, batchImportLoading, selectionAnalyzing]);

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
  const [competitorListingReports, setCompetitorListingReports] = useState<Record<string, CompetitorListingReport>>({});
  const [competitorListingLoadingAsin, setCompetitorListingLoadingAsin] = useState<string | null>(null);
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
      loadCompetitorListingHistory(items).catch(() => {});
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

  const loadCompetitorListingHistory = useCallback(async (productList: Product[]) => {
    if (!productList.length) return;
    const asinSet = new Set(productList.map((product) => product.asin));
    const items = await getActionSnapshots({
      module_key: "asin_selection",
      action_key: "competitor_listing_diagnosis",
      limit: 200,
    });
    const map: Record<string, CompetitorListingReport> = {};
    for (const item of items || []) {
      const input = (item.input_snapshot || {}) as Record<string, unknown>;
      const output = (item.output_snapshot || {}) as Record<string, unknown>;
      const asin = String(item.asin || input.asin || output.asin || "").toUpperCase();
      if (!asin || !asinSet.has(asin) || map[asin]) continue;
      map[asin] = output as unknown as CompetitorListingReport;
    }
    if (Object.keys(map).length) {
      setCompetitorListingReports((prev) => ({ ...prev, ...map }));
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

      return true;
    })
    .sort((a, b) => {
      const scoreA = scoreResults[a.asin]?.total_score ?? 0;
      const scoreB = scoreResults[b.asin]?.total_score ?? 0;
      return scoreB - scoreA;
    });

  const poolCount = products.filter((p) => {
    const score = scoreResults[p.asin];
    return isOpportunityScore(score);
  }).length;

  const libraryCount = products.length;

  /* ---- 6D Scoring ---- */
  const formatSelectionScore = (value: unknown) => {
    const score = Number(value || 0);
    return score ? `${Math.round(score)}/100` : "待录入";
  };

  const selectionItemTitle = (item: any) =>
    String(item?.title || item?.name || item?.module || item?.action || "暂无");

  const selectionItemDetail = (item: any) =>
    [
      item?.evidence,
      item?.reason,
      item?.detail,
      item?.description,
      item?.recommendation,
    ]
      .filter(Boolean)
      .map((value) => String(value))
      .join(" / ") || "暂无";

  const toSelectionTextList = (value: unknown) => {
    if (Array.isArray(value)) {
      return value
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object") return selectionItemDetail(item);
          return String(item || "");
        })
        .map((item) => item.trim())
        .filter(Boolean);
    }
    if (value && typeof value === "object") {
      return Object.values(value as Record<string, unknown>)
        .map((item) => String(item || "").trim())
        .filter(Boolean);
    }
    const text = String(value || "").trim();
    return text ? [text] : [];
  };

  const runSelectionAgent = async (
    product?: Product,
    extraContext: Record<string, unknown> = {}
  ) => {
    const resultAsin = product?.asin || autoImportAsin.trim().toUpperCase();
    const moduleTaskId = `selection:${product?.asin || autoImportAsin.trim().toUpperCase() || opportunityKeyword.trim() || "entry"}`;
    setShowAutoImport(true);
    setShowHistory(false);
    setSelectionAnalyzing(true);
    setSelectionAnalyzingTarget(resultAsin || "entry");
    setSelectionSummary("");
    setSelectionResult(null);
    setSelectionResultAsin(resultAsin);
    setAutoImportProgress((current) => Math.max(current, 88));
    setAutoImportMessage("选品判断正在输出市场机会判断");
    setAnalysisSourceLabel("选品判断");
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "asin-manager",
      label: `选品判断 ${product?.asin || autoImportAsin.trim().toUpperCase() || opportunityKeyword.trim() || ""}`,
      status: "running",
      detail: "正在做机会判断",
      path: "/asin-manager",
    });
    try {
      const res = await axios.post(
        `${getLongRunningApiBase()}/api/v1/workflow-chain/selection-dispatch`,
        {
          auto_run: true,
          max_nodes: 1,
          extra_context: {
            entry: "asin_selection",
            agent: "选品判断",
            asin: product?.asin || autoImportAsin.trim().toUpperCase(),
            keyword: opportunityKeyword.trim(),
            ...extraContext,
          },
        },
        { headers: getAuthHeaders(), timeout: 180000 }
      );
      const result = res.data?.executed_nodes?.[0]?.ai?.result || {};
      const score = Number(result.score || 0);
      const summary = score ? `选品判断已完成判断：${formatSelectionScore(score)}` : "选品判断已完成判断";
      setSelectionSummary(summary);
      setSelectionResult(result);
      setAutoImportProgress(100);
      window.setTimeout(() => {
        document.getElementById("asin-opportunity-result")?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 80);
      saveActionSnapshot({
        module_key: "asin_selection",
        module_name: "选品历史",
        action_key: "selection_analysis",
        action_name: "选品判断AI分析",
        product_id: product?.id || null,
        asin: product?.asin || autoImportAsin.trim().toUpperCase(),
        title: product?.title || opportunityKeyword.trim() || autoImportAsin.trim().toUpperCase() || "待录入",
        input_snapshot: {
          asin: product?.asin || autoImportAsin.trim().toUpperCase(),
          keyword: opportunityKeyword.trim(),
          extra_context: extraContext,
        },
        output_snapshot: result,
        data_source: "选品判断",
        confidence: result.confidence || "low",
        ai_called: true,
        source_record_table: "action_snapshots",
      }).then(() => loadFetchHistory()).catch(() => {});
      finishModuleTask(moduleTaskId, "completed", summary);
      toast.success(summary);
      return res.data;
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? e.response?.data?.detail || "选品判断AI分析失败"
        : e instanceof Error
          ? e.message
          : "选品判断AI分析失败";
      finishModuleTask(moduleTaskId, "failed", msg);
      toast.error(msg);
      throw e;
    } finally {
      setSelectionAnalyzing(false);
      setSelectionAnalyzingTarget("");
      window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
    }
  };

  const pollSelectionKeywordTask = async (context: KeywordResearchTaskContext, fromResume = false) => {
    const cleanKeyword = context.keyword.trim();
    const marketplace = (context.marketplace || autoImportMarketplace || "US").toUpperCase();
    const moduleTaskId = context.moduleTaskId || `amazon-keyword:${marketplace}:${cleanKeyword}`;
    const taskId = context.taskId;
    setShowAutoImport(true);
    setShowHistory(false);
    setOpportunityKeyword(cleanKeyword);
    setAutoImportMarketplace(marketplace);
    setSelectionAnalyzing(true);
    setSelectionAnalyzingTarget(`keyword:${cleanKeyword}`);
    setSelectionSummary(fromResume ? "任务恢复中" : "");
    setSelectionResult(null);
    setSelectionResultAsin("");
    setAutoImportProgress(8);
    setAutoImportElapsed(0);
    setAutoImportMessage("抓取中");
    setAutoImportSubMessage("已抓取 0/40");
    setAnalysisSourceLabel("亚马逊搜索页");
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "asin-manager",
      label: `关键词调研 ${cleanKeyword}`,
      status: "running",
      detail: "正在抓取Top40数据",
      path: "/asin-manager",
    });
    try {
      let task: Record<string, any> = {};
      let taskResult: Record<string, any> | null = null;
      for (let attempt = 0; attempt < 450; attempt += 1) {
        if (attempt > 0) {
          await new Promise((resolve) => window.setTimeout(resolve, 2000));
        }
        const statusRes = await axios.get(
          `${getLongRunningApiBase()}/api/v1/asin-selection/amazon-keyword-research/tasks/${taskId}`,
          { headers: getAuthHeaders(), timeout: 30000 }
        );
        task = statusRes.data;
        const taskProgress = Number(task?.progress_percent || 0);
        setAutoImportProgress(Math.min(95, Math.max(8, taskProgress || 8 + Math.floor(attempt / 3))));
        const partialResult = task?.result_payload?.result || null;
        const partialSteps =
          task?.result_payload?.source_steps ||
          partialResult?.market_research?.source_steps ||
          [];
        const sampleCount = Number(task?.result_payload?.item_count || partialResult?.market_research?.item_count || 0);
        if (partialResult && task?.status !== "completed") {
          const latestStep = partialSteps.length ? partialSteps[partialSteps.length - 1] : null;
          const latestText = String(latestStep?.step || "");
          const phase =
            /输出|复核|初筛|清洗|分析推理/.test(latestText) || sampleCount >= 40
              ? "分析推理中"
              : "抓取中";
          setAutoImportMessage(phase);
          setAutoImportSubMessage(
            phase === "抓取中"
              ? `已抓取 ${Math.min(40, sampleCount)}/40`
              : `已抓取 ${Math.min(40, sampleCount)}/40`
          );
        } else {
          setAutoImportMessage("抓取中");
          setAutoImportSubMessage(`已抓取 ${Math.min(40, sampleCount)}/40`);
        }
        if (task?.status === "completed") {
          taskResult = task.result_payload || null;
          break;
        }
        if (task?.status === "failed" && task?.result_payload?.result) {
          taskResult = task.result_payload || null;
          break;
        }
        if (task?.status === "failed") {
          throw new Error(task.error_message || "分析失败");
        }
      }
      if (!taskResult) throw new Error("仍在分析，请稍后查看");
      const result = (taskResult.result || {}) as Record<string, any>;
      const sampleCount = Number(result.market_research?.item_count || 0);
      const hasMarketSamples = sampleCount > 0;
      const hasCompleteTop40 = sampleCount >= 40;
      const score = Number(result.score || 0);
      const summary = hasCompleteTop40
        ? (score ? `已完成判断：${formatSelectionScore(score)}` : "已完成判断")
        : hasMarketSamples
          ? `Top40数据未抓完整：${sampleCount}/40`
          : "未取到真实样本";
      setSelectionResult(result);
      setSelectionSummary(summary);
      setAutoImportProgress(100);
      if (autoFetch && hasCompleteTop40) {
        saveActionSnapshot({
          module_key: "asin_selection",
          module_name: "选品历史",
          action_key: "selection_analysis",
          action_name: "关键词调研",
          asin: "",
          title: cleanKeyword,
          input_snapshot: {
            keyword: cleanKeyword,
            marketplace,
            source: "selection_keyword_research",
          },
          output_snapshot: result,
          data_source: result.market_research?.data_source || "亚马逊搜索页 / 分析推理",
          confidence: result.confidence || "low",
          ai_called: true,
          source_record_table: "action_snapshots",
        }).then(() => loadFetchHistory()).catch(() => {});
      }
      finishModuleTask(moduleTaskId, "completed", summary);
      clearKeywordResearchTaskContext();
      window.setTimeout(() => {
        document.getElementById("asin-opportunity-result")?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 80);
      if (hasCompleteTop40) toast.success(summary);
      else toast.error(summary);
      return taskResult;
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? e.response?.data?.detail || "分析失败"
        : e instanceof Error
          ? e.message
          : "分析失败";
      finishModuleTask(moduleTaskId, "failed", msg);
      clearKeywordResearchTaskContext();
      toast.error(msg);
      throw e;
    } finally {
      setSelectionAnalyzing(false);
      setSelectionAnalyzingTarget("");
      setAutoImportLoading(false);
      setAutoImportProgress(0);
      setAutoImportElapsed(0);
      setAutoImportMessage("");
      setAutoImportSubMessage("");
      setAnalysisSourceLabel("待录入");
      window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
    }
  };

  const runSelectionKeywordResearch = async (keyword: string) => {
    const cleanKeyword = keyword.trim();
    const marketplace = autoImportMarketplace;
    const moduleTaskId = `amazon-keyword:${marketplace}:${cleanKeyword}`;
    setShowAutoImport(true);
    setShowHistory(false);
    setSelectionAnalyzing(true);
    setSelectionAnalyzingTarget(`keyword:${cleanKeyword}`);
    setSelectionSummary("");
    setSelectionResult(null);
    setAutoImportProgress(8);
    setAutoImportElapsed(0);
    setAutoImportMessage("抓取中");
    setAutoImportSubMessage("已抓取 0/40");
    const taskRes = await axios.post(
      `${getLongRunningApiBase()}/api/v1/asin-selection/amazon-keyword-research/tasks`,
      {
        keyword: cleanKeyword,
        marketplace,
        max_keywords: 3,
      },
      { headers: getAuthHeaders(), timeout: 30000 }
    );
    const taskId = taskRes.data?.task_id;
    if (!taskId) throw new Error("任务创建失败");
    const context = { taskId, keyword: cleanKeyword, marketplace, moduleTaskId };
    saveKeywordResearchTaskContext(context);
    return pollSelectionKeywordTask(context);
  };

  useEffect(() => {
    if (authLoading || selectionAnalyzing) return;
    const context = loadKeywordResearchTaskContext();
    if (!context) return;
    void pollSelectionKeywordTask(context, true).catch(() => {});
  }, [authLoading]);

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
      label: `6维评分 ${product.asin}`,
      status: "running",
      detail: "正在分析",
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
          module_name: "6维选品",
          action_key: "six_dimension_score",
          action_name: "ASIN 6维选品评分",
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
        toast.success(
          `${product.asin} 6维决策完成: ${result.total_score}分 · ${result.decision || "已生成"} · ${result.pool_status === "opportunity_pool" ? "进入机会池" : "未进机会池"}`
        );
        finishModuleTask(moduleTaskId, "completed", "6维评分完成");
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

  useEffect(() => {
    if (authLoading) return;
    const consumeLocalBrowserCapture = async () => {
      const raw = localStorage.getItem("alignx_local_browser_capture");
      if (!raw) return;
      let capture: {
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
        destination?: string;
      };
      try {
        capture = JSON.parse(raw);
      } catch {
        localStorage.removeItem("alignx_local_browser_capture");
        return;
      }
      if (capture.destination && capture.destination !== "asin") return;
      if (!capture.html || !capture.asin) return;

      localStorage.removeItem("alignx_local_browser_capture");
      const mp = capture.marketplace || autoImportMarketplace || "US";
      const moduleTaskId = `asin-local-capture:${capture.asin}`;
      setAutoImportAsin(capture.asin);
      setAutoImportMarketplace(mp);
      setAutoImportLoading(true);
      setAutoImportProgress(45);
      setAutoImportMessage("正在用本地浏览器采集证据写入ASIN选品库");
      upsertModuleTask({
        id: moduleTaskId,
        moduleKey: "asin-manager",
        label: `本地采集写入 ${capture.asin}`,
        status: "running",
        detail: "正在解析本地浏览器页面并写入ASIN库",
        path: "/asin-manager",
      });
      try {
        const res = await axios.post(
          `${getLongRunningApiBase()}/api/v1/asin-analysis/parse-html-analyze`,
          {
            asin: capture.asin,
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
          },
          { headers: getAuthHeaders(), timeout: 180000 }
        );
        const d = res.data;
        if (!d?.success || !d.product_data) {
          const msg = d?.error || "本地采集解析失败";
          finishModuleTask(moduleTaskId, "failed", msg);
          toast.error(msg);
          return;
        }
        const pd = d.product_data || {};
        const productData: Omit<Product, "id" | "created_at" | "marketplace"> = {
          asin: d.asin || capture.asin,
          title: pd.title || d.product_title || capture.title || capture.asin,
          bullet_points: Array.isArray(pd.bullet_points) ? pd.bullet_points.join("\n") : pd.bullet_points || "",
          a_plus_content: pd.description_summary || pd.aplus_content || "",
          search_keywords: Array.isArray(pd.main_keywords) ? pd.main_keywords.join(", ") : pd.main_keywords || "",
          price: parseFloat(String(pd.price || capture.price || "").replace(/[^0-9.]/g, "")) || 0,
          review_count: parseInt(String(pd.review_count || capture.reviewCount || "").replace(/[^0-9]/g, ""), 10) || 0,
          rating: parseFloat(String(pd.rating || capture.rating || "")) || 0,
          category: pd.category || "",
        };
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
        saveActionSnapshot({
          module_key: "asin_selection",
          module_name: "ASIN选品",
          action_key: "local_browser_capture_import",
          action_name: "本地浏览器采集写入ASIN库",
          asin: productData.asin,
          title: productData.title,
          input_snapshot: { asin: capture.asin, marketplace: mp },
          output_snapshot: { ...productData, marketplace: mp, capture_quality: pd.capture_quality },
          data_source: "本地浏览器页面采集",
          confidence: "high",
          ai_called: true,
          source_record_table: "products",
        }).catch(() => {});
        setAutoImportProgress(100);
        finishModuleTask(moduleTaskId, "completed", "本地采集写入完成");
        toast.success(`已用本地浏览器采集${saved.mode === "updated" ? "更新" : "保存"} ${productData.asin}`);
      } catch (err) {
        const msg = axios.isAxiosError(err) ? err.response?.data?.detail || err.message : "本地采集写入失败";
        finishModuleTask(moduleTaskId, "failed", msg);
        toast.error(msg);
      } finally {
        setAutoImportLoading(false);
        setAutoImportMessage("");
        window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
      }
    };

    consumeLocalBrowserCapture();
    const onCapture = () => consumeLocalBrowserCapture();
    window.addEventListener("alignx-local-browser-capture", onCapture);
    return () => window.removeEventListener("alignx-local-browser-capture", onCapture);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading]);

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
        inventory_status: outOfStockAsins[productData.asin] ? "out_of_stock" : "",
        is_own_product: Boolean(outOfStockAsins[productData.asin]),
      },
      { headers: getAuthHeaders(), timeout: 180000 }
    );
    const normalizedReport = normalizeKeywordSalesReport(res.data);
    setKeywordValidationResults((prev) => ({ ...prev, [productData.asin]: normalizedReport }));
    setExpandedKeywordAsin(productData.asin);
    return normalizedReport;
  };

  const runCompetitorListingDiagnosis = async (product: Product) => {
    const marketplace = getProductMarketplace(product);
    const moduleTaskId = `competitor-listing:${product.asin}`;
    setCompetitorListingLoadingAsin(product.asin);
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "asin-manager",
      label: `竞品Listing ${product.asin}`,
      status: "running",
      detail: "正在分析承接能力",
      path: "/asin-manager",
    });
    try {
      const res = await axios.post(
        `${getLongRunningApiBase()}/api/v1/asin-analysis/analyze`,
        { asin: product.asin, marketplace, force_refresh: true },
        { headers: getAuthHeaders(), timeout: 240000 }
      );
      const evidenceReport = res.data as CompetitorListingReport;
      const keywordReport = keywordValidationResults[product.asin];
      let selectionJudgment: Record<string, any> | null = null;
      try {
        const selectionRes = await axios.post(
          `${getLongRunningApiBase()}/api/v1/ai-gateway/agent`,
          {
            agent: "selection_agent",
            task: "基于竞品ASIN页面证据判断Listing承接能力、自然/广告排名来源、评价关键词和是否有机会打。",
            depth: "deep",
            dry_run: false,
            payload: {
              context_type: "competitor_asin_selection",
              analysis_mode: "competitor_listing_attack",
              hard_rules: [
                "只判断单个竞品ASIN在选品考察阶段是否值得作为对标或攻击对象。",
                "不要按本品承接诊断输出修改建议；竞品只输出对标、攻击位置、风险和验证。",
                "必须基于已抓取页面事实、关键词排名证据、评论证据和Listing承接模块输出。",
                "必须覆盖Listing承接能力、自然排名/广告排名来源、5星好评关键词、抱怨关键词、可打判断、验证。",
                "没有证据必须写暂无或待补证据，不能编造。",
              ],
              asin: product.asin,
              marketplace,
              product: {
                title: evidenceReport.product_title || product.title,
                price: evidenceReport.product_data?.price || product.price,
                rating: evidenceReport.product_data?.rating || product.rating,
                review_count: evidenceReport.product_data?.review_count || product.review_count,
                category: evidenceReport.product_data?.category || product.category,
              },
              listing_evidence: {
                scores: evidenceReport.scores || {},
                listing_breakdown: evidenceReport.analysis_report?.listing_breakdown || {},
                rating_histogram: evidenceReport.product_data?.rating_histogram || {},
                low_star_reviews: evidenceReport.product_data?.low_star_reviews || [],
                main_keywords: evidenceReport.product_data?.main_keywords || [],
                data_source: evidenceReport.data_source || evidenceReport.product_data?._data_source || "",
              },
              rank_evidence: {
                rank_source: getRankSourceJudgment(keywordReport).label,
                rank_snapshots: keywordReport?.rank_snapshots || [],
              },
	              output_focus: [
	                "经营结论",
	                "为什么",
	                "观察",
	                "动作",
	                "验证",
	              ],
            },
          },
          { headers: getAuthHeaders(), timeout: 180000 }
        );
        selectionJudgment = selectionRes.data?.result || null;
      } catch (err) {
        void err;
      }
      const report: CompetitorListingReport = {
        ...evidenceReport,
        selection_judgment: selectionJudgment || undefined,
      };
      setCompetitorListingReports((prev) => ({ ...prev, [product.asin]: report }));
      saveActionSnapshot({
        module_key: "asin_selection",
        module_name: "选品历史",
        action_key: "competitor_listing_diagnosis",
        action_name: "竞品Listing诊断",
        product_id: product.id,
        asin: product.asin,
        title: report.product_title || product.title || product.asin,
        input_snapshot: {
          asin: product.asin,
          marketplace,
          source: "competitor_asin",
        },
        output_snapshot: report as unknown as Record<string, unknown>,
        data_source: selectionJudgment ? "选品判断 / 亚马逊ASIN证据" : report.data_source || String(report.product_data?._data_source || "asin_analysis"),
        confidence: String(report.product_data?.data_confidence || "medium"),
        ai_called: Boolean(selectionJudgment),
        source_record_table: "asin_analyses",
        source_record_id: report.id,
      }).then(() => loadFetchHistory()).catch(() => {});
      finishModuleTask(moduleTaskId, "completed", "竞品Listing诊断完成");
      return report;
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? e.response?.data?.detail || "竞品Listing诊断失败"
        : e instanceof Error
          ? e.message
          : "竞品Listing诊断失败";
      finishModuleTask(moduleTaskId, "failed", msg);
      toast.error(msg);
      return null;
    } finally {
      setCompetitorListingLoadingAsin(null);
      window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
    }
  };

  useEffect(() => {
    if (authLoading) return;
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
      setAutoImportLoading(true);
      setAutoImportElapsed(0);
      setAutoImportProgress(20);
      setAutoImportMessage(`正在恢复 ${context.asin} 的后台抓取分析任务`);
      upsertModuleTask({
        id: moduleTaskId,
        moduleKey: "asin-manager",
        label: `ASIN抓取分析 ${context.asin}`,
        status: "running",
        detail: "用户切换页面后继续恢复后台任务",
        path: "/asin-manager",
        startedAt: context.startedAt,
      });

      try {
        let task: AsinDiagnosisTaskResponse | null = null;
        for (let attempt = 0; attempt < 180; attempt += 1) {
          if (cancelled) return;
          const statusRes = await axios.get<AsinDiagnosisTaskResponse>(
            `${apiBase}/api/v1/diagnosis-tasks/${taskId}`,
            { headers: getAuthHeaders(), timeout: 30000 }
          );
          task = statusRes.data;
          if (task.status === "completed") break;
          if (task.status === "failed") {
            throw new Error(task.error_message || "ASIN后台任务失败");
          }
          setAutoImportProgress((current) => Math.min(92, Math.max(current, 20 + attempt)));
          await new Promise((resolve) => window.setTimeout(resolve, 2000));
        }

        if (cancelled) return;
        if (!task || task.status !== "completed" || !task.result_payload) {
          toast.warning("ASIN后台任务仍在运行，稍后返回ASIN选品页会继续恢复");
          return;
        }

        const normalized = productDataFromAsinTaskPayload(task.result_payload, context.asin);
        const productData = normalized.data;
        const sourceLabel = productFetchSourceLabel(normalized.source);
        const isLowConfidence = sourceLabel === "低置信度补充分析";
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
            module_name: "6维选品",
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
          toast.success(`${productData.asin} 后台刷新已完成`);
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
            module_name: "6维选品",
            action_key: "recover_fetch_asin_product",
            action_name: "恢复ASIN后台抓取并保存",
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
          toast.success(`${productData.asin} 后台抓取已${saved.mode === "updated" ? "更新" : "保存"}`);
        }

        setAutoImportProgress(100);
        await loadProducts();
        clearActiveAsinTaskStorage();
        finishModuleTask(moduleTaskId, "completed", "ASIN后台任务已恢复完成");
        window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
      } catch (e: unknown) {
        const msg = axios.isAxiosError(e)
          ? e.response?.data?.detail || e.message
          : e instanceof Error
            ? e.message
            : "ASIN后台任务恢复失败";
        if (!cancelled) {
          toast.error(msg);
          finishModuleTask(moduleTaskId, "failed", msg);
          clearActiveAsinTaskStorage();
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
      detail: "后台正在抓取Amazon页面并生成选品判断",
      path: "/asin-manager",
    });
    let task = taskRes.data;
    for (let attempt = 0; attempt < 180; attempt += 1) {
      const statusRes = await axios.get<AsinDiagnosisTaskResponse>(
        `${apiBase}/api/v1/diagnosis-tasks/${taskRes.data.task_id}`,
        { headers: getAuthHeaders(), timeout: 30000 }
      );
      task = statusRes.data;
      if (task.status === "completed") break;
      if (task.status === "failed") {
        finishModuleTask(moduleTaskId, "failed", task.error_message || "ASIN分析任务失败");
        clearActiveAsinTaskStorage();
        throw new Error(task.error_message || "ASIN分析任务失败");
      }
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
    }
    if (task.status !== "completed" || !task.result_payload) {
      throw new Error("ASIN分析仍在后台运行，请稍后刷新查看");
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

    // Phase 2 + 3: Backend server scrape first, then AI fallback when real data is unavailable.
    setAutoImportMessage("正在补充商品信息并生成低置信度标记");
    setAutoImportProgress(62);
    try {
      const aiResult = await fetchAsinViaAI(asin, marketplace, context);
      setAutoImportProgress(100);
      return aiResult;
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? e.code === "ECONNABORTED"
          ? "分析超过180秒，请稍后重试；如果连续失败，请稍后再试。"
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
        const isLowConfidence = sourceLabel === "低置信度补充分析";
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
    const keyword = opportunityKeyword.trim();
    if (!keyword) {
      toast.error("请输入关键词");
      return;
    }
    setAutoImportLoading(true);
    try {
      await runSelectionKeywordResearch(keyword);
    } finally {
      setAutoImportLoading(false);
      setAutoImportProgress(0);
      setAutoImportElapsed(0);
      setAutoImportMessage("");
      setAnalysisSourceLabel("待录入");
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
                module_name: "6维选品",
                action_key: "batch_fetch_asin_product",
                action_name: "批量ASIN抓取并保存",
                asin,
                title: result.data.title || asin,
                input_snapshot: { asin, marketplace: autoImportMarketplace },
                output_snapshot: { ...productData, marketplace: autoImportMarketplace },
                data_source: productFetchSourceLabel(result.source),
                confidence: productFetchSourceLabel(result.source) === "低置信度补充分析" ? "low" : "high",
                ai_called: productFetchSourceLabel(result.source) === "低置信度补充分析",
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
        const isLowConfidence = sourceLabel === "低置信度补充分析";
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

  useEffect(() => {
    if (!authLoading) loadFetchHistory();
  }, [authLoading]);

  const toggleHistory = () => {
    if (!showHistory) loadFetchHistory();
    setShowHistory(!showHistory);
  };

  const snapshotInput = (item: ActionSnapshot) =>
    (item.input_snapshot || {}) as Record<string, unknown>;

  const snapshotOutput = (item: ActionSnapshot) =>
    (item.output_snapshot || {}) as Record<string, unknown>;

  const loadSelectionHistoryItem = (item: ActionSnapshot) => {
    const input = snapshotInput(item);
    const output = snapshotOutput(item);
    if (item.action_key === "competitor_listing_diagnosis") {
      const asin = String(input.asin || item.asin || (output as Record<string, unknown>).asin || "");
      if (asin) {
        setCompetitorListingReports((prev) => ({
          ...prev,
          [asin]: output as unknown as CompetitorListingReport,
        }));
        setExpandedKeywordAsin(asin);
        setSearchQuery(asin);
      }
        setShowAutoImport(true);
      setShowForm(false);
      setAutoImportAsin(asin);
      return;
    }
    setShowAutoImport(true);
    setShowForm(false);
    setAutoImportAsin(String(input.asin || item.asin || ""));
    setOpportunityKeyword(String(input.keyword || item.title || ""));
    setSelectionResult(output as Record<string, any>);
    setSelectionResultAsin(String(input.asin || item.asin || ""));
    const score = Number((output as Record<string, any>).score || 0);
    setSelectionSummary(score ? `选品判断已完成判断：${formatSelectionScore(score)}` : "选品判断已完成判断");
    window.setTimeout(() => {
      document.getElementById("asin-opportunity-result")?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 80);
  };

  const getSelectionHistoryTitle = (item: ActionSnapshot) => {
    const input = snapshotInput(item);
    return String(input.keyword || item.title || item.asin || "待录入");
  };

  const getSelectionHistoryType = (item: ActionSnapshot) => {
    if (item.action_key === "competitor_listing_diagnosis") return "竞品Listing";
    return "关键词调研";
  };

  const selectionKeywordSampleCount = Number(selectionResult?.market_research?.item_count ?? 0);
  const selectionRequiresKeywordSamples = Boolean(selectionResult?.market_research);
  const selectionHasRequiredSamples = !selectionRequiresKeywordSamples || selectionKeywordSampleCount >= 40;
  const selectionSixDResult = selectionHasRequiredSamples
    ? ((selectionResult?.keyword_six_dimension as FiveDScoreResult | undefined) || (selectionResultAsin ? scoreResults[selectionResultAsin] : null))
    : null;
  const selectionSixDEvidence = sixDimensionEvidenceItems(selectionSixDResult);
  const selectionRadarScores = (() => {
    const rawScores = selectionSixDResult?.dimension_scores || {};
    const maxScore = Math.max(0, ...Object.values(rawScores).map((value) => Number(value) || 0));
    return Object.fromEntries(
      Object.entries(rawScores).map(([key, value]) => {
        const score = Number(value) || 0;
        return [key, Math.max(0, Math.min(20, maxScore > 20 ? score / 5 : score))];
      })
    );
  })();
  const cleanMarketSourceLabel = (value: unknown) => {
    const text = String(value || "").trim();
    if (!text) return "暂无";
    if (/qwen|deepseek|gpt|model|模型|aihub|openai/i.test(text)) return "搜索词矩阵";
    if (/external|virtual desktop|虚拟桌面/i.test(text)) return "浏览器截图";
    if (/local_browser_vision|browser|截图/i.test(text)) return "浏览器截图";
    if (/scrapeless|selection|external|search_result|amazon/i.test(text)) return "亚马逊搜索页";
    if (/scraping|rules|规则/i.test(text)) return "暂无";
    return text;
  };
  const formatMarketPrice = (value: unknown) => {
    const num = Number(value);
    return Number.isFinite(num) && num > 0 ? `${num.toFixed(2)}美元` : String(value || "暂无");
  };
  const formatMarketCount = (value: unknown) => {
    const num = Number(value);
    return Number.isFinite(num) && num > 0 ? String(Math.round(num)) : "暂无";
  };
  const selectionMarketResearch = selectionResult?.market_research || null;
  const selectionMarketLanes = Array.isArray(selectionMarketResearch?.lanes) ? selectionMarketResearch.lanes : [];
  const selectionLaneRows = selectionMarketLanes.map((lane: any) => {
    const summary = lane?.analysis?.summary || {};
    const recommendedBand = lane?.analysis?.recommendedPriceBand || {};
    const rows = Array.isArray(lane?.analysis?.tableRows) ? lane.analysis.tableRows : Array.isArray(lane?.items) ? lane.items : [];
    return {
      keyword: lane?.keyword || "待录入",
      source: cleanMarketSourceLabel(lane?.source),
      count: summary.totalListings ?? rows.length,
      top20Count: summary.top20Count,
      top40Count: summary.top40Count ?? summary.totalListings ?? rows.length,
      medianPrice: summary.medianPrice,
      medianReviews: summary.medianReviews,
      sponsoredCount: summary.sponsoredCount,
      headline: lane?.analysis?.headline || "暂无",
      priceBand: recommendedBand.label || "暂无",
    };
  });
  const selectionMarketSampleRows = selectionMarketLanes.flatMap((lane: any) => {
    const rows = Array.isArray(lane?.analysis?.tableRows) ? lane.analysis.tableRows : Array.isArray(lane?.items) ? lane.items : [];
    return rows
      .slice(0, 40)
      .map((item: any, index: number) => ({
        keyword: lane?.keyword || "待录入",
        rank: item?.searchRank || item?.rank || index + 1,
        asin: item?.asin || "暂无",
        title: item?.title || "暂无",
        price: item?.price ?? item?.searchPrice ?? item?.priceText ?? item?.searchPriceText,
        rating: item?.rating,
        reviews: item?.reviewCount ?? item?.reviews,
        tag: item?.opportunityTag || "暂无",
        source: cleanMarketSourceLabel(item?.source || lane?.source),
      }));
  });
  const formatMarketText = (value: unknown) => {
    if (value === null || value === undefined || value === "") return "暂无";
    if (Array.isArray(value)) return value.length ? value.map(formatMarketText).filter(Boolean).join(" / ") : "暂无";
    if (typeof value === "object") {
      const obj = value as Record<string, unknown>;
      const parts = [obj.value, obj.level, obj.label, obj.name, obj.keyword, obj.asin, obj.risk, obj.slot, obj.pain_point]
        .map((item) => String(item || "").trim())
        .filter(Boolean);
      return parts.length ? parts.join(" / ") : "暂无";
    }
    return String(value);
  };
  const formatSignalText = (value: unknown) => {
    const text = formatMarketText(value);
    const map: Record<string, string> = {
      high: "高",
      medium: "中",
      low: "低",
      true: "是",
      false: "否",
    };
    return map[text] || text;
  };
  const formatMarketList = (value: unknown) => {
    const rows = Array.isArray(value) ? value : value ? [value] : [];
    return rows.map(formatMarketText).filter((text) => text && text !== "暂无").join(" / ") || "暂无";
  };
  const selectionFrontendEvidence = (selectionMarketResearch?.frontend_evidence || {}) as Record<string, any>;
  const selectionPriceBand = (selectionFrontendEvidence.price_band || {}) as Record<string, any>;
  const selectionReviewBarrier = (selectionFrontendEvidence.review_barrier || {}) as Record<string, any>;
  const selectionAdDensity = (selectionFrontendEvidence.ad_density || {}) as Record<string, any>;
  const selectionBrandConcentration = (selectionFrontendEvidence.brand_concentration || {}) as Record<string, any>;
  const selectionIntentPurity = (selectionFrontendEvidence.intent_purity || {}) as Record<string, any>;
  const selectionInferredSignals = (selectionMarketResearch?.inferred_market_signals || {}) as Record<string, any>;
  const selectionKeywordExpansion = (selectionMarketResearch?.keyword_expansion || {}) as Record<string, any>;
  const selectionEntryAssumptions = (selectionMarketResearch?.profit_and_entry_assumptions || {}) as Record<string, any>;
  const selectionEvidenceRows = [
    ["样本数", selectionFrontendEvidence.sample_count ?? selectionMarketResearch?.item_count],
    ["Top ASIN", formatMarketList(selectionFrontendEvidence.top_sample_asins)],
    [
      "价格带",
      [
        selectionPriceBand.min ? `最低${formatMarketPrice(selectionPriceBand.min)}` : "",
        selectionPriceBand.median ? `中位${formatMarketPrice(selectionPriceBand.median)}` : "",
        selectionPriceBand.max ? `最高${formatMarketPrice(selectionPriceBand.max)}` : "",
        selectionPriceBand.dominant_band,
      ].filter(Boolean).join(" / ") || "暂无",
    ],
    [
      "评论壁垒",
      [
        selectionReviewBarrier.median_reviews ? `中位${formatMarketCount(selectionReviewBarrier.median_reviews)}` : "",
        selectionReviewBarrier.top_review_threshold ? `头部${formatMarketCount(selectionReviewBarrier.top_review_threshold)}` : "",
        selectionReviewBarrier.new_low_review_opportunities ? `低评机会${selectionReviewBarrier.new_low_review_opportunities}` : "",
      ].filter(Boolean).join(" / ") || "暂无",
    ],
    [
      "广告密度",
      [
        selectionAdDensity.sponsored_count !== undefined ? `广告${selectionAdDensity.sponsored_count}` : "",
        selectionAdDensity.sponsored_ratio,
        selectionAdDensity.top_of_search_sponsored,
      ].filter(Boolean).join(" / ") || "暂无",
    ],
    [
      "品牌集中",
      [
        selectionBrandConcentration.concentration_level,
        formatMarketList(selectionBrandConcentration.top_brands),
      ].filter((text) => text && text !== "暂无").join(" / ") || "暂无",
    ],
    ["搜索意图", [selectionIntentPurity.level, selectionIntentPurity.basis].filter(Boolean).join(" / ") || "暂无"],
    ["差异化空位", formatMarketList(selectionFrontendEvidence.differentiation_slots)],
    ["差评痛点", formatMarketList(selectionFrontendEvidence.visible_complaint_pain_points)],
    ["敏感风险", formatMarketList(selectionFrontendEvidence.compliance_sensitivity)],
  ];
  const selectionSignalRows = [
    ["搜索量", selectionInferredSignals.search_volume],
    ["趋势", selectionInferredSignals.trend],
    ["季节性", selectionInferredSignals.seasonality],
    ["CPC", selectionInferredSignals.cpc],
    ["点击集中", selectionInferredSignals.click_concentration],
    ["销售强度", selectionInferredSignals.sales_strength],
  ];
  const selectionExpansionRows = [
    ["主词", selectionKeywordExpansion.main_terms],
    ["场景词", selectionKeywordExpansion.scenario_terms],
    ["问题词", selectionKeywordExpansion.problem_terms],
    ["长尾词", selectionKeywordExpansion.long_tail_terms],
    ["低竞争入口", selectionKeywordExpansion.lower_competition_entries],
  ];
  const selectionEntryRows = [
    ["利润压力", selectionEntryAssumptions.margin_pressure],
    ["供应链难度", selectionEntryAssumptions.supply_chain_difficulty],
    ["进入门槛", selectionEntryAssumptions.entry_barrier],
    ["广告可测性", selectionEntryAssumptions.ad_testability],
  ];
  const compactEvidenceParts = (...parts: unknown[]) => {
    const seen = new Set<string>();
    return parts
      .flatMap((part) => Array.isArray(part) ? part : [part])
      .map((part) => String(part || "").trim())
      .filter((part) => part && part !== "暂无" && part !== "待录入")
      .filter((part) => {
        if (seen.has(part)) return false;
        seen.add(part);
        return true;
      })
      .slice(0, 6)
      .join("；") || "暂无";
  };
  const marketSampleCount = Number(selectionFrontendEvidence.sample_count ?? selectionMarketResearch?.item_count ?? selectionMarketSampleRows.length) || 0;
  const priceSpreadRatio =
    Number(selectionPriceBand.min) > 0 && Number(selectionPriceBand.max) > 0 && Number(selectionPriceBand.median) > 0
      ? (Number(selectionPriceBand.max) - Number(selectionPriceBand.min)) / Number(selectionPriceBand.median)
      : 0;
  const laneKeywordSummary = selectionLaneRows.slice(0, 4).map((row: any) =>
    `${row.keyword}：Top40 ${row.top40Count ?? row.count ?? "暂无"}，广告${row.sponsoredCount ?? "暂无"}`
  );
  const topAsinSummary = selectionMarketSampleRows
    .slice(0, 4)
    .map((row: any) => `${row.asin} Rank${row.rank} 评论${formatMarketCount(row.reviews)} 价${formatMarketPrice(row.price)}`);
  const lowReviewTopSamples = selectionMarketSampleRows
    .filter((row: any) => Number(row.rank || 999) <= 40 && Number(String(row.reviews || "").replace(/,/g, "")) > 0 && Number(String(row.reviews || "").replace(/,/g, "")) <= 500)
    .slice(0, 4)
    .map((row: any) => `${row.asin} Rank${row.rank} 评论${formatMarketCount(row.reviews)}`);
  const priceBandEvidence = compactEvidenceParts(
    selectionPriceBand.min ? `最低${formatMarketPrice(selectionPriceBand.min)}` : "",
    selectionPriceBand.median ? `中位${formatMarketPrice(selectionPriceBand.median)}` : "",
    selectionPriceBand.max ? `最高${formatMarketPrice(selectionPriceBand.max)}` : "",
    selectionPriceBand.dominant_band
  );
  const reviewBarrierEvidence = compactEvidenceParts(
    selectionReviewBarrier.median_reviews ? `评论中位${formatMarketCount(selectionReviewBarrier.median_reviews)}` : "",
    selectionReviewBarrier.top_review_threshold ? `头部评论${formatMarketCount(selectionReviewBarrier.top_review_threshold)}` : "",
    selectionReviewBarrier.new_low_review_opportunities ? `低评机会${selectionReviewBarrier.new_low_review_opportunities}` : "",
    lowReviewTopSamples.length ? `低评Top样本：${lowReviewTopSamples.join(" / ")}` : ""
  );
  const adDensityEvidence = compactEvidenceParts(
    selectionAdDensity.sponsored_count !== undefined ? `广告样本${selectionAdDensity.sponsored_count}` : "",
    selectionAdDensity.sponsored_ratio ? `广告占比${selectionAdDensity.sponsored_ratio}` : "",
    selectionAdDensity.top_of_search_sponsored ? `顶部广告${selectionAdDensity.top_of_search_sponsored}` : ""
  );
  const headConcentrated = marketSampleCount >= 40 && lowReviewTopSamples.length === 0 && Number(selectionReviewBarrier.median_reviews || 0) >= 1000;
  const priceConcentrated = priceSpreadRatio > 0 && priceSpreadRatio <= 0.25;
  const normalizeDecisionStatus = (value: unknown) => {
    const text = String(value || "").trim();
    if (!text || text === "待录入") return "";
    if (text.includes("可验证") || text.includes("可进入")) return "可判断";
    if (text.includes("需补") || text.includes("待补") || text.includes("不足")) return "数据不足";
    if (text.includes("暂缓") || text.includes("放弃") || text.includes("不进入")) return "暂不判断";
    return text;
  };
  const statusByEvidence = (point: string, score: number, fallback?: unknown) => {
    const existing = normalizeDecisionStatus(fallback);
    if (existing && existing !== "待录入") return existing;
    if (!marketSampleCount && selectionMarketSampleRows.length === 0) return "数据不足";
    if (point.includes("竞争")) return headConcentrated ? "暂不判断" : lowReviewTopSamples.length ? "可判断" : marketSampleCount >= 40 ? "可判断" : "数据不足";
    if (point.includes("搜索")) return marketSampleCount >= 40 ? "可判断" : "数据不足";
    if (point.includes("商业")) return priceConcentrated ? "暂不判断" : priceBandEvidence !== "暂无" ? "可判断" : "数据不足";
    if (point.includes("风险")) return selectionMarketSampleRows.length || selectionFrontendEvidence.compliance_sensitivity ? "可判断" : "数据不足";
    if (point.includes("进入")) return headConcentrated && priceConcentrated ? "暂不判断" : marketSampleCount >= 40 ? "可判断" : "数据不足";
    return score >= 72 ? "可判断" : score >= 58 ? "数据不足" : "暂不判断";
  };
  const evidenceByDecisionPoint = (point: string, fallback?: unknown) => {
    const existing = String(fallback || "").trim();
    if (point.includes("真实需求")) {
      return compactEvidenceParts(
        marketSampleCount ? `总样本${marketSampleCount}` : "",
        laneKeywordSummary,
        topAsinSummary,
        existing
      );
    }
    if (point.includes("买家")) {
      return compactEvidenceParts(
        selectionIntentPurity.level ? `搜索意图${selectionIntentPurity.level}` : "",
        selectionIntentPurity.basis,
        laneKeywordSummary,
        existing
      );
    }
    if (point.includes("搜索")) {
      return compactEvidenceParts(
        laneKeywordSummary,
        adDensityEvidence,
        selectionInferredSignals.search_volume ? `搜索量${formatMarketText(selectionInferredSignals.search_volume)}` : "",
        existing
      );
    }
    if (point.includes("竞争")) {
      return compactEvidenceParts(
        reviewBarrierEvidence,
        topAsinSummary,
        existing
      );
    }
    if (point.includes("差异")) {
      return compactEvidenceParts(
        formatMarketList(selectionFrontendEvidence.differentiation_slots),
        (selectionMarketResearch?.route_summary || []).slice(0, 4).map((route: any) =>
          `${route.route || "待录入"} 样本${route.count ?? "暂无"}`
        ),
        existing
      );
    }
    if (point.includes("商业")) {
      return compactEvidenceParts(
        priceBandEvidence,
        selectionEntryAssumptions.margin_pressure ? `利润压力${formatMarketText(selectionEntryAssumptions.margin_pressure)}` : "",
        selectionEntryAssumptions.ad_testability ? `广告可测性${formatMarketText(selectionEntryAssumptions.ad_testability)}` : "",
        existing
      );
    }
    if (point.includes("风险")) {
      return compactEvidenceParts(
        formatMarketList(selectionFrontendEvidence.compliance_sensitivity),
        formatMarketList(selectionFrontendEvidence.visible_complaint_pain_points),
        selectionInferredSignals.trend ? `趋势${formatMarketText(selectionInferredSignals.trend)}` : "",
        existing
      );
    }
    if (point.includes("进入")) {
      return compactEvidenceParts(
        `机会评分${formatSelectionScore(selectionResult?.score)}`,
        reviewBarrierEvidence,
        priceBandEvidence,
        existing
      );
    }
    return existing || "暂无";
  };
  const derivedSelectionDecisionRows = (() => {
    const routeNames = Array.from(
      new Set((selectionMarketResearch?.route_summary || []).map((route: any) => String(route?.route || "").trim()).filter(Boolean))
    ).slice(0, 4);
    const recommendedBands = Array.from(
      new Set(selectionLaneRows.map((row: any) => String(row.priceBand || "").trim()).filter((text) => text && text !== "暂无"))
    ).slice(0, 3);
    const laneHeadlines = Array.from(
      new Set(selectionLaneRows.map((row: any) => String(row.headline || "").trim()).filter((text) => text && text !== "暂无"))
    ).slice(0, 3);
    const scoreOf = (title: string) => Number(selectionSixDEvidence.find((item: any) => String(item.title || "").includes(title))?.score || 0);
    const statusOf = (point: string, score: number) => statusByEvidence(point, score);
    return [
      {
        point: "真实需求",
        status: statusOf("真实需求", scoreOf("需求")),
        basis: evidenceByDecisionPoint("真实需求"),
        opinion: scoreOf("需求") >= 70 ? "可进入判断。" : "先确认需求稳定性。",
      },
      {
        point: "买家意图",
        status: statusByEvidence("买家意图", 0, marketSampleCount >= 40 ? "可判断" : "数据不足"),
        basis: evidenceByDecisionPoint("买家意图"),
        opinion: "按主词、形态词、场景词拆开判断。",
      },
      {
        point: "搜索入口",
        status: statusOf("搜索入口", scoreOf("搜索")),
        basis: evidenceByDecisionPoint("搜索入口"),
        opinion: scoreOf("搜索") >= 60 ? "优先验证长尾词和细分场景词。" : "先找更窄关键词。",
      },
      {
        point: "竞争结构",
        status: statusOf("竞争结构", scoreOf("竞争")),
        basis: evidenceByDecisionPoint("竞争结构"),
        opinion: scoreOf("竞争") >= 70 ? "围绕弱竞争样本拆打法。" : "避免直接正面打主词。",
      },
      {
        point: "差异化机会",
        status: statusOf("差异化机会", scoreOf("差异")),
        basis: evidenceByDecisionPoint("差异化机会", routeNames.join("、")),
        opinion: routeNames.length ? "从产品形态、场景或痛点表达找差异化。" : "继续拆评论和场景。",
      },
      {
        point: "商业承受力",
        status: statusOf("商业承受力", scoreOf("商业")),
        basis: evidenceByDecisionPoint("商业承受力", recommendedBands.join("、")),
        opinion: "核算成本、广告承受力、退货和仓储压力。",
      },
      {
        point: "风险判断",
        status: statusOf("风险判断", scoreOf("风险")),
        basis: evidenceByDecisionPoint("风险判断", laneHeadlines.join("；")),
        opinion: "复查趋势、合规、侵权、差评痛点和售后风险。",
      },
      {
        point: "进入方式",
        status: statusOf("进入方式", Number(selectionResult?.score || 0)),
        basis: evidenceByDecisionPoint("进入方式"),
        opinion: selectionResult?.next_step?.module || selectionSixDResult?.decision || "待录入",
      },
    ];
  })();
  const canRenderSelectionJudgment = !selectionRequiresKeywordSamples || selectionHasRequiredSamples;
  const rawSelectionDecisionRows = !canRenderSelectionJudgment
    ? []
    : Array.isArray(selectionResult?.selection_decision_points) && selectionResult.selection_decision_points.length
      ? selectionResult.selection_decision_points
      : Array.isArray(selectionMarketResearch?.decision_points) && selectionMarketResearch.decision_points.length
        ? selectionMarketResearch.decision_points
        : derivedSelectionDecisionRows;
  const selectionDecisionRows = rawSelectionDecisionRows.map((row: any) => {
    const point = String(row?.point || "待录入");
    const score = Number(row?.score || selectionResult?.score || 0);
    return {
      ...row,
      point,
      status: statusByEvidence(point, score, row?.status),
      basis: evidenceByDecisionPoint(point, row?.basis),
      opinion: row?.opinion || "暂无",
    };
  });
  const selectionOperatorConclusion = (selectionResult?.operator_conclusion || {}) as Record<string, any>;
  const selectionConclusionResult = String(
    selectionOperatorConclusion.result ||
      selectionResult?.decision ||
      selectionResult?.next_step?.module ||
      (selectionHasRequiredSamples ? "待录入" : "数据不足")
  );
  const selectionConclusionBasis = toSelectionTextList(selectionOperatorConclusion.basis);
  const selectionConclusionObservations = toSelectionTextList(selectionOperatorConclusion.observations);
  const selectionConclusionActions = toSelectionTextList(selectionOperatorConclusion.actions);
  const selectionConclusionValidation = toSelectionTextList(selectionOperatorConclusion.validation);
  const getDecisionStatusClass = (status: unknown) => {
    const text = String(status || "");
    if (text.includes("放弃") || text.includes("暂不") || text.includes("不进入")) return "border-red-200 bg-red-50 text-red-700";
    if (text.includes("观察") || text.includes("需补") || text.includes("待补") || text.includes("不足")) return "border-amber-200 bg-amber-50 text-amber-700";
    if (text.includes("可验证") || text.includes("验证") || text.includes("可进入") || text.includes("判断")) return "border-emerald-200 bg-emerald-50 text-emerald-700";
    return "border-border bg-background text-muted-foreground";
  };
  const getSixDimensionAnalysis = (item: any) => {
    const title = String(item?.title || "");
    const score = Number(item?.score || 0);
    if (item?.basis || item?.opinion) {
      return {
        basis: item.basis || item.detail || "暂无",
        opinion: item.opinion || "暂无",
      };
    }
    const routeNames = Array.from(
      new Set((selectionMarketResearch?.route_summary || []).map((route: any) => String(route?.route || "").trim()).filter(Boolean))
    ).slice(0, 4);
    const laneHeadlines = Array.from(
      new Set(selectionLaneRows.map((row: any) => String(row.headline || "").trim()).filter((text) => text && text !== "暂无"))
    ).slice(0, 3);
    const recommendedBands = Array.from(
      new Set(selectionLaneRows.map((row: any) => String(row.priceBand || "").trim()).filter((text) => text && text !== "暂无"))
    ).slice(0, 3);
    const scoreTone = score >= 75 ? "强" : score >= 60 ? "中等" : "偏弱";
    const highScoreOpinion = score >= 70 ? "可以继续进入验证。" : score >= 55 ? "需要补充验证后再决定。" : "暂不适合直接进入。";

    if (title.includes("需求")) {
      return {
        basis: score >= 70 ? "搜索结果能形成稳定商品池，买家需求已经被市场验证。" : "搜索结果有商品承接，但需求强度还需要继续确认。",
        opinion: `需求判断${scoreTone}，${highScoreOpinion}`,
      };
    }
    if (title.includes("搜索")) {
      return {
        basis: score >= 60 ? "自然搜索入口仍有观察空间，广告位没有完全压住判断。" : "搜索入口压力偏高，需要先确认自然排名能否进入。",
        opinion: score >= 60 ? "优先验证长尾词和细分场景词。" : "先不要直接打主词，先找更窄的入口。",
      };
    }
    if (title.includes("竞争")) {
      return {
        basis: score >= 70 ? "搜索结果里存在可观察的低评论排名样本。" : "头部商品门槛偏高，新品直接正面竞争压力大。",
        opinion: score >= 70 ? "可以围绕低评论高排名样本拆打法。" : "需要避开头部红海词，先找弱竞争切口。",
      };
    }
    if (title.includes("差异")) {
      return {
        basis: routeNames.length ? `搜索结果出现${routeNames.join("、")}等路线。` : "搜索结果的产品路线暂未形成清晰分层。",
        opinion: score >= 70 ? "可以从产品形态、场景或技术路线里找差异化。" : "差异化证据不足，需要继续拆痛点和场景。",
      };
    }
    if (title.includes("商业")) {
      return {
        basis: recommendedBands.length ? `主要观察价格带：${recommendedBands.join("、")}。` : "价格带承接还需要继续确认。",
        opinion: score >= 70 ? "进入前重点核算成本、广告承受力和利润空间。" : "先算清成本和获客压力，再决定是否进入。",
      };
    }
    if (title.includes("风险")) {
      return {
        basis: laneHeadlines.length ? laneHeadlines.join("；") : "当前仍需复查趋势、合规和差评痛点。",
        opinion: score >= 65 ? "风险可继续验证，不建议跳过复查。" : "风险项偏多，先做小样本验证。",
      };
    }
    return {
      basis: "暂无",
      opinion: "暂无",
    };
  };
  return (
    <div className="flex h-screen bg-[#f5f5f7] text-foreground">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto bg-[#f5f5f7]">
        <div className="p-4 sm:p-6 w-full max-w-none pt-14 md:pt-6">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 sm:mb-8 gap-3">
            <div>
              <h1 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
                <Package className="w-6 h-6 text-brand-600" />
                卖什么？选错品，后面全错
              </h1>
              <p className="text-muted-foreground mt-1 text-sm">关键词调研</p>
            </div>
          </div>

          {/* Auto Import Panel */}
          {showAutoImport && !showForm && (
            <Card id="asin-opportunity-entry" className="mb-6 rounded-3xl border-border/70 bg-white/90 p-5 shadow-[0_18px_50px_rgba(15,23,42,0.06)]">
              {(
                <div className="space-y-3">
                    <div className="rounded-2xl border border-border bg-white p-4">
                      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex items-center gap-3">
                          <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
                            <Sparkles className="h-4 w-4" />
                          </span>
                          <h2 className="text-base font-semibold text-gray-950">关键词调研</h2>
                        </div>
                        <MarketplaceSelect
                          value={autoImportMarketplace}
                          onChange={setAutoImportMarketplace}
                          triggerClassName="h-11 w-full rounded-xl border-border bg-background sm:max-w-[180px]"
                        />
                      </div>
                      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_auto] xl:items-end">
                        <div>
                          <Label className="text-xs font-medium text-muted-foreground">关键词</Label>
                          <Input
                            value={opportunityKeyword}
                            onChange={(e) => setOpportunityKeyword(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && !autoImportLoading && !selectionAnalyzing)
                                handleSingleAutoImportAndValidate();
                            }}
                            placeholder="请输入英文关键词"
                            className="mt-1 h-11 rounded-xl border-border bg-background text-foreground shadow-none"
                          />
                        </div>
                        <Button
                          onClick={handleSingleAutoImportAndValidate}
                          disabled={autoImportLoading || selectionAnalyzing || !opportunityKeyword.trim()}
                          className="h-11 rounded-xl bg-gray-950 px-5 text-white hover:bg-brand-700"
                        >
                          {autoImportLoading || selectionAnalyzing ? (
                            <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                          ) : (
                            <Sparkles className="w-4 h-4 mr-1" />
                          )}
                          {autoImportLoading || selectionAnalyzing ? "分析中..." : "选品判断AI分析"}
                        </Button>
                      </div>
                      <div className="mt-3 flex flex-col gap-3 rounded-2xl bg-background px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                        <label className="flex cursor-pointer items-center gap-2 text-sm text-brand-500">
                          <input
                            type="checkbox"
                            checked={autoFetch}
                            onChange={(e) => setAutoFetch(e.target.checked)}
                            className="h-4 w-4 rounded border-border text-foreground focus:ring-gray-900"
                          />
                          自动保存到选品历史
                        </label>
                        <p className="text-xs text-muted-foreground">机会评分 / 风险评分 / 进入或放弃建议</p>
                      </div>
                    </div>
                {(autoImportLoading || batchImportLoading || selectionAnalyzing) && (
                  <div className="rounded-lg border border-amber-100 bg-gold-50 px-3 py-3">
                    <div className="flex items-center justify-between gap-3 text-xs text-amber-700">
                      <span className="flex items-center gap-1.5">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        {autoImportMessage || "抓取中"}
                        {batchImportCurrent ? ` · 当前 ${batchImportCurrent}` : ""}
                      </span>
                      <span className="shrink-0">{analysisSourceLabel}</span>
                    </div>
                    {autoImportSubMessage && (
                      <div className="mt-1 text-[11px] text-brand-500">{autoImportSubMessage}</div>
                    )}
                    <div className="mt-2 h-2 overflow-hidden rounded-full bg-white">
                      <div
                        className="h-full rounded-full bg-amber-600 transition-all duration-500"
                        style={{ width: `${autoImportProgress}%` }}
                      />
                    </div>
                    <div className="mt-2 flex items-center justify-between text-[11px] text-brand-500">
                      <span>{Math.round(autoImportProgress)}%</span>
                      <span>{autoImportElapsed}s</span>
                    </div>
                  </div>
                )}
                {selectionSummary && (
                  <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-800">
                    {selectionSummary}
                  </div>
                )}
                {selectionResult && (
                  <div id="asin-opportunity-result" className="space-y-3">
                    <Card className="border-emerald-100 bg-white p-4">
	                      <div className="mb-3 flex items-start gap-3">
	                        <div>
	                          <div className="flex items-center gap-2">
	                            <ShieldCheck className="w-4 h-4 text-emerald-700" />
	                            <h3 className="font-bold text-foreground">市场机会判断</h3>
	                          </div>
	                        </div>
	                      </div>
                      <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-3">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <p className="text-sm font-semibold text-foreground">经营结论</p>
                          <span className={`inline-flex w-fit rounded-full border px-3 py-1 text-xs font-semibold ${getDecisionStatusClass(selectionConclusionResult)}`}>
                            {selectionConclusionResult || "暂无"}
                          </span>
                        </div>
                        <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-4">
                          <div className="rounded-lg border border-emerald-100 bg-white p-3">
                            <p className="text-xs font-semibold text-foreground">为什么</p>
                            <div className="mt-2 space-y-1 text-xs leading-relaxed text-muted-foreground">
                              {selectionConclusionBasis.length ? (
                                selectionConclusionBasis.map((item, index) => <p key={`basis-${index}`}>{item}</p>)
                              ) : (
                                <p>暂无</p>
                              )}
                            </div>
                          </div>
                          <div className="rounded-lg border border-emerald-100 bg-white p-3">
                            <p className="text-xs font-semibold text-foreground">观察</p>
                            <div className="mt-2 space-y-1 text-xs leading-relaxed text-muted-foreground">
                              {selectionConclusionObservations.length ? (
                                selectionConclusionObservations.map((item, index) => <p key={`observation-${index}`}>{item}</p>)
                              ) : (
                                <p>暂无</p>
                              )}
                            </div>
                          </div>
                          <div className="rounded-lg border border-emerald-100 bg-white p-3">
                            <p className="text-xs font-semibold text-foreground">动作</p>
                            <div className="mt-2 space-y-1 text-xs leading-relaxed text-muted-foreground">
                              {selectionConclusionActions.length ? (
                                selectionConclusionActions.map((item, index) => <p key={`action-${index}`}>{item}</p>)
                              ) : (
                                <p>暂无</p>
                              )}
                            </div>
                          </div>
                          <div className="rounded-lg border border-emerald-100 bg-white p-3">
                            <p className="text-xs font-semibold text-foreground">验证</p>
                            <div className="mt-2 space-y-1 text-xs leading-relaxed text-muted-foreground">
                              {selectionConclusionValidation.length ? (
                                selectionConclusionValidation.map((item, index) => <p key={`validation-${index}`}>{item}</p>)
                              ) : (
                                <p>暂无</p>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
                        <div className="rounded-lg border border-border bg-background p-3">
                          <p className="text-xs text-muted-foreground">机会评分</p>
                          <p className="mt-1 text-sm font-bold text-foreground">{formatSelectionScore(selectionResult.score)}</p>
                        </div>
                        <div className="rounded-lg border border-border bg-background p-3">
                          <p className="text-xs text-muted-foreground">风险评分</p>
                          <p className="mt-1 text-sm font-bold text-foreground">{selectionResult.risk_level || "待录入"}</p>
                        </div>
                        <div className="rounded-lg border border-border bg-background p-3">
                          <p className="text-xs text-muted-foreground">进入/放弃建议</p>
                          <p className="mt-1 text-sm font-bold text-foreground">{selectionResult.next_step?.module || "待录入"}</p>
                        </div>
                      </div>
	                      {selectionSixDResult && (
	                        <div className="mt-3 rounded-lg border border-border bg-background p-3">
	                          <p className="mb-2 text-sm font-semibold text-foreground">判断依据</p>
	                          <div className="grid grid-cols-1 gap-3 lg:grid-cols-[300px_1fr]">
	                            <div className="rounded-lg border border-border/70 bg-white p-3">
	                              <p className="mb-2 text-sm font-semibold text-foreground">6维评分图形</p>
	                              <RadarChart scores={selectionRadarScores} />
	                            </div>
                          <div className="rounded-lg border border-border/70 bg-white p-3">
                            <p className="mb-2 text-sm font-semibold text-foreground">6维诊断</p>
                            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                              {selectionSixDEvidence.length > 0 ? (
                                selectionSixDEvidence.map((item, index) => {
                                  const dimensionAnalysis = getSixDimensionAnalysis(item);
                                  return (
                                    <div key={`${item.title}-${index}`} className="rounded-lg border border-border/70 bg-background p-2">
                                      <div className="mb-1 flex items-center justify-between gap-2">
                                        <span className="text-xs font-semibold text-foreground">{item.title}</span>
                                        <span className="text-xs font-bold text-brand-600">
                                          {Number(item.score || 0) ? `${Math.round(Number(item.score || 0))}/100` : "待录入"}
                                        </span>
                                      </div>
                                      <div className="mb-2 h-1.5 overflow-hidden rounded-full bg-gray-100">
                                        <div
                                          className="h-full rounded-full bg-brand-500"
                                          style={{ width: `${Math.max(0, Math.min(100, Number(item.score || 0)))}%` }}
                                        />
                                      </div>
                                      <div className="space-y-1 text-xs leading-relaxed text-muted-foreground">
                                        <p>
                                          <span className="font-semibold text-foreground">依据：</span>
                                          {dimensionAnalysis.basis}
                                        </p>
                                        <p>
                                          <span className="font-semibold text-foreground">意见：</span>
                                          {dimensionAnalysis.opinion}
                                        </p>
                                      </div>
                                    </div>
                                  );
                                })
                              ) : (
                                <p className="text-xs text-muted-foreground">暂无</p>
                              )}
	                            </div>
	                          </div>
	                        </div>
	                        </div>
	                      )}
                      {selectionMarketResearch && (
                        <div className="mt-3 space-y-3">
                          <div className="grid grid-cols-1 gap-3">
                            <div className="rounded-lg border border-border bg-background p-3">
                              <p className="mb-2 text-sm font-semibold text-foreground">市场路线</p>
                              <div className="space-y-1.5">
                                {(selectionMarketResearch.route_summary || []).length > 0 ? (
                                  selectionMarketResearch.route_summary.map((route: any, index: number) => (
                                    <div key={`${route.route}-${index}`} className="grid grid-cols-[1fr_52px_78px_78px] gap-2 text-xs text-muted-foreground">
                                      <span className="truncate font-medium text-foreground">{route.route || "待录入"}</span>
                                      <span>{route.count ?? "暂无"}</span>
                                      <span>{formatMarketPrice(route.medianPrice)}</span>
                                      <span>{formatMarketCount(route.medianReviews)}</span>
                                    </div>
                                  ))
                                ) : (
                                  <p className="text-xs text-muted-foreground">暂无</p>
                                )}
                              </div>
                            </div>
                          </div>

                          <div className="rounded-lg border border-border bg-background p-3">
                            <p className="mb-2 text-sm font-semibold text-foreground">前台证据</p>
                            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                              {selectionEvidenceRows.map(([label, value]) => (
                                <div key={String(label)} className="rounded-lg border border-border/70 bg-white p-2">
                                  <p className="text-[11px] font-medium text-muted-foreground">{label}</p>
                                  <p className="mt-1 text-xs font-semibold leading-5 text-foreground">{formatMarketText(value)}</p>
                                </div>
                              ))}
                            </div>
                          </div>

                          <div className="rounded-lg border border-border bg-background p-3">
                            <p className="mb-2 text-sm font-semibold text-foreground">推断信号</p>
                            <div className="overflow-x-auto">
                              <table className="w-full min-w-[760px] text-left text-xs">
                                <thead className="text-muted-foreground">
                                  <tr className="border-b border-border">
                                    <th className="py-2 pr-3 font-medium">判断项</th>
                                    <th className="py-2 pr-3 font-medium">判断</th>
                                    <th className="py-2 pr-3 font-medium">判断依据</th>
                                    <th className="py-2 pr-3 font-medium">证据强度</th>
                                    <th className="py-2 font-medium">是否需验证</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {selectionSignalRows.map(([label, signal]) => {
                                    const row = (signal || {}) as Record<string, any>;
                                    return (
                                      <tr key={String(label)} className="border-b border-border/60 last:border-0">
                                        <td className="py-2 pr-3 font-medium text-foreground">{label}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{formatSignalText(row.value)}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{formatMarketText(row.basis)}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{formatSignalText(row.confidence)}</td>
                                        <td className="py-2 text-muted-foreground">{row.needs_validation === false ? "否" : "是"}</td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                          </div>

                          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                            <div className="rounded-lg border border-border bg-background p-3">
                              <p className="mb-2 text-sm font-semibold text-foreground">关键词扩展</p>
                              <div className="space-y-2">
                                {selectionExpansionRows.map(([label, value]) => (
                                  <div key={String(label)} className="grid grid-cols-[88px_1fr] gap-2 text-xs">
                                    <span className="font-medium text-foreground">{label}</span>
                                    <span className="text-muted-foreground">{formatMarketList(value)}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                            <div className="rounded-lg border border-border bg-background p-3">
                              <p className="mb-2 text-sm font-semibold text-foreground">进入假设</p>
                              <div className="space-y-2">
                                {selectionEntryRows.map(([label, value]) => {
                                  const row = (value || {}) as Record<string, any>;
                                  return (
                                    <div key={String(label)} className="rounded-lg border border-border/70 bg-white p-2 text-xs">
                                      <div className="flex items-center justify-between gap-2">
                                        <span className="font-medium text-foreground">{label}</span>
                                        <span className="text-muted-foreground">{formatMarketText(row.level)}</span>
                                      </div>
                                      <p className="mt-1 leading-5 text-muted-foreground">{formatMarketText(row.basis)}</p>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          </div>

                          <div className="rounded-lg border border-border bg-background p-3">
                            <p className="mb-2 text-sm font-semibold text-foreground">搜索词判断</p>
                            {selectionLaneRows.length > 0 ? (
                              <div className="overflow-x-auto">
                                <table className="w-full min-w-[760px] text-left text-xs">
                                  <thead className="text-muted-foreground">
                                    <tr className="border-b border-border">
                                      <th className="py-2 pr-3 font-medium">搜索词</th>
                                      <th className="py-2 pr-3 font-medium">样本</th>
                                      <th className="py-2 pr-3 font-medium">Top40</th>
                                      <th className="py-2 pr-3 font-medium">价格中位数</th>
                                      <th className="py-2 pr-3 font-medium">评论中位数</th>
                                      <th className="py-2 pr-3 font-medium">广告样本</th>
                                      <th className="py-2 pr-3 font-medium">价格带</th>
                                      <th className="py-2 font-medium">判断</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {selectionLaneRows.map((row: any, index: number) => (
                                      <tr key={`${row.keyword}-${index}`} className="border-b border-border/60 last:border-0">
                                        <td className="py-2 pr-3 font-medium text-foreground">{row.keyword}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{row.count ?? "暂无"}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{row.top40Count ?? row.count ?? "暂无"}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{formatMarketPrice(row.medianPrice)}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{formatMarketCount(row.medianReviews)}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{row.sponsoredCount ?? "暂无"}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{row.priceBand}</td>
                                        <td className="py-2 text-muted-foreground">{row.headline}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            ) : (
                              <p className="text-xs text-muted-foreground">暂无</p>
                            )}
                          </div>

                          <div className="rounded-lg border border-border bg-background p-3">
                            <p className="mb-2 text-sm font-semibold text-foreground">样本明细</p>
                            {selectionMarketSampleRows.length > 0 ? (
                              <div className="max-h-[420px] overflow-auto">
                                <table className="w-full min-w-[920px] text-left text-xs">
                                  <thead className="sticky top-0 bg-background text-muted-foreground">
                                    <tr className="border-b border-border">
                                      <th className="py-2 pr-3 font-medium">搜索词</th>
                                      <th className="py-2 pr-3 font-medium">排名</th>
                                      <th className="py-2 pr-3 font-medium">ASIN</th>
                                      <th className="py-2 pr-3 font-medium">标题</th>
                                      <th className="py-2 pr-3 font-medium">价格</th>
                                      <th className="py-2 pr-3 font-medium">评分</th>
                                      <th className="py-2 pr-3 font-medium">评论</th>
                                      <th className="py-2 pr-3 font-medium">标签</th>
                                      <th className="py-2 font-medium">来源</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {selectionMarketSampleRows.map((row: any, index: number) => (
                                      <tr key={`${row.keyword}-${row.rank}-${row.asin}-${index}`} className="border-b border-border/60 last:border-0">
                                        <td className="py-2 pr-3 text-muted-foreground">{row.keyword}</td>
                                        <td className="py-2 pr-3 font-medium text-foreground">{row.rank}</td>
                                        <td className="py-2 pr-3 font-mono text-[11px] text-foreground">{row.asin}</td>
                                        <td className="max-w-[360px] py-2 pr-3 text-muted-foreground">
                                          <span className="line-clamp-2">{row.title}</span>
                                        </td>
                                        <td className="py-2 pr-3 text-muted-foreground">{formatMarketPrice(row.price)}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{row.rating || "暂无"}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{formatMarketCount(row.reviews)}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{row.tag}</td>
                                        <td className="py-2 text-muted-foreground">{row.source}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            ) : (
                              <p className="text-xs text-muted-foreground">暂无</p>
                            )}
                          </div>

                          <div className="rounded-lg border border-border bg-background p-3">
                            <p className="mb-2 text-sm font-semibold text-foreground">数据来源</p>
                            <div className="space-y-1.5">
                              {(selectionMarketResearch.source_steps || []).length > 0 ? (
                                selectionMarketResearch.source_steps.map((step: any, index: number) => (
                                  <div key={`${step.step}-${index}`} className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                                    <span className="truncate">{step.step || "待录入"}</span>
                                    <span className="shrink-0">{cleanMarketSourceLabel(step.source)} · {step.count ?? "暂无"}</span>
                                  </div>
                                ))
                              ) : (
                                <p className="text-xs text-muted-foreground">暂无</p>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </Card>
                  </div>
                )}
                </div>
              )}

              <p className="text-[10px] text-brand-500 mt-3">
                系统会保存商品字段、评分和来源标记；低置信结果需复核后再进入机会池。
              </p>
            </Card>
          )}

          {/* Form */}
          {showForm && (
            <Card className="bg-white border-border p-4 sm:p-6 mb-6 sm:mb-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold">
                  {editingId ? "编辑产品" : "添加新产品"}
                </h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCancel}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label className="text-brand-500">ASIN *</Label>
                  <Input
                    value={form.asin}
                    onChange={(e) => setForm({ ...form, asin: e.target.value })}
                    placeholder="B0XXXXXXXXX"
                    className="bg-background border-border text-foreground mt-1"
                  />
                </div>
                <div>
                  <Label className="text-brand-500">类目</Label>
                  <Input
                    value={form.category}
                    onChange={(e) =>
                      setForm({ ...form, category: e.target.value })
                    }
                    placeholder="如：Electronics"
                    className="bg-background border-border text-foreground mt-1"
                  />
                </div>
                <div className="md:col-span-2">
                  <Label className="text-brand-500">产品标题 *</Label>
                  <Input
                    value={form.title}
                    onChange={(e) =>
                      setForm({ ...form, title: e.target.value })
                    }
                    placeholder="输入产品标题"
                    className="bg-background border-border text-foreground mt-1"
                  />
                </div>
                <div className="md:col-span-2">
                  <Label className="text-brand-500">五点描述 (Bullet Points)</Label>
                  <Textarea
                    value={form.bullet_points}
                    onChange={(e) =>
                      setForm({ ...form, bullet_points: e.target.value })
                    }
                    placeholder="每行一个卖点"
                    rows={4}
                    className="bg-background border-border text-foreground mt-1"
                  />
                </div>
                <div className="md:col-span-2">
                  <Label className="text-brand-500">A+ 内容描述</Label>
                  <Textarea
                    value={form.a_plus_content}
                    onChange={(e) =>
                      setForm({ ...form, a_plus_content: e.target.value })
                    }
                    placeholder="描述A+页面内容"
                    rows={3}
                    className="bg-background border-border text-foreground mt-1"
                  />
                </div>
                <div className="md:col-span-2">
                  <Label className="text-brand-500">搜索关键词</Label>
                  <Textarea
                    value={form.search_keywords}
                    onChange={(e) =>
                      setForm({ ...form, search_keywords: e.target.value })
                    }
                    placeholder="关键词用逗号分隔"
                    rows={2}
                    className="bg-background border-border text-foreground mt-1"
                  />
                </div>
                <div>
                  <Label className="text-brand-500">价格 (USD)</Label>
                  <Input
                    type="number"
                    value={form.price}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        price: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="bg-background border-border text-foreground mt-1"
                  />
                </div>
                <div>
                  <Label className="text-brand-500">评价数量</Label>
                  <Input
                    type="number"
                    value={form.review_count}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        review_count: parseInt(e.target.value) || 0,
                      })
                    }
                    className="bg-background border-border text-foreground mt-1"
                  />
                </div>
                <div>
                  <Label className="text-brand-500">评分 (1-5)</Label>
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
                    className="bg-background border-border text-foreground mt-1"
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
                  className="text-muted-foreground hover:text-foreground"
                >
                  取消
                </Button>
              </div>
            </Card>
          )}

          {/* Search, Batch Actions, History Toggle */}
          {!showForm && (
            <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div />
              <div className="flex justify-end gap-2">
                {products.length > 0 && selectedIds.size > 0 && (
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
                  className="h-9 rounded-xl border-border bg-white text-brand-500 hover:bg-brand-50 hover:text-foreground"
                >
                  <History className="w-4 h-4 mr-1" /> 选品历史
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
            <Card className="bg-white border-border p-4 mb-4">
              <h3 className="text-sm font-semibold text-brand-500 mb-3 flex items-center gap-2">
                <History className="w-4 h-4 text-muted-foreground" /> 选品历史
              </h3>
              {historyLoading ? (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                </div>
              ) : selectionHistoryItems.length === 0 ? (
                <p className="text-xs text-brand-500 text-center py-4">
                  暂无选品历史
                </p>
              ) : (
                <div className="space-y-1.5 max-h-60 overflow-y-auto">
                  {selectionHistoryItems.map((item) => (
                    <div
                      key={item.id}
                      className="flex cursor-pointer items-center justify-between gap-3 px-3 py-2 rounded-lg bg-background border border-border text-xs hover:bg-brand-50"
                      onClick={() => loadSelectionHistoryItem(item)}
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                        <span className="truncate font-semibold text-brand-600">
                          {getSelectionHistoryTitle(item)}
                        </span>
                        <span className="shrink-0 text-brand-500">
                          {getSelectionHistoryType(item)}
                        </span>
                        {snapshotOutput(item).score !== undefined && (
                          <span className="shrink-0 rounded bg-emerald-50 px-2 py-0.5 text-emerald-700">
                            {formatSelectionScore(snapshotOutput(item).score)}
                          </span>
                        )}
                      </div>
                      <div className="flex shrink-0 items-center gap-3">
                        <span className="text-brand-500">
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
          {showForm && products.length > 0 && (
            <div className="flex items-center gap-4 mb-4 px-2">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Package className="w-3.5 h-3.5" />
              <span>共 {products.length} 个产品</span>
              </div>
              {poolCount > 0 && (
                <div className="flex items-center gap-1.5 text-xs text-emerald-600">
                  <Award className="w-3.5 h-3.5" />
                  <span>{poolCount} 个可继续验证</span>
                </div>
              )}
              {searchQuery && (
                <div className="text-xs text-muted-foreground">
                  匹配 {filteredProducts.length} 个
                </div>
              )}
            </div>
          )}

          {/* Product List */}
          {showForm && loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-20 bg-background rounded-xl animate-pulse"
                />
              ))}
            </div>
          ) : showForm && products.length === 0 ? (
            <Card className="bg-white border-border p-8 sm:p-12 text-center">
              <Package className="w-12 h-12 text-brand-500 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-brand-500 mb-2">
                ASIN库为空
              </h3>
              <p className="text-muted-foreground mb-6 text-sm">
                请在上方输入 ASIN 或 Amazon 商品链接，系统会自动抓取并保存到 ASIN 库。
              </p>
            </Card>
          ) : showForm && filteredProducts.length === 0 ? (
            <Card className="bg-white border-border p-8 text-center">
              <div className="text-center py-4 text-muted-foreground text-sm">
                没有找到匹配的产品
              </div>
            </Card>
          ) : showForm ? (
            <div className="space-y-2 sm:space-y-3">
              {filteredProducts.length > 0 && (
                <div className="flex items-center gap-2 px-2 text-xs text-muted-foreground">
                  <Checkbox
                    checked={
                      selectedIds.size === filteredProducts.length &&
                      filteredProducts.length > 0
                    }
                    onCheckedChange={toggleSelectAll}
                    className="border-border"
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
                const competitorListingReport = competitorListingReports[product.asin];
                const isCompetitorListingLoading = competitorListingLoadingAsin === product.asin;
                const isSelectionRowAnalyzing = selectionAnalyzingTarget === product.asin;
                const isDecisionBusy = isScoring || isKeywordValidating || isSelectionRowAnalyzing || isCompetitorListingLoading;
                const marketplace = getProductMarketplace(product);
                const marketplaceMeta = MARKETPLACE_BY_VALUE[marketplace] || MARKETPLACE_BY_VALUE.US;
                const v5Decision = keywordReport?.v5_market_decision;
                const opportunityLevel = v5Decision?.opportunity_level || "待录入";
                const competitorSummary = getCompetitorListingSummary(competitorListingReport, keywordReport);
                const competitorProductData = competitorListingReport?.product_data || {};
                const isCompetitorAsinAnalysis = Boolean(competitorListingReport || isCompetitorListingLoading);
                const showKeywordMarketOpportunity = Boolean(keywordReport && !isCompetitorAsinAnalysis);
                const hasDecisionHistory = Boolean(scoreResult || keywordReport || competitorListingReport);
                const levelTone =
                  opportunityLevel === "建议推进"
                    ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                    : opportunityLevel === "小预算验证"
                      ? "text-amber-700 bg-gold-50 border-amber-200"
                      : opportunityLevel === "建议放弃"
                        ? "text-red-700 bg-red-50 border-red-200"
                        : "text-brand-600 bg-background border-border";

                return (
                  <div key={product.id} className="space-y-0">
                    <Card
                      className="bg-white border-border p-3 sm:p-4 hover:border-border transition-colors"
                    >
                      <div className="flex items-start gap-3 sm:gap-4">
                        <Checkbox
                          checked={selectedIds.has(product.id)}
                          onCheckedChange={() => toggleSelect(product.id)}
                          className="border-border mt-2"
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
                              <span className="text-xs text-muted-foreground">
                                {product.category}
                              </span>
                            )}
                            <a
                              href={getAmazonProductUrl(product.asin, marketplace)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-brand-500 hover:text-brand-600 transition-colors"
                              title={`在 ${marketplaceMeta.label} 查看：${marketplaceMeta.domain}`}
                            >
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                          <p className="font-medium text-sm truncate">
                            {product.title}
                          </p>
                          <div className="flex items-center gap-3 sm:gap-4 mt-2 text-xs text-muted-foreground flex-wrap">
                            {product.price > 0 && (
                              <span className="text-emerald-600">
                                {marketplaceMeta.currency}
                                {product.price}
                              </span>
                            )}
                            {product.rating > 0 && (
                              <span className="flex items-center gap-1 text-gold-600">
                                <Star className="w-3 h-3" /> {product.rating}
                              </span>
                            )}
                            {product.review_count > 0 && (
                              <span>{product.review_count} 评价</span>
                            )}
                            {product.created_at && (
                              <span className="flex items-center gap-1 text-brand-500">
                                <Clock className="w-3 h-3" />
                                {new Date(product.created_at).toLocaleDateString(
                                  "zh-CN"
                                )}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex gap-1 sm:gap-2 flex-shrink-0 items-center">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={async () => {
                              const shouldCollapse = isExpanded || isKeywordExpanded;
                              if (shouldCollapse) {
                                setExpandedScoreAsin(null);
                                setExpandedKeywordAsin(null);
                                return;
                              }
                              setExpandedScoreAsin(scoreResult ? product.asin : null);
                              setExpandedKeywordAsin((keywordReport || competitorListingReport) ? product.asin : null);
                              if (hasDecisionHistory) return;
                              await runSelectionAgent(product, { source: "product_row" });
                              if (!keywordReport) await handleKeywordSalesValidation(product);
                              if (!competitorListingReport) await runCompetitorListingDiagnosis(product);
                              if (!scoreResult) await handleFiveDScore(product);
                            }}
                            disabled={isDecisionBusy}
                            className="h-8 border-brand-200 bg-brand-50 px-3 text-brand-800 hover:bg-brand-100"
                            title="查看机会判断与验证报告"
                          >
                            {isDecisionBusy ? (
                              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                            ) : (
                              <Award className="w-3.5 h-3.5 mr-1.5" />
                            )}
                            <span className="hidden sm:inline text-xs font-semibold mr-1.5">
                              {isExpanded || isKeywordExpanded ? "收起判断" : "选品判断分析"}
                            </span>
                            {scoreResult?.total_score !== undefined && (
                              <span className="rounded-md border border-amber-200 bg-gold-50 px-2 py-0.5 text-xs font-semibold text-amber-700">
                                {scoreResult.total_score}分
                              </span>
                            )}
                            {keywordReport && (
                              <span className="ml-1.5 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                                验证{Math.round(keywordReport.keyword_sales_score)}分
                              </span>
                            )}
                            {competitorListingReport && (
                              <span className="ml-1.5 rounded-md border border-brand-100 bg-brand-50 px-2 py-0.5 text-xs font-semibold text-brand-700">
                                承接{competitorSummary.score || "待录入"}
                              </span>
                            )}
                          </Button>
                          {keywordReport && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleKeywordSalesValidation(product)}
                              disabled={isKeywordValidating}
                              className="text-muted-foreground hover:text-emerald-700 h-8 px-2"
                              title="重新抓取并验证关键词销量"
                            >
                              {isKeywordValidating ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                              <span className="hidden sm:inline ml-1.5 text-xs font-semibold">重算验证</span>
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRefreshProduct(product)}
                            disabled={refreshingId === product.id}
                            className="text-muted-foreground hover:text-gold-600 h-8 w-8 p-0"
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
                            className="text-muted-foreground hover:text-brand-600 h-8 w-8 p-0"
                            title="编辑"
                          >
                            <Pencil className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(product.id)}
                            className="text-muted-foreground hover:text-red-600 h-8 w-8 p-0"
                            title="删除"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    </Card>

                    {isKeywordExpanded && (keywordReport || competitorListingReport || isCompetitorListingLoading) && (
                      <div id={`keyword-validation-report-${product.asin}`} className="ml-12 mt-1 mb-2 scroll-mt-24">
                        <Card className="bg-white border-emerald-100 p-4">
                          {showKeywordMarketOpportunity && keywordReport && (
                            <>
                          <div className="flex items-start justify-between gap-3 mb-4">
                            <div>
                              <div className="flex items-center gap-2">
                                <ShieldCheck className="w-4 h-4 text-emerald-700" />
                                <h3 className="font-bold text-foreground">市场机会判断</h3>
                              </div>
	                              <p className="text-[11px] text-muted-foreground mt-1">
		                                数据来源：{["external_amazon_top40_search"].includes(String(keywordReport.keyword_rank_summary?.rank_data_source || "")) ? "亚马逊搜索页快照" : "暂无"}
	                              </p>
                              <label className="mt-2 inline-flex items-center gap-2 text-xs text-red-700">
                                <Checkbox
                                  checked={Boolean(outOfStockAsins[product.asin])}
                                  onCheckedChange={(checked) => {
                                    markOutOfStock(product.asin, checked === true);
                                    if (checked === true) toast.info("已标记为自有无库存，请点击重算验证");
                                  }}
                                />
                                自有ASIN当前库存为0/不可售
                              </label>
	                            </div>
                            <div className="text-right">
                              <div className={`rounded-full border px-3 py-1 text-sm font-bold ${levelTone}`}>{opportunityLevel}</div>
                              <div className="mt-1 text-xs text-muted-foreground">机会等级</div>
                            </div>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
                            {[
                              ["成功概率", `${Math.round(v5Decision?.success_probability ?? keywordReport.keyword_sales_score)}%`],
                              ["需求强度", `${Math.round(v5Decision?.demand_strength ?? keywordReport.keyword_sales_score)}%`],
                              ["竞争压力", keywordReport.keyword_rank_summary?.inventory_blocker ? "暂不判断" : `${Math.round(v5Decision?.competition_pressure ?? keywordReport.ad_dependency_risk)}%`],
                              ["验证成本", v5Decision?.validation_cost || "待录入"],
                              ["最大风险", v5Decision?.max_risk || "暂无"],
                              ["机会等级", opportunityLevel],
                            ].map(([label, value]) => (
                              <div key={label} className="rounded-lg bg-background border border-border p-3">
                                <p className="text-xs text-muted-foreground">{label}</p>
                                <p className="mt-1 text-sm font-bold text-foreground line-clamp-2">{value}</p>
                              </div>
                            ))}
                          </div>

                          {scoreResult && (
                            <div className="mb-4">
                              <div className="mb-2 flex items-center justify-between gap-3">
                                <p className="text-sm font-semibold text-foreground">6维诊断</p>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleFiveDScore(product)}
                                  disabled={isScoring}
                                  className="h-8 text-xs text-muted-foreground hover:text-brand-600"
                                >
                                  {isScoring ? (
                                    <Loader2 className="w-3 h-3 animate-spin mr-1" />
                                  ) : (
                                    <RefreshCw className="w-3 h-3 mr-1" />
                                  )}
                                  重算
                                </Button>
                              </div>
                              <FiveDimensionScoreCard result={scoreResult} />
                            </div>
                          )}

                          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 mb-4">
                            <div className="rounded-lg bg-white border border-border p-3">
                              <div className="flex items-center justify-between gap-3 mb-3">
                                <p className="text-sm font-semibold text-foreground">市场演化矩阵</p>
                              </div>
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                <div className="rounded-md bg-background border border-border p-2.5">
                                  <p className="text-xs text-muted-foreground">横向演化指数</p>
                                  <p className="mt-1 text-sm font-bold text-foreground">
                                    {formatIndexValue(
                                      keywordReport.market_evolution_matrix?.horizontal_evolution_index ??
                                        keywordReport.market_evolution_matrix?.meaning_evolution_index
                                    )}
                                  </p>
                                </div>
                                <div className="rounded-md bg-background border border-border p-2.5">
                                  <p className="text-xs text-muted-foreground">技术演化指数</p>
                                  <p className="mt-1 text-sm font-bold text-foreground">
                                    {formatIndexValue(keywordReport.market_evolution_matrix?.technology_evolution_index)}
                                  </p>
                                </div>
                                <div className="rounded-md bg-background border border-border p-2.5">
                                  <p className="text-xs text-muted-foreground">当前市场位置</p>
                                  <p className="mt-1 text-sm font-bold text-foreground">
                                    {keywordReport.market_evolution_matrix?.current_position || "待录入"}
                                  </p>
                                </div>
                                <div className="rounded-md bg-background border border-border p-2.5">
                                  <p className="text-xs text-muted-foreground">推荐突破方向</p>
                                  <p className="mt-1 text-sm font-bold text-foreground">
                                    {keywordReport.market_evolution_matrix?.recommendation || "待录入"}
                                  </p>
                                </div>
                              </div>
                            </div>

                            <div className="rounded-lg bg-white border border-border p-3">
                              <div className="flex items-center justify-between gap-3 mb-3">
                                <p className="text-sm font-semibold text-foreground">解决方案演化</p>
                              </div>
                              <div className="space-y-2">
                                <div className="rounded-md bg-background border border-border p-2.5">
                                  <p className="text-xs text-muted-foreground">方案代际</p>
                                  <p className="mt-1 text-sm font-bold text-foreground">
                                    {formatListValue(keywordReport.solution_evolution?.generations)}
                                  </p>
                                </div>
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                                  <div className="rounded-md bg-background border border-border p-2.5">
                                    <p className="text-xs text-muted-foreground">已解决问题</p>
                                    <p className="mt-1 text-sm font-bold text-foreground">
                                      {formatListValue(keywordReport.solution_evolution?.solved_problems)}
                                    </p>
                                  </div>
                                  <div className="rounded-md bg-background border border-border p-2.5">
                                    <p className="text-xs text-muted-foreground">未解决问题</p>
                                    <p className="mt-1 text-sm font-bold text-foreground">
                                      {formatListValue(keywordReport.solution_evolution?.unsolved_problems)}
                                    </p>
                                  </div>
                                  <div className="rounded-md bg-background border border-border p-2.5">
                                    <p className="text-xs text-muted-foreground">当前机会</p>
                                    <p className="mt-1 text-sm font-bold text-foreground">
                                      {keywordReport.solution_evolution?.current_opportunity || "待录入"}
                                    </p>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>

                          {keywordReport.market_validation_assist && (
                            <div className="rounded-lg bg-slate-50 border border-slate-100 p-3 mb-4">
                              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                                <div>
                                  <p className="text-sm font-semibold text-brand-700">选品验证建议</p>
                                  {keywordReport.market_validation_assist.entry_strategy && (
                                    <p className="text-xs text-brand-500 mt-1 leading-5">{keywordReport.market_validation_assist.entry_strategy}</p>
                                  )}
                                  {(keywordReport.market_validation_assist.validation_actions || []).length > 0 && (
                                    <ul className="mt-2 space-y-1 text-xs text-brand-500">
                                      {(keywordReport.market_validation_assist.validation_actions || []).slice(0, 4).map((action) => (
                                        <li key={action}>• {action}</li>
                                      ))}
                                    </ul>
                                  )}
                                </div>
                                {(keywordReport.market_validation_assist.six_dimension_calibration || []).length > 0 && (
                                  <div>
                                    <p className="text-sm font-semibold text-brand-700">6维校准信号</p>
                                    <div className="mt-2 space-y-2">
                                      {(keywordReport.market_validation_assist.six_dimension_calibration || []).slice(0, 4).map((item) => (
                                        <div key={`${item.dimension}-${item.signal}`} className="rounded-md bg-white border border-border px-2.5 py-2">
                                          <div className="flex items-center justify-between gap-2">
                                            <span className="text-xs font-semibold text-brand-600">{item.dimension}</span>
                                            <span className={`text-[11px] font-semibold ${
                                              item.impact.includes("扣") || item.impact.includes("复查") ? "text-amber-700" : item.impact.includes("暂缓") ? "text-red-700" : "text-emerald-700"
                                            }`}>
                                              {item.impact}
                                            </span>
                                          </div>
                                          <p className="text-xs text-brand-500 mt-1">{item.signal}：{item.reason}</p>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          )}

                          <div className="rounded-lg border border-border overflow-hidden mb-4">
                            <div className="grid grid-cols-5 bg-background text-xs font-semibold text-muted-foreground px-3 py-2">
                              <span className="col-span-2">关键词</span>
                              <span>自然位</span>
                              <span>广告位</span>
                              <span>页码</span>
                            </div>
                            {keywordReport.rank_snapshots.slice(0, 8).map((row) => (
                              <div key={row.keyword} className="grid grid-cols-5 px-3 py-2 text-xs border-t border-border">
                                <span className="col-span-2 font-medium text-brand-600">{row.keyword}</span>
                                <span className={row.organic_position ? "text-emerald-700" : "text-muted-foreground"}>{row.organic_position || "未进Top40"}</span>
                                <span className={row.sponsored_position ? "text-amber-700" : "text-muted-foreground"}>{row.sponsored_position || "-"}</span>
                                <span className="text-muted-foreground">{row.search_page || "-"}</span>
                              </div>
                            ))}
                          </div>
                            </>
                          )}

                          <div className="rounded-lg border border-border bg-background p-3 mb-4">
                            <div className="mb-3 flex items-center justify-between gap-3">
                              <div className="flex items-center gap-2">
                                <Microscope className="w-4 h-4 text-brand-600" />
                                <p className="text-sm font-semibold text-foreground">竞品Listing承接判断</p>
                              </div>
                              <div className="flex items-center gap-2">
                                {isCompetitorListingLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => runCompetitorListingDiagnosis(product)}
                                  disabled={isCompetitorListingLoading}
                                  className="h-8 text-xs text-muted-foreground hover:text-brand-600"
                                >
                                  {isCompetitorListingLoading ? "分析中" : "重算"}
                                </Button>
                              </div>
                            </div>
                            <CompetitorEvidencePanel
                              product={product}
                              productData={competitorProductData}
                              title={competitorListingReport?.product_title || product.title}
                            />
                            <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-4">
                              <div className="rounded-md border border-border bg-white p-3">
                                <p className="text-xs text-muted-foreground">可打判断</p>
                                <p className="mt-1 text-sm font-bold text-foreground">{competitorSummary.judgment}</p>
                              </div>
                              <div className="rounded-md border border-border bg-white p-3">
                                <p className="text-xs text-muted-foreground">承接评分</p>
                                <p className="mt-1 text-sm font-bold text-foreground">
                                  {competitorSummary.score ? `${competitorSummary.score}/100` : "待录入"}
                                </p>
                              </div>
                              <div className="rounded-md border border-border bg-white p-3">
                                <p className="text-xs text-muted-foreground">排名来源</p>
                                <p className="mt-1 text-sm font-bold text-foreground">{competitorSummary.rankSource.label}</p>
                              </div>
                              <div className="rounded-md border border-border bg-white p-3">
                                <p className="text-xs text-muted-foreground">依据</p>
                                <p className="mt-1 text-sm font-bold text-foreground line-clamp-2">{competitorSummary.basis}</p>
                              </div>
                            </div>
                            <div className="mt-3">
                              <CompetitorListingBreakdownPanel modules={competitorSummary.modules} />
                            </div>
                            {competitorSummary.selection?.score && (
                              <div className="mt-3 grid grid-cols-1 gap-2">
                                {[
                                  ["事实层", competitorSummary.selection.fact_layer],
                                  ["语义层", competitorSummary.selection.semantic_layer],
                                  ["推理层", competitorSummary.selection.reasoning_layer],
                                  ["决策层", competitorSummary.selection.decision_layer],
                                  ["验证", competitorSummary.selection.validation_suggestions],
                                ].map(([label, value]) => (
                                  <div key={String(label)} className="rounded-md border border-border bg-white p-3">
                                    <p className="mb-1 text-xs font-semibold text-muted-foreground">{String(label)}</p>
                                    <p className="text-xs leading-relaxed text-foreground">
                                      {formatListValue(Array.isArray(value) ? value.map((item) => String(item)) : [])}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            )}
                            <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
                              <div className="rounded-md border border-border bg-white p-3">
                                <p className="mb-2 text-xs font-semibold text-muted-foreground">5星好评关键词</p>
                                <div className="flex flex-wrap gap-1.5">
                                  {competitorSummary.positiveKeywords.length > 0 ? (
                                    competitorSummary.positiveKeywords.map((keyword) => (
                                      <span key={keyword} className="rounded bg-emerald-50 px-2 py-1 text-xs text-emerald-700">{keyword}</span>
                                    ))
                                  ) : (
                                    <span className="text-xs text-muted-foreground">暂无</span>
                                  )}
                                </div>
                              </div>
                              <div className="rounded-md border border-border bg-white p-3">
                                <p className="mb-2 text-xs font-semibold text-muted-foreground">抱怨关键词</p>
                                <div className="flex flex-wrap gap-1.5">
                                  {competitorSummary.complaintKeywords.length > 0 ? (
                                    competitorSummary.complaintKeywords.map((keyword) => (
                                      <span key={keyword} className="rounded bg-red-50 px-2 py-1 text-xs text-red-700">{keyword}</span>
                                    ))
                                  ) : (
                                    <span className="text-xs text-muted-foreground">暂无</span>
                                  )}
                                </div>
                              </div>
                            </div>
                            <div className="mt-3 overflow-x-auto rounded-md border border-border bg-white">
                              <table className="w-full min-w-[760px] text-left text-xs">
                                <thead className="text-muted-foreground">
                                  <tr className="border-b border-border bg-background">
                                    <th className="py-2 pl-3 pr-3 font-medium">承接模块</th>
                                    <th className="py-2 pr-3 font-medium">强项</th>
                                    <th className="py-2 pr-3 font-medium">弱项</th>
                                    <th className="py-2 pr-3 font-medium">关键词</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {competitorSummary.modules.length > 0 ? (
                                    competitorSummary.modules.slice(0, 6).map((module) => (
                                      <tr key={module.key} className="border-b border-border/60 last:border-0">
                                        <td className="py-2 pl-3 pr-3 font-semibold text-foreground">{module.name || "待录入"}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{formatListValue(module.strengths?.slice(0, 2))}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{formatListValue(module.weaknesses?.slice(0, 2))}</td>
                                        <td className="py-2 pr-3 text-muted-foreground">{formatListValue(module.keywords?.slice(0, 4))}</td>
                                      </tr>
                                    ))
                                  ) : (
                                    <tr>
                                      <td className="py-3 pl-3 pr-3 text-muted-foreground" colSpan={4}>暂无</td>
                                    </tr>
                                  )}
                                </tbody>
                              </table>
                            </div>
                          </div>

                          {showKeywordMarketOpportunity && keywordReport && (
                            <>
                          {keywordReport.keyword_rank_summary?.rank_data_note && (
                            <p className="text-[11px] text-muted-foreground mb-3">{keywordReport.keyword_rank_summary.rank_data_note}</p>
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
                                {keywordReport.keyword_rank_summary.inventory_note || "该ASIN当前无库存或不可售，请补库存并确认页面可售后重算验证。"}
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
                              <p className="font-semibold text-brand-600 mb-2">机会关键词</p>
                              <div className="flex flex-wrap gap-1.5">
                                {keywordReport.opportunity_keywords.map((kw) => <span key={kw} className="rounded bg-emerald-50 px-2 py-1 text-emerald-700">{kw}</span>)}
                              </div>
                            </div>
                            <div>
                              <p className="font-semibold text-brand-600 mb-2">风险关键词</p>
                              <div className="flex flex-wrap gap-1.5">
                                {keywordReport.risk_keywords.map((kw) => <span key={kw} className="rounded bg-gold-50 px-2 py-1 text-amber-700">{kw}</span>)}
                              </div>
                            </div>
                          </div>
                          <p className="text-xs text-muted-foreground mt-3">{keywordReport.final_recommendation}</p>
                            </>
                          )}
                        </Card>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : null}

        </div>
      </main>
    </div>
  );
}
