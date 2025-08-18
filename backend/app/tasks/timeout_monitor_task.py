# backend/app/tasks/timeout_monitor_task.py (使用新的Redis服务)
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.broker import broker
from app.db.base import AsyncSessionLocal
from app.crud.task_execution import crud_task_execution
from app.crud.task_config import crud_task_config
from app.models.task_execution import ExecutionStatus, TaskExecution
from app.models.task_config import TaskConfig
from app.core.redis_manager import redis_services  # 使用新的Redis服务
from app.utils.common import get_current_time
from sqlalchemy import select

logger = logging.getLogger(__name__)

@broker.task(
    task_name="timeout_monitor",
    queue="monitor",
    retry_on_error=False,  # 监控任务不重试
)
async def timeout_monitor_task(
    config_id: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    超时监控任务 - 使用新的Redis超时监控服务
    """
    logger.info("开始执行超时监控...")
    
    # 使用新的Redis服务获取超时任务
    timeout_tasks = await redis_services.timeout.get_expired_tasks()
    
    if not timeout_tasks:
        logger.debug("没有检测到超时任务")
        return {
            "config_id": config_id,
            "checked_at": get_current_time().isoformat(),
            "timeout_count": 0
        }
    
    logger.warning(f"检测到 {len(timeout_tasks)} 个超时任务")
    
    # 批量获取数据，避免N+1查询
    task_ids = [task["task_id"] for task in timeout_tasks]
    config_ids = list(set(task["config_id"] for task in timeout_tasks))
    
    configs_map = await _batch_get_configs(config_ids)
    executions_map = await _batch_get_executions(task_ids)
    
    # 处理每个超时任务
    processed_count = 0
    processed_task_ids = []
    
    async with AsyncSessionLocal() as db:
        for task_data in timeout_tasks:
            try:
                task_id = task_data["task_id"]
                config_id = task_data["config_id"]
                started_at = datetime.fromisoformat(task_data["started_at"])
                timeout_seconds = task_data["timeout_seconds"]
                
                # 从缓存中获取配置和执行记录
                config = configs_map.get(config_id)
                execution = executions_map.get(task_id)
                
                config_name = config.name if config else f"Config#{config_id}"
                
                # 更新任务状态为超时
                if execution and execution.status == ExecutionStatus.RUNNING:
                    running_time = (get_current_time() - started_at).total_seconds()
                    error_msg = f"任务超时 (运行时间: {running_time:.1f}秒, 限制: {timeout_seconds}秒)"
                    
                    await crud_task_execution.update_status(
                        db=db,
                        execution_id=execution.id,
                        status=ExecutionStatus.TIMEOUT,
                        completed_at=get_current_time(),
                        error_message=error_msg
                    )
                    
                    # 记录到调度历史
                    await redis_services.history.add_history_event(
                        config_id=config_id,
                        event_data={
                            "task_id": task_id,
                            "status": "timeout",
                            "error": error_msg,
                            "timestamp": get_current_time().isoformat()
                        }
                    )
                    
                    logger.warning(f"标记任务 {task_id} ({config_name}) 为超时状态")
                    processed_count += 1
                
                processed_task_ids.append(task_id)
                
            except Exception as e:
                logger.error(f"处理超时任务 {task_data.get('task_id')} 时出错: {e}")
    
    # 从Redis中清理已处理的任务（使用新的服务）
    if processed_task_ids:
        await redis_services.timeout.cleanup_completed_tasks(processed_task_ids)
    
    result = {
        "config_id": config_id,
        "checked_at": get_current_time().isoformat(),
        "timeout_count": len(timeout_tasks),
        "processed_count": processed_count
    }
    
    logger.info(f"超时监控完成: 检测 {len(timeout_tasks)} 个，处理 {processed_count} 个")
    return result

async def _batch_get_configs(config_ids: List[int]) -> Dict[int, TaskConfig]:
    """批量获取任务配置，避免N+1查询"""
    if not config_ids:
        return {}
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TaskConfig).where(TaskConfig.id.in_(config_ids))
        )
        configs = result.scalars().all()
        
        return {config.id: config for config in configs}

async def _batch_get_executions(task_ids: List[str]) -> Dict[str, TaskExecution]:
    """批量获取任务执行记录，避免N+1查询"""
    if not task_ids:
        return {}
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TaskExecution).where(TaskExecution.task_id.in_(task_ids))
        )
        executions = result.scalars().all()
        
        return {execution.task_id: execution for execution in executions}

@broker.task(
    task_name="cleanup_timeout_monitor",
    queue="cleanup",
    retry_on_error=False,
)
async def cleanup_timeout_monitor_task(
    config_id: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    清理Redis中的过期监控数据 - 使用新的Redis服务
    """
    logger.info("开始清理超时监控数据...")
    
    # 使用新的Redis服务获取所有任务
    all_tasks = await redis_services.timeout.get_all_tasks()
    
    if not all_tasks:
        return {
            "config_id": config_id,
            "cleaned_at": get_current_time().isoformat(),
            "total_tasks": 0,
            "cleaned_count": 0
        }
    
    # 批量获取所有任务的执行状态，避免N+1查询
    task_ids = [task["task_id"] for task in all_tasks]
    executions_map = await _batch_get_executions(task_ids)
    
    # 找出已经完成的任务
    completed_task_ids = []
    for task_data in all_tasks:
        task_id = task_data["task_id"]
        execution = executions_map.get(task_id)
        
        if not execution or execution.status != ExecutionStatus.RUNNING:
            completed_task_ids.append(task_id)
    
    # 使用新的Redis服务清理已完成的任务
    cleaned_count = 0
    if completed_task_ids:
        cleaned_count = await redis_services.timeout.cleanup_completed_tasks(completed_task_ids)
    
    result = {
        "config_id": config_id,
        "cleaned_at": get_current_time().isoformat(),
        "total_tasks": len(all_tasks),
        "cleaned_count": cleaned_count
    }
    
    logger.info(f"清理完成: 总任务 {len(all_tasks)}，清理 {cleaned_count}")
    return result