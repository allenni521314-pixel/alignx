// lib/label-maps.ts
// 所有后端字段名 → 前端展示文案的统一映射
// 修改展示文案只改这一个文件，不动业务逻辑

// ─── 漏斗阶段 ───────────────────────────────────────────
export const FUNNEL_STAGE_LABELS: Record<string, string> = {
  demand_trigger:     "需求触发",
  search_intent:      "搜索意图",
  search_match:       "搜索匹配",
  click_decision:     "点击承接",
  first_screen:       "首屏确认",
  selling_point:      "卖点理解",
  trust_proof:        "信任证明",
  doubt_removal:      "疑虑消除",
};

// ─── 风险等级 ────────────────────────────────────────────
export const RISK_LEVEL_LABELS: Record<string, string> = {
  high:     "高风险",
  medium:   "中风险",
  low:      "低风险",
  none:     "无风险",
};

export const RISK_LEVEL_COLORS: Record<string, string> = {
  high:   "text-red-600 bg-red-50 border-red-200",
  medium: "text-amber-600 bg-amber-50 border-amber-200",
  low:    "text-emerald-600 bg-emerald-50 border-emerald-200",
  none:   "text-gray-400 bg-gray-50 border-gray-200",
};

// ─── 区位名称 ────────────────────────────────────────────
export const POSITION_LABELS: Record<string, string> = {
  title_front:        "标题前段",
  title_middle:       "标题中段",
  title_end:          "标题尾段",
  main_image:         "主图",
  secondary_image_1:  "副图1",
  secondary_image_2:  "副图2",
  secondary_image_3:  "副图3",
  secondary_image_4_6:"副图4-6",
  secondary_image_7:  "副图7",
  bullet_1:           "核心卖点1",
  bullet_2:           "核心卖点2",
  bullet_3_5:         "卖点3-5",
  a_plus_hero:        "A+首屏",
  a_plus_middle:      "A+中段",
  a_plus_footer:      "A+尾部",
  backend_search_terms:"后台关键词",
  qa:                 "Q&A",
  reviews:            "买家评价",
};

// ─── 覆盖状态 ────────────────────────────────────────────
export const COVERAGE_LABELS: Record<string, string> = {
  covered:      "已覆盖",
  weak:         "待加强",
  missing:      "未覆盖",
  not_priority: "暂不优先",
  forbidden:    "不建议使用",
};

export const COVERAGE_COLORS: Record<string, { dot: string; badge: string }> = {
  covered:      { dot: "bg-emerald-500", badge: "text-emerald-700 bg-emerald-50 border-emerald-200" },
  weak:         { dot: "bg-amber-400",   badge: "text-amber-700 bg-amber-50 border-amber-200" },
  missing:      { dot: "bg-red-500",     badge: "text-red-700 bg-red-50 border-red-200" },
  not_priority: { dot: "bg-gray-400",    badge: "text-gray-500 bg-gray-50 border-gray-200" },
  forbidden:    { dot: "bg-red-400",     badge: "text-red-600 bg-red-50 border-red-200" },
};

// ─── 诊断影响指标 ────────────────────────────────────────
export const IMPACT_METRIC_LABELS: Record<string, string> = {
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
  core_category:    "核心品类词",
  function:         "功能词",
  scenario:         "场景词",
  audience:         "人群词",
  pain_point:       "痛点词",
  scenario_problem: "场景问题词",
  long_tail:        "长尾词",
  state_trigger:    "高意图词",
  relationship:     "场景关联词",
  attribute:        "属性词",
};

// ─── 关键词验证状态 ──────────────────────────────────────
export const KEYWORD_VALIDATION_LABELS: Record<string, string> = {
  validated:   "已验证",
  pending:     "待验证",
  failed:      "验证未通过",
};

// ─── 诊断置信度 ──────────────────────────────────────────
export const CONFIDENCE_LABELS: Record<string, string> = {
  high:   "高置信度",
  medium: "中等置信度",
  low:    "低置信度（仅供参考）",
};

export const CONFIDENCE_COLORS: Record<string, string> = {
  high:   "text-emerald-700 bg-emerald-50 border-emerald-200",
  medium: "text-amber-700 bg-amber-50 border-amber-200",
  low:    "text-gray-500 bg-gray-50 border-gray-200",
};

// ─── 根因层级 ────────────────────────────────────────────
export const ROOT_CAUSE_LABELS: Record<string, string> = {
  image_and_title:          "首屏吸引力不足（主图/标题）",
  content_and_trust:        "详情页说服力不足",
  pricing_and_positioning:  "价格或定位偏差",
  product_quality:          "产品本身有待改善",
  ad_indexing:              "广告投放或关键词索引问题",
  no_data_text_only:        "暂无数据，以下为文案推断结果",
  balanced:                 "各维度表现均衡，建议全面优化",
  insufficient_data:        "数据不足，置信度较低",
};

// ─── 数据来源 ────────────────────────────────────────────
export const DATA_SOURCE_LABELS: Record<string, string> = {
  manual_upload:    "卖家上传报表",
  scraper:          "页面抓取",
  chrome_extension: "插件采集",
  ai_inference:     "AI 推断（无真实数据）",
  mixed:            "多来源混合",
};

// ─── 操作优先级 ──────────────────────────────────────────
export const ACTION_PRIORITY_LABELS: Record<string, string> = {
  P0: "立即处理",
  P1: "本轮优化",
  P2: "下轮跟进",
};

export const ACTION_PRIORITY_COLORS: Record<string, string> = {
  P0: "text-red-600 bg-red-50 border-red-200",
  P1: "text-amber-600 bg-amber-50 border-amber-200",
  P2: "text-teal-600 bg-teal-50 border-teal-200",
};

// ─── 通用 fallback 工具函数 ──────────────────────────────
/**
 * 从映射表取标签，取不到时返回原始 key（避免白屏）
 * 使用方式：label(FUNNEL_STAGE_LABELS, "click_decision") → "点击承接"
 */
export function label(
  map: Record<string, string>,
  key: string | null | undefined,
  fallback?: string
): string {
  if (!key) return fallback ?? "";
  return map[key] ?? fallback ?? key;
}
