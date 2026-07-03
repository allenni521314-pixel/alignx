from datetime import datetime, timezone

from core.database import Base
from sqlalchemy import Column, DateTime, Float, Integer, String


class JudgmentFeedbackRound(Base):
    __tablename__ = "judgment_feedback_rounds"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    asin = Column(String(20), nullable=True, index=True)
    marketplace = Column(String(10), nullable=True, default="US")
    listing_diagnosis_id = Column(Integer, nullable=True, index=True)
    product_id = Column(Integer, nullable=True, index=True)
    optimization_round = Column(Integer, nullable=False, default=1)
    stage = Column(String(40), nullable=False, default="ad_validation")
    status = Column(String(40), nullable=False, default="planned")

    diagnosis_issue = Column(String, nullable=True)
    judgment_basis = Column(String, nullable=True)
    suggested_action = Column(String, nullable=True)
    ad_validation_plan = Column(String, nullable=True)
    before_snapshot = Column(String, nullable=True)
    after_snapshot = Column(String, nullable=True)
    ad_result = Column(String, nullable=True)

    hit_status = Column(String(40), nullable=True)
    miss_reason = Column(String, nullable=True)
    next_iteration = Column(String, nullable=True)
    confidence_before = Column(Float, nullable=True)
    confidence_after = Column(Float, nullable=True)

    executed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))
