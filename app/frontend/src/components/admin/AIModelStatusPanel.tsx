import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getAdminAIModels, probeAdminAIModels, type AdminAIModelProbe, type AdminAIModelStatus } from "@/lib/admin-api";
import { AlertTriangle, CheckCircle2, Cpu, Server, Zap } from "lucide-react";
import { toast } from "sonner";

function formatNumber(value: number | undefined) {
  return Number(value || 0).toLocaleString("zh-CN");
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "从未调用";
  try {
    return new Date(value).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

export function AIModelStatusPanel() {
  const [aiModels, setAIModels] = useState<AdminAIModelStatus | null>(null);
  const [probe, setProbe] = useState<AdminAIModelProbe | null>(null);
  const [probing, setProbing] = useState(false);

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

  const runProbe = async () => {
    setProbing(true);
    try {
      const data = await probeAdminAIModels();
      setProbe(data);
      if (data.ok) {
        toast.success("所有AI模型真实调用通过");
      } else {
        toast.warning("部分AI模型真实调用失败，请查看探针结果");
      }
    } catch (e) {
      console.error(e);
      toast.error("AI模型真实调用检测失败");
    } finally {
      setProbing(false);
    }
  };

  const probeByModel = new Map((probe?.probes || []).map((item) => [item.model, item]));

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
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={loadAIModels}>
            刷新
          </Button>
          <Button size="sm" onClick={runProbe} disabled={probing}>
            <Zap className="w-3.5 h-3.5 mr-1" />
            {probing ? "检测中" : "真实调用检测"}
          </Button>
        </div>
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
                  <th className="text-left font-medium px-3 py-2">模型名称</th>
                  <th className="text-left font-medium px-3 py-2">真实调用</th>
                  <th className="text-right font-medium px-3 py-2">7日次数</th>
                  <th className="text-right font-medium px-3 py-2">输入Token</th>
                  <th className="text-right font-medium px-3 py-2">输出Token</th>
                  <th className="text-right font-medium px-3 py-2">总Token</th>
                  <th className="text-right font-medium px-3 py-2">估算金额</th>
                  <th className="text-left font-medium px-3 py-2">最后调用</th>
                  <th className="text-left font-medium px-3 py-2">用途</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {aiModels.models.map((item) => {
                  const probeRow = probeByModel.get(item.model);
                  const liveStatus = probeRow
                    ? probeRow.ok
                      ? { text: "探针成功", className: "bg-emerald-50 text-emerald-700" }
                      : { text: "探针失败", className: "bg-red-50 text-red-700" }
                    : item.real_called
                      ? { text: "已调用", className: "bg-emerald-50 text-emerald-700" }
                      : item.configured
                        ? { text: "未见调用", className: "bg-amber-50 text-amber-700" }
                        : { text: "未启用", className: "bg-gray-100 text-gray-600" };
                  return (
                    <tr key={item.env_key} className="bg-white align-top">
                      <td className="px-3 py-3 font-medium text-gray-900 whitespace-nowrap">
                        <div>{item.module}</div>
                        <div className="mt-1 font-mono text-[11px] text-gray-400">{item.env_key}</div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="font-mono text-xs text-gray-900 whitespace-nowrap">{item.model}</div>
                        <div className="text-[11px] text-gray-400 flex items-center gap-1 mt-0.5">
                          <Server className="w-3 h-3" />
                          {item.provider}
                        </div>
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap">
                        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${liveStatus.className}`}>
                          {probeRow?.ok || item.real_called ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                          {liveStatus.text}
                        </span>
                        <div className="text-[11px] text-gray-400 mt-1">
                          {item.configured ? "配置已启用" : item.source === "local fallback" ? "本地兜底" : "未配置"}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-right font-semibold text-gray-900">{formatNumber(item.calls_7d)}</td>
                      <td className="px-3 py-3 text-right font-mono text-xs text-gray-700">{formatNumber(item.prompt_tokens_7d)}</td>
                      <td className="px-3 py-3 text-right font-mono text-xs text-gray-700">{formatNumber(item.completion_tokens_7d)}</td>
                      <td className="px-3 py-3 text-right font-mono text-xs text-gray-900">{formatNumber(item.total_tokens_7d)}</td>
                      <td className="px-3 py-3 text-right font-semibold text-gold-700 whitespace-nowrap">
                        ¥{Number(item.estimated_cost_cny_7d || 0).toFixed(4)}
                        <div className="text-[11px] font-normal text-gray-400 mt-1">
                          入¥{Number(item.input_cost_per_1m_cny || 0).toFixed(2)} / 出¥{Number(item.output_cost_per_1m_cny || 0).toFixed(2)}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-xs text-gray-600 whitespace-nowrap">
                        {probeRow ? `刚刚探针 ${probeRow.latency_ms}ms` : formatDateTime(item.last_called_at)}
                      </td>
                      <td className="px-3 py-3 text-xs text-gray-600 min-w-[260px]">{item.purpose}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {probe && (
            <div className="mt-4 rounded-lg border border-gray-100 bg-gray-50 p-3">
              <div className="flex items-center justify-between gap-3 mb-2">
                <p className="text-xs font-semibold text-gray-900">真实调用探针</p>
                <span className={`text-xs font-semibold ${probe.ok ? "text-emerald-700" : "text-red-700"}`}>
                  {probe.ok ? "全部通过" : "存在失败"}
                </span>
              </div>
              <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {probe.probes.map((item) => (
                  <div key={item.name} className="rounded-lg border border-white bg-white p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-xs font-semibold text-gray-900">{item.name}</p>
                        <p className="text-[11px] text-gray-400 font-mono mt-0.5">{item.model}</p>
                      </div>
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${item.ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                        {item.ok ? "成功" : "失败"}
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-500 mt-2">{item.provider} · {item.latency_ms}ms</p>
                    <p className={`text-[11px] mt-1 ${item.ok ? "text-gray-500" : "text-red-600"}`}>
                      {item.detail || item.error || "无返回详情"}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

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
