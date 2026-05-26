import { useState, useCallback } from "react";

import { AppSidebar } from "@/components/AppSidebar";
import { PageHeader } from "@/components/PageHeader";
import { NextStepActions } from "@/components/NextStepActions";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { RadarChartMulti, DIMENSIONS } from "@/components/RadarChartMulti";
import type { RadarDataSet } from "@/components/RadarChartMulti";
import {
  Search,
  Loader2,
  TrendingUp,
  Target,
  Zap,
  History,
  AlertCircle,
  FileText,
  Image as ImageIcon,
  MessageSquare,
  Video,
  ChevronDown,
  ChevronUp,
  Globe,
} from "lucide-react";
import { toast } from "sonner";
import axios from "axios";
import { getAuthHeaders } from "@/lib/auth-headers";
import { saveCompetitorInsight, updateProductLifecycle, saveTimelineEvent, saveActionSnapshot, getActionSnapshots, type ActionSnapshot } from "@/lib/workflow-api";

/* ------------------------------------------------------------------ */
/*  URL / ASIN Extraction Helpers (same as ListingDiagnosis)           */
/* ------------------------------------------------------------------ */

function extractAsinFromUrl(url: string): string {
  const patterns = [/\/dp\/([A-Z0-9]{10})/i, /\/gp\/product\/([A-Z0-9]{10})/i, /\/product\/([A-Z0-9]{10})/i];
  for (const p of patterns) {
    const m = url.match(p);
    if (m) return m[1].toUpperCase();
  }
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

/** Parse user input: could be a plain ASIN or a full Amazon URL */
function parseAsinInput(input: string): { asin: string; marketplace: string; searchKeyword?: string; isSearchUrl?: boolean } {
  const trimmed = input.trim();
  if (trimmed.includes("http") || trimmed.includes("amazon")) {
    const asin = extractAsinFromUrl(trimmed);
    const mp = detectMarketplaceFromUrl(trimmed);
    try {
      const url = new URL(trimmed);
      const keyword = (url.searchParams.get("k") || "").replace(/\+/g, " ").trim();
      const isSearchUrl = /\/s\b/i.test(url.pathname) || Boolean(keyword);
      return { asin, marketplace: mp, searchKeyword: keyword, isSearchUrl };
    } catch {
      return { asin, marketplace: mp };
    }
  }
  return { asin: trimmed.toUpperCase(), marketplace: "" };
}

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





interface ProductData {
  title?: string;
  brand?: string;
  category?: string;
  price?: string;
  price_currency?: string;
  rating?: string;
  review_count?: string;
  date_first_available?: string;
  launch_date?: string;
  bsr_rank?: string;
  bsr_category?: string;
  bullet_points?: string[];
  main_keywords?: string[];
  rating_histogram?: Record<string, string>;
  low_star_reviews?: Array<Record<string, unknown>>;
  product_details?: Record<string, string>;
  image_urls?: string[];
  aplus_image_count?: string;
  aplus_image_urls?: string[];
  seller_type?: string;
  platform_ecosystem?: boolean;
  brand_monopoly_risk?: boolean;
  bought_count?: string;
  amazon_bought_count?: string;
  estimated_monthly_sales?: string;
  estimated_monthly_revenue?: string;
  listing_quality_notes?: string;
  image_count?: string;
  has_video?: boolean;
  has_a_plus?: boolean;
  variation_count?: string;
  [key: string]: unknown;
}

interface Scores {
  functionality: number;
  emotional: number;
  scenario: number;
  user_profile: number;
  differentiation: number;
  market_trend: number;
  product_identity: number;
  compatibility: number;
  subjective_properties: number;
  risk_elimination: number;
}

const SCORE_KEYS: Array<keyof Scores> = [
  "functionality",
  "emotional",
  "scenario",
  "user_profile",
  "differentiation",
  "market_trend",
  "product_identity",
  "compatibility",
  "subjective_properties",
  "risk_elimination",
];

interface AnalysisReport {
  scores: Scores;
  analysis: Record<string, string>;
  overall_summary: string;
  improvement_suggestions: string[];
  listing_breakdown?: ListingBreakdown;
  amazon_compliance?: ComplianceResult;
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

interface ListingBreakdownModule {
  key: string;
  name: string;
  summary?: string;
  raw_content?: unknown;
  structure_breakdown?: string[];
  strengths?: string[];
  weaknesses?: string[];
  covered_user_intents?: string[];
  keywords?: string[];
  borrowable_actions?: string[];
  do_not_copy?: string[];
}

interface ListingBreakdown {
  modules?: ListingBreakdownModule[];
  rating_histogram?: Record<string, string>;
  low_star_reviews?: Array<Record<string, unknown>>;
  image_urls?: string[];
  vision_status?: string;
}

interface AnalysisResult {
  asin: string;
  marketplace: string;
  product_title: string;
  product_data: ProductData;
  scores: Scores;
  analysis_report: AnalysisReport;
  amazon_compliance?: ComplianceResult;
  data_source?: string;
  id?: number;
}

interface HistoryItem {
  id: number;
  asin: string;
  marketplace: string;
  product_title: string;
  scores: Scores;
  created_at: string;
  source?: "analysis" | "snapshot";
  snapshot?: ActionSnapshot;
}

const COLORS = [
  { color: "rgba(99, 102, 241, 1)", fill: "rgba(99, 102, 241, 0.15)" },
  { color: "rgba(239, 68, 68, 1)", fill: "rgba(239, 68, 68, 0.15)" },
  { color: "rgba(34, 197, 94, 1)", fill: "rgba(34, 197, 94, 0.15)" },
  { color: "rgba(234, 179, 8, 1)", fill: "rgba(234, 179, 8, 0.15)" },
  { color: "rgba(168, 85, 247, 1)", fill: "rgba(168, 85, 247, 0.15)" },
  { color: "rgba(236, 72, 153, 1)", fill: "rgba(236, 72, 153, 0.15)" },
];

const MARKETPLACE_OPTIONS = [
  { value: "US", label: "🇺🇸 美国站", domain: "www.amazon.com" },
  { value: "JP", label: "🇯🇵 日本站", domain: "www.amazon.co.jp" },
  { value: "DE", label: "🇩🇪 德国站", domain: "www.amazon.de" },
  { value: "UK", label: "🇬🇧 英国站", domain: "www.amazon.co.uk" },
  { value: "CA", label: "🇨🇦 加拿大站", domain: "www.amazon.ca" },
];

const KEYWORD_TYPE_LABELS: Record<string, string> = {
  attribute: "属性词",
  relationship: "关系词",
  state_trigger: "状态触发词",
};

const KEYWORD_TYPE_BADGES: Record<string, string> = {
  attribute: "bg-gray-100 text-gray-600 border-gray-200",
  relationship: "bg-teal-50 text-teal-700 border-teal-200",
  state_trigger: "bg-orange-50 text-orange-700 border-orange-200",
};

function classifyAmazonKeyword(keyword: string): "attribute" | "relationship" | "state_trigger" {
  const lower = keyword.toLowerCase();
  if (/(odor|smell|ammonia|pain|relief|anxiety|safe|comfort|leak|tracking|mess|stress|sleep|noise|waterproof|outdoor|party)/.test(lower)) {
    return "state_trigger";
  }
  if (/(for|with|without|under|near|compatible|replacement|indoor|apartment|bedroom|travel|kids|women|men|mom|cats|dogs|office|camping)/.test(lower)) {
    return "relationship";
  }
  return "attribute";
}

function KeywordBadge({ keyword, compact = false }: { keyword: string; compact?: boolean }) {
  const displayKeyword = normalizeAmazonKeyword(keyword);
  if (!displayKeyword) return null;
  const type = classifyAmazonKeyword(displayKeyword);
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border ${compact ? "px-2 py-0.5 text-[11px]" : "px-3 py-1.5 text-sm"} ${KEYWORD_TYPE_BADGES[type]}`}>
      <span>{displayKeyword}</span>
      <span className="text-[10px] opacity-75">{KEYWORD_TYPE_LABELS[type]}</span>
    </span>
  );
}

function normalizeAmazonKeyword(keyword: string): string {
  let text = String(keyword || "").trim().toLowerCase();
  if (!text) return "";
  if (/[\u4e00-\u9fff]/.test(text)) {
    return "";
  }
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
  text = text.replace(/[^a-z0-9 +&/-]/g, " ").replace(/\s+/g, " ").trim();
  const normalized = text.split(" ").slice(0, 8).join(" ");
  return /[a-z]/.test(normalized) ? normalized : "";
}

function normalizeStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => (typeof item === "string" ? item : JSON.stringify(item)))
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (typeof value === "string") {
    return value
      .split(/\n+|[•·]/)
      .map((item) => item.replace(/^[-*\d.)\s]+/, "").trim())
      .filter(Boolean);
  }
  return [];
}

function parseRatingPercent(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.max(0, Math.min(100, Math.round(value)));
  }
  const match = String(value || "").match(/(\d{1,3})(?:\.\d+)?\s*%?/);
  if (!match) return null;
  const parsed = Number(match[1]);
  if (!Number.isFinite(parsed) || parsed < 0 || parsed > 100) return null;
  return Math.round(parsed);
}

function normalizeRatingHistogram(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object") return {};
  const raw = value as Record<string, unknown>;
  const normalized: Record<string, string> = {};
  const nums: number[] = [];

  for (const star of [5, 4, 3, 2, 1]) {
    const percent = parseRatingPercent(raw[`${star}_star`] ?? raw[`${star} star`] ?? raw[String(star)]);
    if (percent === null) continue;
    normalized[`${star}_star`] = `${percent}%`;
    nums.push(percent);
  }

  if (nums.length < 5) return {};
  const total = nums.reduce((sum, item) => sum + item, 0);
  const uniqueNonZero = new Set(nums.filter((item) => item > 0));
  if (total < 95 || total > 105 || uniqueNonZero.size <= 1) return {};
  return normalized;
}

function deriveAmazonKeywords(pd: ProductData, title: string): string[] {
  const bullets = normalizeStringList(pd.bullet_points);
  const rawText = `${title || ""} ${bullets.join(" ")} ${pd.category || ""}`;
  const text = rawText.toLowerCase();
  const candidates: string[] = [];
  const has = (pattern: RegExp) => pattern.test(text);

  if (has(/手机壳|保护壳|iphone|magsafe|phone case|case/)) {
    candidates.push("iphone case", "magsafe iphone case", "protective iphone case");
    if (has(/透明|clear|translucent/)) candidates.push("clear iphone case");
    if (has(/防摔|shock|drop|military|protection|protective/)) candidates.push("shockproof iphone case");
    if (has(/磁吸|magsafe|magnetic/)) candidates.push("magnetic phone case");
    if (has(/防指纹|fingerprint/)) candidates.push("anti fingerprint phone case");
  }

  if (has(/bluetooth|speaker|boombox/)) {
    candidates.push("bluetooth speaker", "portable bluetooth speaker");
    if (has(/waterproof|outdoor|beach|pool|camping/)) candidates.push("waterproof outdoor speaker", "speaker for beach trips");
    if (has(/led|light/)) candidates.push("bluetooth speaker with led lights");
    if (has(/bass|sound|loud/)) candidates.push("loud bass bluetooth speaker");
  }
  if (has(/cat|litter/)) {
    candidates.push("cat litter box", "cat litter odor control", "litter box for apartment cats", "reduce litter tracking");
    if (has(/carbon|filter/)) candidates.push("cat litter box with carbon filter");
  }
  if (has(/echo|alexa|smart speaker/)) {
    candidates.push("smart speaker with alexa", "echo dot for bedroom", "voice assistant speaker");
  }
  if (has(/gift|mom|women|dad|men/)) {
    candidates.push("gift for mom", "gift for women", "gift for dad");
  }

  const englishText = text
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((word) => word.length > 2 && !["the", "and", "with", "for", "from", "this", "that", "pink", "white", "black"].includes(word));
  if (englishText.length >= 2) candidates.push(englishText.slice(0, 3).join(" "));

  const seen = new Set<string>();
  return candidates
    .map(normalizeAmazonKeyword)
    .filter((kw) => kw && !seen.has(kw) && seen.add(kw))
    .slice(0, 8);
}

function formatPrice(pd: ProductData): string | undefined {
  const raw = String(pd.price || "").trim();
  if (!raw) return undefined;
  if (/[$€£¥₹]/.test(raw) || /^[A-Z]{3}\s+/i.test(raw)) return raw;
  const currency = String(pd.price_currency || "USD").toUpperCase();
  const symbol: Record<string, string> = { USD: "$", CAD: "$", AUD: "$", GBP: "£", EUR: "€", JPY: "¥", INR: "₹", MXN: "$" };
  return `${symbol[currency] || ""}${raw}`;
}

function formatRawContent(raw: unknown): string {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.images) || obj.text) {
      const images = Array.isArray(obj.images) ? obj.images : [];
      return [`A+ Images: ${images.length}`, String(obj.text || "")].filter(Boolean).join("\n\n");
    }
  }
  if (Array.isArray(raw)) {
    return raw.map((item, index) => `${index + 1}. ${typeof item === "string" ? item : JSON.stringify(item)}`).join("\n");
  }
  if (raw && typeof raw === "object") return JSON.stringify(raw, null, 2);
  return String(raw || "暂无原始内容");
}

function fallbackListingBreakdown(pd: ProductData, keywords: string[]): ListingBreakdown {
  const titleKeywords = cleanEnglishKeywordList(keywords.slice(0, 3), [], "title");
  const bulletKeywords = cleanEnglishKeywordList(keywords.slice(3, 6), [], "bullets");
  const reviewKeywords = cleanEnglishKeywordList(keywords.slice(6, 8), [], "review_validation");
  return {
    modules: [
      {
        key: "title",
        name: "标题 × 广告匹配",
        summary: "标题决定广告能否拿到准流量，并影响搜索词相关性与首轮CTR。",
        raw_content: pd.title,
        structure_breakdown: ["品牌/身份词", "核心品类词", "关键属性", "规格/数量", "适用对象或场景"],
        strengths: ["标题能帮助平台识别产品身份，利于广告匹配到基础流量。"],
        weaknesses: ["若缺少关系词或状态触发词，广告可能拿到泛流量，CTR和CVR都会被稀释。"],
        covered_user_intents: ["识别产品身份", "确认核心品类", "理解关键属性", "判断适用对象/场景"],
        keywords: titleKeywords,
        borrowable_actions: ["借鉴其标题里的高意图词序，把我方标题改成更利于广告搜索词匹配的结构。"],
        do_not_copy: ["不复制竞品品牌名、夸张词和不属于我方产品的规格。"],
      },
      {
        key: "bullets",
        name: "五点 × 转化承接",
        summary: "五点决定点击后的购买理由是否成立，主要影响CVR、ACOS和订单转化。",
        raw_content: pd.bullet_points || [],
        structure_breakdown: ["功能", "效果", "场景", "信任", "售后/风险消除"],
        strengths: [`已识别 ${pd.bullet_points?.length || 0} 条五点，可用于判断其广告点击后的承接能力。`],
        weaknesses: ["如果五点只是堆参数，没有回答顾虑，竞品广告可能有点击但CVR不足。"],
        covered_user_intents: ["确认功能效果", "降低购买犹豫", "理解使用场景", "建立信任", "消除售后/风险顾虑"],
        keywords: bulletKeywords,
        borrowable_actions: ["把竞品五点反推为广告点击后的成交话术，补强我方CVR承接。"],
        do_not_copy: ["不复制无证据支撑的绝对化承诺。"],
      },
      {
        key: "review_validation",
        name: "评论 × 广告承诺可信度",
        summary: "评论验证竞品广告承诺是否可信，直接影响CVR、ACOS和差评风险。",
        raw_content: pd.low_star_reviews || [],
        structure_breakdown: ["评分分布", "3星以下差评", "痛点归纳", "可攻击弱点"],
        strengths: ["评论能支撑竞品广告承诺时，转化阻力更小。"],
        weaknesses: ["低分评论暴露的痛点，是我方广告避开或攻击的机会。"],
        covered_user_intents: ["risk removal", "quality concern", "usage friction"],
        keywords: reviewKeywords,
        borrowable_actions: ["把差评原因转成我方广告落地页必须解释的内容。"],
        do_not_copy: ["不要只照抄好评卖点。"],
      },
    ],
    rating_histogram: pd.rating_histogram,
    low_star_reviews: pd.low_star_reviews,
    image_urls: pd.image_urls,
  };
}

function getDisplayKeywords(pd: ProductData, title: string): string[] {
  const saved = Array.isArray(pd.main_keywords) ? pd.main_keywords : [];
  const normalized = saved.map(normalizeAmazonKeyword).filter(Boolean);
  const seen = new Set<string>();
  const clean = normalized.filter((kw) => !seen.has(kw) && seen.add(kw));
  return clean.length > 0 ? clean : deriveAmazonKeywords(pd, title);
}

function isIncompleteSavedResult(result: AnalysisResult): boolean {
  const pd = result.product_data || {};
  const source = result.data_source || String((pd as Record<string, unknown>)._data_source || "");
  const title = String(pd.title || result.product_title || "");
  const lacksCoreData = !pd.price && !pd.rating && !pd.review_count && !pd.bullet_points?.length;
  return source.includes("saved") && (lacksCoreData || title.includes("待确认"));
}

function hasPlatformEcoRisk(pd: ProductData): boolean {
  const seller = String(pd.seller_type || "");
  return Boolean(pd.platform_ecosystem || pd.brand_monopoly_risk || seller.includes("平台生态") || seller.includes("Amazon自营"));
}

function moduleDefaultIntents(key: string): string[] {
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
}

function sameStringList(a?: string[], b?: string[]): boolean {
  if (!a?.length || !b?.length || a.length !== b.length) return false;
  return a.every((item, index) => item === b[index]);
}

function cleanEnglishKeywordList(values?: string[], fallback: string[] = [], moduleKey = ""): string[] {
  const seen = new Set<string>();
  const clean = (values || [])
    .map(normalizeAmazonKeyword)
    .filter((kw) => kw && !seen.has(kw) && seen.add(kw));
  if (clean.length > 0) return clean.slice(0, 6);

  const moduleOffset: Record<string, number> = {
    title: 0,
    bullets: 1,
    main_image: 2,
    secondary_images: 3,
    a_plus: 1,
    video_brand: 2,
    review_validation: 0,
  };
  const offset = moduleOffset[moduleKey] || 0;
  const rotated = [...fallback.slice(offset), ...fallback.slice(0, offset)];
  return rotated
    .map(normalizeAmazonKeyword)
    .filter((kw) => kw && !seen.has(kw) && seen.add(kw))
    .slice(0, 5);
}

function sanitizeAnalysisKeywords(result: AnalysisResult): AnalysisResult {
  const pd = result.product_data || {};
  pd.bullet_points = normalizeStringList(pd.bullet_points);
  const cleanMainKeywords = cleanEnglishKeywordList(normalizeStringList(pd.main_keywords), [], "title");
  pd.main_keywords = cleanMainKeywords;
  pd.rating_histogram = normalizeRatingHistogram(pd.rating_histogram);
  const scores = getEffectiveScores(result);

  const breakdown = result.analysis_report?.listing_breakdown;
  const modules = breakdown?.modules || [];
  modules.forEach((module) => {
    module.keywords = cleanEnglishKeywordList(module.keywords, [], module.key);
  });
  return {
    ...result,
    product_data: pd,
    scores,
    amazon_compliance: result.amazon_compliance || result.analysis_report?.amazon_compliance,
    analysis_report: {
      ...result.analysis_report,
      scores,
      listing_breakdown: breakdown ? { ...breakdown, modules } : breakdown,
      amazon_compliance: result.analysis_report?.amazon_compliance || result.amazon_compliance,
    },
  };
}

function moduleStructureNarrative(key: string, items?: string[]): string[] {
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
}

function moduleAdMetricMap(key: string) {
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
}

function toScoreNumber(value: unknown): number {
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return 0;
  return Math.max(0, Math.min(100, Math.round(num)));
}

function normalizeScores(value: unknown): Scores {
  const raw = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const nested = raw.scores && typeof raw.scores === "object" ? (raw.scores as Record<string, unknown>) : {};
  const source = { ...nested, ...raw };
  return {
    functionality: toScoreNumber(source.functionality ?? source.score_functionality),
    emotional: toScoreNumber(source.emotional ?? source.score_emotional),
    scenario: toScoreNumber(source.scenario ?? source.score_scenario),
    user_profile: toScoreNumber(source.user_profile ?? source.score_user_profile),
    differentiation: toScoreNumber(source.differentiation ?? source.score_differentiation),
    market_trend: toScoreNumber(source.market_trend ?? source.score_market_trend),
    product_identity: toScoreNumber(source.product_identity ?? source.score_product_identity),
    compatibility: toScoreNumber(source.compatibility ?? source.score_compatibility),
    subjective_properties: toScoreNumber(source.subjective_properties ?? source.score_subjective_properties),
    risk_elimination: toScoreNumber(source.risk_elimination ?? source.score_risk_elimination),
  };
}

function hasAnyScore(scores: Scores): boolean {
  return SCORE_KEYS.some((key) => Number(scores[key]) > 0);
}

function getEffectiveScores(result: Partial<AnalysisResult> & { output_snapshot?: unknown }): Scores {
  const report = result.analysis_report as (Partial<AnalysisReport> & Record<string, unknown>) | undefined;
  const candidates = [
    result.scores,
    report?.scores,
    result.output_snapshot,
    (result.output_snapshot as Record<string, unknown> | undefined)?.scores,
    (result.output_snapshot as Record<string, unknown> | undefined)?.analysis_report,
    ((result.output_snapshot as Record<string, unknown> | undefined)?.analysis_report as Record<string, unknown> | undefined)?.scores,
    result,
  ];
  for (const candidate of candidates) {
    const normalized = normalizeScores(candidate);
    if (hasAnyScore(normalized)) return normalized;
  }
  return normalizeScores(result.scores || report?.scores);
}

function getAvgScore(scores: Scores): number {
  const normalized = normalizeScores(scores);
  const vals = SCORE_KEYS.map((key) => normalized[key]).filter((v) => typeof v === "number");
  if (vals.length === 0) return 0;
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
}

function scoresToRadarData(label: string, scores: Scores, colorIdx: number): RadarDataSet {
  const c = COLORS[colorIdx % COLORS.length];
  const normalized = normalizeScores(scores);
  return {
    label,
    scores: DIMENSIONS.map((d) => ({
      label: d.label,
      key: d.key,
      value: (normalized as Record<string, number>)[d.key] || 0,
    })),
    color: c.color,
    fillColor: c.fill,
  };
}

export default function CompetitorAnalysis() {
  const { loading: authLoading } = useRequireAuth();

  const urlParams = new URLSearchParams(window.location.search);
  const initialTab = urlParams.get("tab") === "history" ? "history" : "single";
  const [activeTab, setActiveTab] = useState(initialTab);
  const [singleAsin, setSingleAsin] = useState("");
  const [marketplace, setMarketplace] = useState("US");
  const [analyzing, setAnalyzing] = useState(false);
  const [singleResult, setSingleResult] = useState<AnalysisResult | null>(null);

  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [expandedReport, setExpandedReport] = useState(false);

  const [analyzeProgress, setAnalyzeProgress] = useState("");

  /* ---- Analysis helpers (no public CORS proxies) ---- */

  /**
   * Core analysis function. Use the backend's full ASIN analysis endpoint directly,
   * because public Netlify function proxying can timeout on long Amazon/AI requests.
   */
  const analyzeAsinWithProxy = useCallback(async (
    asin: string,
    mp: string,
  ): Promise<AnalysisResult | null> => {
    const apiBase = getLongRunningApiBase();

    {
      setAnalyzeProgress("服务器正在抓取Amazon页面并生成竞品诊断，通常需要 10-40 秒...");
      try {
        const res = await axios.post(
          `${apiBase}/api/v1/asin-analysis/analyze`,
          { asin, marketplace: mp, force_refresh: true },
          { headers: getAuthHeaders(), timeout: 240000 }
        );

        if (res.data && ("product_title" in res.data || "scores" in res.data)) {
          const serverDataSource = res.data.data_source || res.data.product_data?._data_source;
          if (serverDataSource === "ai_estimated" || serverDataSource === "ai_estimated_low_confidence") {
            toast.warning("未获取到真实页面数据，已返回AI低置信度兜底分析，建议后续复核。");
          }
          return sanitizeAnalysisKeywords(res.data as AnalysisResult);
        }

        toast.error("服务器返回了意外的数据格式，请重试");
        return null;
      } catch (err) {
        if (axios.isAxiosError(err)) {
          if (err.response?.status === 422) {
            const detail = err.response?.data?.detail || "";
            toast.error(typeof detail === "string" ? detail : "请求参数错误");
            return null;
          }
          if (err.code === "ECONNABORTED" || err.message?.includes("timeout")) {
            toast.error("分析超过240秒，请稍后重试。Amazon页面抓取或模型响应可能较慢。");
            return null;
          }
          if (!err.response) {
            toast.error("网络连接失败，请检查网络后重试");
            return null;
          }
          const serverMsg = err.response?.data?.detail || err.response?.data?.error || `服务器错误 (${err.response?.status})`;
          toast.error(typeof serverMsg === "string" ? serverMsg : "服务器内部错误，请稍后重试");
          return null;
        }

        toast.error("分析过程中发生未知错误，请重试");
        return null;
      }
    }

    /* ---- Phase 1: Backend proxy-fetch → parse-html-analyze ---- */
    try {
      setAnalyzeProgress("🌐 Phase 1: 正在通过本地浏览器代理获取Amazon真实页面数据，通常需要20-60秒...");

      const proxyRes = await axios.post(
        "/api/v1/asin-analysis/proxy-fetch",
        { asin, marketplace: mp },
        { headers: getAuthHeaders(), timeout: 75000 }
      );

      if (proxyRes.data?.success && proxyRes.data?.html) {
        const html = proxyRes.data.html;
        setAnalyzeProgress("🔬 已获取到真实页面HTML，正在进行AI深度分析...");

        try {
          const res = await axios.post(
            "/api/v1/asin-analysis/parse-html-analyze",
            { asin, marketplace: mp, html },
            { headers: getAuthHeaders(), timeout: 180000 }
          );
          const data = res.data;

          if (data?.success && data.scores) {
            return sanitizeAnalysisKeywords({
              asin: data.asin,
              marketplace: mp,
              product_title: data.product_title,
              product_data: data.product_data,
              scores: data.scores,
              analysis_report: data.analysis_report,
              data_source: data.data_source || "browser_proxy",
              id: data.id,
            } as AnalysisResult);
          }
        } catch (parseErr) {
          void parseErr;
        }
      } else {
        void proxyRes;
      }
    } catch (phase1Err) {
      void phase1Err;
    }

    /* ---- Phase 2: Server-side /analyze (full scraping + AI) ---- */
    setAnalyzeProgress("🔍 Phase 2: 服务器补充抓取与AI低置信度兜底，最长约180秒...");
    try {
      const res = await axios.post(
        `${apiBase}/api/v1/asin-analysis/analyze`,
        { asin, marketplace: mp },
        { headers: getAuthHeaders(), timeout: 180000 }
      );

      if (res.data && ("product_title" in res.data || "scores" in res.data)) {
        const serverDataSource = res.data.data_source || res.data.product_data?._data_source;
        if (serverDataSource === "ai_estimated" || serverDataSource === "ai_estimated_low_confidence") {
          toast.warning("未获取到真实页面数据，已返回AI低置信度兜底分析，建议后续复核。");
        }
        return sanitizeAnalysisKeywords(res.data as AnalysisResult);
      }

      toast.error("服务器返回了意外的数据格式，请重试");
      return null;
    } catch (err) {

      if (axios.isAxiosError(err)) {
        if (err.response?.status === 422) {
          const detail = err.response?.data?.detail || "";
          toast.error(typeof detail === "string" ? detail : "请求参数错误");
          return null;
        }
        if (err.code === "ECONNABORTED" || err.message?.includes("timeout")) {
          toast.error("分析超过180秒，请稍后重试。Amazon页面抓取或模型响应可能较慢。");
          return null;
        }
        if (!err.response) {
          toast.error("网络连接失败，请检查网络后重试");
          return null;
        }
        const serverMsg = err.response?.data?.detail || err.response?.data?.error || `服务器错误 (${err.response?.status})`;
        toast.error(typeof serverMsg === "string" ? serverMsg : "服务器内部错误，请稍后重试");
        return null;
      }

      toast.error("分析过程中发生未知错误，请重试");
      return null;
    }
  }, []);

  const handleAnalyze = async () => {
    if (!singleAsin.trim()) {
      toast.error("请输入ASIN或Amazon产品链接");
      return;
    }

    const parsed = parseAsinInput(singleAsin.trim());
    const asin = parsed.asin;
    const mp = parsed.marketplace || marketplace;

    if (!asin || asin.length !== 10) {
      if (parsed.isSearchUrl) {
        toast.error(
          parsed.searchKeyword
            ? `这是Amazon搜索结果页（${parsed.searchKeyword}），请点进具体商品后粘贴商品详情页链接或10位ASIN。`
            : "这是Amazon搜索结果页，请点进具体商品后粘贴商品详情页链接或10位ASIN。"
        );
      } else {
        toast.error("无法识别有效ASIN，请输入10位ASIN或完整Amazon商品详情页链接（/dp/ASIN）。");
      }
      return;
    }

    if (parsed.marketplace) {
      setMarketplace(parsed.marketplace);
    }

    setAnalyzing(true);
    setSingleResult(null);
    setAnalyzeProgress("");

    try {
      const result = await analyzeAsinWithProxy(asin, mp);

      if (result) {
        const cleanResult = sanitizeAnalysisKeywords(result);
        setSingleResult(cleanResult);
        const source = cleanResult.data_source;
        if (source === "browser_proxy") {
          toast.success("✅ 已获取Amazon真实数据并完成分析！");
        } else if (source === "amazon_scrape" || source === "amazon_scrape_httpx" || source === "amazon_scrape_browser") {
          toast.success("✅ 已从Amazon真实页面抓取数据并完成分析！");
        } else {
          toast.success("✅ 分析完成！");
        }

        // Save single analysis result as competitor insight for workflow data flow
        try {
          const report = cleanResult.analysis_report;
          const strengths = report?.improvement_suggestions?.slice(0, 3).join("; ") || "";
          const weaknesses = report?.improvement_suggestions?.slice(3, 6).join("; ") || "";
          const radarJson = JSON.stringify(cleanResult.scores || {});
          saveCompetitorInsight({
            product_id: 0,
            competitor_asin: cleanResult.asin,
            strengths,
            weaknesses,
            gaps: "",
            suggestions: (report?.overall_summary || "").substring(0, 5000),
            radar_scores: radarJson,
          }).catch(() => {});
          // Update lifecycle stage
          updateProductLifecycle(0, "strategy").catch(() => {});
          // Save timeline event
          saveTimelineEvent({
            product_id: 0,
            step_name: "竞品分析",
            action_timestamp: new Date().toISOString(),
            listing_score: 0,
            score_details: "{}",
            optimization_round: 1,
          }).catch(() => {});
          saveActionSnapshot({
            module_key: "competitor_analysis",
            module_name: "竞品诊断",
            action_key: "analyze_competitor_listing",
            action_name: "竞品Listing分析",
            product_id: 0,
            asin: cleanResult.asin,
            title: cleanResult.product_title,
            input_snapshot: { asin, marketplace: mp },
            output_snapshot: cleanResult,
            data_source: cleanResult.data_source || String(cleanResult.product_data?._data_source || ""),
            confidence: String(cleanResult.product_data?.data_confidence || ""),
            ai_called: true,
            source_record_table: "asin_analyses",
            source_record_id: cleanResult.id || null,
          }).catch(() => {});
        } catch {
          // Non-critical
        }
      }
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err) ? err.response?.data?.detail || "分析失败" : "分析失败";
      toast.error(msg);
    } finally {
      setAnalyzing(false);
      setAnalyzeProgress("");
    }
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const [analysisRes, snapshots] = await Promise.all([
        axios
          .get("/api/v1/asin-analysis/history?limit=50", {
            headers: getAuthHeaders(),
          })
          .then((res) => (res.data.items || []) as HistoryItem[])
          .catch(() => [] as HistoryItem[]),
        getActionSnapshots({ module_key: "competitor_analysis", limit: 120 }),
      ]);

      const snapshotRows: HistoryItem[] = snapshots
        .map((snapshot) => {
          const output = snapshot.output_snapshot as Partial<AnalysisResult> | undefined;
          const input = snapshot.input_snapshot as { marketplace?: string } | undefined;
          const scores = getEffectiveScores(output || {});
          if (!output?.asin || !hasAnyScore(scores)) return null;
          return {
            id: snapshot.id,
            asin: output.asin || snapshot.asin || "",
            marketplace: output.marketplace || input?.marketplace || "",
            product_title: output.product_title || output.product_data?.title || snapshot.title || output.asin || "",
            scores,
            created_at: snapshot.created_at || "",
            source: "snapshot" as const,
            snapshot,
          };
        })
        .filter((item): item is HistoryItem => Boolean(item));

      const snapshotRecordIds = new Set(
        snapshots
          .map((snapshot) => snapshot.source_record_id)
          .filter((id): id is number => typeof id === "number")
      );
      const analysisRows = analysisRes
        .filter((item) => !snapshotRecordIds.has(item.id))
        .map((item) => ({ ...item, scores: normalizeScores(item.scores), source: "analysis" as const }));

      setHistory([...snapshotRows, ...analysisRows].sort((a, b) => {
        const aTime = a.created_at ? new Date(a.created_at).getTime() : 0;
        const bTime = b.created_at ? new Date(b.created_at).getTime() : 0;
        return bTime - aTime;
      }));
    } catch {
      toast.error("加载历史记录失败");
    } finally {
      setHistoryLoading(false);
    }
  };

  const loadSnapshotAsAnalysis = (snapshot: ActionSnapshot) => {
    const output = snapshot.output_snapshot as any;
    if (output?.my_product && Array.isArray(output?.competitors)) {
      toast.warning("旧版竞品对比快照已归档，本页仅保留单个竞品拆解快照。");
      return;
    }
    const scores = getEffectiveScores(output || {});
    if (output?.asin && hasAnyScore(scores)) {
      const loaded = sanitizeAnalysisKeywords(output as AnalysisResult);
      setSingleResult(loaded);
      setSingleAsin(loaded.asin || "");
      setExpandedReport(false);
      setActiveTab("single");
      if (isIncompleteSavedResult(loaded)) {
        toast.warning("这是旧残缺快照，未调用AI；请点击开始分析重新抓取完整数据");
      } else {
        toast.success("已打开已保存竞品诊断快照，未调用AI");
      }
      return;
    }
    toast.error("该快照不是完整竞品诊断结果，请从分析历史打开");
  };

  const viewHistorySnapshot = (item: HistoryItem) => {
    if (item.snapshot) {
      loadSnapshotAsAnalysis(item.snapshot);
      return;
    }
    const snapshot: AnalysisResult = {
      asin: item.asin,
      marketplace: item.marketplace,
      product_title: item.product_title || item.asin,
      product_data: {
        title: item.product_title || item.asin,
        _data_source: "saved_history_snapshot",
        data_notes: "历史快照：只读取已保存评分，不重新抓取Amazon页面，也不再次调用AI。",
      },
      scores: item.scores,
      analysis_report: {
        scores: item.scores,
        analysis: Object.fromEntries(DIMENSIONS.map((dim) => [dim.key, "来自历史快照的已保存评分。"])) as Record<string, string>,
        overall_summary: "这是已保存的竞品诊断快照，查看时不会重新抓取或调用AI。",
        improvement_suggestions: ["如需最新市场数据，请手动点击开始分析生成新一轮记录。"],
      },
      data_source: "saved_history_snapshot",
      id: item.id,
    };
    setSingleResult(snapshot);
    setSingleAsin(item.asin || "");
    setExpandedReport(false);
    setActiveTab("single");
    toast.warning("已加载简略历史评分，未调用AI；如需完整拆解请重新抓取分析");
  };

  if (authLoading) {
    return (
      <div className="flex h-screen bg-gray-50 text-gray-900">
        <AppSidebar />
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-6xl mx-auto px-6 py-8">
            <div className="mb-8 space-y-3">
              <div className="h-8 w-80 max-w-full rounded-lg bg-gray-100 animate-pulse" />
              <div className="h-4 w-[520px] max-w-full rounded-lg bg-gray-100 animate-pulse" />
            </div>
            <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
              <div className="mb-5 h-12 rounded-lg bg-gray-100 animate-pulse" />
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-24 rounded-lg bg-gray-100 animate-pulse" />
                ))}
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-6 py-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold bg-gradient-to-r from-brand-400 to-gold-400 bg-clip-text text-transparent">
              输入竞品 ASIN，拆解它为什么卖得好
            </h1>
            <p className="text-gray-500 mt-1">
              系统会分析竞品的标题、五点、图片、A+、评论、关键词和价格销量表现，帮你判断它真正带来点击和转化的原因。
            </p>
          </div>

          <PageHeader
            objective="拆解竞品Listing为什么卖得好，提炼我方可借鉴动作"
            inputSource="竞品ASIN/Amazon链接、标题、五点、主图/副图、A+、评论、关键词、价格和销量表现"
            process="按Listing结构、Rufus/COSMO语义、评论反向验证和价格销量信号拆解转化原因"
            outputTarget="竞品核心优势、广告转化拆解、关键词结构、评论痛点、可借鉴动作和不建议模仿点"
            action="把可借鉴动作带回本品诊断或上新检测"
            feedback="保存竞品诊断快照，沉淀到关键词库、竞品库和后续数据回流"
            tone="violet"
          />

          {/* Marketplace Selector */}
          <div className="flex items-center gap-2 mb-6">
            <span className="text-sm text-gray-500">站点：</span>
            <div className="flex gap-2">
              {MARKETPLACE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setMarketplace(opt.value)}
                  title={`抓取 ${opt.domain} 的竞品页面`}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                    marketplace === opt.value
                      ? "bg-brand-100 text-brand-600 border border-brand-200"
                      : "bg-gray-50 text-gray-500 border border-gray-100 hover:bg-brand-50"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <Tabs
            value={activeTab}
            onValueChange={(value) => {
              setActiveTab(value);
              if (value === "history") void loadHistory();
            }}
          >
            <TabsList className="bg-gray-50 border border-gray-200 mb-6">
              <TabsTrigger value="single" className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600">
                <Search className="w-4 h-4 mr-2" />
                竞品Listing分析
              </TabsTrigger>
              <TabsTrigger
                value="history"
                className="data-[state=active]:bg-brand-100 data-[state=active]:text-brand-600"
              >
                <History className="w-4 h-4 mr-2" />
                分析历史
              </TabsTrigger>
            </TabsList>

            {/* Single Analysis */}
            <TabsContent value="single" className="space-y-6">
              <Card className="bg-gray-50 border-gray-200">
                <CardContent className="pt-6">
                  <div className="flex gap-3">
                    <Input
                      placeholder="输入10位ASIN或Amazon商品详情页链接（/dp/ASIN）；搜索页请先点进具体商品"
                      value={singleAsin}
                      onChange={(e) => setSingleAsin(e.target.value)}
                      className="bg-gray-50 border-gray-200 text-gray-900 placeholder:text-gray-400 font-mono"
                    />
                    <Button
                      onClick={() => handleAnalyze()}
                      disabled={analyzing}
                      className="bg-brand-700 hover:bg-brand-600 text-white min-w-[120px] disabled:bg-brand-200 disabled:text-brand-700"
                    >
                      {analyzing ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          分析中...
                        </>
                      ) : (
                        <>
                          <Zap className="w-4 h-4 mr-2" />
                          开始分析
                        </>
                      )}
                    </Button>
                  </div>
                  {analyzing && (
                    <div className="mt-4 space-y-2">
                      <div className="flex items-center gap-2 text-sm text-brand-600">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        {analyzeProgress || "正在获取Amazon真实数据并生成8D+2评分，请稍候..."}
                      </div>
                      <p className="text-xs text-gray-500 pl-6">
                        💡 AI深度分析通常需要20-40秒，请耐心等待。
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Unanalyzed state */}
              {!singleResult && !analyzing && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    {[
                      ["看标题", "它靠哪些词获得搜索匹配"],
                      ["看图片", "它靠什么提升点击和理解"],
                      ["看评论", "用户真正喜欢和抱怨什么"],
                      ["看策略", "我方该学什么、避开什么"],
                    ].map(([title, desc]) => (
                      <Card key={title} className="bg-white border-gray-200">
                        <CardContent className="p-5">
                          <h3 className="text-base font-semibold text-gray-900">{title}</h3>
                          <p className="text-sm text-gray-500 mt-2 leading-relaxed">{desc}</p>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                  <Card className="bg-brand-50 border-brand-100">
                    <CardContent className="p-5">
                      <h3 className="text-base font-semibold text-gray-900 mb-3">分析完成后你将得到：</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-gray-600">
                        {[
                          "竞品卖得好的核心原因",
                          "标题、图片、五点、A+的关键拆解",
                          "可借鉴的卖点和关键词",
                          "不建议模仿的风险点",
                          "我方下一步优化方向",
                        ].map((item) => (
                          <div key={item} className="flex items-center gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-brand-500" />
                            {item}
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}

              {singleResult && <SingleResultView result={singleResult} expanded={expandedReport} setExpanded={setExpandedReport} />}
            </TabsContent>

            {/* History */}
            <TabsContent value="history" className="space-y-4">
              <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                分析历史已合并自动保存快照，点击查看只读取本地数据库，不会重新抓取页面或再次调用 AI。
              </div>
              {historyLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin text-brand-600" />
                </div>
              ) : history.length === 0 ? (
                <Card className="bg-gray-50 border-gray-200">
                  <CardContent className="py-12 text-center text-gray-500">
                    <History className="w-10 h-10 mx-auto mb-3 opacity-40" />
                    <p>暂无分析历史或自动保存快照</p>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid gap-3">
                  {history.map((item) => (
                    <Card key={item.id} className="bg-gray-50 border-gray-200">
                      <CardContent className="py-4 flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <Badge variant="outline" className="font-mono text-brand-600 border-brand-200">
                            {item.asin}
                          </Badge>
                          <span className="text-sm text-gray-600 truncate max-w-[300px]">
                            {item.product_title || "—"}
                          </span>
                          <Badge variant="secondary" className="text-xs">
                            {item.marketplace}
                          </Badge>
                          <Badge variant="outline" className="text-xs border-emerald-200 text-emerald-700">
                            {item.source === "snapshot" ? "完整快照" : "简略历史"}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className="text-sm font-semibold text-brand-600">
                            均分: {getAvgScore(item.scores)}
                          </span>
                          <span className="text-xs text-gray-500">
                            {item.created_at ? new Date(item.created_at).toLocaleString("zh-CN") : ""}
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => viewHistorySnapshot(item)}
                            className="h-8 border-gray-200 text-gray-600 hover:text-brand-600"
                          >
                            查看快照
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>

          <NextStepActions
            actions={[
              { label: "进入本品诊断", path: "/listing-diagnosis", variant: "default" },
            ]}
          />
        </div>
      </main>
    </div>
  );
}

/* ---- Sub-components ---- */

function DataSourceBadge({ source }: { source?: string; confidence?: string }) {
  if (source === "incomplete_saved_snapshot" || source === "saved_history_snapshot" || source?.includes("saved")) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/15 text-amber-700 border border-amber-500/25">
        <History className="w-3 h-3" /> 已保存快照
      </span>
    );
  }
  if (source === "browser_proxy") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/15 text-emerald-600 border border-emerald-500/20">
        <Globe className="w-3 h-3" /> 浏览器代理抓取（高准确度）
      </span>
    );
  }
  if (source === "amazon_scrape" || source === "amazon_scrape_httpx" || source === "amazon_scrape_browser") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/15 text-emerald-600 border border-emerald-500/20">
        <Globe className="w-3 h-3" /> Amazon实时数据
      </span>
    );
  }
  // All results should be from real data; this fallback should not normally appear
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/15 text-emerald-600 border border-emerald-500/20">
      <Globe className="w-3 h-3" /> 真实数据分析
    </span>
  );
}

/* ---- Sub-tab navigation for single result ---- */

const RESULT_TABS = [
  { key: "overview", label: "总览", icon: Search },
  { key: "score", label: "竞品评分", icon: Target },
  { key: "listing-breakdown", label: "广告转化拆解", icon: FileText },
  { key: "keywords", label: "关键词结构", icon: Zap },
  { key: "review-pain", label: "评论痛点", icon: MessageSquare },
  { key: "strategy", label: "借鉴策略", icon: AlertCircle },
] as const;

type ResultTabKey = (typeof RESULT_TABS)[number]["key"];

function SingleResultView({
  result,
  expanded,
  setExpanded,
}: {
  result: AnalysisResult;
  expanded: boolean;
  setExpanded: (v: boolean) => void;
}) {
  const [resultTab, setResultTab] = useState<ResultTabKey>("overview");
  const scores = getEffectiveScores(result);
  const scorePayloadMissing = !hasAnyScore(scores);
  const radarData = scoresToRadarData(result.asin, scores, 0);
  const avgScore = getAvgScore(scores);
  const report = result.analysis_report;
  const pd = result.product_data;
  const dataSource = result.data_source || (pd as Record<string, unknown>)._data_source as string || "unknown";
  const incompleteSnapshot = isIncompleteSavedResult(result);
  const effectiveDataSource = incompleteSnapshot ? "incomplete_saved_snapshot" : dataSource;
  const isScraped = !incompleteSnapshot && (dataSource === "amazon_scrape" || dataSource === "amazon_scrape_httpx" || dataSource === "amazon_scrape_browser" || dataSource === "browser_proxy");
  const dataConfidence = (pd as Record<string, unknown>).data_confidence as string || (isScraped ? "high" : "medium");
  const analysisMode = String((report as Record<string, unknown> | undefined)?.analysis_mode || "");
  const fallbackReason = String((report as Record<string, unknown> | undefined)?.fallback_reason || "");
  const isRuleFallback = analysisMode === "rule_fallback" || Boolean(fallbackReason);
  const displayKeywords = getDisplayKeywords(pd, pd.title || result.product_title || "");
  const listingBreakdown = report?.listing_breakdown || fallbackListingBreakdown(pd, displayKeywords);
  const platformEcoRisk = hasPlatformEcoRisk(pd);
  const ratingHistogram = normalizeRatingHistogram(pd.rating_histogram);
  const compliance = result.amazon_compliance || report?.amazon_compliance;

  return (
    <div className="space-y-6">
      {/* Data Source Info */}
      {isScraped && (
        <div className="flex items-start gap-3 p-3 rounded-lg bg-emerald-50 border border-emerald-500/20">
          <Globe className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-emerald-600">数据来源：Amazon真实页面数据</p>
            <p className="text-xs text-emerald-600/70 mt-0.5">
              产品数据来自浏览器代理抓取Amazon真实页面，评分基于真实数据分析。
            </p>
          </div>
        </div>
      )}
      {incompleteSnapshot && (
        <div className="flex items-start gap-3 p-3 rounded-lg bg-amber-50 border border-amber-500/25">
          <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-700">这是旧残缺快照，不是完整抓取结果</p>
            <p className="text-xs text-amber-700/80 mt-0.5">
              当前快照缺少标题、价格、评分、评论、五点或图片等核心原始数据。系统没有重新调用AI，请回填ASIN后点击“开始分析”重新抓取完整页面。
            </p>
          </div>
        </div>
      )}
      {isRuleFallback && !incompleteSnapshot && (
        <div className="flex items-start gap-3 p-3 rounded-lg bg-amber-50 border border-amber-500/25">
          <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-700">当前为规则兜底诊断，不是完整AI深度评分</p>
            <p className="text-xs text-amber-700/80 mt-0.5">
              {fallbackReason || "AI模型调用或JSON解析失败，系统基于已抓取字段生成保守评分。建议稍后重新运行AI深度诊断。"}
            </p>
          </div>
        </div>
      )}
      {platformEcoRisk && !incompleteSnapshot && (
        <div className="flex items-start gap-3 p-3 rounded-lg bg-red-50 border border-red-500/20">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-700">平台生态强绑定风险</p>
            <p className="text-xs text-red-700/80 mt-0.5">
              该商品可能属于Amazon自营或 Echo/Alexa/Fire/Kindle 等平台生态入口，适合拆解学习，不建议作为普通第三方卖家直接切入标的。
            </p>
          </div>
        </div>
      )}

      {/* ===== Sub-Tab Navigation Bar ===== */}
      <div className="flex items-center gap-1 p-1 bg-gray-50 border border-gray-200 rounded-xl overflow-x-auto">
        {RESULT_TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = resultTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setResultTab(tab.key)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                isActive
                  ? "bg-brand-100 text-brand-600 shadow-sm shadow-brand-100"
                  : "text-gray-500 hover:text-gray-600 hover:bg-gray-100"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ===== Tab Content ===== */}

      {/* --- 总览 Tab --- */}
      {resultTab === "overview" && (
        <>
          {/* Product Info + Radar */}
          <div className="grid grid-cols-1 gap-6">
            <Card className="bg-gray-50 border-gray-200">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Badge variant="outline" className="font-mono text-brand-600 border-brand-200">
                    {result.asin}
                  </Badge>
                  产品信息
                  <DataSourceBadge source={effectiveDataSource} confidence={dataConfidence} />
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <span className="text-sm text-gray-500">标题：</span>
                  <span className="text-sm text-gray-600">{pd.title || result.product_title}</span>
                </div>
                {/* Official Amazon Bought Count - Prominent Display */}
                {(pd.bought_count || pd.amazon_bought_count) && (
                  <div className="bg-amber-50 border border-amber-500/25 rounded-lg p-3 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
                      <TrendingUp className="w-5 h-5 text-amber-600" />
                    </div>
                    <div>
                      <div className="text-xs text-amber-600/80 font-medium">Amazon官方购买人数</div>
                      <div className="text-lg font-bold text-amber-600">
                        {pd.bought_count || pd.amazon_bought_count}
                      </div>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <InfoItem label="品牌" value={pd.brand} />
                  <InfoItem label="类目" value={pd.category} />
                  <InfoItem label="价格" value={formatPrice(pd)} />
                  <InfoItem label="评分" value={pd.rating ? `${pd.rating} ⭐` : undefined} />
                  <InfoItem label="评论数" value={pd.review_count} />
                  <InfoItem label="上架时间" value={pd.date_first_available || pd.launch_date} />
                  <InfoItem label="BSR排名" value={pd.bsr_rank ? `#${pd.bsr_rank}` : undefined} />
                  <InfoItem label="卖家类型" value={pd.seller_type} />
                  <InfoItem
                    label="BSR预估月销"
                    value={pd.estimated_monthly_sales ? `${pd.estimated_monthly_sales}（仅供参考）` : undefined}
                  />
                  <InfoItem label="预估月收入" value={pd.estimated_monthly_revenue ? `$${pd.estimated_monthly_revenue}` : undefined} />
                  <InfoItem label="主图数量" value={pd.image_count} />
                  <InfoItem label="视频" value={pd.has_video ? "✅ 有" : "❌ 无"} />
                  <InfoItem label="A+" value={pd.has_a_plus ? `✅ 有${pd.aplus_image_count ? `（${pd.aplus_image_count}张图）` : ""}` : "❌ 无"} />
                </div>
                {pd.bullet_points && pd.bullet_points.length > 0 && (
                  <div>
                    <span className="text-sm text-gray-500 block mb-1">五点描述：</span>
                    <ul className="text-xs text-gray-600 space-y-1">
                      {pd.bullet_points.map((bp, i) => (
                        <li key={i} className="flex gap-1">
                          <span className="text-brand-600">•</span> {bp}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {displayKeywords.length > 0 && (
                  <div>
                    <span className="text-sm text-gray-500 block mb-1">Rufus/COSMO关键词：</span>
                    <div className="flex flex-wrap gap-1.5">
                      {displayKeywords.map((kw, i) => (
                        <KeywordBadge key={i} keyword={kw} compact />
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

          </div>

          {/* Report Summary (collapsible) */}
          {report && (
            <Card className="bg-gray-50 border-gray-200">
              <CardHeader>
                <button
                  onClick={() => setExpanded(!expanded)}
                  className="flex items-center justify-between w-full"
                >
                  <CardTitle className="text-lg flex items-center gap-2">
                    <AlertCircle className="w-5 h-5 text-brand-600" />
                    分析报告
                  </CardTitle>
                  {expanded ? <ChevronUp className="w-5 h-5 text-gray-500" /> : <ChevronDown className="w-5 h-5 text-gray-500" />}
                </button>
              </CardHeader>
              {expanded && (
                <CardContent className="space-y-4">
                  {report.overall_summary && (
                    <div>
                      <h4 className="text-sm font-medium text-gray-600 mb-1">总体评价</h4>
                      <p className="text-sm text-gray-500 leading-relaxed">{report.overall_summary}</p>
                    </div>
                  )}
                  {report.improvement_suggestions && report.improvement_suggestions.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium text-gray-600 mb-2">优化建议</h4>
                      <ul className="space-y-1">
                        {report.improvement_suggestions.map((s, i) => (
                          <li key={i} className="text-sm text-gray-500 flex gap-2">
                            <span className="text-brand-600 font-bold">{i + 1}.</span> {s}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </CardContent>
              )}
            </Card>
          )}
        </>
      )}

      {/* --- 竞品评分 Tab --- */}
      {resultTab === "score" && (
        <Card className="bg-gray-50 border-gray-200">
            <CardHeader>
              <CardTitle className="text-lg flex items-center justify-between">
                <span>8D+2评分雷达图</span>
                <span className="text-2xl font-bold text-brand-600">{avgScore}分</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              {scorePayloadMissing && (
                <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                  <div>
                    <p className="font-medium">当前快照缺少8D+2评分数据</p>
                    <p className="mt-1 text-amber-700">这不是Top40搜索快照造成的，请重新运行本竞品诊断或从完整历史记录打开。</p>
                  </div>
                </div>
              )}
              <div className="flex justify-center">
                <RadarChartMulti datasets={[radarData]} size={340} />
              </div>
              <div className="flex flex-wrap gap-2">
                {DIMENSIONS.map((dim) => {
                  const score = (scores as Record<string, number>)[dim.key] || 0;
                  return (
                    <Badge
                      key={dim.key}
                      variant="outline"
                      className={`px-3 py-1 ${
                        score >= 80
                          ? "border-emerald-200 text-emerald-700 bg-emerald-50"
                          : score >= 60
                            ? "border-amber-200 text-amber-700 bg-amber-50"
                            : "border-red-200 text-red-700 bg-red-50"
                      }`}
                    >
                      {dim.label} {score}
                    </Badge>
                  );
                })}
              </div>
            </CardContent>
          </Card>
      )}

      {resultTab === "listing-breakdown" && <ListingBreakdownView breakdown={listingBreakdown} compliance={compliance} />}

      {/* --- 关键词 Tab --- */}
      {resultTab === "keywords" && (
        <Card className="bg-gray-50 border-gray-200">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Zap className="w-5 h-5 text-brand-600" />
              关键词分析
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {displayKeywords.length > 0 ? (
              <>
                <div>
                  <h4 className="text-sm font-medium text-gray-600 mb-2">Rufus/COSMO关键词</h4>
                  <p className="text-xs text-gray-500 mb-3">
                    广告验证优先关系词和状态触发词，属性词只做基础覆盖，避免直接卷入纯价格竞争。
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {displayKeywords.map((kw, i) => (
                      <KeywordBadge key={i} keyword={kw} />
                    ))}
                  </div>
                </div>
                {/* Title keyword analysis */}
                <div>
                  <h4 className="text-sm font-medium text-gray-600 mb-2">标题关键词覆盖</h4>
                  <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
                    <p className="text-sm text-gray-600 leading-relaxed mb-3">{pd.title || result.product_title}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {displayKeywords.map((kw, i) => {
                        const titleLower = (pd.title || result.product_title || "").toLowerCase();
                        const found = titleLower.includes(kw.toLowerCase());
                        return (
                          <span
                            key={i}
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                              found
                                ? "bg-emerald-500/15 text-emerald-600 border border-emerald-500/20"
                                : "bg-red-500/15 text-red-600 border border-red-500/20"
                            }`}
                          >
                            {found ? "✓" : "✗"} {kw}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Zap className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p>暂无关键词数据</p>
                <p className="text-xs mt-1">关键词信息将在抓取到真实Amazon数据时显示</p>
              </div>
            )}
            {/* Keyword score from analysis */}
            {report?.analysis?.functionality && (
              <div>
                <h4 className="text-sm font-medium text-gray-600 mb-2">功能关键词分析</h4>
                <p className="text-xs text-gray-500 leading-relaxed bg-gray-50 rounded-lg p-3 border border-gray-100">
                  {report.analysis.functionality}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* --- 借鉴策略 Tab --- */}
      {resultTab === "strategy" && (
        <Card className="bg-gray-50 border-gray-200">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-brand-600" />
              借鉴策略
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {report?.overall_summary && (
              <div className="bg-brand-50 border border-brand-500/20 rounded-lg p-4">
                <h4 className="text-sm font-semibold text-brand-600 mb-1">总体评价</h4>
                <p className="text-sm text-gray-600 leading-relaxed">{report.overall_summary}</p>
              </div>
            )}

            {report?.improvement_suggestions && report.improvement_suggestions.length > 0 ? (
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-gray-600">我方可借鉴动作</h4>
                {report.improvement_suggestions.map((s, i) => (
                  <div key={i} className="flex gap-3 items-start bg-gray-50 rounded-lg p-4 border border-gray-100">
                    <div className="w-7 h-7 rounded-full bg-brand-100 flex items-center justify-center flex-shrink-0 text-sm font-bold text-brand-600">
                      {i + 1}
                    </div>
                    <p className="text-sm text-gray-600 pt-0.5 leading-relaxed">{s}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p>暂无优化建议</p>
              </div>
            )}

            {displayKeywords.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-600 mb-2">可测试广告词池</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {displayKeywords.slice(0, 8).map((kw, i) => (
                    <div key={i} className="flex items-center justify-between bg-emerald-50 rounded-lg p-3 border border-emerald-100">
                      <span className="text-sm text-gray-700">{kw}</span>
                      <Badge className="bg-emerald-500/15 text-emerald-600 border-emerald-500/20 text-xs">
                        {classifyAmazonKeyword(kw) === "attribute" ? "基础覆盖" : "优先验证"}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Per-dimension weak areas */}
            {(() => {
              const weakDims = DIMENSIONS.filter(
                (d) => ((scores as Record<string, number>)[d.key] || 0) < 70
              );
              if (weakDims.length === 0) return null;
              return (
                <div>
                  <h4 className="text-sm font-medium text-gray-600 mb-2">需重点关注的维度</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {weakDims.map((dim) => {
                      const score = (scores as Record<string, number>)[dim.key] || 0;
                      const analysis = report?.analysis?.[dim.key] || "";
                      return (
                        <div key={dim.key} className="bg-red-500/5 border border-red-500/15 rounded-lg p-3">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-medium text-red-600">{dim.label}</span>
                            <span className="text-sm font-bold text-red-600">{score}分</span>
                          </div>
                          {analysis && <p className="text-xs text-gray-500 leading-relaxed">{analysis}</p>}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })()}
          </CardContent>
        </Card>
      )}

      {/* --- 评论痛点 Tab --- */}
      {resultTab === "review-pain" && (
        <Card className="bg-gray-50 border-gray-200">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-brand-600" />
              评论痛点
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {Object.keys(ratingHistogram).length > 0 || (pd.low_star_reviews && pd.low_star_reviews.length > 0) ? (
              <>
                {Object.keys(ratingHistogram).length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-600 mb-2">评分分布</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-5 gap-2">
                      {[5, 4, 3, 2, 1].map((star) => (
                        <div key={star} className="rounded-lg border border-gray-100 bg-white p-3">
                          <div className="text-xs text-gray-500">{star} star</div>
                          <div className="text-lg font-bold text-gray-900">{ratingHistogram[`${star}_star`] || "—"}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div>
                  <h4 className="text-sm font-medium text-gray-600 mb-2">3星及以下完整评论样本</h4>
                  <div className="space-y-2">
                    {(pd.low_star_reviews || []).slice(0, 12).map((review, i) => (
                      <div key={i} className="rounded-lg border border-red-100 bg-red-50/40 p-3">
                        <div className="flex items-center justify-between gap-3 mb-1">
                          <span className="text-sm font-semibold text-red-600">{String(review.rating || "低分")} star</span>
                          <span className="text-xs text-gray-500">{String(review.date || "")}</span>
                        </div>
                        {review.title && <div className="text-sm font-medium text-gray-800 mb-1">{String(review.title)}</div>}
                        <p className="text-sm text-gray-600 leading-relaxed">{String(review.body || "")}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p>暂无低分评论数据</p>
                <p className="text-xs mt-1">系统会优先抓取评分分布和3星及以下评论作为反向验证证据。</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

    </div>
  );
}

const BREAKDOWN_COMPLIANCE_MODULES: Record<string, string[]> = {
  title: ["TITLE", "PRODUCT_CLAIM"],
  bullets: ["BULLET", "PRODUCT_CLAIM"],
  main_image: ["MAIN_IMAGE"],
  secondary_images: ["SECONDARY_IMAGE", "MAIN_IMAGE"],
  a_plus: ["A_PLUS", "DESCRIPTION", "PRODUCT_CLAIM"],
  review_validation: ["REVIEW_REQUEST"],
};

function getModuleComplianceViolations(moduleKey: string, compliance?: ComplianceResult) {
  const modules = BREAKDOWN_COMPLIANCE_MODULES[moduleKey] || [];
  return (compliance?.violations || [])
    .filter((item) => modules.includes(item.module))
    .sort((a, b) => b.risk_score - a.risk_score)
    .slice(0, 2);
}

function ComplianceInlineNotice({ violations }: { violations: ComplianceViolation[] }) {
  if (violations.length === 0) return null;

  const highest = violations[0];
  const isHard = highest.rule_type === "HARD_BLOCK";
  return (
    <div className={`rounded-lg border p-3 ${isHard ? "bg-red-50 border-red-100" : "bg-amber-50 border-amber-100"}`}>
      <div className="flex items-center gap-2 mb-2">
        <AlertCircle className={`w-4 h-4 ${isHard ? "text-red-600" : "text-amber-600"}`} />
        <span className={`text-xs font-semibold ${isHard ? "text-red-700" : "text-amber-700"}`}>
          检测到可能的亚马逊合规风险
        </span>
      </div>
      <div className="space-y-2">
        {violations.map((item) => (
          <div key={`${item.rule_id}-${item.module}`} className="text-xs text-gray-600 leading-relaxed">
            <span className="font-semibold text-gray-800">{item.category || item.rule_id}：</span>
            {item.suggestion_cn || item.message_cn}
            {item.source_policy && <span className="text-gray-400"> 依据：{item.source_policy}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

function ListingBreakdownView({ breakdown, compliance }: { breakdown: ListingBreakdown; compliance?: ComplianceResult }) {
  const modules = breakdown.modules || [];
  const iconMap: Record<string, typeof FileText> = {
    title: FileText,
    bullets: FileText,
    main_image: ImageIcon,
    secondary_images: ImageIcon,
    a_plus: ImageIcon,
    video_brand: Video,
    review_validation: MessageSquare,
  };

  return (
    <div className="space-y-4">
      <Card className="bg-white border-gray-200">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <TrendingUp className="mt-0.5 h-5 w-5 text-brand-600" />
            <div>
              <h3 className="text-sm font-semibold text-gray-900">竞品广告转化拆解</h3>
              <p className="mt-1 text-sm leading-relaxed text-gray-600">
                按标题、主图、副图、五点、A+和评论拆解其对广告漏斗的影响：标题看流量准不准，主图看点不点击，副图/五点/A+看转不转化，评论看广告承诺能不能被信任。
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {modules.map((module) => {
          const Icon = iconMap[module.key] || FileText;
          const adRead = moduleAdMetricMap(module.key);
          const displayIntents = sameStringList(module.covered_user_intents, module.keywords)
            ? moduleDefaultIntents(module.key)
            : module.covered_user_intents;
          const displayKeywords = cleanEnglishKeywordList(module.keywords, [], module.key);
          const displayStructure = moduleStructureNarrative(module.key, module.structure_breakdown);
          const rawObject = module.raw_content && typeof module.raw_content === "object" && !Array.isArray(module.raw_content)
            ? module.raw_content as Record<string, unknown>
            : null;
          const imageUrlsFromObject = rawObject && Array.isArray(rawObject.images)
            ? rawObject.images.filter((item): item is string => typeof item === "string" && item.startsWith("http"))
            : [];
          const imageUrls = imageUrlsFromObject.length > 0 ? imageUrlsFromObject : Array.isArray(module.raw_content)
            ? module.raw_content.filter((item): item is string => typeof item === "string" && item.startsWith("http"))
            : [];
          const complianceViolations = getModuleComplianceViolations(module.key, compliance);
          return (
            <Card key={module.key} className="bg-gray-50 border-gray-200">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Icon className="w-4 h-4 text-brand-600" />
                  {module.name}
                </CardTitle>
                {module.summary && <p className="text-sm text-gray-600 leading-relaxed">{module.summary}</p>}
              </CardHeader>
              <CardContent className="space-y-4">
                <ComplianceInlineNotice violations={complianceViolations} />
                <div className="rounded-lg border border-brand-100 bg-brand-50 p-3">
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {adRead.metrics.map((metric) => (
                      <span key={metric} className="rounded-full border border-brand-200 bg-white px-2 py-0.5 text-[11px] font-medium text-brand-700">
                        {metric}
                      </span>
                    ))}
                  </div>
                  <p className="text-xs leading-relaxed text-gray-700">{adRead.funnelRole}</p>
                </div>
                {imageUrls.length > 0 && (
                  <div className="flex gap-2 overflow-x-auto pb-1">
                    {imageUrls.slice(0, 8).map((url, idx) => (
                      <img key={idx} src={url} alt={`${module.name} ${idx + 1}`} className="h-20 w-20 rounded-lg border border-gray-200 object-contain bg-white" />
                    ))}
                  </div>
                )}
                <OriginalEvidencePreview raw={module.raw_content} moduleName={module.name} />
                <BreakdownSection title="广告指标判断" items={[adRead.strengthMeaning, adRead.weaknessMeaning]} tone="blue" />
                <BreakdownSection title="结构拆解" items={displayStructure} />
                <BreakdownSection title="强项判断" items={module.strengths} tone="green" />
                <BreakdownSection title="弱项判断" items={module.weaknesses} tone="red" />
                <BreakdownSection title="覆盖的用户意图" items={displayIntents} badge />
                <BreakdownSection title="对应关键词/语义词" items={displayKeywords} badge />
                <BreakdownSection title="我方广告打法" items={[adRead.attackAngle, ...(module.borrowable_actions || [])]} tone="blue" />
                <BreakdownSection title="不建议模仿点" items={module.do_not_copy} tone="amber" />
                <details className="rounded-lg border border-gray-100 bg-white p-3">
                  <summary className="cursor-pointer text-sm font-medium text-gray-600">展开查看原始内容</summary>
                  <pre className="mt-3 whitespace-pre-wrap text-xs leading-relaxed text-gray-500 max-h-60 overflow-auto">
                    {formatRawContent(module.raw_content)}
                  </pre>
                </details>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function OriginalEvidencePreview({ raw, moduleName }: { raw: unknown; moduleName: string }) {
  const emptyText = "本次快照未保存该模块原始内容，需要重新抓取生成完整快照。";
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
    <div className={`rounded-lg border p-3 ${hasEvidence ? "bg-white border-gray-100" : "bg-amber-50 border-amber-100"}`}>
      <div className="flex items-center justify-between gap-3 mb-2">
        <h4 className="text-xs font-semibold text-gray-500">原始内容 / 证据预览</h4>
        {imageUrls.length > 0 && <span className="text-[11px] text-brand-600">{imageUrls.length} 张图片证据</span>}
      </div>
      {imageUrls.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-2">
          {imageUrls.slice(0, 10).map((url, idx) => (
            <img key={idx} src={url} alt={`${moduleName} evidence ${idx + 1}`} className="h-16 w-16 rounded-md border border-gray-200 object-contain bg-white" />
          ))}
        </div>
      )}
      {previewText ? (
        <pre className="whitespace-pre-wrap text-xs leading-relaxed text-gray-600 max-h-40 overflow-auto">{previewText}</pre>
      ) : (
        <p className="text-xs leading-relaxed text-amber-700">{emptyText}</p>
      )}
    </div>
  );
}

function BreakdownSection({
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
    .map((item) => isKeywordSection ? normalizeAmazonKeyword(item) : String(item || "").trim())
    .filter((item) => item && !seen.has(item) && seen.add(item));
  if (clean.length === 0) return null;
  const toneClass = {
    gray: "text-gray-600 bg-gray-50 border-gray-100",
    green: "text-emerald-700 bg-emerald-50 border-emerald-100",
    red: "text-red-700 bg-red-50 border-red-100",
    blue: "text-brand-700 bg-brand-50 border-brand-100",
    amber: "text-amber-700 bg-amber-50 border-amber-100",
  }[tone];
  return (
    <div>
      <h4 className="text-xs font-semibold text-gray-500 mb-2">{title}</h4>
      {badge ? (
        <div className="flex flex-wrap gap-1.5">
          {clean.map((item, i) => (
            <span key={i} className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${toneClass}`}>
              {item}
            </span>
          ))}
        </div>
      ) : (
        <div className="space-y-1.5">
          {clean.map((item, i) => (
            <div key={i} className={`rounded-lg border px-3 py-2 text-xs leading-relaxed ${toneClass}`}>
              {item}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value?: string }) {
  return (
    <div>
      <span className="text-gray-500">{label}：</span>
      <span className="text-gray-600">{value || "—"}</span>
    </div>
  );
}
