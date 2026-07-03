from core.database import Base
from sqlalchemy import Column, DateTime, Integer, String


class Consumer_intent_results(Base):
    __tablename__ = "consumer_intent_results"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    keyword = Column(String, nullable=False)
    categories = Column(String, nullable=True)
    summary = Column(String, nullable=True)
    total_keywords = Column(Integer, nullable=True)
    high_freq_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)