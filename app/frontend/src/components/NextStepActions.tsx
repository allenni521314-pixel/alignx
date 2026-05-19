import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

export interface NextStepAction {
  label: string;
  path: string;
  variant?: "default" | "outline";
}

interface NextStepActionsProps {
  actions: NextStepAction[];
}

export function NextStepActions({ actions }: NextStepActionsProps) {
  if (actions.length === 0) return null;

  return (
    <div className="mt-8 border-t border-gray-100 pt-6">
      <h4 className="text-sm font-semibold text-gray-500 mb-3 flex items-center gap-1.5">
        <ArrowRight className="w-4 h-4 text-brand-500" />
        推荐下一步
      </h4>
      <div className="flex flex-wrap gap-2">
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
