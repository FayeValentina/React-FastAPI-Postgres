from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.schedule_manager import ScheduleManager
from app.models.user import User
from app.dependencies.current_user import get_current_superuser
from app.utils.common import handle_error
from app.crud.schedule_event import CRUDScheduleEvent
from app.crud.task_execution import CRUDTaskExecution
from app.schemas.schedule_event import ScheduleEventResponse
from app.db.base import get_async_session
from app.utils.task_status import get_task_status_calculator

router = APIRouter(prefix="/tasks", tags=["tasks"])

# 创建全局ScheduleManager实例
schedule_manager = ScheduleManager()


@router.get("", response_model=Dict[str, Any])
async def get_system_status(
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, Any]:
    """获取任务系统状态（需要超级管理员权限）"""
    try:
        # 使用ScheduleManager的增强健康检查方法
        return schedule_manager.get_system_health()
    except Exception as e:
        raise handle_error(e)


@router.get("/schedules", response_model=List[Dict[str, Any]])
async def list_schedules(
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)],
    enhanced: bool = Query(False, description="是否返回增强信息（状态、执行摘要）")
) -> List[Dict[str, Any]]:
    """获取调度任务列表，支持基础或增强模式（需要超级管理员权限）"""
    try:
        # 获取基础调度信息
        schedules = schedule_manager.scheduler_instance.get_all_schedules()
        
        # 转换为可序列化的格式
        result = []
        for job in schedules:
            config = schedule_manager.scheduler_instance.get_schedule_config(job.id)
            schedule_data = {
                "schedule_id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "pending": job.pending if hasattr(job, 'pending') else False,
                "config": config
            }
            
            # 如果需要增强信息，添加状态和执行摘要
            if enhanced:
                calculator = get_task_status_calculator()
                task_status = await calculator.calculate_job_status(
                    db=db,
                    job_id=job.id,
                    pending=job.pending if hasattr(job, 'pending') else False,
                    next_run_time=job.next_run_time,
                    scheduler_running=schedule_manager.scheduler_instance._running
                )
                
                execution_summary = await calculator.get_job_execution_summary(
                    db=db,
                    job_id=job.id,
                    hours=24
                )
                
                schedule_data.update({
                    "computed_status": task_status.value,
                    "execution_summary": execution_summary
                })
            
            result.append(schedule_data)
        
        return result
    except Exception as e:
        raise handle_error(e)


@router.get("/active-tasks", response_model=List[Dict[str, Any]])  
async def get_active_tasks(
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> List[Dict[str, Any]]:
    """获取活跃的Celery任务列表（需要超级管理员权限）"""
    try:
        # 使用MessageSender实例获取活跃任务
        return schedule_manager.message_sender_instance.get_active_tasks()
    except Exception as e:
        raise handle_error(e)


@router.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def get_job_details(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)],
    hours: int = Query(72, ge=1, le=168, description="统计时间范围（小时）"),
    events_limit: int = Query(20, ge=1, le=100, description="最近事件数量限制")
) -> Dict[str, Any]:
    """获取指定任务的完整详细信息（需要超级管理员权限）"""
    try:
        # 检查调度器是否运行
        scheduler_running = schedule_manager.scheduler_instance._running
        
        # 获取基础调度信息
        job = schedule_manager.scheduler_instance.get_schedule(job_id)
        if not job:
            # 如果调度器未运行，提供更友好的错误信息
            if not scheduler_running:
                raise HTTPException(
                    status_code=503, 
                    detail=f"调度器未运行，无法获取任务 '{job_id}' 的详细信息"
                )
            else:
                raise HTTPException(status_code=404, detail=f"任务 '{job_id}' 不存在")
        
        # 获取配置信息
        config = schedule_manager.scheduler_instance.get_schedule_config(job_id)
        
        # 计算任务状态
        calculator = get_task_status_calculator()
        task_status = await calculator.calculate_job_status(
            db=db,
            job_id=job_id,
            pending=job.pending if hasattr(job, 'pending') else False,
            next_run_time=job.next_run_time,
            scheduler_running=scheduler_running
        )
        
        # 获取执行摘要和最近事件
        execution_summary = await calculator.get_job_execution_summary(db, job_id, hours)
        recent_events = await calculator.get_job_recent_events(db, job_id, limit=events_limit)
        
        return {
            "job_info": {
                "id": job.id,
                "name": job.name,
                "trigger": str(job.trigger),
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "pending": job.pending if hasattr(job, 'pending') else False,
                "config": config
            },
            "computed_status": task_status.value,
            "execution_summary": execution_summary,
            "recent_events": recent_events
        }
    except Exception as e:
        raise handle_error(e)


