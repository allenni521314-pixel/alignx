from __future__ import annotations
"""AI prompt builders for all four core modules."""

import json

# ═════════════════════════════════════════════════════
# Market Opportunity — 7-layer analysis
# ═════════════════════════════════════════════════════

MARKET_OPPORTUNITY_SYSTEM = """你是一位 Amazon 跨境电商市场分析专家。用户输入产品关键词，你需要基于 Top 20 竞品数据，先做产品分类统计，再做 7 层市场机会判断。

核心分析流程：
1. 先按产品形态/技术路线将 Top 20 归类（如除味器分为：香薰类、喷雾类、活性炭吸附类、负离子电子类、臭氧电子类、光触媒电子类等）
2. 统计每个类目的 ASIN 数量、均价区间、平均评分、平均评论数
3. 判断哪个类目竞争最弱/机会最大
4. 再做 7 层市场分析

规则：
1. 不要编造数据。缺失的字段跳过该维度的判断，并在结论中说明。
2. 用中文回答。数值字段不可见时填 null。
3. 产品分类必须基于实际 Top 20 数据，不能凭空编造类目。
4. 输出必须是合法 JSON，不要带 markdown 代码块标记。"""


def build_market_prompt(keyword: str, marketplace: str, top20_data: dict) -> str:
    """Build prompt for market opportunity analysis with product classification."""
    return f"""请分析以下关键词在 {marketplace} 的市场机会。先做产品分类统计，再做 7 层分析。

关键词：{keyword}

Top 20 竞品数据：
{json.dumps(top20_data, ensure_ascii=False, indent=2)}

请输出以下 JSON 结构：
{{
  "product_categories": [
    {{
      "category_name": "类目名称（如：光触媒电子除味器）",
      "asin_count": 该类的 ASIN 数量,
      "avg_price": "均价",
      "price_range": "价格区间",
      "avg_rating": 平均评分,
      "avg_reviews": 平均评论数,
      "competition_level": "低 | 中 | 高",
      "key_players": ["主要品牌/ASIN"],
      "typical_features": ["共性特征"],
      "common_weaknesses": ["共性弱点（从差评提取）"]
    }}
  ],
  "best_opportunity_category": "最有切入机会的类目名称及原因",
  "market_entry_conclusion": "一句话市场准入结论（结合分类结果）",
  "opportunity_score": 0-100 的机会评分,
  "entry_level": "强建议进入 | 谨慎进入 | 不建议进入",
  "top20_competition_strength": "低 | 中 | 高 | 极高",
  "seven_layer": {{
    "1_市场准入结论": "综合判断",
    "2_类目竞争结构": "各类目的品牌集中度、评论壁垒、新品存活率",
    "3_价格带与利润空间": "各类目主流价格带、利润空间估算",
    "4_需求强度与需求缺口": "搜索量趋势、买家真实需求、未满足痛点",
    "5_竞品卖点共性": "Top20 共性卖点、各类目差异化方向",
    "6_流量与广告风险": "CPC 估算、各类目广告竞争程度",
    "7_建议切入策略": "具体切入类目、产品形态建议和第一步动作"
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

买家语言转译规则（内置）：
1. 分析竞品 Listing 时，必须判断其使用的语言是"卖家技术语言"还是"买家购买语言"
2. 技术词过重 = 转化弱 → 标记为可攻击点
3. 缺乏场景描述 = 买家代入感差 → 标记为可攻击点
4. 卖点没有回答买家问题 = 点击后流失 → 标记为转化断点
5. 合规风险表达 = 高风险 → 明确标注

规则：
1. 每一条判断必须有数据依据。
2. 可攻击点必须是竞品确实存在的弱点，不是猜测。
3. 图片位置必须基于“图片识别（OCR + 场景吻合）”判断：图上文案是否有效、图片内容是否与产品吻合、场景是否错配。
4. 用中文回答。输出合法 JSON。"""


def _format_image_texts(listing_data: dict) -> str:
    image_texts = listing_data.get("ocr_image_texts", {})
    if not isinstance(image_texts, dict) or not image_texts:
        return "（无图片识别结果）"

    lines = []
    for slot, value in image_texts.items():
        if not value:
            continue
        slot_name = slot if isinstance(slot, str) and not slot.startswith("http") else "图片"
        lines.append(f"  {slot_name}: {str(value)[:800]}")
    return "\n".join(lines) if lines else "（无图片识别结果）"


