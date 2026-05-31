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
    <div className="mb-4 rounded-lg border border-gray-200 bg-white/85 px-3 py-2.5 shadow-sm">
      <div className="flex flex-col gap-2 xl:flex-row xl:items-center">
        <div className="flex min-w-0 flex-1 items-start gap-2">
          <span className={`mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md border ${toneClass}`}>
            <Info className="h-3.5 w-3.5" />
          </span>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold leading-4 text-gray-500">运营目标</p>
            <p className="text-sm font-semibold leading-5 text-gray-900">{objective}</p>
          </div>
        </div>

        <div className="grid min-w-0 grid-cols-1 gap-1.5 md:grid-cols-2 xl:w-[58%] xl:grid-cols-4">
          {flowItems.map((item) => (
            <div
              key={item.label}
              className="flex min-w-0 items-start gap-1.5 rounded-md border border-gray-100 bg-gray-50/70 px-2 py-1.5"
            >
              <item.icon className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-gray-400" />
              <div className="min-w-0">
                <p className="text-[10px] font-semibold leading-3 text-gray-400">{item.label}</p>
                <p className="mt-0.5 text-[11px] leading-4 text-gray-600">{item.text}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
