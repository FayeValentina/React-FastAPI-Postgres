from typing import Dict, Any
import asyncio
from app.celery_app import celery_app
from app.db.base import get_worker_session  # 使用 Worker 专用会话
from app.middleware.decorators import task_executor
from app.crud.token import crud_refresh_token
from app.crud.password_reset import crud_password_reset
from app.crud.reddit_content import crud_reddit_content
from app.crud.schedule_event import crud_schedule_event

import logging

# 获取日志记录器
logger = logging.getLogger(__name__)

async def _cleanup_expired_tokens_async(config_id: int, *, days_old: int = 7) -> Dict[str, Any]:
    """
    异步清理过期的刷新令牌和密码重置令牌的内部实现。
    """
    logger.info(f"开始异步清理 {days_old} 天前的过期令牌... (Config ID: {config_id})")
    
    # 使用 Worker 专用会话
    async for db in get_worker_session():
        try:
            expired_refresh = await crud_refresh_token.cleanup_expired(db, days_old=days_old)
            expired_reset = await crud_password_reset.cleanup_expired(db, days_old=days_old)
            
            result = {
                "expired_refresh_tokens": expired_refresh,
                "expired_reset_tokens": expired_reset,
                "total_cleaned": expired_refresh + expired_reset,
                "days_old": days_old
            }
            logger.info(f"清理过期令牌完成: {result}")
            return result
        except Exception as e:
            logger.error(f"清理过期令牌时出错: {e}", exc_info=True)
            raise

@celery_app.task(bind=True, name='cleanup_expired_tokens_task')
@task_executor("清理过期令牌任务") # 使用我们之前完善的装饰器
def cleanup_expired_tokens_task(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    """
    清理过期的刷新令牌和密码重置令牌。
    采用 *args, **kwargs 签名以避免Celery参数绑定问题。
    """
    # 从参数中提取 config_id
    # task_executor 装饰器已经保证了 config_id 的存在
    config_id = kwargs.get("config_id") or (args[0] if args else None)
    
    # 提取特定于任务的参数
    days_old = kwargs.get("days_old", 7)
    
    return asyncio.run(_cleanup_expired_tokens_async(config_id, days_old=days_old))


async def _cleanup_old_content_async(config_id: int, *, days_old: int = 90) -> Dict[str, Any]:
    """
    异步清理旧的 Reddit 内容（帖子和评论）的内部实现。
    """
    logger.info(f"开始异步清理 {days_old} 天前的旧 Reddit 内容... (Config ID: {config_id})")

    # 使用 Worker 专用会话
    async for db in get_worker_session():
        try:
            deleted_posts, deleted_comments = await crud_reddit_content.delete_old_content(
                db, days_to_keep=days_old
            )

            result = {
                "deleted_posts": deleted_posts,
                "deleted_comments": deleted_comments,
                "total_deleted": deleted_posts + deleted_comments,
                "days_old": days_old
            }
            logger.info(f"清理旧内容完成: {result}")
            return result
        except Exception as e:
            logger.error(f"清理旧内容时出错: {e}", exc_info=True)
            raise

@celery_app.task(bind=True, name='cleanup_old_content_task')
@task_executor("清理旧Reddit内容任务")
def cleanup_old_content_task(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    """
    清理旧的 Reddit 内容（帖子和评论）。
    采用 *args, **kwargs 签名以避免Celery参数绑定问题。
    """
    config_id = kwargs.get("config_id") or (args[0] if args else None)
    days_old = kwargs.get("days_old", 90)
    
    return asyncio.run(_cleanup_old_content_async(config_id, days_old=days_old))


async def _cleanup_schedule_events_async(config_id: int, *, days_old: int = 30) -> Dict[str, Any]:
    """
    异步清理旧的调度事件记录的内部实现。
    """
    logger.info(f"开始异步清理 {days_old} 天前的旧调度事件... (Config ID: {config_id})")

    # 使用 Worker 专用会话
    async for db in get_worker_session():
        try:
            deleted_count = await crud_schedule_event.cleanup_old_events(db, days_old)

            result = {
                "deleted_events": deleted_count,
                "days_old": days_old
            }
            logger.info(f"清理调度事件完成: {result}")
            return result
        except Exception as e:
            logger.error(f"清理调度事件时出错: {e}", exc_info=True)
            raise

@celery_app.task(bind=True, name='cleanup_schedule_events_task')
@task_executor("清理调度事件任务")
def cleanup_schedule_events_task(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    """
    清理旧的调度事件记录。
    采用 *args, **kwargs 签名以避免Celery参数绑定问题。
    """
    config_id = kwargs.get("config_id") or (args[0] if args else None)
    days_old = kwargs.get("days_old", 30)

    return asyncio.run(_cleanup_schedule_events_async(config_id, days_old=days_old))