def build_competitor_prompt(asin: str, listing_data: dict) -> str:
    image_text = _format_image_texts(listing_data)
    return f"""请对以下竞品进行 12 维分析。

ASIN：{asin}

Listing 数据：
{json.dumps(listing_data, ensure_ascii=False, indent=2)}

图片识别（OCR + 场景吻合）：
{image_text}

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

Amazon 图片规则（必须遵守）：
- 主图：纯白底(RGB255)，产品占85%以上，无文字/logo/水印
- 副图：根据实际上传的副图素材判断 ASIN 描述完整度，不要求固定张数
- A+内容：根据实际上传的 A+ 素材判断 ASIN 描述完整度，不要求固定张数
- 所有图上文字必须买家语言（利益），不能卖家语言（功能）
- 禁用词：Best, No.1, Guaranteed, 100%, Medical Grade

标题硬规则（必须遵守）：
- 标题必须计算字符数，包括空格和标点。
- title.length > 75 时，status 必须为"需修改"，issue_type 必须包含 title_over_75_characters。
- suggested_rewrite / recommendation 中的建议标题不得超过 75 characters including spaces。
- 标题不是关键词仓库，只保留 Brand、Core Search Term、一个主要场景或身份、1-2 个差异点。
- USB Powered、Wall Mount、Small Spaces、Bathroom、Closet、Shoe Cabinet 等场景词优先放入 Item Highlight 或五点，不强塞标题。
- 必须输出 title_keyword_tradeoff，说明 kept、moved_to_item_highlight、moved_to_bullets、omitted_from_title_reason。

Item Highlight 规则（必须遵守）：
- 最大 125 characters including spaces。
- 承接标题没放下的使用场景、材料、差异点，不重复标题完整内容。

买家语言转译规则（内置）：
1. 每个位置必须判断：语言是卖家视角还是买家视角
2. 卖家视角语言 = 修改项 → 必须标注原因和改法
3. 技术词→结果词、功能词→场景词、堆砌词→单一利益词
4. 检查合规风险：绝对化词汇、夸大效果、无依据医疗承诺。如果 materials 中包含 compliance_violations，必须基于实际检测到的违规词输出高风险警告。

逐位置诊断规则：
标题、五点（1-5）、主图、已上传副图素材、已上传 A+ 素材全部位置都要诊断。
每个位置判定：通过 | 需修改 | 缺失。
最终结论：可以上架 | 谨慎上架 | 暂不建议上架。

硬拦截规则：
- 主图缺失、主图非纯白底、主图出现文字/logo/水印/第三方品牌标识时，整体不得输出"可以上架"。
- 标题超过 75 characters 时，整体不得输出"可以上架"。
- 高风险 claim 未提供证据时，整体不得输出"可以上架"。

Claim Risk Guardrail：
- suggested_rewrite / recommendation 禁止出现：Safe for pets, Safe for cats, Safe for dogs, Safe for family, No harmful ozone, No ozone emissions, Non-toxic, Chemical-free, No harsh chemicals, Kills bacteria, Kills germs, Disinfects, Sterilizes, 100% odor removal, Completely eliminates odors, Eliminates odors, Odor-free home, Guaranteed freshness, Works while pets are present, Naturally removes odors, Medical grade, Hypoallergenic, Purifies all air, Whole home odor removal, Every corner of your home。
- 使用替代表达：Made for pet areas, No ozone design, Made without ozone, No room-clearing ozone routine, No Filters Or Refills, No Fragrance Cover-Up, Helps Reduce Everyday Pet Odors, Freshens Litter Box Areas, Best For Small Odor-Prone Spaces。

规则：
1. 没有 ASIN，只基于上传素材判断。
2. 不出现广告、库存、物流字段。
3. 每个需修改的位置给出具体的英文修改建议——即卖家可以直接粘贴到 Amazon Listing 的英文买家表达。
4. 图片位置：uploaded_images 列出了已上传的位置和文件名，missing_images 列出了未上传的位置。如果 materials 中包含 ocr_texts，必须对照“可见文案、图片内容、产品场景吻合度”判断图片是否错配。错配标注并扣分。已上传的位置 → 各维度至少给 3 分。主图未上传 → 各维度给 1 分，标注缺失。副图和 A+ 未上传位置不参与诊断。

每个位置 issue 必须具体（不少于20字），说明「该位置现在是什么」「应该是什么」「差距在哪」。不允许笼统描述如"图片质量一般"。

每个位置的 recommendation 必须包含可直接粘贴到 Amazon Listing 的英文买家语言表达，不少于30字。如果是图片位置，给图上文字建议；如果是文字位置，给替换文案。
5. 所有 recommendation 和建议必须是英文买家语言。issue 和 position_name 用中文。
6. 图片位置评分规则（分位置独立评分，不套统一维度）：

主图：
- 合规分(0-5)：纯白底？仅产品？无文字logo？
- 点击力(0-5)：买家搜索看到会不会点
- 影响指标：CTR

已上传副图素材：
- 描述完整度(0-5)：是否补足 ASIN 的核心信息
- 文案语言(0-5)：卖家技术语言=低分，买家利益语言=高分
- 场景吻合度(0-5)：图片内容是否与 ASIN 描述一致
- 影响指标：CVR, 加购率

A+模块（每个模块按内容类型评分）：
- 如果是品牌故事 → 品牌记忆度(0-5)
- 如果是对比模块 → 对比说服力(0-5)
- 如果是技术规格 → 信息清晰度(0-5)
- 如果是FAQ → 疑虑覆盖度(0-5)
- 统一检查：文案是卖家语言还是买家语言（卖家语言=低分）
- 影响指标：CVR, 浏览深度, 加购率

每个维度的 score_reason 必须包含具体改法。最终给出位置总分和该位置影响的广告指标列表。
7. 评分依据：如果 materials 中包含 market_context，必须基于 Top 20 搜索结果的真实数据做交叉验证评分。例如标题关键词覆盖率 vs 竞品标题、价格位置 vs 市场均价、卖点独特性 vs 竞品卖点共性。不可凭主观猜测打分。
8. 输出合法 JSON。"""


