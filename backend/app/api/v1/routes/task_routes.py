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


@router.get("", response_model=Dict[str, Any])
async def get_system_status(
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, Any]:
    """获取任务系统状态（需要超级管理员权限）"""
    try:
        status = ScheduleManager.get_system_status()
        return status
    except Exception as e:
        raise handle_error(e)


@router.get("/schedules", response_model=List[Dict[str, Any]])
async def list_schedules(
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> List[Dict[str, Any]]:
    """获取所有调度任务列表（需要超级管理员权限）"""
    try:
        schedules = ScheduleManager.get_all_schedules()
        return schedules
    except Exception as e:
        raise handle_error(e)


@router.get("/schedules/enhanced", response_model=List[Dict[str, Any]])
async def list_schedules_enhanced(
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> List[Dict[str, Any]]:
    """获取增强的调度任务列表，包含状态和执行摘要（需要超级管理员权限）"""
    try:
        schedules = ScheduleManager.get_all_schedules()
        
        # 为每个调度任务计算状态和执行摘要
        calculator = get_task_status_calculator()
        enhanced_schedules = []
        
        for schedule in schedules:
            # 计算任务状态
            task_status = await calculator.calculate_job_status(
                db=db,
                job_id=schedule["schedule_id"],
                pending=schedule["pending"],
                next_run_time=schedule["next_run_time"],
                scheduler_running=True  # 从系统状态获取
            )
            
            # 获取执行摘要
            execution_summary = await calculator.get_job_execution_summary(
                db=db,
                job_id=schedule["schedule_id"],
                hours=24
            )
            
            enhanced_schedule = {
                **schedule,
                "computed_status": task_status.value,
                "execution_summary": execution_summary
            }
            enhanced_schedules.append(enhanced_schedule)
        
        return enhanced_schedules
    except Exception as e:
        raise handle_error(e)


@router.get("/active-tasks", response_model=List[Dict[str, Any]])  
async def get_active_tasks(
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> List[Dict[str, Any]]:
    """获取活跃的Celery任务列表（需要超级管理员权限）"""
    try:
        tasks = ScheduleManager.get_active_tasks()
        return tasks
    except Exception as e:
        raise handle_error(e)


@router.get("/schedule/{schedule_id}", response_model=Dict[str, Any])
async def get_schedule_info(
    schedule_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, Any]:
    """获取指定调度任务详细信息（需要超级管理员权限）"""
    try:
        info = ScheduleManager.get_schedule_info(schedule_id)
        if not info:
            raise HTTPException(status_code=404, detail="调度任务不存在")
        
        # 增强信息
        calculator = get_task_status_calculator()
        
        # 计算任务状态
        task_status = await calculator.calculate_job_status(
            db=db,
            job_id=schedule_id,
            pending=info["pending"],
            next_run_time=info["next_run_time"],
            scheduler_running=True
        )
        
        # 获取执行摘要和最近事件
        execution_summary = await calculator.get_job_execution_summary(db, schedule_id, hours=72)
        recent_events = await calculator.get_job_recent_events(db, schedule_id, limit=10)
        
        enhanced_info = {
            **info,
            "computed_status": task_status.value,
            "execution_summary": execution_summary,
            "recent_events": recent_events
        }
        
        return enhanced_info
    except Exception as e:
        raise handle_error(e)


@router.post("/cleanup")
async def trigger_cleanup_task(
    current_user: Annotated[User, Depends(get_current_superuser)],
    days_old: int = Query(30, description="删除多少天前的数据")
) -> Dict[str, Any]:
    """手动触发清理任务"""
    try:
        task_id = ScheduleManager.trigger_cleanup_task(days_old)
        return {
            "message": "清理任务已启动",
            "task_id": task_id,
            "days_old": days_old,
            "status": "queued"
        }
    except Exception as e:
        raise handle_error(e)


@router.get("/task/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, Any]:
    """获取Celery任务状态（需要超级管理员权限）"""
    try:
        status = ScheduleManager.get_task_status(task_id)
        return status
    except Exception as e:
        raise handle_error(e)


@router.post("/task/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)],
    terminate: bool = Query(False, description="是否强制终止")
) -> Dict[str, Any]:
    """取消Celery任务（需要超级管理员权限）"""
    try:
        result = ScheduleManager.cancel_task(task_id, terminate)
        return result
    except Exception as e:
        raise handle_error(e)


@router.get("/schedule-events/{job_id}", response_model=List[ScheduleEventResponse])
async def get_schedule_events(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)],
    limit: int = Query(50, ge=1, le=200)
) -> List[ScheduleEventResponse]:
    """获取指定任务的调度事件历史"""
    try:
        events = await CRUDScheduleEvent.get_events_by_job(db, job_id, limit)
        return events
    except Exception as e:
        raise handle_error(e)


@router.get("/schedule-events", response_model=List[ScheduleEventResponse])
async def get_recent_schedule_events(
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)],
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, ge=1, le=500)
) -> List[ScheduleEventResponse]:
    """获取最近的调度事件"""
    try:
        events = await CRUDScheduleEvent.get_recent_events(db, hours, limit)
        return events
    except Exception as e:
        raise handle_error(e)


@router.get("/executions", response_model=List[Dict[str, Any]])
async def get_task_executions(
    current_user: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    hours: int = Query(24, ge=1, le=168)
) -> List[Dict[str, Any]]:
    """获取任务执行历史"""
    try:
        executions = await CRUDTaskExecution.get_recent_executions(db, hours)
        return [
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
    except Exception as e:
        raise handle_error(e)


@router.get("/execution-stats", response_model=Dict[str, Any])
async def get_execution_stats(
    current_user: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    days: int = Query(7, ge=1, le=30)
) -> Dict[str, Any]:
    """获取任务执行统计"""
    try:
        stats = await CRUDTaskExecution.get_execution_stats(db, days)
        return stats
    except Exception as e:
        raise handle_error(e)


@router.get("/job/{job_id}/summary", response_model=Dict[str, Any])
async def get_job_summary(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)],
    hours: int = Query(24, ge=1, le=168, description="统计时间范围（小时）")
) -> Dict[str, Any]:
    """获取指定任务的详细摘要信息"""
    try:
        calculator = get_task_status_calculator()
        
        # 获取基本调度信息
        schedule_info = ScheduleManager.get_schedule_info(job_id)
        if not schedule_info:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 计算状态
        task_status = await calculator.calculate_job_status(
            db=db,
            job_id=job_id,
            pending=schedule_info["pending"],
            next_run_time=schedule_info["next_run_time"],
            scheduler_running=True
        )
        
        # 获取执行摘要和最近事件
        execution_summary = await calculator.get_job_execution_summary(db, job_id, hours)
        recent_events = await calculator.get_job_recent_events(db, job_id, limit=20)
        
        return {
            "job_info": schedule_info,
            "computed_status": task_status.value,
            "execution_summary": execution_summary,
            "recent_events": recent_events
        }
    except Exception as e:
        raise handle_error(e)
