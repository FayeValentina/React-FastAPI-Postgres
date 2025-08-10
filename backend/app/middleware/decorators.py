import asyncio
import time
import traceback
import logging
from functools import wraps
from typing import Callable, Any

from celery import Task
from app.models.task_execution import ExecutionStatus

logger = logging.getLogger(__name__)


def run_async_from_sync(coro: Callable[..., Any]) -> Any:
    """
    一个工具函数，用于从同步代码中安全地运行异步协程。
    
    专门为 Celery Worker 进程优化，确保每个进程有自己的事件循环
    """
    try:
        # 尝试获取当前事件循环
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 没有运行中的事件循环，创建新的
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # 如果事件循环已在运行，创建新的事件循环在新线程中运行
        # 这种情况不应该在 Celery Worker 中发生
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        # 正常情况：在当前线程的事件循环中运行
        return loop.run_until_complete(coro)


async def _record_execution(
    task_config_id: int,
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
    if task_config_id == -1:
        logger.info(f"任务 '{job_name}' (ID: {job_id}) 是直接调用任务，跳过数据库记录。")
        return
    
    from app.crud import task_execution as crud_task_execution
    from app.db.base import get_worker_session  # 使用 Worker 专用会话
    from app.schemas.task import TaskExecutionCreate
    
    duration = completed_at - started_at
    execution_data = TaskExecutionCreate(
        task_config_id=task_config_id,
        job_id=job_id,
        job_name=job_name,
        status=status,
        started_at=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(started_at)),
        completed_at=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(completed_at)),
        duration_seconds=duration,
        result=result,
        error_message=error_message,
        error_traceback=error_traceback,
    )
    
    async for db in get_worker_session():  # 使用 Worker 专用会话
        try:
            await crud_task_execution.create(db, obj_in=execution_data)
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
            
            task_config_id = kwargs.get("task_config_id")
            if not task_config_id:
                logger.warning(f"任务 '{task_name}' (ID: {job_id}) 没有 task_config_id，可能是直接调用的任务。")
                task_config_id = -1

            logger.info(f"任务 '{task_name}' (ID: {job_id}) 开始执行。")
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                end_time = time.time()
                logger.info(f"任务 '{task_name}' (ID: {job_id}) 成功完成。")
                run_async_from_sync(
                    _record_execution(
                        task_config_id=task_config_id,
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
                run_async_from_sync(
                    _record_execution(
                        task_config_id=task_config_id,
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