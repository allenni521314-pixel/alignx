const STEPS = [
  "找机会 → 看竞品", "做上架 → 跑诊断", "测广告 → 记执行", "看结果 → 再决策"
];

export default function ProgressBar({ step }: { step: number }) {
  const pct = Math.round(((step + 1) / STEPS.length) * 100);
  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[11px] text-[#86868b]">运营进度</span>
        <span className="text-[11px] text-[#86868b]">{STEPS[step]}</span>
      </div>
      <div className="h-[4px] bg-[#d2d2d7]/20 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-[#0071e3] via-[#34c759] to-[#0F2A24] rounded-full transition-all duration-700 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
