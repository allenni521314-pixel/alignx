import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppSidebar } from "@/components/AppSidebar";
import AdminPanel from "@/components/admin/AdminPanel";
import { FeedbackDialog } from "@/components/FeedbackDialog";
import { getAuthHeaders } from "@/lib/auth-headers";
import { getAPIBaseURL } from "@/lib/config";
import { finishModuleTask, removeModuleTask, upsertModuleTask } from "@/lib/module-task-store";
import { versionLabel } from "@/lib/version";
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
  Download,
  Loader2,
  Lock,
  ShieldCheck,
  Trash2,
  User,
} from "lucide-react";

type SettingsTab = "account" | "usage" | "billing" | "admin";

type UsageValue = number | "unlimited";

interface AccountStatus {
  account: {
    id: string;
    email: string;
    role: string;
    tenant_scope: string;
    scope_user_ids: string[];
  };
  plan: {
    id: string;
    name: string;
    status: string;
    expires_at: string | null;
  };
  usage: Record<string, { used: number; total: UsageValue }>;
  data_counts: Record<string, number>;
  generated_at: string;
}

function formatTotal(total: UsageValue) {
  return total === "unlimited" ? "不限" : String(total);
}

function usagePercent(used: number, total: UsageValue) {
  if (total === "unlimited") return 0;
  if (total <= 0) return used > 0 ? 100 : 0;
  return Math.min(100, Math.round((used / total) * 100));
}

