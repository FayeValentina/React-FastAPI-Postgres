from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, DateTime, func, Integer, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from enum import Enum as PyEnum

from app.db.base_class import Base

class ScheduleEventType(str, PyEnum):
    """调度事件类型枚举"""
    EXECUTED = "executed"     # 成功执行
    ERROR = "error"           # 执行错误
    MISSED = "missed"         # 错过执行
    SCHEDULED = "scheduled"   # 已调度
    PAUSED = "paused"        # 已暂停
    RESUMED = "resumed"      # 已恢复

class ScheduleEvent(Base):
    """调度事件记录表"""
    __tablename__ = "schedule_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    job_name: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[ScheduleEventType] = mapped_column(Enum(ScheduleEventType))
    
    # 事件详情
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
