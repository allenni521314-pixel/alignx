export interface NextStepAction {
  label: string;
  path: string;
  variant?: "default" | "outline";
}

interface NextStepActionsProps {
  actions: NextStepAction[];
  currentStep?: string;
}

export function NextStepActions(_props: NextStepActionsProps) {
  return null;
}
