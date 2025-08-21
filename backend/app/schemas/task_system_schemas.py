"""
任务系统监控相关的Pydantic模型
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


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

class SystemStatusResponse(BaseModel):
    """系统状态响应 - GET /system/status"""
    system_time: str = Field(..., description="系统时间")
    scheduler_status: str = Field(..., description="调度器状态")
    database_status: str = Field(..., description="数据库状态")
    redis_status: str = Field(..., description="Redis状态")
    
    config_stats: ConfigStatsInfo = Field(..., description="配置统计")
    schedule_summary: ScheduleSummaryInfo = Field(..., description="调度状态摘要")
    execution_stats: ExecutionStatsInfo = Field(..., description="执行统计")


class SystemHealthResponse(BaseModel):
    """系统健康检查响应 - GET /system/health"""
    status: str = Field(..., description="整体健康状态 (healthy/degraded/unhealthy)")
    timestamp: str = Field(..., description="检查时间戳")
    components: Dict[str, ComponentHealthInfo] = Field(..., description="各组件健康状态")
    error: Optional[str] = Field(None, description="错误信息")


class SystemEnumsResponse(BaseModel):
    """系统枚举值响应 - GET /system/enums"""
    scheduler_types: List[str] = Field(..., description="调度器类型列表")
    schedule_actions: List[str] = Field(..., description="调度动作列表")
    task_types: List[str] = Field(..., description="任务类型列表")
    schedule_statuses: List[str] = Field(..., description="调度状态列表")


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


class SystemDashboardResponse(BaseModel):
    """系统仪表板响应 - GET /system/dashboard"""
    dashboard: DashboardInfo = Field(..., description="仪表板数据")