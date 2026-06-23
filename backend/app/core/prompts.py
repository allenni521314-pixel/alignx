"""AI prompt builders for all four core modules."""

import json

# ═════════════════════════════════════════════════════
# Market Opportunity — 7-layer analysis
# ═════════════════════════════════════════════════════

MARKET_OPPORTUNITY_SYSTEM = """你是一位 Amazon 跨境电商市场分析专家。用户输入产品关键词和市场站点，你需要基于 Top 20 竞品数据，输出 7 层市场机会判断。

规则：
1. 不要编造数据。缺失的字段跳过该维度的判断，并在结论中说明。
2. 用中文回答。数值字段不可见时填 null。
3. 输出必须是合法 JSON，不要带 markdown 代码块标记。"""


def build_market_prompt(keyword: str, marketplace: str, top20_data: dict) -> str:
    """Build prompt for market opportunity analysis."""
    return f"""请分析以下关键词在 {marketplace} 的市场机会。

关键词：{keyword}

Top 20 竞品数据：
{json.dumps(top20_data, ensure_ascii=False, indent=2)}

请输出以下 JSON 结构：
{{
  "market_entry_conclusion": "一句话市场准入结论",
  "opportunity_score": 0-100 的机会评分,
  "entry_level": "强建议进入 | 谨慎进入 | 不建议进入",
  "top20_competition_strength": "低 | 中 | 高 | 极高",
  "seven_layer": {{
    "1_市场准入结论": "综合判断",
    "2_Top20竞争结构": "品牌集中度、评论壁垒、新品存活率分析",
    "3_价格带与利润空间": "主流价格带、利润空间估算、价格天花板",
    "4_需求强度与需求缺口": "搜索量趋势、购买频率、未满足需求",
    "5_竞品卖点共性": "Top20 共性卖点、差异化方向",
    "6_流量与广告风险": "CPC 估算、广告竞争程度、自然流量机会",
    "7_建议切入策略": "具体切入角度和第一步动作"
  }},
  "price_band_judgment": "价格带综合判断",
  "main_risk": "最大风险点",
  "next_action": "建议的下一步动作"
}}"""


# ═════════════════════════════════════════════════════
# Competitor Analysis — 12-dimension
# ═════════════════════════════════════════════════════

COMPETITOR_SYSTEM = """你是一位 Amazon 竞品拆解专家。基于竞品 ASIN 的 Listing 数据，输出 12 维优劣势分析。

核心目标：找到可攻击点。
规则：
1. 每一条判断必须有数据依据。
2. 可攻击点必须是竞品确实存在的弱点，不是猜测。
3. 用中文回答。输出合法 JSON。"""


def build_competitor_prompt(asin: str, listing_data: dict) -> str:
    return f"""请对以下竞品进行 12 维分析。

ASIN：{asin}

Listing 数据：
{json.dumps(listing_data, ensure_ascii=False, indent=2)}

输出 JSON：
{{
  "overall_judgment": "综合判断（2-3 句话）",
  "main_strengths": ["优势1", "优势2", "优势3"],
  "main_weaknesses": ["弱点1", "弱点2", "弱点3"],
  "attack_points": ["可攻击点1", "可攻击点2"],
  "worth_benchmarking": true/false,
  "twelve_dimension": {{
    "1_价格带位置": "在同类产品中的价格定位分析",
    "2_评论数量壁垒": "评论数是否构成新卖家进入壁垒",
    "3_评分信任度": "评分真实性、差评模式分析",
    "4_主图点击力": "主图在搜索结果中的点击力评估",
    "5_副图承接力": "副图信息结构、说服力评估",
    "6_标题关键词匹配": "标题关键词覆盖和搜索匹配度",
    "7_五点卖点表达": "五点卖点结构和差异化表达",
    "8_Aplus说服力": "A+ 内容说服力和信息完整度",
    "9_评论痛点与未满足需求": "差评中暴露的用户真实痛点",
    "10_差异化强度": "产品差异化程度评估",
    "11_自然流与广告依赖度": "自然排名 vs 广告依赖判断",
    "12_转化风险与可攻击点": "转化漏斗中的薄弱环节"
  }}
}}"""


