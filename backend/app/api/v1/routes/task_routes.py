"""
任务系统API路由 - 重构版 v2.0
使用新的CRUD + Redis架构，消除过度封装，实现职责分离

架构特点：
- PostgreSQL: 存储静态配置
- Redis: 管理调度状态和历史
- 数据组合: API层组合两部分数据返回
- 简化状态: 使用is_success二元状态
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated, Any, Dict, List, Optional
from datetime import datetime

from app.models.user import User
from app.dependencies.current_user import get_current_superuser
from app.db.base import get_async_session
from app.schemas.task_config_schemas import (
    TaskConfigCreate, 
    TaskConfigUpdate, 
    TaskConfigResponse,
    TaskConfigDetailResponse,
    TaskConfigListResponse,
    TaskConfigDeleteResponse,
    TaskConfigQuery
)
from app.schemas.task_schedules_schemas import (
    ScheduleActionResponse,
    ScheduleListResponse,
    ScheduleHistoryResponse,
    ScheduleSummaryResponse
)
from app.schemas.task_executions_schemas import (
    ConfigExecutionsResponse,
    RecentExecutionsResponse,
    FailedExecutionsResponse,
    ExecutionDetailResponse,
    ExecutionCleanupResponse
)
from app.schemas.task_system_schemas import (
    SystemStatusResponse,
    SystemHealthResponse,
    SystemEnumsResponse,
    TaskInfoResponse,
    SystemDashboardResponse
)
from app.utils.registry_decorators import SchedulerType, ScheduleAction
from app.utils import registry_decorators as tr
from app.crud.task_config import crud_task_config
from app.crud.task_execution import crud_task_execution
from app.core.redis_manager import redis_services
from app.utils import cache_list_data, cache_response, cache_stats_data, cache_static, cache_invalidate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


# =============================================================================
# 一、任务配置管理端点 /configs
# 核心理念：配置管理 + 调度状态一体化
# =============================================================================

@router.post("/configs", response_model=TaskConfigResponse, status_code=201)
@cache_invalidate(["task_configs", "system_status", "system_dashboard"])
async def create_task_config(
    request: Request,
    config: TaskConfigCreate,
    auto_schedule: bool = Query(False, description="自动启动调度"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """创建任务配置（可选自动调度）"""
    try:
        # 1. 创建数据库配置（无status字段）
        db_config = await crud_task_config.create(db, config)
        
        # 2. 如果需要自动启动调度（使用统一的调度服务）
        if auto_schedule and config.scheduler_type != SchedulerType.MANUAL:
            success, message = await redis_services.scheduler.register_task(db_config)
            if not success:
                logger.warning(f"自动启动调度失败: {message}")
        
        # 3. 组合返回数据（配置 + 调度状态）
        schedule_info = await redis_services.scheduler.get_task_full_info(db_config.id)
        
        return {
            # 数据库配置
            'id': db_config.id,
            'name': db_config.name,
            'description': db_config.description,
            'task_type': db_config.task_type,
            'scheduler_type': db_config.scheduler_type.value,
            'parameters': db_config.parameters,
            'schedule_config': db_config.schedule_config,
            'max_retries': db_config.max_retries,
            'timeout_seconds': db_config.timeout_seconds,
            'priority': db_config.priority,
            'created_at': db_config.created_at,
            'updated_at': db_config.updated_at,
            
            # Redis调度状态（来自增强的history服务）
            'schedule_status': schedule_info.get('status'),
            'is_scheduled': schedule_info.get('is_scheduled', False),
            'status_consistent': schedule_info.get('status_consistent', True),
            'recent_history': schedule_info.get('recent_history', [])
        }
    except Exception as e:
        logger.error(f"创建任务配置失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/configs", response_model=TaskConfigListResponse)
@cache_list_data("task_configs")
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
    try:
        query = TaskConfigQuery(
            task_type=task_type,
            name_search=name_search,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order_desc=order_desc
        )
        
        # 1. 从数据库获取配置列表
        configs, total = await crud_task_config.get_by_query(db, query)
        
        # 2. 为每个配置获取调度状态
        results = []
        for config in configs:
            schedule_info = await redis_services.scheduler.get_task_full_info(config.id)
            
            config_data = {
                # 数据库配置
                'id': config.id,
                'name': config.name,
                'description': config.description,
                'task_type': config.task_type,
                'scheduler_type': config.scheduler_type.value,
                'parameters': config.parameters,
                'schedule_config': config.schedule_config,
                'max_retries': config.max_retries,
                'timeout_seconds': config.timeout_seconds,
                'priority': config.priority,
                'created_at': config.created_at,
                'updated_at': config.updated_at,
                
                # Redis调度状态
                'schedule_status': schedule_info.get('status'),
                'is_scheduled': schedule_info.get('is_scheduled', False),
                'status_consistent': schedule_info.get('status_consistent', True)
            }
            results.append(config_data)
        
        return {
            'items': results,
            'total': total,
            'page': page,
            'page_size': page_size,
            'pages': (total + page_size - 1) // page_size
        }
    except Exception as e:
        logger.error(f"获取任务配置列表失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/configs/{config_id}", response_model=TaskConfigDetailResponse)
@cache_response("task_config_detail", include_query_params=True)
async def get_task_config(
    request: Request,
    config_id: int = Path(..., description="配置ID"),
    include_stats: bool = Query(False, description="包含统计信息"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取单个配置详情"""
    try:
        # 1. 从数据库获取配置（无status字段）
        config = await crud_task_config.get(db, config_id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        # 2. 从Redis获取独立的调度状态（增强的history服务）
        schedule_info = await redis_services.scheduler.get_task_full_info(config_id)
        
        result = {
            # 数据库配置
            'id': config.id,
            'name': config.name,
            'description': config.description,
            'task_type': config.task_type,
            'scheduler_type': config.scheduler_type.value,
            'parameters': config.parameters,
            'schedule_config': config.schedule_config,
            'max_retries': config.max_retries,
            'timeout_seconds': config.timeout_seconds,
            'priority': config.priority,
            'created_at': config.created_at,
            'updated_at': config.updated_at,
            
            # Redis调度状态（统一服务，无重叠）
            'schedule_status': schedule_info.get('status'),
            'is_scheduled': schedule_info.get('is_scheduled', False),
            'status_consistent': schedule_info.get('status_consistent', True),
            'recent_history': schedule_info.get('recent_history', [])
        }
        
        if include_stats:
            stats = await crud_task_config.get_execution_stats(db, config_id)
            result['stats'] = stats
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取配置详情失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/configs/{config_id}", response_model=TaskConfigResponse)
@cache_invalidate(["task_configs", "system_status", "system_dashboard"])
async def update_task_config(
    request: Request,
    config_id: int,
    update_data: TaskConfigUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """更新任务配置"""
    try:
        # 1. 检查配置是否存在
        config = await crud_task_config.get(db, config_id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        # 2. 更新数据库配置
        updated_config = await crud_task_config.update(db, config, update_data)
        
        # 3. 获取调度状态
        schedule_info = await redis_services.scheduler.get_task_full_info(config_id)
        
        return {
            # 数据库配置
            'id': updated_config.id,
            'name': updated_config.name,
            'description': updated_config.description,
            'task_type': updated_config.task_type,
            'scheduler_type': updated_config.scheduler_type.value,
            'parameters': updated_config.parameters,
            'schedule_config': updated_config.schedule_config,
            'max_retries': updated_config.max_retries,
            'timeout_seconds': updated_config.timeout_seconds,
            'priority': updated_config.priority,
            'created_at': updated_config.created_at,
            'updated_at': updated_config.updated_at,
            
            # Redis调度状态
            'schedule_status': schedule_info.get('status'),
            'is_scheduled': schedule_info.get('is_scheduled', False),
            'status_consistent': schedule_info.get('status_consistent', True)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新配置失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/configs/{config_id}", response_model=TaskConfigDeleteResponse)
@cache_invalidate([
    "task_configs",                 # 清理列表缓存（模式）
    "task_config_detail:{config_id}", # 清理详情缓存（精确）
    "system_status",                # 清理状态缓存（模式）
    "system_dashboard"              # 清理仪表盘缓存（模式）
])
async def delete_task_config(
    request: Request,
    config_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """删除配置（自动停止调度）"""
    try:
        # 1. 检查配置是否存在
        config = await crud_task_config.get(db, config_id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        # 2. 先停止调度
        await redis_services.scheduler.unregister_task(config_id)
        
        # 3. 删除数据库配置
        success = await crud_task_config.delete(db, config_id)
        
        if success:
            return {
                "success": True,
                "message": f"配置 {config.name} 删除成功"
            }
        else:
            raise HTTPException(status_code=500, detail="删除失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除配置失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# 二、调度管理端点 /schedules
# 核心理念：纯调度操作，状态一致性验证
# =============================================================================

@router.post("/schedules/{config_id}/start", response_model=ScheduleActionResponse)
@cache_invalidate(["system_status", "system_dashboard", "schedule_list"])
async def start_schedule(
    request: Request,
    config_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """启动任务调度"""
    try:
        config = await crud_task_config.get(db, config_id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        success, message = await redis_services.scheduler.register_task(config)
        return {
            "success": success,
            "message": message,
            "config_id": config_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动调度失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/schedules/{config_id}/stop", response_model=ScheduleActionResponse)
@cache_invalidate(["system_status", "system_dashboard", "schedule_list"])
async def stop_schedule(
    request: Request,
    config_id: int,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """停止任务调度"""
    try:
        success, message = await redis_services.scheduler.unregister_task(config_id)
        return {
            "success": success,
            "message": message,
            "config_id": config_id
        }
    except Exception as e:
        logger.error(f"停止调度失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/schedules/{config_id}/pause", response_model=ScheduleActionResponse)
@cache_invalidate(["system_status", "system_dashboard", "schedule_list"])
async def pause_schedule(
    request: Request,
    config_id: int,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """暂停任务调度"""
    try:
        success, message = await redis_services.scheduler.pause_task(config_id)
        return {
            "success": success,
            "message": message,
            "config_id": config_id
        }
    except Exception as e:
        logger.error(f"暂停调度失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/schedules/{config_id}/resume", response_model=ScheduleActionResponse)
@cache_invalidate(["system_status", "system_dashboard", "schedule_list"])
async def resume_schedule(
    request: Request,
    config_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """恢复任务调度"""
    try:
        config = await crud_task_config.get(db, config_id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        success, message = await redis_services.scheduler.resume_task(config)
        return {
            "success": success,
            "message": message,
            "config_id": config_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"恢复调度失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/schedules", response_model=ScheduleListResponse)
@cache_response("schedule_list")
async def get_all_schedules(
    request: Request,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取所有调度状态"""
    try:
        schedules = await redis_services.scheduler.get_all_schedules()
        return {
            "schedules": schedules,
            "total": len(schedules)
        }
    except Exception as e:
        logger.error(f"获取调度列表失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/schedules/{config_id}/history", response_model=ScheduleHistoryResponse)
async def get_schedule_history(
    config_id: int,
    limit: int = Query(50, ge=1, le=200, description="历史记录数量"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取调度历史"""
    try:
        history = await redis_services.scheduler.state.get_history(config_id, limit)
        return {
            "config_id": config_id,
            "history": history,
            "count": len(history)
        }
    except Exception as e:
        logger.error(f"获取调度历史失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/schedules/summary", response_model=ScheduleSummaryResponse)
async def get_schedule_summary(
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取调度摘要"""
    try:
        summary = await redis_services.scheduler.get_scheduler_summary()
        return summary
    except Exception as e:
        logger.error(f"获取调度摘要失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


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
    try:
        executions = await crud_task_execution.get_executions_by_config(db, config_id, limit)
        
        results = []
        for execution in executions:
            results.append({
                'id': execution.id,
                'task_id': execution.task_id,
                'config_id': execution.config_id,
                'is_success': execution.is_success,
                'started_at': execution.started_at,
                'completed_at': execution.completed_at,
                'duration_seconds': execution.duration_seconds,
                'result': execution.result,
                'error_message': execution.error_message,
                'created_at': execution.created_at
            })
        
        return {
            "config_id": config_id,
            "executions": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"获取配置执行记录失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/executions/recent", response_model=RecentExecutionsResponse)
async def get_recent_executions(
    hours: int = Query(24, ge=1, le=168, description="时间范围（小时）"),
    limit: int = Query(100, ge=1, le=500, description="记录数量"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取最近执行记录"""
    try:
        executions = await crud_task_execution.get_recent_executions(db, hours, limit)
        
        results = []
        for execution in executions:
            results.append({
                'id': execution.id,
                'task_id': execution.task_id,
                'config_id': execution.config_id,
                'config_name': execution.task_config.name if execution.task_config else None,
                'task_type': execution.task_config.task_type if execution.task_config else None,
                'is_success': execution.is_success,
                'started_at': execution.started_at,
                'completed_at': execution.completed_at,
                'duration_seconds': execution.duration_seconds,
                'error_message': execution.error_message,
                'created_at': execution.created_at
            })
        
        return {
            "hours": hours,
            "executions": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"获取最近执行记录失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/executions/failed", response_model=FailedExecutionsResponse)
async def get_failed_executions(
    days: int = Query(7, ge=1, le=90, description="时间范围（天）"),
    limit: int = Query(50, ge=1, le=200, description="记录数量"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取失败执行记录"""
    try:
        executions = await crud_task_execution.get_failed_executions(db, days, limit)
        
        results = []
        for execution in executions:
            results.append({
                'id': execution.id,
                'task_id': execution.task_id,
                'config_id': execution.config_id,
                'config_name': execution.task_config.name if execution.task_config else None,
                'task_type': execution.task_config.task_type if execution.task_config else None,
                'is_success': execution.is_success,
                'started_at': execution.started_at,
                'completed_at': execution.completed_at,
                'duration_seconds': execution.duration_seconds,
                'error_message': execution.error_message,
                'error_traceback': execution.error_traceback,
                'created_at': execution.created_at
            })
        
        return {
            "days": days,
            "failed_executions": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"获取失败执行记录失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/executions/stats")
@cache_stats_data("execution_stats")
async def get_execution_stats(
    request: Request,
    config_id: Optional[int] = Query(None, description="配置ID（可选）"),
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取执行统计"""
    try:
        if config_id:
            stats = await crud_task_execution.get_stats_by_config(db, config_id, days)
        else:
            stats = await crud_task_execution.get_global_stats(db, days)
        
        return stats
    except Exception as e:
        logger.error(f"获取执行统计失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/executions/{task_id}", response_model=ExecutionDetailResponse)
async def get_execution_by_task_id(
    task_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """通过task_id查询执行记录"""
    try:
        execution = await crud_task_execution.get_by_task_id(db, task_id)
        if not execution:
            raise HTTPException(status_code=404, detail="执行记录不存在")
        
        return {
            'id': execution.id,
            'task_id': execution.task_id,
            'config_id': execution.config_id,
            'config_name': execution.task_config.name if execution.task_config else None,
            'task_type': execution.task_config.task_type if execution.task_config else None,
            'is_success': execution.is_success,
            'started_at': execution.started_at,
            'completed_at': execution.completed_at,
            'duration_seconds': execution.duration_seconds,
            'result': execution.result,
            'error_message': execution.error_message,
            'error_traceback': execution.error_traceback,
            'created_at': execution.created_at
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询执行记录失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/executions/cleanup", response_model=ExecutionCleanupResponse)
@cache_invalidate(["execution_stats", "system_status", "system_dashboard"])
async def cleanup_old_executions(
    request: Request,
    days_to_keep: int = Query(90, ge=30, le=365, description="保留天数"),
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """清理旧执行记录（管理员）"""
    try:
        deleted_count = await crud_task_execution.cleanup_old_executions(db, days_to_keep)
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"清理了 {deleted_count} 条超过 {days_to_keep} 天的执行记录"
        }
    except Exception as e:
        logger.error(f"清理执行记录失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# 四、系统监控端点 /system
# 核心理念：系统状态和健康监控
# =============================================================================

@router.get("/system/status", response_model=SystemStatusResponse)
@cache_stats_data("system_status") 
async def get_system_status(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """系统状态总览"""
    try:
        # 1. 获取配置统计
        config_stats = await crud_task_config.get_stats(db)
        
        # 2. 获取调度状态摘要
        schedule_summary = await redis_services.scheduler.get_scheduler_summary()
        
        # 3. 获取执行统计
        execution_stats = await crud_task_execution.get_global_stats(db, days=7)
        
        return {
            "system_time": datetime.utcnow().isoformat(),
            "scheduler_status": "运行中",
            "database_status": "正常",
            "redis_status": "正常",
            
            "config_stats": config_stats,
            "schedule_summary": schedule_summary,
            "execution_stats": execution_stats
        }
    except Exception as e:
        logger.error(f"获取系统状态失败: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/system/health", response_model=SystemHealthResponse)
async def get_system_health(
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """系统健康检查"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {}
        }
        
        # 数据库健康检查
        try:
            await crud_task_config.get_total_count(db)
            health_status["components"]["database"] = {"status": "healthy", "message": "连接正常"}
        except Exception as e:
            health_status["components"]["database"] = {"status": "unhealthy", "message": str(e)}
            health_status["status"] = "degraded"
        
        # Redis健康检查
        try:
            summary = await redis_services.scheduler.get_scheduler_summary()
            if "error" in summary:
                health_status["components"]["redis"] = {"status": "unhealthy", "message": summary["error"]}
                health_status["status"] = "degraded"
            else:
                health_status["components"]["redis"] = {"status": "healthy", "message": "连接正常"}
        except Exception as e:
            health_status["components"]["redis"] = {"status": "unhealthy", "message": str(e)}
            health_status["status"] = "degraded"
        
        # 调度器健康检查
        try:
            schedules = await redis_services.scheduler.get_all_schedules()
            health_status["components"]["scheduler"] = {
                "status": "healthy", 
                "message": f"调度任务: {len(schedules)} 个"
            }
        except Exception as e:
            health_status["components"]["scheduler"] = {"status": "unhealthy", "message": str(e)}
            health_status["status"] = "degraded"
        
        return health_status
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.get("/system/enums", response_model=SystemEnumsResponse)
@cache_static("system_enums")
async def get_system_enums(
    request: Request,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取系统枚举值"""
    try:
        return {
            "scheduler_types": [t.value for t in SchedulerType],
            "schedule_actions": [a.value for a in ScheduleAction],
            "task_types": tr.TASKS.keys(),
            "schedule_statuses": ["active", "inactive", "paused", "error"]
        }
    except Exception as e:
        logger.error(f"获取枚举值失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/system/task-info", response_model=TaskInfoResponse)
@cache_static("task_info")
async def get_task_info(
    request: Request,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """获取所有任务的详细参数信息"""
    try:
        tasks_info = tr.list_all_tasks()
        
        return {
            "tasks": tasks_info,
            "total_count": len(tasks_info),
            "generated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"获取任务信息失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/system/dashboard", response_model=SystemDashboardResponse)
@cache_stats_data("system_dashboard")
async def get_system_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """全局统计仪表板"""
    try:
        # 1. 配置统计
        config_stats = await crud_task_config.get_stats(db)
        
        # 2. 调度状态摘要
        schedule_summary = await redis_services.scheduler.get_scheduler_summary()
        
        # 3. 执行统计（多个时间段）
        stats_7d = await crud_task_execution.get_global_stats(db, days=7)
        stats_30d = await crud_task_execution.get_global_stats(db, days=30)
        
        return {
            "dashboard": {
                "config_stats": config_stats,
                "schedule_summary": schedule_summary,
                "execution_stats": {
                    "last_7_days": stats_7d,
                    "last_30_days": stats_30d
                },
                "generated_at": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"获取仪表板数据失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))