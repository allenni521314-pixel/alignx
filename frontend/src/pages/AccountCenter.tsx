import { User, Store, CreditCard } from "lucide-react";

export default function AccountCenter() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">账号中心</h1>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-2 text-gray-500 mb-2">
            <User size={16} />
            <span className="text-sm">账户信息</span>
          </div>
          <p className="font-medium">卖家账户</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-2 text-gray-500 mb-2">
            <Store size={16} />
            <span className="text-sm">店铺管理</span>
          </div>
          <p className="font-medium">—</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-2 text-gray-500 mb-2">
            <CreditCard size={16} />
            <span className="text-sm">用量</span>
          </div>
          <p className="font-medium">Free Plan</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
        账号中心详情 — Phase 3 实现
      </div>
    </div>
  );
}
