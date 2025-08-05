"""
消息发送服务
用于向Celery队列发送任务消息
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from app.celery_app import celery_app
from app.tasks.jobs import (
    execute_bot_scraping_task,
    manual_scraping_task,
    batch_scraping_task,
    cleanup_old_sessions_task,
    auto_scraping_all_configs_task
)

logger = logging.getLogger(__name__)


class MessageSender:
    """消息发送器类，负责向Celery队列发送任务"""
    
    @staticmethod
    def send_bot_scraping_task(
        bot_config_id: int,
        queue: str = 'scraping',
        countdown: Optional[int] = None,
        eta: Optional[datetime] = None
    ) -> str:
        """发送Bot爬取任务到队列"""
        try:
            task_args = {
                'queue': queue,
            }
            
            if countdown:
                task_args['countdown'] = countdown
            elif eta:
                task_args['eta'] = eta
            
            result = execute_bot_scraping_task.apply_async(
                args=[bot_config_id],
                **task_args
            )
            
            logger.info(f"已发送Bot爬取任务到队列 {queue}，任务ID: {result.id}, Bot ID: {bot_config_id}")
            return result.id
            
        except Exception as e:
            logger.error(f"发送Bot爬取任务失败: {e}")
            raise
    
    @staticmethod
    def send_manual_scraping_task(
        bot_config_id: int,
        session_type: str = "manual",
        queue: str = 'scraping'
    ) -> str:
        """发送手动爬取任务到队列"""
        try:
            result = manual_scraping_task.apply_async(
                args=[bot_config_id, session_type],
                queue=queue
            )
            
            logger.info(f"已发送手动爬取任务到队列 {queue}，任务ID: {result.id}, Bot ID: {bot_config_id}")
            return result.id
            
        except Exception as e:
            logger.error(f"发送手动爬取任务失败: {e}")
            raise
    
    @staticmethod
    def send_batch_scraping_task(
        bot_config_ids: List[int],
        session_type: str = "manual",
        queue: str = 'scraping'
    ) -> str:
        """发送批量爬取任务到队列"""
        try:
            result = batch_scraping_task.apply_async(
                args=[bot_config_ids, session_type],
                queue=queue
            )
            
            logger.info(f"已发送批量爬取任务到队列 {queue}，任务ID: {result.id}, Bot数量: {len(bot_config_ids)}")
            return result.id
            
        except Exception as e:
            logger.error(f"发送批量爬取任务失败: {e}")
            raise
    
    @staticmethod
    def send_cleanup_task(
        days_old: int = 30,
        queue: str = 'cleanup',
        countdown: Optional[int] = None
    ) -> str:
        """发送清理任务到队列"""
        try:
            task_args = {
                'queue': queue,
            }
            
            if countdown:
                task_args['countdown'] = countdown
            
            result = cleanup_old_sessions_task.apply_async(
                args=[days_old],
                **task_args
            )
            
            logger.info(f"已发送清理任务到队列 {queue}，任务ID: {result.id}, 清理天数: {days_old}")
            return result.id
            
        except Exception as e:
            logger.error(f"发送清理任务失败: {e}")
            raise
    
    @staticmethod
    def send_auto_scraping_all_task(
        queue: str = 'scraping',
        countdown: Optional[int] = None
    ) -> str:
        """发送自动爬取所有配置的任务到队列"""
        try:
            task_args = {
                'queue': queue,
            }
            
            if countdown:
                task_args['countdown'] = countdown
            
            result = auto_scraping_all_configs_task.apply_async(**task_args)
            
            logger.info(f"已发送自动爬取所有配置任务到队列 {queue}，任务ID: {result.id}")
            return result.id
            
        except Exception as e:
            logger.error(f"发送自动爬取所有配置任务失败: {e}")
            raise
    
    @staticmethod
    def get_task_status(task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        try:
            result = celery_app.AsyncResult(task_id)
            return {
                "task_id": task_id,
                "status": result.status,
                "result": result.result if result.ready() else None,
                "traceback": result.traceback if result.failed() else None,
                "date_done": result.date_done.isoformat() if result.date_done else None,
                "successful": result.successful(),
                "failed": result.failed(),
                "ready": result.ready(),
            }
        except Exception as e:
            logger.error(f"获取任务状态失败: {e}")
            return {
                "task_id": task_id,
                "status": "UNKNOWN",
                "error": str(e)
            }
    
    @staticmethod
    def revoke_task(task_id: str, terminate: bool = False) -> Dict[str, Any]:
        """撤销任务"""
        try:
            celery_app.control.revoke(task_id, terminate=terminate)
            logger.info(f"已撤销任务 {task_id}，终止进程: {terminate}")
            return {
                "task_id": task_id,
                "revoked": True,
                "terminated": terminate
            }
        except Exception as e:
            logger.error(f"撤销任务失败: {e}")
            return {
                "task_id": task_id,
                "revoked": False,
                "error": str(e)
            }
    
    @staticmethod
    def get_active_tasks() -> List[Dict[str, Any]]:
        """获取活跃任务列表"""
        try:
            inspect = celery_app.control.inspect()
            active = inspect.active()
            
            if not active:
                return []
            
            tasks = []
            for worker, worker_tasks in active.items():
                for task in worker_tasks:
                    tasks.append({
                        "worker": worker,
                        "task_id": task["id"],
                        "name": task["name"],
                        "args": task.get("args", []),
                        "kwargs": task.get("kwargs", {}),
                        "time_start": task.get("time_start"),
                    })
            
            return tasks
            
        except Exception as e:
            logger.error(f"获取活跃任务失败: {e}")
            return []
    
    @staticmethod
    def get_queue_length(queue_name: str) -> int:
        """获取队列长度"""
        try:
            inspect = celery_app.control.inspect()
            queue_info = inspect.reserved()
            
            if not queue_info:
                return 0
            
            total_length = 0
            for worker, tasks in queue_info.items():
                for task in tasks:
                    if task.get("delivery_info", {}).get("routing_key") == queue_name:
                        total_length += 1
            
            return total_length
            
        except Exception as e:
            logger.error(f"获取队列长度失败: {e}")
            return -1