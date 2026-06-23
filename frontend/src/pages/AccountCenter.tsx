import { User, Store, CreditCard, Settings, LogOut } from "lucide-react";

export default function AccountCenter() {
  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">账号中心</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          管理账户、店铺和用量
        </p>
      </div>

      <div className="space-y-3">
        <div className="apple-card p-5 flex items-center gap-4 hover:bg-[#f5f5f7] cursor-pointer transition-colors">
          <div className="w-10 h-10 rounded-full bg-[#f5f5f7] flex items-center justify-center">
            <User size={20} className="text-[#86868b]" />
          </div>
          <div className="flex-1">
            <p className="text-[15px] font-medium">账户信息</p>
            <p className="text-[13px] text-[#86868b]">卖家账户</p>
          </div>
        </div>

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

        <div className="apple-card p-5 flex items-center gap-4 hover:bg-[#fff5f5] cursor-pointer transition-colors">
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
