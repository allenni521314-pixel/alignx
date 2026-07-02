import { useState } from "react";
import {
  TrendingUp, TrendingDown, AlertTriangle, ChevronRight, X, ArrowRight,
  Target, Eye, MousePointer, DollarSign, ShoppingCart, Activity,
} from "lucide-react";

// ── Mock data ──
const MOCK: any = {
  date: "2026-07-01",
  marketplace: "US",
  is_mock: true,
  data_status: { ads: "synced", sales: "synced", listing_snapshot: "partial", execution_records: "synced" },
  overview_metrics: {
    impressions: { value: 12450, delta_vs_yesterday: 0.12, delta_vs_7day_avg: 0.08, risk_note: "" },
    clicks: { value: 487, delta_vs_yesterday: -0.06, delta_vs_7day_avg: -0.03, risk_note: "点击量轻微下降" },
    ctr: { value: 0.42, delta_vs_yesterday: -0.18, delta_vs_7day_avg: -0.11, risk_note: "点击判断层下降" },
    cpc: { value: 0.87, delta_vs_yesterday: 0.09, delta_vs_7day_avg: 0.05, risk_note: "" },
    ad_spend: { value: 423.69, delta_vs_yesterday: 0.02, delta_vs_7day_avg: -0.01, risk_note: "" },
    orders: { value: 18, delta_vs_yesterday: -0.22, delta_vs_7day_avg: -0.15, risk_note: "订单明显下降" },
    cvr: { value: 3.7, delta_vs_yesterday: -0.14, delta_vs_7day_avg: -0.09, risk_note: "首屏确认层风险" },
    acos: { value: 34.2, delta_vs_yesterday: 0.21, delta_vs_7day_avg: 0.13, risk_note: "ACoS 显著恶化" },
    sales: { value: 1239, delta_vs_yesterday: -0.19, delta_vs_7day_avg: -0.11, risk_note: "" },
    active_asins: 3,
    risk_asins: 2,
    running_hypotheses: 1,
  },
  key_change_summary: {
    summary: "曝光增加，但 CTR 下降 18%、CVR 下降 14%，导致订单下降 22%。",
    possible_reason: "搜索匹配正常，但点击理由不足，首屏内容未有效承接买家预期。",
    affected_funnel_layer: "点击判断层 → 首屏确认层",
    recommended_next_page: "今日决策",
  },
  funnel_risk_distribution: [
    { stage: "demand_trigger", stage_label: "需求触发", risk_level: "low", affected_asin_count: 0, affected_metrics: [], reason: "" },
    { stage: "search_intent", stage_label: "搜索意图", risk_level: "low", affected_asin_count: 0, affected_metrics: [], reason: "" },
    { stage: "search_match", stage_label: "搜索匹配", risk_level: "low", affected_asin_count: 1, affected_metrics: ["impressions"], reason: "B0XXX 曝光小幅下降" },
    { stage: "click_decision", stage_label: "点击判断", risk_level: "high", affected_asin_count: 2, affected_metrics: ["ctr", "cpc"], reason: "曝光正常但 CTR 下降，点击理由不足" },
    { stage: "first_screen_confirmation", stage_label: "首屏确认", risk_level: "high", affected_asin_count: 2, affected_metrics: ["cvr"], reason: "CTR 正常但 CVR 下降，首屏未承接买家预期" },
    { stage: "value_understanding", stage_label: "卖点理解", risk_level: "medium", affected_asin_count: 1, affected_metrics: ["cvr"], reason: "" },
    { stage: "trust_building", stage_label: "信任证明", risk_level: "low", affected_asin_count: 0, affected_metrics: [], reason: "" },
    { stage: "objection_handling", stage_label: "疑虑消除", risk_level: "low", affected_asin_count: 1, affected_metrics: ["orders"], reason: "加购正常但订单未完成" },
  ],
  asin_alerts: [
    {
      asin: "B0FDKQGRCK", sku: "PLR-USB-WHT", product_name: "USB-C 光触媒宠物除臭器 白色",
      change_type: "ctr_down", primary_bottleneck: "click_decision",
      affected_metrics: ["ctr", "cpc", "cvr"], delta_vs_yesterday: { ctr: -0.23, cpc: 0.12, cvr: -0.14 },
      delta_vs_7day_avg: { ctr: -0.15, cpc: 0.07, cvr: -0.08 },
      linked_hypothesis: "P03-001", system_judgment: "曝光正常但 CTR 大幅下降，优先检查标题前段和主图点击理由。CPC 上升说明广告竞争加剧。",
      recommended_next_page: "today_decision",
    },
    {
      asin: "B0GXV4ZXLM", sku: "PLR-USB-BLK", product_name: "USB-C 光触媒宠物除臭器 黑色",
      change_type: "cvr_down", primary_bottleneck: "first_screen_confirmation",
      affected_metrics: ["cvr", "acos", "orders"], delta_vs_yesterday: { cvr: -0.18, acos: 0.25, orders: -0.3 },
      delta_vs_7day_avg: { cvr: -0.11, acos: 0.14, orders: -0.2 },
      linked_hypothesis: "", system_judgment: "CTR 正常但 CVR 和订单同步下降，首屏内容和五点卖点未能承接买家预期。ACoS 恶化。",
      recommended_next_page: "conversion_diagnosis",
    },
  ],
};

