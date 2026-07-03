from core.database import Base
from sqlalchemy import Column, DateTime, Integer, String


class Fetch_history(Base):
    __tablename__ = "fetch_history"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    asin = Column(String, nullable=False)
    marketplace = Column(String, nullable=False)
    status = Column(String, nullable=False)
    data_snapshot = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)