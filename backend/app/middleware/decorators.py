"""
装饰器模块 - 提供事件记录等通用装饰器
"""
import asyncio
import functools
import logging
from datetime import datetime
from typing import Any, Callable, Optional
import traceback

from app.db.base import AsyncSessionLocal
from app.crud.schedule_event import crud_schedule_event
from app.crud.task_execution import crud_task_execution
from app.models.schedule_event import ScheduleEventType
from app.models.task_execution import ExecutionStatus

logger = logging.getLogger(__name__)


def record_schedule_event(event_type: ScheduleEventType):
    """
    装饰器：记录调度事件
    用于APScheduler的事件处理器
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            task_config_id = None
            job_id = None
            job_name = None
            
            # 从参数中提取信息
            if args and hasattr(args[0], 'job_id'):
                event = args[0]
                job_id = event.job_id
                try:
                    task_config_id = int(job_id)
                except (ValueError, TypeError):
                    pass
            
            try:
                result = await func(*args, **kwargs)
                
                # 记录成功事件
                async with AsyncSessionLocal() as db:
                    await crud_schedule_event.create(
                        db,
                        task_config_id=task_config_id,
                        job_id=job_id or str(task_config_id) if task_config_id else None,
                        job_name=job_name or f"Task-{task_config_id}",
                        event_type=event_type,
                        result={'return_value': str(result)} if result else None
                    )
                
                return result
                
            except Exception as e:
                # 记录错误事件
                async with AsyncSessionLocal() as db:
                    await crud_schedule_event.create(
                        db,
                        task_config_id=task_config_id,
                        job_id=job_id or str(task_config_id) if task_config_id else None,
                        job_name=job_name or f"Task-{task_config_id}",
                        event_type=ScheduleEventType.ERROR,
                        error_message=str(e),
                        error_traceback=traceback.format_exc()
                    )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.create_task(async_wrapper(*args, **kwargs))
        
        # 根据函数类型返回对应的wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


def record_task_execution(task_name: str = None):
    """
    装饰器：记录任务执行
    用于Celery任务
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            task_config_id = None
            
            # 提取task_config_id
            if args:
                task_config_id = args[0] if isinstance(args[0], int) else None
            if not task_config_id and 'task_config_id' in kwargs:
                task_config_id = kwargs['task_config_id']
            
            # 获取Celery任务ID
            task_id = None
            try:
                from celery import current_task
                if current_task and hasattr(current_task, 'request'):
                    task_id = current_task.request.id
            except ImportError:
                pass
            
            job_name = task_name or func.__name__
            
            try:
                # 执行任务
                result = func(*args, **kwargs)
                
                # 记录成功执行
                asyncio.run(
                    _record_execution(
                        task_config_id=task_config_id,
                        job_id=task_id or f"{job_name}-{datetime.utcnow().timestamp()}",
                        job_name=job_name,
                        status=ExecutionStatus.SUCCESS,
                        started_at=start_time,
                        result={'return_value': result} if result else None
                    )
                )
                
                return result
                
            except Exception as e:
                # 记录失败执行
                asyncio.run(
                    _record_execution(
                        task_config_id=task_config_id,
                        job_id=task_id or f"{job_name}-{datetime.utcnow().timestamp()}",
                        job_name=job_name,
                        status=ExecutionStatus.FAILED,
                        started_at=start_time,
                        error_message=str(e),
                        error_traceback=traceback.format_exc()
                    )
                )
                raise
        
        return wrapper
    return decorator


async def _record_execution(
    task_config_id: Optional[int],
    job_id: str,
    job_name: str,
    status: ExecutionStatus,
    started_at: datetime,
    result: Optional[dict] = None,
    error_message: Optional[str] = None,
    error_traceback: Optional[str] = None
):
    """内部函数：记录任务执行"""
    try:
        async with AsyncSessionLocal() as db:
            completed_at = datetime.utcnow()
            duration_seconds = (completed_at - started_at).total_seconds()
            
            await crud_task_execution.create(
                db,
                task_config_id=task_config_id,
                job_id=job_id,
                job_name=job_name,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
                result=result,
                error_message=error_message,
                error_traceback=error_traceback
            )
    except Exception as e:
        logger.error(f"记录任务执行失败: {e}")