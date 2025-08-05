"""
任务分发器 - 统一的Celery任务分发组件
替代hybrid_scheduler中的独立发送函数，消除重复代码
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskDispatcher:
    """统一的任务分发器，处理所有Celery任务发送逻辑"""
    
    # 任务注册表 - 统一管理任务配置
    TASK_REGISTRY = {
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
        'cleanup': {
            'celery_task': 'cleanup_old_sessions_task',
            'queue': 'cleanup',
            'default_args': [30]  # 默认清理30天前的数据
        },
        'auto_scraping_all': {
            'celery_task': 'auto_scraping_all_configs_task',
            'queue': 'scraping',
            'default_args': []
        }
    }
    
    @staticmethod
    def dispatch_to_celery(
        task_name: str, 
        args: List = None, 
        kwargs: Dict = None, 
        queue: str = 'default',
        countdown: Optional[int] = None,
        eta: Optional[datetime] = None
    ) -> str:
        """
        统一的Celery任务分发方法
        
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
            from app.celery_app import celery_app
            
            task_args = {
                'queue': queue,
            }
            
            if countdown is not None:
                task_args['countdown'] = countdown
            elif eta is not None:
                task_args['eta'] = eta
            
            result = celery_app.send_task(
                task_name,
                args=args or [],
                kwargs=kwargs or {},
                **task_args
            )
            
            task_id = result.id
            logger.info(f"任务分发器已发送任务 {task_name} 到队列 {queue}，任务ID: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"任务分发失败 {task_name}: {e}")
            raise
    
    @classmethod
    def dispatch_registered_task(
        cls,
        task_type: str,
        args: List = None,
        kwargs: Dict = None,
        **dispatch_options
    ) -> str:
        """
        发送已注册的任务类型
        
        Args:
            task_type: 注册的任务类型键
            args: 任务参数
            kwargs: 任务关键字参数
            **dispatch_options: 分发选项(countdown, eta等)
            
        Returns:
            task_id: Celery任务ID
        """
        if task_type not in cls.TASK_REGISTRY:
            raise ValueError(f"未注册的任务类型: {task_type}")
        
        task_config = cls.TASK_REGISTRY[task_type]
        
        # 使用默认参数如果没有提供
        final_args = args if args is not None else task_config['default_args']
        final_queue = dispatch_options.pop('queue', task_config['queue'])
        
        return cls.dispatch_to_celery(
            task_name=task_config['celery_task'],
            args=final_args,
            kwargs=kwargs,
            queue=final_queue,
            **dispatch_options
        )
    
    @classmethod
    def dispatch_bot_scraping(cls, bot_config_id: int, **options) -> str:
        """发送Bot爬取任务"""
        return cls.dispatch_registered_task(
            'bot_scraping',
            args=[bot_config_id],
            **options
        )
    
    @classmethod
    def dispatch_manual_scraping(
        cls, 
        bot_config_id: int, 
        session_type: str = "manual", 
        **options
    ) -> str:
        """发送手动爬取任务"""
        return cls.dispatch_registered_task(
            'manual_scraping',
            args=[bot_config_id, session_type],
            **options
        )
    
    @classmethod
    def dispatch_batch_scraping(
        cls,
        bot_config_ids: List[int],
        session_type: str = "manual",
        **options
    ) -> str:
        """发送批量爬取任务"""
        return cls.dispatch_registered_task(
            'batch_scraping', 
            args=[bot_config_ids, session_type],
            **options
        )
    
    @classmethod
    def dispatch_cleanup(cls, days_old: int = 30, **options) -> str:
        """发送清理任务"""
        return cls.dispatch_registered_task(
            'cleanup',
            args=[days_old],
            **options
        )
    
    @classmethod
    def dispatch_auto_scraping_all(cls, **options) -> str:
        """发送自动爬取所有配置任务"""
        return cls.dispatch_registered_task(
            'auto_scraping_all',
            **options
        )
    
    @staticmethod
    def get_task_registry() -> Dict[str, Dict[str, Any]]:
        """获取任务注册表"""
        return TaskDispatcher.TASK_REGISTRY.copy()
    
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