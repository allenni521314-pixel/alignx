import { Check, AlertCircle, ShieldAlert } from "lucide-react";

type RiskLevel = "low" | "medium" | "high";

const LEVEL_CONFIG: Record<RiskLevel, { bg: string; iconColor: string; Icon: typeof Check }> = {
  low: { bg: "bg-[#34c759]/10", iconColor: "text-[#34c759]", Icon: Check },
  medium: { bg: "bg-[#ff9500]/10", iconColor: "text-[#ff9500]", Icon: AlertCircle },
  high: { bg: "bg-[#ff3b30]/10", iconColor: "text-[#ff3b30]", Icon: ShieldAlert },
};

/**
 * 风险等级判断结果映射：把后端返回的中文结论文案映射到统一的三档风险等级。
 * 新增结论文案时在此处扩展映射，不要在页面里散写三元判断。
 */
function resolveLevel(resultLabel: string): RiskLevel {
  if (resultLabel === "可以上架" || resultLabel === "低风险") return "low";
  if (resultLabel === "谨慎上架" || resultLabel === "中风险") return "medium";
  return "high";
}

export default function RiskBadge({
  label,
  detail,
  level,
}: {
  /** 展示的结论文案，如"可以上架" */
  label: string;
  /** 结论下方的补充说明，可选 */
  detail?: string | null;
  /** 显式指定风险等级；未提供时按 label 自动推断 */
  level?: RiskLevel;
}) {
  const resolved = level ?? resolveLevel(label);
  const { bg, iconColor, Icon } = LEVEL_CONFIG[resolved];

  return (
    <div className="flex items-center gap-3 mb-3">
      <div className={`w-10 h-10 rounded-full flex items-center justify-center ${bg}`}>
        <Icon size={20} className={iconColor} />
      </div>
      <div>
        <p className="text-[20px] font-semibold">{label}</p>
        {detail && <p className="text-[14px] text-[#86868b] mt-0.5">{detail}</p>}
      </div>
    </div>
  );
}
