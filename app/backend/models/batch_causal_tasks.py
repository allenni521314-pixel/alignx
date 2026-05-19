"""
批量因果分析任务模型

持久化存储批量任务的状态和结果，避免重启丢失
"""

from core.database import Base
from sqlalchemy import Column, DateTime, Integer, String, JSON, Float

from datetime import datetime, timezone


class BatchCausalTask(Base):
    """批量因果分析任务"""
    __tablename__ = "batch_causal_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    batch_id = Column(String(50), unique=True, index=True, nullable=False, comment="批次ID")

    # 任务信息
    user_id = Column(String, nullable=True, index=True)
    task_type = Column(String(50), comment="任务类型: diagnosis / review_validation / ab_comparison")
    marketplace = Column(String(2), default="US")

    # 统计信息
    total_items = Column(Integer, default=0, comment="总项目数")
    completed_items = Column(Integer, default=0, comment="已完成数")
    failed_items = Column(Integer, default=0, comment="失败数")

    # 状态
    status = Column(String(20), default="pending", comment="pending / running / completed / failed / partial_success")
    progress_percent = Column(Float, default=0.0)

    # 输入/输出
    input_items = Column(JSON, nullable=True, comment="输入的ASIN列表")
    results = Column(JSON, nullable=True, comment="分析结果列表")
    errors = Column(JSON, nullable=True, comment="错误列表")

    # 时间戳
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # 元数据
    analysis_version = Column(String(20), default="1.0")
    execution_time_seconds = Column(Float, comment="执行耗时（秒）")

    def update_progress(self) -> None:
        """更新进度百分比"""
        if self.total_items > 0:
            self.progress_percent = round(
                (self.completed_items + self.failed_items) / self.total_items * 100, 1
            )

    def is_finished(self) -> bool:
        """判断是否已结束"""
        return self.status in ["completed", "failed", "partial_success"]

    def get_status_summary(self) -> dict:
        """获取状态摘要"""
        return {
            "batch_id": self.batch_id,
            "task_type": self.task_type,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "total": self.total_items,
            "completed": self.completed_items,
            "failed": self.failed_items,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "has_results": self.is_finished() and self.results is not None
        }
