"""
任务执行相关的Pydantic模型
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


# =============================================================================
# 基础模型
# =============================================================================

class TaskExecutionInfo(BaseModel):
    """任务执行信息基础模型"""
    id: int = Field(..., description="执行记录ID")
    task_id: str = Field(..., description="任务ID")
    config_id: int = Field(..., description="配置ID")
    is_success: bool = Field(..., description="执行是否成功")
    started_at: datetime = Field(..., description="开始时间")
    completed_at: datetime = Field(..., description="完成时间")
    duration_seconds: Optional[float] = Field(None, description="执行时长(秒)")
    result: Optional[Dict[str, Any]] = Field(None, description="执行结果")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")


class TaskExecutionDetailInfo(TaskExecutionInfo):
    """任务执行详细信息（包含配置信息）"""
    config_name: Optional[str] = Field(None, description="配置名称")
    task_type: Optional[str] = Field(None, description="任务类型")
    error_traceback: Optional[str] = Field(None, description="错误堆栈")


# 执行统计相关的数据由CRUD方法直接返回，不需要额外的schema定义


# =============================================================================
# 响应模型 - 对应执行管理端点
# =============================================================================

class ConfigExecutionsResponse(BaseModel):
    """配置执行记录响应 - GET /executions/configs/{id}"""
    config_id: int = Field(..., description="配置ID")
    executions: List[TaskExecutionInfo] = Field(..., description="执行记录列表")
    count: int = Field(..., description="记录数量")


class RecentExecutionsResponse(BaseModel):
    """最近执行记录响应 - GET /executions/recent"""
    hours: int = Field(..., description="时间范围(小时)")
    executions: List[TaskExecutionDetailInfo] = Field(..., description="执行记录列表")
    count: int = Field(..., description="记录数量")


class FailedExecutionsResponse(BaseModel):
    """失败执行记录响应 - GET /executions/failed"""
    days: int = Field(..., description="时间范围(天)")
    failed_executions: List[TaskExecutionDetailInfo] = Field(..., description="失败执行记录列表")
    count: int = Field(..., description="记录数量")


# 注意：/executions/stats 端点不使用 response_model，因为它会根据参数返回不同格式的统计数据

class ExecutionDetailResponse(TaskExecutionDetailInfo):
    """执行详情响应 - GET /executions/{task_id}"""
    pass  # 继承TaskExecutionDetailInfo的所有字段


class ExecutionCleanupResponse(BaseModel):
    """执行记录清理响应 - DELETE /executions/cleanup"""
    success: bool = Field(..., description="清理是否成功")
    deleted_count: int = Field(..., description="删除记录数")
    message: str = Field(..., description="清理结果消息")