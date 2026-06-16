from core.database import Base
from sqlalchemy import Column, DateTime, Integer, String, Text, func


class AdValidationResult(Base):
    __tablename__ = "ad_validation_results"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    product_id = Column(Integer, nullable=True, index=True)
    asin = Column(String, nullable=True, index=True)
    verification_id = Column(String, nullable=False, index=True)
    execution_id = Column(String, nullable=True, index=True)
    original_issue = Column(Text, nullable=True)
    original_hypothesis = Column(Text, nullable=True)
    execution_action = Column(Text, nullable=True)
    validation_period = Column(String, nullable=True)
    metrics_change = Column(Text, nullable=False)
    conclusion = Column(String, nullable=False, index=True)
    reason_explanation = Column(Text, nullable=True)
    next_suggestion = Column(Text, nullable=True)
    suggested_action = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
