from datetime import datetime, timezone

from core.database import Base
from sqlalchemy import Column, DateTime, Float, Integer, JSON, String


class DiagnosisTask(Base):
    """Persistent background task for long-running ASIN and Listing diagnosis."""

    __tablename__ = "diagnosis_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    task_id = Column(String(80), unique=True, index=True, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    task_type = Column(String(40), nullable=False, index=True)
    status = Column(String(24), nullable=False, default="pending", index=True)
    progress_percent = Column(Float, nullable=True, default=0.0)
    title = Column(String, nullable=True)
    asin = Column(String, nullable=True, index=True)
    marketplace = Column(String(12), nullable=True)
    input_payload = Column(JSON, nullable=True)
    result_payload = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)
    source_record_table = Column(String(80), nullable=True)
    source_record_id = Column(String(80), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=True)
