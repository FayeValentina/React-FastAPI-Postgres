"""
改进的任务装饰器 - 提供统一的任务处理功能
"""
import asyncio
import functools
import logging
from typing import Callable, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def with_timeout_handling(func: Callable) -> Callable:
    """
    改进的超时处理装饰器
    
    - 更新已存在的执行记录，而不是创建新记录
    - 支持没有config_id的场景
    - 正确获取TaskIQ分配的task_id
    
    Args:
        func: 要装饰的任务函数
        
    Returns:
        装饰后的函数
    """
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # 提取config_id参数
        config_id = kwargs.get('config_id')
        if config_id is None and args:
            # 通常config_id是第一个参数
            config_id = args[0] if isinstance(args[0], (int, type(None))) else None
        
        # 智能地查找 Context 对象
        from taskiq import Context
        context: Context = None
        
        # 从 args 中查找 Context 实例
        for arg in args:
            if isinstance(arg, Context):
                context = arg
                break
        
        # 如果 args 中没有，从 kwargs 中查找
        if not context:
            for kwarg_val in kwargs.values():
                if isinstance(kwarg_val, Context):
                    context = kwarg_val
                    break
        
        # 从 Context 中安全地获取 task_id
        real_task_id = None
        if context and hasattr(context, 'message') and context.message:
            real_task_id = context.message.task_id
        
        # 如果上下文中没有，再从 kwargs 中找备选
        if not real_task_id:
            real_task_id = kwargs.get('task_id')
        
        try:
            logger.debug(f"开始执行任务 {func.__name__} (config_id={config_id}, task_id={real_task_id})")
            result = await func(*args, **kwargs)
            
            # 成功时更新执行记录为SUCCESS状态
            if real_task_id:
                try:
                    await _update_execution_status(
                        task_id=real_task_id,
                        status="success",
                        completed_at=datetime.utcnow()
                    )
                except Exception as e:
                    logger.warning(f"更新成功状态失败: {e}")
            
            logger.debug(f"任务 {func.__name__} 执行成功 (config_id={config_id})")
            return result
            
        # 这里原本是捕获asyncio.TimeoutError 用来记录超时，后来发现TimeoutError发生在装饰器的外层，根本无法捕获，因此改为捕获asyncio.CancelledError
        except asyncio.CancelledError as e:
            logger.error(f"任务 {func.__name__} 被取消(可能是超时) config_id={config_id}, task_id={real_task_id}: {e}")
            
            # 更新执行记录为超时状态 (TaskIQ中取消通常意味着超时)
            await _handle_task_failure(
                config_id=config_id,
                task_id=real_task_id,
                task_name=func.__name__,
                status="timeout",
                error_message=f"任务被取消(超时): {str(e)}"
            )
            
            # 重新抛出原始异常，让TaskIQ转换为TimeoutError
            raise
            
        except Exception as e:
            # 处理其他异常（不包括超时）
            logger.error(f"任务 {func.__name__} 执行失败 config_id={config_id}, task_id={real_task_id}: {e}")
            
            # 更新执行记录为失败状态
            await _handle_task_failure(
                config_id=config_id,
                task_id=real_task_id,
                task_name=func.__name__,
                status="failed",
                error_message=str(e)
            )
            
            # 重新抛出原始异常
            raise
    
    return wrapper


async def _update_execution_status(
    task_id: str,
    status: str,
    completed_at: datetime = None,
    error_message: str = None
) -> bool:
    """更新已存在的执行记录状态"""
    try:
        from app.db.base import AsyncSessionLocal
        from app.crud.task_execution import crud_task_execution
        from app.models.task_execution import ExecutionStatus
        
        async with AsyncSessionLocal() as db:
            # 查找已存在的记录
            execution = await crud_task_execution.get_by_task_id(db, task_id)
            if execution:
                # 更新状态
                await crud_task_execution.update_status(
                    db=db,
                    execution_id=execution.id,
                    status=ExecutionStatus(status),
                    completed_at=completed_at or datetime.utcnow(),
                    error_message=error_message
                )
                logger.debug(f"已更新执行记录: task_id={task_id}, status={status}")
                return True
            else:
                logger.warning(f"未找到执行记录: task_id={task_id}")
                return False
                
    except Exception as e:
        logger.error(f"更新执行状态失败: {e}")
        return False


async def _handle_task_failure(
    config_id: Optional[int],
    task_id: Optional[str],
    task_name: str,
    status: str,
    error_message: str
) -> None:
    """处理任务失败 - 优先更新已存在记录，否则创建新记录"""
    try:
        # 如果有task_id，尝试更新已存在的记录
        if task_id:
            updated = await _update_execution_status(
                task_id=task_id,
                status=status,
                error_message=error_message
            )
            if updated:
                return
        
        # 如果没有找到已存在的记录，创建新记录
        await _create_failure_execution(
            config_id=config_id,
            task_id=task_id,
            task_name=task_name,
            status=status,
            error_message=error_message
        )
        
    except Exception as e:
        logger.error(f"处理任务失败记录失败: {e}")


async def _create_failure_execution(
    config_id: Optional[int],
    task_id: Optional[str],
    task_name: str,
    status: str,
    error_message: str
) -> None:
    """创建失败执行记录（仅在没有已存在记录时使用）"""
    try:
        from app.db.base import AsyncSessionLocal
        from app.crud.task_execution import crud_task_execution
        from app.models.task_execution import ExecutionStatus
        
        async with AsyncSessionLocal() as db:
            await crud_task_execution.create(
                db=db,
                config_id=config_id,
                task_id=task_id or f"{status}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                status=ExecutionStatus(status),
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                error_message=error_message
            )
            
        logger.info(f"已创建{status}执行记录: config_id={config_id}, task={task_name}")
        
    except Exception as e:
        logger.error(f"创建{status}执行记录失败: {e}")