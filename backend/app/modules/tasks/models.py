from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import ForeignKey, Numeric, String, DateTime, func, Integer, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.infrastructure.database.postgres_base import Base
from app.infrastructure.tasks.task_registry_decorators import SchedulerType
from app.infrastructure.cache.cache_serializer import register_sqlalchemy_model

@register_sqlalchemy_model
class TaskConfig(Base):
    """任务配置表 - 存储所有类型任务的配置信息"""
    __tablename__ = "task_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # 基本信息
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # 任务类型和调度类型
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scheduler_type: Mapped[SchedulerType] = mapped_column(Enum(SchedulerType), nullable=False)
    
    # 配置参数 (使用JSON存储以支持不同任务类型的不同参数)
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default={})
    schedule_config: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default={})
    
    # 执行控制
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timeout_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)  # 1-10
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())
    
    # 关联关系
    task_executions: Mapped[List["TaskExecution"]] = relationship(
        "TaskExecution", 
        back_populates="task_config",
        cascade="all, delete-orphan",
        lazy="select"
    )
    
    def __repr__(self) -> str:
        return f"<TaskConfig(id={self.id}, name='{self.name}', type={self.task_type})>"
    
    @property
    def is_scheduled(self) -> bool:
        """判断任务是否为调度任务"""
        return self.scheduler_type != SchedulerType.MANUAL
    
    def get_parameter(self, key: str, default=None):
        """获取参数值"""
        return self.parameters.get(key, default)
    
    def get_schedule_config(self, key: str, default=None):
        """获取调度配置值"""
        return self.schedule_config.get(key, default)
    
    def update_parameters(self, **kwargs):
        """更新参数"""
        if self.parameters is None:
            self.parameters = {}
        self.parameters.update(kwargs)
    
    def update_schedule_config(self, **kwargs):
        """更新调度配置"""
        if self.schedule_config is None:
            self.schedule_config = {}
        self.schedule_config.update(kwargs)

@register_sqlalchemy_model
class TaskExecution(Base):
    """任务执行历史表"""
    __tablename__ = "task_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # 关联字段
    config_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("task_configs.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id: Mapped[str] = mapped_column(String, nullable=False, index=True)  # TaskIQ任务ID，通常是UUID格式
    
    # 执行信息
    is_success: Mapped[bool] = mapped_column(nullable=False)
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
        return f"<TaskExecution(id={self.id}, config_id={self.config_id}, success={self.is_success})>"