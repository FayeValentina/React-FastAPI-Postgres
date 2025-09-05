"""
任务配置相关的Pydantic模型
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

from app.infrastructure.tasks.task_registry_decorators import SchedulerType
from app.infrastructure.cache.cache_serializer import register_pydantic_model


class TaskConfigBase(BaseModel):
    """任务配置基础模型"""
    name: str = Field(..., description="任务名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="任务描述", max_length=500)
    task_type: str = Field(..., description="任务类型")
    scheduler_type: SchedulerType = Field(..., description="调度器类型")
    # status: ConfigStatus = Field(ConfigStatus.ACTIVE, description="任务状态")  # 已删除status字段
    parameters: Dict[str, Any] = Field({}, description="任务参数(JSON)")
    schedule_config: Dict[str, Any] = Field({}, description="调度配置(JSON)")
    max_retries: int = Field(0, description="最大重试次数", ge=0, le=10)
    timeout_seconds: Optional[int] = Field(None, description="任务超时时间(秒)", gt=0)
    priority: int = Field(5, description="任务优先级(1-10)", ge=1, le=10)
    
    @field_validator('task_type')
    def validate_task_type(cls, v):
        from app.infrastructure.tasks import task_registry_decorators as tr
        if not tr.is_supported(v):
            raise ValueError(f'不支持的任务类型: {v}')
        return v


class TaskConfigCreate(TaskConfigBase):
    """创建任务配置"""
    
    @field_validator('parameters')
    def validate_parameters(cls, v, values):
        """验证任务参数"""
        task_type = values.get('task_type')
        if not task_type:
            return v
        
        # 清理任务参数验证 - 允许使用默认值，不强制要求参数
        if task_type in ["CLEANUP_CONTENT", "CLEANUP_TOKENS"]:
            if 'days_old' in v:
                if not isinstance(v['days_old'], int) or v['days_old'] <= 0:
                    raise ValueError('days_old必须为正整数')
                
        return v
    
    @field_validator('schedule_config')
    def validate_schedule_config(cls, v, values):
        """验证调度配置"""
        scheduler_type = values.get('scheduler_type')
        if not scheduler_type:
            return v
            
        if scheduler_type == SchedulerType.CRON:
            # 支持两种cron格式
            has_cron_expression = 'cron_expression' in v
            required = ['minute', 'hour', 'day', 'month', 'day_of_week']
            has_cron_fields = all(field in v for field in required)
            
            if not has_cron_expression and not has_cron_fields:
                raise ValueError(f'Cron调度需要提供 cron_expression 或者完整的cron字段({", ".join(required)})')
                    
        elif scheduler_type == SchedulerType.DATE:
            if 'run_date' not in v:
                raise ValueError('日期调度缺少必要参数: run_date')
                
        return v


class TaskConfigUpdate(BaseModel):
    """更新任务配置"""
    name: Optional[str] = Field(None, description="任务名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="任务描述", max_length=500)
    # status: Optional[ConfigStatus] = Field(None, description="任务状态")  # 已删除status字段
    parameters: Optional[Dict[str, Any]] = Field(None, description="任务参数(JSON)")
    schedule_config: Optional[Dict[str, Any]] = Field(None, description="调度配置(JSON)")
    max_retries: Optional[int] = Field(None, description="最大重试次数", ge=0, le=10)
    timeout_seconds: Optional[int] = Field(None, description="任务超时时间(秒)", gt=0)
    priority: Optional[int] = Field(None, description="任务优先级(1-10)", ge=1, le=10)


# =============================================================================
# 响应模型 - 对应配置管理端点
# =============================================================================

@register_pydantic_model
class TaskConfigResponse(TaskConfigBase):
    """任务配置基础响应模型"""
    id: int = Field(..., description="配置ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    # 新增：来自Redis的调度状态（统一服务，无重叠）
    schedule_status: Optional[str] = Field(None, description="Redis中的调度状态")
    is_scheduled: Optional[bool] = Field(None, description="是否正在调度中")
    status_consistent: Optional[bool] = Field(None, description="状态是否一致")
    model_config = ConfigDict(from_attributes=True)


@register_pydantic_model
class TaskConfigDetailResponse(TaskConfigResponse):
    """任务配置详情响应 - GET /configs/{id}"""
    recent_history: Optional[list] = Field(None, description="最近历史事件")
    stats: Optional[Dict[str, Any]] = Field(None, description="统计信息")


@register_pydantic_model
class TaskConfigListResponse(BaseModel):
    """任务配置列表响应 - GET /configs"""
    items: list[TaskConfigResponse] = Field(..., description="配置列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")
    pages: int = Field(..., description="总页数")


@register_pydantic_model
class TaskConfigDeleteResponse(BaseModel):
    """任务配置删除响应 - DELETE /configs/{id}"""
    success: bool = Field(..., description="删除是否成功")
    message: str = Field(..., description="删除结果消息")




class TaskConfigQuery(BaseModel):
    """任务配置查询参数"""
    task_type: Optional[str] = Field(None, description="任务类型")
    # status: Optional[ConfigStatus] = Field(None, description="任务状态")  # 已删除status字段
    name_search: Optional[str] = Field(None, description="名称搜索", max_length=100)
    page: int = Field(1, description="页码", ge=1)
    page_size: int = Field(20, description="每页大小", ge=1, le=100)
    order_by: str = Field("created_at", description="排序字段")
    order_desc: bool = Field(True, description="降序排序")

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

@register_pydantic_model
class ConfigExecutionsResponse(BaseModel):
    """配置执行记录响应 - GET /executions/configs/{id}"""
    config_id: int = Field(..., description="配置ID")
    executions: List[TaskExecutionInfo] = Field(..., description="执行记录列表")
    count: int = Field(..., description="记录数量")


@register_pydantic_model
class RecentExecutionsResponse(BaseModel):
    """最近执行记录响应 - GET /executions/recent"""
    hours: int = Field(..., description="时间范围(小时)")
    executions: List[TaskExecutionDetailInfo] = Field(..., description="执行记录列表")
    count: int = Field(..., description="记录数量")


@register_pydantic_model
class FailedExecutionsResponse(BaseModel):
    """失败执行记录响应 - GET /executions/failed"""
    days: int = Field(..., description="时间范围(天)")
    failed_executions: List[TaskExecutionDetailInfo] = Field(..., description="失败执行记录列表")
    count: int = Field(..., description="记录数量")


# 注意：/executions/stats 端点不使用 response_model，因为它会根据参数返回不同格式的统计数据

@register_pydantic_model
class ExecutionDetailResponse(TaskExecutionDetailInfo):
    """执行详情响应 - GET /executions/{task_id}"""
    pass  # 继承TaskExecutionDetailInfo的所有字段


@register_pydantic_model
class ExecutionCleanupResponse(BaseModel):
    """执行记录清理响应 - DELETE /executions/cleanup"""
    success: bool = Field(..., description="清理是否成功")
    deleted_count: int = Field(..., description="删除记录数")
    message: str = Field(..., description="清理结果消息")

# =============================================================================
# 基础模型
# =============================================================================

@register_pydantic_model
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

@register_pydantic_model
class ScheduleListResponse(BaseModel):
    """调度列表响应 - GET /schedules"""
    schedules: List[ScheduledJobInfo] = Field(..., description="调度任务列表")
    total: int = Field(..., description="总数")


@register_pydantic_model
class ScheduleHistoryResponse(BaseModel):
    """调度历史响应 - GET /schedules/{id}/history"""
    config_id: int = Field(..., description="配置ID")
    history: List[ScheduleHistoryEvent] = Field(..., description="历史事件列表")
    count: int = Field(..., description="事件数量")


@register_pydantic_model
class ScheduleSummaryResponse(BaseModel):
    """调度摘要响应 - GET /schedules/summary"""
    total_tasks: int = Field(..., description="总任务数")
    active_tasks: int = Field(..., description="活跃任务数")
    paused_tasks: int = Field(..., description="暂停任务数")
    inactive_tasks: int = Field(..., description="未激活任务数")
    error_tasks: int = Field(..., description="错误任务数")
    last_updated: str = Field(..., description="最后更新时间")
    
# =============================================================================
# 基础模型
# =============================================================================

class ComponentHealthInfo(BaseModel):
    """组件健康信息"""
    status: str = Field(..., description="组件状态 (healthy/unhealthy)")
    message: str = Field(..., description="状态描述")


class ConfigStatsInfo(BaseModel):
    """配置统计信息"""
    total_configs: int = Field(..., description="总配置数")
    by_type: Dict[str, int] = Field(..., description="按类型统计")


class ScheduleSummaryInfo(BaseModel):
    """调度摘要信息"""
    total_tasks: int = Field(..., description="总任务数")
    active_tasks: int = Field(..., description="活跃任务数")
    paused_tasks: int = Field(..., description="暂停任务数")
    inactive_tasks: int = Field(..., description="未激活任务数")
    error_tasks: int = Field(..., description="错误任务数")
    last_updated: str = Field(..., description="最后更新时间")


class ExecutionStatsInfo(BaseModel):
    """执行统计信息"""
    period_days: int = Field(..., description="统计周期(天)")
    total_executions: int = Field(..., description="总执行次数")
    success_count: int = Field(..., description="成功次数")
    failed_count: int = Field(..., description="失败次数")
    success_rate: float = Field(..., description="成功率(%)")
    failure_rate: float = Field(..., description="失败率(%)")
    avg_duration_seconds: float = Field(..., description="平均执行时长(秒)")
    type_breakdown: Dict[str, int] = Field(..., description="按任务类型分组统计")
    timestamp: str = Field(..., description="统计时间戳")


# =============================================================================
# 响应模型 - 对应系统监控端点
# =============================================================================

@register_pydantic_model
class SystemStatusResponse(BaseModel):
    """系统状态响应 - GET /system/status"""
    system_time: str = Field(..., description="系统时间")
    scheduler_status: str = Field(..., description="调度器状态")
    database_status: str = Field(..., description="数据库状态")
    redis_status: str = Field(..., description="Redis状态")
    
    config_stats: ConfigStatsInfo = Field(..., description="配置统计")
    schedule_summary: ScheduleSummaryInfo = Field(..., description="调度状态摘要")
    execution_stats: ExecutionStatsInfo = Field(..., description="执行统计")


@register_pydantic_model
class SystemHealthResponse(BaseModel):
    """系统健康检查响应 - GET /system/health"""
    status: str = Field(..., description="整体健康状态 (healthy/degraded/unhealthy)")
    timestamp: str = Field(..., description="检查时间戳")
    components: Dict[str, ComponentHealthInfo] = Field(..., description="各组件健康状态")
    error: Optional[str] = Field(None, description="错误信息")


@register_pydantic_model
class SystemEnumsResponse(BaseModel):
    """系统枚举值响应 - GET /system/enums"""
    scheduler_types: List[str] = Field(..., description="调度器类型列表")
    schedule_actions: List[str] = Field(..., description="调度动作列表")
    task_types: List[str] = Field(..., description="任务类型列表")
    schedule_statuses: List[str] = Field(..., description="调度状态列表")


class TypeInfo(BaseModel):
    """结构化类型信息（前端渲染不需要原始类型字符串）"""
    type: str = Field(..., description="类型名称")
    args: Optional[List['TypeInfo']] = Field(None, description="类型参数")

# 支持前向引用
TypeInfo.model_rebuild()

class UIMetaInfo(BaseModel):
    """前端渲染的UI元信息（由后端任务注册时生成）"""
    exclude_from_ui: bool = Field(False, description="是否在前端隐藏该参数")
    ui_hint: Optional[str] = Field(None, description="控件类型建议，如 select/number/text/json/boolean/email/password/textarea")
    choices: Optional[List[Any]] = Field(None, description="可选值列表（用于select等）")
    label: Optional[str] = Field(None, description="显示标签（可选）")
    description: Optional[str] = Field(None, description="参数描述（可选）")
    placeholder: Optional[str] = Field(None, description="占位提示（可选）")
    min: Optional[float] = Field(None, description="数值最小值（可选）")
    max: Optional[float] = Field(None, description="数值最大值（可选）")
    step: Optional[float] = Field(None, description="数值步进（可选）")
    pattern: Optional[str] = Field(None, description="输入匹配模式（可选）")
    example: Optional[Any] = Field(None, description="示例值（JSON 可用作结构提示）")


class TaskParameterInfo(BaseModel):
    """任务参数信息"""
    name: str = Field(..., description="参数名")
    type: str = Field(..., description="参数类型（字符串格式）")
    type_info: TypeInfo = Field(..., description="结构化类型信息")
    default: Optional[str] = Field(None, description="默认值")
    required: bool = Field(..., description="是否必需")
    kind: str = Field(..., description="参数种类")
    ui: Optional[UIMetaInfo] = Field(None, description="前端渲染UI元信息")


class TaskInfo(BaseModel):
    """任务信息"""
    name: str = Field(..., description="任务名称")
    worker_name: str = Field(..., description="工作函数名")
    queue: str = Field(..., description="队列名")
    doc: str = Field(..., description="任务描述")
    parameters: List[TaskParameterInfo] = Field(..., description="参数列表")
    has_parameters: bool = Field(..., description="是否有参数")


@register_pydantic_model
class TaskInfoResponse(BaseModel):
    """任务信息响应 - GET /system/task-info"""
    tasks: List[TaskInfo] = Field(..., description="任务信息列表")
    total_count: int = Field(..., description="任务总数")
    generated_at: str = Field(..., description="生成时间")


class DashboardExecutionStats(BaseModel):
    """仪表板执行统计"""
    last_7_days: ExecutionStatsInfo = Field(..., description="最近7天统计")
    last_30_days: ExecutionStatsInfo = Field(..., description="最近30天统计")


class DashboardInfo(BaseModel):
    """仪表板信息"""
    config_stats: ConfigStatsInfo = Field(..., description="配置统计")
    schedule_summary: ScheduleSummaryInfo = Field(..., description="调度状态摘要")
    execution_stats: DashboardExecutionStats = Field(..., description="执行统计")
    generated_at: str = Field(..., description="生成时间")


@register_pydantic_model
class SystemDashboardResponse(BaseModel):
    """系统仪表板响应 - GET /system/dashboard"""
    dashboard: DashboardInfo = Field(..., description="仪表板数据")
