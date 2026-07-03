# AlignX V1.0 Route Registry

> 生成时间：2026-07-03
> 分支：alignx-v1-clean

---

## 认证后路由（RequireAuth 包裹）

| 路径 | 组件 | 侧边栏分组 | 侧边栏标签 | 图标 |
|------|------|-----------|-----------|------|
| /market-opportunity | MarketOpportunity | 市场机会 | 产品机会 | PackageSearch |
| /competitor-analysis | CompetitorAnalysis | 市场机会 | 竞品分析 | BarChart3 |
| /prelaunch-check | PrelaunchCheck | 新品上架 | 上架准入 | ClipboardCheck |
| /yesterday-report | YesterdayReport | 运营验证 | 昨日战报 | FileText |
| /today-decisions | TodayDecisions | 运营验证 | 今日决策 | Zap |
| /conversion-diagnosis | ConversionDiagnosis | 运营验证 | 承接转化 | ArrowDownToLine |
| /traffic-strategy | TrafficStrategy | 运营验证 | 广告测试 | Route |
| /execution-records | ExecutionRecords | 运营验证 | 执行记录 | ListChecks |
| /business-validation | BusinessValidation | 运营验证 | 效果验证 | Shield |
| /account | AccountCenter | 账号中心 | 账号中心 | User |
| /admin | AdminDashboard | （仅管理员） | 管理后台 | Shield |

## 公开路由

| 路径 | 组件 | 说明 |
|------|------|------|
| / | RootRedirect | 自动跳转 /login 或 /market-opportunity |
| /login | Login | 邮箱验证码登录 |
| /en | PublicSite | 英文官网首页 |
| /en/about | PublicSite | 英文关于 |
| /en/privacy-policy | PublicSite | 英文隐私政策 |
| /en/terms | PublicSite | 英文服务条款 |
| /en/data-use-policy | PublicSite | 英文数据使用政策 |
| /en/security | PublicSite | 英文安全 |
| /en/contact | PublicSite | 英文联系 |
| /zh | PublicSite | 中文官网首页 |
| /zh/about | PublicSite | 中文关于 |
| /zh/privacy-policy | PublicSite | 中文隐私政策 |
| /zh/terms | PublicSite | 中文服务条款 |
| /zh/data-use-policy | PublicSite | 中文数据使用政策 |
| /zh/security | PublicSite | 中文安全 |
| /zh/contact | PublicSite | 中文联系 |

## 已删除路由

| 路径 | 原组件 | 删除原因 |
|------|--------|----------|
| /product-research | ProductResearch（已删除） | 孤立路由，无侧边栏入口，与 MarketOpportunity 调用相同 API |

## 侧边栏导航结构（不可修改）

```
市场机会 (group, default open)
  ├── 产品机会 → /market-opportunity
  └── 竞品分析 → /competitor-analysis
新品上架 (group, default open)
  └── 上架准入 → /prelaunch-check
运营验证 (group, default open)
  ├── 昨日战报 → /yesterday-report
  ├── 今日决策 → /today-decisions
  ├── 承接转化 → /conversion-diagnosis
  ├── 广告测试 → /traffic-strategy
  ├── 执行记录 → /execution-records
  └── 效果验证 → /business-validation
账号中心 (group, default closed, 底部)
  ├── 数据中心 → /account#data-center
  ├── 充值记录 → /account#recharge-records
  └── 消费记录 → /account#spending-records
管理后台 (仅 admin 可见) → /admin
退出登录 (按钮)
```
