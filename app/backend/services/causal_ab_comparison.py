"""
因果A/B对比服务 - Causal A/B Comparison Service

Phase 3 核心功能：
1. 两个Listing变体的因果维度对比
2. 基于历史数据的转化率预测
3. 哪个版本"更因果诚信"的判断
4. 具体优化建议

这是从"诊断"到"行动建议"的关键一步。
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from schemas.aihub import ChatMessage, GenTxtRequest
from services.aihub import AIHubService
from services.causal_diagnosis import CausalDiagnosisService
from services.review_causal_validation import ReviewCausalValidationService
from services.causal_service_base import CausalServiceBase, with_cache

logger = logging.getLogger(__name__)


@dataclass
class ABComparisonResult:
    """A/B对比结果"""
    variant_a_id: str
    variant_b_id: str
    winner: str  # "A" / "B" / "tie"
    win_margin: float  # 获胜优势 0-100
    dimension_comparison: Dict[str, Dict[str, float]]
    key_strengths_a: List[str]
    key_strengths_b: List[str]
    key_weaknesses_a: List[str]
    key_weaknesses_b: List[str]
    actionable_recommendations: List[str]
    predicted_conversion_impact: Dict[str, float]  # 预测A/B的转化率提升
    confidence_score: float  # 预测置信度 0-100


class CausalABComparisonService(CausalServiceBase):
    """因果A/B对比服务"""

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.causal_diagnosis = CausalDiagnosisService(db)
        self.review_validation = ReviewCausalValidationService(db)
        self.ai_service = AIHubService()

        # 历史基准数据（生产环境应该从数据库加载）
        # 基于历史分析得出的"因果得分 vs 转化率提升"的关系
        self.baseline_impact = {
            "state_gap_coverage": 0.3,   # 每10分提升3%转化率
            "mechanism_clarity": 0.25,   # 每10分提升2.5%转化率
            "side_effect_transparency": 0.2,  # 每10分提升2%转化率
            "honesty_score": 0.35,       # 每10分诚信度提升3.5%转化率
        }

    @staticmethod
    def _extract_json(content: str) -> Dict[str, Any]:
        text = (content or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if not match:
                raise
            return json.loads(match.group(0))

    async def compare_listings_ai(
        self,
        variant_a: Dict[str, Any],
        variant_b: Dict[str, Any],
        variant_a_id: str = "A",
        variant_b_id: str = "B",
        historical_conversion_a: Optional[float] = None,
        historical_conversion_b: Optional[float] = None,
        test_plan: Optional[Dict[str, Any]] = None,
        source_diagnosis_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Single-call DeepSeek A/B reasoning for Listing hypothesis validation.

        This is the primary production path. Static rules are only fallback.
        """
        prompt = f"""
你是 AlignX 的 Amazon Listing A/B 测试判断模型。请用用户意图 × 平台识别 × 顶级亚马逊运营操盘手逻辑，对两个版本做广告验证前判断。

重要边界：
1. A/B 不是文案审美比较，而是 Listing 假设验证。
2. 必须围绕本轮单变量，不要鼓励同时改多个变量。
3. 判断要落到广告指标：CTR、CVR、CPC、ACOS、关键词订单、无效点击率。
4. 不能把规则分当作最终结论；规则只做一致性校验。你需要做语义推理。
5. 真实广告数据最高优先级；当前没有真实广告结果时，只能输出“预测/建议验证”，不能说已验证。

来源诊断ID：{source_diagnosis_id or ""}
本轮测试计划：
{json.dumps(test_plan or {}, ensure_ascii=False)}

A版本（{variant_a_id}）：
{json.dumps(variant_a, ensure_ascii=False)}
历史CVR A：{historical_conversion_a if historical_conversion_a is not None else "未提供"}

B版本（{variant_b_id}）：
{json.dumps(variant_b, ensure_ascii=False)}
历史CVR B：{historical_conversion_b if historical_conversion_b is not None else "未提供"}

请只输出 JSON，结构必须如下：
{{
  "winner": "A | B | tie",
  "win_margin": 0-100,
  "confidence_score": 0-100,
  "model_used": "AI_DEEP_MODEL",
  "judgment_source": "deepseek_v4_reasoning",
  "dimension_comparison": {{
    "语义相关性": {{"A": 0-100, "B": 0-100, "delta": B-A, "winner": "A|B|tie"}},
    "点击吸引": {{"A": 0-100, "B": 0-100, "delta": B-A, "winner": "A|B|tie"}},
    "转化承接": {{"A": 0-100, "B": 0-100, "delta": B-A, "winner": "A|B|tie"}},
    "机制可信": {{"A": 0-100, "B": 0-100, "delta": B-A, "winner": "A|B|tie"}},
    "风险控制": {{"A": 0-100, "B": 0-100, "delta": B-A, "winner": "A|B|tie"}},
    "广告归因清晰": {{"A": 0-100, "B": 0-100, "delta": B-A, "winner": "A|B|tie"}}
  }},
  "key_strengths": {{"variant_a": ["..."], "variant_b": ["..."]}},
  "key_weaknesses": {{"variant_a": ["..."], "variant_b": ["..."]}},
  "predicted_conversion_impact": {{
    "variant_a_impact_pct": 0,
    "variant_b_impact_pct": 0,
    "delta_pct": 0
  }},
  "recommendations": [
    "必须包含小预算广告验证建议",
    "必须说明看哪些指标，以及如果CTR升CVR不升代表什么"
  ],
  "text_report": "中文完整判断，说明为什么这样判断，以及下一轮怎么验证"
}}
"""
        response = await self.ai_service.gentxt(
            GenTxtRequest(
                messages=[ChatMessage(role="user", content=prompt)],
                model="AI_DEEP_MODEL",
                temperature=0,
                max_tokens=2600,
            )
        )
        data = self._extract_json(response.content)
        winner = str(data.get("winner") or "tie").strip().upper()
        data["winner"] = winner if winner in {"A", "B"} else "tie"
        data["win_margin"] = float(data.get("win_margin") or 0)
        data["confidence_score"] = float(data.get("confidence_score") or 0)
        data["model_used"] = response.model
        data["judgment_source"] = "deepseek_v4_reasoning"
        data["data_source"] = "deepseek_v4_reasoning"
        data["usage"] = response.usage or {}
        return data

    async def compare_listings(
        self,
        variant_a: Dict[str, Any],
        variant_b: Dict[str, Any],
        variant_a_id: str = "A",
        variant_b_id: str = "B",
        historical_conversion_a: Optional[float] = None,
        historical_conversion_b: Optional[float] = None,
    ) -> ABComparisonResult:
        """
        对比两个Listing变体的因果表现

        Args:
            variant_a: 变体A的信息 {"title", "bullets", "description", "reviews"}
            variant_b: 变体B的信息
            variant_a_id: 变体A标识
            variant_b_id: 变体B标识
            historical_conversion_a: 变体A的历史转化率（可选，用于校准预测）
            historical_conversion_b: 变体B的历史转化率（可选）

        Returns:
            完整的A/B对比结果
        """
        logger.info(f"Starting causal A/B comparison: {variant_a_id} vs {variant_b_id}")

        # Step 1: 分别对两个变体做因果诊断
        diagnosis_a = await self._diagnose_variant(variant_a, variant_a_id)
        diagnosis_b = await self._diagnose_variant(variant_b, variant_b_id)

        # Step 2: 如果有评论，做因果诚信度分析
        if variant_a.get("reviews") and len(variant_a["reviews"]) >= 3:
            honesty_a = await self._analyze_honesty(variant_a)
        else:
            honesty_a = {"overall_honesty_score": 50}  # 默认中间值

        if variant_b.get("reviews") and len(variant_b["reviews"]) >= 3:
            honesty_b = await self._analyze_honesty(variant_b)
        else:
            honesty_b = {"overall_honesty_score": 50}

        # Step 3: 维度对比分析
        dimension_comparison = self._compare_dimensions(
            diagnosis_a["scores"],
            diagnosis_b["scores"],
            honesty_a["overall_honesty_score"],
            honesty_b["overall_honesty_score"]
        )

        # Step 4: 计算综合得分和获胜者
        score_a = self._calculate_comprehensive_score(
            diagnosis_a["scores"], honesty_a["overall_honesty_score"]
        )
        score_b = self._calculate_comprehensive_score(
            diagnosis_b["scores"], honesty_b["overall_honesty_score"]
        )

        winner, win_margin = self._determine_winner(score_a, score_b)

        # Step 5: 识别优缺点
        strengths_a, weaknesses_a = self._identify_strengths_weaknesses(
            diagnosis_a, honesty_a, "A"
        )
        strengths_b, weaknesses_b = self._identify_strengths_weaknesses(
            diagnosis_b, honesty_b, "B"
        )

        # Step 6: 预测转化率影响
        conversion_impact = self._predict_conversion_impact(
            diagnosis_a["scores"],
            diagnosis_b["scores"],
            honesty_a["overall_honesty_score"],
            honesty_b["overall_honesty_score"],
            historical_conversion_a,
            historical_conversion_b
        )

        # Step 7: 生成可执行建议
        recommendations = self._generate_recommendations(
            winner,
            diagnosis_a,
            diagnosis_b,
            dimension_comparison,
            strengths_a,
            weaknesses_a,
            strengths_b,
            weaknesses_b
        )

        result = ABComparisonResult(
            variant_a_id=variant_a_id,
            variant_b_id=variant_b_id,
            winner=winner,
            win_margin=win_margin,
            dimension_comparison=dimension_comparison,
            key_strengths_a=strengths_a,
            key_strengths_b=strengths_b,
            key_weaknesses_a=weaknesses_a,
            key_weaknesses_b=weaknesses_b,
            actionable_recommendations=recommendations,
            predicted_conversion_impact=conversion_impact,
            confidence_score=self._calculate_confidence(
                diagnosis_a, diagnosis_b, honesty_a, honesty_b
            )
        )

        logger.info(
            f"A/B comparison complete: {winner} wins with {win_margin:.1f}% margin. "
            f"Predicted impact: {conversion_impact}"
        )

        return result

    async def _diagnose_variant(self, variant: Dict[str, Any], variant_id: str) -> Dict[str, Any]:
        """诊断单个变体"""
        try:
            result = await self.causal_diagnosis.diagnose_listing_causality(
                title=variant.get("title", ""),
                bullets=variant.get("bullets", ""),
                description=variant.get("description", ""),
                asin=variant.get("asin"),
                marketplace=variant.get("marketplace", "US")
            )
            return result
        except Exception as e:
            logger.error(f"Diagnosis failed for variant {variant_id}: {e}")
            # 返回默认降级结果
            return {
                "scores": {
                    "state_gap_coverage": 50,
                    "mechanism_clarity": 50,
                    "side_effect_transparency": 50,
                    "overall": 50
                },
                "state_gaps": [],
                "causal_mechanisms": [],
                "side_effects": []
            }

    async def _analyze_honesty(self, variant: Dict[str, Any]) -> Dict[str, Any]:
        """分析因果诚信度"""
        try:
            result = await self.review_validation.validate_listing_claims(
                listing_title=variant.get("title", ""),
                listing_bullets=variant.get("bullets", ""),
                listing_description=variant.get("description", ""),
                reviews=variant.get("reviews", [])
            )
            return result
        except Exception as e:
            logger.error(f"Honesty analysis failed: {e}")
            return {"overall_honesty_score": 50}

    def _compare_dimensions(
        self,
        scores_a: Dict[str, float],
        scores_b: Dict[str, float],
        honesty_a: float,
        honesty_b: float
    ) -> Dict[str, Dict[str, float]]:
        """对比各个维度的表现"""
        dimensions = [
            "state_gap_coverage",
            "mechanism_clarity",
            "side_effect_transparency"
        ]

        comparison = {}
        for dim in dimensions:
            score_a = scores_a.get(dim, 50)
            score_b = scores_b.get(dim, 50)
            comparison[dim] = {
                "A": score_a,
                "B": score_b,
                "delta": score_a - score_b,
                "winner": "A" if score_a > score_b else "B" if score_b > score_a else "tie"
            }

        # 诚信度维度
        comparison["causal_honesty"] = {
            "A": honesty_a,
            "B": honesty_b,
            "delta": honesty_a - honesty_b,
            "winner": "A" if honesty_a > honesty_b else "B" if honesty_b > honesty_a else "tie"
        }

        return comparison

    def _calculate_comprehensive_score(
        self,
        scores: Dict[str, float],
        honesty_score: float
    ) -> float:
        """计算综合因果得分"""
        weighted_score = (
            scores.get("state_gap_coverage", 50) * 0.35 +
            scores.get("mechanism_clarity", 50) * 0.30 +
            scores.get("side_effect_transparency", 50) * 0.15 +
            honesty_score * 0.20
        )
        return round(weighted_score, 1)

    def _determine_winner(self, score_a: float, score_b: float) -> Tuple[str, float]:
        """判断获胜者和优势"""
        delta = abs(score_a - score_b)

        if delta < 3:
            # 差距小于3分，算平手
            return "tie", delta

        if score_a > score_b:
            return "A", delta
        else:
            return "B", delta

    def _identify_strengths_weaknesses(
        self,
        diagnosis: Dict[str, Any],
        honesty: Dict[str, Any],
        variant_label: str
    ) -> Tuple[List[str], List[str]]:
        """识别变体的优缺点"""
        scores = diagnosis.get("scores", {})
        strengths = []
        weaknesses = []

        # 分析得分维度
        if scores.get("state_gap_coverage", 0) >= 70:
            strengths.append("状态差距覆盖全面，能有效解决用户痛点")
        elif scores.get("state_gap_coverage", 0) < 50:
            weaknesses.append("状态差距覆盖不足，没有充分解决用户核心痛点")

        if scores.get("mechanism_clarity", 0) >= 70:
            strengths.append("因果机制清晰，有证据支撑，说服力强")
        elif scores.get("mechanism_clarity", 0) < 50:
            weaknesses.append("因果机制模糊，缺乏数据支撑，说服力不足")

        if scores.get("side_effect_transparency", 0) >= 70:
            strengths.append("副作用透明度高，诚实说明权衡取舍，易建立用户信任")
        elif scores.get("side_effect_transparency", 0) < 50:
            weaknesses.append("副作用披露不足，可能导致用户期望落差和差评")

        if honesty.get("overall_honesty_score", 50) >= 70:
            strengths.append("宣传高度诚信，用户实际体验与宣称一致")
        elif honesty.get("overall_honesty_score", 50) < 40:
            weaknesses.append("存在宣传夸大，用户评论验证实际效果与宣称有差距")

        # 分析发现的机会
        missing_gaps = diagnosis.get("missing_gaps", [])
        if len(missing_gaps) >= 2:
            gap_names = [g.get("gap_name", "") for g in missing_gaps[:2]]
            weaknesses.append(f"存在未覆盖的用户需求：{', '.join(gap_names)}")

        undisclosed = [
            e for e in diagnosis.get("side_effects", [])
            if not e.get("mentioned_in_listing", True) and e.get("severity", 0) > 50
        ]
        if undisclosed:
            effect_names = [e.get("effect", "") for e in undisclosed[:2]]
            weaknesses.append(f"存在未披露的高影响副作用：{', '.join(effect_names)}")

        return strengths, weaknesses

    def _predict_conversion_impact(
        self,
        scores_a: Dict[str, float],
        scores_b: Dict[str, float],
        honesty_a: float,
        honesty_b: float,
        historical_a: Optional[float] = None,
        historical_b: Optional[float] = None,
    ) -> Dict[str, float]:
        """预测转化率影响"""

        def _calculate_impact(scores: Dict[str, float], honesty: float) -> float:
            impact = 0.0
            impact += (scores.get("state_gap_coverage", 50) - 50) * self.baseline_impact["state_gap_coverage"] / 10
            impact += (scores.get("mechanism_clarity", 50) - 50) * self.baseline_impact["mechanism_clarity"] / 10
            impact += (scores.get("side_effect_transparency", 50) - 50) * self.baseline_impact["side_effect_transparency"] / 10
            impact += (honesty - 50) * self.baseline_impact["honesty_score"] / 10
            return round(impact, 1)

        impact_a = _calculate_impact(scores_a, honesty_a)
        impact_b = _calculate_impact(scores_b, honesty_b)

        result = {
            "variant_a_impact_pct": impact_a,
            "variant_b_impact_pct": impact_b,
            "delta_pct": round(impact_a - impact_b, 1)
        }

        # 如果有历史数据，结合进来
        if historical_a is not None and historical_b is not None:
            baseline_delta = (historical_a - historical_b) / historical_b * 100
            result["historical_delta_pct"] = round(baseline_delta, 1)
            result["combined_predicted_delta_pct"] = round(
                baseline_delta * 0.6 + (impact_a - impact_b) * 0.4, 1
            )

        return result

    def _generate_recommendations(
        self,
        winner: str,
        diagnosis_a: Dict[str, Any],
        diagnosis_b: Dict[str, Any],
        dimension_comparison: Dict[str, Dict[str, float]],
        strengths_a: List[str],
        weaknesses_a: List[str],
        strengths_b: List[str],
        weaknesses_b: List[str],
    ) -> List[str]:
        """生成可执行的优化建议"""
        recommendations = []

        # 总体建议
        if winner == "tie":
            recommendations.append(
                "📊 两个变体表现接近，建议进行真实A/B测试验证。"
                "当前因果分析无法分出明显优劣。"
            )
        else:
            recommendations.append(
                f"🏆 建议选择变体{winner}，在因果维度上表现更优。"
                f"但建议先进行小流量A/B测试验证实际效果。"
            )

        # 取长补短建议
        for dim, comp in dimension_comparison.items():
            dim_name = {
                "state_gap_coverage": "状态差距覆盖",
                "mechanism_clarity": "因果机制清晰度",
                "side_effect_transparency": "副作用透明度",
                "causal_honesty": "因果诚信度"
            }.get(dim, dim)

            if comp["winner"] == "A" and comp["delta"] > 10:
                recommendations.append(
                    f"💡 变体B可以借鉴变体A在「{dim_name}」上的优秀表现"
                    f"（差距{comp['delta']:.1f}分）"
                )
            elif comp["winner"] == "B" and comp["delta"] > 10:
                recommendations.append(
                    f"💡 变体A可以借鉴变体B在「{dim_name}」上的优秀表现"
                    f"（差距{comp['delta']:.1f}分）"
                )

        # 具体改进点
        all_weaknesses = [(w, "A") for w in weaknesses_a] + [(w, "B") for w in weaknesses_b]
        for weakness, variant in all_weaknesses[:5]:  # 最多5条
            recommendations.append(f"⚠️ 变体{variant}需要改进：{weakness}")

        # 共同的改进方向
        common_missing = set()
        for gap in diagnosis_a.get("missing_gaps", []):
            common_missing.add(gap.get("gap_type", ""))
        for gap in diagnosis_b.get("missing_gaps", []):
            if gap.get("gap_type", "") in common_missing:
                recommendations.append(
                    f"🎯 两个变体都存在「{gap.get('gap_name')}」覆盖不足，"
                    f"建议都加强这方面的描述"
                )
                break

        return recommendations

    def _calculate_confidence(
        self,
        diagnosis_a: Dict[str, Any],
        diagnosis_b: Dict[str, Any],
        honesty_a: Dict[str, Any],
        honesty_b: Dict[str, Any],
    ) -> float:
        """计算预测置信度"""
        confidence = 70.0  # 基准置信度

        # 如果有有效的诊断结果，置信度提升
        if diagnosis_a.get("scores", {}).get("overall", 0) > 0:
            confidence += 10
        if diagnosis_b.get("scores", {}).get("overall", 0) > 0:
            confidence += 10

        # 如果有评论验证，置信度大幅提升
        if honesty_a.get("overall_honesty_score", 50) != 50:  # 不是默认值
            confidence += 5
        if honesty_b.get("overall_honesty_score", 50) != 50:
            confidence += 5

        return min(confidence, 95)  # 最高95分，永远保留一点不确定性

    async def generate_comparison_report(
        self,
        comparison: ABComparisonResult,
        format_type: str = "text"
    ) -> str:
        """生成人类可读的对比报告"""

        if format_type == "markdown":
            return self._generate_markdown_report(comparison)
        else:
            return self._generate_text_report(comparison)

    def _generate_text_report(self, comparison: ABComparisonResult) -> str:
        """生成文本格式报告"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"因果A/B对比报告: {comparison.variant_a_id} vs {comparison.variant_b_id}")
        lines.append("=" * 60)
        lines.append("")

        if comparison.winner == "tie":
            lines.append("🏁 结果：两个变体表现相当，建议进行真实A/B测试")
        else:
            lines.append(
                f"🏆 获胜者：变体{comparison.winner} "
                f"(优势 {comparison.win_margin:.1f}分)"
            )
        lines.append("")

        lines.append("📊 维度对比：")
        for dim, comp in comparison.dimension_comparison.items():
            dim_name = {
                "state_gap_coverage": "状态差距覆盖",
                "mechanism_clarity": "因果机制清晰度",
                "side_effect_transparency": "副作用透明度",
                "causal_honesty": "因果诚信度"
            }.get(dim, dim)
            lines.append(
                f"  {dim_name}: A={comp['A']:.1f}, B={comp['B']:.1f} "
                f"(差距 {comp['delta']:+.1f})"
            )
        lines.append("")

        lines.append("💡 各变体优势：")
        for i, s in enumerate(comparison.key_strengths_a, 1):
            lines.append(f"  A-{i}: {s}")
        for i, s in enumerate(comparison.key_strengths_b, 1):
            lines.append(f"  B-{i}: {s}")
        lines.append("")

        lines.append("⚠️ 需要改进：")
        for i, w in enumerate(comparison.key_weaknesses_a, 1):
            lines.append(f"  A-{i}: {w}")
        for i, w in enumerate(comparison.key_weaknesses_b, 1):
            lines.append(f"  B-{i}: {w}")
        lines.append("")

        impact = comparison.predicted_conversion_impact
        lines.append("📈 预测转化率影响：")
        lines.append(f"  变体A: +{impact['variant_a_impact_pct']:.1f}%")
        lines.append(f"  变体B: +{impact['variant_b_impact_pct']:.1f}%")
        lines.append(f"  差距: {impact['delta_pct']:+.1f}%")
        lines.append("")

        lines.append(f"🎯 预测置信度: {comparison.confidence_score:.0f}%")
        lines.append("")

        lines.append("📋 行动建议：")
        for i, rec in enumerate(comparison.actionable_recommendations, 1):
            lines.append(f"  {i}. {rec}")

        return "\n".join(lines)

    def _generate_markdown_report(self, comparison: ABComparisonResult) -> str:
        """生成Markdown格式报告"""
        # 可以实现更丰富的Markdown格式
        return self._generate_text_report(comparison)
