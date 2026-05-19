from core.database import Base
from sqlalchemy import Boolean, Column, DateTime, Integer, String


class Scrape_logs(Base):
    __tablename__ = "scrape_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    asin = Column(String, nullable=False)
    marketplace = Column(String, nullable=True)
    scrape_method = Column(String, nullable=False)
    success = Column(Boolean, nullable=False)
    data_source = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)