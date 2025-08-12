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
                task_config_id=task_config_id,
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

def async_celery_task(task_name: str, celery_task_name: str):
    """
    整合的装饰器：将异步函数包装为Celery任务，并自动记录执行履历
    
    使用方法:
        @async_celery_task("清理过期令牌任务", "cleanup_expired_tokens_task")
        async def cleanup_expired_tokens_async(task_config_id: int, *, days_old: int = 7):
            # 异步业务逻辑
            pass
    
    参数说明:
        - task_name: 任务显示名称，用于日志和数据库记录
        - celery_task_name: Celery任务名称，用于任务注册
    
    注意事项:
        1. 异步函数的第一个参数必须是 task_config_id: int
        2. 其他参数建议使用关键字参数（keyword-only arguments），即在参数前加 *
        3. 装饰器会自动处理 Celery 的 bind=True 参数顺序问题
        4. 会自动记录任务执行履历到数据库
    """
    def decorator(async_func: Callable):
        # 导入这里，避免循环导入
        from app.celery_app import celery_app
        
        @celery_app.task(bind=True, name=celery_task_name)
        @wraps(async_func)
        def sync_wrapper(self, *args: Any, **kwargs: Any) -> Any:
            # self 是 Celery task instance（因为 bind=True）
            task_instance: Task = self
            job_id = task_instance.request.id
            
            # 提取 task_config_id
            # 因为 bind=True，self 已经被 Celery 处理，所以：
            # - args[0] 就是第一个实际参数（task_config_id）
            # - 或者从 kwargs 中获取
            task_config_id = kwargs.get("task_config_id") or (args[0] if args else None)
            if not task_config_id:
                logger.warning(f"任务 '{task_name}' (ID: {job_id}) 没有 task_config_id，可能是直接调用的任务。")
                task_config_id = -1

            # 准备传递给异步函数的参数
            # 如果 task_config_id 来自 kwargs，则从 kwargs 中移除
            # 如果 task_config_id 来自 args[0]，则移除 args[0]
            if "task_config_id" in kwargs:
                filtered_kwargs = {k: v for k, v in kwargs.items() if k != "task_config_id"}
                filtered_args = args
            else:
                filtered_kwargs = kwargs
                filtered_args = args[1:] if args else ()
            
            logger.info(f"任务 '{task_name}' (ID: {job_id}) 开始执行 (Config ID: {task_config_id})")
            start_time = time.time()
            
            try:
                # 在新的事件循环中运行异步函数
                # task_config_id 作为第一个参数传递
                result = asyncio.run(async_func(task_config_id, *filtered_args, **filtered_kwargs))
                end_time = time.time()
                logger.info(f"任务 '{task_name}' (ID: {job_id}) 成功完成")
                
                # 记录成功执行
                asyncio.run(
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
                
                # 记录失败执行
                asyncio.run(
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