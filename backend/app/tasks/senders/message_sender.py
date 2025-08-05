"""
消息发送服务
用于向Celery队列发送任务消息
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from app.tasks.core import TaskDispatcher

logger = logging.getLogger(__name__)


class MessageSender:
    """消息发送器类，负责向Celery队列发送任务（重构为实例类）"""
    
    def __init__(self, task_dispatcher: Optional[TaskDispatcher] = None):
        self.task_dispatcher = task_dispatcher or TaskDispatcher()
        self._celery_app = None
        self._task_registry = {}
    
    @property
    def celery_app(self):
        """延迟加载Celery应用"""
        if self._celery_app is None:
            from app.celery_app import celery_app
            self._celery_app = celery_app
        return self._celery_app
    
    def send_bot_scraping_task(
        self,
        bot_config_id: int,
        queue: str = 'scraping',
        countdown: Optional[int] = None,
        eta: Optional[datetime] = None
    ) -> str:
        """发送Bot爬取任务到队列（使用TaskDispatcher）"""
        try:
            return self.task_dispatcher.dispatch_bot_scraping(
                bot_config_id,
                queue=queue,
                countdown=countdown,
                eta=eta
            )
        except Exception as e:
            logger.error(f"发送Bot爬取任务失败: {e}")
            raise
    
    def send_manual_scraping_task(
        self,
        bot_config_id: int,
        session_type: str = "manual",
        queue: str = 'scraping'
    ) -> str:
        """发送手动爬取任务到队列（使用TaskDispatcher）"""
        try:
            return self.task_dispatcher.dispatch_manual_scraping(
                bot_config_id,
                session_type,
                queue=queue
            )
        except Exception as e:
            logger.error(f"发送手动爬取任务失败: {e}")
            raise
    
    def send_batch_scraping_task(
        self,
        bot_config_ids: List[int],
        session_type: str = "manual",
        queue: str = 'scraping'
    ) -> str:
        """发送批量爬取任务到队列（使用TaskDispatcher）"""
        try:
            return self.task_dispatcher.dispatch_batch_scraping(
                bot_config_ids,
                session_type,
                queue=queue
            )
        except Exception as e:
            logger.error(f"发送批量爬取任务失败: {e}")
            raise
    
    def send_cleanup_task(
        self,
        days_old: int = 30,
        queue: str = 'cleanup',
        countdown: Optional[int] = None
    ) -> str:
        """发送清理任务到队列（使用TaskDispatcher）"""
        try:
            return self.task_dispatcher.dispatch_cleanup(
                days_old,
                queue=queue,
                countdown=countdown
            )
        except Exception as e:
            logger.error(f"发送清理任务失败: {e}")
            raise
    
    def send_auto_scraping_all_task(
        self,
        queue: str = 'scraping',
        countdown: Optional[int] = None
    ) -> str:
        """发送自动爬取所有配置的任务到队列（使用TaskDispatcher）"""
        try:
            return self.task_dispatcher.dispatch_auto_scraping_all(
                queue=queue,
                countdown=countdown
            )
        except Exception as e:
            logger.error(f"发送自动爬取所有配置任务失败: {e}")
            raise
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        try:
            result = self.celery_app.AsyncResult(task_id)
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
    
    def revoke_task(self, task_id: str, terminate: bool = False) -> Dict[str, Any]:
        """撤销任务"""
        try:
            self.celery_app.control.revoke(task_id, terminate=terminate)
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
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """获取活跃任务列表"""
        try:
            inspect = self.celery_app.control.inspect()
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
    
    def get_queue_length(self, queue_name: str) -> int:
        """获取队列长度"""
        try:
            inspect = self.celery_app.control.inspect()
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