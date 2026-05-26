import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppSidebar } from "@/components/AppSidebar";
import AdminPanel from "@/components/admin/AdminPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { toast } from "sonner";
import {
  Activity,
  CreditCard,
  Database,
  Loader2,
  Lock,
  ShieldCheck,
  User,
} from "lucide-react";

type SettingsTab = "account" | "usage" | "billing" | "admin";

const usage = [
  { label: "ASIN 分析用量", used: 1, total: 1 },
  { label: "Listing 诊断用量", used: 1, total: 1 },
  { label: "广告验证用量", used: 0, total: 0 },
  { label: "AI 调用额度", used: 42, total: 100 },
];

export default function Settings() {
  const navigate = useNavigate();
  const { user } = useRequireAuth();
  const [activeTab, setActiveTab] = useState<SettingsTab>("account");
  const [isSuperAdmin, setIsSuperAdmin] = useState(
    sessionStorage.getItem("super_admin_unlocked") === "1"
  );
  const [gatePhone, setGatePhone] = useState("");
  const [gatePassword, setGatePassword] = useState("");
  const [gateSubmitting, setGateSubmitting] = useState(false);
  const SUPER_ADMIN_PHONE = "13924666118";
  const SUPER_ADMIN_PASSWORD = "alignx2026";

  const handleGateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setGateSubmitting(true);
    setTimeout(() => {
      if (gatePhone.trim() === SUPER_ADMIN_PHONE && gatePassword === SUPER_ADMIN_PASSWORD) {
        sessionStorage.setItem("super_admin_unlocked", "1");
        setIsSuperAdmin(true);
        toast.success("超级管理员验证通过");
      } else {
        toast.error("账号或密码错误");
      }
      setGateSubmitting(false);
    }, 300);
  };

  const tabs = [
    { key: "account" as const, label: "账号中心", icon: User },
    { key: "usage" as const, label: "套餐与用量", icon: Activity },
    { key: "billing" as const, label: "账单记录", icon: CreditCard },
    { key: "admin" as const, label: "超级管理员入口", icon: ShieldCheck },
  ];

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="p-4 sm:p-8 max-w-6xl mx-auto pt-14 md:pt-8">
          <div className="mb-6">
            <h1 className="text-2xl font-bold">系统设置</h1>
            <p className="text-sm text-gray-500 mt-1">管理账号、套餐、用量、账单和超级管理员入口。</p>
          </div>

          <div className="flex gap-2 overflow-x-auto mb-6">
            {tabs.map((tab) => (
              <Button
                key={tab.key}
                variant={activeTab === tab.key ? "default" : "outline"}
                onClick={() => setActiveTab(tab.key)}
                className={activeTab === tab.key ? "bg-brand-600 hover:bg-brand-500 text-white" : "bg-white"}
              >
                <tab.icon className="w-4 h-4 mr-1.5" />
                {tab.label}
              </Button>
            ))}
          </div>

          {activeTab === "account" && (
            <div className="grid lg:grid-cols-3 gap-4">
              <Card className="bg-white border-gray-200 p-5 lg:col-span-2">
                <h2 className="text-sm font-semibold mb-4">账号中心</h2>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <Label className="text-gray-500">账号</Label>
                    <Input value={user?.email || "未登录"} disabled className="mt-1.5 bg-gray-50" />
                  </div>
                  <div>
                    <Label className="text-gray-500">用户状态</Label>
                    <Input value="试用中" disabled className="mt-1.5 bg-gray-50" />
                  </div>
                </div>
              </Card>
              <Card className="bg-white border-gray-200 p-5">
                <p className="text-xs text-gray-500">当前套餐</p>
                <h2 className="text-xl font-bold mt-1">免费试用</h2>
                <Badge className="mt-3 bg-amber-50 text-amber-700 border-amber-200">到期时间 2026-06-16</Badge>
                <Button onClick={() => navigate("/pricing")} className="w-full mt-5 bg-brand-600 hover:bg-brand-500 text-white">
                  查看套餐
                </Button>
              </Card>
            </div>
          )}

          {activeTab === "usage" && (
            <div className="space-y-4">
              <Card className="bg-white border-gray-200 p-5">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs text-gray-500">当前套餐</p>
                    <h2 className="text-xl font-bold mt-1">免费试用</h2>
                    <p className="text-sm text-gray-500 mt-1">使用状态：试用中 · 到期时间：2026-06-16</p>
                  </div>
                  <Button onClick={() => navigate("/pricing")} className="bg-brand-600 hover:bg-brand-500 text-white">
                    升级套餐
                  </Button>
                </div>
              </Card>
              <div className="grid md:grid-cols-2 gap-4">
                {usage.map((item) => {
                  const value = item.total > 0 ? Math.min(100, Math.round((item.used / item.total) * 100)) : 100;
                  return (
                    <Card key={item.label} className="bg-white border-gray-200 p-5">
                      <p className="text-sm font-medium">{item.label}</p>
                      <p className="text-xl font-bold mt-2">{item.used} / {item.total}</p>
                      <Progress value={value} className="h-2 mt-3" />
                    </Card>
                  );
                })}
              </div>
            </div>
          )}

          {activeTab === "billing" && (
            <Card className="bg-white border-gray-200 p-5">
              <h2 className="text-sm font-semibold flex items-center gap-2 mb-4">
                <Database className="w-4 h-4 text-emerald-600" />
                账单记录
              </h2>
              <div className="space-y-3">
                {[
                  { time: "2026-05-16", plan: "免费试用", amount: "0 元", status: "已开通" },
                  { time: "待支付", plan: "专业版", amount: "699 元", status: "未支付" },
                ].map((item) => (
                  <div key={`${item.time}-${item.plan}`} className="grid grid-cols-4 gap-2 text-sm rounded-lg bg-gray-50 p-3">
                    <span>{item.time}</span>
                    <span>{item.plan}</span>
                    <span>{item.amount}</span>
                    <span className="text-brand-600">{item.status}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {activeTab === "admin" && (
            isSuperAdmin ? (
              <AdminPanel />
            ) : (
              <Card className="bg-white border-gray-200 p-6 max-w-md">
                <div className="mb-5">
                  <Lock className="w-6 h-6 text-gold-600 mb-3" />
                  <h2 className="text-lg font-bold">超级管理员入口</h2>
                  <p className="text-sm text-gray-500 mt-1">请输入超级管理员账号与密码以进入。</p>
                </div>
                <form onSubmit={handleGateSubmit} className="space-y-4">
                  <Input placeholder="管理员账号" value={gatePhone} onChange={(e) => setGatePhone(e.target.value)} />
                  <Input type="password" placeholder="管理员密码" value={gatePassword} onChange={(e) => setGatePassword(e.target.value)} />
                  <Button disabled={gateSubmitting} className="w-full bg-gold-600 hover:bg-gold-500 text-white">
                    {gateSubmitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ShieldCheck className="w-4 h-4 mr-2" />}
                    进入管理后台
                  </Button>
                </form>
              </Card>
            )
          )}
        </div>
      </main>
    </div>
  );
}
