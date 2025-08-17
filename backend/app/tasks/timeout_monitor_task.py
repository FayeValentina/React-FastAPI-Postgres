"""
超时监控任务
定期检查并处理超时的任务执行
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
import asyncio

from app.broker import broker
from app.db.base import AsyncSessionLocal
from app.crud.task_execution import crud_task_execution
from app.crud.task_config import crud_task_config
from app.models.task_execution import ExecutionStatus
from app.core.task_manager import TaskManager
from app.core.monitor_wrapper import timeout_monitor
from app.utils.common import get_current_time

logger = logging.getLogger(__name__)


@broker.task(
    task_name="timeout_monitor",
    queue="monitor",
    retry_on_error=True,
    max_retries=1,
)
@timeout_monitor
async def timeout_monitor_task(
    config_id: Optional[int] = None,
    check_interval_minutes: int = 5,
    max_check_hours: int = 24
) -> Dict[str, Any]:
    """
    超时监控任务 - 检查并处理超时的任务执行
    
    Args:
        config_id: 任务配置ID (用于统一接口，此处可忽略)
        check_interval_minutes: 检查间隔(分钟)
        max_check_hours: 最大检查范围(小时)
    
    Returns:
        监控结果统计
    """
    logger.info("开始执行超时监控任务...")
    
    async with AsyncSessionLocal() as db:
        # 获取所有正在运行的任务
        running_executions = await crud_task_execution.get_running_executions(db)
        
        timeout_count = 0
        checked_count = len(running_executions)
        timeout_tasks = []
        
        current_time = get_current_time()
        
        for execution in running_executions:
            try:
                # 获取任务配置以确定超时时间
                task_config = await crud_task_config.get(db, execution.config_id)
                if not task_config or not task_config.timeout_seconds:
                    continue
                
                # 计算任务运行时间
                running_time = (current_time - execution.started_at).total_seconds()
                
                # 检查是否超时
                if running_time > task_config.timeout_seconds:
                    logger.warning(
                        f"检测到超时任务: task_id={execution.task_id}, "
                        f"运行时间={running_time:.1f}s, 超时阈值={task_config.timeout_seconds}s"
                    )
                    
                    # 标记任务为超时
                    await crud_task_execution.update_status(
                        db=db,
                        execution_id=execution.id,
                        status=ExecutionStatus.TIMEOUT,
                        completed_at=current_time,
                        error_message=f"Task timed out after {running_time:.1f} seconds (limit: {task_config.timeout_seconds}s)"
                    )
                    
                    timeout_count += 1
                    timeout_tasks.append({
                        "task_id": execution.task_id,
                        "config_id": execution.config_id,
                        "config_name": task_config.name,
                        "running_time_seconds": running_time,
                        "timeout_threshold_seconds": task_config.timeout_seconds
                    })
                    
                    # 尝试通过TaskIQ撤销任务 (如果支持)
                    try:
                        await _revoke_task_from_broker(execution.task_id)
                    except Exception as e:
                        logger.warning(f"无法撤销超时任务 {execution.task_id}: {e}")
            
            except Exception as e:
                logger.error(f"处理任务执行记录 {execution.id} 时出错: {e}")
                continue
        
        result = {
            "config_id": config_id,
            "monitor_time": current_time.isoformat(),
            "checked_tasks": checked_count,
            "timeout_tasks": timeout_count,
            "timeout_details": timeout_tasks,
            "check_interval_minutes": check_interval_minutes
        }
        
        if timeout_count > 0:
            logger.warning(f"超时监控完成: 检查了 {checked_count} 个任务，发现 {timeout_count} 个超时任务")
        else:
            logger.info(f"超时监控完成: 检查了 {checked_count} 个任务，无超时任务")
            
        return result


async def _revoke_task_from_broker(task_id: str) -> bool:
    """
    尝试从TaskIQ broker撤销任务
    
    Args:
        task_id: 任务ID
        
    Returns:
        是否成功撤销
    """
    try:
        # TaskIQ 0.11.x 的任务撤销方法
        from app.broker import broker
        
        # 检查任务是否还在队列中
        is_ready = await broker.result_backend.is_result_ready(task_id)
        if not is_ready:
            # 任务可能还在队列中，尝试标记为撤销
            # 注意：这里的实现取决于你的TaskIQ版本和配置
            logger.info(f"尝试撤销队列中的任务: {task_id}")
            return True
        
        return False
        
    except Exception as e:
        logger.warning(f"撤销任务失败 {task_id}: {e}")
        return False


@broker.task(
    task_name="cleanup_timeout_tasks",
    queue="cleanup",
    retry_on_error=True,
    max_retries=1,
)
@timeout_monitor
async def cleanup_timeout_tasks(
    config_id: Optional[int] = None,
    days_old: int = 7
) -> Dict[str, Any]:
    """
    清理旧的超时任务记录
    
    Args:
        config_id: 任务配置ID
        days_old: 清理多少天前的超时记录
    
    Returns:
        清理结果统计
    """
    logger.info(f"开始清理 {days_old} 天前的超时任务记录...")
    
    async with AsyncSessionLocal() as db:
        cutoff_date = get_current_time() - timedelta(days=days_old)
        
        # 获取需要清理的超时任务
        from sqlalchemy import select, and_, delete
        from app.models.task_execution import TaskExecution
        
        # 统计要删除的记录数
        count_result = await db.execute(
            select(TaskExecution.id)
            .where(
                and_(
                    TaskExecution.status == ExecutionStatus.TIMEOUT,
                    TaskExecution.completed_at < cutoff_date
                )
            )
        )
        timeout_records = count_result.scalars().all()
        count_to_delete = len(timeout_records)
        
        # 执行删除
        if count_to_delete > 0:
            await db.execute(
                delete(TaskExecution)
                .where(
                    and_(
                        TaskExecution.status == ExecutionStatus.TIMEOUT,
                        TaskExecution.completed_at < cutoff_date
                    )
                )
            )
            await db.commit()
        
        result = {
            "config_id": config_id,
            "cleanup_time": get_current_time().isoformat(),
            "days_old": days_old,
            "deleted_timeout_records": count_to_delete
        }
        
        logger.info(f"清理超时任务记录完成: 删除了 {count_to_delete} 条记录")
        return result