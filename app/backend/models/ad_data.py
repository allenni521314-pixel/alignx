from core.database import Base
from sqlalchemy import Column, DateTime, Float, Integer, String


class Ad_data(Base):
    __tablename__ = "ad_data"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    product_id = Column(Integer, nullable=False)
    ad_group_name = Column(String, nullable=False)
    keyword = Column(String, nullable=False)
    match_type = Column(String, nullable=True)
    impressions = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    spend = Column(Float, nullable=True)
    orders = Column(Integer, nullable=True)
    sales = Column(Float, nullable=True)
    date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)