# ═════════════════════════════════════════════════════
# Pre-launch Check — position-by-position
# ═════════════════════════════════════════════════════

PRELAUNCH_SYSTEM = """你是一位 Amazon 上架准入审核专家。检查 Listing 素材是否达到上架标准。

逐位置诊断：标题、亮点、五点（1-5）、主图、副图（1-6）、A+（1-7）。
每个位置判定：通过 | 需修改 | 缺失。
最终结论：可以上架 | 谨慎上架 | 暂不建议上架。

规则：
1. 没有 ASIN，只基于上传素材判断。
2. 不出现广告、库存、物流字段。
3. 每个需修改的位置给出具体的修改建议和修改示例。
4. 用中文回答。输出合法 JSON。"""


def build_prelaunch_prompt(materials: dict) -> str:
    return f"""请审核以下 Listing 素材是否达到上架标准。

素材内容：
{json.dumps(materials, ensure_ascii=False, indent=2)}

输出 JSON：
{{
  "admission_result": "可以上架 | 谨慎上架 | 暂不建议上架",
  "conclusion": "综合结论（2-3句）",
  "next_action": "建议的下一步动作",
  "position_diagnoses": [
    {{
      "position_id": "title",
      "position_name": "标题",
      "position_type": "text",
      "status": "通过 | 需修改 | 缺失",
      "issue": "具体问题（通过时填 null）",
      "impact": "对上架的影响",
      "recommendation": "修改建议",
      "modification_example": "修改示例"
    }},
    ... (同样结构覆盖：highlights, bullet_1~5, main_image, image_2~7, aplus_1~7)
  ]
}}

注意：未上传的位置标记为"缺失"，不要编造内容。"""


# ═════════════════════════════════════════════════════
# Conversion Diagnosis — position + ad metric mapping
# ═════════════════════════════════════════════════════

CONVERSION_SYSTEM = """你是一位 Amazon 转化率诊断专家。诊断在售 ASIN 的 Listing，找出转化瓶颈。

逐位置诊断：标题、亮点、五点（1-5）、主图、副图（1-6）、A+（1-7）、价格、评论/评分。
每个位置判定：通过 | 需修改 | 严重影响转化 | 缺失。
每个位置映射受影响的广告指标。

可选广告指标：CTR、CVR、ACOS、TACOS、CPC、加购率、订单量、退货率、自然排名、广告相关性。

规则：
1. 必须基于数据，不要猜测。
2. 找到"最大断点"——最影响转化的单一位置。
3. 给出优先改动的具体建议。
4. 输出合法 JSON。"""


def build_conversion_prompt(asin: str, listing_data: dict) -> str:
    return f"""请诊断以下在售 ASIN 的转化问题。

ASIN：{asin}

Listing 数据：
{json.dumps(listing_data, ensure_ascii=False, indent=2)}

输出 JSON：
{{
  "overall_conclusion": "综合结论（2-3句）",
  "biggest_breakpoint": "最大断点位置",
  "priority_position": "优先改动位置",
  "priority_action": "优先动作描述",
  "impacted_ad_metrics": ["CTR", "CVR"],
  "current_status": "当前 Listing 状态概述",
  "position_diagnoses": [
    {{
      "position_id": "title",
      "position_name": "标题",
      "position_type": "text",
      "status": "通过 | 需修改 | 严重影响转化 | 缺失",
      "impacted_ad_metrics": ["CTR", "CVR"],
      "issue": "具体问题",
      "evidence": "数据依据",
      "conversion_impact": "对转化的具体影响",
      "recommendation": "修改建议",
      "priority": 1-5（1最高）
    }},
    ... (覆盖所有位置)
  ]
}}"""
