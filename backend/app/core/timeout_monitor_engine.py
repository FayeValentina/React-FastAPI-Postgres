"""
任务超时中间件
为任务执行提供超时保护和监控
"""
import asyncio
import functools
import logging
from typing import Any, Callable, Optional, Dict
from datetime import datetime

from app.db.base import AsyncSessionLocal
from app.crud.task_execution import crud_task_execution
from app.models.task_execution import ExecutionStatus
from app.utils.common import get_current_time

logger = logging.getLogger(__name__)


def timeout_wrapper(timeout_seconds: Optional[int] = None):
    """
    任务超时装饰器
    
    Args:
        timeout_seconds: 超时时间(秒)，如果为None则从任务配置中获取
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 从参数中获取config_id (通常是第一个参数)
            config_id = args[0] if args else kwargs.get('config_id')
            
            # 如果没有指定超时时间，尝试从数据库获取
            effective_timeout = timeout_seconds
            if effective_timeout is None and config_id:
                effective_timeout = await _get_timeout_from_config(config_id)
            
            # 如果仍然没有超时时间，直接执行任务
            if effective_timeout is None:
                return await func(*args, **kwargs)
            
            # 使用asyncio.wait_for实现超时控制
            try:
                logger.debug(f"执行任务 {func.__name__} (config_id={config_id}) 超时限制: {effective_timeout}秒")
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=effective_timeout
                )
                return result
                
            except asyncio.TimeoutError:
                error_msg = f"任务 {func.__name__} 执行超时 (超时限制: {effective_timeout}秒)"
                logger.error(error_msg)
                
                # 更新数据库中的任务状态为超时
                await _mark_task_timeout(config_id, error_msg)
                
                # 抛出超时异常
                raise asyncio.TimeoutError(error_msg)
                
        return wrapper
    return decorator


async def _get_timeout_from_config(config_id: int) -> Optional[int]:
    """
    从任务配置中获取超时时间
    
    Args:
        config_id: 任务配置ID
        
    Returns:
        超时时间(秒)，如果未配置返回None
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


async def _mark_task_timeout(config_id: Optional[int], error_message: str):
    """
    标记任务为超时状态
    
    Args:
        config_id: 任务配置ID
        error_message: 错误信息
    """
    if not config_id:
        return
        
    try:
        async with AsyncSessionLocal() as db:
            # 查找最近的运行中任务
            from sqlalchemy import select, and_
            from app.models.task_execution import TaskExecution
            
            result = await db.execute(
                select(TaskExecution)
                .where(
                    and_(
                        TaskExecution.config_id == config_id,
                        TaskExecution.status == ExecutionStatus.RUNNING
                    )
                )
                .order_by(TaskExecution.started_at.desc())
                .limit(1)
            )
            
            execution = result.scalar_one_or_none()
            if execution:
                await crud_task_execution.update_status(
                    db=db,
                    execution_id=execution.id,
                    status=ExecutionStatus.TIMEOUT,
                    completed_at=get_current_time(),
                    error_message=error_message
                )
                logger.info(f"已标记任务执行 {execution.id} 为超时状态")
            
    except Exception as e:
        logger.error(f"标记任务超时状态失败: {e}")


class TaskTimeoutMonitor:
    """
    任务超时监控器
    用于在任务执行过程中实时监控超时情况
    """
    
    def __init__(self):
        self._running_tasks: Dict[str, Dict[str, Any]] = {}
        self._monitor_interval = 30  # 监控间隔(秒)
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def start_monitor(self):
        """启动超时监控"""
        if self._monitor_task and not self._monitor_task.done():
            return
        
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("任务超时监控器已启动")
    
    async def stop_monitor(self):
        """停止超时监控"""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        self._running_tasks.clear()
        logger.info("任务超时监控器已停止")
    
    def register_task(self, task_id: str, config_id: int, timeout_seconds: Optional[int], started_at: datetime):
        """
        注册任务到监控器
        
        Args:
            task_id: 任务ID
            config_id: 任务配置ID
            timeout_seconds: 超时时间
            started_at: 开始时间
        """
        if timeout_seconds is None:
            return
        
        self._running_tasks[task_id] = {
            "config_id": config_id,
            "timeout_seconds": timeout_seconds,
            "started_at": started_at,
            "registered_at": get_current_time()
        }
        
        logger.debug(f"已注册任务到超时监控: {task_id} (超时: {timeout_seconds}秒)")
    
    def unregister_task(self, task_id: str):
        """
        从监控器中移除任务
        
        Args:
            task_id: 任务ID
        """
        if task_id in self._running_tasks:
            del self._running_tasks[task_id]
            logger.debug(f"已从超时监控中移除任务: {task_id}")
    
    async def _monitor_loop(self):
        """监控循环"""
        while True:
            try:
                await self._check_timeouts()
                await asyncio.sleep(self._monitor_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"超时监控循环出错: {e}")
                await asyncio.sleep(self._monitor_interval)
    
    async def _check_timeouts(self):
        """检查超时任务"""
        current_time = get_current_time()
        timeout_tasks = []
        
        for task_id, task_info in self._running_tasks.items():
            running_time = (current_time - task_info["started_at"]).total_seconds()
            
            if running_time > task_info["timeout_seconds"]:
                timeout_tasks.append((task_id, task_info))
                logger.warning(
                    f"检测到超时任务: {task_id}, "
                    f"运行时间: {running_time:.1f}秒, "
                    f"超时阈值: {task_info['timeout_seconds']}秒"
                )
        
        # 处理超时任务
        for task_id, task_info in timeout_tasks:
            await _mark_task_timeout(
                task_info["config_id"],
                f"任务运行超时 (运行时间: {(current_time - task_info['started_at']).total_seconds():.1f}秒)"
            )
            self.unregister_task(task_id)


# 全局超时监控器实例
timeout_monitor = TaskTimeoutMonitor()


# 便捷装饰器
def with_timeout(timeout_seconds: Optional[int] = None):
    """
    便捷的超时装饰器
    
    Args:
        timeout_seconds: 超时时间(秒)
    """
    return timeout_wrapper(timeout_seconds)


# 上下文管理器
class TaskTimeoutContext:
    """
    任务超时上下文管理器
    用于在 with 语句中自动注册和注销任务
    """
    
    def __init__(self, task_id: str, config_id: int, timeout_seconds: Optional[int]):
        self.task_id = task_id
        self.config_id = config_id
        self.timeout_seconds = timeout_seconds
        self.started_at = None
    
    async def __aenter__(self):
        self.started_at = get_current_time()
        timeout_monitor.register_task(
            self.task_id, 
            self.config_id, 
            self.timeout_seconds, 
            self.started_at
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        timeout_monitor.unregister_task(self.task_id)
        
        # 如果是超时异常，不需要额外处理
        if exc_type is asyncio.TimeoutError:
            logger.info(f"任务 {self.task_id} 超时退出")