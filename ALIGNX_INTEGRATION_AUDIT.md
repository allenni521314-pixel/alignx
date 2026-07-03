# AlignX V1.0 Integration Audit Report

> 生成时间：2026-07-03  
> 分支：alignx-v1-clean  
> 审计范围：全项目只读扫描，不修改任何文件

---

## 1. 项目拓扑全景

### 1.1 目录结构

```
~/Desktop/alignx/
├── frontend/              ← ✅ 活跃 V1 前端（React+TS+Vite+Tailwind，端口5173）
├── backend/               ← ✅ 活跃 V1 后端（FastAPI+SQLAlchemy，端口8001）
│   ├── app/
│   │   ├── api/           ← 14 个 API 路由模块
│   │   ├── core/          ← 业务核心逻辑（AI、抓取、诊断、规则）
│   │   ├── services/      ← 服务层（数据聚合、AI pipeline）
│   │   ├── models/        ← 19 张 ORM 表定义
│   │   ├── schemas/       ← Pydantic 请求/响应模型
│   │   ├── config.py
│   │   ├── constants.py
│   │   ├── database.py
│   │   └── main.py        ← FastAPI 入口
│   ├── run.py             ← uvicorn 启动脚本
│   ├── start.py           ← 带环境变量启动
│   └── requirements.txt
├── app/                   ← ❌ 旧版废弃代码（整个目录）
│   ├── backend/           ← 旧后端（60+路由，50+服务，无/api/v1前缀）
│   ├── frontend/          ← 旧前端（shadcn/ui，20+页面）
│   ├── chrome-extension-alignx-local-capture/
│   ├── docs/              ← 研究文档
│   └── start_app_v2.sh
├── scripts/               ← 工程护栏脚本
├── render.yaml            ← Render 部署配置（指向 backend/ + frontend/）
├── AGENTS.md              ← 工程护栏规则
└── 旧文档 (CAUSAL_*.md, README_UPDATE.md, todo.md)
```

### 1.2 活跃代码判定依据

| 判据 | frontend/ + backend/ | app/frontend/ + app/backend/ |
|------|---------------------|------------------------------|
| render.yaml 部署指向 | ✅ `backend/` + `frontend/` | ❌ 未引用 |
| 前端 API 前缀 `/api/v1` | ✅ 匹配 | ❌ 无此前缀 |
| Vite 代理 → localhost:8001 | ✅ 匹配 `backend/run.py` | ❌ |
| npm run build 通过 | ✅ | 未测试 |
| 代码结构清洁度 | 14 路由 / 14 页面 | 60+ 路由 / 20+ 页面 |
| 最后修改时间 | 2026-07-02 | 2026-06-23 |

**结论：`frontend/` + `backend/` 是 V1 活跃主线，`app/` 整个目录是旧版废弃代码。**

---

## 2. 前端页面清单

### 2.1 活跃页面（14个 .tsx 文件）

