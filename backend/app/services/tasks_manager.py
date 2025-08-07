"""
统一任务管理器 - 协调4个核心组件
"""
import logging
from typing import Dict, Any, List
from datetime import datetime

from app.core.scheduler import scheduler
from app.core.event_recorder import event_recorder
from app.core.task_dispatcher import task_dispatcher
from app.core.job_config_manager import job_config_manager

logger = logging.getLogger(__name__)


# 调度任务的包装函数（避免序列化问题）
async def send_bot_scraping_task(bot_config_id: int):
    """发送Bot爬取任务的包装函数"""
    return task_dispatcher.dispatch_bot_scraping(bot_config_id)

async def send_cleanup_sessions_task(days_old: int):
    """发送清理会话任务的包装函数"""
    return task_dispatcher.dispatch_cleanup_sessions(days_old)

async def send_cleanup_tokens_task():
    """发送清理令牌任务的包装函数"""
    return task_dispatcher.dispatch_cleanup_tokens()

async def send_cleanup_content_task(days_old: int):
    """发送清理内容任务的包装函数"""
    return task_dispatcher.dispatch_cleanup_content(days_old)

async def send_cleanup_events_task(days_old: int):
    """发送清理事件任务的包装函数"""
    return task_dispatcher.dispatch_cleanup_events(days_old)


