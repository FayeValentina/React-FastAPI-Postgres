"""
清理任务定义
"""
from typing import Dict, Any, Optional
import logging

from app.broker import broker
from app.db.base import AsyncSessionLocal
from app.crud.token import crud_refresh_token
from app.crud.password_reset import crud_password_reset
from app.crud.reddit_content import crud_reddit_content
from app.crud.schedule_event import crud_schedule_event
from app.core.timeout_decorator import with_timeout  # 改为使用新的装饰器

logger = logging.getLogger(__name__)


@broker.task(
    task_name="cleanup_expired_tokens",
    queue="cleanup",
    retry_on_error=True,
    max_retries=3,
)
@with_timeout  # 使用新的超时装饰器
async def cleanup_expired_tokens(
    config_id: Optional[int] = None,
    days_old: int = 7,
    **kwargs  # 接收task_id等额外参数
) -> Dict[str, Any]:
    """
    清理过期的令牌
    """
    logger.info(f"开始清理 {days_old} 天前的过期令牌... (Config ID: {config_id})")
    
    async with AsyncSessionLocal() as db:
        expired_refresh = await crud_refresh_token.cleanup_expired(db, days_old=days_old)
        expired_reset = await crud_password_reset.cleanup_expired(db, days_old=days_old)
        
        result = {
            "config_id": config_id,
            "expired_refresh_tokens": expired_refresh,
            "expired_reset_tokens": expired_reset,
            "total_cleaned": expired_refresh + expired_reset,
            "days_old": days_old
        }
        
        logger.info(f"清理过期令牌完成: {result}")
        return result


@broker.task(
    task_name="cleanup_old_content",
    queue="cleanup",
    retry_on_error=True,
    max_retries=3,
)
@with_timeout
async def cleanup_old_content(
    config_id: Optional[int] = None,
    days_old: int = 90,
    **kwargs
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


@broker.task(
    task_name="cleanup_schedule_events",
    queue="cleanup",
    retry_on_error=True,
    max_retries=3,
)
@with_timeout
async def cleanup_schedule_events(
    config_id: Optional[int] = None,
    days_old: int = 30,
    **kwargs
) -> Dict[str, Any]:
    """
    清理旧的调度事件
    """
    logger.info(f"开始清理 {days_old} 天前的旧调度事件... (Config ID: {config_id})")
    
    async with AsyncSessionLocal() as db:
        deleted_count = await crud_schedule_event.cleanup_old_events(db, days_old)
        
        result = {
            "config_id": config_id,
            "deleted_events": deleted_count,
            "days_old": days_old
        }
        
        logger.info(f"清理调度事件完成: {result}")
        return result