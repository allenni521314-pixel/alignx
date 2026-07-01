"""
因果诊断服务 - 将COSmo从语义层升级到因果层

核心哲学：
- 传统COSmo：分析"说了什么关键词"
- 因果COSmo：分析"解决了什么人类状态差距，通过什么机制，有什么副作用"
- AlignX因果关键词：属性词只做基础覆盖，关系词和状态触发词用于找到低价格竞争的广告验证切口
"""

import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.human_state_body import HumanStateBody
from services.aihub import AIHubService
from schemas.aihub import GenTxtRequest, ChatMessage

logger = logging.getLogger(__name__)


def _keyword_type(keyword: str) -> str:
    kw = keyword.lower()
    state_terms = ("odor", "smell", "ammonia", "pain", "relief", "anxiety", "safe", "comfort", "leak", "tracking", "mess", "stress", "sleep", "noise", "spill", "dust")
    relation_terms = ("for ", "with ", "without ", "under ", "near ", "compatible", "replacement", "indoor", "outdoor", "apartment", "bedroom", "travel", "kids", "women", "men", "cats", "dogs", "office")
    if any(term in kw for term in state_terms):
        return "state_trigger"
    if any(term in kw for term in relation_terms):
        return "relationship"
    return "attribute"


def _clean_keyword(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    # The ad system needs Amazon US-ready keywords, not Chinese labels or translations.
    if any("\u4e00" <= ch <= "\u9fff" for ch in text):
        return ""
    replacements = {
        "odour": "odor",
        "colour": "color",
        "flavour": "flavor",
        "favourite": "favorite",
        "organiser": "organizer",
        "travelling": "traveling",
        "jewellery": "jewelry",
    }
    for british, american in replacements.items():
        text = text.replace(british, american)
    import re
    text = re.sub(r"[^a-z0-9 +&/\\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_/")
    return " ".join(text.split()[:8])


# ========================================
# 状态差距分类体系 (State Gap Taxonomy)
# ========================================
STATE_GAP_TAXONOMY = {
    "odor_mess_control": {
        "keywords": ["odor", "smell", "ammonia", "mess", "tracking", "stain", "spill", "leak", "dust"],
        "chinese_keywords": ["异味", "氨气味", "脏乱", "带砂", "泄漏", "灰尘"],
        "description": "气味/脏乱控制类 - 解决家庭环境尴尬、清洁压力和复购风险",
        "category": "state_trigger"
    },
    "environment_fit": {
        "keywords": ["apartment", "bedroom", "office", "outdoor", "small space", "travel", "camping", "kitchen"],
        "chinese_keywords": ["公寓", "卧室", "办公室", "户外", "小空间", "旅行", "露营", "厨房"],
        "description": "环境适配类 - 让平台和买家理解产品适合什么空间/场景",
        "category": "relationship"
    },
    "relationship_fit": {
        "keywords": ["for", "with", "without", "compatible", "replacement", "under", "near", "fits"],
        "chinese_keywords": ["适合", "搭配", "兼容", "替换", "用于", "不需要"],
        "description": "关系适配类 - 表达产品与人群、场景、配件、限制条件的关系",
        "category": "relationship"
    },
    "anxiety_reduction": {
        "keywords": ["worry", "fear", "anxiety", "afraid", "protect", "safe", "secure", "never worry", "peace of mind"],
        "chinese_keywords": ["怕", "担心", "焦虑", "安全", "保护", "安心", "再也不用担心"],
        "description": "焦虑缓解类 - 消除用户对负面后果的恐惧",
        "category": "emotional"
    },
    "convenience_improvement": {
        "keywords": ["fast", "quick", "easy", "save time", "convenient", "simplify", "hassle free", "effortless"],
        "chinese_keywords": ["方便", "快速", "轻松", "省时", "省心", "简单", "免麻烦"],
        "description": "便利性提升类 - 减少用户的时间和精力成本",
        "category": "practical"
    },
    "pain_elimination": {
        "keywords": ["pain", "ache", "relief", "comfort", "ergonomic", "soothe", "less strain"],
        "chinese_keywords": ["疼痛", "酸痛", "缓解", "舒适", "人体工学", "不累"],
        "description": "身体疼痛消除类 - 减少生理不适感",
        "category": "physical"
    },
    "social_identity": {
        "keywords": ["stylish", "premium", "professional", "minimalist", "elegant", "sleek", "modern"],
        "chinese_keywords": ["时尚", "高端", "专业", "极简", "优雅", "质感"],
        "description": "社会身份类 - 帮助用户表达自我身份",
        "category": "social"
    },
    "status_enhancement": {
        "keywords": ["premium", "luxury", "elite", "professional grade", "upgrade", "advanced"],
        "chinese_keywords": ["高级", "奢华", "精英", "专业级", "升级", "进阶"],
        "description": "地位提升类 - 帮助用户获得社会认可",
        "category": "social"
    },
    "cost_saving": {
        "keywords": ["save money", "value", "affordable", "budget", "economical", "cost effective"],
        "chinese_keywords": ["省钱", "划算", "实惠", "性价比", "便宜"],
        "description": "成本节约类 - 减少用户的经济负担",
        "category": "practical"
    },
    "health_improvement": {
        "keywords": ["healthy", "clean", "hygienic", "non toxic", "bpa free", "eco friendly"],
        "chinese_keywords": ["健康", "干净", "卫生", "无毒", "环保", "安全材质"],
        "description": "健康改善类 - 提升用户的健康水平",
        "category": "physical"
    },
    "aesthetic_satisfaction": {
        "keywords": ["beautiful", "elegant", "sleek", "minimalist", "design", "aesthetic", "look great"],
        "chinese_keywords": ["好看", "美观", "精致", "设计感", "颜值"],
        "description": "审美满足类 - 满足用户的审美需求",
        "category": "emotional"
    }
}


class CausalDiagnosisService:
    """因果诊断服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_service = AIHubService()
    
    async def diagnose_listing_causality(
        self,
        title: str,
        bullets: str,
        description: str = "",
        listing_diagnosis_id: Optional[int] = None,
        asin: Optional[str] = None,
        marketplace: str = "US",
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        对Listing进行完整的因果诊断
        
        返回:
        - 识别到的状态差距列表
        - 因果机制分析
        - 副作用检测
        - 三个因果维度评分
        """
        logger.info(f"Starting causal diagnosis for listing: {title[:60]}...")
        
        # 并行执行三个核心分析
        results = await asyncio.gather(
            self._extract_state_gaps(title, bullets, description),
            self._analyze_causal_mechanisms(title, bullets, description),
            self._detect_side_effects(title, bullets, description),
        )
        state_gaps_result, mechanisms_result, side_effects_result = results
        
        # 计算三个因果维度得分
        scores = self._calculate_causal_scores(
            state_gaps_result,
            mechanisms_result,
            side_effects_result
        )
        
        # 整合结果
        result = {
            "scores": scores,
            "state_gaps": state_gaps_result,
            "causal_mechanisms": mechanisms_result,
            "side_effects": side_effects_result,
            "overall_causal_score": scores["overall"],
            "keyword_causality": self._build_keyword_causality(state_gaps_result, mechanisms_result),
            "analysis_version": "1.1"
        }
        
        # 保存到数据库
        try:
            hsb = HumanStateBody(
                user_id=user_id,
                asin=asin,
                marketplace=marketplace,
                listing_diagnosis_id=listing_diagnosis_id,
                state_gaps=state_gaps_result.get("state_gaps_detected", []),
                causal_mechanisms=mechanisms_result.get("mechanisms", []),
                side_effects=side_effects_result.get("side_effects", []),
                population_heterogeneity=state_gaps_result.get("population_heterogeneity", {}),
                overall_causal_score=scores["overall"],
                state_gap_coverage_score=scores["state_gap_coverage"],
                mechanism_clarity_score=scores["mechanism_clarity"],
                side_effect_transparency_score=scores["side_effect_transparency"],
                source_type="listing_analysis",
                confidence_level=0.85,  # 可以根据分析质量动态调整
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(hsb)
            await self.db.commit()
            logger.info(f"Saved causal diagnosis result with id: {hsb.id}")
            result["hsb_id"] = hsb.id
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to save causal diagnosis: {e}")
        
        return result
    
    async def _extract_state_gaps(
        self,
        title: str,
        bullets: str,
        description: str
    ) -> Dict[str, Any]:
        """从Listing内容中提取人类状态差距"""
        
        prompt = f"""你是因果关系建模师。请分析以下Amazon Listing，识别它试图解决哪些人类状态差距。

【核心哲学】
商品不是"有属性的物品"，而是"状态转移算子"。它将人类从不满意的状态S1转移到满意的状态S2。
状态差距 = S2(期望状态) - S1(当前状态) = 需求的本质

【AlignX平台识别因果关键词规则】
1. 属性词(attribute)只说明"这是什么"，例如 cat litter box、bluetooth speaker，通常价格竞争激烈。
2. 关系词(relationship)说明"给谁/在哪/和什么一起用/避免什么限制"，例如 for apartment cats、with carbon filter、compatible with Echo Dot。
3. 状态触发词(state_trigger)说明"用户正在经历什么问题或想摆脱什么状态"，例如 ammonia odor control、litter tracking mess、sleep noise relief。
4. 平台识别最需要的是：产品身份词 + 关系词 + 状态触发词 + 可信因果机制。
5. 广告验证优先级必须是 state_trigger > relationship > attribute。

【产品信息】
标题: {title}
五点描述: {bullets}
产品描述: {description}

【分析要求】
请以JSON格式返回以下内容：
{{
  "state_gaps_detected": [
    {{
      "gap_type": "odor_mess_control | environment_fit | relationship_fit | anxiety_reduction | convenience_improvement | pain_elimination | social_identity | status_enhancement | cost_saving | health_improvement | aesthetic_satisfaction",
      "gap_name": "这个差距的简短名称（如'手机摔坏的焦虑'）",
      "gap_description": "详细描述这个人类状态差距是什么",
      "keyword_type": "state_trigger | relationship | attribute",
      "rufus_cosmo_role": "这个状态差距如何帮助平台识别产品身份、使用关系或购买意图",
      "american_english_keywords": ["自然美式英语关键词，不允许中文，不允许直译腔"],
      "ad_validation_keywords": ["用于广告小预算验证的美式英语关键词，优先状态触发词和关系词"],
      "gap_strength_score": 0-100分, 这个差距在目标用户中的强烈程度,
      "listing_coverage_score": 0-100分, 当前Listing覆盖并解决这个差距的程度,
      "mechanism_description": "产品通过什么机制解决这个差距",
      "evidence_provided": true/false, 是否提供了数据/证据支撑,
      "evidence_strength": 0-100分, 证据的可信度,
      "listing_expression_gap": "当前Listing在关系词、状态触发词或机制表达上的缺口",
      "gaps_in_mechanism": "因果链条中缺失或模糊的环节"
    }}
  ],
  "missing_gaps": [
    {{
      "gap_type": "gap_type",
      "gap_name": "这个产品应该解决但没有提及的状态差距",
      "keyword_type": "state_trigger | relationship",
      "suggested_keywords": ["应该补充的美式英语关系词/状态触发词"],
      "opportunity_potential": 0-100分, 填补这个差距带来的转化提升潜力
    }}
  ],
  "coverage_summary": "状态差距覆盖情况的整体总结",
  "population_heterogeneity": {{
    "segments": [
      {{
        "segment_name": "目标用户细分",
        "gap_priority": ["该用户最关心的差距1", "差距2"]
      }}
    ]
  }}
}}

只返回有效的JSON，不要其他内容。"""

        try:
            request = GenTxtRequest(
                messages=[
                    ChatMessage(
                        role="system",
                        content="你是因果关系建模师，专门分析商品如何解决人类状态差距。你擅长识别隐藏的需求和因果链条。"
                    ),
                    ChatMessage(role="user", content=prompt)
                ],
                model="AI_DEEP_MODEL",
                temperature=0.2,
                max_tokens=3000,
            )
            
            response = await self.ai_service.gentxt(request)
            return json.loads(response.content)
        except Exception as e:
            logger.error(f"State gap extraction failed: {e}")
            return {"state_gaps_detected": [], "missing_gaps": [], "error": str(e)}
    
    async def _analyze_causal_mechanisms(
        self,
        title: str,
        bullets: str,
        description: str
    ) -> Dict[str, Any]:
        """分析因果机制的清晰度和可信度"""
        
        prompt = f"""因果机制分析：商品解决问题的作用机制是否清晰可信？

【核心原则】
好的因果机制 = 清晰的因果链条 + 可验证的证据
坏的因果机制 = 黑盒宣称（"有效"但不说为什么）+ 没有证据
AlignX额外要求 = 机制必须能落到平台可识别的关系词和状态触发词，并能转成广告验证关键词。

【产品信息】
标题: {title}
五点描述: {bullets}

【分析要求】
请以JSON格式返回：
{{
  "mechanisms": [
    {{
      "mechanism_id": "简短ID",
      "gap_type": "对应的状态差距类型",
      "causal_chain": ["环节1：材质/设计", "环节2：物理/心理作用", "环节3：产生的效果", "环节4：用户感受变化"],
      "rufus_cosmo_chain": ["产品身份词", "关系词", "状态触发词", "机制证据词"],
      "validation_keyword_theme": "可用于广告验证的关键词主题，例如 ammonia odor control for apartments",
      "is_complete_chain": true/false, 因果链条是否完整清晰,
      "has_evidence": true/false, 是否有数据/测试支撑,
      "evidence_description": "证据是什么（如'1.5米跌落测试'）",
      "evidence_strength": 0-100分, 证据的说服力,
      "mechanism_clarity_score": 0-100分, 这个机制的清晰度,
      "black_box_claims": ["没有解释机制的黑盒宣称1", "宣称2"]
    }}
  ],
  "overall_mechanism_quality": 0-100分, 整体因果机制质量,
  "black_box_count": 黑盒宣称的数量,
  "improvement_suggestions": ["机制改进建议1", "建议2"]
}}

只返回有效的JSON。"""

        try:
            request = GenTxtRequest(
                messages=[
                    ChatMessage(
                        role="system",
                        content="你是因果机制分析师，擅长识别产品宣称中的因果链条完整性和证据质量。"
                    ),
                    ChatMessage(role="user", content=prompt)
                ],
                model="AI_DEEP_MODEL",
                temperature=0.2,
                max_tokens=2500,
            )
            
            response = await self.ai_service.gentxt(request)
            return json.loads(response.content)
        except Exception as e:
            logger.error(f"Causal mechanism analysis failed: {e}")
            return {"mechanisms": [], "error": str(e)}
    
    async def _detect_side_effects(
        self,
        title: str,
        bullets: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """检测产品可能带来的副作用（新的状态差距）
        
        核心洞察：任何产品在解决某些问题的同时，几乎必然会制造新的问题。
        诚实告知副作用 = 建立信任 = 长期更高转化
        """
        
        prompt = f"""副作用检测：任何产品在解决某些问题的同时，几乎必然会制造新的问题。

【核心洞察】
天下没有免费的午餐。每一个"优点"背后都有代价。
诚实告知代价 = 管理用户预期 = 减少差评退货

【产品信息】
标题: {title}
五点描述: {bullets}
产品描述: {description}

【分析要求】
请以JSON格式返回：
{{
  "side_effects": [
    {{
      "effect": "副作用描述（如'手机厚度增加35%'）",
      "effect_type": "physical_experience | convenience_cost | aesthetic_compromise | compatibility_loss | durability_tradeoff",
      "effect_strength": 0-100分, 副作用强度,
      "likelihood": 0-100分, 发生概率,
      "severity": 0-100分, 对用户体验的影响程度,
      "mentioned_in_listing": true/false, Listing中是否提及,
      "transparency_score": 如果提及了就是100分，如果没提及根据严重程度扣分,
      "user_complaint_risk": 0-100分, 用户可能因此抱怨的概率,
      "hidden_tradeoff": true/false, 是否是隐藏的权衡取舍
    }}
  ],
  "overall_transparency_score": 0-100分, 整体副作用透明度,
  "hidden_costs": ["没有明说但用户实际需要承担的代价1", "代价2"],
  "trade_off_honesty": 0-100分, 产品是否诚实地告知了权衡取舍,
  "improvement_suggestions": ["透明度改进建议1", "建议2"]
}}

只返回有效的JSON。"""

        try:
            request = GenTxtRequest(
                messages=[
                    ChatMessage(
                        role="system",
                        content="你是副作用检测专家，擅长发现产品宣称背后隐藏的权衡取舍和代价。你相信诚实告知代价是建立信任的最好方式。"
                    ),
                    ChatMessage(role="user", content=prompt)
                ],
                model="AI_DEEP_MODEL",
                temperature=0.2,
                max_tokens=2500,
            )
            
            response = await self.ai_service.gentxt(request)
            return json.loads(response.content)
        except Exception as e:
            logger.error(f"Side effect detection failed: {e}")
            return {"side_effects": [], "error": str(e)}
    
    def _calculate_causal_scores(
        self,
        state_gaps_result: Dict,
        mechanisms_result: Dict,
        side_effects_result: Dict
    ) -> Dict[str, float]:
        """计算三个因果维度得分"""
        
        # 1. 状态差距覆盖度
        gaps = state_gaps_result.get("state_gaps_detected", [])
        if gaps:
            avg_coverage = sum(g.get("listing_coverage_score", 0) for g in gaps) / len(gaps)
            has_gaps = 1.0 if len(gaps) >= 2 else 0.7 if len(gaps) >= 1 else 0.3
            state_gap_coverage = avg_coverage * 0.7 + has_gaps * 30
        else:
            state_gap_coverage = 20.0
        
        # 2. 因果机制清晰度
        mechanisms = mechanisms_result.get("mechanisms", [])
        if mechanisms:
            avg_clarity = sum(m.get("mechanism_clarity_score", 0) for m in mechanisms) / len(mechanisms)
            evidence_ratio = sum(1 for m in mechanisms if m.get("has_evidence", False)) / len(mechanisms)
            mechanism_clarity = avg_clarity * 0.6 + evidence_ratio * 40
        else:
            mechanism_clarity = 30.0
        
        # 3. 副作用透明度
        side_effects = side_effects_result.get("side_effects", [])
        if side_effects:
            avg_transparency = sum(s.get("transparency_score", 0) for s in side_effects) / len(side_effects)
            mentioned_ratio = sum(1 for s in side_effects if s.get("mentioned_in_listing", False)) / len(side_effects)
            side_effect_transparency = avg_transparency * 0.7 + mentioned_ratio * 30
        else:
            side_effect_transparency = 50.0  # 没发现也没说，给中间分

        # 4. 平台关键词验证就绪度
        keyword_causality = self._build_keyword_causality(state_gaps_result, mechanisms_result)
        keyword_validation_readiness = keyword_causality.get("readiness_score", 0)
        
        # 整体得分
        overall = (
            state_gap_coverage * 0.35 +
            mechanism_clarity * 0.30 +
            side_effect_transparency * 0.20 +
            keyword_validation_readiness * 0.15
        )
        
        return {
            "state_gap_coverage": round(state_gap_coverage, 2),
            "mechanism_clarity": round(mechanism_clarity, 2),
            "side_effect_transparency": round(side_effect_transparency, 2),
            "keyword_validation_readiness": round(keyword_validation_readiness, 2),
            "overall": round(overall, 2)
        }

    def _build_keyword_causality(self, state_gaps_result: Dict, mechanisms_result: Dict) -> Dict[str, Any]:
        """Extract the ad-verifiable platform keyword layer from causal analysis."""
        keywords: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_keyword(raw: Any, source: str, priority: str = "P1") -> None:
            keyword = _clean_keyword(raw)
            if not keyword or keyword in seen:
                return
            keyword_type = _keyword_type(keyword)
            keywords.append({
                "keyword": keyword,
                "keyword_type": keyword_type,
                "source": source,
                "priority": "P0" if keyword_type == "state_trigger" else priority,
                "validation_role": (
                    "验证用户状态差距和痛点承接"
                    if keyword_type == "state_trigger"
                    else "验证使用关系、场景和人群承接"
                    if keyword_type == "relationship"
                    else "基础品类覆盖"
                ),
            })
            seen.add(keyword)

        for gap in state_gaps_result.get("state_gaps_detected", []) or []:
            for raw in gap.get("ad_validation_keywords", []) or []:
                add_keyword(raw, "state_gap_ad_validation", "P0")
            for raw in gap.get("american_english_keywords", []) or []:
                add_keyword(raw, "state_gap_semantics", "P1")

        for gap in state_gaps_result.get("missing_gaps", []) or []:
            for raw in gap.get("suggested_keywords", []) or []:
                add_keyword(raw, "missing_gap_opportunity", "P0")

        for mechanism in mechanisms_result.get("mechanisms", []) or []:
            add_keyword(mechanism.get("validation_keyword_theme"), "causal_mechanism_theme", "P1")
            for raw in mechanism.get("rufus_cosmo_chain", []) or []:
                add_keyword(raw, "rufus_cosmo_chain", "P2")

        type_counts = {
            "state_trigger": len([item for item in keywords if item["keyword_type"] == "state_trigger"]),
            "relationship": len([item for item in keywords if item["keyword_type"] == "relationship"]),
            "attribute": len([item for item in keywords if item["keyword_type"] == "attribute"]),
        }
        strategic_count = type_counts["state_trigger"] + type_counts["relationship"]
        readiness_score = min(100, strategic_count * 18 + type_counts["state_trigger"] * 12 + max(0, 20 - type_counts["attribute"] * 2))
        priority_keywords = sorted(
            keywords,
            key=lambda item: (
                0 if item["keyword_type"] == "state_trigger" else 1 if item["keyword_type"] == "relationship" else 2,
                item["priority"],
            ),
        )[:12]
        return {
            "framework": "rufus_cosmo_causal_keywords",
            "priority_order": ["state_trigger", "relationship", "attribute"],
            "readiness_score": round(float(readiness_score), 2),
            "type_counts": type_counts,
            "priority_keywords": priority_keywords,
            "summary": "关系词和状态触发词优先进入广告验证；属性词只承担基础品类覆盖，避免纯价格竞争。",
        }
    
    @staticmethod
    def integrate_with_existing_diagnosis(
        existing_diagnosis: Dict[str, Any],
        causal_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """将因果诊断结果整合到现有的10D诊断结果中
        
        这是关键的集成函数，让因果分析成为现有诊断的增强，而不是替代
        """
        scores = causal_result.get("scores", {})
        
        # 新增因果评分到scores字段
        if "scores" in existing_diagnosis:
            existing_diagnosis["scores"]["causal_state_gap_coverage"] = scores.get("state_gap_coverage", 0)
            existing_diagnosis["scores"]["causal_mechanism_clarity"] = scores.get("mechanism_clarity", 0)
            existing_diagnosis["scores"]["causal_side_effect_transparency"] = scores.get("side_effect_transparency", 0)
        
        # 新增因果分析到analysis字段
        if "analysis" in existing_diagnosis:
            existing_diagnosis["analysis"]["causal_state_gap_coverage"] = causal_result.get("state_gaps", {}).get("coverage_summary", "")
            existing_diagnosis["analysis"]["causal_mechanism_clarity"] = f"识别到{len(causal_result.get('causal_mechanisms', {}).get('mechanisms', []))}个因果机制，整体质量{ causal_result.get('causal_mechanisms', {}).get('overall_mechanism_quality', 0)}/100"
            existing_diagnosis["analysis"]["causal_side_effect_transparency"] = causal_result.get("side_effects", {}).get("overall_transparency_score", 0)
        
        # 新增因果专属的优化建议
        suggestions = existing_diagnosis.get("suggestions", {})
        causal_suggestions = []
        
        # 状态差距优化建议
        missing_gaps = causal_result.get("state_gaps", {}).get("missing_gaps", [])
        for gap in missing_gaps:
            causal_suggestions.append(f"补充「{gap.get('gap_name')}」的场景描述和解决方案")
        
        # 机制优化建议
        mechanism_suggestions = causal_result.get("causal_mechanisms", {}).get("improvement_suggestions", [])
        causal_suggestions.extend(mechanism_suggestions)
        
        # 副作用透明度建议
        side_effect_suggestions = causal_result.get("side_effects", {}).get("improvement_suggestions", [])
        causal_suggestions.extend(side_effect_suggestions)
        
        suggestions["causal_optimization"] = causal_suggestions
        existing_diagnosis["suggestions"] = suggestions
        
        # 保存完整的因果诊断报告
        existing_diagnosis["causal_diagnosis"] = causal_result
        
        return existing_diagnosis
