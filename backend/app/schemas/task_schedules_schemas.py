"""
任务调度相关的Pydantic模型
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


# =============================================================================
# 基础模型
# =============================================================================

class ScheduleActionResponse(BaseModel):
    """调度操作响应 - POST /schedules/{id}/{action}"""
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="操作结果消息")
    config_id: int = Field(..., description="任务配置ID")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "任务 205 启动成功",
                "config_id": 205
            }
        }
    )


class ScheduledJobInfo(BaseModel):
    """调度任务信息"""
    task_id: str = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")
    config_id: Optional[int] = Field(None, description="配置ID")
    schedule: str = Field(..., description="调度配置")
    labels: Dict[str, Any] = Field({}, description="任务标签")
    next_run: Optional[str] = Field(None, description="下次运行时间")


class ScheduleHistoryEvent(BaseModel):
    """调度历史事件"""
    event: str = Field(..., description="事件类型")
    timestamp: str = Field(..., description="事件时间")
    success: Optional[bool] = Field(None, description="操作是否成功")
    task_name: Optional[str] = Field(None, description="任务名称")
    error: Optional[str] = Field(None, description="错误信息")


# =============================================================================
# 响应模型 - 对应调度管理端点
# =============================================================================

class ScheduleListResponse(BaseModel):
    """调度列表响应 - GET /schedules"""
    schedules: List[ScheduledJobInfo] = Field(..., description="调度任务列表")
    total: int = Field(..., description="总数")


class ScheduleHistoryResponse(BaseModel):
    """调度历史响应 - GET /schedules/{id}/history"""
    config_id: int = Field(..., description="配置ID")
    history: List[ScheduleHistoryEvent] = Field(..., description="历史事件列表")
    count: int = Field(..., description="事件数量")


class ScheduleSummaryResponse(BaseModel):
    """调度摘要响应 - GET /schedules/summary"""
    total_tasks: int = Field(..., description="总任务数")
    active_tasks: int = Field(..., description="活跃任务数")
    paused_tasks: int = Field(..., description="暂停任务数")
    inactive_tasks: int = Field(..., description="未激活任务数")
    error_tasks: int = Field(..., description="错误任务数")
    last_updated: str = Field(..., description="最后更新时间")