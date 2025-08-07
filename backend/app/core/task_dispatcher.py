"""
纯任务分发器 - 只负责注册任务和分发到Celery
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskDispatcher:
    """纯任务分发器 - 负责任务注册、分发和管理"""
    
    # 任务注册表 - 统一管理所有任务配置
    TASK_REGISTRY = {
        # 爬取任务
        'bot_scraping': {
            'celery_task': 'execute_bot_scraping_task',
            'queue': 'scraping',
            'default_args': []
        },
        'manual_scraping': {
            'celery_task': 'manual_scraping_task', 
            'queue': 'scraping',
            'default_args': []
        },
        'batch_scraping': {
            'celery_task': 'batch_scraping_task',
            'queue': 'scraping', 
            'default_args': []
        },
        'auto_scraping_all': {
            'celery_task': 'auto_scraping_all_configs_task',
            'queue': 'scraping',
            'default_args': []
        },
        
        # 清理任务
        'cleanup_sessions': {
            'celery_task': 'cleanup_old_sessions_task',
            'queue': 'cleanup',
            'default_args': [30]
        },
        'cleanup_tokens': {
            'celery_task': 'cleanup_expired_tokens_task',
            'queue': 'cleanup',
            'default_args': []
        },
        'cleanup_content': {
            'celery_task': 'cleanup_old_content_task', 
            'queue': 'cleanup',
            'default_args': [90]
        },
        'cleanup_events': {
            'celery_task': 'cleanup_schedule_events_task',
            'queue': 'cleanup', 
            'default_args': [30]
        },
    }
    
    def __init__(self):
        self._celery_app = None
    
    @property
    def celery_app(self):
        """延迟加载Celery应用"""
        if self._celery_app is None:
            from app.celery_app import celery_app
            self._celery_app = celery_app
        return self._celery_app
    
    # === 核心分发方法 ===
    
    def dispatch_task(
        self, 
        task_name: str, 
        args: List = None, 
        kwargs: Dict = None, 
        queue: str = 'default',
        countdown: Optional[int] = None,
        eta: Optional[datetime] = None
    ) -> str:
        """
        发送任务到Celery队列
        
        Args:
            task_name: Celery任务名称
            args: 任务参数列表
            kwargs: 任务关键字参数
            queue: 队列名称
            countdown: 延迟秒数
            eta: 指定执行时间
            
        Returns:
            task_id: Celery任务ID
        """
        try:
            task_args = {'queue': queue}
            
            if countdown is not None:
                task_args['countdown'] = countdown
            elif eta is not None:
                task_args['eta'] = eta
            
            result = self.celery_app.send_task(
                task_name,
                args=args or [],
                kwargs=kwargs or {},
                **task_args
            )
            
            task_id = result.id
            logger.info(f"已发送任务 {task_name} 到队列 {queue}，任务ID: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"任务分发失败 {task_name}: {e}")
            raise
    
    def dispatch_registered_task(
        self,
        task_type: str,
        args: List = None,
        kwargs: Dict = None,
        **options
    ) -> str:
        """
        发送已注册的任务类型
        
        Args:
            task_type: 注册的任务类型键
            args: 任务参数
            kwargs: 任务关键字参数
            **options: 分发选项(queue, countdown, eta等)
            
        Returns:
            task_id: Celery任务ID
        """
        if task_type not in self.TASK_REGISTRY:
            raise ValueError(f"未注册的任务类型: {task_type}")
        
        task_config = self.TASK_REGISTRY[task_type]
        
        # 使用提供的参数或默认参数
        final_args = args if args is not None else task_config['default_args']
        final_queue = options.pop('queue', task_config['queue'])
        
        return self.dispatch_task(
            task_name=task_config['celery_task'],
            args=final_args,
            kwargs=kwargs,
            queue=final_queue,
            **options
        )
    
    # === 便捷方法 ===
    
    def dispatch_bot_scraping(self, bot_config_id: int, **options) -> str:
        """发送Bot爬取任务"""
        return self.dispatch_registered_task(
            'bot_scraping', args=[bot_config_id], **options
        )
    
    def dispatch_manual_scraping(
        self, bot_config_id: int, session_type: str = "manual", **options
    ) -> str:
        """发送手动爬取任务"""
        return self.dispatch_registered_task(
            'manual_scraping', args=[bot_config_id, session_type], **options
        )
    
    def dispatch_batch_scraping(
        self, bot_config_ids: List[int], session_type: str = "manual", **options
    ) -> str:
        """发送批量爬取任务"""
        return self.dispatch_registered_task(
            'batch_scraping', args=[bot_config_ids, session_type], **options
        )
    
    def dispatch_cleanup_sessions(self, days_old: int = 30, **options) -> str:
        """发送清理会话任务"""
        return self.dispatch_registered_task(
            'cleanup_sessions', args=[days_old], **options
        )
    
    def dispatch_cleanup_tokens(self, **options) -> str:
        """发送清理令牌任务"""
        return self.dispatch_registered_task('cleanup_tokens', **options)
    
    def dispatch_cleanup_content(self, days_old: int = 90, **options) -> str:
        """发送清理内容任务"""
        return self.dispatch_registered_task(
            'cleanup_content', args=[days_old], **options
        )
    
    def dispatch_cleanup_events(self, days_old: int = 30, **options) -> str:
        """发送清理事件任务"""
        return self.dispatch_registered_task(
            'cleanup_events', args=[days_old], **options
        )
    
    def dispatch_auto_scraping_all(self, **options) -> str:
        """发送自动爬取所有配置任务"""
        return self.dispatch_registered_task('auto_scraping_all', **options)
    
    # === 任务管理方法 ===
    
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
            return {"task_id": task_id, "status": "UNKNOWN", "error": str(e)}
    
    def revoke_task(self, task_id: str, terminate: bool = False) -> Dict[str, Any]:
        """撤销任务"""
        try:
            self.celery_app.control.revoke(task_id, terminate=terminate)
            logger.info(f"已撤销任务 {task_id}，终止进程: {terminate}")
            return {"task_id": task_id, "revoked": True, "terminated": terminate}
        except Exception as e:
            logger.error(f"撤销任务失败: {e}")
            return {"task_id": task_id, "revoked": False, "error": str(e)}
    
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
    
    # === 注册表管理 ===
    
    @classmethod
    def register_task(
        cls,
        task_type: str,
        celery_task: str, 
        queue: str = 'default',
        default_args: List = None
    ):
        """注册新的任务类型"""
        cls.TASK_REGISTRY[task_type] = {
            'celery_task': celery_task,
            'queue': queue,
            'default_args': default_args or []
        }
        logger.info(f"已注册任务类型: {task_type} -> {celery_task}")
    
    @classmethod
    def get_task_registry(cls) -> Dict[str, Dict[str, Any]]:
        """获取任务注册表"""
        return cls.TASK_REGISTRY.copy()


# 全局任务分发器实例
task_dispatcher = TaskDispatcher()