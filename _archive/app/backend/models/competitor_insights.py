from core.database import Base
from sqlalchemy import Column, DateTime, Integer, String


class Competitor_insights(Base):
    __tablename__ = "competitor_insights"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    product_id = Column(Integer, nullable=False)
    competitor_asin = Column(String, nullable=False)
    strengths = Column(String, nullable=True)
    weaknesses = Column(String, nullable=True)
    gaps = Column(String, nullable=True)
    suggestions = Column(String, nullable=True)
    radar_scores = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)