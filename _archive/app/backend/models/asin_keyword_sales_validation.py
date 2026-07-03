from core.database import Base
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text


class AsinKeywordRankSnapshot(Base):
    __tablename__ = "asin_keyword_rank_snapshots"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, default="US", index=True)
    keyword = Column(String, nullable=False, index=True)
    search_page = Column(Integer, nullable=True)
    organic_position = Column(Integer, nullable=True)
    sponsored_position = Column(Integer, nullable=True)
    overall_position = Column(Integer, nullable=True)
    is_organic = Column(Boolean, nullable=False, default=False)
    is_sponsored = Column(Boolean, nullable=False, default=False)
    rank_type = Column(String, nullable=False, default="estimated")
    crawl_time = Column(DateTime(timezone=True), nullable=False)


class AsinKeywordSalesValidationReport(Base):
    __tablename__ = "asin_keyword_sales_validation_reports"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    asin = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, default="US", index=True)
    category = Column(String, nullable=True)
    days_range = Column(Integer, nullable=False, default=30)
    keyword_sales_score = Column(Float, nullable=False, default=0)
    traffic_quality_level = Column(String, nullable=False)
    sales_source_judgment = Column(String, nullable=False)
    organic_rank_strength = Column(Float, nullable=False, default=0)
    ad_dependency_risk = Column(Float, nullable=False, default=0)
    product_snapshot = Column(Text, nullable=True)
    keyword_rank_summary = Column(Text, nullable=True)
    suspicious_signals = Column(Text, nullable=True)
    opportunity_keywords = Column(Text, nullable=True)
    risk_keywords = Column(Text, nullable=True)
    final_recommendation = Column(Text, nullable=True)
    report_payload = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class AsinKeywordIntentScore(Base):
    __tablename__ = "asin_keyword_intent_scores"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    keyword = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, default="US", index=True)
    category = Column(String, nullable=True)
    estimated_search_volume = Column(Integer, nullable=True)
    estimated_cpc = Column(Float, nullable=True)
    competition_level = Column(String, nullable=True)
    relevance_score = Column(Float, nullable=False, default=0)
    intent_type = Column(String, nullable=True)
    conversion_intent_score = Column(Float, nullable=False, default=0)
    crawl_time = Column(DateTime(timezone=True), nullable=False)