export default function Settings() {
  const navigate = useNavigate();
  const { user } = useRequireAuth();
  const [activeTab, setActiveTab] = useState<SettingsTab>("account");
  const [isSuperAdminUnlocked, setIsSuperAdminUnlocked] = useState(
    sessionStorage.getItem("super_admin_unlocked") === "1"
  );
  const [gateAccount, setGateAccount] = useState("");
  const [gatePassword, setGatePassword] = useState("");
  const [gateSubmitting, setGateSubmitting] = useState(false);
  const [accountStatus, setAccountStatus] = useState<AccountStatus | null>(null);
  const [accountLoading, setAccountLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const isSuperAdmin = user?.role === "super_admin";
  const SUPER_ADMIN_ACCOUNT = "alignXallen";
  const SUPER_ADMIN_PASSWORD = "allen240247";

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const loadAccountStatus = async () => {
      setAccountLoading(true);
      try {
        const res = await fetch(`${getAPIBaseURL()}/api/v1/users/account-status`, {
          headers: getAuthHeaders(),
        });
        if (!res.ok) throw new Error("账号状态加载失败");
        const data = await res.json();
        if (!cancelled) setAccountStatus(data);
      } catch (err) {
        if (!cancelled) toast.error(err instanceof Error ? err.message : "账号状态加载失败");
      } finally {
        if (!cancelled) setAccountLoading(false);
      }
    };
    void loadAccountStatus();
    return () => {
      cancelled = true;
    };
  }, [user]);

  const usageRows = useMemo(() => {
    const usage = accountStatus?.usage || {};
    return [
      { key: "asin_analysis", label: "ASIN 分析用量", value: usage.asin_analysis },
      { key: "listing_diagnosis", label: "Listing 诊断用量", value: usage.listing_diagnosis },
      { key: "ad_validation", label: "广告验证用量", value: usage.ad_validation },
      { key: "snapshots", label: "历史快照", value: usage.snapshots },
    ].map((item) => ({
      key: item.key,
      label: item.label,
      used: item.value?.used ?? 0,
      total: item.value?.total ?? 0,
    }));
  }, [accountStatus]);

  const downloadDataExport = async () => {
    const moduleTaskId = `settings-data-export:${Date.now()}`;
    setExporting(true);
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "settings",
      label: "导出账号数据",
      status: "running",
      detail: "正在生成当前账号的数据导出文件",
      path: "/settings",
    });
    try {
      const res = await fetch(`${getAPIBaseURL()}/api/v1/users/data-export`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error("数据导出失败");
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const email = (user?.email || "alignx-user").replace(/[^a-zA-Z0-9._-]/g, "_");
      a.href = url;
      a.download = `alignx-data-export-${email}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      finishModuleTask(moduleTaskId, "completed", "账号数据导出已生成");
      toast.success("数据导出已生成");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "数据导出失败";
      finishModuleTask(moduleTaskId, "failed", msg);
      toast.error(msg);
    } finally {
      setExporting(false);
      window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
    }
  };

  const requestDataDeletion = async () => {
    if (!window.confirm("删除申请需要超级管理员复核。确认提交当前邮箱数据删除申请？")) return;
    const moduleTaskId = `settings-delete-request:${Date.now()}`;
    setDeleting(true);
    upsertModuleTask({
      id: moduleTaskId,
      moduleKey: "settings",
      label: "提交数据删除申请",
      status: "running",
      detail: "正在提交当前账号的数据删除申请",
      path: "/settings",
    });
    try {
      const res = await fetch(`${getAPIBaseURL()}/api/v1/users/data-deletion-request`, {
        method: "POST",
        headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "用户在设置页主动提交" }),
      });
      if (!res.ok) throw new Error("删除申请提交失败");
      const data = await res.json();
      finishModuleTask(moduleTaskId, "completed", data.message || "删除申请已提交");
      toast.success(data.message || "删除申请已提交");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "删除申请提交失败";
      finishModuleTask(moduleTaskId, "failed", msg);
      toast.error(msg);
    } finally {
      setDeleting(false);
      window.setTimeout(() => removeModuleTask(moduleTaskId), 1200);
    }
  };

  const handleGateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setGateSubmitting(true);
    setTimeout(() => {
      if (gateAccount.trim() === SUPER_ADMIN_ACCOUNT && gatePassword === SUPER_ADMIN_PASSWORD) {
        sessionStorage.setItem("super_admin_unlocked", "1");
        setIsSuperAdminUnlocked(true);
        toast.success("管理员后台已解锁");
      } else {
        toast.error("管理员账号或密码错误");
      }
      setGateSubmitting(false);
    }, 300);
  };

  const tabs = [
    { key: "account" as const, label: "账号中心", icon: User },
    { key: "usage" as const, label: "套餐与用量", icon: Activity },
    { key: "billing" as const, label: "账单记录", icon: CreditCard },
    ...(isSuperAdmin ? [{ key: "admin" as const, label: "管理员后台", icon: ShieldCheck }] : []),
  ];

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto bg-[#f5f5f7]">
        <div className="p-4 sm:p-8 max-w-6xl mx-auto pt-14 md:pt-8">
          <div className="mb-6">
            <h1 className="text-2xl font-bold">系统设置</h1>
            <p className="text-sm text-gray-500 mt-1">管理账号、套餐、用量和账单。当前版本：{versionLabel()}</p>
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
                    <Label className="text-gray-500">登录邮箱</Label>
                    <Input value={user?.email || "未登录"} disabled className="mt-1.5 bg-gray-50" />
                  </div>
                  <div>
                    <Label className="text-gray-500">数据隔离方式</Label>
                    <Input value="按邮箱独立隔离" disabled className="mt-1.5 bg-gray-50" />
                  </div>
                  <div>
                    <Label className="text-gray-500">账号角色</Label>
                    <Input value={accountStatus?.account.role || user?.role || "user"} disabled className="mt-1.5 bg-gray-50" />
                  </div>
                  <div>
                    <Label className="text-gray-500">历史身份合并</Label>
                    <Input value={`${accountStatus?.account.scope_user_ids.length || 1} 个同邮箱身份`} disabled className="mt-1.5 bg-gray-50" />
                  </div>
                </div>
              </Card>
              <Card className="bg-white border-gray-200 p-5">
                <p className="text-xs text-gray-500">当前套餐</p>
                <h2 className="text-xl font-bold mt-1">{accountStatus?.plan.name || "加载中"}</h2>
                <Badge className="mt-3 bg-amber-50 text-amber-700 border-amber-200">
                  {accountStatus?.plan.expires_at ? `到期时间 ${accountStatus.plan.expires_at}` : "内测账号"}
                </Badge>
                <Button onClick={() => navigate("/pricing")} className="w-full mt-5 bg-brand-600 hover:bg-brand-500 text-white">
                  查看套餐
                </Button>
                <FeedbackDialog triggerClassName="w-full mt-3 bg-white" />
              </Card>
              <Card className="bg-white border-gray-200 p-5 lg:col-span-3">
                <h2 className="text-sm font-semibold flex items-center gap-2">
                  <Database className="w-4 h-4 text-emerald-600" />
                  我的数据
                </h2>
                <p className="text-sm text-gray-500 mt-2">
                  当前邮箱的数据与其它用户隔离；同邮箱重新登录会合并读取历史身份下的测试记录。
                </p>
                <div className="grid md:grid-cols-4 gap-3 mt-4">
                  {Object.entries(accountStatus?.data_counts || {}).slice(0, 8).map(([key, value]) => (
                    <div key={key} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                      <p className="text-xs text-gray-500">{key}</p>
                      <p className="text-lg font-bold mt-1">{value}</p>
                    </div>
                  ))}
                </div>
                <div className="flex flex-wrap gap-3 mt-5">
                  <Button onClick={downloadDataExport} disabled={exporting} className="bg-brand-600 hover:bg-brand-500 text-white">
                    {exporting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                    导出我的数据
                  </Button>
                  <Button onClick={requestDataDeletion} disabled={deleting} variant="outline" className="bg-white text-red-700 border-red-200 hover:bg-red-50">
                    {deleting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Trash2 className="w-4 h-4 mr-2" />}
                    申请删除数据
                  </Button>
                </div>
              </Card>
            </div>
          )}

          {activeTab === "usage" && (
            <div className="space-y-4">
              <Card className="bg-white border-gray-200 p-5">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs text-gray-500">当前套餐</p>
                    <h2 className="text-xl font-bold mt-1">{accountStatus?.plan.name || "加载中"}</h2>
                    <p className="text-sm text-gray-500 mt-1">
                      使用状态：{accountStatus?.plan.status || (accountLoading ? "加载中" : "内测")} · 数据按邮箱隔离
                    </p>
                  </div>
                  <Button onClick={() => navigate("/pricing")} className="bg-brand-600 hover:bg-brand-500 text-white">
                    升级套餐
                  </Button>
                </div>
              </Card>
              <div className="grid md:grid-cols-2 gap-4">
                {usageRows.map((item) => {
                  const value = usagePercent(item.used, item.total);
                  return (
                    <Card key={item.label} className="bg-white border-gray-200 p-5">
                      <p className="text-sm font-medium">{item.label}</p>
                      <p className="text-xl font-bold mt-2">{item.used} / {formatTotal(item.total)}</p>
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
            isSuperAdmin && isSuperAdminUnlocked ? (
              <AdminPanel />
            ) : isSuperAdmin ? (
              <Card className="bg-white border-gray-200 p-6 max-w-md">
                <div className="mb-5">
                  <Lock className="w-6 h-6 text-gold-600 mb-3" />
                  <h2 className="text-lg font-bold">管理员后台</h2>
                  <p className="text-sm text-gray-500 mt-1">请输入超级管理员账号与密码以进入。</p>
                </div>
                <form onSubmit={handleGateSubmit} className="space-y-4">
                  <Input
                    placeholder="管理员账号"
                    value={gateAccount}
                    onChange={(e) => setGateAccount(e.target.value)}
                  />
                  <Input
                    type="password"
                    placeholder="管理员密码"
                    value={gatePassword}
                    onChange={(e) => setGatePassword(e.target.value)}
                  />
                  <Button disabled={gateSubmitting} className="w-full bg-gold-600 hover:bg-gold-500 text-white">
                    {gateSubmitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ShieldCheck className="w-4 h-4 mr-2" />}
                    进入管理后台
                  </Button>
                </form>
              </Card>
            ) : (
              <Card className="bg-white border-gray-200 p-6 max-w-md">
                <div className="mb-5">
                  <Lock className="w-6 h-6 text-amber-600 mb-3" />
                  <h2 className="text-lg font-bold">管理员后台</h2>
                  <p className="text-sm text-gray-500 mt-1">
                    当前邮箱不是超级管理员账号，不能查看其它用户的测试内容。
                  </p>
                </div>
                <Button onClick={() => {
                  toast.info("请使用超级管理员邮箱重新登录");
                  navigate("/login");
                }} className="w-full bg-brand-600 hover:bg-brand-500 text-white">
                  切换超级管理员邮箱
                </Button>
              </Card>
            )
          )}
        </div>
      </main>
    </div>
  );
}
