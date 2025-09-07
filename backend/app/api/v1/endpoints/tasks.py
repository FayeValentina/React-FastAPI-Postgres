"""任务系统API路由 - 使用服务层处理业务逻辑"""

from fastapi import APIRouter, Depends, Query, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated, Any, Dict, List, Optional

from app.modules.auth.models import User
from app.api.dependencies import get_current_superuser
from app.infrastructure.database.postgres_base import get_async_session
from app.modules.tasks.schemas import (
    TaskConfigCreate,
    TaskConfigUpdate,
    TaskConfigResponse,
    TaskConfigDetailResponse,
    TaskConfigListResponse,
    TaskConfigDeleteResponse,
    TaskConfigQuery,
    ConfigExecutionsResponse,
    RecentExecutionsResponse,
    FailedExecutionsResponse,
    ExecutionDetailResponse,
    ExecutionCleanupResponse,
    ScheduleOperationResponse,
    ScheduleListResponse,
    ScheduleHistoryResponse,
    ScheduleSummaryResponse,
    ConfigSchedulesResponse,
    ScheduleInstanceResponse,
    SystemStatusResponse,
    SystemHealthResponse,
    SystemEnumsResponse,
    TaskInfoResponse,
    SystemDashboardResponse,
    OrphanListResponse,
    OrphanCleanupResponse,
    CleanupLegacyResponse,
)
from app.infrastructure.cache.cache_decorators import cache, invalidate
from app.constant.cache_tags import CacheTags
from app.modules.tasks.service import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


# =============================================================================
# 一、任务配置管理端点 /configs
# 核心理念：配置管理 + 调度状态一体化
# =============================================================================

