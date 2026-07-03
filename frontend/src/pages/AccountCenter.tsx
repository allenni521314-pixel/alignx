import { User, Store, CreditCard, Settings, LogOut, Shield, Database, ReceiptText } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { useQuery } from "@tanstack/react-query";
import { getAccountInfo, type AccountInfo } from "@/lib/api";

export default function AccountCenter() {
  const { t, language, setLanguage } = useI18n();
  const { data: account } = useQuery({
    queryKey: ["account"],
    queryFn: getAccountInfo,
    staleTime: 60_000,
  });
  const userData = JSON.parse(localStorage.getItem("alignx_user") || "{}");
  const isAdmin = userData.email === "allenni521314@gmail.com";

  const handleLogout = () => {
    localStorage.removeItem("alignx_token");
    localStorage.removeItem("alignx_user");
    window.location.href = "/login";
  };

  const planLabel = (plan: string) => {
    const map: Record<string, string> = { free: "Free Plan", pro: "Pro", enterprise: "Enterprise" };
    return map[plan] || plan;
  };

  return (
    <div className="max-w-[680px] mx-auto py-10">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">{t("account.title")}</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">{t("account.subtitle")}</p>
      </div>

      {/* User info card */}
      <div className="apple-card p-6 mb-3">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-12 h-12 rounded-full bg-[#0F2A24] flex items-center justify-center text-white text-[18px] font-bold">
            {(userData.email || "?")[0].toUpperCase()}
          </div>
          <div>
            <p className="text-[17px] font-semibold">{userData.email || t("account.notLoggedIn")}</p>
            <p className="text-[13px] text-[#86868b]">{userData.store_name || "—"}</p>
          </div>
          {isAdmin && (
            <span className="ml-auto px-2 py-1 rounded-full bg-[#ff9500]/10 text-[#ff9500] text-[12px] font-medium">{t("common.admin")}</span>
          )}
        </div>
        <div className="grid grid-cols-2 gap-2 text-[13px]">
          <div className="p-3 rounded-lg bg-[#fbfaf7]">
            <p className="text-[#86868b]">{t("account.accountType")}</p>
            <p className="font-medium">{isAdmin ? t("common.superAdmin") : t("common.seller")}</p>
          </div>
          <div className="p-3 rounded-lg bg-[#fbfaf7]">
            <p className="text-[#86868b]">{t("account.userId")}</p>
            <p className="font-medium font-mono text-[12px]">{(userData.id || "—").slice(0, 12)}...</p>
          </div>
        </div>
      </div>

      {/* Usage stats — real data from backend */}
      <div className="apple-card p-5 mb-3">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-[#fbfaf7] flex items-center justify-center">
            <Database size={20} className="text-[#86868b]" />
          </div>
          <div className="flex-1">
            <p className="text-[15px] font-medium">{t("account.planUsage")}</p>
            <p className="text-[13px] text-[#86868b]">{account ? planLabel(account.plan) : t("account.planUsage")}</p>
          </div>
          <span className="text-[13px] font-semibold text-[#0F2A24]">
            {account?.used_calls ?? 0} / {account?.total_calls ?? 0}
          </span>
        </div>
        {/* Progress bar */}
        <div className="w-full h-2 rounded-full bg-[#E3DED2] overflow-hidden">
          <div
            className="h-full rounded-full bg-[#0F2A24] transition-all duration-500"
            style={{
              width: account && account.total_calls > 0
                ? `${Math.min(100, (account.used_calls / account.total_calls) * 100)}%`
                : "0%",
            }}
          />
        </div>
        <p className="text-[12px] text-[#86868b] mt-2">AI 调用量</p>
      </div>

      {/* Balance */}
      <div className="apple-card p-5 mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-[#fbfaf7] flex items-center justify-center">
            <ReceiptText size={20} className="text-[#86868b]" />
          </div>
          <div className="flex-1">
            <p className="text-[15px] font-medium">账户余额</p>
          </div>
          <span className="text-[20px] font-bold text-[#C6A86E]">
            ${(account?.balance ?? 0).toFixed(2)}
          </span>
        </div>
      </div>

      {/* Settings */}
      <div className="space-y-3">
        <div className="apple-card p-5 flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-[#fbfaf7] flex items-center justify-center">
            <Settings size={20} className="text-[#86868b]" />
          </div>
          <div className="flex-1">
            <p className="text-[15px] font-medium">{t("language.switch")}</p>
            <p className="text-[13px] text-[#86868b]">{language === "zh" ? "中文" : "English"}</p>
          </div>
          <select
            value={language}
            onChange={(event) => setLanguage(event.target.value === "en" ? "en" : "zh")}
            className="rounded-full border border-[#d2d2d7] bg-white px-3 py-2 text-[13px]"
            aria-label={t("language.label")}
          >
            <option value="zh">中文</option>
            <option value="en">English</option>
          </select>
        </div>

        <div className="apple-card p-5 flex items-center gap-4 hover:bg-[#fbfaf7] cursor-pointer transition-colors">
          <div className="w-10 h-10 rounded-full bg-[#fbfaf7] flex items-center justify-center">
            <Store size={20} className="text-[#86868b]" />
          </div>
          <div className="flex-1">
            <p className="text-[15px] font-medium">{t("account.storeManagement")}</p>
            <p className="text-[13px] text-[#86868b]">{t("account.amazonStoreBinding")}</p>
          </div>
        </div>

        {isAdmin && (
          <a href="/admin" className="apple-card p-5 flex items-center gap-4 hover:bg-[#fbfaf7] cursor-pointer transition-colors no-underline">
            <div className="w-10 h-10 rounded-full bg-[#0F2A24]/[0.06] flex items-center justify-center">
              <Shield size={20} className="text-[#0F2A24]" />
            </div>
            <div className="flex-1">
              <p className="text-[15px] font-medium text-[#0F2A24]">{t("nav.adminDashboard")}</p>
              <p className="text-[13px] text-[#86868b]">{t("account.adminDesc")}</p>
            </div>
          </a>
        )}

        <div onClick={handleLogout} className="apple-card p-5 flex items-center gap-4 hover:bg-[#ff3b30]/[0.04] cursor-pointer transition-colors">
          <div className="w-10 h-10 rounded-full bg-[#ff3b30]/[0.06] flex items-center justify-center">
            <LogOut size={20} className="text-[#ff3b30]" />
          </div>
          <div className="flex-1">
            <p className="text-[15px] font-medium text-[#ff3b30]">{t("common.logout")}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
