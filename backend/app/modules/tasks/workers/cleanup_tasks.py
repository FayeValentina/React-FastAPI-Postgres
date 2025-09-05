"""
清理任务定义
"""
from typing import Dict, Any, Optional
import logging

from taskiq import Context, TaskiqDepends
from app.broker import broker
from app.infrastructure.database.postgres_base import AsyncSessionLocal
from app.modules.auth.repository import crud_password_reset
from app.modules.content.repository import crud_reddit_content
from app.infrastructure.tasks.exec_record_decorators import execution_handler
from app.infrastructure.tasks.task_registry_decorators import task

logger = logging.getLogger(__name__)


@task("CLEANUP_TOKENS", queue="cleanup")
@broker.task(
    task_name="cleanup_expired_tokens",
    queue="cleanup",
    retry_on_error=True,
    max_retries=3,
)
@execution_handler
async def cleanup_expired_tokens(
    config_id: Optional[int] = None,
    days_old: int = 7,
    context: Context = TaskiqDepends()
) -> Dict[str, Any]:
    """
    清理过期的令牌
    """
    logger.info(f"开始清理 {days_old} 天前的过期令牌... (Config ID: {config_id})")
    
    async with AsyncSessionLocal() as db:
        expired_reset = await crud_password_reset.cleanup_expired(db, days_old=days_old)
        
        result = {
            "config_id": config_id,
            "expired_reset_tokens": expired_reset,
            "days_old": days_old
        }
        
        logger.info(f"清理过期令牌完成: {result}")
        return result


@task("CLEANUP_CONTENT", queue="cleanup")
@broker.task(
    task_name="cleanup_old_content",
    queue="cleanup",
    retry_on_error=True,
    max_retries=3,
)
@execution_handler
async def cleanup_old_content(
    config_id: Optional[int] = None,
    days_old: int = 90,
    context: Context = TaskiqDepends()
) -> Dict[str, Any]:
    """
    清理旧内容
    """
    logger.info(f"开始清理 {days_old} 天前的旧内容... (Config ID: {config_id})")
    
    async with AsyncSessionLocal() as db:
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
        
        logger.info(f"清理旧内容完成: {result}")
        return result
