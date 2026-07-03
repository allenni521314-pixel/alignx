from core.database import Base
from sqlalchemy import Column, DateTime, Float, Integer, String


class Asin_analyses(Base):
    __tablename__ = "asin_analyses"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    asin = Column(String, nullable=False)
    marketplace = Column(String, nullable=True)
    product_title = Column(String, nullable=True)
    product_data = Column(String, nullable=True)
    # COSMO Core 8D scores
    score_functionality = Column(Float, nullable=True)
    score_emotional = Column(Float, nullable=True)
    score_scenario = Column(Float, nullable=True)
    score_user_profile = Column(Float, nullable=True)
    score_differentiation = Column(Float, nullable=True)
    score_product_identity = Column(Float, nullable=True)
    score_compatibility = Column(Float, nullable=True)
    score_subjective_properties = Column(Float, nullable=True)
    # Seller Extension 2D scores
    score_market_trend = Column(Float, nullable=True)
    score_risk_elimination = Column(Float, nullable=True)
    analysis_report = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    # 6-Dimension Product Scoring (6维产品判断打分) - 原5维 + 新增价格带维度
    score_5d_total = Column(Float, nullable=True)
    score_5d_demand = Column(Float, nullable=True)      # 1. 需求维度
    score_5d_scenario = Column(Float, nullable=True)    # 2. 场景维度
    score_5d_competition = Column(Float, nullable=True) # 3. 竞争维度
    score_5d_profit = Column(Float, nullable=True)      # 4. 利润维度
    score_5d_trend = Column(Float, nullable=True)       # 5. 趋势维度
    # ==== 新增：第6维 价格带维度 ====
    score_5d_price_tier = Column(Float, nullable=True)  # 6. 价格带维度 (高/中/低分段评分)
    price_tier_category = Column(String, nullable=True)  # high / medium / low - 实际价格带归类
    price_tier_analysis = Column(String, nullable=True)  # 价格带分析JSON
    
    score_5d_detail = Column(String, nullable=True)  # JSON with all 24 sub-item scores (原来20+新增4)
    qualified = Column(Integer, nullable=True)  # 1=qualified (>=70), 0=not qualified