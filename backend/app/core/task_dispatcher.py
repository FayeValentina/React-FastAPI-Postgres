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
        eta: Optional[datetime] = None,
        time_limit: Optional[int] = None,
        max_retries: Optional[int] = None
    ) -> str:
        """
        发送任务到Celery队列
        """
        try:
            task_args = {'queue': queue}

            if countdown is not None:
                task_args['countdown'] = countdown
            elif eta is not None:
                task_args['eta'] = eta

            if time_limit is not None:
                task_args['time_limit'] = time_limit

            if max_retries is not None:
                task_args['retries'] = max_retries

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
        """
        async with AsyncSessionLocal() as db:
            from app.crud.task_config import crud_task_config

            config = await crud_task_config.get(db, id=task_config_id)
            if not config:
                raise ValueError(f"任务配置不存在: {task_config_id}")

            celery_task = get_celery_task_name(config.task_type)

            args = [task_config_id]
            kwargs = config.parameters or {}

            queue = config.parameters.get('queue', 'default') if config.parameters else 'default'

            return self.dispatch_task(
                task_name=celery_task,
                args=args,
                kwargs=kwargs,
                queue=queue,
                time_limit=config.timeout_seconds,
                max_retries=config.max_retries,
                **options
            )


    async def dispatch_by_task_type(
        self,
        task_type: str,
        parameters: Dict = None,
        queue: str = 'default',
        **options
    ) -> str:
        """
        根据任务类型直接分发（不使用数据库配置）
        """
        celery_task = get_celery_task_name(task_type)

        return self.dispatch_task(
            task_name=celery_task,
            args=[],
            kwargs=parameters or {},
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
        """
        task_ids = []
        for config_id in task_config_ids:
            try:
                task_id = await self.dispatch_by_config_id(config_id, **options)
                task_ids.append(task_id)
            except Exception as e:
                logger.error(f"分发任务配置 {config_id} 失败: {e}")

        return task_ids

    async def dispatch_by_task_type_batch(
        self,
        task_type: str,
        **options
    ) -> List[str]:
        """
        批量分发指定类型的所有活跃任务配置
        """
        async with AsyncSessionLocal() as db:
            from app.crud.task_config import crud_task_config
            from app.core.task_type import TaskType, TaskStatus

            configs = await crud_task_config.get_by_type(
                db,
                task_type=TaskType(task_type),
                status=TaskStatus.ACTIVE
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
