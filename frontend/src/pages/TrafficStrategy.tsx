import { Route } from "lucide-react";

export default function TrafficStrategy() {
  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">流量策略</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          基于 ASIN 诊断，制定广告策略和验证任务
        </p>
      </div>
      <div className="apple-card p-16 text-center">
        <Route size={32} className="text-[#d2d2d7] mx-auto mb-3" />
        <p className="text-[15px] text-[#86868b]">即将上线</p>
        <p className="text-[13px] text-[#86868b]/60 mt-1">Phase 4 实现</p>
      </div>
    </div>
  );
}
