import axios from "axios";

import { getAuthHeaders } from "@/lib/auth-headers";

const API_BASE = "/api/v1/asin-business-profiles";

export type LifecycleStage = "Testing" | "Growth" | "Mature" | "Decline";
export type ValidationStatus = "Pending" | "Running" | "Success" | "Failed" | "Inconclusive";
export type ValidationType = "Listing" | "Traffic" | "Price" | "Coupon" | "Keyword" | "Advertising" | "Review";
export type DecisionType =
  | "Yesterday Report"
  | "Today Decision"
  | "Listing Diagnosis"
  | "Traffic Strategy"
  | "Effect Validation";
export type AsinModuleViewType =
  | "yesterday-report"
  | "today-decision"
  | "listing-diagnosis"
  | "traffic-strategy"
  | "execution-records"
  | "effect-validation";

export interface AsinBusinessProfile {
  id: number;
  seller_id: string;
  store_id: string;
  marketplace: string;
  asin: string;
  sku?: string | null;
  brand?: string | null;
  product_name?: string | null;
  category?: string | null;
  launch_date?: string | null;
  current_price?: number | null;
  lifecycle_stage?: LifecycleStage | string | null;
  overall_score?: number | null;
  traffic_score?: number | null;
  ctr_score?: number | null;
  cvr_score?: number | null;
  ads_score?: number | null;
  profit_score?: number | null;
  competition_score?: number | null;
  title_score?: number | null;
  main_image_score?: number | null;
  gallery_score?: number | null;
  aplus_score?: number | null;
  bullet_score?: number | null;
  review_score?: number | null;
  price_score?: number | null;
  current_primary_problem?: string | null;
  priority_actions?: string | null;
  confidence_score?: number | null;
  data_source?: string | null;
  is_demo: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AsinProfileListResponse {
  items: AsinBusinessProfile[];
  total: number;
  skip: number;
  limit: number;
}

export interface ValidationTask {
  id: number;
  validation_id: string;
  seller_id: string;
  store_id: string;
  marketplace: string;
  asin: string;
  intent_decision_id?: string | null;
  validation_type: ValidationType | string;
  problem?: string | null;
  hypothesis?: string | null;
  action_plan?: string | null;
  target_metric?: string | null;
  baseline_start_date?: string | null;
  baseline_end_date?: string | null;
  test_start_date?: string | null;
  test_end_date?: string | null;
  result_start_date?: string | null;
  result_end_date?: string | null;
  baseline_value?: number | null;
  target_value?: number | null;
  result_value?: number | null;
  improvement_rate?: number | null;
  confidence_score?: number | null;
  status: ValidationStatus | string;
  data_source?: string | null;
  is_demo: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DailySnapshot {
  id: number;
  seller_id: string;
  store_id: string;
  marketplace: string;
  asin: string;
  date: string;
  sessions?: number | null;
  page_views?: number | null;
  units_ordered?: number | null;
  clicks?: number | null;
  orders?: number | null;
  sales?: number | null;
  impressions?: number | null;
  ctr?: number | null;
  cvr?: number | null;
  acos?: number | null;
  tacos?: number | null;
  ad_spend?: number | null;
  ad_sales?: number | null;
  organic_sales?: number | null;
  total_sales?: number | null;
  inventory?: number | null;
  buybox_status?: string | null;
  data_source?: string | null;
  is_demo: boolean;
  created_at?: string | null;
}

export interface ExecutionLog {
  id: number;
  execution_id: string;
  validation_id: string;
  intent_decision_id?: string | null;
  seller_id: string;
  store_id: string;
  marketplace: string;
  asin: string;
  action_type: string;
  before_value?: string | null;
  after_value?: string | null;
  executed_by?: string | null;
  executed_at?: string | null;
  note?: string | null;
  data_source?: string | null;
  is_demo: boolean;
  created_at?: string | null;
}

export interface AiDecisionTrace {
  id: number;
  decision_id: string;
  seller_id: string;
  store_id: string;
  marketplace: string;
  asin: string;
  related_validation_id?: string | null;
  decision_type: DecisionType | string;
  conclusion?: string | null;
  input_data_refs?: Record<string, unknown> | string | null;
  evidence_metrics?: Record<string, unknown>;
  metric_snapshot?: Record<string, unknown> | string | null;
  semantic_evidence?: Record<string, unknown> | string | null;
  reasoning_summary?: string | null;
  confidence_score?: number | null;
  recommended_action?: string | null;
  prompt_version?: string | null;
  model_name?: string | null;
  data_source?: string | null;
  is_demo: boolean;
  created_at?: string | null;
}

export interface MetricDictionaryItem {
  id: number;
  metric_key: string;
  metric_name: string;
  formula: string;
  description?: string | null;
}

export interface AsinModuleView {
  view_type: AsinModuleViewType | string;
  seller_id: string;
  store_id: string;
  marketplace: string;
  asin: string;
  summary: Record<string, unknown>;
  metrics: Record<string, unknown>;
  records: Array<Record<string, unknown>>;
}

export interface DemoImportResponse {
  imported_profiles: number;
  imported_snapshots: number;
  imported_validation_tasks: number;
  imported_ai_traces: number;
  skipped_without_complete_aplus: number;
  source: string;
}

export interface ReportUploadResponse {
  report_id: string;
  seller_id: string;
  store_id: string;
  marketplace?: string | null;
  report_type: string;
  original_filename?: string | null;
  file_path?: string | null;
  upload_time?: string | null;
  uploaded_by?: string | null;
  parse_status: string;
  parse_error?: string | null;
  date_range_start?: string | null;
  date_range_end?: string | null;
  row_count?: number | null;
  matched_rows?: number | null;
  unresolved_rows?: number | null;
  ambiguous_rows?: number | null;
  writable_rows?: number | null;
  match_summary?: string | null;
  created_at?: string | null;
}

export interface ReportParseSummary {
  report_id: string;
  report_type: string;
  parse_status: string;
  total_rows: number;
  matched_asin_rows: number;
  unmatched_rows: number;
  ambiguous_rows: number;
  writable_rows: number;
}

export interface ReportStagingRow {
  id: number;
  report_id: string;
  seller_id: string;
  store_id: string;
  marketplace: string;
  asin?: string | null;
  date?: string | null;
  row_number: number;
  report_type: string;
  match_status: string;
  match_method?: string | null;
  extracted_asin?: string | null;
  extracted_sku?: string | null;
  campaign_id?: string | null;
  ad_group_id?: string | null;
  ad_id?: string | null;
  matched_asin?: string | null;
  candidate_matches?: string | null;
  is_writable?: boolean;
  resolution_status?: string | null;
  raw_data?: string | null;
  normalized_data?: string | null;
  created_at?: string | null;
}

export interface ReportStagingListResponse {
  items: ReportStagingRow[];
  total: number;
  skip: number;
  limit: number;
}

export interface ReportStagingResolveResponse extends ReportParseSummary {
  action: string;
}

export type IntentRecommendedAction = "Listing First" | "Low-Bid Test" | "Scale Test" | "Do Not Invest" | "Blocked";
export type IntentDecisionStatus = "Candidate" | "Ready To Test" | "Testing" | "Validated" | "Failed" | "Inconclusive" | "Blocked";

export interface IntentEvidenceInput {
  source_type: string;
  evidence_text?: string;
  metric_snapshot?: Record<string, unknown> | string;
  strength_score?: number;
  data_source?: string;
  is_demo?: boolean;
}

export interface ListingSnapshotInput {
  store_id?: string;
  marketplace?: string;
  asin?: string;
  title?: string;
  bullet_points?: string[] | string;
  description?: string;
  aplus?: Record<string, unknown> | unknown[] | string;
  main_image?: string;
  secondary_images?: string[] | string;
  backend_terms?: string;
  price?: number;
  coupon?: string;
  snapshot_at?: string;
  data_source?: string;
  is_demo?: boolean;
}

export interface IntentDecision {
  id: number;
  intent_decision_id: string;
  seller_id: string;
  store_id: string;
  marketplace: string;
  asin: string;
  intent_name: string;
  intent_description?: string | null;
  position_reception_result?: string | null;
  semantic_audit_result?: string | null;
  buyer_language_result?: string | null;
  intent_evidence_status?: string | null;
  product_platform_safety_status?: string | null;
  investment_value_status?: string | null;
  reception_gap?: string | null;
  safe_expression?: string | null;
  blocked_expression?: string | null;
  recommended_action: IntentRecommendedAction | string;
  priority_score?: number | null;
  confidence_score?: number | null;
  validation_task_id?: string | null;
  validation_result?: string | null;
  status: IntentDecisionStatus | string;
  data_source?: string | null;
  is_demo: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface IntentDecisionListResponse {
  items: IntentDecision[];
  total: number;
  skip: number;
  limit: number;
}

export interface AsinAiMemory {
  id: number;
  seller_id: string;
  store_id: string;
  marketplace: string;
  asin: string;
  validated_intents?: string | null;
  failed_intents?: string | null;
  current_main_bottleneck?: string | null;
  current_listing_gap?: string | null;
  current_traffic_problem?: string | null;
  next_best_hypothesis?: string | null;
  proven_actions?: string | null;
  failed_actions?: string | null;
  latest_learning?: string | null;
  data_source?: string | null;
  is_demo: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AsinProfileDetail {
  profile?: AsinBusinessProfile | null;
  memory?: AsinAiMemory | null;
  intent_decisions: IntentDecision[];
  latest_snapshots: Array<Record<string, unknown>>;
}

export interface RunIntentDecisionParams {
  asin: string;
  store_id?: string;
  marketplace?: string;
  intent_name: string;
  intent_description?: string;
  listing_snapshot?: ListingSnapshotInput;
  evidences?: IntentEvidenceInput[];
  input_data_refs?: Record<string, unknown> | string;
  metric_snapshot?: Record<string, unknown> | string;
  data_source?: string;
  is_demo?: boolean;
}

export interface CreateValidationTaskParams {
  asin: string;
  store_id?: string;
  marketplace?: string;
  intent_decision_id?: string;
  validation_type: string;
  problem?: string;
  hypothesis?: string;
  action_plan?: string;
  target_metric?: string;
  baseline_start_date?: string;
  baseline_end_date?: string;
  test_start_date?: string;
  test_end_date?: string;
  result_start_date?: string;
  result_end_date?: string;
  target_value?: number;
  status?: string;
}

export interface CreateExecutionLogParams {
  validation_id: string;
  intent_decision_id?: string;
  asin: string;
  store_id?: string;
  marketplace?: string;
  action_type: string;
  before_value?: string;
  after_value?: string;
  executed_by?: string;
  executed_at?: string;
  note?: string;
  source?: string;
  data_source?: string;
}

export async function listAsinProfiles(params: {
  store_id?: string;
  marketplace?: string;
  is_demo?: boolean;
  skip?: number;
  limit?: number;
} = {}): Promise<AsinProfileListResponse> {
  const res = await axios.get(API_BASE, { params, headers: getAuthHeaders() });
  return res.data;
}

export async function getAsinProfile(params: {
  marketplace: string;
  asin: string;
  store_id?: string;
}): Promise<AsinBusinessProfile> {
  const res = await axios.get(`${API_BASE}/${params.marketplace}/${params.asin}`, {
    params: { store_id: params.store_id },
    headers: getAuthHeaders(),
  });
  return res.data;
}

export async function listValidationTasks(params: {
  asin?: string;
  store_id?: string;
  marketplace?: string;
  skip?: number;
  limit?: number;
} = {}): Promise<{ items: ValidationTask[]; total: number; skip: number; limit: number }> {
  const res = await axios.get(`${API_BASE}/validations`, { params, headers: getAuthHeaders() });
  return res.data;
}

export async function listDailySnapshots(params: {
  asin?: string;
  store_id?: string;
  marketplace?: string;
  skip?: number;
  limit?: number;
} = {}): Promise<{ items: DailySnapshot[]; total: number; skip: number; limit: number }> {
  const res = await axios.get(`${API_BASE}/snapshots`, { params, headers: getAuthHeaders() });
  return res.data;
}

export async function listExecutionLogs(params: {
  asin?: string;
  validation_id?: string;
  store_id?: string;
  marketplace?: string;
  skip?: number;
  limit?: number;
} = {}): Promise<{ items: ExecutionLog[]; total: number; skip: number; limit: number }> {
  const res = await axios.get(`${API_BASE}/execution-logs`, { params, headers: getAuthHeaders() });
  return res.data;
}

export async function listAiDecisionTraces(params: {
  asin?: string;
  decision_type?: string;
  related_validation_id?: string;
  store_id?: string;
  marketplace?: string;
  skip?: number;
  limit?: number;
} = {}): Promise<{ items: AiDecisionTrace[]; total: number; skip: number; limit: number }> {
  const res = await axios.get(`${API_BASE}/ai-decision-traces`, { params, headers: getAuthHeaders() });
  return res.data;
}

export async function getAsinProfileDetail(params: {
  asin: string;
  store_id?: string;
  marketplace?: string;
}): Promise<AsinProfileDetail> {
  const res = await axios.get(`/api/asins/${params.asin}/profile`, {
    params: {
      store_id: params.store_id || "default",
      marketplace: params.marketplace || "US",
    },
    headers: getAuthHeaders(),
  });
  return res.data;
}

export async function listIntentDecisions(params: {
  asin: string;
  store_id?: string;
  marketplace?: string;
  skip?: number;
  limit?: number;
}): Promise<IntentDecisionListResponse> {
  const res = await axios.get(`/api/asins/${params.asin}/intent-decisions`, {
    params: {
      store_id: params.store_id || "default",
      marketplace: params.marketplace || "US",
      skip: params.skip,
      limit: params.limit,
    },
    headers: getAuthHeaders(),
  });
  return res.data;
}

export async function runIntentDecision(params: RunIntentDecisionParams): Promise<IntentDecision> {
  const { asin, ...payload } = params;
  const res = await axios.post(`/api/asins/${asin}/intent-decisions/run`, payload, { headers: getAuthHeaders() });
  return res.data;
}

export async function createValidationTask(params: CreateValidationTaskParams): Promise<ValidationTask> {
  const res = await axios.post(`${API_BASE}/validations`, params, { headers: getAuthHeaders() });
  return res.data;
}

export async function createExecutionLog(params: CreateExecutionLogParams): Promise<{
  execution_id: string;
  validation_id: string;
  asin: string;
  created_at?: string;
}> {
  const res = await axios.post("/api/execution-logs", params, { headers: getAuthHeaders() });
  return res.data;
}

export async function runEffectValidation(params: {
  validation_id: string;
  result_start_date?: string;
  result_end_date?: string;
  minimum_sample_ready?: boolean;
}): Promise<{
  validation_id: string;
  intent_decision_id?: string | null;
  asin: string;
  status: string;
  baseline_value?: number | null;
  target_value?: number | null;
  result_value?: number | null;
  improvement_rate?: number | null;
  decision_id?: string | null;
}> {
  const res = await axios.post("/api/effect-validation/run", params, { headers: getAuthHeaders() });
  return res.data;
}

export async function listMetricDictionary(): Promise<MetricDictionaryItem[]> {
  const res = await axios.get(`${API_BASE}/metrics`, { headers: getAuthHeaders() });
  return res.data;
}

export async function getAsinModuleView(params: {
  view_type: AsinModuleViewType;
  asin?: string;
  store_id?: string;
  marketplace?: string;
}): Promise<AsinModuleView> {
  const res = await axios.get(`${API_BASE}/views/${params.view_type}`, {
    params: {
      asin: params.asin,
      store_id: params.store_id,
      marketplace: params.marketplace,
    },
    headers: getAuthHeaders(),
  });
  return res.data;
}

export async function importDemoFromListingDiagnosis(params: {
  store_id?: string;
  marketplace?: string;
  limit?: number;
} = {}): Promise<DemoImportResponse> {
  const res = await axios.post(`${API_BASE}/demo/import-from-listing-diagnosis`, null, {
    params,
    headers: getAuthHeaders(),
  });
  return res.data;
}

export async function clearDemoAsinProfileData(): Promise<{ deleted: Record<string, number> }> {
  const res = await axios.delete(`${API_BASE}/demo`, { headers: getAuthHeaders() });
  return res.data;
}

export async function uploadReport(params: {
  file: File;
  report_type: string;
  store_id?: string;
  marketplace?: string;
  date_range_start?: string;
  date_range_end?: string;
}): Promise<ReportUploadResponse> {
  const form = new FormData();
  form.append("file", params.file);
  form.append("report_type", params.report_type);
  form.append("store_id", params.store_id || "default");
  form.append("marketplace", params.marketplace || "US");
  if (params.date_range_start) form.append("date_range_start", params.date_range_start);
  if (params.date_range_end) form.append("date_range_end", params.date_range_end);
  const res = await axios.post("/api/reports/upload", form, { headers: getAuthHeaders() });
  return res.data;
}

export async function parseReport(reportId: string): Promise<ReportParseSummary> {
  const res = await axios.post(`/api/reports/${reportId}/parse`, null, { headers: getAuthHeaders() });
  return res.data;
}

export async function listReportStagingRows(params: {
  report_id: string;
  match_status?: string;
  skip?: number;
  limit?: number;
}): Promise<ReportStagingListResponse> {
  const res = await axios.get("/api/reports/staging", { params, headers: getAuthHeaders() });
  return res.data;
}

export async function resolveReportStagingRows(params: {
  report_id: string;
  action: "bind_existing" | "create_profile" | "ignore";
  asin?: string;
  staging_row_ids?: number[];
}): Promise<ReportStagingResolveResponse> {
  const res = await axios.post("/api/reports/staging/resolve", {
    report_id: params.report_id,
    action: params.action,
    asin: params.asin,
    staging_row_ids: params.staging_row_ids || [],
  }, { headers: getAuthHeaders() });
  return res.data;
}
