from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.task_execution import ExecutionStatus
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    RUNNING = "running"        # 正在执行
    SCHEDULED = "scheduled"    # 已调度等待执行
    PAUSED = "paused"         # 已暂停
    STOPPED = "stopped"       # 已停止（调度器未运行）
    FAILED = "failed"         # 最近执行失败
    IDLE = "idle"             # 空闲状态
    TIMEOUT = "timeout"       # 执行超时
    MISFIRED = "misfired"     # 错过执行时间


class JobInfo(BaseModel):
    """任务信息"""
    id: str
    name: str
    trigger: str
    next_run_time: Optional[datetime] = None
    pending: bool = False
    status: TaskStatus = TaskStatus.IDLE  # 新增：计算出的综合状态
    
    # 详细信息（可选）
    func: Optional[str] = None
    args: Optional[List[Any]] = None
    kwargs: Optional[Dict[str, Any]] = None
    executor: Optional[str] = None
    max_instances: Optional[int] = None
    misfire_grace_time: Optional[int] = None
    coalesce: Optional[bool] = None


class TaskExecutionResponse(BaseModel):
    """任务执行历史响应"""
    id: int
    job_id: str
    job_name: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class JobStatsResponse(BaseModel):
    """任务统计响应"""
    total_runs: int
    successful_runs: int
    failed_runs: int
    success_rate: float
    avg_duration_seconds: float


class JobCreateRequest(BaseModel):
    """创建任务请求"""
    func: str = Field(..., description="任务函数引用")
    name: str = Field(..., description="任务名称")
    trigger: str = Field(..., description="触发器类型: date/interval/cron")
    trigger_args: Dict[str, Any] = Field(..., description="触发器参数")
    args: Optional[List[Any]] = Field(None, description="函数参数")
    kwargs: Optional[Dict[str, Any]] = Field(None, description="函数关键字参数")
    max_retries: int = Field(0, description="最大重试次数")
    timeout: Optional[int] = Field(None, description="超时时间（秒）")


class JobScheduleUpdate(BaseModel):
    """更新任务调度"""
    trigger: Optional[str] = None
    trigger_args: Optional[Dict[str, Any]] = None