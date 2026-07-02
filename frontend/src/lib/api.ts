/** AlignX V1 — typed API client over backend REST endpoints. */

const BASE = (import.meta.env.VITE_API_BASE || "") + "/api/v1";

export const API_BASE = BASE;

function clearAuthState() {
  localStorage.removeItem("alignx_token");
  localStorage.removeItem("alignx_user");
}

export async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("alignx_token");
  const headers: Record<string, string> = { ...(options?.headers as Record<string, string> || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!headers["Content-Type"] && options?.method !== "GET") {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE}${url}`, { ...options, headers });
  if (!res.ok) {
    if (res.status === 401) {
      clearAuthState();
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    }
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

export function sendLoginCode(email: string) {
  return request<{ code?: string; detail?: string }>("/auth/send-code", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function verifyLoginCode(data: { email: string; code: string; store_name?: string }) {
  return request<{
    success: boolean;
    token: string;
    user_id: string;
    email: string;
    store_name: string;
    detail?: string;
  }>("/auth/verify-code", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

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

export function getMarketOpportunity(id: string) {
  return request<MarketOpportunity>(`/market-opportunity/${id}`);
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

export function getCompetitorAnalysis(id: string) {
  return request<CompetitorAnalysis>(`/competitor-analysis/${id}`);
}

// ── Pre-launch Check ──

export interface PrelaunchCheck {
  id: string;
  product_name: string;
  marketplace?: string;
  title_draft?: string | null;
  key_highlights?: string | null;
  bullet_1?: string | null;
  bullet_2?: string | null;
  bullet_3?: string | null;
  bullet_4?: string | null;
  bullet_5?: string | null;
  main_image_path?: string | null;
  image_2_path?: string | null;
  image_3_path?: string | null;
  image_4_path?: string | null;
  image_5_path?: string | null;
  image_6_path?: string | null;
  image_7_path?: string | null;
  aplus_images_json?: Array<{ slot?: string; name?: string; url?: string }> | null;
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
  uploaded?: boolean;
  ocr_status?: "success" | "failed" | "pending" | string | null;
  status: string;
  issue: string | null;
  impact: string | null;
  recommendation: string | null;
  modification_example: string | null;
  final_score?: number | null;
  usable_status?: string | null;
  impact_metrics?: string[] | null;
  issue_type?: string[] | null;
  evidence?: string | null;
  risk_level?: string | null;
  suggested_rewrite?: string | null;
  suggested_action?: string | null;
}

export function analyzePrelaunch(data: Record<string, unknown>) {
  return request<PrelaunchCheck>("/prelaunch-check/analyze", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function listPrelaunchChecks(page = 1) {
  return request<{ items: PrelaunchCheck[]; total: number }>(
    `/prelaunch-check/history?page=${page}`
  );
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
  ai_readability_score_json?: ListingValidationResult | null;
  ai_readability_score_version?: string | null;
  created_at: string;
}

export interface ListingValidationResult {
  diagnosis_type?: string;
  primary_bottleneck?: string;
  secondary_bottleneck?: string;
  overall_health_score?: number;
  confidence?: number;
  evidence_strength?: number;
  prediction_policy?: string;
  rule_check?: {
    rule_status?: string;
    blocked_reasons?: string[];
    warnings?: string[];
    allowed_actions?: string[];
    forbidden_actions?: string[];
  };
  keyword_position_mapping?: Array<Record<string, unknown>>;
  top20_keyword_mapping_context?: {
    source?: string;
    source_keyword?: string | null;
    source_keyword_candidates?: string[];
    top20_capture_status?: string;
    top20_sample_count?: number;
    top20_asins?: Array<Record<string, unknown>>;
    capture_job_id?: string;
    error_message?: string;
  };
  funnel_diagnosis?: Array<Record<string, unknown>>;
  position_gap_heatmap?: ConversionPositionDiagnosis[];
  top_actions?: Array<Record<string, unknown>>;
  validation_plan?: Record<string, unknown>;
}

export interface ConversionPositionDiagnosis {
  position_id: string;
  position_name: string;
  position?: string;
  position_type?: string;
  funnel_stage?: string;
  position_role?: string;
  current_status?: string;
  risk_level?: string;
  impact_direction?: string[] | null;
  evidence_strength?: number | null;
  recommended_fix_type?: string | null;
  impacted_ad_metrics?: string[] | null;
  status: string;
  score?: number | null;
  currentText?: string | null;
  issueTypes?: string[] | null;
  humanDriver?: {
    gainDrivers?: string[];
    avoidanceDrivers?: string[];
    primaryDriverType?: string | null;
    primaryDriver?: string | null;
    explanation?: string | null;
  } | null;
  mentalValuePoint?: {
    primaryValuePoint?: string | null;
    buyerMemorySentence?: string | null;
    supportingBenefits?: string[];
    proofPoints?: string[];
  } | null;
  buyerLanguageProblem?: string | null;
  positionProblem?: string | null;
  complianceRisk?: {
    riskLevel?: string | null;
    riskPhrases?: string[];
    evidenceRequired?: boolean;
    saferAlternatives?: string[];
  } | null;
  suggestedRewrite?: string | null;
  reason?: string | null;
  placementAdvice?: string | null;
  rejectedPhrases?: string[] | null;
  validationMetrics?: string[] | null;
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

export function getConversionDiagnosis(id: string) {
  return request<ConversionDiagnosis>(`/conversion-diagnosis/${id}`);
}

// ── Multi-Source Diagnosis ──

export interface MultiSourceResult {
  asin: string;
  diagnosis_type: string;
  primary_problem: string;
  primary_confidence: number;
  primary_evidence: string;
  dimensions: Array<{
    dimension: string;
    label: string;
    confidence: number;
    evidence: string;
    system_capable: boolean;
  }>;
  top_actions: Array<{
    priority: number;
    action: string;
    target: string;
    system_capable: boolean;
    route?: string;
  }>;
  system_can_fix: Array<Record<string, unknown>>;
  human_required: Array<Record<string, unknown>>;
}

export function runMultiSourceDiagnosis(payload: {
  asin: string;
  ad_metrics?: Record<string, unknown>;
  listing_data?: Record<string, unknown>;
  ai_result?: Record<string, unknown>;
  top20_context?: Record<string, unknown>;
}) {
  return request<MultiSourceResult>("/conversion-diagnosis/multi-source", {
    method: "POST",
    body: JSON.stringify(payload),
  });
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

export function createValidationTask(data: {
  asin: string;
  proposition_code: string;
  proposition_name?: string | null;
  source_module?: string | null;
  source_record_id?: string | null;
  hypothesis_text?: string | null;
  evidence_snapshot?: Record<string, unknown> | null;
  controlled_variable?: string | null;
  forbidden_simultaneous_changes?: string[] | null;
  validation_period?: string | null;
  success_criteria?: string | null;
  failure_criteria?: string | null;
}) {
  return request<ValidationTask>("/validation-tasks", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Report Upload Staging ──

export interface ReportUploadStagingResponse {
  batch_id: string;
  total_rows: number;
  resolved_count: number;
  ambiguous_count: number;
  unresolved_count: number;
}

export function stageReportUpload(data: {
  report_type?: string;
  marketplace?: string;
  source_filename?: string;
  rows: Array<Record<string, string>>;
}) {
  return request<ReportUploadStagingResponse>("/report-uploads/staging", {
    method: "POST",
    body: JSON.stringify(data),
  });
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
  interfered_count: number;
  insufficient_data_count: number;
  current_main_problem: string | null;
  next_recommended_proposition: string | null;
  asin_learning_summary: string | null;
  updated_at: string;
}

export function listAsinProfiles() {
  return request<{ items: AsinProfile[]; total: number }>("/asin-profiles");
}

// ── Execution Records ──

export function createExecutionRecord(data: {
  validation_task_id: string;
  asin: string;
  action_summary?: string | null;
  changed_variable?: string | null;
  cost_amount?: number | null;
  cost_type?: string | null;
  changed_position?: string | null;
  change_detail?: string | null;
  evidence_note?: string | null;
}) {
  return request<{ id: string }>("/execution-records", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface ExecutionRecord {
  id: string;
  validation_task_id: string;
  asin: string;
  action_summary: string | null;
  cost_amount: number | null;
  cost_type: string | null;
  evidence_note: string | null;
  created_at: string;
}

export function listExecutionRecords(taskId?: string) {
  const qs = taskId ? `?validation_task_id=${taskId}` : "";
  return request<{ items: ExecutionRecord[]; total: number }>(`/execution-records${qs}`);
}

export function updateValidationTask(
  id: string,
  data: {
    execution_status?: string;
    result_status?: string;
    next_action?: string;
    audit_source?: string;
  },
) {
  return request<ValidationTask>(`/validation-tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// ── Validation Results ──

export interface ValidationResult {
  id: string;
  asin: string;
  validation_task_id: string;
  final_result_status: "effective" | "ineffective" | "interfered" | "insufficient_data";
  notes: string | null;
  attribution_conclusion: string | null;
  next_step: string | null;
  baseline_metrics_json: Record<string, number> | null;
  result_metrics_json: Record<string, number> | null;
  created_at: string;
}

export function listValidationResults(pageSize = 50) {
  return request<{ items: ValidationResult[]; total: number }>(`/validation-results?page_size=${pageSize}`);
}

export function createValidationResult(data: {
  validation_task_id: string;
  asin: string;
  final_result_status: string;
  notes?: string | null;
  attribution_conclusion?: string | null;
}) {
  return request<ValidationResult>("/validation-results", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Lifecycle ──

export interface LifecycleData {
  asin: string;
  current_stage: string;
  stage_label: string;
  days_active: number;
  should_transition: boolean;
  transition_alert: string | null;
  ad_strategy: Record<string, string>;
  keyword_groups: Array<{
    group_name: string;
    source_type: string;
    source_record_id: string | null;
    keywords: string[];
  }>;
  metrics: {
    total_orders: number;
    total_spend: number;
    total_sales: number;
    acos: number | null;
    weeks_active: number;
    recent_weekly_orders: number[];
    weekly_order_growth_pct: number | null;
    impression_trend_pct: number | null;
    effective_validations: number;
  };
}

export function getLifecycle(asin: string) {
  return request<LifecycleData>(`/lifecycle/${asin}`);
}

export function applyLifecycle(asin: string) {
  return request<LifecycleData>(`/lifecycle/${asin}/apply`, { method: "POST" });
}

// ── Help Assistant ──

export interface HelpChatResponse {
  answer: string;
  source: string;
  should_create_ticket: boolean;
  suggested_issue_type: string;
  message_id?: string | null;
}

export interface HelpTicket {
  ticket_id: string;
  user_email?: string | null;
  issue_type: string;
  priority: string;
  language: string;
  page_url?: string | null;
  user_message: string;
  screenshots?: string[] | null;
  status: string;
  created_at: string;
}

export interface HelpFaqItem {
  category: string;
  language: string;
  question: string;
  answer: string;
  keywords: string[];
}

export function sendHelpMessage(data: {
  message: string;
  language: "zh" | "en";
  page_url?: string;
  recent_error_code?: string | null;
}) {
  return request<HelpChatResponse>("/help/chat", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function createHelpTicket(data: {
  issue_type: string;
  priority: string;
  language: "zh" | "en";
  page_url?: string;
  user_message: string;
  screenshots?: string[];
}) {
  return request<HelpTicket>("/help/tickets", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function listHelpTickets() {
  return request<HelpTicket[]>("/help/tickets");
}

export function listHelpFaq(language: "zh" | "en") {
  return request<HelpFaqItem[]>(`/help/faq?language=${language}`);
}

// ── Admin ──

export interface AdminProposition {
  id: string;
  proposition_code: string;
  category_code: string;
  name: string;
  definition: string | null;
  controlled_variable: string | null;
  archived: boolean;
}

export function listAdminPropositions() {
  return request<AdminProposition[]>("/admin/propositions");
}

export function listAdminProfiles() {
  return request<Array<Record<string, unknown>>>("/admin/asin-profiles");
}

export function getAdminAudit() {
  return request<{ loop_health?: Record<string, boolean>; stages?: Record<string, unknown> }>("/admin/audit");
}

export function listAdminRules() {
  return request<Record<string, { category: string; name: string; description: string; risk: string; items: string[] }>>("/admin/rules");
}

export function updateAdminRule(ruleId: string, items: string[]) {
  return request<{ success: boolean }>(`/admin/rules/${ruleId}`, {
    method: "PUT",
    body: JSON.stringify(items),
  });
}

export function translateBuyerLanguage(data: Record<string, unknown>) {
  return request<Record<string, unknown>>("/admin/buyer-lang-translate", {
    method: "POST",
    body: JSON.stringify(data),
  });
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
  priority_score?: number;
  history_signal?: string;
  next_step?: string;
  budget_gate?: {
    status: string;
    limit: number | null;
    blocked: boolean;
  };
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
  budget_gate: {
    status: string;
    limit: number | null;
  };
}

export function getYesterdayReport() {
  return request<YesterdayReport>("/reports/yesterday");
}

export function getTodayDecisions() {
  return request<TodayDecisions>("/reports/today");
}
