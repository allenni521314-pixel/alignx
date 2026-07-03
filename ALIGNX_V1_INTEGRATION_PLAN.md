# AlignX V1.0 Integration Plan

> 生成时间：2026-07-03
> 基于：ALIGNX_INTEGRATION_AUDIT.md
> 原则：只读不改 → 制定计划 → 逐步执行 → 验证

---

## 1. 保留清单

### 1.1 前端保留页面（12个业务页面 + 2个公开页面）

| # | 页面 | 路由 | 处理方式 |
|---|------|------|----------|
| 1 | MarketOpportunity.tsx | /market-opportunity | ✅ 保留原样 |
| 2 | CompetitorAnalysis.tsx | /competitor-analysis | ✅ 保留原样 |
| 3 | PrelaunchCheck.tsx | /prelaunch-check | ✅ 保留原样 |
| 4 | YesterdayReport.tsx | /yesterday-report | ✅ 保留原样 |
| 5 | TodayDecisions.tsx | /today-decisions | ⚠️ 保留，隔离 mock 常量 |
| 6 | ConversionDiagnosis.tsx | /conversion-diagnosis | ✅ 保留原样 |
| 7 | TrafficStrategy.tsx | /traffic-strategy | ✅ 保留原样 |
| 8 | ExecutionRecords.tsx | /execution-records | ⚠️ 保留，隔离 mock 常量 |
| 9 | BusinessValidation.tsx | /business-validation | ✅ 保留原样 |
| 10 | AccountCenter.tsx | /account | ✅ 保留原样 |
| 11 | AdminDashboard.tsx | /admin | ✅ 保留原样 |
| 12 | Login.tsx | /login | ✅ 保留原样 |
| 13 | PublicSite.tsx | /, /en/*, /zh/* | ✅ 保留原样 |

### 1.2 后端保留模块（14个 API 路由）

全部保留，无删除。

### 1.3 保留的公共文件

| 文件 | 说明 |
|------|------|
| frontend/src/lib/api.ts | API 客户端（795行，完整） |
| frontend/src/lib/label-maps.ts | 字段翻译入口（120行） |
| frontend/src/lib/i18n.tsx | 国际化 |
| frontend/src/lib/useProgress.ts | 进度条 hook |
| frontend/src/lib/usePageState.ts | 页面状态持久化 hook |
| frontend/src/components/Sidebar.tsx | 侧边栏（不修改） |
| frontend/src/components/ProgressBar.tsx | 进度条组件 |
| frontend/src/components/help/HelpAssistant.tsx | 帮助助手 |
| frontend/src/App.tsx | 路由定义（需删除孤立路由） |
| frontend/src/main.tsx | 入口 |
| render.yaml | 部署配置 |
| AGENTS.md | 工程护栏 |
| scripts/engineering_guardrails.py | 护栏脚本 |
| backend/requirements.txt | Python 依赖 |
| backend/run.py | 启动脚本 |
| backend/start.py | 环境变量启动 |

---

## 2. 删除/隔离清单

### 2.1 删除（前端死页面 + 孤立路由）

| 文件 | 原因 | 处理 |
|------|------|------|
| frontend/src/pages/ValidationResults.tsx | 死文件，未在 App.tsx import，功能已被 BusinessValidation.tsx 覆盖 | **删除文件** |
| frontend/src/pages/ProductResearch.tsx | 有路由无侧边栏入口，与 MarketOpportunity.tsx 调用相同 API | **删除文件** |
| App.tsx 中的 `/product-research` 路由 | 孤立路由，删除 ProductResearch 后无组件 | **删除路由行** |

### 2.2 隔离（旧版废弃代码 — 不删除，移入 _archive/）

| 目录/文件 | 原因 | 处理 |
|-----------|------|------|
| app/backend/ | 旧后端，60+ 路由，无 /api/v1 前缀 | **移入 _archive/** |
| app/frontend/ | 旧前端，shadcn/ui，20+ 页面 | **移入 _archive/** |
| app/chrome-extension-alignx-local-capture/ | Chrome 扩展，独立项目 | **移入 _archive/** |
| app/docs/ | 研究文档 | **移入 _archive/** |
| app/start_app_v2.sh | 旧启动脚本 | **移入 _archive/** |
| app/.mgx | 旧配置 | **移入 _archive/** |
| code.ipynb | 旧 Jupyter notebook | **移入 _archive/** |
| CAUSAL_API_QUICKSTART.md | 旧文档 | **移入 _archive/** |
| CAUSAL_COSMO_FINAL_STATUS.md | 旧文档 | **移入 _archive/** |
| CAUSAL_COSMO_UPGRADE.md | 旧文档 | **移入 _archive/** |
| README_UPDATE.md | 旧文档 | **移入 _archive/** |
| todo.md | 旧待办 | **移入 _archive/** |
| .netlify/ | 旧部署残留 | **移入 _archive/** |
| .claude/ | 旧 AI 配置 | **移入 _archive/** |

### 2.3 清理（数据库残留文件）

| 文件 | 处理 |
|------|------|
| backend/alignx.db | **删除**（旧库，V2 用 alignx_v2.db） |
| backend/alignx.db-shm | **删除** |
| backend/alignx.db-wal | **删除** |
| backend/alignx_v2.db-shm | **保留**（WAL 正常文件） |
| backend/alignx_v2.db-wal | **保留** |
| frontend/tsconfig.tsbuildinfo | **删除**（构建缓存） |

---

## 3. Bug 修复清单

### 3.1 🔴 conversion_diagnosis.py — 跨后端 import

**文件**: `backend/app/api/conversion_diagnosis.py`  
**行**: 150  
**问题**: `from app.backend.models.ad_data import Ad_data` — 引用旧后端模型，V2 后端无此路径  
**影响**: `_fetch_ad_metrics_from_db()` 永远返回 None（ImportError 被 try/except 吞掉），multi-source 诊断的 ad_metrics 来源永远缺失  
**修复**: 删除此 import 和 `_fetch_ad_metrics_from_db` 函数体中的旧模型引用。V2 后端无 ad_data 表，广告数据通过 report_upload_staging_records 获取。函数应返回 None 并标注 "not_available"

### 3.2 🔴 conversion_diagnosis.py — CaptureJob.extracted_fields 不存在

**文件**: `backend/app/api/conversion_diagnosis.py`  
**行**: ~175  
**问题**: `job.extracted_fields` — CaptureJob 模型无此字段（只有 raw_html_path, screenshot_path 等）  
**影响**: `_fetch_top20_from_db()` 永远返回 None，multi-source 诊断的 top20 来源永远缺失  
**修复**: 函数返回 None 并标注 "not_available"，或从 ListingSnapshot 关联查询

### 3.3 🟡 TodayDecisions.tsx — 硬编码 mock 数据

**文件**: `frontend/src/pages/TodayDecisions.tsx`  
**行**: 11-28  
**问题**: `PRIORITY_TASKS` 常量含 P0-P3 假数据（ASIN B0FDKQGRCK 等），非后端返回  
**影响**: 页面展示的优先级卡片是假数据，与后端 `reports/today` 返回的 pending/running/effective 无关  
**修复**: 将 `PRIORITY_TASKS` 标注为 `// PLACEHOLDER — 待后端提供优先级数据`，不删除（避免白屏），但加注释说明数据来源

### 3.4 🟡 ExecutionRecords.tsx — mock 效果标签

**文件**: `frontend/src/pages/ExecutionRecords.tsx`  
**行**: 11  
**问题**: `EFFECT` 常量标注 "Mock effect data — will come from validation results API in production"  
**影响**: 效果标签（有效/无效/观察中）是前端硬编码，非后端返回  
**修复**: 保留常量但更新注释，说明这是 UI 展示映射而非 mock 数据（效果标签本质是 result_status 的前端翻译）

---

## 4. 统一路由表

### 4.1 认证后路由（RequireAuth）

| 路径 | 组件 | 侧边栏分组 | 侧边栏标签 |
|------|------|-----------|-----------|
| /market-opportunity | MarketOpportunity | 市场机会 | 产品机会 |
| /competitor-analysis | CompetitorAnalysis | 市场机会 | 竞品分析 |
| /prelaunch-check | PrelaunchCheck | 新品上架 | 上架准入 |
| /yesterday-report | YesterdayReport | 运营验证 | 昨日战报 |
| /today-decisions | TodayDecisions | 运营验证 | 今日决策 |
| /conversion-diagnosis | ConversionDiagnosis | 运营验证 | 承接转化 |
| /traffic-strategy | TrafficStrategy | 运营验证 | 广告测试 |
| /execution-records | ExecutionRecords | 运营验证 | 执行记录 |
| /business-validation | BusinessValidation | 运营验证 | 效果验证 |
| /account | AccountCenter | 账号中心 | 账号中心 |
| /admin | AdminDashboard | （仅管理员） | 管理后台 |

**删除的路由**: `/product-research`（孤立，无侧边栏入口）

### 4.2 公开路由

| 路径 | 组件 |
|------|------|
| / | RootRedirect |
| /login | Login |
| /en, /en/* | PublicSite |
| /zh, /zh/* | PublicSite |

---

## 5. API 合同

### 5.1 前端→后端调用表

| 前端函数 | HTTP | 路径 | 请求体 | 响应类型 |
|---------|------|------|--------|---------|
| sendLoginCode | POST | /api/v1/auth/send-code | {email} | {code?, detail?} |
| verifyLoginCode | POST | /api/v1/auth/verify-code | {email, code, store_name?} | {success, token, user_id, email, store_name} |
| analyzeMarketOpportunity | POST | /api/v1/market-opportunity/analyze | {keyword, marketplace} | MarketOpportunityResponse |
| listMarketOpportunities | GET | /api/v1/market-opportunity?page=N | — | PaginatedResponse |
| getMarketOpportunity | GET | /api/v1/market-opportunity/{id} | — | MarketOpportunityResponse |
| analyzeCompetitor | POST | /api/v1/competitor-analysis/analyze | {asin, marketplace} | CompetitorAnalysisResponse |
| listCompetitorAnalyses | GET | /api/v1/competitor-analysis?page=N | — | PaginatedResponse |
| getCompetitorAnalysis | GET | /api/v1/competitor-analysis/{id} | — | CompetitorAnalysisResponse |
| analyzePrelaunch | POST | /api/v1/prelaunch-check/analyze | PrelaunchCheckRequest | PrelaunchCheckResponse |
| listPrelaunchChecks | GET | /api/v1/prelaunch-check?page=N | — | PaginatedResponse |
| diagnoseConversion | POST | /api/v1/conversion-diagnosis/analyze | {asin, marketplace} | ConversionDiagnosisResponse |
| listConversionDiagnoses | GET | /api/v1/conversion-diagnosis/history?page=N | — | PaginatedResponse |
| getConversionDiagnosis | GET | /api/v1/conversion-diagnosis/{id} | — | ConversionDiagnosisResponse |
| runMultiSourceDiagnosis | POST | /api/v1/conversion-diagnosis/multi-source | {asin, marketplace, ...} | dict |
| listValidationTasks | GET | /api/v1/validation-tasks?asin=X | — | PaginatedResponse |
| createValidationTask | POST | /api/v1/validation-tasks | ValidationTaskCreate | ValidationTaskResponse |
| updateValidationTask | PATCH | /api/v1/validation-tasks/{id} | ValidationTaskUpdate | ValidationTaskResponse |
| listExecutionRecords | GET | /api/v1/validation-tasks?task_id=X | — | PaginatedResponse |
| createExecutionRecord | POST | /api/v1/execution-records | ExecutionRecordCreate | ExecutionRecordResponse |
| listValidationResults | GET | /api/v1/validation-results?page_size=N | — | PaginatedResponse |
| createValidationResult | POST | /api/v1/validation-results | ValidationResultCreate | ValidationResultResponse |
| listAsinProfiles | GET | /api/v1/asin-profiles | — | AsinOperationProfileResponse[] |
| getLifecycle | GET | /api/v1/lifecycle/{asin} | — | LifecycleData |
| applyLifecycle | POST | /api/v1/lifecycle/{asin}/apply | — | LifecycleData |
| stageReportUpload | POST | /api/v1/report-uploads/stage | ReportUploadStagingRequest | ReportUploadStagingResponse |
| getYesterdayReport | GET | /api/v1/reports/yesterday | — | YesterdayReport |
| getTodayDecisions | GET | /api/v1/reports/today | — | TodayDecisions |
| sendHelpMessage | POST | /api/v1/help/chat | HelpChatRequest | HelpChatResponse |
| createHelpTicket | POST | /api/v1/help/tickets | HelpTicketCreate | HelpTicketResponse |
| listHelpTickets | GET | /api/v1/help/tickets | — | HelpTicketResponse[] |
| listHelpFaq | GET | /api/v1/help/faq?language=X | — | HelpFaqResponse[] |
| listAdminPropositions | GET | /api/v1/admin/propositions | — | PropositionResponse[] |
| listAdminProfiles | GET | /api/v1/admin/profiles | — | AsinOperationProfileResponse[] |
| getAdminAudit | GET | /api/v1/admin/audit | — | dict |
| listAdminRules | GET | /api/v1/admin/rules | — | dict |
| updateAdminRule | PATCH | /api/v1/admin/rules/{ruleId} | {items} | dict |
| translateBuyerLanguage | POST | /api/v1/admin/translate | {title, claims, ...} | dict |

### 5.2 前端必需字段 → 后端必须返回字段

#### YesterdayReport（后端 reports.py → 前端 YesterdayReport interface）

| 前端字段 | 后端来源 | 状态 |
|---------|---------|------|
| date | datetime.utcnow() | ✅ |
| summary.total_executions | len(executions) | ✅ |
| summary.total_cost | sum(cost_amount) | ✅ |
| summary.ad_spend | sum(cost_amount where ad_spend) | ✅ |
| summary.changed_positions | len(set(changed_position)) | ✅ |
| summary.active_asins | len(profiles) | ✅ |
| summary.pending_tasks | len(tasks where pending) | ✅ |
| recent_ads[] | executions where ad_spend | ✅ |
| validation_stats.* | ValidationResult 聚合 | ✅ |
| active_problems[] | AsinOperationProfile.current_main_problem | ✅ |
| profile_summaries[].* | AsinOperationProfile + ExecutionRecord 聚合 | ✅ |

#### TodayDecisions（后端 reports.py → 前端 TodayDecisions interface）

| 前端字段 | 后端来源 | 状态 |
|---------|---------|------|
| date | datetime.utcnow() | ✅ |
| summary.pending/running/effective | ValidationTask 聚合 | ✅ |
| pending[].* | _build_item() | ✅ |
| running[].running_days | _running_days() | ✅ |
| effective[].conclusion/verified_at/next_step | ValidationResult | ✅ |
| global_recommendation | 逻辑生成 | ✅ |
| budget_gate | Account.balance | ✅ |
| DecisionItem.history_signal | _history_signal() | ✅ |
| DecisionItem.priority_score | _history_score() | ✅ |
| DecisionItem.budget_gate | _budget_gate() | ✅ |

---

## 6. 执行步骤（第三阶段）

### Step 1: 创建 _archive/ 目录，移入废弃代码

```bash
mkdir -p _archive
mv app/ _archive/app/
mv code.ipynb _archive/
mv CAUSAL_API_QUICKSTART.md _archive/
mv CAUSAL_COSMO_FINAL_STATUS.md _archive/
mv CAUSAL_COSMO_UPGRADE.md _archive/
mv README_UPDATE.md _archive/
mv todo.md _archive/
mv .netlify/ _archive/netlify/
mv .claude/ _archive/claude/
```

### Step 2: 删除前端死页面 + 清理路由

```bash
rm frontend/src/pages/ValidationResults.tsx
rm frontend/src/pages/ProductResearch.tsx
```

App.tsx 删除:
- `import ProductResearch from "./pages/ProductResearch";`
- `<Route path="/product-research" element={<ProductResearch />} />`

### Step 3: 清理 DB 残留

```bash
rm backend/alignx.db backend/alignx.db-shm backend/alignx.db-wal
rm frontend/tsconfig.tsbuildinfo
```

### Step 4: 修复后端 bug

**conversion_diagnosis.py**:
- 删除 `from app.backend.models.ad_data import Ad_data`
- `_fetch_ad_metrics_from_db` 返回 None（V2 无 ad_data 表）
- `_fetch_top20_from_db` 不引用 `job.extracted_fields`（字段不存在）

### Step 5: 标注 mock 数据

**TodayDecisions.tsx**: PRIORITY_TASKS 加注释 `// PLACEHOLDER`
**ExecutionRecords.tsx**: EFFECT 注释更新为 UI 映射说明

### Step 6: 验证

```bash
cd frontend && npm run build        # 必须通过
cd backend && python3 -c "from app.main import app; print('OK')"  # 必须通过
```

---

## 7. 不修改清单（铁律）

- ❌ 不修改 Sidebar.tsx（左侧菜单顺序/结构）
- ❌ 不修改任何页面的 UI 设计
- ❌ 不修改 label-maps.ts 的翻译内容
- ❌ 不修改 backend/app/models/（表结构）
- ❌ 不修改 backend/app/schemas/（API 合同）
- ❌ 不修改 render.yaml（部署配置）
- ❌ 不修改 AGENTS.md（工程护栏）
- ❌ 不新增任何功能
- ❌ 不重命名任何路由
- ❌ 不修改业务定位和页面含义
