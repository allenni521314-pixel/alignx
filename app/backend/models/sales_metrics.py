from core.database import Base
from sqlalchemy import Column, Date, Float, Integer, String


class Sales_metrics(Base):
    __tablename__ = "sales_metrics"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    revenue = Column(Float, nullable=False)
    orders = Column(Integer, nullable=False)
    acos = Column(Float, nullable=True)
    profit_margin = Column(Float, nullable=True)
    sessions = Column(Integer, nullable=True)
    conversion_rate = Column(Float, nullable=True)