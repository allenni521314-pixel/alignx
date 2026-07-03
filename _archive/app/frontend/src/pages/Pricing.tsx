import { AppSidebar } from "@/components/AppSidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  addOnPacks,
  billingRows,
  mockAccountPlan,
  planRows,
  usagePercent,
  usageWarning,
} from "@/lib/plan-permissions";
import { Check, CreditCard, Database, Lock, PackagePlus, Sparkles } from "lucide-react";

const columns = [
  ["套餐名称", "plan"],
  ["价格", "price"],
  ["适合用户", "audience"],
  ["ASIN 选品分析", "asinAnalysis"],
  ["机会池容量", "opportunityPool"],
  ["Listing 上新检测", "launchCheck"],
  ["本品诊断", "listingDiagnosis"],
  ["竞品诊断", "competitorDiagnosis"],
  ["对齐度分析", "alignment"],
  ["广告假设验证", "adValidation"],
  ["数据回流复盘", "reviewOptimization"],
  ["历史记录", "history"],
  ["团队成员", "members"],
  ["店铺数量", "stores"],
  ["批量导入", "batchImport"],
  ["报告导出", "reportExport"],
  ["API / 定制能力", "apiCustom"],
] as const;

export default function Pricing() {
  return (
    <div className="flex min-h-screen bg-gray-50 text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto bg-[#f5f5f7]">
        <div className="p-4 sm:p-6 lg:p-8 w-full max-w-none pt-14 md:pt-8">
          <div className="mb-6">
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <CreditCard className="w-6 h-6 text-brand-600" />
              套餐与用量
            </h1>
            <p className="text-sm text-gray-500 mt-1">按套餐权益、月度额度和加量包控制从诊断假设到广告验证、数据回流的闭环能力。</p>
          </div>

          <Card className="bg-white border-gray-200 p-5 mb-6">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <p className="text-xs text-gray-500">当前套餐</p>
                <div className="flex items-center gap-2 mt-1">
                  <h2 className="text-xl font-bold">{mockAccountPlan.planName}</h2>
                  <Badge className="bg-amber-50 text-amber-700 border-amber-200">{mockAccountPlan.statusLabel}</Badge>
                </div>
                <p className="text-sm text-gray-500 mt-2">到期时间：{mockAccountPlan.expiresAt}</p>
              </div>
              <Button className="bg-brand-600 hover:bg-brand-500 text-white">升级套餐</Button>
            </div>
          </Card>

          <div className="grid lg:grid-cols-5 gap-4 mb-6">
            {mockAccountPlan.usage.map((item) => {
              const percent = usagePercent(item);
              const warning = usageWarning(item);
              return (
                <Card key={item.key} className="bg-white border-gray-200 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-xs text-gray-500">{item.label}</p>
                    {warning && (
                      <Badge className={percent >= 100 ? "bg-red-50 text-red-600 border-red-200" : "bg-amber-50 text-amber-700 border-amber-200"}>
                        {warning}
                      </Badge>
                    )}
                  </div>
                  <p className="text-lg font-bold mt-2">
                    {item.used} / {item.total}
                  </p>
                  <Progress value={percent} className="mt-3 h-2" />
                </Card>
              );
            })}
          </div>

          <div className="grid lg:grid-cols-5 gap-4 mb-6">
            {planRows.map((plan) => (
              <Card key={plan.plan} className={`bg-white border-gray-200 p-5 shadow-sm ${plan.recommended ? "ring-2 ring-brand-500" : ""}`}>
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-semibold">{plan.plan}</h3>
                  {plan.recommended && <Badge className="bg-brand-50 text-brand-700 border-brand-200">推荐</Badge>}
                </div>
                <p className="text-xl font-bold mt-3">{plan.price}</p>
                <p className="text-xs text-gray-500 mt-1">{plan.audience}</p>
                <div className="space-y-2 mt-4 text-sm text-gray-600">
                  {[plan.asinAnalysis, plan.launchCheck, plan.listingDiagnosis, plan.adValidation, plan.reviewOptimization].map((feature) => (
                    <div key={feature} className="flex items-start gap-2">
                      {feature.includes("不支持") ? (
                        <Lock className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                      ) : (
                        <Check className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
                      )}
                      <span>{feature}</span>
                    </div>
                  ))}
                </div>
                <Button variant={plan.recommended ? "default" : "outline"} className={`w-full mt-5 ${plan.recommended ? "bg-brand-600 hover:bg-brand-500 text-white" : ""}`}>
                  {plan.button}
                </Button>
              </Card>
            ))}
          </div>

          <Card className="bg-white border-gray-200 p-5 mb-6">
            <h2 className="text-sm font-semibold mb-4">套餐权益表</h2>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1280px] text-sm">
                <thead>
                  <tr className="border-b border-gray-100 text-gray-500">
                    {columns.map(([label]) => (
                      <th key={label} className="text-left font-medium p-3 whitespace-nowrap">{label}</th>
                    ))}
                    <th className="text-left font-medium p-3 whitespace-nowrap">操作按钮</th>
                  </tr>
                </thead>
                <tbody>
                  {planRows.map((plan) => (
                    <tr key={plan.plan} className={plan.recommended ? "bg-brand-50/50" : "border-b border-gray-50"}>
                      {columns.map(([label, key]) => (
                        <td key={`${plan.plan}-${label}`} className="p-3 whitespace-nowrap">
                          <span className={String(plan[key]).includes("不支持") ? "text-gray-400" : "text-gray-700"}>
                            {plan[key]}
                          </span>
                        </td>
                      ))}
                      <td className="p-3 whitespace-nowrap">
                        <Button size="sm" variant={plan.recommended ? "default" : "outline"} className={plan.recommended ? "bg-brand-600 hover:bg-brand-500 text-white" : ""}>
                          {plan.button}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="grid lg:grid-cols-2 gap-4">
            <Card className="bg-white border-gray-200 p-5">
              <h2 className="text-sm font-semibold flex items-center gap-2 mb-4">
                <PackagePlus className="w-4 h-4 text-brand-600" />
                加量包
              </h2>
              <div className="grid sm:grid-cols-2 gap-3">
                {addOnPacks.map((item) => (
                  <div key={item.name} className="rounded-lg border border-gray-200 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-gray-800">{item.name}</span>
                      <span className="text-sm font-bold text-gray-900">{item.price}</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">{item.benefit}</p>
                    <Button size="sm" variant="outline" className="mt-3 w-full">购买加量包</Button>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="bg-white border-gray-200 p-5">
              <h2 className="text-sm font-semibold flex items-center gap-2 mb-4">
                <Database className="w-4 h-4 text-emerald-600" />
                账单记录
              </h2>
              <div className="space-y-3">
                {billingRows.map((item) => (
                  <div key={`${item.time}-${item.plan}`} className="grid grid-cols-5 gap-2 text-sm rounded-lg bg-gray-50 p-3">
                    <span>{item.time}</span>
                    <span>{item.plan}</span>
                    <span>{item.amount}</span>
                    <span className="text-brand-600">{item.status}</span>
                    <Button size="sm" variant="outline">查看详情</Button>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <Card className="bg-brand-50 border-brand-100 p-5 mt-6">
            <div className="flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-brand-600 mt-0.5" />
              <div>
                <h2 className="font-semibold text-gray-900">权限说明</h2>
                <p className="text-sm text-gray-600 mt-1">
                  试用版用于验证单点判断价值；轻量版适合小规模跑通诊断；专业版开放诊断假设、广告验证和数据回流完整闭环；团队版提升多人多店协同；企业版提供数据资产和定制诊断服务。
                </p>
              </div>
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}
