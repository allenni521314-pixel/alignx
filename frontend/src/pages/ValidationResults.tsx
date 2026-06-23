import { CheckCircle2 } from "lucide-react";

export default function ValidationResults() {
  return (
    <div className="max-w-4xl">
      <div className="flex items-center gap-3 mb-6">
        <CheckCircle2 className="text-brand-600" size={24} />
        <h1 className="text-2xl font-bold">效果验证</h1>
      </div>
      <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
        效果验证 — Phase 4 实现
        <p className="text-sm mt-2">前后指标对比 · 是否有效 · 是否受干扰 · 继续/调整/停止</p>
      </div>
    </div>
  );
}
