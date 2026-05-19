from core.database import Base
from sqlalchemy import Column, DateTime, Float, Integer, String, Text


class Prelaunch_test_results(Base):
    __tablename__ = "prelaunch_test_results"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id = Column(String, nullable=False)
    title = Column(String(500), nullable=True)
    keywords = Column(Text, nullable=True)
    bullet_points = Column(Text, nullable=True)
    a_plus_desc = Column(Text, nullable=True)
    overall_score = Column(Float, nullable=True)
    score_title_keywords = Column(Float, nullable=True)
    score_main_image = Column(Float, nullable=True)
    score_a_plus = Column(Float, nullable=True)
    score_bullet_points = Column(Float, nullable=True)
    overall_summary = Column(Text, nullable=True)
    cosmo_alignment = Column(Text, nullable=True)
    rufus_alignment = Column(Text, nullable=True)
    full_report = Column(Text, nullable=True)  # JSON string of full ScoringResult
    has_images = Column(Integer, nullable=True, default=0)  # 0=no, 1=main only, 2=a+ only, 3=both
    created_at = Column(DateTime(timezone=True), nullable=True)