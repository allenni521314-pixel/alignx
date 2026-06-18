import { AsinModuleViewPage } from "@/components/AsinModuleViewPage";

export default function AdvertisingStrategy() {
  return (
    <AsinModuleViewPage
      title="流量策略"
      viewType="traffic-strategy"
      uploadConfig={{
        buttonLabel: "上传周度流量数据",
        options: [
          { value: "SEARCH_TERM_REPORT", label: "搜索词报表" },
          { value: "TARGETING_REPORT", label: "Target报表" },
        ],
      }}
      metrics={[
        { key: "sessions", label: "Sessions" },
        { key: "ctr", label: "CTR" },
        { key: "cvr", label: "CVR" },
        { key: "organic_sales_ratio", label: "Organic Sales Ratio" },
        { key: "ads_sales_ratio", label: "Ads Sales Ratio" },
        { key: "acos", label: "ACOS" },
        { key: "tacos", label: "TACOS" },
        { key: "keyword_count", label: "Keyword Count" },
        { key: "traffic_dependency", label: "流量依赖" },
        { key: "advertising_dependency", label: "广告依赖" },
      ]}
      columns={[
        { key: "decision_id", label: "决策ID" },
        { key: "conclusion", label: "结论" },
        { key: "reasoning_summary", label: "依据" },
        { key: "recommended_action", label: "动作" },
        { key: "confidence_score", label: "置信度" },
        { key: "created_at", label: "生成时间" },
      ]}
    />
  );
}
