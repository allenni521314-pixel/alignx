from core.database import Base
from sqlalchemy import Column, DateTime, Float, Integer, String


class Products(Base):
    __tablename__ = "products"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    asin = Column(String, nullable=False)
    title = Column(String, nullable=False)
    bullet_points = Column(String, nullable=True)
    a_plus_content = Column(String, nullable=True)
    search_keywords = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    category = Column(String, nullable=True)
    lifecycle_stage = Column(String, nullable=True)
    optimization_round = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)