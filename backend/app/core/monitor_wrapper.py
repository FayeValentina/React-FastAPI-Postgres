"""
任务包装器
为所有任务提供统一的状态管理和超时处理
"""
import asyncio
import functools
import logging
import traceback
from typing import Any, Callable, Optional, Dict
from datetime import datetime

from app.db.base import AsyncSessionLocal
from app.crud.task_execution import crud_task_execution
from app.models.task_execution import ExecutionStatus
from app.utils.common import get_current_time
from app.core.timeout_monitor_engine import timeout_monitor

logger = logging.getLogger(__name__)


def task_wrapper(func: Callable):
    """
    任务包装装饰器，为所有任务提供统一的状态管理
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # 从参数中获取config_id和task_id
        config_id = args[0] if args else kwargs.get('config_id')
        
        # 生成或获取task_id (如果没有则生成一个)
        import uuid
        task_id = kwargs.get('task_id', f"task_{uuid.uuid4().hex[:8]}")
        
        # 获取任务配置信息
        timeout_seconds = None
        if config_id:
            timeout_seconds = await _get_timeout_from_config(config_id)
        
        async with AsyncSessionLocal() as db:
            execution = None
            try:
                # 查找现有的任务执行记录
                execution = await crud_task_execution.get_by_task_id(db, task_id)
                
                if execution:
                    # 更新为实际开始执行状态
                    logger.info(f"任务 {task_id} 开始执行 (config_id={config_id})")
                    await crud_task_execution.update_status(
                        db=db,
                        execution_id=execution.id,
                        status=ExecutionStatus.RUNNING,
                        started_at=get_current_time()
                    )
                    
                    # 注册到超时监控器
                    if timeout_seconds:
                        timeout_monitor.register_task(
                            task_id, 
                            config_id, 
                            timeout_seconds, 
                            execution.started_at
                        )
                
                # 执行任务
                if timeout_seconds:
                    # 使用asyncio.wait_for实现超时控制
                    try:
                        result = await asyncio.wait_for(
                            func(*args, **kwargs),
                            timeout=timeout_seconds
                        )
                    except asyncio.TimeoutError:
                        error_msg = f"任务 {func.__name__} 执行超时 (超时限制: {timeout_seconds}秒)"
                        logger.error(error_msg)
                        
                        # 更新为超时状态
                        if execution:
                            await crud_task_execution.update_status(
                                db=db,
                                execution_id=execution.id,
                                status=ExecutionStatus.TIMEOUT,
                                completed_at=get_current_time(),
                                error_message=error_msg
                            )
                        
                        # 从监控器移除
                        timeout_monitor.unregister_task(task_id)
                        raise asyncio.TimeoutError(error_msg)
                else:
                    # 无超时限制，直接执行
                    result = await func(*args, **kwargs)
                
                # 任务成功完成
                if execution:
                    completed_at = get_current_time()
                    duration = (completed_at - execution.started_at).total_seconds() if execution.started_at else None
                    
                    await crud_task_execution.update_status(
                        db=db,
                        execution_id=execution.id,
                        status=ExecutionStatus.SUCCESS,
                        completed_at=completed_at,
                        duration_seconds=duration,
                        result={"return_value": result} if result is not None else None
                    )
                    
                    logger.info(f"任务 {task_id} 成功完成 (耗时: {duration:.2f}秒)")
                
                # 从监控器移除
                timeout_monitor.unregister_task(task_id)
                
                return result
                
            except Exception as e:
                # 任务执行失败
                error_msg = str(e)
                error_trace = traceback.format_exc()
                
                # 确定失败类型
                status = ExecutionStatus.TIMEOUT if isinstance(e, asyncio.TimeoutError) else ExecutionStatus.FAILED
                
                if execution:
                    completed_at = get_current_time()
                    duration = (completed_at - execution.started_at).total_seconds() if execution.started_at else None
                    
                    await crud_task_execution.update_status(
                        db=db,
                        execution_id=execution.id,
                        status=status,
                        completed_at=completed_at,
                        duration_seconds=duration,
                        error_message=error_msg,
                        error_traceback=error_trace
                    )
                
                # 从监控器移除
                timeout_monitor.unregister_task(task_id)
                
                logger.error(f"任务 {task_id} 执行失败: {error_msg}")
                raise
    
    return wrapper


async def _get_timeout_from_config(config_id: int) -> Optional[int]:
    """
    从任务配置中获取超时时间
    """
    try:
        async with AsyncSessionLocal() as db:
            from app.crud.task_config import crud_task_config
            config = await crud_task_config.get(db, config_id)
            if config:
                return config.timeout_seconds
    except Exception as e:
        logger.warning(f"获取任务配置 {config_id} 的超时时间失败: {e}")
    
    return None


def timeout_monitor(func: Callable):
    """
    便捷装饰器，为任务添加完整的状态管理
    """
    return task_wrapper(func)