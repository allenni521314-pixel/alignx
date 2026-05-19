from core.database import Base
from sqlalchemy import Column, Float, Integer, String


class Keywords(Base):
    __tablename__ = "keywords"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    keyword = Column(String, nullable=False)
    match_type = Column(String, nullable=True)
    search_volume = Column(Integer, nullable=True)
    bid = Column(Float, nullable=True)
    suggested_bid = Column(Float, nullable=True)
    acos = Column(Float, nullable=True)
    conversions = Column(Integer, nullable=True)
    relevance_score = Column(Float, nullable=True)
    campaign_id = Column(Integer, nullable=True)