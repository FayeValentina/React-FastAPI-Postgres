from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, DateTime, func, Integer, Text, Enum, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base_class import Base
from app.core.tasks.registry import ExecutionStatus
if TYPE_CHECKING:
    from .task_config import TaskConfig


class TaskExecution(Base):
    """任务执行历史表"""
    __tablename__ = "task_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # 关联字段
    config_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("task_configs.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id: Mapped[str] = mapped_column(String, nullable=False, index=True)  # TaskIQ任务ID，通常是UUID格式
    
    # 执行信息
    status: Mapped[ExecutionStatus] = mapped_column(Enum(ExecutionStatus))
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Numeric(10, 3))
    
    # 执行结果
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # 关联关系
    task_config: Mapped["TaskConfig"] = relationship("TaskConfig", back_populates="task_executions")
    
    def __repr__(self) -> str:
        return f"<TaskExecution(id={self.id}, config_id={self.config_id}, status={self.status})>"