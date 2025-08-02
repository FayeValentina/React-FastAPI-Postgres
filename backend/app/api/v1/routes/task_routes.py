from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated, List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import asyncio

from app.tasks.scheduler import task_scheduler
from app.tasks.manager import TaskManager
from app.schemas.task import JobInfo, TaskExecutionResponse, JobStatsResponse, TaskStatus
from app.db.base import get_async_session
from app.models.user import User
from app.dependencies.current_user import get_current_superuser
from app.utils.common import handle_error
from app.utils.task_status import calculate_job_status

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=List[JobInfo])
async def list_jobs(
    current_user: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_async_session)]
) -> List[JobInfo]:
    """获取所有任务列表（需要超级管理员权限）"""
    jobs = task_scheduler.get_jobs()
    scheduler_running = task_scheduler._running
    
    job_infos = []
    for job in jobs:
        # 计算任务状态
        status = await calculate_job_status(
            db=db,
            job_id=job.id,
            pending=job.pending,
            next_run_time=job.next_run_time,
            scheduler_running=scheduler_running
        )
        
        job_infos.append(JobInfo(
            id=job.id,
            name=job.name,
            trigger=str(job.trigger),
            next_run_time=job.next_run_time,
            pending=job.pending,
            status=status
        ))
    
    return job_infos


@router.get("/{job_id}", response_model=JobInfo)
async def get_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_async_session)]
) -> JobInfo:
    """获取任务详情（需要超级管理员权限）"""
    job = task_scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 计算任务状态
    status = await calculate_job_status(
        db=db,
        job_id=job.id,
        pending=job.pending,
        next_run_time=job.next_run_time,
        scheduler_running=task_scheduler._running
    )
    
    return JobInfo(
        id=job.id,
        name=job.name,
        trigger=str(job.trigger),
        next_run_time=job.next_run_time,
        pending=job.pending,
        status=status,
        func=job.func.__name__ if hasattr(job.func, '__name__') else str(job.func),
        args=job.args,
        kwargs=job.kwargs,
        executor=job.executor,
        max_instances=job.max_instances,
        misfire_grace_time=job.misfire_grace_time,
        coalesce=job.coalesce
    )


@router.get("/{job_id}/status")
async def get_job_status(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_async_session)]
) -> Dict[str, Any]:
    """快速获取任务状态（需要超级管理员权限）"""
    job = task_scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 计算任务状态
    status = await calculate_job_status(
        db=db,
        job_id=job.id,
        pending=job.pending,
        next_run_time=job.next_run_time,
        scheduler_running=task_scheduler._running
    )
    
    return {
        "job_id": job_id,
        "status": status,
        "pending": job.pending,
        "next_run_time": job.next_run_time,
        "scheduler_running": task_scheduler._running
    }


@router.post("/{job_id}/pause")
async def pause_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, str]:
    """暂停任务（需要超级管理员权限）"""
    try:
        task_scheduler.pause_job(job_id)
        return {"status": "paused", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{job_id}/resume")
async def resume_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, str]:
    """恢复任务（需要超级管理员权限）"""
    try:
        task_scheduler.resume_job(job_id)
        return {"status": "resumed", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{job_id}/run")
async def run_job_now(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, Any]:
    """立即运行任务（需要超级管理员权限）"""
    job = task_scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    try:
        # 立即执行任务
        # 注意：这里需要使用 asyncio.create_task 来异步执行
        asyncio.create_task(job.func())
        return {"status": "triggered", "job_id": job_id, "message": "任务已触发执行"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, str]:
    """删除任务（需要超级管理员权限）"""
    try:
        task_scheduler.remove_job(job_id)
        return {"status": "deleted", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_id}/executions", response_model=List[TaskExecutionResponse])
async def get_job_executions(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)],
    limit: int = Query(50, ge=1, le=200)
) -> List[TaskExecutionResponse]:
    """获取任务执行历史（需要超级管理员权限）"""
    try:
        manager = TaskManager(task_scheduler.scheduler)
        executions = await manager.get_job_executions(db, job_id, limit)
        return executions
    except Exception as e:
        raise handle_error(e)


@router.get("/{job_id}/stats", response_model=JobStatsResponse)
async def get_job_stats(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> JobStatsResponse:
    """获取任务执行统计（需要超级管理员权限）"""
    try:
        manager = TaskManager(task_scheduler.scheduler)
        stats = await manager.get_job_stats(db, job_id)
        return JobStatsResponse(**stats)
    except Exception as e:
        raise handle_error(e)


@router.get("/system/stats")
async def get_system_stats(
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, Any]:
    """获取系统任务统计概览（需要超级管理员权限）"""
    jobs = task_scheduler.get_jobs()
    
    # 统计各种任务类型
    task_types = {}
    for job in jobs:
        task_type = job.id.split('_')[0]  # 从job_id提取任务类型
        task_types[task_type] = task_types.get(task_type, 0) + 1
    
    return {
        "total_jobs": len(jobs),
        "active_jobs": len([j for j in jobs if not j.pending]),
        "paused_jobs": len([j for j in jobs if j.pending]),
        "task_types": task_types,
        "scheduler_running": task_scheduler._running
    }