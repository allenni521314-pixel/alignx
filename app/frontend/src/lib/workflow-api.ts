/**
 * Centralized workflow API for cross-module data flow.
 * Connects all AlignX modules into a closed-loop data pipeline.
 */
import { client } from "@/lib/api";
import { withRetry } from "@/lib/api-retry";
import { getAuthHeaders } from "@/lib/auth-headers";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface CompetitorInsight {
  id?: number;
  product_id: number;
  competitor_asin: string;
  strengths?: string;
  weaknesses?: string;
  gaps?: string;
  suggestions?: string;
  radar_scores?: string;
  created_at?: string;
}

export interface HealthReport {
  id?: number;
  product_id: number;
  total_score?: number;
  grade?: string;
  title_score?: number;
  keyword_score?: number;
  bullet_score?: number;
  aplus_score?: number;
  review_score?: number;
  suggestions?: string;
}

export interface AdRecommendation {
  id?: number;
  product_id: number;
  recommendation_type: string;
  content?: string;
}

export interface ListingDiagnosis {
  id?: number;
  listing_title: string;
  marketplace?: string;
  diagnosis_report?: string;
  keyword_report?: string;
  score_function_expression?: number;
  score_scenario_expression?: number;
  score_identity_fit?: number;
  score_psychology_benefit?: number;
  score_risk_elimination?: number;
  score_product_identity?: number;
  score_compatibility?: number;
  score_subjective_properties?: number;
  score_differentiation?: number;
  score_market_trend?: number;
}

export type LifecycleStage =
  | "discovery"
  | "semantic"
  | "strategy"
  | "verification"
  | "optimization";

export const LIFECYCLE_LABELS: Record<LifecycleStage, string> = {
  discovery: "① 选品决策",
  semantic: "② Listing上新检测",
  strategy: "③ 上线后诊断",
  verification: "④ 广告投放验证",
  optimization: "⑤ 复盘优化",
};

export const LIFECYCLE_PATHS: Record<LifecycleStage, string> = {
  discovery: "/asin-manager",
  semantic: "/listing-launch-check",
  strategy: "/listing-diagnosis",
  verification: "/ad-analytics?view=validation",
  optimization: "/optimization-suggestions?view=next-round",
};

/* ------------------------------------------------------------------ */
/*  Competitor Insights                                                */
/* ------------------------------------------------------------------ */

export async function saveCompetitorInsight(
  data: Omit<CompetitorInsight, "id">
): Promise<CompetitorInsight | null> {
  try {
    const res = await withRetry(() =>
      client.entities.competitor_insights.create({
        product_id: data.product_id,
        competitor_asin: data.competitor_asin,
        strengths: data.strengths || "",
        weaknesses: data.weaknesses || "",
        gaps: data.gaps || "",
        suggestions: data.suggestions || "",
        radar_scores: data.radar_scores || "",
      })
    );
    return res?.data || null;
  } catch (e) {
    console.error("Failed to save competitor insight:", e);
    return null;
  }
}

export async function getCompetitorInsights(
  productId: number
): Promise<CompetitorInsight[]> {
  try {
    const res = await withRetry(() =>
      client.entities.competitor_insights.query({
        query: { product_id: productId },
        sort: "-created_at",
        limit: 20,
      })
    );
    return res?.data?.items || [];
  } catch (e) {
    console.error("Failed to fetch competitor insights:", e);
    return [];
  }
}

/* ------------------------------------------------------------------ */
/*  Health Reports                                                     */
/* ------------------------------------------------------------------ */

export async function getHealthReportForProduct(
  productId: number
): Promise<HealthReport | null> {
  try {
    const res = await withRetry(() =>
      client.entities.health_reports.query({
        query: { product_id: productId },
        sort: "-created_at",
        limit: 1,
      })
    );
    const items = res?.data?.items || [];
    return items.length > 0 ? items[0] : null;
  } catch (e) {
    console.error("Failed to fetch health report:", e);
    return null;
  }
}

export async function getAllHealthReports(
  limit = 100
): Promise<HealthReport[]> {
  try {
    const res = await withRetry(() =>
      client.entities.health_reports.query({
        sort: "-created_at",
        limit,
      })
    );
    return res?.data?.items || [];
  } catch (e) {
    console.error("Failed to fetch health reports:", e);
    return [];
  }
}

