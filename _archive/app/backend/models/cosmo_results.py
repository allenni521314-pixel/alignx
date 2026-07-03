from core.database import Base
from sqlalchemy import Column, DateTime, Integer, String


class Cosmo_results(Base):
    __tablename__ = "cosmo_results"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    product_id = Column(Integer, nullable=False)
    model_name = Column(String, nullable=False)
    optimized_title = Column(String, nullable=True)
    optimized_bullets = Column(String, nullable=True)
    optimized_keywords = Column(String, nullable=True)
    analysis_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)