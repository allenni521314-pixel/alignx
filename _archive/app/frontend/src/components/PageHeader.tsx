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
  objective: _objective,
  inputSource: _inputSource,
  outputTarget: _outputTarget,
  process: _process,
  action: _action,
  feedback: _feedback,
  tone: _tone,
}: PageHeaderProps) {
  return null;
}