/* ------------------------------------------------------------------ */
/*  Ad Recommendations                                                 */
/* ------------------------------------------------------------------ */

export async function getAdRecommendationsForProduct(
  productId: number
): Promise<AdRecommendation[]> {
  try {
    const res = await withRetry(() =>
      client.entities.ad_recommendations.query({
        query: { product_id: productId },
        sort: "-created_at",
        limit: 20,
      })
    );
    return res?.data?.items || [];
  } catch (e) {
    console.error("Failed to fetch ad recommendations:", e);
    return [];
  }
}

export async function getAllAdRecommendations(
  limit = 100
): Promise<AdRecommendation[]> {
  try {
    const res = await withRetry(() =>
      client.entities.ad_recommendations.query({
        sort: "-created_at",
        limit,
      })
    );
    return res?.data?.items || [];
  } catch (e) {
    console.error("Failed to fetch ad recommendations:", e);
    return [];
  }
}

/* ------------------------------------------------------------------ */
/*  Listing Diagnoses                                                  */
/* ------------------------------------------------------------------ */

export async function getListingDiagnoses(
  limit = 50
): Promise<ListingDiagnosis[]> {
  try {
    const res = await withRetry(() =>
      client.entities.listing_diagnoses.query({
        sort: "-created_at",
        limit,
      })
    );
    return res?.data?.items || [];
  } catch (e) {
    console.error("Failed to fetch listing diagnoses:", e);
    return [];
  }
}

/* ------------------------------------------------------------------ */
/*  Product Lifecycle                                                  */
/* ------------------------------------------------------------------ */

export async function updateProductLifecycle(
  productId: number,
  stage: LifecycleStage,
  round?: number
): Promise<boolean> {
  try {
    const updateData: Record<string, unknown> = { lifecycle_stage: stage };
    if (round !== undefined) updateData.optimization_round = round;
    await withRetry(() =>
      client.entities.products.update({ id: productId, ...updateData })
    );
    return true;
  } catch (e) {
    console.error("Failed to update product lifecycle:", e);
    return false;
  }
}

export async function getAllProducts(limit = 50) {
  try {
    const res = await withRetry(() =>
      client.entities.products.query({ sort: "-created_at", limit })
    );
    return res?.data?.items || [];
  } catch (e) {
    console.error("Failed to fetch products:", e);
    return [];
  }
}

/* ------------------------------------------------------------------ */
/*  Judgment Feedback / Learning Memory                                */
/* ------------------------------------------------------------------ */

export interface JudgmentFeedbackRound {
  id: number;
  product_id?: number | null;
  asin?: string | null;
  optimization_round: number;
  stage: string;
  status: string;
  diagnosis_issue?: string;
  judgment_basis?: unknown;
  suggested_action?: string;
  ad_validation_plan?: unknown;
  before_snapshot?: unknown;
  after_snapshot?: unknown;
  ad_result?: {
    primary_validation?: {
      hypothesis_id?: string;
      keyword_group_id?: string;
      optimization_round?: number;
    };
    [key: string]: unknown;
  };
  hit_status?: string;
  miss_reason?: string;
  next_iteration?: string;
}

interface FeedbackRoundPayload {
  product_id?: number | null;
  asin?: string;
  marketplace?: string;
  optimization_round: number;
  stage: string;
  status: string;
  diagnosis_issue?: string;
  judgment_basis?: unknown;
  suggested_action?: string;
  ad_validation_plan?: unknown;
  before_snapshot?: unknown;
  after_snapshot?: unknown;
  ad_result?: JudgmentFeedbackRound["ad_result"];
  hit_status?: string;
  miss_reason?: string;
  next_iteration?: string;
  confidence_before?: number;
  confidence_after?: number;
  executed_at?: string;
}

function sameValidationRound(round: JudgmentFeedbackRound, payload: FeedbackRoundPayload) {
  const current = round.ad_result?.primary_validation || {};
  const next = payload.ad_result?.primary_validation || {};
  return (
    round.stage === payload.stage &&
    Number(round.optimization_round || 1) === Number(payload.optimization_round || 1) &&
    String(current.hypothesis_id || "") === String(next.hypothesis_id || "") &&
    String(current.keyword_group_id || "") === String(next.keyword_group_id || "")
  );
}

