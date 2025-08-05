from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated, List, Dict, Any
from app.services.schedule_manager import ScheduleManager
from app.models.user import User
from app.dependencies.current_user import get_current_superuser
from app.utils.common import handle_error
from app.crud.schedule_event import CRUDScheduleEvent
from app.schemas.schedule_event import ScheduleEventResponse

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


@router.get("/schedule/{schedule_id}")
async def get_schedule_info(
    schedule_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, Any]:
    """获取指定调度任务信息（需要超级管理员权限）"""
    try:
        info = ScheduleManager.get_schedule_info(schedule_id)
        if not info:
            raise HTTPException(status_code=404, detail="调度任务不存在")
        return info
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
