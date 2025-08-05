"""
混合调度器 - APScheduler + Celery
APScheduler负责定时调度，Celery负责任务执行
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
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.core.config import settings
from app.db.base import AsyncSessionLocal
from app.tasks.core import TaskDispatcher, EventRecorder, JobConfigManager

logger = logging.getLogger(__name__)


# 重构后使用TaskDispatcher的包装函数，避免序列化问题
async def send_bot_scraping_task(bot_config_id: int):
    """发送Bot爬取任务（使用TaskDispatcher）"""
    return TaskDispatcher.dispatch_bot_scraping(bot_config_id)


async def send_cleanup_task(days_old: int):
    """发送清理任务（使用TaskDispatcher）"""
    return TaskDispatcher.dispatch_cleanup(days_old)


async def send_custom_task(celery_task_name: str, args: list, kwargs: dict):
    """发送自定义任务（使用TaskDispatcher）"""
    return TaskDispatcher.dispatch_to_celery(celery_task_name, args, kwargs)


class HybridScheduler:
    """混合调度器 - APScheduler负责调度，Celery负责执行"""
    
    def __init__(
        self,
        task_dispatcher: Optional[TaskDispatcher] = None,
        config_manager: Optional[JobConfigManager] = None,
        event_recorder: Optional[EventRecorder] = None
    ):
        # 依赖注入核心组件
        self.task_dispatcher = task_dispatcher or TaskDispatcher()
        self.config_manager = config_manager or JobConfigManager()
        self.event_recorder = event_recorder or EventRecorder()
        
        # 配置作业存储 - 使用 SQLAlchemyJobStore
        jobstores = {
            'default': SQLAlchemyJobStore(
                url=settings.postgres.SYNC_DATABASE_URL,  # 使用同步URL
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
            'max_instances': 1,  # 减少实例数，因为实际执行在Celery
            'misfire_grace_time': 30
        }
        
        # 创建调度器
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        
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
        """作业执行成功监听器"""
        logger.info(f"调度任务 {event.job_id} 执行成功")
        
        # 使用EventRecorder记录事件
        job_config = self.config_manager.get_config(event.job_id)
        self.event_recorder.record_schedule_event_sync(
            event.job_id,
            'scheduled', 
            job_config,
            event.retval if hasattr(event, 'retval') else None
        )
    
    def _job_error_listener(self, event):
        """作业执行错误监听器"""
        logger.error(
            f"调度任务 {event.job_id} 执行失败: {event.exception}",
            exc_info=event.exception
        )
        
        # 使用EventRecorder记录事件
        job_config = self.config_manager.get_config(event.job_id)
        self.event_recorder.record_schedule_event_sync(
            event.job_id,
            'schedule_error',
            job_config,
            error=str(event.exception),
            traceback=event.traceback if hasattr(event, 'traceback') else None
        )
    
    def _job_missed_listener(self, event):
        """作业错过执行监听器"""
        logger.warning(f"调度任务 {event.job_id} 错过了执行时间")
        
        # 使用EventRecorder记录事件
        job_config = self.config_manager.get_config(event.job_id)
        self.event_recorder.record_schedule_event_sync(
            event.job_id,
            'missed',
            job_config
        )
    
    # 移除_record_job_event方法，现在使用EventRecorder处理
    
    # === Bot爬取任务调度方法 ===
    
    def add_bot_scraping_schedule(
        self,
        bot_config_id: int,
        bot_config_name: str,
        interval_hours: int,
        replace_existing: bool = True
    ) -> str:
        """添加Bot爬取任务调度"""
        job_id = f'bot_scraping_{bot_config_id}'
        
        try:
            # 使用JobConfigManager存储任务配置
            config = {
                'type': 'bot_scraping',
                'bot_config_id': bot_config_id,
                'bot_config_name': bot_config_name,
                'interval_hours': interval_hours
            }
            self.config_manager.register_config(job_id, config)
            
            # 添加到APScheduler，使用独立函数避免序列化问题
            self.scheduler.add_job(
                send_bot_scraping_task,
                trigger=IntervalTrigger(hours=interval_hours),
                id=job_id,
                name=f'Bot-{bot_config_name} 自动爬取调度',
                args=[bot_config_id],
                replace_existing=replace_existing
            )
            
            logger.info(f"已添加Bot {bot_config_id} 的调度任务，执行间隔: {interval_hours}小时")
            return job_id
            
        except Exception as e:
            logger.error(f"添加Bot爬取调度失败: {e}")
            raise
    
    def remove_bot_scraping_schedule(self, bot_config_id: int) -> bool:
        """移除Bot爬取任务调度"""
        job_id = f'bot_scraping_{bot_config_id}'
        try:
            self.scheduler.remove_job(job_id)
            self.config_manager.remove_config(job_id)
            logger.info(f"已移除Bot {bot_config_id} 的调度任务")
            return True
        except Exception as e:
            logger.error(f"移除Bot爬取调度失败: {e}")
            return False
    
    def update_bot_scraping_schedule(
        self,
        bot_config_id: int,
        bot_config_name: str,
        interval_hours: int
    ) -> str:
        """更新Bot爬取任务调度"""
        self.remove_bot_scraping_schedule(bot_config_id)
        return self.add_bot_scraping_schedule(bot_config_id, bot_config_name, interval_hours)
    
    
    # === 清理任务调度方法 ===
    
    def add_cleanup_schedule(
        self,
        schedule_id: str = "cleanup_old_sessions",
        days_old: int = 30,
        cron_expression: str = "0 2 * * *",  # 默认每天2点执行
        replace_existing: bool = True
    ) -> str:
        """添加清理任务调度"""
        try:
            # 使用JobConfigManager存储任务配置
            config = {
                'type': 'cleanup',
                'days_old': days_old,
                'cron_expression': cron_expression
            }
            self.config_manager.register_config(schedule_id, config)
            
            # 解析cron表达式
            cron_parts = cron_expression.split()
            if len(cron_parts) != 5:
                raise ValueError(f"无效的cron表达式: {cron_expression}")
            
            minute, hour, day, month, day_of_week = cron_parts
            
            # 添加到APScheduler，使用独立函数避免序列化问题
            self.scheduler.add_job(
                send_cleanup_task,
                trigger=CronTrigger(
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week
                ),
                id=schedule_id,
                name=f'清理旧会话调度 ({days_old}天)',
                args=[days_old],
                replace_existing=replace_existing
            )
            
            logger.info(f"已添加清理任务调度，ID: {schedule_id}, cron: {cron_expression}")
            return schedule_id
            
        except Exception as e:
            logger.error(f"添加清理任务调度失败: {e}")
            raise
    
    
    # === 通用调度方法 ===
    
    def add_custom_schedule(
        self,
        schedule_id: str,
        celery_task_name: str,
        trigger_type: str,
        args: List = None,
        kwargs: Dict = None,
        **trigger_args
    ) -> str:
        """添加自定义任务调度"""
        try:
            # 使用JobConfigManager存储任务配置
            config = {
                'type': 'custom',
                'celery_task_name': celery_task_name,
                'trigger_type': trigger_type,
                'args': args or [],
                'kwargs': kwargs or {},
                'trigger_args': trigger_args
            }
            self.config_manager.register_config(schedule_id, config)
            
            # 根据触发器类型创建触发器对象
            if trigger_type == 'interval':
                trigger_obj = IntervalTrigger(**trigger_args)
            elif trigger_type == 'cron':
                trigger_obj = CronTrigger(**trigger_args)
            elif trigger_type == 'date':
                trigger_obj = DateTrigger(**trigger_args)
            else:
                raise ValueError(f"不支持的触发器类型: {trigger_type}")
            
            # 添加到APScheduler，使用独立函数避免序列化问题
            self.scheduler.add_job(
                send_custom_task,
                trigger=trigger_obj,
                id=schedule_id,
                name=f'自定义任务调度: {celery_task_name}',
                args=[celery_task_name, args or [], kwargs or {}],
                replace_existing=True
            )
            
            logger.info(f"已添加自定义任务调度，ID: {schedule_id}")
            return schedule_id
            
        except Exception as e:
            logger.error(f"添加自定义任务调度失败: {e}")
            raise
    
    
    # === 调度器管理方法 ===
    
    def remove_schedule(self, schedule_id: str) -> bool:
        """移除调度任务"""
        try:
            self.scheduler.remove_job(schedule_id)
            self.config_manager.remove_config(schedule_id)
            logger.info(f"已移除调度任务: {schedule_id}")
            return True
        except Exception as e:
            logger.error(f"移除调度任务失败: {e}")
            return False
    
    def pause_schedule(self, schedule_id: str) -> bool:
        """暂停调度任务"""
        try:
            self.scheduler.pause_job(schedule_id)
            logger.info(f"已暂停调度任务: {schedule_id}")
            return True
        except Exception as e:
            logger.error(f"暂停调度任务失败: {e}")
            return False
    
    def resume_schedule(self, schedule_id: str) -> bool:
        """恢复调度任务"""
        try:
            self.scheduler.resume_job(schedule_id)
            logger.info(f"已恢复调度任务: {schedule_id}")
            return True
        except Exception as e:
            logger.error(f"恢复调度任务失败: {e}")
            return False
    
    def get_schedule(self, schedule_id: str):
        """获取调度任务信息"""
        return self.scheduler.get_job(schedule_id)
    
    def get_all_schedules(self):
        """获取所有调度任务"""
        return self.scheduler.get_jobs()
    
    def get_schedule_config(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """获取调度任务配置"""
        return self.config_manager.get_config(schedule_id)
    
    # === 调度器生命周期管理 ===
    
    async def start(self):
        """启动混合调度器"""
        if self._running:
            logger.warning("混合调度器已经在运行")
            return
            
        self.scheduler.start()
        self._running = True
        
        # 注册所有任务
        await self._register_all_schedules()
        
        logger.info("混合调度器已启动")
        
        # 打印已加载的调度任务
        jobs = self.get_all_schedules()
        logger.info(f"已加载 {len(jobs)} 个调度任务")
        for job in jobs:
            logger.info(f"- {job.name} (ID: {job.id}, 下次运行: {job.next_run_time})")
    
    async def _register_all_schedules(self):
        """注册所有调度任务"""
        try:
            # 为所有启用自动爬取的Bot配置添加调度任务
            from app.crud.bot_config import CRUDBotConfig
            async with AsyncSessionLocal() as db:
                active_configs = await CRUDBotConfig.get_active_configs_for_auto_scraping(db)
                
                for config in active_configs:
                    self.add_bot_scraping_schedule(
                        config.id, 
                        config.name, 
                        config.scrape_interval_hours
                    )
                    logger.info(f"已为Bot配置 {config.id} 添加调度任务")
            
            # 添加默认的清理任务调度
            self.add_cleanup_schedule(
                schedule_id="cleanup_old_sessions",
                days_old=30,
                cron_expression="0 2 * * *"  # 每天2点执行
            )
            
        except Exception as e:
            logger.error(f"注册调度任务失败: {e}")
    
    def shutdown(self):
        """关闭混合调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("混合调度器已关闭")


# 全局混合调度器实例（使用新的解耦架构）
scheduler = HybridScheduler()



