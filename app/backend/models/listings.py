from core.database import Base
from sqlalchemy import Column, DateTime, Float, Integer, String


class Listings(Base):
    __tablename__ = "listings"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    asin = Column(String, nullable=False)
    title = Column(String, nullable=False)
    cosmo_score = Column(Float, nullable=True)
    current_rank = Column(Integer, nullable=True)
    sessions_30d = Column(Integer, nullable=True)
    conversion_rate = Column(Float, nullable=True)
    status = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)