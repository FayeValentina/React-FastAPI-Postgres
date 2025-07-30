from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from typing import Optional

from app.db.base import AsyncSessionLocal
from app.crud.token import refresh_token
from app.crud.password_reset import password_reset
from app.crud.scrape_session import CRUDScrapeSession
from app.crud.reddit_content import CRUDRedditContent
from app.services.scraping_orchestrator import ScrapingOrchestrator

logger = logging.getLogger(__name__)


class TaskScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running = False
    
    async def cleanup_expired_tokens(self):
        """清理过期令牌任务 - 每小时执行"""
        try:
            async with AsyncSessionLocal() as db:
                # 清理过期的刷新令牌
                expired_refresh_tokens = await refresh_token.cleanup_expired(db)
                # 清理过期的密码重置令牌
                expired_reset_tokens = await password_reset.cleanup_expired(db)
                
                logger.info(f"令牌清理完成: {expired_refresh_tokens}个刷新令牌, {expired_reset_tokens}个重置令牌")
        except Exception as e:
            logger.error(f"令牌清理任务失败: {e}")
    
    async def cleanup_old_sessions(self):
        """清理旧爬取会话 - 每天执行"""
        try:
            async with AsyncSessionLocal() as db:
                deleted_sessions = await CRUDScrapeSession.cleanup_old_sessions(db, days_to_keep=30)
                logger.info(f"会话清理完成: 删除了{deleted_sessions}个旧会话")
        except Exception as e:
            logger.error(f"会话清理任务失败: {e}")
    
    async def cleanup_old_content(self):
        """清理旧Reddit内容 - 每周执行"""
        try:
            async with AsyncSessionLocal() as db:
                deleted_posts, deleted_comments = await CRUDRedditContent.delete_old_content(db, days_to_keep=90)
                logger.info(f"内容清理完成: 删除了{deleted_posts}个帖子, {deleted_comments}条评论")
        except Exception as e:
            logger.error(f"内容清理任务失败: {e}")
    
    async def auto_scraping_task(self):
        """自动爬取任务 - 每6小时执行"""
        try:
            async with AsyncSessionLocal() as db:
                orchestrator = ScrapingOrchestrator()
                results = await orchestrator.execute_auto_scraping(db)
                
                if results:
                    successful = len([r for r in results if r.get('status') != 'error'])
                    logger.info(f"自动爬取完成: {successful}/{len(results)}个配置成功执行")
                else:
                    logger.info("自动爬取检查完成: 没有启用自动爬取的配置")
        except Exception as e:
            logger.error(f"自动爬取任务失败: {e}")
    
    def start(self):
        """启动所有定时任务"""
        if self._running:
            logger.warning("调度器已经在运行")
            return
        
        # 1. 每小时清理过期令牌 (每小时的0分执行)
        self.scheduler.add_job(
            self.cleanup_expired_tokens,
            CronTrigger(minute=0),
            id='cleanup_tokens',
            name='清理过期令牌',
            replace_existing=True
        )
        
        # 2. 每天凌晨2点清理旧会话
        self.scheduler.add_job(
            self.cleanup_old_sessions,
            CronTrigger(hour=2, minute=0),
            id='cleanup_sessions',
            name='清理旧会话',
            replace_existing=True
        )
        
        # 3. 每周日凌晨2点30分清理旧内容
        self.scheduler.add_job(
            self.cleanup_old_content,
            CronTrigger(day_of_week=6, hour=2, minute=30),  # 周日=6
            id='cleanup_content',
            name='清理旧内容',
            replace_existing=True
        )
        
        # 4. 每6小时检查自动爬取 (00:00, 06:00, 12:00, 18:00)
        self.scheduler.add_job(
            self.auto_scraping_task,
            CronTrigger(hour='0,6,12,18', minute=0),
            id='auto_scraping',
            name='自动爬取检查',
            replace_existing=True
        )
        
        self.scheduler.start()
        self._running = True
        logger.info("定时任务调度器已启动")
        
        # 打印已注册的任务
        jobs = self.scheduler.get_jobs()
        for job in jobs:
            logger.info(f"已注册任务: {job.name} (ID: {job.id})")
    
    def shutdown(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("定时任务调度器已关闭")


# 全局调度器实例
task_scheduler = TaskScheduler()