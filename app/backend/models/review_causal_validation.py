"""
评论因果验证结果模型

持久化存储商家宣称与用户实际体验的对比验证结果
"""

from core.database import Base
from sqlalchemy import Column, DateTime, Integer, String, JSON, Float, Boolean

from datetime import datetime, timezone


class ReviewCausalValidation(Base):
    """评论因果验证结果"""
    __tablename__ = "review_causal_validations"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=True, index=True)

    # 关联信息
    asin = Column(String(10), nullable=True, index=True)
    marketplace = Column(String(2), default="US")
    listing_title = Column(String(500))

    # 核心验证结果
    overall_honesty_score = Column(Float, nullable=True, comment="整体因果诚信度得分 0-100")
    total_claims_analyzed = Column(Integer, default=0, comment="分析的宣称总数")
    total_reviews_used = Column(Integer, default=0, comment="使用的评论数量")

    # 详细的宣称验证结果
    claims_validation = Column(JSON, nullable=True)
    """
    格式:
    [
        {
            "claim_text": "宣称原文",
            "gap_type": "anxiety_reduction",
            "claimed_effect": 85,
            "actual_effect": 65,
            "effect_gap": 20,
            "confidence": 80,
            "verification_status": "verified / partially_verified / refuted / insufficient_data",
            "supporting_quotes": ["评论1", "评论2"]
        }
    ]
    """

    # 发现的未披露效应
    undisclosed_effects = Column(JSON, nullable=True)
    """
    格式:
    [
        {
            "effect": "增加手机厚度",
            "effect_type": "negative_side_effect / unexpected_benefit",
            "prevalence_score": 75,
            "sentiment_score": -60,
            "mentioned_in_listing": false,
            "example_quotes": ["评论1", "评论2"]
        }
    ]
    """

    # 优化建议
    optimization_suggestions = Column(JSON, nullable=True)
    """
    格式: ["建议1", "建议2", ...]
    """

    # 统计摘要
    validation_summary = Column(JSON, nullable=True)
    """
    格式:
    {
        "verified_count": 5,
        "partially_verified_count": 3,
        "refuted_count": 1,
        "insufficient_data_count": 0,
        "negative_side_effects_count": 2,
        "unexpected_benefits_count": 1
    }
    """

    # 元数据
    confidence_score = Column(Float, nullable=True, comment="验证置信度")
    analysis_version = Column(String(20), default="1.0")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    def get_summary(self) -> dict:
        """获取摘要信息"""
        return {
            "id": self.id,
            "asin": self.asin,
            "listing_title": self.listing_title[:100] + "..." if self.listing_title and len(self.listing_title) > 100 else self.listing_title,
            "overall_honesty_score": self.overall_honesty_score,
            "total_claims": self.total_claims_analyzed,
            "total_reviews": self.total_reviews_used,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
