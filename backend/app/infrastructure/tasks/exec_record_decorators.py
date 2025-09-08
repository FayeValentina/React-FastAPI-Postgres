"""
改进的任务装饰器 - 提供统一的任务处理功能
"""
import asyncio
import functools
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from taskiq import Context, TaskiqDepends

logger = logging.getLogger(__name__)


async def _create_execution_record(
    config_id: Optional[int],
    task_id: str,
    is_success: bool,
    started_at: datetime,
    completed_at: datetime,
    duration_seconds: Optional[float] = None,
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> None:
    """创建任务执行记录（原 executor 功能）"""
    try:
        from app.infrastructure.database.postgres_base import AsyncSessionLocal
        from app.modules.tasks.repository import crud_task_execution

        async with AsyncSessionLocal() as db:
            await crud_task_execution.create(
                db=db,
                config_id=config_id,
                task_id=task_id,
                is_success=is_success,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
                result=result,
                error_message=error_message,
            )
            logger.debug(
                f"已创建执行记录: task_id={task_id}, success={is_success}"
            )
    except Exception:
        logger.exception("创建执行记录失败")
        raise


def execution_handler(func: Callable) -> Callable:
    """
    改进的超时处理装饰器 - 使用新的 is_success 记录方式

    Args:
        func: 要装饰的任务函数

    Returns:
        装饰后的函数
    """

    @functools.wraps(func)
    async def wrapper(
        *args,
        context: Context = TaskiqDepends(),
        **kwargs,
    ) -> Any:
        # 提取 config_id 参数
        config_id = kwargs.get("config_id")
        if config_id is None and args:
            # 通常 config_id 是第一个参数
            config_id = args[0] if isinstance(args[0], (int, type(None))) else None

        real_task_id = None
        if context and getattr(context, "message", None):
            real_task_id = context.message.task_id

        start_time = datetime.utcnow()

        try:
            logger.debug(
                f"开始执行任务 {func.__name__} (config_id={config_id}, task_id={real_task_id})"
            )
            result = await func(*args, context=context, **kwargs)

            # 成功时记录
            if real_task_id:
                await _create_execution_record(
                    config_id=config_id,
                    task_id=real_task_id,
                    is_success=True,
                    started_at=start_time,
                    completed_at=datetime.utcnow(),
                    result={"return_value": result} if result is not None else None,
                )

            logger.debug(
                f"任务 {func.__name__} 执行成功 (config_id={config_id})"
            )
            return result

        except asyncio.CancelledError as e:
            logger.error(
                f"任务 {func.__name__} 被取消(可能是超时) config_id={config_id}, task_id={real_task_id}: {e}"
            )

            # 取消时记录失败
            if real_task_id:
                await _create_execution_record(
                    config_id=config_id,
                    task_id=real_task_id,
                    is_success=False,
                    started_at=start_time,
                    completed_at=datetime.utcnow(),
                    error_message=f"任务被取消(超时): {str(e)}",
                )
            raise

        except Exception as e:
            # 处理其他异常（不包括超时）
            logger.error(
                f"任务 {func.__name__} 执行失败 config_id={config_id}, task_id={real_task_id}: {e}"
            )

            # 失败时记录
            if real_task_id:
                await _create_execution_record(
                    config_id=config_id,
                    task_id=real_task_id,
                    is_success=False,
                    started_at=start_time,
                    completed_at=datetime.utcnow(),
                    error_message=str(e),
                )

            # 重新抛出原始异常
            raise

    return wrapper

