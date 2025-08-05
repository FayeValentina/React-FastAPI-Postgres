"""
调度管理服务
提供统一的调度管理接口
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from app.tasks.schedulers import scheduler
from app.tasks.senders import MessageSender

# 创建MessageSender实例
message_sender = MessageSender()

logger = logging.getLogger(__name__)


class ScheduleManager:
    """调度管理器，提供调度相关的业务逻辑"""
    
    # === Bot爬取调度管理 ===
    
    @staticmethod
    def create_bot_schedule(
        bot_config_id: int,
        bot_config_name: str,
        interval_hours: int
    ) -> str:
        """创建Bot爬取调度"""
        try:
            job_id = scheduler.add_bot_scraping_schedule(
                bot_config_id, bot_config_name, interval_hours
            )
            logger.info(f"已创建Bot {bot_config_id} 的调度，任务ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"创建Bot调度失败: {e}")
            raise
    
    @staticmethod
    def update_bot_schedule(
        bot_config_id: int,
        bot_config_name: str,
        interval_hours: int
    ) -> str:
        """更新Bot爬取调度"""
        try:
            job_id = scheduler.update_bot_scraping_schedule(
                bot_config_id, bot_config_name, interval_hours
            )
            logger.info(f"已更新Bot {bot_config_id} 的调度，任务ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"更新Bot调度失败: {e}")
            raise
    
    @staticmethod
    def remove_bot_schedule(bot_config_id: int) -> bool:
        """移除Bot爬取调度"""
        try:
            success = scheduler.remove_bot_scraping_schedule(bot_config_id)
            if success:
                logger.info(f"已移除Bot {bot_config_id} 的调度")
            return success
        except Exception as e:
            logger.error(f"移除Bot调度失败: {e}")
            return False
    
    @staticmethod
    def pause_bot_schedule(bot_config_id: int) -> bool:
        """暂停Bot爬取调度"""
        job_id = f'bot_scraping_{bot_config_id}'
        return scheduler.pause_schedule(job_id)
    
    @staticmethod
    def resume_bot_schedule(bot_config_id: int) -> bool:
        """恢复Bot爬取调度"""
        job_id = f'bot_scraping_{bot_config_id}'
        return scheduler.resume_schedule(job_id)
    
    # === 手动任务触发 ===
    
    @staticmethod
    def trigger_manual_scraping(
        bot_config_id: int,
        session_type: str = "manual"
    ) -> str:
        """手动触发爬取任务"""
        try:
            task_id = message_sender.send_manual_scraping_task(
                bot_config_id, session_type, queue='scraping'
            )
            logger.info(f"已手动触发Bot {bot_config_id} 爬取任务，任务ID: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"手动触发爬取任务失败: {e}")
            raise
    
    @staticmethod
    def trigger_batch_scraping(
        bot_config_ids: List[int],
        session_type: str = "manual"
    ) -> str:
        """手动触发批量爬取任务"""
        try:
            task_id = message_sender.send_batch_scraping_task(
                bot_config_ids, session_type, queue='scraping'
            )
            logger.info(f"已手动触发批量爬取任务，Bot数量: {len(bot_config_ids)}, 任务ID: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"手动触发批量爬取任务失败: {e}")
            raise
    
    @staticmethod
    def trigger_cleanup_task(days_old: int = 30) -> str:
        """手动触发清理任务"""
        try:
            task_id = message_sender.send_cleanup_task(days_old, queue='cleanup')
            logger.info(f"已手动触发清理任务，清理天数: {days_old}, 任务ID: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"手动触发清理任务失败: {e}")
            raise
    
    # === 任务状态管理 ===
    
    @staticmethod
    def get_task_status(task_id: str) -> Dict[str, Any]:
        """获取Celery任务状态"""
        return message_sender.get_task_status(task_id)
    
    @staticmethod
    def cancel_task(task_id: str, terminate: bool = False) -> Dict[str, Any]:
        """取消Celery任务"""
        return message_sender.revoke_task(task_id, terminate)
    
    @staticmethod
    def get_active_tasks() -> List[Dict[str, Any]]:
        """获取活跃的Celery任务"""
        return message_sender.get_active_tasks()
    
    @staticmethod
    def get_queue_length(queue_name: str) -> int:
        """获取队列长度"""
        return message_sender.get_queue_length(queue_name)
    
    # === 调度状态管理 ===
    
    @staticmethod
    def get_schedule_info(schedule_id: str) -> Optional[Dict[str, Any]]:
        """获取调度任务信息"""
        try:
            job = scheduler.get_schedule(schedule_id)
            if not job:
                return None
            
            config = scheduler.get_schedule_config(schedule_id)
            
            return {
                "schedule_id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "config": config,
                "pending": job.pending,
            }
        except Exception as e:
            logger.error(f"获取调度信息失败: {e}")
            return None
    
    @staticmethod
    def get_all_schedules() -> List[Dict[str, Any]]:
        """获取所有调度任务信息"""
        try:
            jobs = scheduler.get_all_schedules()
            schedules = []
            
            for job in jobs:
                config = scheduler.get_schedule_config(job.id)
                schedules.append({
                    "schedule_id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger),
                    "config": config,
                    "pending": job.pending,
                })
            
            return schedules
        except Exception as e:
            logger.error(f"获取所有调度信息失败: {e}")
            return []
    
    @staticmethod
    def get_bot_schedule_info(bot_config_id: int) -> Optional[Dict[str, Any]]:
        """获取Bot的调度信息"""
        schedule_id = f'bot_scraping_{bot_config_id}'
        return ScheduleManager.get_schedule_info(schedule_id)
    
    # === 系统状态统计 ===
    
    @staticmethod
    def get_system_status() -> Dict[str, Any]:
        """获取整个任务系统的状态"""
        try:
            # 调度任务统计
            all_schedules = ScheduleManager.get_all_schedules()
            active_schedules = len([s for s in all_schedules if s.get("next_run_time")])
            
            # Celery任务统计
            active_tasks = ScheduleManager.get_active_tasks()
            
            # 队列长度统计
            scraping_queue_length = message_sender.get_queue_length('scraping')
            cleanup_queue_length = message_sender.get_queue_length('cleanup')
            default_queue_length = message_sender.get_queue_length('default')
            
            return {
                "scheduler": {
                    "total_schedules": len(all_schedules),
                    "active_schedules": active_schedules,
                    "running": scheduler._running,
                },
                "celery": {
                    "active_tasks": len(active_tasks),
                    "tasks": active_tasks,
                },
                "queues": {
                    "scraping": scraping_queue_length,
                    "cleanup": cleanup_queue_length,
                    "default": default_queue_length,
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    # === 清理任务调度管理 ===
    
    @staticmethod
    def create_cleanup_schedule(
        schedule_id: str = "cleanup_old_sessions",
        days_old: int = 30,
        cron_expression: str = "0 2 * * *"
    ) -> str:
        """创建清理任务调度"""
        try:
            job_id = scheduler.add_cleanup_schedule(
                schedule_id, days_old, cron_expression
            )
            logger.info(f"已创建清理任务调度，ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"创建清理任务调度失败: {e}")
            raise
    
    @staticmethod
    def update_cleanup_schedule(
        schedule_id: str,
        days_old: int,
        cron_expression: str
    ) -> str:
        """更新清理任务调度"""
        try:
            # 先移除旧的
            scheduler.remove_schedule(schedule_id)
            # 再添加新的
            job_id = scheduler.add_cleanup_schedule(
                schedule_id, days_old, cron_expression
            )
            logger.info(f"已更新清理任务调度，ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"更新清理任务调度失败: {e}")
            raise