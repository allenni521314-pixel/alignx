# AlignX V1.0 API Contract

> 生成时间：2026-07-03
> 分支：alignx-v1-clean
> 后端：backend/（FastAPI，端口 8001）
> 前端：frontend/（Vite 代理 /api → localhost:8001）
> 所有路由前缀：/api/v1

---

## Auth（认证）

| Method | Path | 请求体 | 响应 | 前端调用方 |
|--------|------|--------|------|-----------|
| POST | /api/v1/auth/send-code | {email: string} | {code?, detail?} | Login.tsx |
| POST | /api/v1/auth/verify-code | {email, code, store_name?} | {success, token, user_id, email, store_name, detail?} | Login.tsx |

## Market Opportunity（市场机会）

| Method | Path | 请求体 | 响应 | 前端调用方 |
|--------|------|--------|------|-----------|
| POST | /api/v1/market-opportunity/analyze | {keyword, marketplace?} | MarketOpportunityResponse | MarketOpportunity.tsx |
| GET | /api/v1/market-opportunity?page=N | — | PaginatedResponse<MarketOpportunityResponse> | MarketOpportunity.tsx |
| GET | /api/v1/market-opportunity/{id} | — | MarketOpportunityResponse | MarketOpportunity.tsx |

### MarketOpportunityResponse 字段

```
id: str
keyword: str
marketplace: str
category: str | null
subcategory: str | null
category_confidence: float | null
opportunity_score: float | null
entry_level: str | null              # 强建议进入 | 谨慎进入 | 不建议进入
market_entry_conclusion: str | null
top20_competition_strength: str | null  # 低 | 中 | 高 | 极高
price_band_judgment: str | null
main_risk: str | null
next_action: str | null
best_opportunity_category: str | null
product_categories: list | null
seven_layer_result_json: dict | null
created_at: datetime
```

## Competitor Analysis（竞品分析）

| Method | Path | 请求体 | 响应 | 前端调用方 |
|--------|------|--------|------|-----------|
| POST | /api/v1/competitor-analysis/analyze | {asin?, product_url?, marketplace?} | CompetitorAnalysisResponse | CompetitorAnalysis.tsx |
| GET | /api/v1/competitor-analysis?page=N | — | PaginatedResponse | CompetitorAnalysis.tsx |
| GET | /api/v1/competitor-analysis/{id} | — | CompetitorAnalysisResponse | CompetitorAnalysis.tsx |

### CompetitorAnalysisResponse 字段

```
id: str
asin: str
product_url: str | null
marketplace: str
product_title: str | null
brand: str | null
seller_name: str | null
store_name: str | null
category: str | null
subcategory: str | null
price: str | null
rating: float | null
review_count: int | null
bought_in_past_month_raw: str | null
revenue_floor_30d: float | null
overall_judgment: str | null
main_strengths: list | null
main_weaknesses: list | null
attack_points: list | null
worth_benchmarking: bool | null
listing_presentation_json: dict | null
twelve_dimension_result_json: dict | null
created_at: datetime
```

## Prelaunch Check（上架准入）

| Method | Path | 请求体 | 响应 | 前端调用方 |
|--------|------|--------|------|-----------|
| POST | /api/v1/prelaunch-check/analyze | PrelaunchCheckRequest | PrelaunchCheckResponse | PrelaunchCheck.tsx |
| GET | /api/v1/prelaunch-check?page=N | — | PaginatedResponse | PrelaunchCheck.tsx |

### PrelaunchCheckRequest 字段

```
product_name: str (required)
marketplace: str = "amazon.com"
title_draft: str | null
key_highlights: str | null
bullet_1 ~ bullet_5: str | null
image_count: int = 0
image_slots: list = []
main_image_path: str | null
image_2_path ~ image_7_path: str | null
aplus_images_json: list | null
```

### PrelaunchCheckResponse 字段

```
id: str
product_name: str
marketplace: str
title_draft: str | null
key_highlights: str | null
bullet_1 ~ bullet_5: str | null
main_image_path: str | null
image_2_path ~ image_7_path: str | null
aplus_images_json: list | null
admission_result: str | null       # 可以上架 | 谨慎上架 | 暂不建议上架
conclusion: str | null
position_diagnoses_json: list | null  # PositionDiagnosis[]
next_action: str | null
created_at: datetime
```

### PositionDiagnosis 字段（position_diagnoses_json 数组元素）

```
position_id: str
position_name: str
position_type: str
content_text: str | null
image_url: str | null
status: str                         # 通过 | 需修改 | 缺失
issue: str | null
impact: str | null
recommendation: str | null
modification_example: str | null
```

