import { AsinModuleViewPage } from "@/components/AsinModuleViewPage";

export default function Dashboard() {
  return (
    <AsinModuleViewPage
      title="今日决策"
      viewType="today-decision"
      metrics={[
        { key: "overall_score", label: "综合评分" },
        { key: "traffic_score", label: "流量评分" },
        { key: "ctr_score", label: "CTR评分" },
        { key: "cvr_score", label: "CVR评分" },
        { key: "ads_score", label: "广告评分" },
        { key: "profit_score", label: "利润评分" },
        { key: "competition_score", label: "竞争评分" },
        { key: "confidence_score", label: "置信度" },
      ]}
      columns={[
        { key: "validation_id", label: "验证ID" },
        { key: "validation_type", label: "验证类型" },
        { key: "problem", label: "问题" },
        { key: "hypothesis", label: "假设" },
        { key: "action_plan", label: "动作" },
        { key: "target_metric", label: "目标指标" },
        { key: "baseline_value", label: "基准值" },
        { key: "target_value", label: "目标值" },
        { key: "confidence_score", label: "置信度" },
        { key: "status", label: "状态" },
      ]}
    />
  );
}
