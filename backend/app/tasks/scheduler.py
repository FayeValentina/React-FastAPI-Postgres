from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import (
    EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
)
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.config import settings
from app.tasks.manager import TaskManager
from app.db.base import AsyncSessionLocal

logger = logging.getLogger(__name__)


class EnhancedScheduler:
    """增强的任务调度器"""
    
    def __init__(self):
        # 配置作业存储 - 使用 SQLAlchemyJobStore
        jobstores = {
            'default': SQLAlchemyJobStore(
                url=settings.postgres.SQLALCHEMY_DATABASE_URL.replace(
                    '+asyncpg', ''  # SQLAlchemyJobStore需要同步驱动
                ),
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
            'max_instances': 3,
            'misfire_grace_time': 30
        }
        
        # 创建调度器
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        
        self.manager = TaskManager(self.scheduler)
        
        # 添加任务配置缓存
        self.job_configs = {}  # 存储任务的额外配置
        
        self._setup_listeners()
        self._running = False
    
    def _setup_listeners(self):
        """设置事件监听器"""
        self.scheduler.add_listener(
            self._job_executed_listener,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._job_error_listener,
            EVENT_JOB_ERROR
        )
        self.scheduler.add_listener(
            self._job_missed_listener,
            EVENT_JOB_MISSED
        )
    
    def _job_executed_listener(self, event):
        """作业执行成功监听器 - 改进版"""
        logger.info(f"作业 {event.job_id} 执行成功")
        
        # 异步记录到数据库
        asyncio.create_task(self._record_job_event(
            event.job_id, 
            'executed',
            event.retval if hasattr(event, 'retval') else None
        ))
    
    def _job_error_listener(self, event):
        """作业执行错误监听器 - 改进版"""
        logger.error(
            f"作业 {event.job_id} 执行失败: {event.exception}",
            exc_info=event.exception
        )
        
        # 异步记录到数据库
        asyncio.create_task(self._record_job_event(
            event.job_id,
            'error',
            error=str(event.exception),
            traceback=event.traceback if hasattr(event, 'traceback') else None
        ))
    
    def _job_missed_listener(self, event):
        """作业错过执行监听器"""
        logger.warning(f"作业 {event.job_id} 错过了执行时间")
        
        # 异步记录到数据库
        asyncio.create_task(self._record_job_event(
            event.job_id,
            'missed'
        ))
    
    async def _record_job_event(self, job_id: str, event_type: str, result=None, error=None, traceback=None):
        """记录任务事件到数据库"""
        try:
            async with AsyncSessionLocal() as db:
                # 这里可以记录到TaskExecution表或创建新的事件表
                # 目前先记录日志，具体实现可以根据需要调整
                logger.info(f"记录任务事件: {job_id} - {event_type}")
        except Exception as e:
            logger.error(f"记录任务事件失败: {e}")
    
    def add_job_with_config(
        self,
        func: str,
        trigger: str,
        id: str,
        name: str = None,
        args: list = None,
        kwargs: dict = None,
        max_retries: int = 0,  # 新增：最大重试次数
        retry_interval: int = 60,  # 新增：重试间隔（秒）
        timeout: int = None,  # 新增：任务超时时间（秒）
        **trigger_args
    ):
        """添加任务的增强版本，支持重试和超时配置"""
        # 存储额外配置
        self.job_configs[id] = {
            'max_retries': max_retries,
            'retry_interval': retry_interval,
            'timeout': timeout,
            'retry_count': 0
        }
        
        # 包装原始函数以支持超时和重试
        if timeout:
            kwargs = kwargs or {}
            kwargs['_timeout'] = timeout
            
        self.add_job(func, trigger, id, name, args, kwargs, **trigger_args)
    
    def add_job(
        self,
        func: str,  # 明确标注只接受字符串
        trigger: str,
        id: str,
        name: str = None,
        args: list = None,
        kwargs: dict = None,
        **trigger_args
    ):
        """添加任务的便捷方法"""
        
        # 确保 func 是字符串引用
        if not isinstance(func, str):
            raise ValueError(
                f"func 必须是字符串引用，格式为 'module:function'，"
                f"收到的类型: {type(func)}"
            )
        
        # 根据触发器类型创建触发器对象
        if trigger == 'interval':
            trigger_obj = IntervalTrigger(**trigger_args)
        elif trigger == 'cron':
            trigger_obj = CronTrigger(**trigger_args)
        elif trigger == 'date':
            trigger_obj = DateTrigger(**trigger_args)
        else:
            raise ValueError(f"不支持的触发器类型: {trigger}")
        
        # 准备job参数，自动添加 _job_id
        job_kwargs = kwargs or {}
        job_kwargs['_job_id'] = id  # 确保每个任务都能获取到 job_id
        job_args = args or []
        
        self.scheduler.add_job(
            func,
            trigger=trigger_obj,
            id=id,
            name=name or id,
            args=job_args,
            kwargs=job_kwargs,
            replace_existing=True
        )
    
    def remove_job(self, job_id: str):
        """移除任务"""
        self.scheduler.remove_job(job_id)
    
    def pause_job(self, job_id: str):
        """暂停任务"""
        self.scheduler.pause_job(job_id)
    
    def resume_job(self, job_id: str):
        """恢复任务"""
        self.scheduler.resume_job(job_id)
    
    def get_job(self, job_id: str):
        """获取任务信息"""
        return self.scheduler.get_job(job_id)
    
    def get_jobs(self):
        """获取所有任务"""
        return self.scheduler.get_jobs()
    
    async def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("调度器已经在运行")
            return
            
        self.scheduler.start()
        self._running = True
        
        # 注册所有任务
        await self._register_all_tasks()
        
        logger.info("任务调度器已启动")
        
        # 打印已加载的任务
        jobs = self.get_jobs()
        logger.info(f"已加载 {len(jobs)} 个任务")
        for job in jobs:
            logger.info(f"- {job.name} (ID: {job.id}, 下次运行: {job.next_run_time})")
    
    async def _register_all_tasks(self):
        """注册所有定时任务"""
        # 导入任务模块，这会自动注册任务
        from app.tasks.jobs import cleanup, scraping
        
        # 为所有启用自动爬取的Bot配置添加任务
        from app.crud.bot_config import CRUDBotConfig
        async with AsyncSessionLocal() as db:
            active_configs = await CRUDBotConfig.get_active_configs_for_auto_scraping(db)
            
            for config in active_configs:
                from app.tasks.jobs.scraping import create_bot_scraping_task
                await create_bot_scraping_task(config.id, config.scrape_interval_hours)
                logger.info(f"已为Bot配置 {config.id} 添加定时任务")
    
    def shutdown(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("任务调度器已关闭")


# 全局调度器实例
task_scheduler = EnhancedScheduler()