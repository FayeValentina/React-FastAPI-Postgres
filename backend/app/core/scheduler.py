"""
纯APScheduler调度器 - 只负责时间调度，不管配置和事件
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import (
    EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
)
import logging
from typing import Optional, Any, Callable
from datetime import datetime

from .config import settings

logger = logging.getLogger(__name__)


class Scheduler:
    """纯APScheduler封装 - 只负责调度，不管其他业务逻辑"""
    
    def __init__(self):
        # 配置作业存储
        jobstores = {
            'default': SQLAlchemyJobStore(
                url=settings.postgres.SYNC_DATABASE_URL,
                tablename='apscheduler_jobs'
            )
        }
        
        # 配置执行器
        executors = {
            'default': AsyncIOExecutor(),
        }
        
        # 配置作业默认设置
        job_defaults = {
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 30
        }
        
        # 创建调度器
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        
        self._running = False
        self._event_listeners = []
    
    def add_event_listener(self, callback: Callable, event_type: int):
        """添加事件监听器"""
        self.scheduler.add_listener(callback, event_type)
        self._event_listeners.append((callback, event_type))
    
    def add_job(
        self,
        func: Callable,
        trigger_type: str,
        job_id: str,
        name: str = None,
        args: list = None,
        kwargs: dict = None,
        replace_existing: bool = True,
        **trigger_kwargs
    ) -> str:
        """添加调度任务"""
        try:
            # 创建触发器
            if trigger_type == 'interval':
                trigger = IntervalTrigger(**trigger_kwargs)
            elif trigger_type == 'cron':
                trigger = CronTrigger(**trigger_kwargs)
            elif trigger_type == 'date':
                trigger = DateTrigger(**trigger_kwargs)
            else:
                raise ValueError(f"不支持的触发器类型: {trigger_type}")
            
            # 添加任务
            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                name=name or job_id,
                args=args or [],
                kwargs=kwargs or {},
                replace_existing=replace_existing
            )
            
            logger.info(f"已添加调度任务: {job_id}")
            return job_id
            
        except Exception as e:
            logger.error(f"添加调度任务失败 {job_id}: {e}")
            raise
    
    def remove_job(self, job_id: str) -> bool:
        """移除调度任务"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"已移除调度任务: {job_id}")
            return True
        except Exception as e:
            logger.error(f"移除调度任务失败 {job_id}: {e}")
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """暂停调度任务"""
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"已暂停调度任务: {job_id}")
            return True
        except Exception as e:
            logger.error(f"暂停调度任务失败 {job_id}: {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """恢复调度任务"""
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"已恢复调度任务: {job_id}")
            return True
        except Exception as e:
            logger.error(f"恢复调度任务失败 {job_id}: {e}")
            return False
    
    def get_job(self, job_id: str):
        """获取调度任务"""
        return self.scheduler.get_job(job_id)
    
    def get_all_jobs(self):
        """获取所有调度任务"""
        return self.scheduler.get_jobs()
    
    def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("调度器已经在运行")
            return
            
        self.scheduler.start()
        self._running = True
        logger.info("调度器已启动")
    
    def shutdown(self, wait: bool = True):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            self._running = False
            logger.info("调度器已关闭")
    
    @property
    def running(self) -> bool:
        """调度器是否运行中"""
        return self._running
    
    def print_jobs(self):
        """打印所有任务（调试用）"""
        jobs = self.get_all_jobs()
        logger.info(f"当前有 {len(jobs)} 个调度任务:")
        for job in jobs:
            logger.info(f"- {job.name} (ID: {job.id}, 下次运行: {job.next_run_time})")


# 全局调度器实例
scheduler = Scheduler()