"""
清理任务定义
"""
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from app.broker import broker
from app.db.base import AsyncSessionLocal
from app.crud.token import crud_refresh_token
from app.crud.password_reset import crud_password_reset
from app.crud.reddit_content import crud_reddit_content
from app.crud.schedule_event import crud_schedule_event

logger = logging.getLogger(__name__)


@broker.task(
    task_name="cleanup_expired_tokens",
    queue="cleanup",
    retry_on_error=True,
    max_retries=3,
)
async def cleanup_expired_tokens(
    config_id: Optional[int] = None,
    days_old: int = 7
) -> Dict[str, Any]:
    """
    清理过期的令牌
    
    Args:
        config_id: 任务配置ID
        days_old: 清理多少天前的过期令牌
    
    Returns:
        清理结果统计
    """
    logger.info(f"开始清理 {days_old} 天前的过期令牌... (Config ID: {config_id})")
    
    async with AsyncSessionLocal() as db:
        try:
            expired_refresh = await crud_refresh_token.cleanup_expired(db, days_old=days_old)
            expired_reset = await crud_password_reset.cleanup_expired(db, days_old=days_old)
            
            result = {
                "config_id": config_id,
                "expired_refresh_tokens": expired_refresh,
                "expired_reset_tokens": expired_reset,
                "total_cleaned": expired_refresh + expired_reset,
                "days_old": days_old
            }
            
            # 记录执行结果到数据库
            await record_task_execution(db, config_id, "success", result)
            
            logger.info(f"清理过期令牌完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"清理过期令牌时出错: {e}", exc_info=True)
            await record_task_execution(db, config_id, "failed", error=str(e))
            raise


@broker.task(
    task_name="cleanup_old_content",
    queue="cleanup",
    retry_on_error=True,
    max_retries=3,
)
async def cleanup_old_content(
    config_id: Optional[int] = None,
    days_old: int = 90
) -> Dict[str, Any]:
    """
    清理旧内容
    
    Args:
        config_id: 任务配置ID
        days_old: 清理多少天前的内容
    
    Returns:
        清理结果统计
    """
    logger.info(f"开始清理 {days_old} 天前的旧内容... (Config ID: {config_id})")
    
    async with AsyncSessionLocal() as db:
        try:
            deleted_posts, deleted_comments = await crud_reddit_content.delete_old_content(
                db, days_to_keep=days_old
            )
            
            result = {
                "config_id": config_id,
                "deleted_posts": deleted_posts,
                "deleted_comments": deleted_comments,
                "total_deleted": deleted_posts + deleted_comments,
                "days_old": days_old
            }
            
            await record_task_execution(db, config_id, "success", result)
            logger.info(f"清理旧内容完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"清理旧内容时出错: {e}", exc_info=True)
            await record_task_execution(db, config_id, "failed", error=str(e))
            raise


@broker.task(
    task_name="cleanup_schedule_events",
    queue="cleanup",
    retry_on_error=True,
    max_retries=3,
)
async def cleanup_schedule_events(
    config_id: Optional[int] = None,
    days_old: int = 30
) -> Dict[str, Any]:
    """
    清理旧的调度事件
    
    Args:
        config_id: 任务配置ID
        days_old: 清理多少天前的事件
    
    Returns:
        清理结果统计
    """
    logger.info(f"开始清理 {days_old} 天前的旧调度事件... (Config ID: {config_id})")
    
    async with AsyncSessionLocal() as db:
        try:
            deleted_count = await crud_schedule_event.cleanup_old_events(db, days_old)
            
            result = {
                "config_id": config_id,
                "deleted_events": deleted_count,
                "days_old": days_old
            }
            
            await record_task_execution(db, config_id, "success", result)
            logger.info(f"清理调度事件完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"清理调度事件时出错: {e}", exc_info=True)
            await record_task_execution(db, config_id, "failed", error=str(e))
            raise


async def record_task_execution(db, config_id: Optional[int], status: str, result: Dict = None, error: str = None):
    """记录任务执行结果到数据库"""
    from app.models.task_execution import TaskExecution
    import uuid
    
    execution = TaskExecution(
        config_id=config_id,
        task_id=str(uuid.uuid4()),  # 生成唯一的task_id
        status=status,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        result=result,
        error_message=error
    )
    db.add(execution)
    await db.commit()