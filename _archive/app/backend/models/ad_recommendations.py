from core.database import Base
from sqlalchemy import Column, DateTime, Integer, String


class Ad_recommendations(Base):
    __tablename__ = "ad_recommendations"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    product_id = Column(Integer, nullable=False)
    recommendation_type = Column(String, nullable=False)
    content = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)