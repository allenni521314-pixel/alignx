from core.database import Base
from sqlalchemy import Column, DateTime, Float, Integer, String


class Ad_campaigns(Base):
    __tablename__ = "ad_campaigns"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    campaign_name = Column(String, nullable=False)
    campaign_type = Column(String, nullable=True)
    daily_budget = Column(Float, nullable=True)
    spend = Column(Float, nullable=True)
    sales = Column(Float, nullable=True)
    acos = Column(Float, nullable=True)
    impressions = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    ctr = Column(Float, nullable=True)
    status = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)