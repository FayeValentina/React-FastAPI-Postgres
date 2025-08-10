from typing import Dict, Any
from app.celery_app import celery_app
from app.db.base import AsyncSessionLocal
from app.middleware.decorators import task_executor # 假设这是您最终的装饰器
from app.crud import token, password_reset, reddit_content, schedule_event

import logging

# 获取日志记录器
logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name='cleanup_expired_tokens_task')
@task_executor("清理过期令牌任务") # 使用我们之前完善的装饰器
async def cleanup_expired_tokens_task(self, task_config_id: int, *, days_old: int = 7) -> Dict[str, Any]:
    """
    异步清理过期的刷新令牌和密码重置令牌。
    """
    logger.info(f"开始异步清理 {days_old} 天前的过期令牌...")
    
    async with AsyncSessionLocal() as db:
        try:
            expired_refresh = await token.cleanup_expired(db, days_old=days_old)
            expired_reset = await password_reset.cleanup_expired(db, days_old=days_old)
            
            await db.commit()

            result = {
                "expired_refresh_tokens": expired_refresh,
                "expired_reset_tokens": expired_reset,
                "total_cleaned": expired_refresh + expired_reset,
                "days_old": days_old
            }
            logger.info(f"清理过期令牌完成: {result}")
            return result
        except Exception as e:
            await db.rollback()
            logger.error(f"清理过期令牌时出错: {e}", exc_info=True)
            raise


@celery_app.task(bind=True, name='cleanup_old_content_task')
@task_executor("清理旧Reddit内容任务")
async def cleanup_old_content_task(self, task_config_id: int, *, days_old: int = 90) -> Dict[str, Any]:
    """
    异步清理旧的 Reddit 内容（帖子和评论）。
    """
    logger.info(f"开始异步清理 {days_old} 天前的旧 Reddit 内容...")

    async with AsyncSessionLocal() as db:
        try:
            deleted_posts, deleted_comments = await reddit_content.CRUDRedditContent.delete_old_content(
                db, days_to_keep=days_old
            )
            await db.commit()

            result = {
                "deleted_posts": deleted_posts,
                "deleted_comments": deleted_comments,
                "total_deleted": deleted_posts + deleted_comments,
                "days_old": days_old
            }
            logger.info(f"清理旧内容完成: {result}")
            return result
        except Exception as e:
            await db.rollback()
            logger.error(f"清理旧内容时出错: {e}", exc_info=True)
            raise


@celery_app.task(bind=True, name='cleanup_schedule_events_task')
@task_executor("清理调度事件任务")
async def cleanup_schedule_events_task(self, task_config_id: int, *, days_old: int = 30) -> Dict[str, Any]:
    """
    异步清理旧的调度事件记录。
    """
    logger.info(f"开始异步清理 {days_old} 天前的旧调度事件...")

    async with AsyncSessionLocal() as db:
        try:
            deleted_count = await schedule_event.CRUDScheduleEvent.cleanup_old_events(db, days_old)
            await db.commit()

            result = {
                "deleted_events": deleted_count,
                "days_old": days_old
            }
            logger.info(f"清理调度事件完成: {result}")
            return result
        except Exception as e:
            await db.rollback()
            logger.error(f"清理调度事件时出错: {e}", exc_info=True)
            raise

