/** AlignX V1 — typed API client over backend REST endpoints. */

const BASE = (import.meta.env.VITE_API_BASE || "") + "/api/v1";

export const API_BASE = BASE;

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("alignx_token");
  const headers: Record<string, string> = { ...(options?.headers as Record<string, string> || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!headers["Content-Type"] && options?.method !== "GET") {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE}${url}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = Array.isArray(err.detail)
      ? err.detail.map((item: { msg?: string }) => item.msg || JSON.stringify(item)).join("；")
      : typeof err.detail === "string"
      ? err.detail
      : err.detail
      ? JSON.stringify(err.detail)
      : "";
    throw new Error(detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

// ── Market Opportunity ──

export interface MarketOpportunity {
  id: string;
  keyword: string;
  marketplace: string;
  opportunity_score: number | null;
  entry_level: string | null;
  market_entry_conclusion: string | null;
  top20_competition_strength: string | null;
  price_band_judgment: string | null;
  main_risk: string | null;
  next_action: string | null;
  best_opportunity_category: string | null;
  product_categories: Array<{
    category_name: string;
    asin_count: number;
    avg_price: string;
    price_range: string;
    avg_rating: number;
    avg_reviews: number;
    competition_level: string;
    key_players: string[];
    typical_features: string[];
    common_weaknesses: string[];
  }> | null;
  seven_layer_result_json: Record<string, unknown> | null;
  created_at: string;
}

export function analyzeMarketOpportunity(keyword: string, marketplace = "amazon.com") {
  return request<MarketOpportunity>("/market-opportunity/analyze", {
    method: "POST",
    body: JSON.stringify({ keyword, marketplace }),
  });
}

export function listMarketOpportunities(page = 1) {
  return request<{ items: MarketOpportunity[]; total: number }>(
    `/market-opportunity/history?page=${page}`
  );
}

// ── Competitor Analysis ──

export interface CompetitorAnalysis {
  id: string;
  asin: string;
  marketplace: string;
  product_title: string | null;
  brand: string | null;
  price: string | null;
  rating: number | null;
  review_count: number | null;
  overall_judgment: string | null;
  main_strengths: string[] | null;
  main_weaknesses: string[] | null;
  attack_points: string[] | null;
  twelve_dimension_result_json: Record<string, unknown> | null;
  created_at: string;
}

function amazonInputPayload(input: string, marketplace = "amazon.com") {
  const value = input.trim();
  const isUrl = /^https?:\/\//i.test(value);
  return isUrl
    ? { product_url: value, marketplace }
    : { asin: value.toUpperCase(), marketplace };
}

export function analyzeCompetitor(asin: string, marketplace = "amazon.com") {
  return request<CompetitorAnalysis>("/competitor-analysis/analyze", {
    method: "POST",
    body: JSON.stringify(amazonInputPayload(asin, marketplace)),
  });
}

export function listCompetitorAnalyses(page = 1) {
  return request<{ items: CompetitorAnalysis[]; total: number }>(
    `/competitor-analysis/history?page=${page}`
  );
}

// ── Pre-launch Check ──

export interface PrelaunchCheck {
  id: string;
  product_name: string;
  admission_result: string | null;
  conclusion: string | null;
  position_diagnoses_json: PositionDiagnosis[] | null;
  next_action: string | null;
  created_at: string;
}

export interface PositionDiagnosis {
  position_id: string;
  position_name: string;
  position_type: string;
  status: string;
  issue: string | null;
  impact: string | null;
  recommendation: string | null;
  modification_example: string | null;
}

export function analyzePrelaunch(data: Record<string, unknown>) {
  return request<PrelaunchCheck>("/prelaunch-check/analyze", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Conversion Diagnosis ──

export interface ConversionDiagnosis {
  id: string;
  asin: string;
  product_title: string | null;
  overall_conclusion: string | null;
  biggest_breakpoint: string | null;
  priority_position: string | null;
  priority_action: string | null;
  impacted_ad_metrics: string[] | null;
  position_diagnoses_json: ConversionPositionDiagnosis[] | null;
  created_at: string;
}

export interface ConversionPositionDiagnosis {
  position_id: string;
  position_name: string;
  status: string;
  issue: string | null;
  evidence: string | null;
  conversion_impact: string | null;
  recommendation: string | null;
  priority: number | null;
}

export function diagnoseConversion(asin: string, marketplace = "amazon.com") {
  return request<ConversionDiagnosis>("/conversion-diagnosis/analyze", {
    method: "POST",
    body: JSON.stringify(amazonInputPayload(asin, marketplace)),
  });
}

export function listConversionDiagnoses(page = 1) {
  return request<{ items: ConversionDiagnosis[]; total: number }>(
    `/conversion-diagnosis/history?page=${page}`
  );
}

// ── Validation Tasks ──

export interface ValidationTask {
  id: string;
  asin: string;
  proposition_code: string;
  proposition_name: string | null;
  source_module: string | null;
  source_record_id: string | null;
  hypothesis_text: string | null;
  evidence_snapshot: Record<string, unknown> | null;
  controlled_variable: string | null;
  forbidden_simultaneous_changes: string[] | null;
  validation_period: string | null;
  success_criteria: string | null;
  failure_criteria: string | null;
  execution_status: string;
  result_status: string | null;
  next_action: string | null;
  created_at: string;
}

export function listValidationTasks(asin?: string) {
  const qs = asin ? `?asin=${asin}` : "";
  return request<{ items: ValidationTask[]; total: number }>(`/validation-tasks${qs}`);
}

// ── ASIN Profiles ──

export interface AsinProfile {
  id: string;
  asin: string;
  product_title: string | null;
  category: string | null;
  lifecycle_stage: string | null;
  total_validation_count: number;
  effective_count: number;
  ineffective_count: number;
  current_main_problem: string | null;
  next_recommended_proposition: string | null;
  asin_learning_summary: string | null;
  updated_at: string;
}

export function listAsinProfiles() {
  return request<{ items: AsinProfile[]; total: number }>("/asin-profiles");
}

// ── Reports ──

export interface YesterdayReport {
  date: string;
  summary: {
    total_executions: number;
    total_cost: number;
    ad_spend: number;
    changed_positions: number;
    active_asins: number;
    pending_tasks: number;
  };
  recent_ads: Array<{
    asin: string;
    cost: number;
    summary: string;
    date: string;
  }>;
  validation_stats: {
    effective: number;
    ineffective: number;
    interfered: number;
    insufficient_data: number;
  };
  active_problems: Array<{
    asin: string;
    problem: string;
    next_action: string | null;
  }>;
  profile_summaries: Array<{
    asin: string;
    product_title: string | null;
    total_validations: number;
    effective: number;
    ineffective: number;
    ad_spend: number;
    ad_executions: number;
    total_cost: number;
    impressions: number;
    clicks: number;
    orders: number;
    sales: number;
    current_problem: string | null;
    next_recommended: string | null;
    learning: string | null;
  }>;
}

export interface DecisionItem {
  id: string;
  asin: string;
  product_title: string | null;
  hypothesis: string;
  source: string;
  validation_period: string | null;
  estimated_cost: number | null;
  created_at: string;
  running_days?: number;
  result_id?: string;
  conclusion?: string | null;
  verified_at?: string;
}

export interface TodayDecisions {
  date: string;
  summary: {
    pending: number;
    running: number;
    effective: number;
  };
  pending: DecisionItem[];
  running: DecisionItem[];
  effective: DecisionItem[];
  global_recommendation: string;
}

export function getYesterdayReport() {
  return request<YesterdayReport>("/reports/yesterday");
}

export function getTodayDecisions() {
  return request<TodayDecisions>("/reports/today");
}