class TaskManager:
    """统一任务管理器 - 协调调度器、分发器、记录器和配置管理器"""
    
    def __init__(self):
        # 设置事件监听器
        self._setup_event_listeners()
    
    def _setup_event_listeners(self):
        """设置调度器事件监听器"""
        from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
        
        scheduler.add_event_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        scheduler.add_event_listener(self._on_job_error, EVENT_JOB_ERROR)
        scheduler.add_event_listener(self._on_job_missed, EVENT_JOB_MISSED)
    
    def _on_job_executed(self, event):
        """任务执行成功事件处理"""
        job_config = job_config_manager.get_config(event.job_id)
        job_name = job_config.get('name', event.job_id) if job_config else event.job_id
        
        # 异步记录事件（不阻塞调度器）
        import asyncio
        asyncio.create_task(event_recorder.record_schedule_event(
            job_id=event.job_id,
            event_type='executed',
            job_name=job_name,
            result=event.retval if hasattr(event, 'retval') else None
        ))
    
    def _on_job_error(self, event):
        """任务执行错误事件处理"""
        job_config = job_config_manager.get_config(event.job_id)
        job_name = job_config.get('name', event.job_id) if job_config else event.job_id
        
        # 异步记录事件
        import asyncio
        asyncio.create_task(event_recorder.record_schedule_event(
            job_id=event.job_id,
            event_type='error',
            job_name=job_name,
            error_message=str(event.exception),
            error_traceback=event.traceback if hasattr(event, 'traceback') else None
        ))
    
    def _on_job_missed(self, event):
        """任务错过执行事件处理"""
        job_config = job_config_manager.get_config(event.job_id)
        job_name = job_config.get('name', event.job_id) if job_config else event.job_id
        
        # 异步记录事件
        import asyncio
        asyncio.create_task(event_recorder.record_schedule_event(
            job_id=event.job_id,
            event_type='missed',
            job_name=job_name
        ))
    
    # === Bot爬取任务管理 ===
    
    def add_bot_scraping_schedule(
        self,
        bot_config_id: int,
        bot_config_name: str,
        interval_hours: int
    ) -> str:
        """添加Bot爬取任务调度"""
        job_id = f'bot_scraping_{bot_config_id}'
        
        try:
            # 注册配置
            config = {
                'type': 'bot_scraping',
                'name': f'Bot-{bot_config_name} 自动爬取',
                'bot_config_id': bot_config_id,
                'bot_config_name': bot_config_name,
                'interval_hours': interval_hours
            }
            job_config_manager.register_config(job_id, config)
            
            # 添加调度
            scheduler.add_job(
                func=send_bot_scraping_task,
                trigger_type='interval',
                job_id=job_id,
                name=config['name'],
                args=[bot_config_id],
                hours=interval_hours
            )
            
            logger.info(f"已添加Bot爬取调度: {job_id}, 间隔: {interval_hours}小时")
            return job_id
            
        except Exception as e:
            logger.error(f"添加Bot爬取调度失败: {e}")
            raise
    
    def remove_bot_scraping_schedule(self, bot_config_id: int) -> bool:
        """移除Bot爬取任务调度"""
        job_id = f'bot_scraping_{bot_config_id}'
        
        try:
            scheduler.remove_job(job_id)
            job_config_manager.remove_config(job_id)
            logger.info(f"已移除Bot爬取调度: {job_id}")
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
    
    # === 清理任务管理 ===
    
    def add_cleanup_schedule(
        self,
        schedule_id: str,
        cleanup_type: str,  # 'sessions', 'tokens', 'content', 'events'
        cron_expression: str,
        days_old: int = None
    ) -> str:
        """添加清理任务调度"""
        try:
            # 选择对应的发送函数和参数
            func_map = {
                'sessions': (send_cleanup_sessions_task, [days_old or 30]),
                'tokens': (send_cleanup_tokens_task, []),
                'content': (send_cleanup_content_task, [days_old or 90]),
                'events': (send_cleanup_events_task, [days_old or 30])
            }
            
            if cleanup_type not in func_map:
                raise ValueError(f"不支持的清理类型: {cleanup_type}")
            
            send_func, args = func_map[cleanup_type]
            
            # 注册配置
            config = {
                'type': 'cleanup',
                'name': f'清理{cleanup_type}任务',
                'cleanup_type': cleanup_type,
                'cron_expression': cron_expression,
                'days_old': days_old
            }
            job_config_manager.register_config(schedule_id, config)
            
            # 解析cron表达式
            cron_parts = cron_expression.split()
            if len(cron_parts) != 5:
                raise ValueError(f"无效的cron表达式: {cron_expression}")
            
            minute, hour, day, month, day_of_week = cron_parts
            
            # 添加调度
            scheduler.add_job(
                func=send_func,
                trigger_type='cron',
                job_id=schedule_id,
                name=config['name'],
                args=args,
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week
            )
            
            logger.info(f"已添加清理任务调度: {schedule_id}")
            return schedule_id
            
        except Exception as e:
            logger.error(f"添加清理任务调度失败: {e}")
            raise
    
    # === 手动触发任务 ===
    
    def trigger_manual_scraping(self, bot_config_id: int, session_type: str = "manual") -> str:
        """手动触发爬取任务"""
        return task_dispatcher.dispatch_manual_scraping(bot_config_id, session_type)
    
    def trigger_batch_scraping(self, bot_config_ids: List[int], session_type: str = "manual") -> str:
        """手动触发批量爬取任务"""
        return task_dispatcher.dispatch_batch_scraping(bot_config_ids, session_type)
    
    def trigger_cleanup(self, cleanup_type: str, days_old: int = None) -> str:
        """手动触发清理任务"""
        dispatch_map = {
            'sessions': lambda: task_dispatcher.dispatch_cleanup_sessions(days_old or 30),
            'tokens': lambda: task_dispatcher.dispatch_cleanup_tokens(),
            'content': lambda: task_dispatcher.dispatch_cleanup_content(days_old or 90),
            'events': lambda: task_dispatcher.dispatch_cleanup_events(days_old or 30)
        }
        
        if cleanup_type not in dispatch_map:
            raise ValueError(f"不支持的清理类型: {cleanup_type}")
        
        return dispatch_map[cleanup_type]()
    
    # === 系统管理 ===
    
    async def start(self):
        """启动任务管理器"""
        # 启动调度器
        scheduler.start()
        
        # 注册默认调度任务
        await self._register_default_schedules()
        
        logger.info("任务管理器已启动")
    
    async def _register_default_schedules(self):
        """注册默认的调度任务"""
        try:
            # 为所有启用自动爬取的Bot配置添加调度
            from app.crud.bot_config import CRUDBotConfig
            from app.db.base import AsyncSessionLocal
            
            async with AsyncSessionLocal() as db:
                active_configs = await CRUDBotConfig.get_active_configs_for_auto_scraping(db)
                
                for config in active_configs:
                    self.add_bot_scraping_schedule(
                        config.id, 
                        config.name, 
                        config.scrape_interval_hours
                    )
            
            # 添加默认清理任务
            self.add_cleanup_schedule("cleanup_sessions", "sessions", "0 2 * * *", 30)
            self.add_cleanup_schedule("cleanup_tokens", "tokens", "0 3 * * *")
            self.add_cleanup_schedule("cleanup_content", "content", "0 4 * * 0", 90)
            self.add_cleanup_schedule("cleanup_events", "events", "0 5 * * 0", 30)
            
        except Exception as e:
            logger.error(f"注册默认调度任务失败: {e}")
    
    def shutdown(self):
        """关闭任务管理器"""
        scheduler.shutdown()
        logger.info("任务管理器已关闭")
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "scheduler_running": scheduler.running,
            "total_jobs": len(scheduler.get_all_jobs()),
            "total_configs": len(job_config_manager.get_all_configs()),
            "active_tasks": len(task_dispatcher.get_active_tasks()),
            "timestamp": datetime.utcnow().isoformat()
        }


# 全局任务管理器实例
task_manager = TaskManager()