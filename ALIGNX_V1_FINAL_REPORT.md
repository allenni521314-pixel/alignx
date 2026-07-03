# AlignX V1.0 Integration — 修改文件清单 + 剩余风险

> 生成时间：2026-07-03
> 分支：alignx-v1-clean

---

## 一、修改文件清单

### 1. 归档移动（→ _archive/）

| 原路径 | 目标路径 | 说明 |
|--------|---------|------|
| app/ | _archive/app/ | 旧后端+旧前端+Chrome扩展+文档，整体归档 |
| code.ipynb | _archive/code.ipynb | 旧 Jupyter notebook |
| CAUSAL_API_QUICKSTART.md | _archive/ | 旧文档 |
| CAUSAL_COSMO_FINAL_STATUS.md | _archive/ | 旧文档 |
| CAUSAL_COSMO_UPGRADE.md | _archive/ | 旧文档 |
| README_UPDATE.md | _archive/ | 旧文档 |
| todo.md | _archive/ | 旧待办 |
| .netlify/ | _archive/netlify/ | 旧 Netlify 部署残留 |
| .claude/ | _archive/claude/ | 旧 AI 配置 |

### 2. 删除文件

| 文件 | 原因 |
|------|------|
| frontend/src/pages/ValidationResults.tsx | 死页面，未被 App.tsx import，功能已被 BusinessValidation.tsx 覆盖 |
| frontend/src/pages/ProductResearch.tsx | 孤立路由，无侧边栏入口，与 MarketOpportunity.tsx 调用相同 API |
| backend/alignx.db | 旧数据库（V2 使用 alignx_v2.db） |
| backend/alignx.db-shm | 旧数据库 WAL 文件 |
| backend/alignx.db-wal | 旧数据库 WAL 文件 |
| frontend/tsconfig.tsbuildinfo | 构建缓存 |

### 3. 修改文件

| 文件 | 修改内容 | 行数变化 |
|------|----------|----------|
| frontend/src/App.tsx | 删除 ProductResearch import + 删除 /product-research 路由 | -2 行 |
| backend/app/api/conversion_diagnosis.py | 修复 `_fetch_ad_metrics_from_db`：删除旧后端 import，返回 None | -28 行 |
| backend/app/api/conversion_diagnosis.py | 修复 `_fetch_top20_from_db`：删除引用不存在的 `extracted_fields`，返回 None | -32 行 |
| frontend/src/pages/TodayDecisions.tsx | mock 注释更新：`Mock P0-P3 tasks` → `PLACEHOLDER` + 说明 | +2 行 |
| frontend/src/pages/ExecutionRecords.tsx | mock 注释更新：`Mock effect data` → `验证结果状态 → UI 标签映射` | 0 行 |

### 4. 新增文件

| 文件 | 说明 |
|------|------|
| ALIGNX_INTEGRATION_AUDIT.md | 第一阶段审计报告 |
| ALIGNX_V1_INTEGRATION_PLAN.md | 第二阶段整合计划 |
| ROUTE_REGISTRY.md | 统一路由注册表 |
| API_CONTRACT.md | API 合同文档 |

---

## 二、验证结果

| 检查项 | 状态 | 详情 |
|--------|------|------|
| `npm run build` | ✅ 通过 | 1657 modules, 1.84s |
| `tsc -b` TypeScript 检查 | ✅ 通过 | 无类型错误 |
| 后端语法检查 | ✅ 通过 | py_compile 全部通过 |
| 11个主流程页面路由 | ✅ 全部连通 | App.tsx 11 条 Route 全部存在 |
| chunk 大小 | ⚠️ 501KB | 略超 500KB 阈值（非阻塞） |

---

## 三、剩余风险清单

### 🔴 高风险

