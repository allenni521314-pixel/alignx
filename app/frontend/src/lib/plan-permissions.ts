export type AccountStatus = "trial" | "free_expired" | "paid_active" | "plan_expired" | "quota_exhausted";
export type PlanId = "trial" | "lite" | "pro" | "team" | "enterprise";

export interface UsageMetric {
  key: string;
  label: string;
  used: number;
  total: number | "custom" | "unlimited";
}

export interface PlanFeatureRow {
  plan: string;
  price: string;
  audience: string;
  asinAnalysis: string;
  opportunityPool: string;
  launchCheck: string;
  listingDiagnosis: string;
  competitorDiagnosis: string;
  alignment: string;
  adValidation: string;
  reviewOptimization: string;
  history: string;
  members: string;
  stores: string;
  batchImport: string;
  reportExport: string;
  apiCustom: string;
  button: string;
  recommended?: boolean;
}

export const mockAccountPlan = {
  status: "paid_active" as AccountStatus,
  planId: "enterprise" as PlanId,
  planName: "企业版 / 超级管理员",
  expiresAt: "长期有效",
  statusLabel: "超级管理员",
  usage: [
    { key: "asin", label: "ASIN 分析用量", used: 12, total: "unlimited" },
    { key: "listing", label: "Listing 诊断用量", used: 18, total: "unlimited" },
    { key: "competitor", label: "竞品诊断用量", used: 7, total: "unlimited" },
    { key: "ad", label: "广告验证用量", used: 9, total: "unlimited" },
    { key: "ai", label: "AI 深度分析额度", used: 128, total: "unlimited" },
  ] as UsageMetric[],
};

export const planRows: PlanFeatureRow[] = [
  {
    plan: "免费试用版",
    price: "0 元",
    audience: "首次体验",
    asinAnalysis: "1 个",
    opportunityPool: "1 个",
    launchCheck: "1 次",
    listingDiagnosis: "1 次",
    competitorDiagnosis: "不支持",
    alignment: "基础",
    adValidation: "不支持",
    reviewOptimization: "不支持数据回流",
    history: "7 天",
    members: "1 人",
    stores: "1 个",
    batchImport: "不支持",
    reportExport: "不支持",
    apiCustom: "不支持",
    button: "开始试用",
  },
  {
    plan: "轻量版",
    price: "199 元/月",
    audience: "个人卖家",
    asinAnalysis: "10 个/月",
    opportunityPool: "5 个",
    launchCheck: "10 次/月",
    listingDiagnosis: "10 次/月",
    competitorDiagnosis: "5 次/月",
    alignment: "基础",
    adValidation: "1 次假设验证",
    reviewOptimization: "不支持完整数据回流",
    history: "30 天",
    members: "1 人",
    stores: "1 个",
    batchImport: "不支持",
    reportExport: "基础报告",
    apiCustom: "不支持",
    button: "开通轻量版",
  },
  {
    plan: "专业版",
    price: "699 元/月",
    audience: "运营团队",
    asinAnalysis: "50 个/月",
    opportunityPool: "20 个",
    launchCheck: "50 次/月",
    listingDiagnosis: "50 次/月",
    competitorDiagnosis: "50 次/月",
    alignment: "完整",
    adValidation: "30 次/月",
    reviewOptimization: "30 次/月，支持闭环",
    history: "180 天",
    members: "3 人",
    stores: "1 个",
    batchImport: "支持",
    reportExport: "完整报告",
    apiCustom: "不支持",
    button: "开通专业版",
    recommended: true,
  },
  {
    plan: "团队版",
    price: "1999 元/月",
    audience: "多店铺团队",
    asinAnalysis: "200 个/月",
    opportunityPool: "100 个",
    launchCheck: "200 次/月",
    listingDiagnosis: "200 次/月",
    competitorDiagnosis: "200 次/月",
    alignment: "完整",
    adValidation: "100 次/月",
    reviewOptimization: "100 次/月，支持团队回流",
    history: "不限期",
    members: "10 人",
    stores: "5 个",
    batchImport: "支持",
    reportExport: "高级报告",
    apiCustom: "可选",
    button: "开通团队版",
  },
  {
    plan: "企业版",
    price: "联系销售",
    audience: "大卖 / 品牌方 / 服务商",
    asinAnalysis: "定制",
    opportunityPool: "定制",
    launchCheck: "定制",
    listingDiagnosis: "定制",
    competitorDiagnosis: "定制",
    alignment: "完整 + 定制模型",
    adValidation: "定制",
    reviewOptimization: "定制闭环",
    history: "不限期",
    members: "定制",
    stores: "定制",
    batchImport: "支持",
    reportExport: "定制报告",
    apiCustom: "支持",
    button: "联系销售",
  },
];

export const addOnPacks = [
  { name: "ASIN 分析加量包", price: "99 元", benefit: "增加 10 个 ASIN 6维选品分析" },
  { name: "Listing 诊断加量包", price: "99 元", benefit: "增加 10 次 Listing 上新检测或本品诊断" },
  { name: "竞品诊断加量包", price: "199 元", benefit: "增加 10 次竞品诊断" },
  { name: "广告验证加量包", price: "199 元", benefit: "增加 10 次广告验证任务" },
  { name: "AI 深度分析加量包", price: "299 元", benefit: "增加 100 次 AI 深度分析额度" },
];

export const billingRows = [
  { time: "2026-05-16", plan: "免费试用版", amount: "0 元", status: "已开通" },
  { time: "待支付", plan: "专业版", amount: "699 元", status: "未支付" },
];

export function usagePercent(metric: UsageMetric) {
  if (metric.total === "custom" || metric.total === "unlimited") return 0;
  if (metric.total <= 0) return 100;
  return Math.min(100, Math.round((metric.used / metric.total) * 100));
}

export function usageWarning(metric: UsageMetric) {
  const percent = usagePercent(metric);
  if (percent >= 100) return "额度已用完";
  if (percent >= 80) return "额度即将用完";
  return "";
}
