import { AsinModuleViewPage } from "@/components/AsinModuleViewPage";

export default function YesterdayReport() {
  return (
    <AsinModuleViewPage
      title="昨日战报"
      viewType="yesterday-report"
      uploadConfig={{
        buttonLabel: "上传昨日经营数据",
        options: [
          { value: "BUSINESS_REPORT", label: "销售流量报表" },
          { value: "ADVERTISED_PRODUCT_REPORT", label: "广告商品报表" },
        ],
      }}
      metrics={[
        { key: "overall_score", label: "综合评分" },
        { key: "sessions", label: "Sessions" },
        { key: "clicks", label: "Clicks" },
        { key: "orders", label: "Orders" },
        { key: "sales", label: "Sales" },
        { key: "ctr", label: "CTR" },
        { key: "cvr", label: "CVR" },
        { key: "acos", label: "ACOS" },
        { key: "tacos", label: "TACOS" },
        { key: "ad_spend", label: "Ad Spend" },
        { key: "ad_sales", label: "Ad Sales" },
        { key: "organic_sales", label: "Organic Sales" },
        { key: "total_sales", label: "Total Sales" },
        { key: "inventory", label: "Inventory" },
        { key: "buybox_status", label: "Buy Box" },
      ]}
      columns={[
        { key: "date", label: "日期" },
        { key: "sessions", label: "Sessions" },
        { key: "clicks", label: "Clicks" },
        { key: "orders", label: "Orders" },
        { key: "sales", label: "Sales" },
        { key: "ctr", label: "CTR" },
        { key: "cvr", label: "CVR" },
        { key: "acos", label: "ACOS" },
        { key: "tacos", label: "TACOS" },
        { key: "ad_spend", label: "Ad Spend" },
        { key: "ad_sales", label: "Ad Sales" },
        { key: "organic_sales", label: "Organic Sales" },
        { key: "total_sales", label: "Total Sales" },
        { key: "inventory", label: "Inventory" },
        { key: "buybox_status", label: "Buy Box" },
      ]}
    />
  );
}
