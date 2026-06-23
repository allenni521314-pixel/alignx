import { CheckCircle2, TrendingUp, TrendingDown, AlertTriangle, HelpCircle } from "lucide-react";

export default function ValidationResults() {
  return (
    <div className="max-w-[720px] mx-auto py-8">
      <div className="mb-10">
        <h1 className="text-[32px] font-bold tracking-[-0.025em] mb-2">效果验证</h1>
        <p className="text-[17px] text-[#86868b] leading-relaxed">
          前后指标对比，判断有效 / 无效 / 受干扰，决定继续 / 调整 / 停止
        </p>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-8">
        <ResultCard icon={TrendingUp} label="有效" value="—" color="text-[#34c759]" bg="bg-[#34c759]/[0.06]" />
        <ResultCard icon={TrendingDown} label="无效" value="—" color="text-[#ff3b30]" bg="bg-[#ff3b30]/[0.06]" />
        <ResultCard icon={AlertTriangle} label="受干扰" value="—" color="text-[#ff9500]" bg="bg-[#ff9500]/[0.06]" />
        <ResultCard icon={HelpCircle} label="数据不足" value="—" color="text-[#86868b]" bg="bg-[#f5f5f7]" />
      </div>

      <div className="apple-card p-16 text-center">
        <CheckCircle2 size={32} className="text-[#d2d2d7] mx-auto mb-3" />
        <p className="text-[15px] text-[#86868b]">暂无验证结果</p>
        <p className="text-[13px] text-[#86868b]/60 mt-1">完成执行并录入结果后显示</p>
      </div>
    </div>
  );
}

function ResultCard({
  icon: Icon,
  label,
  value,
  color,
  bg,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  value: string;
  color: string;
  bg: string;
}) {
  return (
    <div className={`apple-card p-4 text-center ${bg}`}>
      <Icon size={20} className={`mx-auto mb-1.5 ${color}`} />
      <p className="text-[22px] font-bold">{value}</p>
      <p className="text-[11px] text-[#86868b] mt-0.5">{label}</p>
    </div>
  );
}