@router.post("/configs", response_model=TaskConfigResponse, status_code=201)
@invalidate([CacheTags.TASK_CONFIGS, CacheTags.SYSTEM_STATUS, CacheTags.SYSTEM_DASHBOARD])
async def create_task_config(
    request: Request,
    config: TaskConfigCreate,
    auto_schedule: bool = Query(False, description="自动启动调度"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """创建任务配置（可选自动调度）"""
    return await task_service.create_task_config(db=db, config=config, auto_schedule=auto_schedule)


@router.get("/configs", response_model=TaskConfigListResponse)
@cache([CacheTags.TASK_CONFIGS], exclude_params=["request", "db", "current_user"])
async def list_task_configs(
    request: Request,
    task_type: Optional[str] = Query(None, description="按任务类型过滤"),
    name_search: Optional[str] = Query(None, description="按名称搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    order_by: str = Query("created_at", description="排序字段"),
    order_desc: bool = Query(True, description="降序排序"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取任务配置列表（带状态）"""
    query = TaskConfigQuery(
        task_type=task_type,
        name_search=name_search,
        page=page,
        page_size=page_size,
        order_by=order_by,
        order_desc=order_desc,
    )
    return await task_service.list_task_configs(db=db, query=query)


@router.get("/configs/{config_id}", response_model=TaskConfigDetailResponse)
@cache([CacheTags.TASK_CONFIG_DETAIL], exclude_params=["request", "db", "current_user"])
async def get_task_config(
    request: Request,
    config_id: int = Path(..., description="配置ID"),
    include_stats: bool = Query(False, description="包含统计信息"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取单个配置详情"""
    return await task_service.get_task_config(db=db, config_id=config_id, include_stats=include_stats)


@router.patch("/configs/{config_id}", response_model=TaskConfigResponse)
@invalidate([CacheTags.TASK_CONFIGS, CacheTags.SYSTEM_STATUS, CacheTags.SYSTEM_DASHBOARD])
async def update_task_config(
    request: Request,
    config_id: int,
    update_data: TaskConfigUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """更新任务配置"""
    return await task_service.update_task_config(db=db, config_id=config_id, update_data=update_data)


@router.delete("/configs/{config_id}", response_model=TaskConfigDeleteResponse)
@invalidate([
    CacheTags.TASK_CONFIGS,                 # 清理列表缓存（模式）
    CacheTags.TASK_CONFIG_DETAIL, # 清理详情缓存（精确）
    CacheTags.SYSTEM_STATUS,                # 清理状态缓存（模式）
    CacheTags.SYSTEM_DASHBOARD              # 清理仪表盘缓存（模式）
])
async def delete_task_config(
    request: Request,
    config_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """删除配置（自动停止调度）"""
    return await task_service.delete_task_config(db=db, config_id=config_id)


# =============================================================================
# 二、调度管理端点 /schedules
# 核心理念：纯调度操作，状态一致性验证
# =============================================================================

@router.post("/configs/{config_id}/schedules", response_model=ScheduleOperationResponse, status_code=201)
@invalidate([CacheTags.SYSTEM_STATUS, CacheTags.SYSTEM_DASHBOARD, CacheTags.SCHEDULE_LIST])
async def create_schedule_instance(
    request: Request,
    config_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """从配置创建一个新的调度实例（返回 schedule_id）。"""
    return await task_service.create_schedule_instance(db=db, config_id=config_id)


@router.delete("/schedules/{schedule_id}", response_model=ScheduleOperationResponse)
@invalidate([CacheTags.SYSTEM_STATUS, CacheTags.SYSTEM_DASHBOARD, CacheTags.SCHEDULE_LIST])
async def unregister_schedule(
    request: Request,
    schedule_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """注销调度实例。"""
    return await task_service.unregister_schedule(schedule_id=schedule_id)


@router.post("/schedules/{schedule_id}/pause", response_model=ScheduleOperationResponse)
@invalidate([CacheTags.SYSTEM_STATUS, CacheTags.SYSTEM_DASHBOARD, CacheTags.SCHEDULE_LIST])
async def pause_schedule(
    request: Request,
    schedule_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """暂停调度实例"""
    return await task_service.pause_schedule(schedule_id=schedule_id)


@router.post("/schedules/{schedule_id}/resume", response_model=ScheduleOperationResponse)
@invalidate([CacheTags.SYSTEM_STATUS, CacheTags.SYSTEM_DASHBOARD, CacheTags.SCHEDULE_LIST])
async def resume_schedule(
    request: Request,
    schedule_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """恢复调度实例"""
    return await task_service.resume_schedule(schedule_id=schedule_id)


@router.get("/schedules", response_model=ScheduleListResponse)
@cache([CacheTags.SCHEDULE_LIST], exclude_params=["request", "current_user"])
async def get_all_schedules(
    request: Request,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取所有调度状态"""
    return await task_service.get_all_schedules()


@router.get("/configs/{config_id}/schedules", response_model=ConfigSchedulesResponse)
async def list_config_schedules(
    config_id: int,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """列出配置下的所有调度实例ID。"""
    return await task_service.list_config_schedules(config_id=config_id)


@router.get("/schedules/{schedule_id}", response_model=ScheduleInstanceResponse)
async def get_schedule_instance(
    schedule_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取单个调度实例的详细信息。"""
    return await task_service.get_schedule_info(schedule_id=schedule_id)


@router.get("/schedules/{schedule_id}/history", response_model=ScheduleHistoryResponse)
async def get_schedule_history(
    schedule_id: str,
    limit: int = Query(50, ge=1, le=200, description="历史记录数量"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取调度实例的历史事件。"""
    return await task_service.get_schedule_history(schedule_id=schedule_id, limit=limit)


@router.get("/schedules/summary", response_model=ScheduleSummaryResponse)
async def get_schedule_summary(
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取调度摘要"""
    return await task_service.get_schedule_summary()


# =============================================================================
# 三、执行管理端点 /executions
# 核心理念：执行记录查询和统计分析
# =============================================================================

@router.get("/executions/configs/{config_id}", response_model=ConfigExecutionsResponse)
async def get_config_executions(
    config_id: int,
    limit: int = Query(50, ge=1, le=200, description="记录数量"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """按配置获取执行记录"""
    return await task_service.get_config_executions(db=db, config_id=config_id, limit=limit)


@router.get("/executions/recent", response_model=RecentExecutionsResponse)
async def get_recent_executions(
    hours: int = Query(24, ge=1, le=168, description="时间范围（小时）"),
    limit: int = Query(100, ge=1, le=500, description="记录数量"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取最近执行记录"""
    return await task_service.get_recent_executions(db=db, hours=hours, limit=limit)


@router.get("/executions/failed", response_model=FailedExecutionsResponse)
async def get_failed_executions(
    days: int = Query(7, ge=1, le=90, description="时间范围（天）"),
    limit: int = Query(50, ge=1, le=200, description="记录数量"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取失败执行记录"""
    return await task_service.get_failed_executions(db=db, days=days, limit=limit)


@router.get("/executions/stats")
@cache([CacheTags.EXECUTION_STATS], exclude_params=["request", "db", "current_user"])
async def get_execution_stats(
    request: Request,
    config_id: Optional[int] = Query(None, description="配置ID（可选）"),
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取执行统计"""
    return await task_service.get_execution_stats(db=db, config_id=config_id, days=days)


@router.get("/executions/{task_id}", response_model=ExecutionDetailResponse)
async def get_execution_by_task_id(
    task_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """通过task_id查询执行记录"""
    return await task_service.get_execution_by_task_id(db=db, task_id=task_id)


@router.delete("/executions/cleanup", response_model=ExecutionCleanupResponse)
@invalidate([CacheTags.EXECUTION_STATS, CacheTags.SYSTEM_STATUS, CacheTags.SYSTEM_DASHBOARD])
async def cleanup_old_executions(
    request: Request,
    days_to_keep: int = Query(90, ge=30, le=365, description="保留天数"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """清理旧执行记录（管理员）"""
    return await task_service.cleanup_execution_history(db=db, days_to_keep=days_to_keep)


# =============================================================================
# 四、系统监控端点 /system
# 核心理念：系统状态和健康监控
# =============================================================================

@router.get("/system/status", response_model=SystemStatusResponse)
@cache([CacheTags.SYSTEM_STATUS], exclude_params=["request", "db", "current_user"]) 
async def get_system_status(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """系统状态总览"""
    return await task_service.get_system_status(db=db)


@router.get("/system/health", response_model=SystemHealthResponse)
async def get_system_health(
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """系统健康检查"""
    return await task_service.get_system_health(db=db)


@router.get("/system/enums", response_model=SystemEnumsResponse)
@cache([CacheTags.SYSTEM_ENUMS], exclude_params=["request", "current_user"])
async def get_system_enums(
    request: Request,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取系统枚举值"""
    return await task_service.get_system_enums()


@router.get("/system/task-info", response_model=TaskInfoResponse)
@cache([CacheTags.TASK_INFO], exclude_params=["request", "current_user"])
async def get_task_info(
    request: Request,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取所有任务的详细参数信息"""
    return await task_service.get_task_info()


@router.get("/system/dashboard", response_model=SystemDashboardResponse)
@cache([CacheTags.SYSTEM_DASHBOARD], exclude_params=["request", "db", "current_user"])
async def get_system_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """全局统计仪表板"""
    return await task_service.get_system_dashboard(db=db)


# =============================================================================
# 五、管理员维护端点 /system/cleanup & /system/orphans
# =============================================================================

@router.get("/system/orphans", response_model=OrphanListResponse)
async def list_orphans(
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """列出孤儿调度实例（无对应 TaskConfig）。"""
    return await task_service.list_orphans()


@router.post("/system/cleanup/orphans", response_model=OrphanCleanupResponse)
@invalidate([CacheTags.SYSTEM_STATUS, CacheTags.SYSTEM_DASHBOARD, CacheTags.SCHEDULE_LIST])
async def cleanup_orphans(
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """手动清理孤儿调度实例。"""
    return await task_service.cleanup_orphans()


@router.post("/system/cleanup/legacy", response_model=CleanupLegacyResponse)
@invalidate([CacheTags.SYSTEM_STATUS, CacheTags.SYSTEM_DASHBOARD, CacheTags.SCHEDULE_LIST])
async def cleanup_legacy(
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """手动清理遗留旧键与旧格式调度ID。"""
    return await task_service.cleanup_legacy()
