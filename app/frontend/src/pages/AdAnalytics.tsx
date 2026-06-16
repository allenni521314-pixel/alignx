import { useMemo } from "react";
import { useLocation } from "react-router-dom";

import { AsinModuleViewPage } from "@/components/AsinModuleViewPage";

export default function AdAnalytics() {
  const location = useLocation();
  const view = new URLSearchParams(location.search).get("view");
  const isRecords = view === "records";

  const config = useMemo(() => {
    if (isRecords) {
      return {
        title: "执行记录",
        viewType: "execution-records" as const,
        metrics: [
          { key: "overall_score", label: "综合评分" },
          { key: "confidence_score", label: "置信度" },
        ],
        columns: [
          { key: "execution_id", label: "执行ID" },
          { key: "validation_id", label: "验证ID" },
          { key: "action_type", label: "动作类型" },
          { key: "before_value", label: "修改前" },
          { key: "after_value", label: "修改后" },
          { key: "executed_by", label: "执行人" },
          { key: "executed_at", label: "执行时间" },
          { key: "note", label: "备注" },
        ],
      };
    }

    return {
      title: "效果验证",
      viewType: "effect-validation" as const,
      metrics: [
        { key: "overall_score", label: "综合评分" },
        { key: "confidence_score", label: "置信度" },
      ],
      columns: [
        { key: "validation_id", label: "验证ID" },
        { key: "validation_type", label: "验证类型" },
        { key: "problem", label: "问题" },
        { key: "hypothesis", label: "假设" },
        { key: "action_plan", label: "动作" },
        { key: "target_metric", label: "目标指标" },
        { key: "baseline_start_date", label: "基准期开始" },
        { key: "baseline_end_date", label: "基准期结束" },
        { key: "test_start_date", label: "验证期开始" },
        { key: "test_end_date", label: "验证期结束" },
        { key: "result_start_date", label: "结果期开始" },
        { key: "result_end_date", label: "结果期结束" },
        { key: "baseline_value", label: "基准值" },
        { key: "target_value", label: "目标值" },
        { key: "result_value", label: "结果值" },
        { key: "improvement_rate", label: "提升率" },
        { key: "confidence_score", label: "置信度" },
        { key: "status", label: "状态" },
      ],
    };
  }, [isRecords]);

  return (
    <AsinModuleViewPage
      title={config.title}
      viewType={config.viewType}
      metrics={config.metrics}
      columns={config.columns}
    />
  );
}
