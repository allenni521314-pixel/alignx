import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";

import { AppSidebar } from "@/components/AppSidebar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import {
  type AsinBusinessProfile,
  type AsinModuleView,
  type AsinModuleViewType,
  getAsinModuleView,
  listAsinProfiles,
} from "@/lib/asin-business-profile-api";

const EMPTY = "暂无";
const UNSET = "未设置";

export interface AsinModuleColumn {
  key: string;
  label: string;
}

export interface AsinModuleMetric {
  key: string;
  label: string;
}

interface AsinModuleViewPageProps {
  title: string;
  viewType: AsinModuleViewType;
  metrics: AsinModuleMetric[];
  columns: AsinModuleColumn[];
}

function valueOrEmpty(value: unknown) {
  if (value === null || value === undefined || value === "") return EMPTY;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return EMPTY;
    return String(Number.isInteger(value) ? value : Number(value.toFixed(4)));
  }
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return value.length ? value.map(valueOrEmpty).join("；") : EMPTY;
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).filter(([, item]) => item !== null && item !== undefined && item !== "");
    return entries.length ? entries.map(([key, item]) => `${key}：${valueOrEmpty(item)}`).join("；") : EMPTY;
  }
  return String(value);
}

function formatDate(value: unknown) {
  const text = valueOrEmpty(value);
  if (text === EMPTY) return text;
  return text.replace("T", " ").replace(/\.\d+Z?$/, "");
}

function statusClass(status: string) {
  if (["Success", "已完成", "成功"].includes(status)) return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (["Failed", "失败"].includes(status)) return "border-red-200 bg-red-50 text-red-700";
  if (["Running", "Pending", "Inconclusive", "运行中", "待执行", "无法判断"].includes(status)) return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-gray-200 bg-gray-50 text-gray-600";
}