| # | 文件 | 路由 | 侧边栏 | 状态 | API 调用 |
|---|------|------|--------|------|----------|
| 1 | MarketOpportunity.tsx | /market-opportunity | ✅ 产品机会 | ✅ 活跃 | market-opportunity |
| 2 | CompetitorAnalysis.tsx | /competitor-analysis | ✅ 竞品分析 | ✅ 活跃 | competitor-analysis |
| 3 | PrelaunchCheck.tsx | /prelaunch-check | ✅ 上架准入 | ✅ 活跃 | prelaunch-check |
| 4 | YesterdayReport.tsx | /yesterday-report | ✅ 昨日战报 | ✅ 活跃 | reports/yesterday, execution-records |
| 5 | TodayDecisions.tsx | /today-decisions | ✅ 今日决策 | ⚠️ 含 mock | reports/today, validation-tasks, execution-records, report-uploads |
| 6 | ConversionDiagnosis.tsx | /conversion-diagnosis | ✅ 承接转化 | ✅ 活跃 | conversion-diagnosis |
| 7 | TrafficStrategy.tsx | /traffic-strategy | ✅ 广告测试 | ✅ 活跃 | asin-profiles, conversion-diagnosis, validation-tasks, lifecycle, execution-records |
| 8 | ExecutionRecords.tsx | /execution-records | ✅ 执行记录 | ⚠️ 含 mock | execution-records |
| 9 | BusinessValidation.tsx | /business-validation | ✅ 效果验证 | ✅ 活跃 | validation-results, validation-tasks |
| 10 | AccountCenter.tsx | /account | ✅ 账号中心 | ✅ 活跃 | 无 API 调用（纯静态 UI） |
| 11 | AdminDashboard.tsx | /admin | 🔒 仅管理员 | ✅ 活跃 | admin/* |
| 12 | Login.tsx | /login | 公开页面 | ✅ 活跃 | auth/* |
| 13 | PublicSite.tsx | /, /en/*, /zh/* | 公开页面 | ✅ 活跃 | 无 API |
| 14 | **ProductResearch.tsx** | /product-research | ❌ 不在侧边栏 | ⚠️ 孤立 | market-opportunity（与 #1 重复调用） |

### 2.2 死页面 / 重复页面

| 文件 | 问题 | 详情 |
|------|------|------|
| **ValidationResults.tsx** | 🔴 死文件 | 未在 App.tsx 中 import，无路由，无侧边栏入口。功能已被 BusinessValidation.tsx 覆盖（同样调用 `listValidationResults`） |
| **ProductResearch.tsx** | 🟡 孤立路由 | 在 App.tsx 有路由 `/product-research`，但侧边栏无入口。调用 `analyzeMarketOpportunity` / `listMarketOpportunities` / `getMarketOpportunity`，与 MarketOpportunity.tsx 完全重复 |

---

## 3. 后端 API 清单

### 3.1 活跃后端路由（14个，全部 `/api/v1` 前缀）

| # | 路由模块 | 前缀 | 前端调用方 |
|---|---------|------|-----------|
| 1 | auth.py | /api/v1/auth | Login.tsx |
| 2 | market_opportunity.py | /api/v1/market-opportunity | MarketOpportunity.tsx, ProductResearch.tsx |
| 3 | competitor_analysis.py | /api/v1/competitor-analysis | CompetitorAnalysis.tsx |
| 4 | prelaunch_check.py | /api/v1/prelaunch-check | PrelaunchCheck.tsx |
| 5 | conversion_diagnosis.py | /api/v1/conversion-diagnosis | ConversionDiagnosis.tsx, TrafficStrategy.tsx |
| 6 | validation_tasks.py | /api/v1/validation-tasks | TodayDecisions.tsx, TrafficStrategy.tsx, BusinessValidation.tsx |
| 7 | validation_results.py | /api/v1/validation-results | BusinessValidation.tsx, ValidationResults.tsx(死) |
| 8 | execution_records.py | /api/v1/execution-records | YesterdayReport.tsx, TodayDecisions.tsx, TrafficStrategy.tsx, ExecutionRecords.tsx |
| 9 | asin_profiles.py | /api/v1/asin-profiles | TrafficStrategy.tsx |
| 10 | report_uploads.py | /api/v1/report-uploads | TodayDecisions.tsx |
| 11 | lifecycle.py | /api/v1/lifecycle | TrafficStrategy.tsx |
| 12 | help.py | /api/v1/help | HelpAssistant.tsx (组件) |
| 13 | admin.py | /api/v1/admin | AdminDashboard.tsx |
| 14 | reports.py | /api/v1/reports | YesterdayReport.tsx, TodayDecisions.tsx, AdminDashboard.tsx |

### 3.2 数据库模型（19张表）

```
users, verification_codes, accounts, stores, asins,
capture_jobs, listing_snapshots,
market_opportunity_reports, competitor_analysis_reports,
prelaunch_checks, conversion_diagnoses,
proposition_categories, propositions,
validation_tasks, execution_records, validation_results,
asin_operation_profiles, ai_call_logs,
report_upload_batches, report_upload_staging_records,
operation_audit_logs,
help_tickets, help_messages, help_faq_items, help_feedback
```

数据库文件：`backend/alignx_v2.db`（SQLite，WAL模式）

---

## 4. 问题清单

### 4.1 🔴 严重 — 必须处理

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| S1 | **两套后端并存** | `app/backend/` vs `backend/` | 混乱源头。旧后端 60+ 路由无 `/api/v1` 前缀，与前端不兼容 |
| S2 | **两套前端并存** | `app/frontend/` vs `frontend/` | 旧前端 20+ 页面，shadcn/ui 体系，与当前 V1 完全不同 |
| S3 | **死页面 ValidationResults.tsx** | `frontend/src/pages/` | 未被引用，与 BusinessValidation.tsx 功能重复 |
| S4 | **孤立路由 ProductResearch.tsx** | `frontend/src/pages/` | 有路由无入口，与 MarketOpportunity.tsx 调用相同 API |

### 4.2 🟡 中等 — 建议处理

| # | 问题 | 位置 | 详情 |
|---|------|------|------|
| M1 | **TodayDecisions 硬编码 mock** | TodayDecisions.tsx L11-28 | `PRIORITY_TASKS` 常量含 P0-P3 假数据（ASIN B0FDKQGRCK 等），非后端返回 |
| M2 | **ExecutionRecords mock 效果数据** | ExecutionRecords.tsx L11 | `EFFECT` 常量标注 "Mock effect data — will come from validation results API in production" |
| M3 | **旧文档残留** | 根目录 | CAUSAL_API_QUICKSTART.md, CAUSAL_COSMO_FINAL_STATUS.md, CAUSAL_COSMO_UPGRADE.md, README_UPDATE.md, todo.md — 均为旧版 Codex 生成 |
| M4 | **多个 DB 文件** | backend/ | alignx.db + alignx_v2.db 同时存在（含 WAL/SHM 文件） |
| M5 | **app/start_app_v2.sh** | app/ | 旧启动脚本，指向旧后端 |

### 4.3 🟢 轻微 — 记录备查

| # | 问题 | 位置 | 详情 |
|---|------|------|------|
| L1 | chunk 大小警告 | frontend build | 508KB > 500KB 阈值，建议未来 code-split |
| L2 | code.ipynb | 根目录 | 92KB Jupyter notebook，非生产代码 |
| L3 | sketches/ | 根目录 | 设计草图目录 |
| L4 | .netlify/ | 根目录 | 旧 Netlify 部署残留 |

---

## 5. 路由表（当前状态）

### 5.1 认证后路由（RequireAuth 包裹）

| 路径 | 组件 | 侧边栏入口 | 状态 |
|------|------|-----------|------|
| /market-opportunity | MarketOpportunity | ✅ 产品机会 | 活跃 |
| /product-research | ProductResearch | ❌ 无 | ⚠️ 孤立 |
| /competitor-analysis | CompetitorAnalysis | ✅ 竞品分析 | 活跃 |
| /prelaunch-check | PrelaunchCheck | ✅ 上架准入 | 活跃 |
| /yesterday-report | YesterdayReport | ✅ 昨日战报 | 活跃 |
| /today-decisions | TodayDecisions | ✅ 今日决策 | 活跃（含 mock） |
| /conversion-diagnosis | ConversionDiagnosis | ✅ 承接转化 | 活跃 |
| /traffic-strategy | TrafficStrategy | ✅ 广告测试 | 活跃 |
| /execution-records | ExecutionRecords | ✅ 执行记录 | 活跃（含 mock） |
| /business-validation | BusinessValidation | ✅ 效果验证 | 活跃 |
| /account | AccountCenter | ✅ 账号中心 | 活跃 |
| /admin | AdminDashboard | 🔒 管理员 | 活跃 |

### 5.2 公开路由

| 路径 | 组件 | 说明 |
|------|------|------|
| / | RootRedirect → /login 或 /market-opportunity | 根跳转 |
| /login | Login | 登录页 |
| /en, /en/* | PublicSite | 英文公开站 |
| /zh, /zh/* | PublicSite | 中文公开站 |

### 5.3 侧边栏导航结构（不允许修改）

```
市场机会 (group)
  ├── 产品机会 → /market-opportunity
  └── 竞品分析 → /competitor-analysis
新品上架 (group)
  └── 上架准入 → /prelaunch-check
运营验证 (group)
  ├── 昨日战报 → /yesterday-report
  ├── 今日决策 → /today-decisions
  ├── 承接转化 → /conversion-diagnosis
  ├── 广告测试 → /traffic-strategy
  ├── 执行记录 → /execution-records
  └── 效果验证 → /business-validation
账号中心 (group, 底部)
  ├── 数据中心 → /account#data-center
  ├── 充值记录 → /account#recharge-records
  └── 消费记录 → /account#spending-records
管理后台 (仅 admin 可见) → /admin
```

---

## 6. 构建状态

| 检查项 | 状态 | 备注 |
|--------|------|------|
| `npm run build` (vite) | ✅ 通过 | 1658 modules, 1.87s |
| `tsc -b` (TypeScript) | ✅ 通过 | 无类型错误 |
| chunk 大小警告 | ⚠️ | 508KB > 500KB（非阻塞） |
| 后端 import 测试 | ⏭️ 未完成 | 被 timeout 拦截，需后续验证 |

---

## 7. 字段一致性快速检查

### 7.1 前端接口定义 vs 后端 Schema 对应关系

| 前端 Interface | 后端 Schema | 一致性 |
|---------------|------------|--------|
| MarketOpportunity | MarketOpportunityResponse | ✅ 字段匹配 |
| CompetitorAnalysis | CompetitorAnalysisResponse | ✅ 字段匹配 |
| PrelaunchCheck | PrelaunchCheckResponse | ✅ 字段匹配 |
| ConversionDiagnosis | ConversionDiagnosisResponse | ✅ 字段匹配（后端含额外 funnel/heatmap 字段） |
| ValidationTask | ValidationTaskResponse | ✅ 字段匹配 |
| ExecutionRecord | ExecutionRecordResponse | ✅ 字段匹配 |
| ValidationResult | ValidationResultResponse | ✅ 字段匹配 |
| AsinProfile | AsinOperationProfileResponse | ✅ 字段匹配 |
| YesterdayReport | (reports.py 动态生成) | ⚠️ 需验证后端 service 返回结构 |
| TodayDecisions | (reports.py 动态生成) | ⚠️ 需验证后端 service 返回结构 |

### 7.2 label-maps.ts 字段翻译入口

`frontend/src/lib/label-maps.ts` 是后端字段名 → 中文展示的唯一翻译入口：
- `FUNNEL_STAGE_LABELS` — 漏斗阶段标签
- `POSITION_LABELS` — Listing 位置标签
- `IMPACT_METRIC_LABELS` — 广告指标标签
- `KEYWORD_TYPE_LABELS` — 关键词类型标签
- `label()` / `labelMetrics()` — 统一调用函数

---

## 8. 主线代码判定

### 活跃 V1 主线

```
前端：frontend/（14 页面，React+TS+Vite+Tailwind）
后端：backend/（14 路由，FastAPI+SQLAlchemy+SQLite/PostgreSQL）
部署：render.yaml（backend/ + frontend/）
```

### 废弃代码（可隔离/归档）

```
app/backend/     — 旧后端（60+路由，无/api/v1前缀）
app/frontend/    — 旧前端（shadcn/ui，20+页面）
app/docs/        — 研究文档（可保留参考）
app/chrome-extension-alignx-local-capture/ — Chrome 扩展（独立项目）
app/start_app_v2.sh — 旧启动脚本
code.ipynb       — 旧 Jupyter notebook
CAUSAL_*.md      — 旧文档
README_UPDATE.md — 旧文档
todo.md          — 旧待办
```

---

## 9. 下一步建议（进入第二阶段）

1. **隔离废弃代码**：将 `app/` 目录标记为 `_archive/app/`，不从其中引用任何代码
2. **清理死页面**：`ValidationResults.tsx` 删除或隔离（功能已被 BusinessValidation 覆盖）
3. **处理孤立路由**：`ProductResearch.tsx` 需决策 — 删除路由 + 文件，还是加入侧边栏
4. **清理 mock 数据**：TodayDecisions 的 `PRIORITY_TASKS` 和 ExecutionRecords 的 `EFFECT` 需接入真实后端或标记为 placeholder
5. **统一 DB 文件**：确认 `alignx_v2.db` 为唯一活跃数据库，清理 `alignx.db`
6. **验证后端启动**：需实际运行 `python3 run.py` 确认无 import 错误
7. **验证昨日战报/今日决策 API**：检查 `reports.py` service 返回结构是否与前端 interface 匹配
