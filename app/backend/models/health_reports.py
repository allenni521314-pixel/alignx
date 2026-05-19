from core.database import Base
from sqlalchemy import Column, DateTime, Integer, String


class Health_reports(Base):
    __tablename__ = "health_reports"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    product_id = Column(Integer, nullable=False)
    title_score = Column(Integer, nullable=True)
    keyword_score = Column(Integer, nullable=True)
    bullet_score = Column(Integer, nullable=True)
    aplus_score = Column(Integer, nullable=True)
    review_score = Column(Integer, nullable=True)
    total_score = Column(Integer, nullable=True)
    grade = Column(String, nullable=True)
    suggestions = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)