function StatusValue({ value }: { value: unknown }) {
  const text = valueOrEmpty(value);
  if (text === EMPTY) return <span>{EMPTY}</span>;
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${statusClass(text)}`}>{text}</span>;
}

function MetricGrid({ metrics, values }: { metrics: AsinModuleMetric[]; values: Record<string, unknown> }) {
  if (!metrics.length) return null;
  return (
    <Card className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="text-[15px] font-semibold text-gray-950">指标</h2>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <div key={metric.key} className="min-h-[76px] rounded-lg border border-gray-100 bg-gray-50 px-3 py-2.5">
            <div className="text-xs font-medium text-gray-500">{metric.label}</div>
            <div className="mt-2 break-words text-[15px] font-semibold text-gray-950">{valueOrEmpty(values[metric.key])}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function RecordsTable({ columns, records }: { columns: AsinModuleColumn[]; records: Array<Record<string, unknown>> }) {
  return (
    <Card className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="text-[15px] font-semibold text-gray-950">记录</h2>
      <div className="mt-3 overflow-x-auto">
        {records.length ? (
          <table className="w-full min-w-[920px] border-collapse text-left text-[13px]">
            <thead>
              <tr className="border-b border-gray-200 text-xs text-gray-500">
                {columns.map((column) => (
                  <th key={column.key} className="whitespace-nowrap px-3 py-2 font-semibold">
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((record, index) => (
                <tr key={`${valueOrEmpty(record.id)}-${index}`} className="border-b border-gray-100 align-top last:border-0">
                  {columns.map((column) => (
                    <td key={column.key} className="max-w-[320px] px-3 py-3 text-gray-700">
                      {column.key === "status" ? <StatusValue value={record[column.key]} /> : valueOrEmpty(record[column.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-center text-sm text-gray-500">
            {EMPTY}
          </div>
        )}
      </div>
    </Card>
  );
}

export function AsinModuleViewPage({ title, viewType, metrics, columns }: AsinModuleViewPageProps) {
  const { loading: authLoading } = useRequireAuth();
  const [profiles, setProfiles] = useState<AsinBusinessProfile[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [view, setView] = useState<AsinModuleView | null>(null);
  const [loading, setLoading] = useState(true);

  const selectedProfile = useMemo(
    () => profiles.find((profile) => `${profile.store_id}::${profile.marketplace}::${profile.asin}` === selectedKey) || profiles[0] || null,
    [profiles, selectedKey],
  );

  const loadView = useCallback(async (profile: AsinBusinessProfile | null) => {
    setLoading(true);
    try {
      const data = await getAsinModuleView({
        view_type: viewType,
        asin: profile?.asin,
        store_id: profile?.store_id,
        marketplace: profile?.marketplace,
      });
      setView(data);
    } catch {
      setView(null);
    } finally {
      setLoading(false);
    }
  }, [viewType]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const profileData = await listAsinProfiles({ limit: 100 });
      setProfiles(profileData.items);
      const nextProfile = profileData.items[0] || null;
      setSelectedKey(nextProfile ? `${nextProfile.store_id}::${nextProfile.marketplace}::${nextProfile.asin}` : "");
      await loadView(nextProfile);
    } catch {
      setProfiles([]);
      setView(null);
      setLoading(false);
    }
  }, [loadView]);

  useEffect(() => {
    if (!authLoading) void loadData();
  }, [authLoading, loadData]);

  useEffect(() => {
    if (!authLoading && selectedProfile) void loadView(selectedProfile);
  }, [authLoading, selectedProfile, loadView]);

  if (authLoading) return null;

  const summary = view?.summary || {};
  const records = view?.records || [];
  const mergedMetrics = { ...(view?.metrics || {}), ...summary };

  return (
    <div className="flex h-screen bg-[#f5f5f7] text-gray-900">
      <AppSidebar />
      <main className="flex-1 overflow-y-auto bg-[#f5f5f7]">
        <div className="w-full max-w-none px-4 py-5 pt-14 sm:px-6 md:pt-6">
          <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h1 className="text-[24px] font-semibold tracking-normal text-gray-950">{title}</h1>
            <Button variant="outline" onClick={loadData} disabled={loading} className="h-9 gap-2 px-4 text-[13px]">
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              刷新
            </Button>
          </div>

          <Card className="mb-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_180px_180px]">
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-gray-500">ASIN</span>
                <select
                  value={selectedKey}
                  onChange={(event) => setSelectedKey(event.target.value)}
                  className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm font-semibold text-gray-900 outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
                >
                  {profiles.length ? profiles.map((profile) => (
                    <option key={`${profile.store_id}::${profile.marketplace}::${profile.asin}`} value={`${profile.store_id}::${profile.marketplace}::${profile.asin}`}>
                      {profile.asin} · {profile.product_name || UNSET}
                    </option>
                  )) : <option value="">{EMPTY}</option>}
                </select>
              </label>
              <div>
                <div className="text-xs font-medium text-gray-500">站点</div>
                <div className="mt-1 flex h-10 items-center rounded-lg border border-gray-100 bg-gray-50 px-3 text-sm font-semibold text-gray-900">
                  {valueOrEmpty(selectedProfile?.marketplace)}
                </div>
              </div>
              <div>
                <div className="text-xs font-medium text-gray-500">店铺</div>
                <div className="mt-1 flex h-10 items-center rounded-lg border border-gray-100 bg-gray-50 px-3 text-sm font-semibold text-gray-900">
                  {valueOrEmpty(selectedProfile?.store_id)}
                </div>
              </div>
            </div>
          </Card>

          <div className="space-y-4">
            <Card className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
              <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.4fr_1fr_1fr_160px]">
                <div>
                  <div className="text-xs font-medium text-gray-500">判断结论</div>
                  <div className="mt-2 text-[16px] font-semibold leading-7 text-brand-800">
                    {valueOrEmpty(summary.conclusion)}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium text-gray-500">当前最大问题</div>
                  <div className="mt-2 text-sm font-semibold leading-6 text-gray-950">
                    {valueOrEmpty(summary.current_primary_problem)}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium text-gray-500">优先动作</div>
                  <div className="mt-2 text-sm font-semibold leading-6 text-gray-950">
                    {valueOrEmpty(summary.priority_actions || summary.recommended_action)}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium text-gray-500">生成时间</div>
                  <div className="mt-2 text-sm font-semibold text-gray-950">
                    {formatDate(summary.created_at)}
                  </div>
                </div>
              </div>
            </Card>

            <MetricGrid metrics={metrics} values={mergedMetrics} />
            <RecordsTable columns={columns} records={records} />
          </div>
        </div>
      </main>
    </div>
  );
}