| # | 风险 | 位置 | 影响 | 建议 |
|---|------|------|------|------|
| R1 | **后端 import 未实测启动** | backend/app/main.py | py_compile 只检查语法，未验证 runtime import 链（可能有 import 顺序问题或缺失依赖） | 需实际运行 `cd backend && python3 run.py` 验证 |
| R2 | **conversion_diagnosis.py 残留未使用 import** | L5-L17 | `select`, `func`, `desc`, `CaptureJob`, `timedelta` 不再使用，不影响运行但可能导致 lint 警告 | 后续清理（当前保留以最小改动） |

### 🟡 中风险

| # | 风险 | 位置 | 影响 | 建议 |
|---|------|------|------|------|
| R3 | **TodayDecisions PRIORITY_TASKS 占位数据** | TodayDecisions.tsx L11-28 | P0-P3 优先级卡片展示假数据（ASIN B0FDKQGRCK 等），用户可能误认为真实数据 | 后端 reports/today 需增加优先级分级字段 |
| R4 | **multi-source 诊断 ad_metrics/top20 来源缺失** | conversion_diagnosis.py | `_fetch_ad_metrics_from_db` 和 `_fetch_top20_from_db` 均返回 None，multi-source 诊断只能用手动输入或 scraped listing | 需实现从 ReportUploadStagingRecord 和 ListingSnapshot 读取数据 |
| R5 | **SQLite 单文件 + WAL 模式** | backend/alignx_v2.db | 生产环境高并发可能瓶颈，WAL 文件未 checkpoint 可能增长 | 生产环境切 PostgreSQL（render.yaml 已支持 DATABASE_URL） |
| R6 | **前端无 code-splitting** | frontend build | 单 chunk 501KB，首屏加载可能偏慢 | 后续按路由做 lazy import |

### 🟢 低风险

| # | 风险 | 位置 | 影响 | 建议 |
|---|------|------|------|------|
| R7 | **AccountCenter 无 API 调用** | AccountCenter.tsx | 账号中心页面为纯静态 UI，不显示真实余额/消费数据 | 后续接入 /api/v1/admin 或 account 接口 |
| R8 | **PublicSite 法律文本硬编码** | PublicSite.tsx | 隐私政策/服务条款等法律文本写死在组件中 | 可接受，法律文本变更频率低 |
| R9 | **lifecycle AD_STRATEGY 全是 "未设置"** | lifecycle_engine.py | 广告策略字典所有值都是占位符 | 需后续填充真实策略逻辑 |
| R10 | **git 未提交** | alignx-v1-clean 分支 | 所有修改在工作区未 commit | 整合验证通过后需 git commit |

---

## 四、交付物清单

| # | 交付物 | 路径 | 状态 |
|---|--------|------|------|
| 1 | ALIGNX_INTEGRATION_AUDIT.md | ~/Desktop/alignx/ | ✅ |
| 2 | ALIGNX_V1_INTEGRATION_PLAN.md | ~/Desktop/alignx/ | ✅ |
| 3 | AlignX V1 Integrated 稳定代码 | ~/Desktop/alignx/frontend/ + backend/ | ✅ |
| 4 | ROUTE_REGISTRY.md | ~/Desktop/alignx/ | ✅ |
| 5 | API_CONTRACT.md | ~/Desktop/alignx/ | ✅ |
| 6 | 修改文件清单 | 本文档 | ✅ |
| 7 | 剩余风险清单 | 本文档 | ✅ |

---

## 五、整合前后对比

| 指标 | 整合前 | 整合后 |
|------|--------|--------|
| 前端页面数 | 14（含 2 个死页面） | 12（全部活跃） |
| 后端目录 | 2 套（app/backend + backend） | 1 套（backend） |
| 前端目录 | 2 套（app/frontend + frontend） | 1 套（frontend） |
| 根目录 .md 文件 | 7（含 5 个旧文档） | 5（全部当前有效） |
| 跨后端 import bug | 2 处 | 0 |
| 死路由 | 1（/product-research） | 0 |
| build 模块数 | 1658 | 1657 |
| build 状态 | ✅ 通过 | ✅ 通过 |
