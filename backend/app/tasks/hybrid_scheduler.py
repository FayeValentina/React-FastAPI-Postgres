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
from app.tasks.message_sender import MessageSender
from app.db.base import AsyncSessionLocal

logger = logging.getLogger(__name__)


# 独立的任务函数，避免序列化scheduler实例
async def send_bot_scraping_task(bot_config_id: int):
    """发送Bot爬取任务到Celery队列（独立函数，避免序列化问题）"""
    try:
        from app.celery_app import celery_app
        result = celery_app.send_task(
            'execute_bot_scraping_task',
            args=[bot_config_id],
            queue='scraping'
        )
        task_id = result.id
        logger.info(f"调度器已发送Bot {bot_config_id} 爬取任务到Celery，任务ID: {task_id}")
        return task_id
    except Exception as e:
        logger.error(f"发送Bot爬取任务到Celery失败: {e}")
        raise


async def send_cleanup_task(days_old: int):
    """发送清理任务到Celery队列（独立函数，避免序列化问题）"""
    try:
        from app.celery_app import celery_app
        result = celery_app.send_task(
            'cleanup_old_sessions_task',
            args=[days_old],
            queue='cleanup'
        )
        task_id = result.id
        logger.info(f"调度器已发送清理任务到Celery，任务ID: {task_id}")
        return task_id
    except Exception as e:
        logger.error(f"发送清理任务到Celery失败: {e}")
        raise


async def send_custom_task(celery_task_name: str, args: list, kwargs: dict):
    """发送自定义任务到Celery队列（独立函数，避免序列化问题）"""
    try:
        from app.celery_app import celery_app
        result = celery_app.send_task(celery_task_name, args=args, kwargs=kwargs)
        task_id = result.id
        logger.info(f"调度器已发送自定义任务 {celery_task_name} 到Celery，任务ID: {task_id}")
        return task_id
    except Exception as e:
        logger.error(f"发送自定义任务到Celery失败: {e}")
        raise


class HybridScheduler:
    """混合调度器 - APScheduler负责调度，Celery负责执行"""
    
    def __init__(self):
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
        
        # 任务配置缓存
        self.job_configs = {}
        
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
        
        # 异步记录到数据库
        asyncio.create_task(self._record_job_event(
            event.job_id, 
            'scheduled',
            event.retval if hasattr(event, 'retval') else None
        ))
    
    def _job_error_listener(self, event):
        """作业执行错误监听器"""
        logger.error(
            f"调度任务 {event.job_id} 执行失败: {event.exception}",
            exc_info=event.exception
        )
        
        # 异步记录到数据库
        asyncio.create_task(self._record_job_event(
            event.job_id,
            'schedule_error',
            error=str(event.exception),
            traceback=event.traceback if hasattr(event, 'traceback') else None
        ))
    
    def _job_missed_listener(self, event):
        """作业错过执行监听器"""
        logger.warning(f"调度任务 {event.job_id} 错过了执行时间")
        
        # 异步记录到数据库
        asyncio.create_task(self._record_job_event(
            event.job_id,
            'missed'
        ))
    
    async def _record_job_event(self, job_id: str, event_type: str, result=None, error=None, traceback=None):
        """记录任务事件到数据库"""
        try:
            async with AsyncSessionLocal() as db:
                from app.models.schedule_event import ScheduleEvent, ScheduleEventType
                
                # 获取任务配置信息
                job_config = self.job_configs.get(job_id, {})
                job_name = job_config.get('bot_config_name', job_id)
                
                # 处理任务名称
                if job_config.get('type') == 'bot_scraping':
                    job_name = f"Bot自动爬取: {job_config.get('bot_config_name', 'Unknown')}"
                elif job_config.get('type') == 'cleanup':
                    job_name = f"数据清理: {job_config.get('days_old', 30)}天前"
                else:
                    job_name = f"调度任务: {job_id}"
                
                # 映射事件类型
                event_type_map = {
                    'scheduled': ScheduleEventType.SCHEDULED,
                    'schedule_error': ScheduleEventType.ERROR,
                    'missed': ScheduleEventType.MISSED
                }
                
                event_type_enum = event_type_map.get(event_type, ScheduleEventType.EXECUTED)
                
                # 创建调度事件记录
                event = ScheduleEvent(
                    job_id=job_id,
                    job_name=job_name,
                    event_type=event_type_enum,  # 使用枚举值
                    result=result if isinstance(result, dict) else {'result': str(result)} if result else None,
                    error_message=error,
                    error_traceback=traceback
                )
                
                db.add(event)
                await db.commit()
                
                logger.info(f"已记录调度事件到数据库: {job_id} - {event_type}")
                
        except Exception as e:
            logger.error(f"记录调度事件失败: {e}")
    
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
            # 存储任务配置
            self.job_configs[job_id] = {
                'type': 'bot_scraping',
                'bot_config_id': bot_config_id,
                'bot_config_name': bot_config_name,
                'interval_hours': interval_hours
            }
            
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
            if job_id in self.job_configs:
                del self.job_configs[job_id]
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
            # 存储任务配置
            self.job_configs[schedule_id] = {
                'type': 'cleanup',
                'days_old': days_old,
                'cron_expression': cron_expression
            }
            
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
            # 存储任务配置
            self.job_configs[schedule_id] = {
                'type': 'custom',
                'celery_task_name': celery_task_name,
                'trigger_type': trigger_type,
                'args': args or [],
                'kwargs': kwargs or {},
                'trigger_args': trigger_args
            }
            
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
            if schedule_id in self.job_configs:
                del self.job_configs[schedule_id]
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
        return self.job_configs.get(schedule_id)
    
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


# 全局混合调度器实例

scheduler = HybridScheduler()



