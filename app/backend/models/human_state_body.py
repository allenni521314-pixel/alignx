"""
人类状态体 (Human State Body) - 因果电商系统的核心基石

核心哲学：
- 商品不是"有属性的物品"，而是"状态转移算子"
- 它将人类从不满意的状态 S1 转移到满意的状态 S2
- 属性只是这个转移过程的"作用参数"

状态差距 = 期望状态 - 当前状态 = 需求的本质
"""

from core.database import Base
from sqlalchemy import Column, DateTime, Integer, String, JSON, Float, ForeignKey
from sqlalchemy.orm import relationship


class HumanStateBody(Base):
    """人类状态体 - 记录商品对人类状态的因果影响"""
    __tablename__ = "human_state_body"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=True)  # 关联用户，如果是通用分析则为空
    
    # 关联信息
    asin = Column(String(10), nullable=True, index=True)
    marketplace = Column(String(2), default="US")
    listing_diagnosis_id = Column(Integer, nullable=True)  # 关联Listing诊断记录
    product_id = Column(Integer, nullable=True)
    
    # ========================================
    # 核心：状态差距向量 (State Gap Vector)
    # ========================================
    state_gaps = Column(JSON, nullable=True)
    """
    格式示例（手机壳）：
    {
        "anxiety_reduction": {                    # 差距类型
            "gap_name": "手机摔坏的焦虑",          # 差距的人类语言描述
            "gap_strength": 0.85,                 # 这个差距在目标用户中的强烈程度 0-1
            "coverage_score": 0.72,               # 当前Listing覆盖并解决这个差距的程度 0-1
            "mechanism": "通过军工级防摔承诺消除摔机焦虑",  # 解决方案机制描述
            "evidence_provided": true,            # 是否提供了数据/证据支撑
            "evidence_strength": 0.80,            # 证据的可信度 0-1
            "competitor_coverage_avg": 0.55       # 竞品平均覆盖度（用于发现机会）
        },
        "convenience_improvement": {
            "gap_name": "充电等待的不便",
            "gap_strength": 0.68,
            "coverage_score": 0.55,
            "mechanism": "通过支持无线充电提升便利性",
            "evidence_provided": false,
            "evidence_strength": 0.30
        }
    }
    """
    
    # ========================================
    # 因果机制库 (Causal Mechanism Library)
    # ========================================
    causal_mechanisms = Column(JSON, nullable=True)
    """
    格式示例：
    [
        {
            "mechanism_id": "mech_impact_protection_001",
            "gap_type": "anxiety_reduction",
            "causal_chain": [
                "使用军工级TPU+PC材质",
                "→ 四角气囊设计",
                "→ 吸收90%跌落冲击力",
                "→ 屏幕和背板完好率99%",
                "→ 用户不再担心手机摔坏"
            ],
            "effect_strength": 0.85,           # 机制效果强度 0-1
            "confidence": 0.92,                # 置信度
            "evidence": "1.5米跌落测试报告",    # 支撑证据
            "is_well_defined": true            # 机制是否清晰可解释
        }
    ]
    """
    
    # ========================================
    # 副作用检测 (Side Effects)
    # ========================================
    side_effects = Column(JSON, nullable=True)
    """
    格式示例：
    [
        {
            "effect": "手机厚度增加35%",
            "effect_type": "physical_experience",  # 体验类型
            "effect_strength": 0.35,               # 副作用强度
            "likelihood": 0.90,                    # 发生概率
            "severity": 0.40,                      # 严重程度
            "mentioned_in_listing": false,         # Listing中是否提及
            "transparency_score": 25,              # 透明度评分（提及=100分，没提及按严重程度扣分）
            "user_complaint_rate": 0.12            # 评论中提到这个问题的比例
        }
    ]
    """
    
    # ========================================
    # 人群异质性 (Population Heterogeneity)
    # ========================================
    population_heterogeneity = Column(JSON, nullable=True)
    """
    格式示例：
    {
        "segments": [
            {
                "segment_name": "经常出差的商务人士",
                "size_estimate": 0.35,              # 占目标用户比例
                "gap_priorities": ["anxiety_reduction", "battery_life"],
                "effect_modifier": 1.2,             # 效果倍率
                "side_effect_tolerance": {
                    "bulkiness": 0.80,              # 对厚重的容忍度高
                    "price_premium": 0.60
                }
            },
            {
                "segment_name": "追求时尚的年轻女性",
                "size_estimate": 0.25,
                "gap_priorities": ["aesthetic_identity", "portability"],
                "effect_modifier": 0.7,
                "side_effect_tolerance": {
                    "bulkiness": 0.20,              # 对厚重的容忍度低
                    "price_premium": 0.80
                }
            }
        ]
    }
    """
    
    # ========================================
    # 整体因果评分
    # ========================================
    overall_causal_score = Column(Float, nullable=True)      # 整体因果质量分
    state_gap_coverage_score = Column(Float, nullable=True)  # 状态差距覆盖分
    mechanism_clarity_score = Column(Float, nullable=True)    # 因果机制清晰度分
    side_effect_transparency_score = Column(Float, nullable=True)  # 副作用透明度分
    
    # ========================================
    # 元数据
    # ========================================
    source_type = Column(String(50), nullable=True)  # listing_analysis / review_mining / manual
    confidence_level = Column(Float, nullable=True)  # 分析置信度
    analysis_version = Column(String(20), default="1.0")  # 因果分析器版本
    
    created_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    
    # 关联关系
    # listing_diagnosis = relationship("Listing_diagnoses", backref="human_state_body")
