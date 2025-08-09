"""
清理相关的Celery任务
"""
from typing import Dict, Any
import logging
from datetime import datetime, timedelta
from celery import current_task

from app.celery_app import celery_app
from app.db.base import AsyncSessionLocal
from app.models.task_execution import ExecutionStatus
from .common_utils import run_async_task, record_task_execution

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='cleanup_expired_tokens_task')
def cleanup_expired_tokens_task(self, task_config_id: int, days_old: int = 7) -> Dict[str, Any]:
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
                    "total_cleaned": expired_refresh + expired_reset,
                    "days_old": days_old
                }
        
        result = run_async_task(_execute())
        
        # 记录成功执行
        run_async_task(record_task_execution(
            task_id, f"清理过期令牌任务-{days_old}天前 (config_id: {task_config_id})", start_time, ExecutionStatus.SUCCESS, result, None, task_config_id
        ))
        
        logger.info(f"清理过期令牌完成: {result}")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(record_task_execution(
            task_id, f"清理过期令牌任务-{days_old}天前 (config_id: {task_config_id})", start_time, ExecutionStatus.FAILED, None, exc, task_config_id
        ))
        
        logger.error(f"清理过期令牌失败: {exc}")
        return {"status": "failed", "reason": str(exc)}


@celery_app.task(bind=True, name='cleanup_old_content_task')
def cleanup_old_content_task(self, task_config_id: int, days_old: int = 90) -> Dict[str, Any]:
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
            task_id, f"清理旧内容任务-{days_old}天前 (config_id: {task_config_id})", start_time, ExecutionStatus.SUCCESS, result, None, task_config_id
        ))
        
        logger.info(f"清理旧内容完成: {result}")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(record_task_execution(
            task_id, f"清理旧内容任务-{days_old}天前 (config_id: {task_config_id})", start_time, ExecutionStatus.FAILED, None, exc, task_config_id
        ))
        
        logger.error(f"清理旧内容失败: {exc}")
        return {"status": "failed", "reason": str(exc)}


@celery_app.task(bind=True, name='cleanup_schedule_events_task')
def cleanup_schedule_events_task(self, task_config_id: int, days_old: int = 30) -> Dict[str, Any]:
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
            task_id, f"清理调度事件任务-{days_old}天前 (config_id: {task_config_id})", start_time, ExecutionStatus.SUCCESS, result, None, task_config_id
        ))
        
        logger.info(f"清理调度事件完成: {result}")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(record_task_execution(
            task_id, f"清理调度事件任务-{days_old}天前 (config_id: {task_config_id})", start_time, ExecutionStatus.FAILED, None, exc, task_config_id
        ))
        
        logger.error(f"清理调度事件失败: {exc}")
        return {"status": "failed", "reason": str(exc)}