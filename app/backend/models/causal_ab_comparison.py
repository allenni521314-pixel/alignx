"""
因果A/B对比结果模型

持久化存储两个Listing变体的因果对比结果
"""

from core.database import Base
from sqlalchemy import Column, DateTime, Integer, String, JSON, Float

from datetime import datetime, timezone


class CausalABComparison(Base):
    """因果A/B对比结果"""
    __tablename__ = "causal_ab_comparisons"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=True, index=True)

    # 变体标识
    variant_a_label = Column(String(100), default="A")
    variant_b_label = Column(String(100), default="B")

    # 变体信息（快照）
    variant_a_info = Column(JSON, nullable=True)
    variant_b_info = Column(JSON, nullable=True)
    """
    格式: {"title": "...", "asin": "...", "has_reviews": true/false}
    """

    # 对比结果
    winner = Column(String(10), comment="A / B / tie")
    win_margin = Column(Float, comment="获胜优势 0-100")
    confidence_score = Column(Float, comment="预测置信度 0-100")

    # 维度详细对比
    dimension_comparison = Column(JSON, nullable=True)
    """
    格式:
    {
        "state_gap_coverage": {"A": 75.5, "B": 82.0, "delta": 6.5, "winner": "B"},
        "mechanism_clarity": {...},
        "side_effect_transparency": {...},
        "causal_honesty": {...}
    }
    """

    # 优缺点分析
    key_strengths_a = Column(JSON, nullable=True)
    key_strengths_b = Column(JSON, nullable=True)
    key_weaknesses_a = Column(JSON, nullable=True)
    key_weaknesses_b = Column(JSON, nullable=True)

    # 转化率预测
    predicted_conversion_impact = Column(JSON, nullable=True)
    """
    格式:
    {
        "variant_a_impact_pct": 8.5,
        "variant_b_impact_pct": 12.3,
        "delta_pct": 3.8
    }
    """

    # 优化建议
    actionable_recommendations = Column(JSON, nullable=True)

    # 文本报告
    text_report = Column(String, nullable=True)

    # 完整的诊断快照（可选，用于追溯）
    full_diagnosis_a = Column(JSON, nullable=True)

    # 元数据
    analysis_version = Column(String(20), default="1.0")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def get_summary(self) -> dict:
        """获取摘要信息"""
        return {
            "id": self.id,
            "variant_a": self.variant_a_label,
            "variant_b": self.variant_b_label,
            "winner": self.winner,
            "win_margin": self.win_margin,
            "confidence_score": self.confidence_score,
            "predicted_impact_a": self.predicted_conversion_impact.get("delta_pct", 0) if self.predicted_conversion_impact else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
