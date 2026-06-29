import { createContext, useContext, useMemo, useState } from "react";

export type Language = "en" | "zh";
type Dictionary = Record<string, string>;

const STORAGE_KEY = "alignx_language";

export const dictionaries: Record<Language, Dictionary> = {
  en: {
    "brand.method": "Validate before you invest",
    "language.label": "Language",
    "language.english": "English",
    "language.chinese": "Chinese",
    "language.switch": "Language: English / 中文",
    "common.na": "Not set",
    "common.none": "None",
    "common.pending": "Pending",
    "common.loading": "Loading",
    "common.submit": "Submit",
    "common.cancel": "Cancel",
    "common.save": "Save",
    "common.logout": "Log out",
    "common.admin": "Admin",
    "common.seller": "Seller",
    "common.superAdmin": "Super Admin",
    "common.networkError": "Network error",
    "common.requestFailed": "Request failed",
    "common.unauthorized": "Unauthorized",
    "compliance.sellerAuthorizedDataOnly": "Seller-authorized data only",
    "compliance.noSellerCentralPassword": "We do not collect your Seller Central password",
    "compliance.operationValidationOnly": "Data is used only for operation validation",
    "compliance.revokeAnytime": "You can revoke authorization at any time",
    "compliance.amazonDisclaimer": "AlignX is not affiliated with, endorsed by, or officially sponsored by Amazon",
    "nav.marketOpportunity": "Market Opportunity",
    "nav.productResearch": "Product Research",
    "nav.competitorAnalysis": "Competitor Analysis",
    "nav.newProductLaunch": "New Product Launch",
    "nav.prelaunchCheck": "Launch Readiness",
    "nav.conversionDiagnosis": "Listing Readiness",
    "nav.operationValidation": "Operation Validation",
    "nav.todayDecisions": "Today Decisions",
    "nav.adTesting": "Ad Testing",
    "nav.executionRecords": "Execution Records",
    "nav.businessValidation": "Result Validation",
    "nav.yesterdayReport": "Yesterday Report",
    "nav.accountCenter": "Account Center",
    "nav.adminDashboard": "Admin Dashboard",
    "login.title": "AlignX",
    "login.storeName": "Store Name",
    "login.storePlaceholder": "Enter store name or company name",
    "login.email": "Email",
    "login.emailPlaceholder": "Enter email address",
    "login.code": "Verification Code",
    "login.codePlaceholder": "6-digit code",
    "login.sending": "Sending...",
    "login.resend": "Resend",
    "login.sendCode": "Send Code",
    "login.devCode": "Development Code",
    "login.verifying": "Verifying...",
    "login.enterWorkspace": "Enter Workspace",
    "login.sendFailed": "Failed to send",
    "login.verifyFailed": "Verification failed",
    "account.title": "Account Center",
    "account.subtitle": "Manage account, store and usage",
    "account.notLoggedIn": "Not logged in",
    "account.accountType": "Account Type",
    "account.userId": "User ID",
    "account.storeManagement": "Store Management",
    "account.amazonStoreBinding": "Amazon Store Binding",
    "account.planUsage": "Plan And Usage",
    "account.preferences": "Preferences",
    "account.preferenceDesc": "Language, notifications and AI configuration",
    "account.adminDesc": "Proposition Library · ASIN Profiles · Loop Audit",
  },
  zh: {
    "brand.method": "先验证 · 再投入",
    "language.label": "语言",
    "language.english": "English",
    "language.chinese": "中文",
    "language.switch": "Language: English / 中文",
    "common.na": "未设置",
    "common.none": "暂无",
    "common.pending": "待录入",
    "common.loading": "加载中",
    "common.submit": "提交",
    "common.cancel": "取消",
    "common.save": "保存",
    "common.logout": "退出登录",
    "common.admin": "管理员",
    "common.seller": "卖家",
    "common.superAdmin": "超级管理员",
    "common.networkError": "网络错误",
    "common.requestFailed": "请求失败",
    "common.unauthorized": "未授权",
    "compliance.sellerAuthorizedDataOnly": "仅使用卖家授权数据",
    "compliance.noSellerCentralPassword": "不收集 Seller Central 登录密码",
    "compliance.operationValidationOnly": "数据仅用于经营验证",
    "compliance.revokeAnytime": "你可以随时撤销授权",
    "compliance.amazonDisclaimer": "AlignX 不是 Amazon 官方服务，也不代表 Amazon 官方背书",
    "nav.marketOpportunity": "市场机会",
    "nav.productResearch": "产品调研",
    "nav.competitorAnalysis": "竞品分析",
    "nav.newProductLaunch": "新品上架",
    "nav.prelaunchCheck": "上架准入",
    "nav.conversionDiagnosis": "承接转化",
    "nav.operationValidation": "运营验证",
    "nav.todayDecisions": "今日决策",
    "nav.adTesting": "广告测试",
    "nav.executionRecords": "执行记录",
    "nav.businessValidation": "经营验证",
    "nav.yesterdayReport": "昨日战报",
    "nav.accountCenter": "账号中心",
    "nav.adminDashboard": "管理后台",
    "login.title": "AlignX",
    "login.storeName": "店铺名称",
    "login.storePlaceholder": "输入店铺名称或公司名",
    "login.email": "邮箱",
    "login.emailPlaceholder": "输入邮箱地址",
    "login.code": "验证码",
    "login.codePlaceholder": "6位验证码",
    "login.sending": "发送中...",
    "login.resend": "重新发送",
    "login.sendCode": "发送验证码",
    "login.devCode": "开发模式 · 验证码",
    "login.verifying": "验证中...",
    "login.enterWorkspace": "进入工作台",
    "login.sendFailed": "发送失败",
    "login.verifyFailed": "验证失败",
    "account.title": "账号中心",
    "account.subtitle": "管理账户、店铺和用量",
    "account.notLoggedIn": "未登录",
    "account.accountType": "账户类型",
    "account.userId": "用户 ID",
    "account.storeManagement": "店铺管理",
    "account.amazonStoreBinding": "Amazon 店铺绑定",
    "account.planUsage": "套餐与用量",
    "account.preferences": "偏好设置",
    "account.preferenceDesc": "语言、通知、AI 配置",
    "account.adminDesc": "命题库 · ASIN档案 · 闭环审计",
  },
};

type I18nContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: string) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

export function detectLanguage(): Language {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "en" || saved === "zh") return saved;
  return "zh";
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => detectLanguage());

  const value = useMemo<I18nContextValue>(() => ({
    language,
    setLanguage: (next) => {
      localStorage.setItem(STORAGE_KEY, next);
      const rawUser = localStorage.getItem("alignx_user");
      if (rawUser) {
        try {
          const user = JSON.parse(rawUser);
          localStorage.setItem("alignx_user", JSON.stringify({ ...user, language: next }));
        } catch {
          localStorage.setItem(STORAGE_KEY, next);
        }
      }
      setLanguageState(next);
    },
    t: (key) => dictionaries[language][key] ?? dictionaries.en[key] ?? key,
  }), [language]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used within I18nProvider");
  return value;
}