@router.post("/cleanup")
async def manage_cleanup(
    current_user: Annotated[User, Depends(get_current_superuser)],
    action: str = Query("trigger", description="操作类型: trigger, create, update, remove"),
    days_old: int = Query(30, description="清理天数"),
    schedule_id: str = Query("cleanup_old_sessions", description="调度ID"),
    cron_expression: str = Query("0 2 * * *", description="Cron表达式")
) -> Dict[str, Any]:
    """统一的清理任务管理端点（需要超级管理员权限）"""
    try:
        if action == "trigger":
            # 手动触发清理任务
            task_id = schedule_manager.trigger_cleanup_with_validation(days_old)
            return {
                "message": "清理任务已启动",
                "task_id": task_id,
                "days_old": days_old,
                "status": "queued"
            }
        elif action in ["create", "update", "remove"]:
            # 管理清理任务调度
            return schedule_manager.manage_cleanup_schedule(
                action=action,
                schedule_id=schedule_id,
                days_old=days_old,
                cron_expression=cron_expression
            )
        else:
            raise HTTPException(status_code=400, detail="不支持的操作类型")
    except Exception as e:
        raise handle_error(e)


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, Any]:
    """获取Celery任务状态（需要超级管理员权限）"""
    try:
        # 使用MessageSender实例获取任务状态
        return schedule_manager.message_sender_instance.get_task_status(task_id)
    except Exception as e:
        raise handle_error(e)


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)],
    terminate: bool = Query(False, description="是否强制终止")
) -> Dict[str, Any]:
    """取消Celery任务（需要超级管理员权限）"""
    try:
        # 使用MessageSender实例撤销任务
        return schedule_manager.message_sender_instance.revoke_task(task_id, terminate)
    except Exception as e:
        raise handle_error(e)


@router.get("/events", response_model=List[ScheduleEventResponse])
async def get_schedule_events(
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)],
    job_id: str = Query(None, description="指定任务ID，不提供则获取所有任务事件"),
    hours: int = Query(24, ge=1, le=168, description="时间范围（小时）"),
    limit: int = Query(100, ge=1, le=500, description="结果数量限制")
) -> List[ScheduleEventResponse]:
    """统一的调度事件查询端点（需要超级管理员权限）"""
    try:
        if job_id:
            # 获取指定任务的事件
            events = await CRUDScheduleEvent.get_events_by_job(db, job_id, limit)
        else:
            # 获取最近的事件
            events = await CRUDScheduleEvent.get_recent_events(db, hours, limit)
        return events
    except Exception as e:
        raise handle_error(e)


@router.get("/executions", response_model=Dict[str, Any])
async def get_execution_data(
    current_user: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    include_stats: bool = Query(False, description="是否包含统计信息"),
    hours: int = Query(24, ge=1, le=168, description="执行历史时间范围（小时）"),
    stats_days: int = Query(7, ge=1, le=30, description="统计时间范围（天）")
) -> Dict[str, Any]:
    """统一的任务执行数据端点，支持历史记录和统计信息（需要超级管理员权限）"""
    try:
        result = {}
        
        # 获取执行历史
        executions = await CRUDTaskExecution.get_recent_executions(db, hours)
        result["executions"] = [
            {
                "job_id": exe.job_id,
                "job_name": exe.job_name,
                "status": exe.status,
                "started_at": exe.started_at,
                "completed_at": exe.completed_at,
                "duration_seconds": exe.duration_seconds,
                "result": exe.result,
                "error_message": exe.error_message
            }
            for exe in executions
        ]
        
        # 如果需要统计信息，添加统计数据
        if include_stats:
            stats = await CRUDTaskExecution.get_execution_stats(db, stats_days)
            result["stats"] = stats
        
        return result
    except Exception as e:
        raise handle_error(e)


# 新增的高级管理端点

@router.post("/schedules/batch-update")
async def batch_update_schedules(
    updates: List[Dict[str, Any]],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, Any]:
    """批量更新调度任务（需要超级管理员权限）"""
    try:
        return await schedule_manager.bulk_update_schedules(db, updates)
    except Exception as e:
        raise handle_error(e)


@router.get("/analysis")
async def get_system_analysis(
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, Any]:
    """获取系统分析报告，包括调度分布和优化建议（需要超级管理员权限）"""
    try:
        analysis = await schedule_manager.optimize_schedule_distribution()
        config_stats = schedule_manager.config_manager.get_stats()
        queue_status = {
            "scraping": {
                "length": schedule_manager.message_sender_instance.get_queue_length('scraping')
            },
            "cleanup": {
                "length": schedule_manager.message_sender_instance.get_queue_length('cleanup')
            },
            "default": {
                "length": schedule_manager.message_sender_instance.get_queue_length('default')
            }
        }
        
        return {
            "schedule_distribution": analysis,
            "config_stats": config_stats,
            "queue_status": queue_status
        }
    except Exception as e:
        raise handle_error(e)
