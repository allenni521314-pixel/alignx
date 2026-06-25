import { User, Store, CreditCard, Settings, LogOut, Shield } from "lucide-react";

export default function AccountCenter() {
  const userData = JSON.parse(localStorage.getItem("alignx_user") || "{}");
  const isAdmin = userData.email === "allenni521314@gmail.com";

  const handleLogout = () => {
    localStorage.removeItem("alignx_token");
    localStorage.removeItem("alignx_user");
    window.location.href = "/login";
  };

  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">账号中心</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">管理账户、店铺和用量</p>
      </div>

      {/* User info card */}
      <div className="apple-card p-6 mb-3">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-12 h-12 rounded-full bg-[#0071e3] flex items-center justify-center text-white text-[18px] font-bold">
            {(userData.email || "?")[0].toUpperCase()}
          </div>
          <div>
            <p className="text-[17px] font-semibold">{userData.email || "未登录"}</p>
            <p className="text-[13px] text-[#86868b]">{userData.store_name || "—"}</p>
          </div>
          {isAdmin && (
            <span className="ml-auto px-2 py-1 rounded-full bg-[#ff9500]/10 text-[#ff9500] text-[12px] font-medium">管理员</span>
          )}
        </div>
        <div className="grid grid-cols-2 gap-2 text-[13px]">
          <div className="p-3 rounded-lg bg-[#f5f5f7]">
            <p className="text-[#86868b]">账户类型</p>
            <p className="font-medium">{isAdmin ? "超级管理员" : "卖家"}</p>
          </div>
          <div className="p-3 rounded-lg bg-[#f5f5f7]">
            <p className="text-[#86868b]">用户 ID</p>
            <p className="font-medium font-mono text-[12px]">{(userData.id || "—").slice(0, 12)}...</p>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <div className="apple-card p-5 flex items-center gap-4 hover:bg-[#f5f5f7] cursor-pointer transition-colors">
          <div className="w-10 h-10 rounded-full bg-[#f5f5f7] flex items-center justify-center">
            <Store size={20} className="text-[#86868b]" />
          </div>
          <div className="flex-1">
            <p className="text-[15px] font-medium">店铺管理</p>
            <p className="text-[13px] text-[#86868b]">Amazon 店铺绑定</p>
          </div>
        </div>

        <div className="apple-card p-5 flex items-center gap-4 hover:bg-[#f5f5f7] cursor-pointer transition-colors">
          <div className="w-10 h-10 rounded-full bg-[#f5f5f7] flex items-center justify-center">
            <CreditCard size={20} className="text-[#86868b]" />
          </div>
          <div className="flex-1">
            <p className="text-[15px] font-medium">套餐与用量</p>
            <p className="text-[13px] text-[#86868b]">Free Plan</p>
          </div>
        </div>

        <div className="apple-card p-5 flex items-center gap-4 hover:bg-[#f5f5f7] cursor-pointer transition-colors">
          <div className="w-10 h-10 rounded-full bg-[#f5f5f7] flex items-center justify-center">
            <Settings size={20} className="text-[#86868b]" />
          </div>
          <div className="flex-1">
            <p className="text-[15px] font-medium">偏好设置</p>
            <p className="text-[13px] text-[#86868b]">语言、通知、AI 配置</p>
          </div>
        </div>

        {isAdmin && (
          <a href="/admin" className="apple-card p-5 flex items-center gap-4 hover:bg-[#f5f5f7] cursor-pointer transition-colors no-underline">
            <div className="w-10 h-10 rounded-full bg-[#0071e3]/[0.06] flex items-center justify-center">
              <Shield size={20} className="text-[#0071e3]" />
            </div>
            <div className="flex-1">
              <p className="text-[15px] font-medium text-[#0071e3]">管理后台</p>
              <p className="text-[13px] text-[#86868b]">命题库 · ASIN档案 · 闭环审计</p>
            </div>
          </a>
        )}

        <div onClick={handleLogout} className="apple-card p-5 flex items-center gap-4 hover:bg-[#fff5f5] cursor-pointer transition-colors">
          <div className="w-10 h-10 rounded-full bg-[#ff3b30]/[0.06] flex items-center justify-center">
            <LogOut size={20} className="text-[#ff3b30]" />
          </div>
          <div className="flex-1">
            <p className="text-[15px] font-medium text-[#ff3b30]">退出登录</p>
          </div>
        </div>
      </div>
    </div>
  );
}
