import { PackageSearch } from "lucide-react";

export default function ProductResearch() {
  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">产品调研</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          深度调研产品线、供应链和差异化空间
        </p>
      </div>
      <div className="apple-card p-16 text-center">
        <PackageSearch size={32} className="text-[#d2d2d7] mx-auto mb-3" />
        <p className="text-[15px] text-[#86868b]">即将上线</p>
        <p className="text-[13px] text-[#86868b]/60 mt-1">Phase 3 实现</p>
      </div>
    </div>
  );
}
