// lib/label-maps.ts
// 所有后端字段名 → 前端展示文案的统一映射
// 修改展示文案只改这一个文件，不动业务逻辑

// ─── 漏斗阶段 ────────────────────────────────────────────
export const FUNNEL_STAGE_LABELS: Record<string, string> = {
  demand_trigger:     "需求触发",
  search_intent:      "搜索意图",
  search_match:       "搜索匹配",
  click_decision:     "点击承接",
  first_screen:       "首屏确认",
  first_screen_confirmation: "首屏确认",
  selling_point:      "卖点理解",
  value_understanding:"价值理解",
  trust_proof:        "信任证明",
  trust_building:     "信任建立",
  doubt_removal:      "疑虑消除",
  objection_handling: "疑虑消除",
};

// ─── 风险等级 ────────────────────────────────────────────
export const RISK_LEVEL_LABELS: Record<string, string> = {
  high:     "高风险",
  medium:   "中风险",
  low:      "低风险",
  none:     "无风险",
};

// ─── 区位名称 ────────────────────────────────────────────
export const POSITION_LABELS: Record<string, string> = {
  title_front:        "标题前段",
  title_middle:       "标题中段",
  title_end:          "标题尾段",
  title:              "标题",
  listing:            "Listing",
  main_image:         "主图",
  image_2:            "副图2",
  image_3:            "副图3",
  image_4_6:          "副图4-6",
  image_7:            "副图7",
  bullet_1:           "核心卖点1",
  bullet_2:           "核心卖点2",
  bullet_3_5:         "卖点3-5",
  a_plus_top:         "A+首屏",
  a_plus_middle:      "A+中段",
  a_plus_bottom:      "A+尾部",
  backend_search_terms:"后台关键词",
  qa:                 "Q&A",
  reviews:            "买家评价",
};

// ─── 覆盖状态 ────────────────────────────────────────────
export const COVERAGE_LABELS: Record<string, string> = {
  covered:          "已覆盖",
  weak:             "待加强",
  missing:          "未覆盖",
  not_priority:     "暂不优先",
  blocked_by_rule:  "规则禁止",
  wrong_position:   "位置不当",
};

// ─── 诊断影响指标 ────────────────────────────────────────
export const IMPACT_METRIC_LABELS: Record<string, string> = {
  impressions:          "曝光量",
  clicks:               "点击量",
  ctr:                  "点击率",
  cpc:                  "点击成本",
  cvr:                  "转化率",
  acos:                 "广告成本比",
  orders:               "订单量",
  sales:                "销售额",
  keyword_rank:         "关键词排名",
  add_to_cart:          "加购率",
  purchase:             "购买率",
  increase_impressions: "提升曝光量",
  increase_ctr:         "提升点击率",
  reduce_cpc:           "降低点击成本",
  increase_cvr:         "提升转化率",
  reduce_acos:          "降低广告成本",
  increase_orders:      "增加订单量",
  improve_ranking:      "提升自然排名",
};

// ─── 关键词类型 ──────────────────────────────────────────
export const KEYWORD_TYPE_LABELS: Record<string, string> = {
  state_trigger:    "高意图词",
  relationship:     "场景关联词",
  attribute:        "属性词",
};

// ─── 诊断置信度 ──────────────────────────────────────────
export const CONFIDENCE_LABELS: Record<string, string> = {
  high:   "高置信度",
  medium: "中等置信度",
  low:    "低置信度（仅供参考）",
};

// ─── 数据来源 ────────────────────────────────────────────
export const DATA_SOURCE_LABELS: Record<string, string> = {
  scraped:   "实时抓取",
  database:  "历史数据",
  manual:    "手动输入",
  missing:   "缺失",
};

// ─── 通用 fallback 工具函数 ──────────────────────────────
export function label(
  map: Record<string, string>,
  key: string | null | undefined,
  fallback?: string
): string {
  if (!key) return fallback ?? "暂无";
  return map[key] ?? fallback ?? key;
}

/** 翻译 impact_metrics 数组 */
export function labelMetrics(metrics: string[] | null | undefined): string {
  if (!metrics || metrics.length === 0) return "暂无";
  return metrics.map(m => label(IMPACT_METRIC_LABELS, m)).join(" / ");
}
