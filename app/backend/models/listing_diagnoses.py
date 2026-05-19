from core.database import Base
from sqlalchemy import Column, DateTime, Float, Integer, String


class Listing_diagnoses(Base):
    __tablename__ = "listing_diagnoses"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    listing_title = Column(String, nullable=False)
    marketplace = Column(String, nullable=True)
    input_data = Column(String, nullable=True)
    # COSMO Core 8D scores
    score_function_expression = Column(Float, nullable=True)
    score_scenario_expression = Column(Float, nullable=True)
    score_identity_fit = Column(Float, nullable=True)
    score_psychology_benefit = Column(Float, nullable=True)
    score_risk_elimination = Column(Float, nullable=True)
    score_product_identity = Column(Float, nullable=True)
    score_compatibility = Column(Float, nullable=True)
    score_subjective_properties = Column(Float, nullable=True)
    # Seller Extension 2D scores
    score_differentiation = Column(Float, nullable=True)
    score_market_trend = Column(Float, nullable=True)
    # ========== 新增：因果维度 (P0阶段) ==========
    # 因果维度1: 状态差距覆盖度 - 商品解决了哪些人类状态差距，解决到什么程度
    score_causal_state_gap_coverage = Column(Float, nullable=True)
    # 因果维度2: 因果机制清晰度 - 商品解决问题的作用机制是否清晰可信
    score_causal_mechanism_clarity = Column(Float, nullable=True)
    # 因果维度3: 副作用透明度 - 是否诚实告知产品可能带来的负面代价
    score_causal_side_effect_transparency = Column(Float, nullable=True)
    # ========== 新增：因果诊断报告JSON字段 ==========
    causal_diagnosis_report = Column(String, nullable=True)
    diagnosis_report = Column(String, nullable=True)
    keyword_report = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)