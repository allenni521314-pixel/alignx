from core.database import Base
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text


class ActionSnapshot(Base):
    __tablename__ = "action_snapshots"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=True, index=True)
    module_key = Column(String, nullable=False, index=True)
    module_name = Column(String, nullable=False)
    action_key = Column(String, nullable=False, index=True)
    action_name = Column(String, nullable=False)
    product_id = Column(Integer, nullable=True, index=True)
    asin = Column(String, nullable=True, index=True)
    title = Column(String, nullable=True)
    input_snapshot = Column(Text, nullable=True)
    output_snapshot = Column(Text, nullable=True)
    data_source = Column(String, nullable=True)
    confidence = Column(String, nullable=True)
    ai_called = Column(Boolean, nullable=True, default=False)
    source_record_table = Column(String, nullable=True)
    source_record_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
