from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, DateTime, func, Integer, Text, Enum, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from enum import Enum as PyEnum

from app.db.base_class import Base


class ExecutionStatus(str, PyEnum):
    """执行状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RUNNING = "running"


class TaskExecution(Base):
    """任务执行历史表"""
    __tablename__ = "task_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    job_name: Mapped[str] = mapped_column(String, nullable=False)
    
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