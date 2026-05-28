"""
因果诊断API路由 - Causal Diagnosis Router

提供独立的因果分析端点，包括：
- Listing因果诊断
- 状态差距机会池分析
- 因果机制验证
- 副作用深度检测
"""

import json
import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.database import get_db
from dependencies.auth import get_current_user, get_user_scope_ids
from schemas.auth import UserResponse
from services.causal_diagnosis import CausalDiagnosisService, STATE_GAP_TAXONOMY
from services.review_causal_validation import ReviewCausalValidationService
from services.causal_ab_comparison import CausalABComparisonService
from services.causal_service_base import get_batch_processor
from models.human_state_body import HumanStateBody

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/causal", tags=["causal-diagnosis"])


# ---------- Request / Response Models ----------

class ListingCausalRequest(BaseModel):
    """Listing因果诊断请求"""
    title: str = ""
    bullet_points: str = ""
    description: str = ""
    asin: Optional[str] = None
    marketplace: str = "US"


class StateGapAnalysisRequest(BaseModel):
    """状态差距分析请求（跨品类）"""
    category: str = ""
    keyword: str = ""
    marketplace: str = "US"
    analysis_depth: str = "standard"  # standard / deep


class GapOpportunityResponse(BaseModel):
    """状态差距机会点"""
    gap_type: str
    gap_name: str
    description: str
    market_size_estimate: int  # 估计的市场规模指数 0-100
    coverage_ratio: float     # 当前竞品的平均覆盖率
    opportunity_score: float   # 机会得分 = 市场需求 × (1-覆盖率)
    difficulty_score: float   # 实现难度
    example_listings: List[str] = []


class CausalDiagnosisResponse(BaseModel):
    """因果诊断响应"""
    scores: Dict[str, float]
    state_gaps: List[Dict[str, Any]]
    causal_mechanisms: List[Dict[str, Any]]
    side_effects: List[Dict[str, Any]]
    missing_gaps: List[Dict[str, Any]]
    overall_summary: str
    optimization_suggestions: List[str]


class CausalHistoryItem(BaseModel):
    """因果诊断历史项"""
    id: int
    asin: Optional[str]
    marketplace: str
    overall_causal_score: Optional[float]
    state_gap_count: int
    created_at: Optional[str]


# ---------- API Endpoints ----------

