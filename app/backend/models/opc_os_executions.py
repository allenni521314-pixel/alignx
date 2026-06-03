from core.database import Base
from sqlalchemy import Column, DateTime, Integer, String, Text, func


class OPCOSExecutionRecord(Base):
    __tablename__ = "opc_os_executions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    object_type = Column(String, nullable=False, index=True)
    object_id = Column(String, nullable=False, index=True)
    opportunity_id = Column(String, nullable=True, index=True)
    source_module = Column(String, nullable=True, index=True)
    source_record_id = Column(Integer, nullable=True, index=True)
    asin = Column(String, nullable=True, index=True)
    title = Column(String, nullable=True)
    status = Column(String, nullable=True, index=True)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())