export async function listJudgmentFeedbackRounds(params: {
  productId?: number;
  asin?: string;
  limit?: number;
}): Promise<JudgmentFeedbackRound[]> {
  try {
    const search = new URLSearchParams();
    if (params.productId) search.set("product_id", String(params.productId));
    if (params.asin) search.set("asin", params.asin);
    search.set("limit", String(params.limit || 100));
    const res = await fetch(`/api/v1/judgment-system/listing/feedback-rounds?${search.toString()}`, {
      headers: getAuthHeaders(),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || "Failed to load feedback rounds");
    return data?.items || [];
  } catch (e) {
    console.error("Failed to fetch judgment feedback rounds:", e);
    return [];
  }
}

export async function upsertAdValidationFeedbackRound(payload: FeedbackRoundPayload): Promise<boolean> {
  try {
    const rounds = await listJudgmentFeedbackRounds({
      productId: payload.product_id || undefined,
      asin: payload.asin,
      limit: 100,
    });
    const existing = rounds.find((round) => sameValidationRound(round, payload));
    const url = existing
      ? `/api/v1/judgment-system/listing/feedback-rounds/${existing.id}`
      : "/api/v1/judgment-system/listing/feedback-rounds";
    const res = await fetch(url, {
      method: existing ? "PATCH" : "POST",
      headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data?.detail || "Failed to save feedback round");
    }
    return true;
  } catch (e) {
    console.error("Failed to upsert ad validation feedback round:", e);
    return false;
  }
}

/* ------------------------------------------------------------------ */
/*  Dashboard Aggregation                                              */
/* ------------------------------------------------------------------ */

export interface DashboardStats {
  totalProducts: number;
  needOptimization: number;
  verifyingCount: number;
  completedRounds: number;
  products: Array<{
    id: number;
    asin: string;
    title: string;
    category: string;
    price: number;
    rating: number;
    review_count: number;
    lifecycle_stage?: string;
    optimization_round?: number;
  }>;
  healthReports: HealthReport[];
  adRecommendations: AdRecommendation[];
  suggestions: Array<{ text: string; action: string; path: string }>;
  feedbackItems: Array<{
    text: string;
    type: "cosmo" | "listing" | "ad";
  }>;
}

export async function loadDashboardData(): Promise<DashboardStats> {
  const [products, healthReports, adRecs, competitorInsights] =
    await Promise.all([
      getAllProducts(50),
      getAllHealthReports(100),
      getAllAdRecommendations(100),
      withRetry(() =>
        client.entities.competitor_insights.query({
          sort: "-created_at",
          limit: 100,
        })
      )
        .then((r) => r?.data?.items || [])
        .catch(() => []),
    ]);

  const totalProducts = products.length;

  // Products with low health grades need optimization
  const needOptimization = healthReports.filter(
    (h: HealthReport) =>
      h.grade === "C" || h.grade === "D" || h.grade === "F"
  ).length;

  // Products in verification stage
  const verifyingCount = products.filter(
    (p: { lifecycle_stage?: string }) => p.lifecycle_stage === "verification"
  ).length;

  // Max optimization round across all products
  const completedRounds =
    products.length > 0
      ? Math.max(
          ...products.map(
            (p: { optimization_round?: number }) => p.optimization_round || 0
          ),
          0
        )
      : 0;

  // Generate smart suggestions based on real data
  const suggestions: DashboardStats["suggestions"] = [];

  // Check for products without health reports
  const productIdsWithHealth = new Set(
    healthReports.map((h: HealthReport) => h.product_id)
  );
  const productsWithoutHealth = products.filter(
    (p: { id: number }) => !productIdsWithHealth.has(p.id)
  );
  if (productsWithoutHealth.length > 0) {
    suggestions.push({
      text: `${productsWithoutHealth.length} 个商品尚未进行 Listing 诊断`,
      action: "去诊断",
      path: "/listing-diagnosis",
    });
  }

  if (products.length > 0) {
    suggestions.push({
      text: `${products.length} 个商品可进入上新检测确认表达和风险`,
      action: "去检测",
      path: "/listing-launch-check",
    });
  }

  // Check for products without competitor insights
  const productIdsWithComp = new Set(
    competitorInsights.map((c: { product_id: number }) => c.product_id)
  );
  const productsWithoutComp = products.filter(
    (p: { id: number }) => !productIdsWithComp.has(p.id)
  );
  if (productsWithoutComp.length > 0) {
    suggestions.push({
      text: `${productsWithoutComp.length} 个商品未进行竞品对比分析`,
      action: "去对比",
      path: "/competitor-analysis?tab=strategy",
    });
  }

  // Check for low-grade health reports needing ad verification
  const lowGradeProducts = healthReports.filter(
    (h: HealthReport) => h.grade === "C" || h.grade === "D"
  );
  const productIdsWithAdRec = new Set(
    adRecs.map((a: AdRecommendation) => a.product_id)
  );
  const needVerification = lowGradeProducts.filter(
    (h: HealthReport) => !productIdsWithAdRec.has(h.product_id)
  );
  if (needVerification.length > 0) {
    suggestions.push({
      text: `${needVerification.length} 个低分商品需要广告验证策略`,
      action: "去验证",
      path: "/ad-analytics?view=validation",
    });
  }

  // Fallback suggestions if no data-driven ones
  if (suggestions.length === 0) {
    if (totalProducts === 0) {
      suggestions.push({
        text: "添加第一个 ASIN 开始分析",
        action: "去添加",
        path: "/asin-manager",
      });
    } else {
      suggestions.push({
        text: "从机会池进入上新检测，启动下一轮验证",
        action: "去检测",
        path: "/listing-launch-check",
      });
    }
  }

  // Generate feedback items based on recent data
  const feedbackItems: DashboardStats["feedbackItems"] = [];
  if (healthReports.length > 0) {
    const avgScore =
      healthReports.reduce(
        (sum: number, h: HealthReport) => sum + (h.total_score || 0),
        0
      ) / healthReports.length;
    feedbackItems.push({
      text: `Listing 平均健康分 ${Math.round(avgScore)} 分`,
      type: "listing",
    });
  }
  if (adRecs.length > 0) {
    feedbackItems.push({
      text: `已生成 ${adRecs.length} 条广告优化建议`,
      type: "ad",
    });
  }
  if (competitorInsights.length > 0) {
    feedbackItems.push({
      text: `已分析 ${competitorInsights.length} 个竞品洞察`,
      type: "cosmo",
    });
  }
  // Fallback
  if (feedbackItems.length === 0) {
    feedbackItems.push({
      text: "暂无验证数据，开始第一轮分析吧",
      type: "listing",
    });
  }

  return {
    totalProducts,
    needOptimization,
    verifyingCount,
    completedRounds,
    products,
    healthReports,
    adRecommendations: adRecs,
    suggestions: suggestions.slice(0, 4),
    feedbackItems: feedbackItems.slice(0, 4),
  };
}

/* ------------------------------------------------------------------ */
/*  Product Stage Helper                                               */
/* ------------------------------------------------------------------ */

export function getProductStageInfo(
  product: { id: number; lifecycle_stage?: string; optimization_round?: number },
  healthReports: HealthReport[]
): {
  stage: string;
  issue: string;
  suggestion: string;
  action: string;
} {
  const health = healthReports.find((h) => h.product_id === product.id);
  const stage = product.lifecycle_stage as LifecycleStage | undefined;

  if (stage && LIFECYCLE_LABELS[stage]) {
    const label = LIFECYCLE_LABELS[stage];
    const path = LIFECYCLE_PATHS[stage];

    switch (stage) {
      case "discovery":
        return {
          stage: label,
          issue: "正在进行6维选品判断",
          suggestion: "查看机会池",
          action: path,
        };
      case "semantic":
        return {
          stage: label,
          issue: "正在进行Listing上新检测",
          suggestion: "继续上新检测",
          action: path,
        };
      case "strategy":
        return {
          stage: label,
          issue: health
            ? `Listing评分${health.grade}级`
            : "正在进行上线后诊断",
          suggestion: "查看本品诊断",
          action: path,
        };
      case "verification":
        return {
          stage: label,
          issue: "正在进行广告验证",
          suggestion: "查看验证结果",
          action: path,
        };
      case "optimization":
        return {
          stage: label,
          issue: `已完成${product.optimization_round || 1}轮优化`,
          suggestion: "查看下一轮优化",
          action: path,
        };
    }
  }

  // Fallback: infer stage from health data
  if (!health) {
    return {
      stage: "① 选品决策",
      issue: "尚未进入上新检测",
      suggestion: "进入上新检测",
      action: "/listing-launch-check",
    };
  }
  if (health.grade === "A" || health.grade === "B") {
    return {
      stage: "④ 广告投放验证",
      issue: "Listing已优化，需验证效果",
      suggestion: "进入广告验证",
      action: "/ad-analytics?view=validation",
    };
  }
  return {
    stage: "③ 上线后诊断",
    issue: `Listing评分${health.grade}级，需优化`,
    suggestion: "查看本品诊断",
    action: "/listing-diagnosis",
  };
}
/* ------------------------------------------------------------------ */
/*  Optimization Timeline                                              */
/* ------------------------------------------------------------------ */

export interface TimelineEvent {
  id?: number;
  product_id: number;
  step_name: string;
  action_timestamp: string;
  listing_score: number;
  score_details: string;
  optimization_round: number;
  created_at?: string;
}

export async function saveTimelineEvent(
  data: Omit<TimelineEvent, "id" | "created_at">
): Promise<TimelineEvent | null> {
  try {
    const res = await withRetry(() =>
      client.entities.optimization_timeline.create({
        product_id: data.product_id,
        step_name: data.step_name,
        action_timestamp: data.action_timestamp,
        listing_score: data.listing_score,
        score_details: data.score_details || "{}",
        optimization_round: data.optimization_round,
      })
    );
    return res?.data || null;
  } catch (e) {
    console.error("Failed to save timeline event:", e);
    return null;
  }
}

export async function getTimelineEvents(
  productId?: number,
  limit = 200
): Promise<TimelineEvent[]> {
  try {
    const queryParams: Record<string, unknown> = {
      sort: "-action_timestamp",
      limit,
    };
    if (productId !== undefined && productId !== 0) {
      queryParams.query = { product_id: productId };
    }
    const res = await withRetry(() =>
      client.entities.optimization_timeline.query(queryParams)
    );
    return res?.data?.items || [];
  } catch (e) {
    console.error("Failed to fetch timeline events:", e);
    return [];
  }
}

/* ------------------------------------------------------------------ */
/*  Unified Action Snapshots                                           */
/* ------------------------------------------------------------------ */

export interface ActionSnapshotPayload {
  module_key: string;
  module_name: string;
  action_key: string;
  action_name: string;
  product_id?: number | null;
  asin?: string;
  title?: string;
  input_snapshot?: unknown;
  output_snapshot?: unknown;
  data_source?: string;
  confidence?: string;
  ai_called?: boolean;
  source_record_table?: string;
  source_record_id?: number | null;
}

export interface ActionSnapshot extends ActionSnapshotPayload {
  id: number;
  created_at?: string;
}

export async function saveActionSnapshot(payload: ActionSnapshotPayload): Promise<number | null> {
  try {
    const res = await fetch("/api/v1/action-snapshots", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data?.success) return null;
    return data.id || null;
  } catch (e) {
    console.error("Failed to save action snapshot:", e);
    return null;
  }
}

export async function getActionSnapshots(params: {
  module_key?: string;
  action_key?: string;
  asin?: string;
  limit?: number;
} = {}): Promise<ActionSnapshot[]> {
  try {
    const qs = new URLSearchParams();
    if (params.module_key) qs.set("module_key", params.module_key);
    if (params.action_key) qs.set("action_key", params.action_key);
    if (params.asin) qs.set("asin", params.asin);
    qs.set("limit", String(params.limit || 50));
    const res = await fetch(`/api/v1/action-snapshots?${qs.toString()}`, {
      headers: getAuthHeaders(),
    });
    const data = await res.json().catch(() => ({}));
    return data?.items || [];
  } catch (e) {
    console.error("Failed to fetch action snapshots:", e);
    return [];
  }
}
