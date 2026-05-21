from core.database import Base
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text


class AmazonRule(Base):
    __tablename__ = "amazon_rules"
    __table_args__ = {"extend_existing": True}

    pk = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    id = Column(String, nullable=False, unique=True, index=True)
    marketplace = Column(Text, nullable=False, default="[]")
    module = Column(String, nullable=False, index=True)
    rule_type = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False)
    trigger_type = Column(String, nullable=False, index=True)
    trigger_patterns = Column(Text, nullable=False, default="[]")
    allowed_when = Column(Text, nullable=True)
    forbidden_when = Column(Text, nullable=True)
    risk_score = Column(Integer, nullable=False, default=0)
    message_cn = Column(Text, nullable=False)
    message_en = Column(Text, nullable=True)
    suggestion_cn = Column(Text, nullable=False)
    suggestion_en = Column(Text, nullable=True)
    source_policy = Column(String, nullable=False)
    source_url = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    version = Column(String, nullable=False, default="1.0.0")
    updated_at = Column(DateTime(timezone=True), nullable=True)
