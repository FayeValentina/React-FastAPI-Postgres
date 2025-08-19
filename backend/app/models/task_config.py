from datetime import datetime
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from sqlalchemy import String, DateTime, func, Integer, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base_class import Base
from app.constant.task_registry import ConfigStatus, SchedulerType

if TYPE_CHECKING:
    from .task_execution import TaskExecution


class TaskConfig(Base):
    """任务配置表 - 存储所有类型任务的配置信息"""
    __tablename__ = "task_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # 基本信息
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # 任务类型和状态
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scheduler_type: Mapped[SchedulerType] = mapped_column(Enum(SchedulerType), nullable=False)
    status: Mapped[ConfigStatus] = mapped_column(Enum(ConfigStatus), nullable=False, default=ConfigStatus.ACTIVE, index=True)
    
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
        return f"<TaskConfig(id={self.id}, name='{self.name}', type={self.task_type}, status={self.status})>"
    
    @property
    def is_active(self) -> bool:
        """判断任务是否为活跃状态"""
        return self.status == ConfigStatus.ACTIVE
    
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