"""
任务管理服务
统一管理任务的创建、调度、执行和监控
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.broker import broker
from app.scheduler import scheduler, load_schedules_from_db, register_scheduled_task, initialize_scheduler
from app.db.base import AsyncSessionLocal
from app.models.task_config import TaskConfig
from app.schemas.task_config_schemas import TaskConfigCreate, TaskConfigUpdate
from app.crud.task_config import crud_task_config
from app.crud.task_execution import crud_task_execution
from app.core.task_registry import TaskType, ConfigStatus, SchedulerType

logger = logging.getLogger(__name__)


class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self.broker = broker
        self.scheduler = scheduler
        self._initialized = False
    
    async def initialize(self):
        """初始化任务管理器"""
        if self._initialized:
            return
        
        # 初始化调度器
        await initialize_scheduler()
        
        # 加载数据库中的调度任务
        await load_schedules_from_db()
        self._initialized = True
        logger.info("任务管理器初始化完成")
    
    async def create_task_config(
        self,
        config_data: TaskConfigCreate
    ) -> int:
        """创建任务配置"""
        async with AsyncSessionLocal() as db:
            config = await crud_task_config.create(db, config_data)
            
            # 如果是调度任务，注册到调度器
            if config.scheduler_type != SchedulerType.MANUAL:
                await register_scheduled_task(config)
            
            logger.info(f"已创建任务配置: {config.id} - {config.name}")
            return config.id
    
    async def update_task_config(
        self,
        config_id: int,
        update_data: TaskConfigUpdate
    ) -> bool:
        """更新任务配置"""
        async with AsyncSessionLocal() as db:
            config = await crud_task_config.get(db, config_id)
            if not config:
                return False
            
            updated_config = await crud_task_config.update(db, config, update_data)
            
            # 重新注册调度任务
            if updated_config.scheduler_type != SchedulerType.MANUAL:
                await self._unregister_scheduled_task(config_id)
                await register_scheduled_task(updated_config)
            
            logger.info(f"已更新任务配置: {config_id}")
            return True
    
    async def delete_task_config(self, config_id: int) -> bool:
        """删除任务配置"""
        async with AsyncSessionLocal() as db:
            # 取消调度
            await self._unregister_scheduled_task(config_id)
            
            success = await crud_task_config.delete(db, config_id)
            if success:
                logger.info(f"已删除任务配置: {config_id}")
            return success
    
    async def get_task_config(self, config_id: int) -> Optional[Dict[str, Any]]:
        """获取任务配置详情"""
        async with AsyncSessionLocal() as db:
            config = await crud_task_config.get(db, config_id)
            if not config:
                return None
            
            return {
                'id': config.id,
                'name': config.name,
                'description': config.description,
                'task_type': config.task_type.value if hasattr(config.task_type, 'value') else config.task_type,
                'scheduler_type': config.scheduler_type.value if hasattr(config.scheduler_type, 'value') else config.scheduler_type,
                'status': config.status.value if hasattr(config.status, 'value') else config.status,
                'parameters': config.parameters or {},
                'schedule_config': config.schedule_config or {},
                'max_retries': config.max_retries or 0,
                'timeout_seconds': config.timeout_seconds,
                'created_at': config.created_at.isoformat() if config.created_at else None,
                'updated_at': config.updated_at.isoformat() if config.updated_at else None
            }
    
    async def list_task_configs(
        self,
        task_type: str = None,
        status: str = None
    ) -> List[Dict[str, Any]]:
        """列出任务配置"""
        async with AsyncSessionLocal() as db:
            if task_type or status:
                # 使用CRUD的查询方法
                from app.schemas.task_config_schemas import TaskConfigQuery
                query = TaskConfigQuery(
                    task_type=TaskType(task_type) if task_type else None,
                    status=ConfigStatus(status) if status else None,
                    page=1,
                    page_size=1000  # 获取所有结果
                )
                configs, _ = await crud_task_config.get_by_query(db, query)
            else:
                configs = await crud_task_config.get_multi(db, skip=0, limit=1000)
            
            return [
                {
                    'id': c.id,
                    'name': c.name,
                    'description': c.description,
                    'task_type': c.task_type.value if hasattr(c.task_type, 'value') else c.task_type,
                    'scheduler_type': c.scheduler_type.value if hasattr(c.scheduler_type, 'value') else c.scheduler_type,
                    'status': c.status.value if hasattr(c.status, 'value') else c.status,
                    'parameters': c.parameters or {},
                    'schedule_config': c.schedule_config or {},
                    'max_retries': c.max_retries or 0,
                    'timeout_seconds': c.timeout_seconds,
                    'created_at': c.created_at.isoformat() if c.created_at else None,
                    'updated_at': c.updated_at.isoformat() if c.updated_at else None
                }
                for c in configs
            ]
    
    async def execute_task_immediately(
        self,
        config_id: int,
        **kwargs
    ) -> str:
        """立即执行任务"""
        async with AsyncSessionLocal() as db:
            config = await crud_task_config.get(db, config_id)
            if not config:
                raise ValueError(f"任务配置不存在: {config_id}")
            
            # 获取任务函数
            task_func = self._get_task_function(config.task_type)
            if not task_func:
                raise ValueError(f"不支持的任务类型: {config.task_type}")
            
            # 发送任务到队列
            task = await task_func.kiq(
                config_id,
                **config.parameters,
                **kwargs
            )
            
            logger.info(f"已立即执行任务 {config_id}，任务ID: {task.task_id}")
            return task.task_id
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        try:
            # 从Redis结果后端获取任务状态
            result = await self.broker.result_backend.get_result(task_id)
            
            if result:
                return {
                    "task_id": task_id,
                    "status": result.status.name.lower() if result.status else "unknown",
                    "result": result.result,
                    "error": result.error,
                    "started_at": result.started_at.isoformat() if hasattr(result, 'started_at') and result.started_at else None,
                    "completed_at": result.completed_at.isoformat() if hasattr(result, 'completed_at') and result.completed_at else None,
                }
            else:
                # 如果Redis中没有结果，尝试从数据库查询
                async with AsyncSessionLocal() as db:
                    execution = await crud_task_execution.get_latest_by_task_id(db, task_id)
                    
                    if execution:
                        return {
                            "task_id": task_id,
                            "status": execution.status.value if hasattr(execution.status, 'value') else execution.status,
                            "result": execution.result,
                            "error": execution.error_message,
                            "started_at": execution.started_at.isoformat() if execution.started_at else None,
                            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                        }
                    else:
                        return {
                            "task_id": task_id,
                            "status": "unknown",
                            "result": None,
                            "error": None,
                        }
        except Exception as e:
            logger.error(f"获取任务状态失败 {task_id}: {e}")
            return {
                "task_id": task_id,
                "status": "error",
                "result": None,
                "error": str(e),
            }
    
    async def list_active_tasks(self) -> List[Dict[str, Any]]:
        """列出活跃的任务执行记录"""
        async with AsyncSessionLocal() as db:
            executions = await crud_task_execution.get_running_executions(db)
            
            return [
                {
                    "task_id": e.task_id,
                    "config_id": e.config_id,
                    "status": e.status.value if hasattr(e.status, 'value') else e.status,
                    "started_at": e.started_at.isoformat() if e.started_at else None,
                }
                for e in executions
            ]
    
    async def _unregister_scheduled_task(self, config_id: int):
        """取消调度任务"""
        # 从调度器中移除任务
        task_name = f"task_{config_id}"
        try:
            await self.scheduler.delete_schedule(task_name)
        except Exception as e:
            logger.warning(f"取消调度任务失败 {config_id}: {e}")
    
    def _get_task_function(self, task_type: TaskType):
        """根据任务类型获取任务函数"""
        from app.tasks import cleanup_tasks, notification_tasks, data_tasks
        
        task_mapping = {
            TaskType.CLEANUP_TOKENS: cleanup_tasks.cleanup_expired_tokens,
            TaskType.CLEANUP_CONTENT: cleanup_tasks.cleanup_old_content,
            TaskType.CLEANUP_EVENTS: cleanup_tasks.cleanup_schedule_events,
            TaskType.SEND_EMAIL: notification_tasks.send_email,
            TaskType.DATA_EXPORT: data_tasks.export_data,
            TaskType.DATA_BACKUP: data_tasks.backup_data,
            # 添加其他任务映射
        }
        return task_mapping.get(task_type)
    
    async def _check_broker_connection(self) -> bool:
        """检查broker连接状态"""
        try:
            # 尝试ping broker的连接
            if hasattr(self.broker, 'is_started'):
                return self.broker.is_started
            # 备用方法：尝试获取broker状态
            await self.broker.result_backend.is_result_ready("test")
            return True
        except Exception as e:
            logger.warning(f"Broker连接检查失败: {e}")
            return False

    async def _get_scheduled_jobs_count(self) -> int:
        """获取已调度的任务数量"""
        try:
            async with AsyncSessionLocal() as db:
                # 获取所有需要调度的活跃任务配置数量
                scheduled_configs = await crud_task_config.get_scheduled_configs(db)
                return len(scheduled_configs)
        except Exception as e:
            logger.warning(f"获取调度任务数量失败: {e}")
            return 0

    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            # 检查broker连接状态
            broker_connected = await self._check_broker_connection()
            
            # 获取调度任务数量
            scheduled_count = await self._get_scheduled_jobs_count()
            
            # 获取活跃任务数量
            active_tasks = await self.list_active_tasks()
            
            # 获取任务配置统计
            async with AsyncSessionLocal() as db:
                total_configs = await crud_task_config.get_total_count(db)
                active_configs = await crud_task_config.get_active_count(db)
            
            return {
                "broker_connected": broker_connected,
                "scheduler_running": self._initialized,
                "total_configs": total_configs,
                "active_configs": active_configs,
                "scheduled_jobs": scheduled_count,
                "active_tasks": len(active_tasks),
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {
                "broker_connected": False,
                "scheduler_running": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }


# 全局任务管理器实例
task_manager = TaskManager()