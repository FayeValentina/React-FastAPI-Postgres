"""
清理相关的Celery任务
"""
from typing import Dict, Any
import logging
from datetime import datetime, timedelta
from celery import current_task

from app.celery_app import celery_app
from app.db.base import AsyncSessionLocal
from app.crud.scrape_session import CRUDScrapeSession
from app.models.task_execution import ExecutionStatus
from .common import run_async_task, record_task_execution

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='cleanup_old_sessions_task')
def cleanup_old_sessions_task(self, days_old: int = 30) -> Dict[str, Any]:
    """清理旧的爬取会话任务"""
    start_time = datetime.utcnow()
    task_id = self.request.id
    
    try:
        logger.info(f"开始执行清理任务，删除{days_old}天前的会话")
        
        async def _execute():
            async with AsyncSessionLocal() as db:
                cutoff_date = datetime.utcnow() - timedelta(days=days_old)
                
                # 获取要删除的会话数量
                old_sessions = await CRUDScrapeSession.get_sessions_before_date(
                    db, cutoff_date
                )
                session_count = len(old_sessions)
                
                if session_count > 0:
                    # 删除旧会话
                    deleted_count = await CRUDScrapeSession.delete_sessions_before_date(
                        db, cutoff_date
                    )
                    logger.info(f"成功删除 {deleted_count} 个旧会话")
                    return {
                        "status": "completed",
                        "deleted_sessions": deleted_count,
                        "cutoff_date": cutoff_date.isoformat()
                    }
                else:
                    logger.info("没有找到需要清理的旧会话")
                    return {
                        "status": "completed",
                        "deleted_sessions": 0,
                        "message": "没有需要清理的会话"
                    }
        
        result = run_async_task(_execute())
        
        # 记录成功执行
        run_async_task(record_task_execution(
            task_id, f"清理旧会话任务-{days_old}天前", start_time, ExecutionStatus.SUCCESS, result
        ))
        
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(record_task_execution(
            task_id, f"清理旧会话任务-{days_old}天前", start_time, ExecutionStatus.FAILED, error=exc
        ))
        
        logger.error(f"清理任务失败: {exc}")
        
        # 清理任务失败时重试
        if self.request.retries < self.max_retries:
            logger.info(f"第 {self.request.retries + 1} 次重试清理任务")
            raise self.retry(countdown=300, exc=exc)  # 5分钟后重试
        
        return {
            "status": "failed",
            "reason": str(exc),
            "retries": self.request.retries
        }


@celery_app.task(bind=True, name='cleanup_expired_tokens_task')
def cleanup_expired_tokens_task(self) -> Dict[str, Any]:
    """清理过期令牌任务"""
    start_time = datetime.utcnow()
    task_id = self.request.id
    
    try:
        async def _execute():
            async with AsyncSessionLocal() as db:
                from app.crud.token import refresh_token
                from app.crud.password_reset import password_reset
                
                expired_refresh = await refresh_token.cleanup_expired(db)
                expired_reset = await password_reset.cleanup_expired(db)
                
                return {
                    "expired_refresh_tokens": expired_refresh,
                    "expired_reset_tokens": expired_reset,
                    "total_cleaned": expired_refresh + expired_reset
                }
        
        result = run_async_task(_execute())
        
        # 记录成功执行
        run_async_task(record_task_execution(
            task_id, "清理过期令牌任务", start_time, ExecutionStatus.SUCCESS, result
        ))
        
        logger.info(f"清理过期令牌完成: {result}")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(record_task_execution(
            task_id, "清理过期令牌任务", start_time, ExecutionStatus.FAILED, error=exc
        ))
        
        logger.error(f"清理过期令牌失败: {exc}")
        return {"status": "failed", "reason": str(exc)}


@celery_app.task(bind=True, name='cleanup_old_content_task')
def cleanup_old_content_task(self, days_old: int = 90) -> Dict[str, Any]:
    """清理旧Reddit内容任务"""
    start_time = datetime.utcnow()
    task_id = self.request.id
    
    try:
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
        
        # 记录成功执行
        run_async_task(record_task_execution(
            task_id, f"清理旧内容任务-{days_old}天前", start_time, ExecutionStatus.SUCCESS, result
        ))
        
        logger.info(f"清理旧内容完成: {result}")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(record_task_execution(
            task_id, f"清理旧内容任务-{days_old}天前", start_time, ExecutionStatus.FAILED, error=exc
        ))
        
        logger.error(f"清理旧内容失败: {exc}")
        return {"status": "failed", "reason": str(exc)}


@celery_app.task(bind=True, name='cleanup_schedule_events_task')
def cleanup_schedule_events_task(self, days_old: int = 30) -> Dict[str, Any]:
    """清理旧的调度事件任务"""
    start_time = datetime.utcnow()
    task_id = self.request.id
    
    try:
        async def _execute():
            async with AsyncSessionLocal() as db:
                from app.crud.schedule_event import CRUDScheduleEvent
                deleted_count = await CRUDScheduleEvent.cleanup_old_events(db, days_old)
                return {
                    "deleted_events": deleted_count,
                    "days_old": days_old
                }
        
        result = run_async_task(_execute())
        
        # 记录成功执行
        run_async_task(record_task_execution(
            task_id, f"清理调度事件任务-{days_old}天前", start_time, ExecutionStatus.SUCCESS, result
        ))
        
        logger.info(f"清理调度事件完成: {result}")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(record_task_execution(
            task_id, f"清理调度事件任务-{days_old}天前", start_time, ExecutionStatus.FAILED, error=exc
        ))
        
        logger.error(f"清理调度事件失败: {exc}")
        return {"status": "failed", "reason": str(exc)}