@router.post("/diagnose", response_model=CausalDiagnosisResponse)
async def diagnose_listing_causality(
    request: ListingCausalRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    对Listing进行独立的因果诊断（不依赖传统10D分析）
    
    这是因果系统的核心入口，专注于：
    - 识别人类状态差距
    - 分析因果机制清晰度
    - 检测副作用透明度
    """
    try:
        if not request.title and not request.bullet_points:
            raise HTTPException(status_code=400, detail="请至少输入标题或五点描述")

        service = CausalDiagnosisService(db)
        result = await service.diagnose_listing_causality(
            title=request.title or "",
            bullets=request.bullet_points or "",
            description=request.description or "",
            asin=request.asin,
            marketplace=request.marketplace,
            user_id=str(current_user.id),
        )

        # 生成优化建议汇总
        optimization_suggestions = []
        missing_gaps = result.get("state_gaps", {}).get("missing_gaps", [])
        for gap in missing_gaps:
            optimization_suggestions.append(
                f"补充「{gap.get('gap_name', '')}」的场景描述和解决方案 "
                f"(潜在机会: {gap.get('opportunity_potential', 0)}分)"
            )

        mechanism_suggestions = result.get("causal_mechanisms", {}).get("improvement_suggestions", [])
        if isinstance(mechanism_suggestions, list):
            optimization_suggestions.extend(mechanism_suggestions)

        side_effect_suggestions = result.get("side_effects", {}).get("improvement_suggestions", [])
        if isinstance(side_effect_suggestions, list):
            optimization_suggestions.extend(side_effect_suggestions)

        # 生成整体总结
        scores = result.get("scores", {})
        overall_score = scores.get("overall", 0)
        gaps_count = len(result.get("state_gaps", {}).get("state_gaps_detected", []))
        mechanisms_count = len(result.get("causal_mechanisms", {}).get("mechanisms", []))
        side_effects_count = len(result.get("side_effects", {}).get("side_effects", []))

        if overall_score >= 80:
            summary_level = "优秀"
        elif overall_score >= 60:
            summary_level = "良好"
        elif overall_score >= 40:
            summary_level = "一般"
        else:
            summary_level = "待提升"

        overall_summary = (
            f"因果诊断整体得分: {overall_score:.1f}分（{summary_level}）。"
            f"识别到 {gaps_count} 个用户状态差距，{mechanisms_count} 个因果解决机制，"
            f"{side_effects_count} 个潜在副作用/权衡点。"
            f"建议重点优化 {len(missing_gaps)} 个未覆盖的状态差距。"
        )

        return CausalDiagnosisResponse(
            scores=scores,
            state_gaps=result.get("state_gaps", {}).get("state_gaps_detected", []),
            causal_mechanisms=result.get("causal_mechanisms", {}).get("mechanisms", []),
            side_effects=result.get("side_effects", {}).get("side_effects", []),
            missing_gaps=missing_gaps,
            overall_summary=overall_summary,
            optimization_suggestions=optimization_suggestions[:10],  # 最多返回10条
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Causal diagnosis error: {e}")
        raise HTTPException(status_code=500, detail=f"因果诊断失败: {str(e)}")


@router.get("/gap-taxonomy")
async def get_state_gap_taxonomy():
    """
    获取状态差距分类体系
    
    返回所有已定义的状态差距类型，用于：
    - 前端展示选项
    - 卖家理解因果分析框架
    """
    return {
        "taxonomy_version": "1.0",
        "total_categories": len(STATE_GAP_TAXONOMY),
        "categories": [
            {
                "gap_type": gap_type,
                "description": data.get("description", ""),
                "category": data.get("category", ""),
            }
            for gap_type, data in STATE_GAP_TAXONOMY.items()
        ]
    }


@router.post("/gap-opportunity-analysis")
async def analyze_gap_opportunities(
    request: StateGapAnalysisRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    分析品类中的状态差距机会
    
    通过历史数据分析：
    - 哪些状态差距在该品类中普遍存在
    - 竞品的平均覆盖率是多少
    - 哪些是高价值的空白机会点
    """
    try:
        # 1. 获取该品类的历史诊断数据
        query = select(HumanStateBody).where(
            HumanStateBody.marketplace == request.marketplace
        )
        
        # 如果有关键词，过滤相关的
        if request.keyword:
            # 这里可以加入更复杂的匹配逻辑
            pass
            
        result = await db.execute(query.limit(100))
        historical_data = result.scalars().all()

        # 2. 统计各状态差距的出现频率和平均覆盖率
        gap_stats = {}
        for record in historical_data:
            if not record.state_gaps:
                continue
                
            for gap in record.state_gaps:
                gap_type = gap.get("gap_type", "unknown")
                if gap_type not in gap_stats:
                    gap_stats[gap_type] = {
                        "count": 0,
                        "coverage_scores": [],
                        "gap_names": set()
                    }
                
                gap_stats[gap_type]["count"] += 1
                gap_stats[gap_type]["coverage_scores"].append(gap.get("coverage_score", 0))
                gap_stats[gap_type]["gap_names"].add(gap.get("gap_name", ""))

        # 3. 生成机会分析
        opportunities = []
        total_records = max(len(historical_data), 1)
        
        for gap_type, stats in gap_stats.items():
            frequency = stats["count"] / total_records
            avg_coverage = sum(stats["coverage_scores"]) / max(len(stats["coverage_scores"]), 1) / 100
            
            # 机会得分 = 需求频率 × (1 - 平均覆盖率) × 100
            opportunity_score = frequency * (1 - avg_coverage) * 100
            
            # 实现难度估算（基于机制复杂度）
            difficulty_score = _estimate_difficulty(gap_type)
            
            opportunities.append(GapOpportunityResponse(
                gap_type=gap_type,
                gap_name=list(stats["gap_names"])[0] if stats["gap_names"] else gap_type,
                description=STATE_GAP_TAXONOMY.get(gap_type, {}).get("description", ""),
                market_size_estimate=int(frequency * 100),
                coverage_ratio=round(avg_coverage, 2),
                opportunity_score=round(opportunity_score, 1),
                difficulty_score=difficulty_score,
                example_listings=[]
            ))

        # 按机会得分排序
        opportunities.sort(key=lambda x: x.opportunity_score, reverse=True)

        return {
            "category": request.category or "all",
            "analyzed_samples": len(historical_data),
            "total_gap_types_found": len(gap_stats),
            "opportunities": opportunities[:15],  # 返回Top 15机会点
            "summary": (
                f"基于 {len(historical_data)} 个样本分析，发现 {len(gap_stats)} 种状态差距。"
                f"Top 3机会: {', '.join([o.gap_name for o in opportunities[:3]])}"
            )
        }

    except Exception as e:
        logger.error(f"Gap opportunity analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"机会分析失败: {str(e)}")


@router.get("/history", response_model=List[CausalHistoryItem])
async def get_causal_diagnosis_history(
    skip: int = 0,
    limit: int = 20,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户的因果诊断历史记录"""
    try:
        scope_user_ids = await get_user_scope_ids(current_user, db)
        query = (
            select(HumanStateBody)
            .where(HumanStateBody.user_id.in_(scope_user_ids))
            .order_by(HumanStateBody.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        records = result.scalars().all()

        return [
            CausalHistoryItem(
                id=r.id,
                asin=r.asin,
                marketplace=r.marketplace or "US",
                overall_causal_score=r.overall_causal_score,
                state_gap_count=len(r.state_gaps) if r.state_gaps else 0,
                created_at=r.created_at.isoformat() if r.created_at else None
            )
            for r in records
        ]

    except Exception as e:
        logger.error(f"Get causal history error: {e}")
        raise HTTPException(status_code=500, detail=f"获取历史记录失败: {str(e)}")


@router.get("/history/{diagnosis_id}")
async def get_causal_diagnosis_detail(
    diagnosis_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单条因果诊断的详细结果"""
    try:
        query = select(HumanStateBody).where(HumanStateBody.id == diagnosis_id)
        result = await db.execute(query)
        record = result.scalar_one_or_none()

        if not record:
            raise HTTPException(status_code=404, detail="因果诊断记录不存在")

        # 验证所有权
        scope_user_ids = await get_user_scope_ids(current_user, db)
        if record.user_id and record.user_id not in scope_user_ids:
            raise HTTPException(status_code=403, detail="无权访问此记录")

        return {
            "id": record.id,
            "asin": record.asin,
            "marketplace": record.marketplace,
            "scores": {
                "overall": record.overall_causal_score,
                "state_gap_coverage": record.state_gap_coverage_score,
                "mechanism_clarity": record.mechanism_clarity_score,
                "side_effect_transparency": record.side_effect_transparency_score,
            },
            "state_gaps": record.state_gaps or [],
            "causal_mechanisms": record.causal_mechanisms or [],
            "side_effects": record.side_effects or [],
            "population_heterogeneity": record.population_heterogeneity or {},
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get causal detail error: {e}")
        raise HTTPException(status_code=500, detail=f"获取诊断详情失败: {str(e)}")


@router.post("/side-effect-deep-dive")
async def deep_dive_side_effects(
    request: ListingCausalRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    副作用深度检测
    
    专门深入分析产品可能带来的隐藏代价和权衡取舍：
    - 物理体验权衡（厚度 vs 防护）
    - 使用便利性代价（功能多了会不会更复杂？）
    - 美学妥协（功能性 vs 美观）
    - 兼容性损失
    - 长期使用风险
    """
    try:
        service = CausalDiagnosisService(db)
        side_effect_result = await service._detect_side_effects(
            title=request.title or "",
            bullets=request.bullet_points or ""
        )

        # 增强分析：按影响领域分类
        side_effects = side_effect_result.get("side_effects", [])
        categorized = {}
        
        for se in side_effects:
            effect_type = se.get("effect_type", "other")
            if effect_type not in categorized:
                categorized[effect_type] = []
            categorized[effect_type].append(se)

        # 风险评级
        high_risk_count = sum(
            1 for se in side_effects 
            if se.get("severity", 0) > 60 and not se.get("mentioned_in_listing", False)
        )

        risk_level = "高" if high_risk_count >= 2 else "中" if high_risk_count >= 1 else "低"

        return {
            "overall_transparency_score": side_effect_result.get("overall_transparency_score", 0),
            "trade_off_honesty": side_effect_result.get("trade_off_honesty", 0),
            "risk_level": risk_level,
            "high_risk_items_count": high_risk_count,
            "categorized_side_effects": categorized,
            "hidden_costs": side_effect_result.get("hidden_costs", []),
            "improvement_suggestions": side_effect_result.get("improvement_suggestions", []),
            "summary": (
                f"副作用透明度得分为 {side_effect_result.get('overall_transparency_score', 0):.1f}分，"
                f"风险级别为「{risk_level}」。发现 {len(side_effects)} 个潜在副作用，"
                f"其中 {high_risk_count} 个属于高风险且未在Listing中提及。"
            )
        }

    except Exception as e:
        logger.error(f"Side effect deep dive error: {e}")
        raise HTTPException(status_code=500, detail=f"副作用深度分析失败: {str(e)}")


# ---------- 评论因果验证端点 ----------

class ReviewValidationRequest(BaseModel):
    """评论因果验证请求"""
    listing_title: str
    listing_bullets: str = ""
    listing_description: str = ""
    reviews: List[str]  # 用户评论列表，建议10-20条
    asin: Optional[str] = None


@router.post("/review-validation")
async def validate_reviews_causality(
    request: ReviewValidationRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    🔍 评论因果验证 - 因果COSmo的核心闭环功能
    
    这个功能是因果系统最强大的部分：
    1. 从Listing中提取商家宣称的所有因果效应（"减少85%摔机焦虑"）
    2. 从用户评论中反向验证这些宣称是否真实兑现
    3. 计算"宣称-实际"差距分数
    4. 发现商家未宣称的意外副作用/额外好处
    
    这是真正的因果闭环：
        商家宣称 → 用户实际体验 → 验证一致性 → 反馈优化
    """
    try:
        if len(request.reviews) < 3:
            raise HTTPException(
                status_code=400, 
                detail="请至少提供3条用户评论以进行有效验证"
            )

        service = ReviewCausalValidationService(db)
        result = await service.validate_listing_claims(
            listing_title=request.listing_title,
            listing_bullets=request.listing_bullets,
            listing_description=request.listing_description,
            reviews=request.reviews,
            asin=request.asin,
            user_id=str(current_user.id),
        )

        # 根据得分给出评级
        score = result.get("overall_honesty_score", 50)
        if score >= 80:
            rating = "🎖️ 优秀 - 宣传高度诚信"
        elif score >= 60:
            rating = "👍 良好 - 基本属实"
        elif score >= 40:
            rating = "⚠️ 一般 - 部分夸大"
        else:
            rating = "🚨 需改进 - 宣传与实际差距较大"

        result["honesty_rating"] = rating
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Review causal validation error: {e}")
        raise HTTPException(status_code=500, detail=f"评论因果验证失败: {str(e)}")


# ---------- Phase 3: 因果A/B对比端点 ----------

class ABComparisonRequest(BaseModel):
    """因果A/B对比请求"""
    variant_a: dict  # {"title", "bullets", "description", "reviews", "asin"}
    variant_b: dict
    variant_a_label: str = "Original"
    variant_b_label: str = "Optimized"
    historical_conversion_a: Optional[float] = None
    historical_conversion_b: Optional[float] = None
    test_plan: Optional[dict] = None
    source_diagnosis_id: Optional[int] = None


@router.post("/ab-comparison")
async def compare_listings_ab(
    request: ABComparisonRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    🆚 因果A/B对比 - Phase 3 核心功能
    
    对比两个Listing变体的因果表现：
    1. 三维度因果得分对比（状态差距、机制清晰度、透明度）
    2. 因果诚信度对比
    3. 识别各变体的优缺点
    4. 预测转化率影响
    5. 给出可执行的优化建议
    
    **使用场景**：
    - 两个Listing版本哪个更好？
    - 我的Listing vs 竞品Listing，差距在哪里？
    - 优化前后对比，验证改进效果
    """
    try:
        service = CausalABComparisonService(db)
        try:
            return await service.compare_listings_ai(
                variant_a=request.variant_a,
                variant_b=request.variant_b,
                variant_a_id=request.variant_a_label,
                variant_b_id=request.variant_b_label,
                historical_conversion_a=request.historical_conversion_a,
                historical_conversion_b=request.historical_conversion_b,
                test_plan=request.test_plan or {},
                source_diagnosis_id=request.source_diagnosis_id,
            )
        except Exception as ai_error:
            logger.warning(f"DeepSeek A/B comparison failed, using backend rules fallback: {ai_error}")

        result = await service.compare_listings(
            variant_a=request.variant_a,
            variant_b=request.variant_b,
            variant_a_id=request.variant_a_label,
            variant_b_id=request.variant_b_label,
            historical_conversion_a=request.historical_conversion_a,
            historical_conversion_b=request.historical_conversion_b,
        )

        # 生成文本报告
        text_report = await service.generate_comparison_report(result, format_type="text")

        return {
            "winner": result.winner,
            "win_margin": result.win_margin,
            "confidence_score": result.confidence_score,
            "dimension_comparison": result.dimension_comparison,
            "key_strengths": {
                "variant_a": result.key_strengths_a,
                "variant_b": result.key_strengths_b
            },
            "key_weaknesses": {
                "variant_a": result.key_weaknesses_a,
                "variant_b": result.key_weaknesses_b
            },
            "predicted_conversion_impact": result.predicted_conversion_impact,
            "recommendations": result.actionable_recommendations,
            "text_report": f"DeepSeek A/B推理不可用，已使用后端规则兜底。\n\n{text_report}",
            "model_used": "backend_rules_fallback",
            "judgment_source": "backend_rules_fallback",
            "data_source": "backend_rules_fallback"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"A/B comparison error: {e}")
        raise HTTPException(status_code=500, detail=f"A/B对比分析失败: {str(e)}")


# ---------- 批量处理端点 ----------

class BatchCausalRequest(BaseModel):
    """批量因果诊断请求"""
    items: List[dict]  # 每个item包含 {"title", "bullets", "description", "asin"}
    analysis_type: str = "diagnosis"  # diagnosis / review_validation


@router.post("/batch/submit")
async def submit_batch_causal_analysis(
    request: BatchCausalRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    📦 提交批量因果分析任务
    
    支持一次提交多个ASIN进行分析，后台异步处理
    分析完成后通过 /batch/status/{batch_id} 获取结果
    """
    try:
        processor = get_batch_processor()

        # 定义处理函数
        async def process_item(item: dict):
            service = CausalDiagnosisService(db)
            result = await service.diagnose_listing_causality(
                title=item.get("title", ""),
                bullets=item.get("bullets", ""),
                description=item.get("description", ""),
                asin=item.get("asin"),
                marketplace=item.get("marketplace", "US"),
                user_id=str(current_user.id),
            )
            return {"asin": item.get("asin"), "result": result}

        batch_id = await processor.submit_batch(
            task_type=f"causal_{request.analysis_type}",
            items=request.items,
            processor_func=process_item,
            user_id=str(current_user.id),
        )

        return {
            "batch_id": batch_id,
            "total_items": len(request.items),
            "status": "pending",
            "message": f"批量任务已提交，共{len(request.items)}个项目"
        }

    except Exception as e:
        logger.error(f"Batch submission error: {e}")
        raise HTTPException(status_code=500, detail=f"批量任务提交失败: {str(e)}")


@router.get("/batch/status/{batch_id}")
async def get_batch_status(batch_id: str):
    """获取批量任务状态和结果"""
    try:
        processor = get_batch_processor()
        status = processor.get_batch_status(batch_id)

        if not status:
            raise HTTPException(status_code=404, detail="批次不存在")

        # 如果完成了，返回完整结果
        if status["has_results"]:
            results = processor.get_batch_results(batch_id)
            return {**status, "results": results}

        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch status error: {e}")
        raise HTTPException(status_code=500, detail=f"获取批次状态失败: {str(e)}")


# ---------- 系统管理端点 ----------

@router.get("/system/stats")
async def get_causal_system_stats(
    db: AsyncSession = Depends(get_db),
):
    """获取因果分析系统的运行统计（缓存命中率等）"""
    try:
        # 缓存统计
        from services.causal_service_base import _cache
        cache_stats = _cache.stats()

        # 批量任务统计
        processor = get_batch_processor()
        pending_count = len(
            [t for t in processor._tasks.values() if t["status"] in ["pending", "running"]]
        )

        return {
            "cache": cache_stats,
            "pending_batches": pending_count,
            "version": "1.0.0",
            "status": "healthy"
        }

    except Exception as e:
        logger.error(f"System stats error: {e}")
        raise HTTPException(status_code=500, detail=f"获取系统统计失败: {str(e)}")


# ---------- Helper Functions ----------

def _estimate_difficulty(gap_type: str) -> float:
    """估计解决某类状态差距的难度"""
    difficulty_map = {
        "anxiety_reduction": 60,      # 需要建立信任，相对困难
        "convenience_improvement": 40, # 功能改进，中等难度
        "pain_elimination": 70,       # 消除身体疼痛通常需要硬件创新
        "social_identity": 80,        # 建立身份认同非常困难
        "status_enhancement": 85,     # 提升社会地位最困难
        "cost_saving": 30,            # 降价/省钱相对容易
        "health_improvement": 75,     # 健康改善需要严谨验证
        "aesthetic_satisfaction": 65, # 审美满足主观性强
    }
    return difficulty_map.get(gap_type, 50.0)
