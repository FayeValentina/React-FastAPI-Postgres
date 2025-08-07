"""
纯APScheduler调度器 - 只负责时间调度，从task_config表读取配置
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
from typing import Optional, Any, Callable, List
from datetime import datetime

from .config import settings
from app.db.base import AsyncSessionLocal

logger = logging.getLogger(__name__)


class Scheduler:
    """纯APScheduler封装 - 从task_config表读取配置并调度"""
    
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
    
    async def load_tasks_from_database(self) -> List[dict]:
        """从task_config表加载活跃的任务配置"""
        try:
            async with AsyncSessionLocal() as db:
                from app.crud.task_config import crud_task_config
                from app.core.task_type import TaskStatus
                
                # 获取所有活跃的任务配置
                active_configs = await crud_task_config.get_active_configs(db)
                
                tasks = []
                for config in active_configs:
                    if config.schedule_config:
                        tasks.append({
                            'task_config_id': config.id,
                            'job_id': str(config.id),
                            'name': config.name,
                            'task_type': config.task_type,
                            'schedule_config': config.schedule_config,
                            'task_params': config.task_params,
                            'max_instances': config.max_instances or 1,
                            'timeout_seconds': config.timeout_seconds or 300,
                            'retry_count': config.retry_count or 0
                        })
                
                logger.info(f"从数据库加载了 {len(tasks)} 个活跃任务配置")
                return tasks
                
        except Exception as e:
            logger.error(f"从数据库加载任务配置失败: {e}")
            return []
    
    async def register_tasks_from_database(self, execution_func: Callable):
        """从数据库注册所有活跃任务到调度器"""
        tasks = await self.load_tasks_from_database()
        
        for task_data in tasks:
            try:
                await self._register_single_task(task_data, execution_func)
            except Exception as e:
                logger.error(f"注册任务失败 {task_data['job_id']}: {e}")
    
    async def _register_single_task(self, task_data: dict, execution_func: Callable):
        """注册单个任务到调度器"""
        schedule_config = task_data['schedule_config']
        scheduler_type = schedule_config.get('scheduler_type')
        
        # 准备触发器参数
        trigger_kwargs = {}
        
        if scheduler_type == 'interval':
            trigger_type = 'interval'
            if 'seconds' in schedule_config:
                trigger_kwargs['seconds'] = schedule_config['seconds']
            if 'minutes' in schedule_config:
                trigger_kwargs['minutes'] = schedule_config['minutes']
            if 'hours' in schedule_config:
                trigger_kwargs['hours'] = schedule_config['hours']
            if 'days' in schedule_config:
                trigger_kwargs['days'] = schedule_config['days']
                
        elif scheduler_type == 'cron':
            trigger_type = 'cron'
            cron_fields = ['second', 'minute', 'hour', 'day', 'month', 'day_of_week', 'year']
            for field in cron_fields:
                if field in schedule_config:
                    trigger_kwargs[field] = schedule_config[field]
                    
        elif scheduler_type == 'date':
            trigger_type = 'date'
            if 'run_date' in schedule_config:
                # 解析日期字符串
                if isinstance(schedule_config['run_date'], str):
                    trigger_kwargs['run_date'] = datetime.fromisoformat(schedule_config['run_date'])
                else:
                    trigger_kwargs['run_date'] = schedule_config['run_date']
        else:
            logger.warning(f"不支持的调度器类型: {scheduler_type}")
            return
        
        # 添加任务到调度器
        self.add_job(
            func=execution_func,
            trigger_type=trigger_type,
            job_id=task_data['job_id'],
            name=task_data['name'],
            args=[task_data['task_config_id']],  # 传递task_config_id作为参数
            max_instances=task_data['max_instances'],
            **trigger_kwargs
        )
    
    def add_job(
        self,
        func: Callable,
        trigger_type: str,
        job_id: str,
        name: str = None,
        args: list = None,
        kwargs: dict = None,
        replace_existing: bool = True,
        max_instances: int = None,
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
            job_kwargs = {
                'func': func,
                'trigger': trigger,
                'id': job_id,
                'name': name or job_id,
                'args': args or [],
                'kwargs': kwargs or {},
                'replace_existing': replace_existing
            }
            
            # 如果指定了max_instances，添加到job配置中
            if max_instances is not None:
                job_kwargs['max_instances'] = max_instances
            
            self.scheduler.add_job(**job_kwargs)
            
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
    
    async def reload_task_from_database(self, task_config_id: int, execution_func: Callable) -> bool:
        """从数据库重新加载指定任务配置"""
        try:
            async with AsyncSessionLocal() as db:
                from app.crud.task_config import crud_task_config
                
                config = await crud_task_config.get(db, id=task_config_id)
                if not config or not config.schedule_config:
                    return False
                
                task_data = {
                    'task_config_id': config.id,
                    'job_id': str(config.id),
                    'name': config.name,
                    'task_type': config.task_type,
                    'schedule_config': config.schedule_config,
                    'task_params': config.task_params,
                    'max_instances': config.max_instances or 1,
                    'timeout_seconds': config.timeout_seconds or 300,
                    'retry_count': config.retry_count or 0
                }
                
                # 先移除现有任务
                self.remove_job(task_data['job_id'])
                
                # 重新注册任务
                await self._register_single_task(task_data, execution_func)
                logger.info(f"已重新加载任务配置: {task_config_id}")
                return True
                
        except Exception as e:
            logger.error(f"重新加载任务配置失败 {task_config_id}: {e}")
            return False
    
    def remove_task_by_config_id(self, task_config_id: int) -> bool:
        """根据任务配置ID移除调度任务"""
        return self.remove_job(str(task_config_id))
    
    def print_jobs(self):
        """打印所有任务（调试用）"""
        jobs = self.get_all_jobs()
        logger.info(f"当前有 {len(jobs)} 个调度任务:")
        for job in jobs:
            logger.info(f"- {job.name} (ID: {job.id}, 下次运行: {job.next_run_time})")


# 全局调度器实例
scheduler = Scheduler()