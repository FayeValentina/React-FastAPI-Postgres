# backend/app/core/timeout_decorator.py (使用新的Redis服务)
import asyncio
import functools
import logging
from typing import Optional, Callable
from datetime import datetime

from app.db.base import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.task_execution import crud_task_execution
from app.crud.task_config import crud_task_config
from app.models.task_execution import ExecutionStatus
from app.core.redis_manager import redis_services  # 使用新的Redis服务
from app.utils.common import get_current_time

logger = logging.getLogger(__name__)

def with_timeout(func: Callable):
    """
    任务超时装饰器 - 使用新的Redis超时监控服务
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # 获取config_id和task_id
        config_id = kwargs.get('config_id')
        task_id = kwargs.get('task_id')
        
        if not task_id:
            import uuid
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            kwargs['task_id'] = task_id
        
        # 统一创建 db session
        async with AsyncSessionLocal() as db:
            # 获取超时配置
            timeout_seconds = await _get_timeout_seconds(db, config_id)
            
            # 如果没有超时设置，直接执行
            if not timeout_seconds:
                return await func(*args, **kwargs)
            
            # 记录开始时间
            started_at = get_current_time()
            
            # 注册到新的Redis超时监控服务
            if config_id:
                await redis_services.timeout.add_task(
                    task_id=task_id,
                    config_id=config_id,
                    timeout_seconds=timeout_seconds,
                    started_at=started_at
                )
            
            try:
                # 使用asyncio.wait_for实现超时
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
                
                # 任务成功完成，更新状态
                await _update_task_status(
                    db=db,
                    task_id=task_id,
                    status=ExecutionStatus.SUCCESS,
                    started_at=started_at,
                    result={"return_value": result} if result is not None else None
                )
                
                # 记录到调度历史
                await redis_services.history.add_history_event(
                    config_id=config_id,
                    event_data={
                        "task_id": task_id,
                        "status": "success",
                        "started_at": started_at.isoformat(),
                        "completed_at": get_current_time().isoformat(),
                        "result": result
                    }
                )
                
                return result
                
            except asyncio.TimeoutError:
                # 任务超时
                error_msg = f"任务超时 (限制: {timeout_seconds}秒)"
                logger.error(f"任务 {task_id} {error_msg}")
                
                await _update_task_status(
                    db=db,
                    task_id=task_id,
                    status=ExecutionStatus.TIMEOUT,
                    started_at=started_at,
                    error_message=error_msg
                )
                
                # 记录到调度历史
                await redis_services.history.add_history_event(
                    config_id=config_id,
                    event_data={
                        "task_id": task_id,
                        "status": "timeout",
                        "started_at": started_at.isoformat(),
                        "error": error_msg
                    }
                )
                
                raise
                
            except Exception as e:
                # 其他错误
                logger.error(f"任务 {task_id} 执行失败: {e}")
                
                await _update_task_status(
                    db=db,
                    task_id=task_id,
                    status=ExecutionStatus.FAILED,
                    started_at=started_at,
                    error_message=str(e)
                )
                
                # 记录到调度历史
                await redis_services.history.add_history_event(
                    config_id=config_id,
                    event_data={
                        "task_id": task_id,
                        "status": "failed",
                        "started_at": started_at.isoformat(),
                        "error": str(e)
                    }
                )
                
                raise
                
            finally:
                # 从Redis注销任务（使用新的服务）
                await redis_services.timeout.remove_task(task_id)
                
                # 更新调度状态
                if config_id:
                    status = "idle"  # 任务完成后设置为空闲
                    await redis_services.history.update_status(config_id, status)
    
    return wrapper

async def _get_timeout_seconds(db: AsyncSession, config_id: Optional[int]) -> Optional[int]:
    """获取任务超时配置"""
    if not config_id:
        return None
    
    try:
        config = await crud_task_config.get(db, config_id)
        return config.timeout_seconds if config else None
    except Exception as e:
        logger.warning(f"获取超时配置失败: {e}")
        return None

async def _update_task_status(
    db: AsyncSession,
    task_id: str,
    status: ExecutionStatus,
    started_at: datetime,
    result: Optional[dict] = None,
    error_message: Optional[str] = None
):
    """更新任务执行状态"""
    try:
        execution = await crud_task_execution.get_by_task_id(db, task_id)
        if execution:
            completed_at = get_current_time()
            duration = (completed_at - started_at).total_seconds()
            
            await crud_task_execution.update_status(
                db=db,
                execution_id=execution.id,
                status=status,
                completed_at=completed_at,
                duration_seconds=duration,
                result=result,
                error_message=error_message
            )
    except Exception as e:
        logger.error(f"更新任务状态失败: {e}")