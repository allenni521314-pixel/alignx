import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getAdminAIModels, type AdminAIModelStatus } from "@/lib/admin-api";
import { AlertTriangle, CheckCircle2, Cpu, Server } from "lucide-react";
import { toast } from "sonner";

export function AIModelStatusPanel() {
  const [aiModels, setAIModels] = useState<AdminAIModelStatus | null>(null);

  const loadAIModels = async () => {
    try {
      const data = await getAdminAIModels();
      setAIModels(data);
    } catch (e) {
      console.error(e);
      toast.error("加载AI模型配置失败");
    }
  };

  useEffect(() => {
    void loadAIModels();
  }, []);

  return (
    <Card className="p-4 mb-5">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-brand-600" />
            AI模型调用表
          </h2>
          <p className="text-xs text-gray-500 mt-1">
            只读配置面板，仅超级管理员可见。展示当前生产环境模型、token消耗、估算成本和充值入口。
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={loadAIModels}>
          刷新
        </Button>
      </div>

      {aiModels ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-6 gap-3 mb-4">
            <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p className="text-xs text-gray-500">主Provider</p>
              <p className="text-sm font-semibold text-gray-900 mt-1">{aiModels.provider}</p>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p className="text-xs text-gray-500">调用模式</p>
              <p className="text-sm font-semibold text-gray-900 mt-1">{aiModels.api_mode}</p>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p className="text-xs text-gray-500">文本服务</p>
              <p className={`text-sm font-semibold mt-1 ${aiModels.gateway_configured ? "text-emerald-700" : "text-red-700"}`}>
                {aiModels.gateway_configured ? "已配置" : "未配置"}
              </p>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p className="text-xs text-gray-500">视觉服务</p>
              <p className={`text-sm font-semibold mt-1 ${aiModels.vision_configured ? "text-emerald-700" : "text-amber-700"}`}>
                {aiModels.vision_configured ? "已配置" : "未配置"}
              </p>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p className="text-xs text-gray-500">7日调用</p>
              <p className="text-sm font-semibold text-gray-900 mt-1">{aiModels.usage_7d?.calls || 0} 次</p>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p className="text-xs text-gray-500">7日成本</p>
              <p className="text-sm font-semibold text-gold-700 mt-1">
                ¥{Number(aiModels.usage_7d?.estimated_cost_cny || 0).toFixed(4)}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 mb-4">
            {aiModels.recharge_links.map((link) => (
              <a
                key={link.provider}
                href={link.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                {link.provider} 充值/账单
              </a>
            ))}
          </div>

          <div className="overflow-x-auto rounded-lg border border-gray-100">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500">
                <tr>
                  <th className="text-left font-medium px-3 py-2">模块</th>
                  <th className="text-left font-medium px-3 py-2">变量</th>
                  <th className="text-left font-medium px-3 py-2">模型</th>
                  <th className="text-left font-medium px-3 py-2">状态/成本</th>
                  <th className="text-left font-medium px-3 py-2">用途</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {aiModels.models.map((item) => (
                  <tr key={item.env_key} className="bg-white">
                    <td className="px-3 py-2 font-medium text-gray-900 whitespace-nowrap">{item.module}</td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-500 whitespace-nowrap">{item.env_key}</td>
                    <td className="px-3 py-2">
                      <div className="font-mono text-xs text-gray-900 whitespace-nowrap">{item.model}</div>
                      <div className="text-[11px] text-gray-400 flex items-center gap-1 mt-0.5">
                        <Server className="w-3 h-3" />
                        {item.provider}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${
                          item.configured
                            ? "bg-emerald-50 text-emerald-700"
                            : item.source === "local fallback"
                              ? "bg-amber-50 text-amber-700"
                              : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {item.configured ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                        {item.configured ? "已启用" : item.source === "local fallback" ? "本地兜底" : "未启用"}
                      </span>
                      <div className="text-[11px] text-gray-400 mt-1 whitespace-nowrap">
                        入 ¥{Number(item.input_cost_per_1m_cny || 0).toFixed(2)} / 出 ¥{Number(item.output_cost_per_1m_cny || 0).toFixed(2)} 每百万token
                      </div>
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-600 min-w-[240px]">{item.purpose}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-xs text-gray-500 mt-3">
            {aiModels.legacy_alias_policy} 成本为系统按环境变量价格估算，需定期和各平台账单核对。
          </p>
        </>
      ) : (
        <div className="h-24 rounded-lg bg-gray-50 animate-pulse" />
      )}
    </Card>
  );
}
