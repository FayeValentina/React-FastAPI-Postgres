from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime

class SystemStatusResponse(BaseModel):
    """系统状态响应"""
    broker_connected: bool = Field(..., description="broker运行状态")
    scheduler_running: bool = Field(..., description="调度器运行状态")
    total_configs: int = Field(..., description="总配置数")
    active_configs: int = Field(..., description="总活跃配置数")
    total_scheduled_jobs: int = Field(..., description="总调度任务数")
    total_active_tasks: int = Field(..., description="总活跃任务数")
    timestamp: str = Field(..., description="状态时间戳")
    scheduler: Dict[str, Any] = Field(..., description="调度器状态")
    worker: Dict[str, Any] = Field(..., description="worker状态")
    queues: Dict[str, Any] = Field(..., description="队列状态")


class TaskExecutionResult(BaseModel):
    """任务执行结果响应"""
    task_id: str = Field(..., description="任务ID")
    config_id: Optional[int] = Field(None, description="配置ID")
    task_type: Optional[str] = Field(None, description="任务类型")
    status: str = Field(..., description="执行状态")
    queue: Optional[str] = Field(None, description="队列名称")
    message: Optional[str] = Field(None, description="结果消息")


class TaskRevokeResponse(BaseModel):
    """任务撤销响应"""
    task_id: str = Field(..., description="任务ID")
    revoked: bool = Field(..., description="是否成功撤销")
    message: str = Field(..., description="操作结果")


class QueueStatsResponse(BaseModel):
    """队列统计响应"""
    queues: Dict[str, Dict[str, Any]] = Field(..., description="队列统计信息")
    total_tasks: int = Field(..., description="总任务数")

class TaskTypeDetail(BaseModel):
    """任务类型的详细信息"""
    name: str = Field(..., description="任务类型的名称 (e.g., 'cleanup_tokens')")
    description: str = Field(..., description="任务类型的描述")
    implemented: bool = Field(..., description="该任务类型是否已实现")

class EnumValuesResponse(BaseModel):
    """枚举值响应"""
    task_types: List[TaskTypeDetail] = Field(..., description="任务类型列表，包含详细信息")
    task_statuses: List[str] = Field(..., description="任务状态列表")
    scheduler_types: List[str] = Field(..., description="调度器类型列表")

class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    result: Optional[Dict[str, Any]] = Field(None, description="任务结果")
    traceback: Optional[str] = Field(None, description="错误追踪")
    execution_time: Optional[datetime] = Field(None, description = "执行时间")
    started_at: Optional[datetime] = Field(None, description = "开始时间")
    completed_at: Optional[datetime] =Field(None, description = "完成时间")


class ActiveTaskInfo(BaseModel):
    """活跃任务信息"""
    task_id: str = Field(..., description="任务ID")
    config_id: int = Field(..., description="配置ID")
    name: str = Field(..., description="任务名称")
    parameters: Dict[str, Any] = Field(..., description="任务关键字参数")
    status: str = Field(..., description="任务状态")
    started_at: datetime = Field(..., description = "启动时间")
    task_type: str = Field(..., description = "任务类型")
    queue: Optional[str] = Field(None, description="队列名称")


class ScheduledJobInfo(BaseModel):
    """调度任务信息"""
    id: str = Field(..., description="任务ID")
    name: str = Field(..., description="任务名称")
    next_run_time: Optional[str] = Field(None, description="下次运行时间")
    trigger: str = Field(..., description="触发器信息")
    pending: bool = Field(..., description="是否等待中")
    func: Optional[str] = Field(None, description="函数名称")
    args: Optional[List[Any]] = Field(None, description="函数参数")
    kwargs: Optional[Dict[str, Any]] = Field(None, description="函数关键字参数")


class ScheduleActionResponse(BaseModel):
    """统一调度操作响应"""
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="操作结果消息")
    action: str = Field(..., description="执行的操作类型")
    config_id: int = Field(..., description="任务配置ID")
    status: str = Field(..., description="任务状态")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "任务 205 暂停成功",
                "action": "pause",
                "config_id": 205,
                "status": "paused"
            }
        }
    )

