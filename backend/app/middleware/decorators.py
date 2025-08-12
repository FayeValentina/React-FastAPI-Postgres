import asyncio
import time
import traceback
import logging
from functools import wraps
from typing import Callable, Any
from datetime import datetime

from celery import Task
from app.models.task_execution import ExecutionStatus

logger = logging.getLogger(__name__)

async def _record_execution(
    config_id: int,
    job_id: str,
    job_name: str,
    status: ExecutionStatus,
    started_at: float,
    completed_at: float,
    result: Any = None,
    error_message: str | None = None,
    error_traceback: str | None = None,
):
    """
    异步地将任务执行记录保存到数据库。
    """
    if config_id == -1:
        logger.info(f"任务 '{job_name}' (ID: {job_id}) 是直接调用任务，跳过数据库记录。")
        return
    
    from app.crud.task_execution import crud_task_execution
    from app.db.base import get_worker_session  # 使用 Worker 专用会话
    
    # 将时间戳转换为datetime对象
    started_at_dt = datetime.fromtimestamp(started_at)
    completed_at_dt = datetime.fromtimestamp(completed_at)
    duration = completed_at - started_at
    
    async for db in get_worker_session():  # 使用 Worker 专用会话
        try:
            await crud_task_execution.create(
                db=db,
                config_id=config_id,
                job_id=job_id,
                job_name=job_name,
                status=status,
                started_at=started_at_dt,
                completed_at=completed_at_dt,
                duration_seconds=duration,
                result=result,
                error_message=error_message,
                error_traceback=error_traceback
            )
            logger.info(f"任务执行记录已保存: {job_name} (ID: {job_id})")
        except Exception as e:
            logger.error(f"记录任务执行失败: {e}", exc_info=True)


def task_executor(task_name: str):
    """
    一个装饰器，用于包装 Celery 任务，自动记录其执行状态。
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            task_instance: Task = args[0]
            job_id = task_instance.request.id
            
            # config_id = kwargs.get("config_id")
            config_id = kwargs.get("config_id") or (args[1] if len(args) > 1 else None)
            if not config_id:
                logger.warning(f"任务 '{task_name}' (ID: {job_id}) 没有 config_id，可能是直接调用的任务。")
                config_id = -1

            logger.info(f"任务 '{task_name}' (ID: {job_id}) 开始执行。")
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                end_time = time.time()
                logger.info(f"任务 '{task_name}' (ID: {job_id}) 成功完成。")
                asyncio.run(
                    _record_execution(
                        config_id=config_id,
                        job_id=job_id,
                        job_name=task_name,
                        status=ExecutionStatus.SUCCESS,
                        started_at=start_time,
                        completed_at=end_time,
                        result=result,
                    )
                )
                return result
            except Exception as e:
                end_time = time.time()
                error_msg = str(e)
                error_tb = traceback.format_exc()
                logger.error(f"任务 '{task_name}' (ID: {job_id}) 执行失败: {error_msg}", exc_info=True)
                asyncio.run(
                    _record_execution(
                        config_id=config_id,
                        job_id=job_id,
                        job_name=task_name,
                        status=ExecutionStatus.FAILED,
                        started_at=start_time,
                        completed_at=end_time,
                        error_message=error_msg,
                        error_traceback=error_tb,
                    )
                )
                raise
        
        return wrapper
    return decorator