"""
评论因果验证服务 - Review Causal Validation Service

核心功能：
1. 从Listing中提取商家宣称的因果效应（"减少85%摔机焦虑"）
2. 从用户评论中验证这些宣称是否真实兑现
3. 计算"宣称-实际"差距分数
4. 发现商家未宣称的意外副作用/额外好处

这是因果COSmo系统的核心闭环：
    商家宣称 → 用户实际体验 → 验证一致性 → 反馈优化
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from services.aihub import AIHubService
from schemas.aihub import GenTxtRequest, ChatMessage
from models.review_causal_validation import ReviewCausalValidation

logger = logging.getLogger(__name__)


@dataclass
class ClaimValidation:
    """单个因果宣称的验证结果"""
    claim_id: str
    original_claim: str           # 商家原始宣称
    gap_type: str                # 对应的状态差距类型
    claimed_effect: float        # 宣称的效果强度（如85%）
    actual_effect: float         # 评论中实际观察到的效果
    effect_gap: float            # 差距 = 宣称 - 实际
    confidence: float            # 验证置信度
    supporting_quotes: List[str] # 支持或反驳的评论引述
    verification_status: str     # verified / partially_verified / refuted / insufficient_data


@dataclass
class SideEffectDiscovery:
    """发现的未宣称副作用/额外好处"""
    effect_name: str
    effect_type: str             # negative_side_effect / unexpected_benefit
    prevalence_score: float      # 普遍性得分 0-100
    sentiment_score: float       # 情感得分 -100~100
    example_quotes: List[str]
    mentioned_in_listing: bool   # Listing中是否提及


class ReviewCausalValidationService:
    """评论因果验证服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_service = AIHubService()

    async def validate_listing_claims(
        self,
        listing_title: str,
        listing_bullets: str,
        reviews: List[str],
        listing_description: str = "",
        asin: Optional[str] = None,
        marketplace: str = "US",
        user_id: Optional[str] = None,
        save_result: bool = True,  # 自动保存结果
    ) -> Dict[str, Any]:
        """
        完整的因果验证流程

        Args:
            listing_title: 商品标题
            listing_bullets: 五点描述
            reviews: 用户评论列表（建议10-20条最新+最热评论）
            listing_description: 商品描述
            asin: 产品ASIN
            user_id: 用户ID

        Returns:
            完整的验证报告
        """
        logger.info(f"Starting causal validation for listing: {listing_title[:60]}...")

        # Step 1: 从Listing中提取所有因果宣称
        claims = await self._extract_causal_claims(
            listing_title, listing_bullets, listing_description
        )

        # Step 2: 从评论中验证每个宣称
        validations = []
        for claim in claims:
            validation = await self._validate_single_claim(claim, reviews)
            validations.append(validation)

        # Step 3: 发现Listing中未宣称的效应（副作用/意外好处）
        undiscovered_effects = await self._discover_undisclosed_effects(
            claims, reviews, listing_title
        )

        # Step 4: 计算整体诚信度得分
        honesty_score = self._calculate_honesty_score(validations, undiscovered_effects)

        # Step 5: 生成优化建议
        suggestions = self._generate_optimization_suggestions(
            validations, undiscovered_effects
        )

        result = {
            "overall_honesty_score": honesty_score,
            "claim_validations": [v.__dict__ for v in validations],
            "undiscovered_effects": [e.__dict__ for e in undiscovered_effects],
            "total_claims_analyzed": len(claims),
            "reviews_analyzed": len(reviews),
            "optimization_suggestions": suggestions,
            "summary": self._generate_validation_summary(
                honesty_score, validations, undiscovered_effects
            )
        }

        # 自动保存结果到数据库
        if save_result:
            record_id = await self._save_result(
                result=result,
                title=listing_title,
                asin=asin,
                marketplace=marketplace,
                user_id=user_id
            )
            result["id"] = record_id

        return result

    async def _extract_causal_claims(
        self, title: str, bullets: str, description: str
    ) -> List[Dict[str, Any]]:
        """
        从Listing内容中提取所有因果效应宣称

        例子：
        - "军工级防摔，减少85%碎屏风险" → {gap: anxiety_reduction, effect: 85%}
        - "30分钟充满电，节省70%充电时间" → {gap: convenience, effect: 70%}
        """

        prompt = f"""你是因果宣称提取专家。请从以下Amazon Listing中提取所有的因果效应宣称。

【Listing内容】
标题：{title}

五点描述：{bullets}

产品描述：{description}

【提取规则】
1. 因果宣称 = 明确声称产品能产生某种效果的语句
2. 效果必须是可测量的（百分比、程度、时间等）或明确的状态改变
3. 忽略纯粹的主观形容词（如"最好的"、"顶级的"）
4. 重点提取：问题解决、状态改变、效果量化的宣称

【返回格式】请以JSON格式返回：
{{
  "claims": [
    {{
      "claim_text": "原始宣称文本",
      "gap_type": "anxiety_reduction / convenience_improvement / pain_elimination / social_identity / cost_saving / health_improvement / aesthetic_satisfaction / other",
      "claimed_effect_strength": 0-100的数值（宣称的效果强度，如果没有数字则根据语义估算）,
      "effect_direction": "positive / negative",
      "has_quantitative_claim": true/false, 是否有量化宣称（如"85%"）,
      "mechanism_mentioned": "简述提到的作用机制，如果有的话"
    }}
  ],
  "summary": "提取总结"
}}

只返回JSON，不要其他内容。"""

        try:
            request = GenTxtRequest(
                messages=[
                    ChatMessage(
                        role="system",
                        content="你是因果宣称提取专家，擅长识别产品营销中的因果效应宣称。"
                    ),
                    ChatMessage(role="user", content=prompt)
                ],
                model="AI_DEEP_MODEL",
                temperature=0.1,
                max_tokens=3000,
            )

            response = await self.ai_service.gentxt(request)
            result = json.loads(response.content)
            return result.get("claims", [])
        except Exception as e:
            logger.error(f"Claim extraction failed: {e}")
            return []

    async def _validate_single_claim(
        self, claim: Dict[str, Any], reviews: List[str]
    ) -> ClaimValidation:
        """验证单个因果宣称的真实性"""

        claim_text = claim.get("claim_text", "")
        claimed_effect = claim.get("claimed_effect_strength", 50)
        gap_type = claim.get("gap_type", "other")

        reviews_text = "\n\n---评论分隔---\n\n".join(reviews[:20])  # 最多用20条评论

        prompt = f"""请验证以下商品宣称在用户评论中的真实表现。

【商家宣称】
{claim_text}
宣称效果强度：{claimed_effect}%

【用户评论样本】
{reviews_text}

【分析要求】
请基于评论内容分析：
1. 有多少评论提到了这个宣称相关的体验？
2. 实际体验与宣称相比，是更好、差不多、还是更差？
3. 提取最能支持或反驳的3条评论原文
4. 给出0-100的实际效果得分

请以JSON格式返回：
{{
  "actual_effect_score": 0-100,
  "confidence": 0-100（验证置信度，基于提及此话题的评论数量）,
  "supporting_quotes": ["评论原文1", "评论原文2", "评论原文3"],
  "verdict": "verified / partially_verified / refuted / insufficient_data",
  "verdict_reason": "判决理由说明"
}}

只返回JSON。"""

        try:
            request = GenTxtRequest(
                messages=[
                    ChatMessage(
                        role="system",
                        content="你是客观的因果效应验证者，基于真实用户评论验证商家宣称的真实性。你既不吹毛求疵也不轻易放过夸大宣传。"
                    ),
                    ChatMessage(role="user", content=prompt)
                ],
                model="AI_DEEP_MODEL",
                temperature=0.1,
                max_tokens=2000,
            )

            response = await self.ai_service.gentxt(request)
            result = json.loads(response.content)

            actual_effect = result.get("actual_effect_score", 50)
            effect_gap = claimed_effect - actual_effect

            return ClaimValidation(
                claim_id=f"claim_{hash(claim_text) % 10000}",
                original_claim=claim_text,
                gap_type=gap_type,
                claimed_effect=claimed_effect,
                actual_effect=actual_effect,
                effect_gap=effect_gap,
                confidence=result.get("confidence", 0),
                supporting_quotes=result.get("supporting_quotes", []),
                verification_status=result.get("verdict", "insufficient_data")
            )

        except Exception as e:
            logger.error(f"Claim validation failed for '{claim_text[:50]}': {e}")
            return ClaimValidation(
                claim_id=f"claim_{hash(claim_text) % 10000}",
                original_claim=claim_text,
                gap_type=gap_type,
                claimed_effect=claimed_effect,
                actual_effect=50,
                effect_gap=0,
                confidence=0,
                supporting_quotes=[],
                verification_status="insufficient_data"
            )

    async def _discover_undisclosed_effects(
        self, claims: List[Dict[str, Any]], reviews: List[str], title: str
    ) -> List[SideEffectDiscovery]:
        """
        发现Listing中未宣称的效应：
        - 负面：未提及的副作用（"这个壳太厚了，放口袋很不舒服"）
        - 正面：意外的额外好处（"没想到这个支架看剧这么方便"）
        """

        reviews_text = "\n\n---评论分隔---\n\n".join(reviews[:30])

        claimed_effects_text = ", ".join([
            c.get("claim_text", "") for c in claims
        ])

        prompt = f"""请分析以下用户评论，发现商家在Listing中没有明确宣称的效应。

【产品】
{title}

【商家已宣称的效应】
{claimed_effects_text}

【用户评论样本】
{reviews_text}

【分析要求】
请找出评论中频繁提到但商家没有明确宣称的效应：
1. 负面的未宣称副作用（如厚度、重量、兼容性问题等）
2. 正面的意外好处（如发现了宣传中没提到的方便功能）

请以JSON格式返回：
{{
  "undisclosed_effects": [
    {{
      "effect_name": "效应名称（简短）",
      "effect_type": "negative_side_effect / unexpected_benefit",
      "prevalence_score": 0-100（评论中提到的频繁程度）,
      "sentiment_score": -100~100（用户对此的情感，负面为负，正面为正）,
      "example_quotes": ["评论原文1", "评论原文2"],
      "mentioned_in_listing": false（几乎总是false，因为是未宣称的）
    }}
  ]
}}

只返回JSON。"""

        try:
            request = GenTxtRequest(
                messages=[
                    ChatMessage(
                        role="system",
                        content="你是用户体验分析师，擅长发现商品宣传中没提到的真实体验，无论是惊喜还是失望。"
                    ),
                    ChatMessage(role="user", content=prompt)
                ],
                model="AI_DEEP_MODEL",
                temperature=0.2,
                max_tokens=3000,
            )

            response = await self.ai_service.gentxt(request)
            result = json.loads(response.content)

            effects = result.get("undisclosed_effects", [])
            return [
                SideEffectDiscovery(**e) for e in effects
            ]
        except Exception as e:
            logger.error(f"Undiscovered effect detection failed: {e}")
            return []

    def _calculate_honesty_score(
        self,
        validations: List[ClaimValidation],
        undiscovered: List[SideEffectDiscovery]
    ) -> float:
        """
        计算整体"因果诚信度"得分 (0-100)

        计算逻辑：
        1. 宣称与实际的差距（权重50%）
        2. 被反驳的宣称数量惩罚（权重25%）
        3. 未披露的负面副作用惩罚（权重25%）
        """

        if not validations:
            return 50.0  # 没有宣称可验证，给中间分

        # 1. 效果差距得分：差距越小得分越高
        total_gap = sum(abs(v.effect_gap) for v in validations)
        avg_gap = total_gap / len(validations)
        gap_score = max(0, 100 - avg_gap * 1.5)  # 每1%差距扣1.5分

        # 2. 验证状态得分
        verified_count = sum(1 for v in validations if v.verification_status == "verified")
        refuted_count = sum(1 for v in validations if v.verification_status == "refuted")
        verification_score = (verified_count / len(validations)) * 100
        # 被反驳的额外惩罚
        verification_score = max(0, verification_score - refuted_count * 15)

        # 3. 未披露副作用惩罚
        negative_effects = [
            e for e in undiscovered
            if e.effect_type == "negative_side_effect" and e.prevalence_score > 30
        ]
        side_effect_penalty = sum(e.prevalence_score / 10 for e in negative_effects)

        # 加权汇总
        honesty_score = (
            gap_score * 0.5 +
            verification_score * 0.25 +
            max(0, 100 - side_effect_penalty) * 0.25
        )

        return round(honesty_score, 1)

    def _generate_optimization_suggestions(
        self,
        validations: List[ClaimValidation],
        undiscovered: List[SideEffectDiscovery]
    ) -> List[str]:
        """生成因果优化建议"""
        suggestions = []

        # 1. 被反驳宣称的建议
        refuted = [v for v in validations if v.verification_status == "refuted"]
        for v in refuted:
            suggestions.append(
                f"⚠️ 宣称「{v.original_claim[:40]}...」被评论验证为夸大。"
                f"宣称效果{v.claimed_effect}%，实际仅{v.actual_effect}%。建议调降宣传或改进产品。"
            )

        # 2. 部分验证的建议
        partial = [v for v in validations if v.verification_status == "partially_verified"]
        for v in partial:
            suggestions.append(
                f"🔍 宣称「{v.original_claim[:40]}...」部分验证。"
                f"建议补充更具体的使用条件或人群说明。"
            )

        # 3. 未披露副作用建议
        negative_effects = [
            e for e in undiscovered
            if e.effect_type == "negative_side_effect" and e.prevalence_score > 40
        ]
        for e in negative_effects:
            suggestions.append(
                f"💡 发现未披露副作用「{e.effect_name}」。"
                f"建议在Listing中诚实提及这一权衡取舍，可建立用户信任并降低退货率。"
            )

        # 4. 意外好处建议（可以作为新卖点！）
        unexpected_benefits = [
            e for e in undiscovered
            if e.effect_type == "unexpected_benefit" and e.prevalence_score > 30
        ]
        for e in unexpected_benefits:
            suggestions.append(
                f"✨ 发现意外好处「{e.effect_name}」。"
                f"用户很喜欢但你没宣传！建议加到Listing中作为新卖点。"
            )

        return suggestions

    def _generate_validation_summary(
        self,
        honesty_score: float,
        validations: List[ClaimValidation],
        undiscovered: List[SideEffectDiscovery]
    ) -> str:
        """生成验证摘要"""

        if honesty_score >= 80:
            rating = "优秀🎖️"
        elif honesty_score >= 60:
            rating = "良好👍"
        elif honesty_score >= 40:
            rating = "一般⚠️"
        else:
            rating = "待改进🚨"

        verified = sum(1 for v in validations if v.verification_status == "verified")
        refuted = sum(1 for v in validations if v.verification_status == "refuted")
        negative_effects = sum(
            1 for e in undiscovered
            if e.effect_type == "negative_side_effect" and e.prevalence_score > 40
        )
        benefits = sum(
            1 for e in undiscovered
            if e.effect_type == "unexpected_benefit" and e.prevalence_score > 30
        )

        return (
            f"因果诚信度得分: {honesty_score:.1f}分（{rating}）。"
            f"分析了{len(validations)}个因果宣称，其中{verified}个验证属实，"
            f"{refuted}个被证伪。"
            f"发现{negative_effects}个未披露的高影响副作用，"
            f"和{benefits}个可以作为新卖点的意外好处。"
        )


    async def _save_result(
        self,
        result: Dict[str, Any],
        title: str = "",
        asin: Optional[str] = None,
        marketplace: str = "US",
        user_id: Optional[str] = None,
    ) -> int:
        """保存验证结果到数据库"""
        try:
            validations = result.get("claim_validations", [])
            summary = {
                "verified_count": sum(1 for v in validations if v.get("verification_status") == "verified"),
                "partially_verified_count": sum(1 for v in validations if v.get("verification_status") == "partially_verified"),
                "refuted_count": sum(1 for v in validations if v.get("verification_status") == "refuted"),
                "insufficient_data_count": sum(1 for v in validations if v.get("verification_status") == "insufficient_data"),
                "negative_side_effects_count": sum(
                    1 for e in result.get("undiscovered_effects", [])
                    if e.get("effect_type") == "negative_side_effect"
                ),
                "unexpected_benefits_count": sum(
                    1 for e in result.get("undiscovered_effects", [])
                    if e.get("effect_type") == "unexpected_benefit"
                ),
            }

            record = ReviewCausalValidation(
                user_id=user_id,
                asin=asin,
                marketplace=marketplace,
                listing_title=title[:500] if title else None,
                overall_honesty_score=result.get("overall_honesty_score"),
                total_claims_analyzed=result.get("total_claims_analyzed", 0),
                total_reviews_used=result.get("reviews_analyzed", 0),
                claims_validation=validations,
                undisclosed_effects=result.get("undiscovered_effects", []),
                optimization_suggestions=result.get("optimization_suggestions", []),
                validation_summary=summary,
                confidence_score=80.0,
            )

            self.db.add(record)
            await self.db.commit()
            await self.db.refresh(record)

            logger.info(f"Saved review causal validation result id={record.id}")
            return record.id

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to save review causal validation: {e}")
            raise

    async def get_history(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """获取用户的验证历史"""
        try:
            query = select(ReviewCausalValidation).where(
                ReviewCausalValidation.user_id == user_id
            ).order_by(ReviewCausalValidation.created_at.desc())

            count_query = select(func.count(ReviewCausalValidation.id)).where(
                ReviewCausalValidation.user_id == user_id
            )

            result = await self.db.execute(query.offset(skip).limit(limit))
            records = result.scalars().all()

            count_result = await self.db.execute(count_query)
            total = count_result.scalar() or 0

            return {
                "items": [r.get_summary() for r in records],
                "total": total,
                "skip": skip,
                "limit": limit
            }

        except Exception as e:
            logger.error(f"Failed to get review causal validation history: {e}")
            raise

    async def get_detail(self, record_id: int, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取单条验证详情"""
        try:
            query = select(ReviewCausalValidation).where(ReviewCausalValidation.id == record_id)
            result = await self.db.execute(query)
            record = result.scalar_one_or_none()

            if not record:
                return None

            if user_id and record.user_id and record.user_id != user_id:
                return None

            return {
                "id": record.id,
                "asin": record.asin,
                "listing_title": record.listing_title,
                "overall_honesty_score": record.overall_honesty_score,
                "total_claims_analyzed": record.total_claims_analyzed,
                "total_reviews_used": record.total_reviews_used,
                "claims_validation": record.claims_validation or [],
                "undisclosed_effects": record.undisclosed_effects or [],
                "optimization_suggestions": record.optimization_suggestions or [],
                "validation_summary": record.validation_summary or {},
                "created_at": record.created_at.isoformat() if record.created_at else None
            }

        except Exception as e:
            logger.error(f"Failed to get review causal validation detail: {e}")
            raise
