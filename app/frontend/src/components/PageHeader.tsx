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
    blue: "border-teal-100 bg-teal-50/45 text-teal-700",
    teal: "border-teal-100 bg-teal-50/45 text-teal-700",
    violet: "border-gold-100 bg-gold-50/45 text-gold-700",
    indigo: "border-brand-100 bg-brand-50/45 text-brand-700",
    amber: "border-amber-100 bg-amber-50/45 text-amber-700",
    orange: "border-orange-100 bg-orange-50/45 text-orange-700",
    emerald: "border-emerald-100 bg-emerald-50/45 text-emerald-700",
    cyan: "border-teal-100 bg-teal-50/45 text-teal-700",
    purple: "border-gold-100 bg-gold-50/45 text-gold-700",
    rose: "border-rose-100 bg-rose-50/45 text-rose-700",
  }[tone];

  const flowItems = [
    { label: "输入", text: inputSource, icon: ArrowRight },
    { label: "判断", text: process, icon: Activity },
    { label: "输出", text: outputTarget, icon: CheckCircle2 },
    { label: "动作", text: `${action}；${feedback}`, icon: PlayCircle },
  ];

  return (
    <div className="mb-5 rounded-2xl border border-gray-200/70 bg-white/75 px-4 py-3 shadow-[0_12px_36px_rgba(15,23,42,0.045)] backdrop-blur">
      <div className="flex flex-col gap-3">
        <div className="flex min-w-0 flex-1 items-start gap-2">
          <span className={`mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border ${toneClass}`}>
            <Info className="h-3.5 w-3.5" />
          </span>
          <div className="min-w-0">
            <p className="text-[11px] font-medium leading-4 text-gray-400">运营目标</p>
            <p className="text-[15px] font-semibold leading-5 text-gray-950">{objective}</p>
          </div>
        </div>

        <div className="flex min-w-0 flex-wrap gap-1.5 border-t border-gray-100 pt-2">
          {flowItems.map((item) => (
            <div
              key={item.label}
              className="flex min-w-0 items-center gap-1.5 rounded-full bg-gray-50/90 px-2.5 py-1.5"
            >
              <item.icon className="h-3.5 w-3.5 flex-shrink-0 text-gray-300" />
              <span className="text-[10px] font-medium text-gray-400">{item.label}</span>
              <span className="max-w-[260px] truncate text-[11px] text-gray-600">{item.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
