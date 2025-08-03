from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Annotated, List, Optional, Dict, Any, Union
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import asyncio

from app.tasks.scheduler import task_scheduler
from app.tasks.manager import TaskManager
from app.schemas.task import (
    JobInfo, TaskExecutionResponse, JobStatsResponse, TaskStatus,
    JobCreateRequest, JobScheduleUpdate
)
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


@router.get("/system")
async def get_system_info(
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)],
    include_health: bool = Query(True, description="是否包含健康状态"),
    include_stats: bool = Query(True, description="是否包含统计信息")
) -> Dict[str, Any]:
    """获取系统信息（需要超级管理员权限）"""
    jobs = task_scheduler.get_jobs()
    result = {}
    
    if include_stats:
        # 统计各种任务类型
        task_types = {}
        for job in jobs:
            task_type = job.id.split('_')[0]  # 从job_id提取任务类型
            task_types[task_type] = task_types.get(task_type, 0) + 1
        
        # 修正：使用 next_run_time 来判断暂停状态
        active_jobs = len([j for j in jobs if j.next_run_time is not None])
        paused_jobs = len([j for j in jobs if j.next_run_time is None and hasattr(j, 'trigger')])
        
        result["stats"] = {
            "total_jobs": len(jobs),
            "active_jobs": active_jobs,
            "paused_jobs": paused_jobs,
            "task_types": task_types,
            "scheduler_running": task_scheduler._running
        }
    
    if include_health:
        unhealthy_jobs = []
        
        for job in jobs:
            status = await calculate_job_status(
                db, job.id, job.pending, job.next_run_time, task_scheduler._running
            )
            
            # 检查异常状态
            if status in [TaskStatus.FAILED, TaskStatus.TIMEOUT, TaskStatus.MISFIRED]:
                unhealthy_jobs.append({
                    "job_id": job.id,
                    "name": job.name,
                    "status": status,
                    "next_run_time": job.next_run_time
                })
        
        result["health"] = {
            "total_jobs": len(jobs),
            "healthy_jobs": len(jobs) - len(unhealthy_jobs),
            "unhealthy_jobs": unhealthy_jobs,
            "scheduler_running": task_scheduler._running,
            "health_score": (len(jobs) - len(unhealthy_jobs)) / len(jobs) if jobs else 1.0
        }
    
    return result


@router.post("/batch")
async def batch_operation(
    current_user: Annotated[User, Depends(get_current_superuser)],
    action: str = Query(..., description="操作类型: pause/resume/delete"),
    job_ids: List[str] = Body(..., description="任务ID列表")
) -> Dict[str, Any]:
    """批量操作任务"""
    if action not in ["pause", "resume", "delete"]:
        raise HTTPException(status_code=400, detail="不支持的操作类型，支持的操作: pause/resume/delete")
    
    results = {}
    for job_id in job_ids:
        try:
            if action == "pause":
                task_scheduler.pause_job(job_id)
                results[job_id] = "paused"
            elif action == "resume":
                task_scheduler.resume_job(job_id)
                results[job_id] = "resumed"
            elif action == "delete":
                task_scheduler.remove_job(job_id)
                results[job_id] = "deleted"
        except Exception as e:
            results[job_id] = f"error: {str(e)}"
    
    return {"action": action, "results": results}

# 新增API端点
@router.post("/", response_model=JobInfo)
async def create_adhoc_job(
    job_data: JobCreateRequest,
    current_user: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_async_session)]
) -> JobInfo:
    """创建临时任务（一次性执行）"""
    try:
        # 生成任务ID
        job_id = f"adhoc_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # 添加任务
        task_scheduler.add_job_with_config(
            func=job_data.func,
            trigger=job_data.trigger,
            id=job_id,
            name=job_data.name,
            args=job_data.args,
            kwargs=job_data.kwargs,
            max_retries=job_data.max_retries,
            timeout=job_data.timeout,
            **job_data.trigger_args
        )
        
        # 获取创建的任务
        job = task_scheduler.get_job(job_id)
        if not job:
            raise HTTPException(status_code=500, detail="任务创建失败")
        
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
            status=status
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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



@router.post("/{job_id}/action")
async def perform_job_action(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)],
    action: str = Query(..., description="操作类型: pause/resume/run")
) -> Dict[str, Any]:
    """对任务执行操作（需要超级管理员权限）"""
    if action not in ["pause", "resume", "run"]:
        raise HTTPException(status_code=400, detail="不支持的操作类型，支持的操作: pause/resume/run")
    
    try:
        if action == "pause":
            task_scheduler.pause_job(job_id)
            return {"status": "paused", "job_id": job_id, "action": action}
        elif action == "resume":
            task_scheduler.resume_job(job_id)
            return {"status": "resumed", "job_id": job_id, "action": action}
        elif action == "run":
            job = task_scheduler.get_job(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="任务不存在")
            
            # 立即执行任务，传递正确的参数
            args = job.args or []
            kwargs = job.kwargs or {}
            
            # 使用 asyncio.create_task 来异步执行，传递正确的参数
            asyncio.create_task(job.func(*args, **kwargs))
            return {"status": "triggered", "job_id": job_id, "action": action, "message": "任务已触发执行"}
    except Exception as e:
        error_detail = f"执行失败: {str(e)}" if action == "run" else str(e)
        raise HTTPException(status_code=500 if action == "run" else 400, detail=error_detail)


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


@router.get("/{job_id}/history")
async def get_job_history(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)],
    format: str = Query("detailed", description="返回格式: detailed/logs"),
    limit: int = Query(50, ge=1, le=200)
) -> Union[List[TaskExecutionResponse], List[Dict[str, Any]]]:
    """获取任务执行历史（需要超级管理员权限）"""
    try:
        manager = TaskManager(task_scheduler.scheduler)
        executions = await manager.get_job_executions(db, job_id, limit)
        
        if format == "logs":
            # 返回日志格式
            logs = []
            for execution in executions:
                logs.append({
                    "timestamp": execution.started_at.isoformat(),
                    "level": "ERROR" if execution.status == "FAILED" else "INFO",
                    "message": execution.error_message if execution.error_message else f"任务执行{execution.status}",
                    "duration": execution.duration_seconds,
                    "result": execution.result
                })
            return logs
        else:
            # 返回详细执行记录
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


@router.patch("/{job_id}/schedule")
async def update_job_schedule(
    job_id: str,
    schedule_data: JobScheduleUpdate,
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, str]:
    """更新任务的调度时间"""
    job = task_scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    try:
        # 移除原任务
        old_func = job.func
        old_name = job.name
        old_args = job.args
        old_kwargs = job.kwargs
        
        task_scheduler.remove_job(job_id)
        
        # 重新添加任务
        trigger = schedule_data.trigger or str(job.trigger).split('[')[0]
        trigger_args = schedule_data.trigger_args or {}
        
        task_scheduler.add_job(
            func=old_func,
            trigger=trigger,
            id=job_id,
            name=old_name,
            args=old_args,
            kwargs=old_kwargs,
            **trigger_args
        )
        
        return {"status": "updated", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


