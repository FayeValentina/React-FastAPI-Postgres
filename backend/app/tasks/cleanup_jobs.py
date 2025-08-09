"""
清理相关的Celery任务
"""
from typing import Dict, Any
import logging
from datetime import datetime, timedelta
from celery import current_task

from app.celery_app import celery_app
from app.db.base import AsyncSessionLocal
from app.middleware.decorators import record_task_execution
from .common_utils import run_async_task

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='cleanup_expired_tokens_task')
@record_task_execution("清理过期令牌任务")
def cleanup_expired_tokens_task(self, task_config_id: int, *, days_old: int = 7) -> Dict[str, Any]:
    """清理过期令牌任务"""
    async def _execute():
        async with AsyncSessionLocal() as db:
            from app.crud.token import refresh_token
            from app.crud.password_reset import password_reset
            
            expired_refresh = await refresh_token.cleanup_expired(db)
            expired_reset = await password_reset.cleanup_expired(db)
            
            return {
                "expired_refresh_tokens": expired_refresh,
                "expired_reset_tokens": expired_reset,
                "total_cleaned": expired_refresh + expired_reset,
                "days_old": days_old
            }
    
    result = run_async_task(_execute())
    logger.info(f"清理过期令牌完成: {result}")
    return result


@celery_app.task(bind=True, name='cleanup_old_content_task')
@record_task_execution("清理旧Reddit内容任务")
def cleanup_old_content_task(self, task_config_id: int, *, days_old: int = 90) -> Dict[str, Any]:
    """清理旧Reddit内容任务"""
    async def _execute():
        async with AsyncSessionLocal() as db:
            from app.crud.reddit_content import CRUDRedditContent
            deleted_posts, deleted_comments = await CRUDRedditContent.delete_old_content(
                db, days_to_keep=days_old
            )
            return {
                "deleted_posts": deleted_posts,
                "deleted_comments": deleted_comments,
                "total_deleted": deleted_posts + deleted_comments
            }
    
    result = run_async_task(_execute())
    logger.info(f"清理旧内容完成: {result}")
    return result


@celery_app.task(bind=True, name='cleanup_schedule_events_task')
@record_task_execution("清理调度事件任务")
def cleanup_schedule_events_task(self, task_config_id: int, *, days_old: int = 30) -> Dict[str, Any]:
    """清理旧的调度事件任务"""
    async def _execute():
        async with AsyncSessionLocal() as db:
            from app.crud.schedule_event import CRUDScheduleEvent
            deleted_count = await CRUDScheduleEvent.cleanup_old_events(db, days_old)
            return {
                "deleted_events": deleted_count,
                "days_old": days_old
            }
    
    result = run_async_task(_execute())
    logger.info(f"清理调度事件完成: {result}")
    return result