from core.database import Base
from sqlalchemy import Column, DateTime, Float, Integer, String


class OptimizationTimeline(Base):
    __tablename__ = "optimization_timeline"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    product_id = Column(Integer, nullable=False)
    step_name = Column(String, nullable=False)
    action_timestamp = Column(String, nullable=True)
    listing_score = Column(Integer, nullable=True, default=0)
    score_details = Column(String, nullable=True, default="{}")
    optimization_round = Column(Integer, nullable=True, default=1)
    created_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
