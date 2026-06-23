import { ShieldCheck } from "lucide-react";

export default function BusinessValidation() {
  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">经营验证</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          对每一项经营投入进行「命题-执行-验证」闭环
        </p>
      </div>
      <div className="apple-card p-16 text-center">
        <ShieldCheck size={32} className="text-[#d2d2d7] mx-auto mb-3" />
        <p className="text-[15px] text-[#86868b]">即将上线</p>
        <p className="text-[13px] text-[#86868b]/60 mt-1">Phase 4 实现</p>
      </div>
    </div>
  );
}
