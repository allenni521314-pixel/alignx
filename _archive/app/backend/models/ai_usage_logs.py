from models.base import BaseModel
from sqlalchemy import Column, Float, Integer, String


class AIUsageLog(BaseModel):
    __tablename__ = "ai_usage_logs"

    provider = Column(String(80), nullable=False, default="")
    model = Column(String(160), nullable=False, default="")
    module = Column(String(120), nullable=False, default="")
    endpoint = Column(String(120), nullable=False, default="")
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    estimated_cost_cny = Column(Float, nullable=False, default=0.0)
    input_cost_per_1m_cny = Column(Float, nullable=False, default=0.0)
    output_cost_per_1m_cny = Column(Float, nullable=False, default=0.0)
    user_id = Column(String(255), nullable=True)