## Conversion Diagnosis（承接转化）

| Method | Path | 请求体 | 响应 | 前端调用方 |
|--------|------|--------|------|-----------|
| POST | /api/v1/conversion-diagnosis/analyze | {asin?, product_url?, marketplace?} | ConversionDiagnosisResponse | ConversionDiagnosis.tsx |
| GET | /api/v1/conversion-diagnosis/history?page=N | — | PaginatedResponse | ConversionDiagnosis.tsx, TrafficStrategy.tsx |
| GET | /api/v1/conversion-diagnosis/{id} | — | ConversionDiagnosisResponse | ConversionDiagnosis.tsx |
| POST | /api/v1/conversion-diagnosis/multi-source | {asin, marketplace?, ad_metrics?, listing_data?, ai_result?, top20_context?} | dict | ConversionDiagnosis.tsx |

### ConversionDiagnosisResponse 字段

```
id: str
asin: str
product_url: str | null
marketplace: str
product_title: str | null
overall_conclusion: str | null
biggest_breakpoint: str | null
priority_position: str | null
priority_action: str | null
impacted_ad_metrics: list[str] | null
current_status: str | null
position_diagnoses_json: list | null   # ConversionPositionDiagnosis[]
ai_readability_score_json: dict | null
ai_readability_score_version: str | null
primary_matched_proposition_code: str | null
overall_health_score: int | null
root_cause: str | null
funnel_diagnosis: list | null
heatmap: list | null
top_3_actions: list | null
keyword_map: list | null
data_sources: dict | null
confidence: str | null
created_at: datetime
```

## Validation Tasks（验证任务）

| Method | Path | 请求体 | 响应 | 前端调用方 |
|--------|------|--------|------|-----------|
| GET | /api/v1/validation-tasks?asin=X | — | PaginatedResponse<ValidationTaskResponse> | TodayDecisions, TrafficStrategy, BusinessValidation |
| POST | /api/v1/validation-tasks | ValidationTaskCreate | ValidationTaskResponse | TrafficStrategy, TodayDecisions |
| PATCH | /api/v1/validation-tasks/{id} | ValidationTaskUpdate | ValidationTaskResponse | TodayDecisions, BusinessValidation |

### ValidationTaskResponse 字段

```
id: str
asin: str
proposition_code: str
proposition_name: str | null
source_module: str | null
source_record_id: str | null
hypothesis_text: str | null
evidence_snapshot: dict | null
controlled_variable: str | null
forbidden_simultaneous_changes: list | null
validation_period: str | null        # 7d | 14d | 30d
success_criteria: str | null
failure_criteria: str | null
execution_status: str                # pending | running | completed
result_status: str | null            # effective | ineffective | interfered | insufficient_data
next_action: str | null
created_at: datetime
```

## Execution Records（执行记录）

| Method | Path | 请求体 | 响应 | 前端调用方 |
|--------|------|--------|------|-----------|
| GET | /api/v1/execution-records?task_id=X | — | PaginatedResponse<ExecutionRecordResponse> | YesterdayReport, TodayDecisions, TrafficStrategy, ExecutionRecords |
| POST | /api/v1/execution-records | ExecutionRecordCreate | ExecutionRecordResponse | TodayDecisions, TrafficStrategy |

### ExecutionRecordResponse 字段

```
id: str
validation_task_id: str
asin: str
executed_at: datetime
executor: str | null
action_summary: str | null
changed_variable: str | null
changed_position: str | null
change_detail: str | null
cost_amount: float | null
cost_type: str | null               # ad_spend | design_cost | other
evidence_note: str | null
created_at: datetime
```

## Validation Results（效果验证）

| Method | Path | 请求体 | 响应 | 前端调用方 |
|--------|------|--------|------|-----------|
| GET | /api/v1/validation-results?page_size=N | — | PaginatedResponse<ValidationResultResponse> | BusinessValidation |
| POST | /api/v1/validation-results | ValidationResultCreate | ValidationResultResponse | BusinessValidation |

### ValidationResultResponse 字段

```
id: str
validation_task_id: str
asin: str
baseline_metrics_json: dict | null
result_metrics_json: dict | null
sample_days: int | null
sample_clicks: int | null
sample_orders: int | null
suggested_result_status: str | null
final_result_status: str | null      # effective | ineffective | interfered | insufficient_data
attribution_conclusion: str | null
notes: str | null
next_step: str | null
created_at: datetime
```

## ASIN Profiles（ASIN 经营档案）

