import { Button } from "@/components/ui/button";
import { ArrowRight, CheckCircle2 } from "lucide-react";

export interface NextStepAction {
  label: string;
  path: string;
  variant?: "default" | "outline";
}

interface NextStepActionsProps {
  actions: NextStepAction[];
  currentStep?: string;
}

const LOOP_STEPS = ["ASIN选品", "上新检测", "本品诊断", "广告验证", "验证回流", "下一轮优化"];

function inferCurrentStep(actions: NextStepAction[], explicit?: string) {
  if (explicit) return explicit;
  const text = actions.map((item) => `${item.label} ${item.path}`).join(" ");
  if (text.includes("listing-launch-check")) return "ASIN选品";
  if (text.includes("listing-diagnosis")) return "上新检测";
  if (text.includes("ad-analytics") || text.includes("ab-test")) return "本品诊断";
  if (text.includes("optimization-suggestions")) return "广告验证";
  return "";
}

export function NextStepActions({ actions, currentStep }: NextStepActionsProps) {
  if (actions.length === 0) return null;
  const activeStep = inferCurrentStep(actions, currentStep);
  const activeIndex = LOOP_STEPS.findIndex((step) => step === activeStep);

  return (
    <div className="mt-8 rounded-lg border border-brand-100 bg-brand-50/40 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold text-gray-900 flex items-center gap-1.5">
            <ArrowRight className="w-4 h-4 text-brand-500" />
            推荐下一步
          </h4>
          <p className="mt-1 text-xs text-gray-500">
            按 AlignX 决策闭环继续推进，每一步都会保存输入、判断和验证结果。
          </p>
        </div>
        {activeStep && (
          <span className="inline-flex w-fit items-center gap-1 rounded border border-brand-100 bg-white px-2 py-1 text-[11px] font-semibold text-brand-700">
            当前：{activeStep}
          </span>
        )}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {LOOP_STEPS.map((step, index) => {
          const done = activeIndex >= 0 && index < activeIndex;
          const active = activeIndex === index;
          return (
            <div key={step} className="flex items-center gap-1.5">
              <span
                className={`inline-flex h-6 items-center gap-1 rounded-full border px-2 text-[10px] font-semibold ${
                  active
                    ? "border-brand-200 bg-brand-600 text-white"
                    : done
                      ? "border-emerald-100 bg-emerald-50 text-emerald-700"
                      : "border-gray-200 bg-white text-gray-500"
                }`}
              >
                {done && <CheckCircle2 className="h-3 w-3" />}
                {step}
              </span>
              {index < LOOP_STEPS.length - 1 && <ArrowRight className="h-3 w-3 text-gray-300" />}
            </div>
          );
        })}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {actions.map((action) => (
          <Button
            asChild
            key={action.path + action.label}
            variant={action.variant || "outline"}
            size="sm"
            className={
              action.variant === "default"
                ? "bg-brand-600 hover:bg-brand-500 text-white"
                : "border-gray-200 text-gray-700 hover:bg-brand-50 hover:text-brand-700 hover:border-brand-200"
            }
          >
            <a href={action.path}>
              {action.label}
              <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </a>
          </Button>
        ))}
      </div>
    </div>
  );
}
