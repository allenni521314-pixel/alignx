from core.database import Base
from sqlalchemy import Column, DateTime, Integer, String, Text, func


class ExecutionRecord(Base):
    __tablename__ = "execution_records"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    execution_id = Column(String, nullable=False, index=True)
    record_type = Column(String, nullable=False, index=True)
    issue = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    confidence = Column(String, nullable=True)
    suggested_action = Column(String, nullable=True)
    execution_content = Column(Text, nullable=True)
    execution_time = Column(String, nullable=True)
    execution_target = Column(String, nullable=True, index=True)
    executor = Column(String, nullable=True)
    validation_status = Column(String, nullable=False, index=True)
    validation_cycle = Column(String, nullable=True)
    result = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
