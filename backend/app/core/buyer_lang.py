from __future__ import annotations
"""Buyer Language Translation — seller language → Amazon buyer purchase language."""

BUYER_LANG_SYSTEM = """你是 Amazon 跨境电商买家语言转译专家。你的任务是把卖家技术语言转译成美国亚马逊买家能快速理解、愿意点击、愿意购买的表达。

核心原则：
不要问"卖家想表达什么"，要问"买家为什么会买、为什么不买、看完这句话是否更敢下单"。

转译规则：
1. 禁止只翻译词，要翻译购买动机
2. 卖家讲功能，买家要结果
3. 技术必须变成买家能感知的好处
4. 不能只说"高品质"，必须说清楚为什么降低风险
5. 不能只说"适合所有人"，必须锁定场景
6. 不要堆砌形容词，要给购买理由
7. 每个卖点必须回答一个买家问题

语言分类：
- 痛点语言：指出买家正在经历的问题
- 结果语言：告诉买家使用后得到什么
- 对比语言：区分竞品
- 风险降低语言：降低买家疑虑
- 场景语言：让买家代入
- 信任语言：解释机制、材料、参数
- 行动语言：推动购买

合规约束（禁止使用）：
- 绝对化词汇：Best, No.1, Guaranteed, 100%, Completely Eliminates, Permanent, Cure, Safest
- 无证据医疗承诺：Prevents Disease, Kills All Bacteria, Medical Grade
- 夸大效果：Removes All Odors Instantly, Works Forever
- 无依据竞品攻击

输出必须是合法 JSON，包含评分、位置映射、验证建议。"""


def build_buyer_lang_prompt(input_data: dict) -> str:
    """Build prompt for buyer language translation."""
    product_info = input_data.get("product_info", {})
    seller_claims = input_data.get("seller_claims", [])
    buyer_evidence = input_data.get("buyer_evidence", {})

    claims_text = "\n".join([f"  - {c}" for c in seller_claims]) if seller_claims else "（未提供）"
    evidence_text = ""
    if buyer_evidence:
        for k, v in buyer_evidence.items():
            if isinstance(v, list):
                evidence_text += f"\n  {k}: " + "; ".join(v[:5])

    return f"""请将以下卖家产品信息转译成买家购买语言。

产品信息：
- 标题：{product_info.get('title', '未提供')}
- 价格带：{product_info.get('price_band', '未提供')}
- 目标人群：{product_info.get('target_buyer', '未提供')}
- 使用场景：{product_info.get('use_scenario', '未提供')}

卖家原始卖点：
{claims_text}

买家证据（评论/Q&A/搜索词提取）：
{evidence_text if evidence_text else '（未提供）'}

请输出以下 JSON：
{{
  "asin": "{input_data.get('asin', '')}",
  "product_category": "产品类别",
  "price_band": "价格带",
  "target_buyer": "目标买家描述",
  "buyer_top_question": "买家最核心的一个问题",
  "seller_claims": [
    {{
      "original_claim": "原始卖点",
      "claim_type": "technology|feature|material|price|scene|emotion|trust",
      "problem": "这个表达的卖家语言问题",
      "buyer_question": "买家看到这句话会问什么问题",
      "buyer_language_short": "标题/主图用短句",
      "buyer_language_bullet": "五点描述用完整句",
      "buyer_language_aplus": "A+解释用长句",
      "trust_support_needed": "需要什么证据支撑",
      "listing_position": "标题|主图|副图2-7|五点1-5|A+模块1-6",
      "metric_to_validate": "CTR|CVR|ACOS",
      "score": {{
        "clarity": 0,
        "intent_match": 0,
        "scene_fit": 0,
        "result_specificity": 0,
        "trust": 0,
        "differentiation": 0,
        "compliance_risk": 0,
        "conversion_strength": 0
      }},
      "final_score": 0.0,
      "usable_status": "可直接使用|可使用但建议优化|表达弱需重写|不可使用",
      "reason": "评分理由"
    }}
  ],
  "top_buyer_pain_points": ["买家痛点1"],
  "top_conversion_messages": ["最能推动购买的一句话"],
  "listing_position_recommendations": [
    {{"position": "位置名称", "content": "推荐文案", "goal": "CTR|CVR|信任", "priority": 1}}
  ],
  "risk_warnings": ["违规风险点"],
  "next_validation": "下一步应该验证什么指标"
}}

中文解释必须包括：
1. 卖家语言最大问题
2. 买家真正关心什么
3. 哪些语言放主图/副图/五点/A+
4. 哪些语言不能用
5. 下一步验证什么"""
