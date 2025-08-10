from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.task_execution import ExecutionStatus
from enum import Enum


class TaskExecutionCreate(BaseModel):
    """创建任务执行记录"""
    task_config_id: int = Field(..., description="任务配置ID")
    job_id: str = Field(..., description="任务执行ID")
    job_name: str = Field(..., description="任务名称")
    status: ExecutionStatus = Field(..., description="执行状态")
    started_at: str = Field(..., description="开始时间")
    completed_at: Optional[str] = Field(None, description="完成时间")
    duration_seconds: Optional[float] = Field(None, description="执行时长(秒)")
    result: Optional[Dict[str, Any]] = Field(None, description="执行结果")
    error_message: Optional[str] = Field(None, description="错误消息")
    error_traceback: Optional[str] = Field(None, description="错误堆栈")


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


class JobExecutionSummary(BaseModel):
    """任务执行摘要"""
    total_runs: int = Field(..., description="总执行次数")
    successful_runs: int = Field(..., description="成功执行次数")
    failed_runs: int = Field(..., description="失败执行次数")
    success_rate: float = Field(..., description="成功率（百分比）")
    avg_duration: float = Field(..., description="平均执行时间（秒）")
    last_run: Optional[str] = Field(None, description="最后执行时间")
    last_status: Optional[str] = Field(None, description="最后执行状态")
    last_error: Optional[str] = Field(None, description="最后错误信息")


class ScheduleEventInfo(BaseModel):
    """调度事件信息"""
    event_type: str = Field(..., description="事件类型")
    created_at: str = Field(..., description="创建时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    result: Optional[Dict[str, Any]] = Field(None, description="执行结果")


class EnhancedJobInfo(BaseModel):
    """增强的任务信息"""
    schedule_id: str = Field(..., description="调度任务ID")
    name: str = Field(..., description="任务名称")
    next_run_time: Optional[str] = Field(None, description="下次运行时间")
    trigger: str = Field(..., description="触发器配置")
    config: Optional[Dict[str, Any]] = Field(None, description="任务配置")
    pending: bool = Field(..., description="是否等待中")
    computed_status: TaskStatus = Field(..., description="计算的任务状态")
    execution_summary: JobExecutionSummary = Field(..., description="执行摘要")


class JobDetailResponse(BaseModel):
    """任务详情响应"""
    job_info: Dict[str, Any] = Field(..., description="基本任务信息")
    computed_status: TaskStatus = Field(..., description="计算的任务状态")
    execution_summary: JobExecutionSummary = Field(..., description="执行摘要")
    recent_events: List[ScheduleEventInfo] = Field(..., description="最近事件")


class JobInfo(BaseModel):
    """任务信息"""
    id: str
    name: str
    trigger: str
    next_run_time: Optional[datetime] = None
    pending: bool = False
    status: TaskStatus = TaskStatus.IDLE  # 计算出的综合状态
    
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

    model_config = ConfigDict(from_attributes=True)


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


class SystemStatusResponse(BaseModel):
    """系统状态响应"""
    scheduler: Dict[str, Any] = Field(..., description="调度器状态")
    celery: Dict[str, Any] = Field(..., description="Celery状态")
    queues: Dict[str, Any] = Field(..., description="队列状态")
    timestamp: str = Field(..., description="状态时间戳")

