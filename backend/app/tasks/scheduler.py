from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import logging
from typing import Optional, List

from app.db.base import AsyncSessionLocal
from app.crud.token import refresh_token
from app.crud.password_reset import password_reset
from app.crud.scrape_session import CRUDScrapeSession
from app.crud.reddit_content import CRUDRedditContent
from app.crud.bot_config import CRUDBotConfig
from app.models.scrape_session import SessionType
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

    async def _execute_single_bot_scraping(self, bot_config_id: int):
        """执行单个bot的爬取任务"""
        try:
            async with AsyncSessionLocal() as db:
                orchestrator = ScrapingOrchestrator()
                result = await orchestrator.execute_scraping_session(
                    db, bot_config_id, session_type=SessionType.AUTO
                )
                
                if result and result.get('status') == 'completed':
                    logger.info(f"Bot {bot_config_id} 自动爬取完成: {result.get('total_posts', 0)}个帖子, {result.get('total_comments', 0)}条评论")
                elif result and result.get('status') == 'failed':
                    logger.error(f"Bot {bot_config_id} 自动爬取失败: {result.get('error', 'Unknown error')}")
                else:
                    logger.warning(f"Bot {bot_config_id} 自动爬取未返回有效结果")
        except Exception as e:
            logger.error(f"Bot {bot_config_id} 自动爬取任务失败: {e}")
    
    async def add_bot_task(self, bot_config_id: int, interval_hours: int):
        """为单个bot添加定时任务"""
        try:
            job_id = f"bot_scraping_{bot_config_id}"
            
            # 如果任务已存在，先删除
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            
            # 添加新任务
            self.scheduler.add_job(
                func=self._execute_single_bot_scraping,
                trigger=IntervalTrigger(hours=interval_hours),
                args=[bot_config_id],
                id=job_id,
                name=f'Bot {bot_config_id} 自动爬取',
                replace_existing=True
            )
            
            logger.info(f"已添加Bot {bot_config_id}的定时任务，执行间隔: {interval_hours}小时")
            return True
        except Exception as e:
            logger.error(f"添加Bot {bot_config_id}的定时任务失败: {e}")
            return False
    
    def remove_bot_task(self, bot_config_id: int):
        """移除单个bot的定时任务"""
        try:
            job_id = f"bot_scraping_{bot_config_id}"
            
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"已移除Bot {bot_config_id}的定时任务")
                return True
            else:
                logger.warning(f"Bot {bot_config_id}的定时任务不存在")
                return False
        except Exception as e:
            logger.error(f"移除Bot {bot_config_id}的定时任务失败: {e}")
            return False
    
    async def update_bot_task(self, bot_config_id: int, interval_hours: int):
        """更新单个bot的定时任务"""
        return await self.add_bot_task(bot_config_id, interval_hours)
    
    async def reload_all_bot_tasks(self):
        """重新加载所有bot的定时任务"""
        try:
            async with AsyncSessionLocal() as db:
                # 获取所有启用自动爬取的bot配置
                active_configs = await CRUDBotConfig.get_active_configs_for_auto_scraping(db)
                
                # 获取当前所有bot任务的job_id
                current_bot_jobs = [
                    job.id for job in self.scheduler.get_jobs() 
                    if job.id.startswith('bot_scraping_')
                ]
                
                # 移除所有现有的bot任务
                for job_id in current_bot_jobs:
                    try:
                        self.scheduler.remove_job(job_id)
                    except:
                        pass
                
                # 为每个活跃的bot配置添加任务
                added_tasks = 0
                for config in active_configs:
                    success = await self.add_bot_task(
                        config.id, 
                        config.scrape_interval_hours
                    )
                    if success:
                        added_tasks += 1
                
                logger.info(f"重新加载bot任务完成: 添加了{added_tasks}个任务")
                return added_tasks
        except Exception as e:
            logger.error(f"重新加载bot任务失败: {e}")
            return 0
    
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
        
        self.scheduler.start()
        self._running = True
        logger.info("定时任务调度器已启动")
        
        # 打印已注册的任务
        jobs = self.scheduler.get_jobs()
        for job in jobs:
            logger.info(f"已注册任务: {job.name} (ID: {job.id})")
    
    async def start_with_bot_tasks(self):
        """启动调度器并加载所有bot任务"""
        # 先启动基础调度器
        self.start()
        
        # 然后加载所有bot任务
        if self._running:
            added_tasks = await self.reload_all_bot_tasks()
            logger.info(f"调度器启动完成，已加载{added_tasks}个bot任务")
    
    def get_bot_tasks_status(self):
        """获取所有bot任务的状态"""
        bot_tasks = []
        for job in self.scheduler.get_jobs():
            if job.id.startswith('bot_scraping_'):
                bot_config_id = int(job.id.replace('bot_scraping_', ''))
                
                # 获取下次执行时间
                next_run_time = job.next_run_time.isoformat() if job.next_run_time else None
                
                # 获取触发器信息
                trigger_info = str(job.trigger)
                
                bot_tasks.append({
                    'bot_config_id': bot_config_id,
                    'job_id': job.id,
                    'job_name': job.name,
                    'next_run_time': next_run_time,
                    'trigger_info': trigger_info,
                    'is_running': not job.pending
                })
        
        return bot_tasks
    
    def get_bot_task_info(self, bot_config_id: int):
        """获取特定bot任务的信息"""
        job_id = f"bot_scraping_{bot_config_id}"
        job = self.scheduler.get_job(job_id)
        
        if not job:
            return None
        
        return {
            'bot_config_id': bot_config_id,
            'job_id': job.id,
            'job_name': job.name,
            'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger_info': str(job.trigger),
            'is_running': not job.pending,
            'args': job.args,
            'kwargs': job.kwargs
        }
    
    def shutdown(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("定时任务调度器已关闭")


# 全局调度器实例
task_scheduler = TaskScheduler()