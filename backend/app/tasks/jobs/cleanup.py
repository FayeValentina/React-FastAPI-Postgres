from typing import Dict, Any
from app.tasks.scheduler import task_scheduler
from app.tasks.decorators import with_task_logging
from app.db.base import AsyncSessionLocal
from app.crud.token import refresh_token
from app.crud.password_reset import password_reset
from app.crud.scrape_session import CRUDScrapeSession
from app.crud.reddit_content import CRUDRedditContent


@with_task_logging("清理过期令牌")
async def cleanup_expired_tokens(**kwargs) -> Dict[str, Any]:
    """清理过期令牌任务"""
    async with AsyncSessionLocal() as db:
        expired_refresh = await refresh_token.cleanup_expired(db)
        expired_reset = await password_reset.cleanup_expired(db)
        
        return {
            "expired_refresh_tokens": expired_refresh,
            "expired_reset_tokens": expired_reset,
            "total_cleaned": expired_refresh + expired_reset
        }


@with_task_logging("清理旧会话")
async def cleanup_old_sessions(**kwargs) -> Dict[str, Any]:
    """清理旧会话任务"""
    async with AsyncSessionLocal() as db:
        deleted_sessions = await CRUDScrapeSession.cleanup_old_sessions(db, days_to_keep=30)
        return {"deleted_sessions": deleted_sessions}


@with_task_logging("清理旧内容")
async def cleanup_old_content(**kwargs) -> Dict[str, Any]:
    """清理旧Reddit内容任务"""
    async with AsyncSessionLocal() as db:
        deleted_posts, deleted_comments = await CRUDRedditContent.delete_old_content(
            db, days_to_keep=90
        )
        return {
            "deleted_posts": deleted_posts,
            "deleted_comments": deleted_comments
        }


@with_task_logging("清理执行历史")
async def cleanup_execution_history(**kwargs) -> Dict[str, Any]:
    """清理旧的任务执行历史"""
    async with AsyncSessionLocal() as db:
        from app.tasks.manager import TaskManager
        manager = TaskManager(task_scheduler.scheduler)
        deleted_count = await manager.cleanup_old_executions(db, days_to_keep=30)
        return {"deleted_executions": deleted_count}


# 注册定时任务
task_scheduler.add_job(
    'app.tasks.jobs.cleanup:cleanup_expired_tokens',
    trigger='interval',
    id='cleanup_tokens',
    name='清理过期令牌',
    hours=1
)

task_scheduler.add_job(
    'app.tasks.jobs.cleanup:cleanup_old_sessions',
    trigger='cron',
    id='cleanup_sessions',
    name='清理旧会话',
    hour=2,
    minute=0
)

task_scheduler.add_job(
    'app.tasks.jobs.cleanup:cleanup_old_content',
    trigger='cron',
    id='cleanup_content',
    name='清理旧内容',
    day_of_week=6,  # 周日
    hour=2,
    minute=30
)

task_scheduler.add_job(
    'app.tasks.jobs.cleanup:cleanup_execution_history',
    trigger='cron',
    id='cleanup_executions',
    name='清理执行历史',
    hour=3,
    minute=0
)