def build_prelaunch_prompt(materials: dict) -> str:
    return """请审核以下 Listing 素材是否达到上架标准。

素材内容：
__MATERIALS_JSON__

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
      "recommendation": "修改建议（英文）",
      "modification_example": "修改示例（英文）",
      "score_clarity": 0,
      "score_reason_clarity": "为什么给这个分（必填）",
      "score_intent": 0,
      "score_reason_intent": "为什么给这个分（必填）",
      "score_scene": 0,
      "score_reason_scene": "为什么给这个分（必填）",
      "score_trust": 0,
      "score_reason_trust": "为什么给这个分（必填）",
      "score_differentiation": 0,
      "score_reason_differentiation": "为什么给这个分（必填）",
      "score_compliance": 0,
      "score_reason_compliance": "为什么给这个分（必填）",
      "score_conversion": 0,
      "score_reason_conversion": "为什么给这个分（必填）",
      "final_score": 0.0,
      "usable_status": "可直接使用 | 可使用但建议优化 | 表达弱需重写 | 不可使用",
      "impact_metrics": ["CTR", "CVR"]
    }},
    ... (同样结构覆盖：highlights, bullet_1~5, main_image, 已上传副图素材, 已上传 A+ 素材)
  ],
  "overall_status": "ready_to_launch | cautious_launch_after_fix | fix_required_before_launch | not_recommended",
  "hard_blockers": [],
  "title_analysis": {
    "current_title": "",
    "character_count": 0,
    "max_characters": 75,
    "is_over_limit": false,
    "kept_keywords": [],
    "missing_keywords": [],
    "moved_to_item_highlight": [],
    "moved_to_bullets": [],
    "suggested_title": "",
    "suggested_title_character_count": 0,
    "title_tradeoff_reason": ""
  },
  "item_highlight_analysis": {
    "current_text": "",
    "character_count": 0,
    "max_characters": 125,
    "is_over_limit": false,
    "suggested_highlight": "",
    "suggested_highlight_character_count": 0
  },
  "a_plus_analysis": [],
  "claim_risk_analysis": {
    "risk_phrases_found": [],
    "risk_level": "low | medium | high",
    "evidence_required": false,
    "safer_alternatives": {{}}
  }
}}

注意：未上传的位置标记为"缺失"，不要编造内容。""".replace(
        "__MATERIALS_JSON__",
        json.dumps(materials, ensure_ascii=False, indent=2),
    )


# ═════════════════════════════════════════════════════
# Conversion Diagnosis — position + ad metric mapping
# ═════════════════════════════════════════════════════

CONVERSION_SYSTEM = """你是一位 Amazon 转化率诊断专家。诊断在售 ASIN 的 Listing，找出转化瓶颈。

买家语言转译规则（内置）：
1. 每个位置必须判断：语言是卖家视角还是买家视角
2. 卖家视角语言 = 转化断点 → 必须标注
3. 指出具体改法：技术词→结果词、功能词→场景词、堆砌词→单一利益词
4. 判断是否存在合规风险表达

逐位置诊断规则：

逐位置诊断：标题、亮点、五点（1-5）、主图、副图（1-6）、A+（1-7）、价格、评论/评分。
每个位置判定：通过 | 需修改 | 严重影响转化 | 缺失。
每个位置映射受影响的广告指标。

可选广告指标：CTR、CVR、ACOS、TACOS、CPC、加购率、订单量、退货率、自然排名、广告相关性。

规则：
1. 必须基于数据，不要猜测。
2. 找到"最大断点"——最影响转化的单一位置。
3. 给出优先改动的具体建议。
4. 图片位置必须基于“图片识别（OCR + 场景吻合）”判断：图上文案是否有效、图片内容是否与产品吻合、场景是否错配。
5. 输出合法 JSON。"""


def build_conversion_prompt(asin: str, listing_data: dict) -> str:
    image_text = _format_image_texts(listing_data)
    return f"""请诊断以下在售 ASIN 的转化问题。

ASIN：{asin}

Listing 数据：
{json.dumps(listing_data, ensure_ascii=False, indent=2)}

图片识别（OCR + 场景吻合）：
{image_text}

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