| Method | Path | 请求体 | 响应 | 前端调用方 |
|--------|------|--------|------|-----------|
| GET | /api/v1/asin-profiles | — | AsinOperationProfileResponse[] | TrafficStrategy |

### AsinOperationProfileResponse 字段

```
id: str
asin: str
marketplace: str
product_title: str | null
category: str | null
lifecycle_stage: str | null
total_validation_count: int
effective_count: int
ineffective_count: int
interfered_count: int
insufficient_data_count: int
successful_propositions_json: list | null
failed_propositions_json: list | null
repeated_failure_patterns_json: list | null
current_main_problem: str | null
next_recommended_proposition: str | null
asin_learning_summary: str | null
updated_at: datetime
```

## Lifecycle（生命周期）

| Method | Path | 请求体 | 响应 | 前端调用方 |
|--------|------|--------|------|-----------|
| GET | /api/v1/lifecycle/{asin} | — | LifecycleData | TrafficStrategy |
| POST | /api/v1/lifecycle/{asin}/apply | — | LifecycleData | TrafficStrategy |

## Report Uploads（报表上传）

| Method | Path | 请求体 | 响应 | 前端调用方 |
|--------|------|--------|------|-----------|
| POST | /api/v1/report-uploads/stage | ReportUploadStagingRequest | ReportUploadStagingResponse | TodayDecisions |

## Reports（战报 + 决策）

| Method | Path | 请求体 | 响应 | 前端调用方 |
|--------|------|--------|------|-----------|
| GET | /api/v1/reports/yesterday | — | YesterdayReport | YesterdayReport.tsx |
| GET | /api/v1/reports/today | — | TodayDecisions | TodayDecisions.tsx |

### YesterdayReport 字段

```
date: str
summary: {
  total_executions: int
  total_cost: float
  ad_spend: float
  changed_positions: int
  active_asins: int
  pending_tasks: int
}
recent_ads: Array<{asin, cost, summary, date}>
validation_stats: {effective, ineffective, interfered, insufficient_data}
active_problems: Array<{asin, problem, next_action}>
profile_summaries: Array<{
  asin, product_title, total_validations, effective, ineffective,
  ad_spend, ad_executions, total_cost, impressions, clicks, orders, sales,
  current_problem, next_recommended, learning
}>
```

### TodayDecisions 字段

```
date: str
summary: {pending: int, running: int, effective: int}
pending: DecisionItem[]
running: DecisionItem[]
effective: DecisionItem[]
global_recommendation: str
budget_gate: {status: str, limit: float | null}
```

### DecisionItem 字段

```
id: str
asin: str
product_title: str | null
hypothesis: str
source: str
validation_period: str | null
estimated_cost: float | null
created_at: str
priority_score: int                  # 历史信号评分
history_signal: str                  # 可靠方向 | 值得尝试 | 不建议重试 | 新方向
budget_gate: {status: str, limit: float | null, blocked: bool}
# running 专属:
running_days?: int
# effective 专属:
result_id?: str
conclusion?: str | null
verified_at?: str
next_step?: str
```

## Help（帮助助手）

| Method | Path | 请求体 | 响应 | 前端调用方 |
|--------|------|--------|------|-----------|
| POST | /api/v1/help/chat | {message, language, page_url?} | {answer, source, should_create_ticket, suggested_issue_type, message_id?} | HelpAssistant.tsx |
| POST | /api/v1/help/tickets | {issue_type, priority, language, page_url?, user_message, screenshots?} | HelpTicketResponse | HelpAssistant.tsx |
| GET | /api/v1/help/tickets | — | HelpTicketResponse[] | HelpAssistant.tsx |
| GET | /api/v1/help/faq?language=zh|en | — | HelpFaqResponse[] | HelpAssistant.tsx |

## Admin（管理后台）

| Method | Path | 请求体 | 响应 | 前端调用方 |
|--------|------|--------|------|-----------|
| GET | /api/v1/admin/propositions | — | PropositionResponse[] | AdminDashboard.tsx |
| GET | /api/v1/admin/profiles | — | AsinOperationProfileResponse[] | AdminDashboard.tsx |
| GET | /api/v1/admin/audit | — | dict | AdminDashboard.tsx |
| GET | /api/v1/admin/rules | — | dict | AdminDashboard.tsx |
| PATCH | /api/v1/admin/rules/{ruleId} | {items: string[]} | dict | AdminDashboard.tsx |
| POST | /api/v1/admin/translate | {title, claims, ...} | dict | AdminDashboard.tsx |

## Health

| Method | Path | 响应 |
|--------|------|------|
| GET | /health | {status: "ok", version: str} |
