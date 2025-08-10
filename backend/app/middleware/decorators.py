import asyncio
import time
import traceback
import logging
from functools import wraps
from typing import Callable, Any

from celery import Task

from app.crud import task_execution as crud_task_execution
from app.db.base import AsyncSessionLocal
from app.models.task_execution import ExecutionStatus

# 获取日志记录器
logger = logging.getLogger(__name__)

def run_async_from_sync(coro: Callable[..., Any]) -> Any:
    """
    一个工具函数，用于从同步代码中安全地运行异步协程。
    它会获取或创建一个事件循环来运行任务。
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # 如果事件循环已在运行（例如，在 Celery worker 的主线程中），
        # 使用 run_coroutine_threadsafe 是线程安全的方式。
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    else:
        # 如果没有正在运行的循环，我们可以安全地使用 run_until_complete。
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
    
    async with AsyncSessionLocal() as db:
        try:
            await crud_task_execution.create(db, obj_in=execution_data)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"记录任务执行失败: {e}", exc_info=True)


def task_executor(task_name: str):
    """
    一个装饰器，用于包装 Celery 任务，自动记录其执行状态。
    它能同时处理同步和异步的任务。
    """
    def decorator(func: Callable):
        # 检查被装饰的函数是同步还是异步
        if asyncio.iscoroutinefunction(func):
            # --- 异步任务的包装器 ---
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # 第一个参数是绑定的 Celery Task 实例
                task_instance: Task = args[0]
                job_id = task_instance.request.id
                
                # 从关键字参数中安全地获取 task_config_id
                task_config_id = kwargs.get("task_config_id")
                if not task_config_id:
                    logger.error(f"任务 '{task_name}' (ID: {job_id}) 启动失败: 未提供 'task_config_id'。")
                    return

                logger.info(f"任务 '{task_name}' (ID: {job_id}) 开始执行。")
                start_time = time.time()
                
                try:
                    # 使用 await 调用异步任务
                    result = await func(*args, **kwargs)
                    end_time = time.time()
                    logger.info(f"任务 '{task_name}' (ID: {job_id}) 成功完成。")
                    await _record_execution(
                        task_config_id=task_config_id,
                        job_id=job_id,
                        job_name=task_name,
                        status=ExecutionStatus.SUCCESS,
                        started_at=start_time,
                        completed_at=end_time,
                        result=result,
                    )
                    return result
                except Exception as e:
                    end_time = time.time()
                    error_msg = str(e)
                    error_tb = traceback.format_exc()
                    logger.error(f"任务 '{task_name}' (ID: {job_id}) 执行失败: {error_msg}", exc_info=True)
                    await _record_execution(
                        task_config_id=task_config_id,
                        job_id=job_id,
                        job_name=task_name,
                        status=ExecutionStatus.FAILED,
                        started_at=start_time,
                        completed_at=end_time,
                        error_message=error_msg,
                        error_traceback=error_tb,
                    )
                    raise

            return async_wrapper
        else:
            # --- 同步任务的包装器 ---
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                task_instance: Task = args[0]
                job_id = task_instance.request.id
                
                task_config_id = kwargs.get("task_config_id")
                if not task_config_id:
                    logger.error(f"任务 '{task_name}' (ID: {job_id}) 启动失败: 未提供 'task_config_id'。")
                    return

                logger.info(f"任务 '{task_name}' (ID: {job_id}) 开始执行。")
                start_time = time.time()
                
                try:
                    # 直接调用同步任务
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
            
            return sync_wrapper
    return decorator