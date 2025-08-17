from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.task_execution import ExecutionStatus
from enum import Enum


class TaskExecutionCreate(BaseModel):
    """创建任务执行记录"""
    config_id: int = Field(..., description="任务配置ID")
    job_id: str = Field(..., description="任务执行ID")
    job_name: str = Field(..., description="任务名称")
    status: ExecutionStatus = Field(..., description="执行状态")
    started_at: str = Field(..., description="开始时间")
    completed_at: Optional[str] = Field(None, description="完成时间")
    duration_seconds: Optional[float] = Field(None, description="执行时长(秒)")
    result: Optional[Dict[str, Any]] = Field(None, description="执行结果")
    error_message: Optional[str] = Field(None, description="错误消息")
    error_traceback: Optional[str] = Field(None, description="错误堆栈")

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


class OperationResponse(BaseModel):
    """通用操作响应"""
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="操作结果消息")


class TaskExecutionResult(BaseModel):
    """任务执行结果响应"""
    task_id: str = Field(..., description="任务ID")
    config_id: Optional[int] = Field(None, description="配置ID")
    task_type: Optional[str] = Field(None, description="任务类型")
    status: str = Field(..., description="执行状态")
    queue: Optional[str] = Field(None, description="队列名称")
    message: Optional[str] = Field(None, description="结果消息")


class BatchCreateResponse(BaseModel):
    """批量创建响应"""
    created: List[int] = Field(..., description="成功创建的ID列表")
    failed: List[Dict[str, Any]] = Field(..., description="失败项目列表")
    total_created: int = Field(..., description="创建成功总数")
    total_failed: int = Field(..., description="创建失败总数")


class BatchDeleteResponse(BaseModel):
    """批量删除响应"""
    deleted: List[int] = Field(..., description="成功删除的ID列表")
    failed: List[Dict[str, Any]] = Field(..., description="失败项目列表")
    total_deleted: int = Field(..., description="删除成功总数")
    total_failed: int = Field(..., description="删除失败总数")


class BatchExecutionResponse(BaseModel):
    """批量执行响应"""
    task_ids: List[str] = Field(..., description="任务ID列表")
    total_submitted: int = Field(..., description="提交任务总数")
    config_ids: Optional[List[int]] = Field(None, description="配置ID列表")
    task_type: Optional[str] = Field(None, description="任务类型")
    status: str = Field(..., description="提交状态")


class TaskRevokeResponse(BaseModel):
    """任务撤销响应"""
    task_id: str = Field(..., description="任务ID")
    revoked: bool = Field(..., description="是否成功撤销")
    message: str = Field(..., description="操作结果")


class BatchRevokeResponse(BaseModel):
    """批量撤销响应"""
    total_revoked: int = Field(..., description="撤销成功总数")
    total_failed: int = Field(..., description="撤销失败总数")
    results: List[TaskRevokeResponse] = Field(..., description="详细结果列表")


class QueueStatsResponse(BaseModel):
    """队列统计响应"""
    queues: Dict[str, Dict[str, Any]] = Field(..., description="队列统计信息")
    total_tasks: int = Field(..., description="总任务数")


class QueueLengthResponse(BaseModel):
    """队列长度响应"""
    queue_name: str = Field(..., description="队列名称")
    length: int = Field(..., description="队列长度")
    status: str = Field(..., description="队列状态")



class TaskTypeSupportResponse(BaseModel):
    """任务类型支持检查响应"""
    task_type: str = Field(..., description="任务类型")
    supported: bool = Field(..., description="是否支持")
    worker_task_name: Optional[str] = Field(None, description="对应的worker任务名")

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


class ValidationResponse(BaseModel):
    """配置验证响应"""
    valid: bool = Field(..., description="是否有效")
    message: str = Field(..., description="验证消息")
    config: Optional[Dict[str, Any]] = Field(None, description="配置数据")


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    result: Optional[Dict[str, Any]] = Field(None, description="任务结果")
    traceback: Optional[str] = Field(None, description="错误追踪")
    name: Optional[str] = Field(None, description="任务名称")
    args: Optional[List[Any]] = Field(None, description="任务参数")
    kwargs: Optional[Dict[str, Any]] = Field(None, description="任务关键字参数")


class ActiveTaskInfo(BaseModel):
    """活跃任务信息"""
    task_id: str = Field(..., description="任务ID")
    name: str = Field(..., description="任务名称")
    args: List[Any] = Field(..., description="任务参数")
    kwargs: Dict[str, Any] = Field(..., description="任务关键字参数")
    worker: Optional[str] = Field(None, description="执行工作者")
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

