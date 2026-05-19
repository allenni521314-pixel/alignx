import { Activity, ArrowRight, CheckCircle2, Info, PlayCircle } from "lucide-react";

interface PageHeaderProps {
  objective: string;
  inputSource: string;
  outputTarget: string;
  process?: string;
  action?: string;
  feedback?: string;
  tone?: "blue" | "teal" | "violet" | "indigo" | "amber" | "orange" | "emerald" | "cyan" | "purple" | "rose";
}

export function PageHeader({
  objective,
  inputSource,
  outputTarget,
  process = "按本页业务标准计算并生成判断结果",
  action = "进入下一步执行动作",
  feedback = "保存结果并回流到下一轮优化",
  tone = "indigo",
}: PageHeaderProps) {
  const toneClass = {
    blue: "bg-teal-50/70 border-teal-100",
    teal: "bg-teal-50/70 border-teal-100",
    violet: "bg-gold-50/70 border-gold-100",
    indigo: "bg-brand-50/70 border-brand-100",
    amber: "bg-amber-50/70 border-amber-100",
    orange: "bg-orange-50/70 border-orange-100",
    emerald: "bg-emerald-50/70 border-emerald-100",
    cyan: "bg-teal-50/70 border-teal-100",
    purple: "bg-gold-50/70 border-gold-100",
    rose: "bg-rose-50/70 border-rose-100",
  }[tone];

  const items = [
    { label: "本页目标", text: objective, icon: Info, color: "text-brand-600", iconColor: "text-brand-500" },
    { label: "输入", text: inputSource, icon: ArrowRight, color: "text-teal-600", iconColor: "text-teal-500" },
    { label: "处理", text: process, icon: Activity, color: "text-teal-600", iconColor: "text-teal-500" },
    { label: "输出", text: outputTarget, icon: CheckCircle2, color: "text-emerald-600", iconColor: "text-emerald-500" },
    { label: "动作/反馈", text: `${action}；${feedback}`, icon: PlayCircle, color: "text-amber-600", iconColor: "text-amber-500" },
  ];

  return (
    <div className={`${toneClass} border rounded-xl p-4 mb-6`}>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3 text-sm">
        {items.map((item) => (
          <div key={item.label} className="flex items-start gap-2">
            <item.icon className={`w-4 h-4 ${item.iconColor} mt-0.5 flex-shrink-0`} />
            <div>
              <span className={`${item.color} font-semibold text-xs uppercase tracking-wide`}>
                {item.label}
              </span>
              <p className="text-gray-700 mt-0.5">{item.text}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