const RISK_CLASS: Record<string, string> = {
  high: "text-[#ff3b30] bg-[#ff3b30]/8 border-[#ff3b30]/20",
  medium: "text-[#ff9500] bg-[#ff9500]/8 border-[#ff9500]/20",
  low: "text-[#34c759] bg-[#34c759]/8 border-[#34c759]/20",
};

const PAGE_ROUTES: Record<string, string> = {
  today_decision: "/today-decisions",
  ad_testing: "/advertising-strategy",
  conversion_diagnosis: "/conversion-diagnosis",
  validation_results: "/validation-results",
};

export default function YesterdayReport() {
  const [selectedAsin, setSelectedAsin] = useState<any>(null);
  const data = MOCK;

  return (
    <div className="max-w-[760px] mx-auto py-12">
      {/* Header */}
      <div className="text-center mb-10">
        <h1 className="text-[36px] font-bold tracking-[-0.025em] mb-2">昨日战报</h1>
        <p className="text-[17px] text-[#86868b]">昨日经营变化</p>
        {data.is_mock && (
          <span className="inline-block mt-2 text-[11px] px-2 py-0.5 rounded-full bg-[#ff9500]/10 text-[#ff9500] font-medium">Mock Data</span>
        )}
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2 mb-8 text-[12px]">
        <span className="text-[#86868b]">{data.date}</span>
        <span className="text-[#d2d2d7]">·</span>
        <span>{data.marketplace}</span>
        <span className="text-[#d2d2d7]">·</span>
        {Object.entries(data.data_status).map(([k, v]: any) => (
          <span key={k} className={`px-1.5 py-0.5 rounded text-[11px] ${v === "synced" ? "bg-[#34c759]/10 text-[#34c759]" : v === "partial" ? "bg-[#ff9500]/10 text-[#ff9500]" : "bg-[#86868b]/10 text-[#86868b]"}`}>
            {k === "ads" ? "广告" : k === "sales" ? "销售" : k === "listing_snapshot" ? "Listing" : "执行记录"} · {v === "synced" ? "已同步" : v === "partial" ? "部分" : "缺失"}
          </span>
        ))}
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-4 gap-3 mb-8">
        <MetricCard label="曝光" value="12,450" delta={12} delta7={8} icon={Eye} risk="" />
        <MetricCard label="点击" value="487" delta={-6} delta7={-3} icon={MousePointer} risk="轻微下降" />
        <MetricCard label="CTR" value="0.42%" delta={-18} delta7={-11} icon={TrendingDown} risk="点击判断层下降" color="text-[#ff3b30]" />
        <MetricCard label="CPC" value="$0.87" delta={9} delta7={5} icon={DollarSign} risk="" />
        <MetricCard label="广告花费" value="$424" delta={2} delta7={-1} icon={DollarSign} risk="" />
        <MetricCard label="订单" value="18" delta={-22} delta7={-15} icon={ShoppingCart} risk="明显下降" color="text-[#ff3b30]" />
        <MetricCard label="CVR" value="3.7%" delta={-14} delta7={-9} icon={TrendingDown} risk="首屏确认层风险" color="text-[#ff3b30]" />
        <MetricCard label="ACoS" value="34.2%" delta={21} delta7={13} icon={TrendingUp} risk="显著恶化" color="text-[#ff3b30]" invert />
        <MetricCard label="销售额" value="$1,239" delta={-19} delta7={-11} icon={DollarSign} risk="" />
        <MetricCard label="活跃 ASIN" value={3} delta={0} delta7={0} icon={Target} risk="" plain />
        <MetricCard label="异常 ASIN" value={2} delta={0} delta7={0} icon={AlertTriangle} risk="" plain color="text-[#ff3b30]" />
        <MetricCard label="验证中" value={1} delta={0} delta7={0} icon={Activity} risk="" plain />
      </div>

      {/* Key Change Summary */}
      <div className="apple-card p-5 mb-6">
        <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide mb-3">昨日关键变化解释</h3>
        <div className="space-y-2 text-[14px]">
          <p><span className="text-[#86868b]">变化：</span>{data.key_change_summary.summary}</p>
          <p><span className="text-[#86868b]">可能原因：</span>{data.key_change_summary.possible_reason}</p>
          <p><span className="text-[#86868b]">受影响漏斗层：</span><span className="text-[#ff9500] font-medium">{data.key_change_summary.affected_funnel_layer}</span></p>
          <p><span className="text-[#86868b]">建议处理：</span>
            <a href={PAGE_ROUTES[data.key_change_summary.recommended_next_page] || "#"} className="text-[#0071e3] underline ml-1">
              {data.key_change_summary.recommended_next_page === "today_decision" ? "今日决策" : data.key_change_summary.recommended_next_page}
            </a>
          </p>
        </div>
      </div>

      {/* ASIN Alert Table */}
      <div className="apple-card mb-8 overflow-x-auto">
        <div className="p-5 border-b border-[#d2d2d7]/20">
          <h3 className="text-[13px] font-semibold text-[#86868b] uppercase tracking-wide">ASIN 异常列表</h3>
        </div>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-[11px] text-[#86868b] border-b border-[#d2d2d7]/10">
              <th className="text-left px-4 py-2 font-medium">ASIN</th>
              <th className="text-left px-4 py-2 font-medium">变化类型</th>
              <th className="text-left px-4 py-2 font-medium">主断点</th>
              <th className="text-left px-4 py-2 font-medium">系统判断</th>
              <th className="text-left px-4 py-2 font-medium">建议入口</th>
            </tr>
          </thead>
          <tbody>
            {data.asin_alerts.map((a: any) => (
              <tr
                key={a.asin}
                className="border-b border-[#d2d2d7]/5 hover:bg-[#fbfaf7] cursor-pointer transition-colors"
                onClick={() => setSelectedAsin(a)}
              >
                <td className="px-4 py-3">
                  <p className="font-semibold">{a.asin}</p>
                  <p className="text-[11px] text-[#86868b]">{a.product_name}</p>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-[11px] px-1.5 py-0.5 rounded-full font-medium ${a.change_type === "ctr_down" ? "bg-[#ff3b30]/10 text-[#ff3b30]" : "bg-[#ff9500]/10 text-[#ff9500]"}`}>
                    {a.change_type === "ctr_down" ? "CTR ↓" : a.change_type === "cvr_down" ? "CVR ↓" : a.change_type}
                  </span>
                </td>
                <td className="px-4 py-3 text-[12px]">{a.primary_bottleneck === "click_decision" ? "点击判断" : a.primary_bottleneck === "first_screen_confirmation" ? "首屏确认" : a.primary_bottleneck}</td>
                <td className="px-4 py-3 text-[12px] text-[#86868b] max-w-[260px] truncate">{a.system_judgment}</td>
                <td className="px-4 py-3">
                  <a
                    href={PAGE_ROUTES[a.recommended_next_page] || "#"}
                    className="text-[11px] px-2 py-1 rounded-full bg-[#0F2A24]/8 text-[#0F2A24] font-medium hover:bg-[#0F2A24]/15 transition-colors"
                    onClick={e => e.stopPropagation()}
                  >
                    {a.recommended_next_page === "today_decision" ? "今日决策" : a.recommended_next_page === "conversion_diagnosis" ? "承接转化" : a.recommended_next_page} →
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Bottom CTAs */}
      <div className="flex items-center justify-center gap-3 pb-8">
        <a href="/today-decisions" className="apple-btn-primary inline-flex items-center gap-2 px-5 py-2.5 text-[14px]">生成今日决策 <ArrowRight size={14} /></a>
        <a href="/advertising-strategy" className="apple-btn-secondary inline-flex items-center gap-2 px-5 py-2.5 text-[14px]">进入广告测试</a>
        <a href="/conversion-diagnosis" className="apple-btn-secondary inline-flex items-center gap-2 px-5 py-2.5 text-[14px]">查看承接转化</a>
      </div>

      {/* ASIN Detail Drawer */}
      {selectedAsin && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/20" onClick={() => setSelectedAsin(null)} />
          <div className="relative w-[480px] bg-white h-full overflow-y-auto shadow-2xl animate-slide-in">
            <div className="sticky top-0 bg-white border-b border-[#d2d2d7]/20 p-5 flex items-center justify-between">
              <div>
                <h2 className="text-[16px] font-semibold">{selectedAsin.asin}</h2>
                <p className="text-[12px] text-[#86868b]">{selectedAsin.product_name}</p>
              </div>
              <button onClick={() => setSelectedAsin(null)} className="p-1.5 rounded-lg hover:bg-[#f5f5f7]"><X size={18} /></button>
            </div>
            <div className="p-5 space-y-5">
              {/* Metrics */}
              <div>
                <h4 className="text-[12px] font-semibold text-[#86868b] uppercase mb-2">昨日 vs 前日</h4>
                <div className="grid grid-cols-3 gap-2">
                  {Object.entries(selectedAsin.delta_vs_yesterday || {}).map(([k, v]: any) => (
                    <div key={k} className="bg-[#fbfaf7] rounded-lg p-2 text-center">
                      <p className="text-[10px] text-[#86868b] uppercase">{k}</p>
                      <p className={`text-[15px] font-bold ${v < 0 ? "text-[#ff3b30]" : "text-[#34c759]"}`}>{v > 0 ? "+" : ""}{(v * 100).toFixed(0)}%</p>
                    </div>
                  ))}
                </div>
              </div>
              {/* System judgment */}
              <div>
                <h4 className="text-[12px] font-semibold text-[#86868b] uppercase mb-2">系统判断</h4>
                <p className="text-[14px] text-[#1d1d1f]">{selectedAsin.system_judgment}</p>
              </div>
              {/* Bottleneck */}
              <div className="flex items-center gap-3">
                <span className="text-[12px] text-[#86868b]">当前主断点：</span>
                <span className="text-[13px] font-semibold text-[#ff9500]">{selectedAsin.primary_bottleneck === "click_decision" ? "点击判断层" : selectedAsin.primary_bottleneck === "first_screen_confirmation" ? "首屏确认层" : selectedAsin.primary_bottleneck}</span>
              </div>
              {/* Hypothesis */}
              {selectedAsin.linked_hypothesis && (
                <div className="flex items-center gap-2">
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-[#0071e3]/10 text-[#0071e3]">正在验证：{selectedAsin.linked_hypothesis}</span>
                </div>
              )}
              {/* Next step */}
              <a
                href={PAGE_ROUTES[selectedAsin.recommended_next_page] || "#"}
                className="apple-btn-primary inline-flex items-center gap-2 px-5 py-2.5 text-[14px] w-full justify-center"
              >
                {selectedAsin.recommended_next_page === "today_decision" ? "进入今日决策" : selectedAsin.recommended_next_page === "conversion_diagnosis" ? "查看承接转化诊断" : "进入处理"} <ChevronRight size={14} />
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, delta, delta7, icon: Icon, risk, color, invert, plain }: {
  label: string; value: string | number; delta: number; delta7: number;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  risk?: string; color?: string; invert?: boolean; plain?: boolean;
}) {
  const up = invert ? delta > 0 : delta < 0;
  const DeltaIcon = up ? TrendingUp : delta !== 0 ? TrendingDown : null;
  return (
    <div className="apple-card p-3 text-center">
      <Icon size={16} className={`mx-auto mb-1 ${color || "text-[#86868b]"}`} />
      <p className={`text-[17px] font-bold ${color || ""}`}>{value}</p>
      <p className="text-[10px] text-[#86868b]">{label}</p>
      {!plain && (
        <div className="flex items-center justify-center gap-1.5 mt-1">
          {DeltaIcon && <DeltaIcon size={10} className={up ? "text-[#34c759]" : "text-[#ff3b30]"} />}
          <span className={`text-[10px] font-medium ${up ? "text-[#34c759]" : delta !== 0 ? "text-[#ff3b30]" : "text-[#86868b]"}`}>
            {delta > 0 ? "+" : ""}{delta}%
          </span>
          <span className="text-[9px] text-[#d2d2d7]">7d {delta7 > 0 ? "+" : ""}{delta7}%</span>
        </div>
      )}
      {risk && <p className="text-[9px] text-[#ff3b30] mt-0.5">{risk}</p>}
    </div>
  );
}
