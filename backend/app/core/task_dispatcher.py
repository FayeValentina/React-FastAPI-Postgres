"""
纯任务分发器 - 从task_config表读取配置并分发到Celery
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from app.db.base import AsyncSessionLocal
from app.core.task_mapping import (
    get_celery_task_name, 
    register_task_type as register_mapping, 
    is_task_type_supported
)

logger = logging.getLogger(__name__)


class TaskDispatcher:
    """纯任务分发器 - 从数据库获取配置并分发任务"""
    
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
    
    async def dispatch_by_config_id(
        self,
        task_config_id: int,
        **options
    ) -> str:
        """
        根据任务配置ID分发任务
        
        Args:
            task_config_id: 任务配置ID
            **options: 分发选项(countdown, eta等)
            
        Returns:
            task_id: Celery任务ID
        """
        async with AsyncSessionLocal() as db:
            from app.crud.task_config import crud_task_config
            
            # 获取任务配置
            config = await crud_task_config.get(db, id=task_config_id)
            if not config:
                raise ValueError(f"任务配置不存在: {task_config_id}")
            
            # 获取对应的Celery任务名称
            celery_task = get_celery_task_name(config.task_type)
            
            # 准备参数
            args = [task_config_id]  # 总是传递配置ID作为第一个参数
            kwargs = config.task_params or {}
            
            # 使用配置中的队列或默认队列
            queue = config.task_params.get('queue', 'default') if config.task_params else 'default'
            
            return self.dispatch_task(
                task_name=celery_task,
                args=args,
                kwargs=kwargs,
                queue=queue,
                **options
            )
    
    
    async def dispatch_by_task_type(
        self,
        task_type: str,
        task_params: Dict = None,
        queue: str = 'default',
        **options
    ) -> str:
        """
        根据任务类型直接分发（不使用数据库配置）
        
        Args:
            task_type: 任务类型
            task_params: 任务参数
            queue: 队列名称
            **options: 分发选项
            
        Returns:
            task_id: Celery任务ID
        """
        celery_task = get_celery_task_name(task_type)
        
        return self.dispatch_task(
            task_name=celery_task,
            args=[],
            kwargs=task_params or {},
            queue=queue,
            **options
        )
    
    # === 批量操作方法 ===
    
    async def dispatch_multiple_configs(
        self, 
        task_config_ids: List[int],
        **options
    ) -> List[str]:
        """
        批量分发多个任务配置
        
        Args:
            task_config_ids: 任务配置ID列表
            **options: 分发选项
            
        Returns:
            List[str]: Celery任务ID列表
        """
        task_ids = []
        for config_id in task_config_ids:
            try:
                task_id = await self.dispatch_by_config_id(config_id, **options)
                task_ids.append(task_id)
            except Exception as e:
                logger.error(f"分发任务配置 {config_id} 失败: {e}")
                # 继续处理其他任务
        
        return task_ids
    
    async def dispatch_by_task_type_batch(
        self,
        task_type: str,
        **options
    ) -> List[str]:
        """
        批量分发指定类型的所有活跃任务配置
        
        Args:
            task_type: 任务类型
            **options: 分发选项
            
        Returns:
            List[str]: Celery任务ID列表
        """
        async with AsyncSessionLocal() as db:
            from app.crud.task_config import crud_task_config
            from app.core.task_type import TaskType
            
            # 获取指定类型的所有活跃配置
            configs = await crud_task_config.get_by_type_and_status(
                db,
                task_type=TaskType(task_type),
                status=None  # 获取活跃配置
            )
            
            config_ids = [config.id for config in configs]
            return await self.dispatch_multiple_configs(config_ids, **options)
    
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
    
    # === 任务类型管理 ===
    
    def register_task_type(
        self,
        task_type: str,
        celery_task: str
    ):
        """注册新的任务类型映射"""
        register_mapping(task_type, celery_task)
        logger.info(f"已注册任务类型映射: {task_type} -> {celery_task}")
    
    def get_supported_task_types(self) -> Dict[str, str]:
        """获取支持的任务类型映射"""
        from app.core.task_mapping import get_all_task_types
        return get_all_task_types()
    
    def is_task_type_supported(self, task_type: str) -> bool:
        """检查是否支持指定的任务类型"""
        return is_task_type_supported(task_type)


# 全局任务分发器实例
task_dispatcher = TaskDispatcher()