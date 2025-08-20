import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.core.tasks.base import TaskServiceBase
from app.db.base import AsyncSessionLocal
from app.models.task_config import TaskConfig
from app.schemas.task_config_schemas import TaskConfigCreate, TaskConfigUpdate, TaskConfigQuery
from app.crud.task_config import crud_task_config
from app.core.tasks.registry import ConfigStatus, SchedulerType

logger = logging.getLogger(__name__)


class TaskConfigService(TaskServiceBase):
    """任务配置服务"""
    
    def __init__(self):
        super().__init__(service_name="TaskConfigService")
    
    async def create_config(self, **config_data) -> Optional[int]:
        """创建任务配置"""
        async with AsyncSessionLocal() as db:
            try:
                config_obj = TaskConfigCreate(**config_data)
                config = await crud_task_config.create(db, config_obj)
                
                # 如果是调度任务且状态为活跃，通知调度服务
                if (config.scheduler_type != SchedulerType.MANUAL and 
                    config.status == ConfigStatus.ACTIVE):
                    await self._notify_scheduler_service(config, "create")
                
                logger.info(f"已创建任务配置: {config.id} - {config.name}")
                return config.id
                
            except Exception as e:
                logger.error(f"创建任务配置失败: {e}")
                return None
    
    async def update_config(self, config_id: int, update_data: Dict[str, Any]) -> bool:
        """更新任务配置"""
        async with AsyncSessionLocal() as db:
            try:
                config = await crud_task_config.get(db, config_id)
                if not config:
                    return False
                
                update_obj = TaskConfigUpdate(**update_data)
                updated_config = await crud_task_config.update(db, config, update_obj)
                
                # 通知调度服务更新
                if updated_config.scheduler_type != SchedulerType.MANUAL:
                    await self._notify_scheduler_service(updated_config, "update")
                
                logger.info(f"已更新任务配置: {config_id}")
                return True
                
            except Exception as e:
                logger.error(f"更新任务配置失败: {e}")
                return False
    
    async def delete_config(self, config_id: int) -> bool:
        """删除任务配置"""
        async with AsyncSessionLocal() as db:
            try:
                # 通知调度服务移除任务
                await self._notify_scheduler_service_remove(config_id)
                
                success = await crud_task_config.delete(db, config_id)
                
                if success:
                    logger.info(f"已删除任务配置: {config_id}")
                    
                return success
                
            except Exception as e:
                logger.error(f"删除任务配置失败: {e}")
                return False
    
    async def get_config(
        self, 
        config_id: int, 
        verify_scheduler_status: bool = False,
        include_stats: bool = False
    ) -> Optional[Dict[str, Any]]:
        """获取任务配置详情"""
        async with AsyncSessionLocal() as db:
            config = await crud_task_config.get_with_relations(db, config_id)
            if not config:
                return None
            
            result = self._serialize_config(config)
            
            # 验证调度器中的状态
            if verify_scheduler_status:
                scheduled_tasks = await self.redis_services.scheduler.get_all_schedules()
                task_id = f"scheduled_task_{config_id}"
                is_scheduled = any(t.get("task_id") == task_id for t in scheduled_tasks)
                result['scheduler_status'] = "scheduled" if is_scheduled else "not_scheduled"
            
            # 包含执行统计数据
            if include_stats:
                stats = await crud_task_config.get_execution_stats(db, config_id)
                result["stats"] = stats
                
                # 从Redis获取最近的历史记录
                history = await self.redis_services.history.get_history(config_id, limit=10)
                result["recent_history"] = history
            
            return result
    
    async def list_configs(self, query: TaskConfigQuery) -> List[Dict[str, Any]]:
        """列出任务配置"""
        async with AsyncSessionLocal() as db:
            configs, _ = await crud_task_config.get_by_query(db, query)
            return [self._serialize_config(c) for c in configs]
    
    async def get_configs_by_type(self, task_type: str, status: Optional[ConfigStatus] = None) -> List[Dict[str, Any]]:
        """根据类型获取任务配置"""
        async with AsyncSessionLocal() as db:
            configs = await crud_task_config.get_by_type(db, task_type, status)
            return [self._serialize_config(c) for c in configs]
    
    async def get_scheduled_configs(self) -> List[Dict[str, Any]]:
        """获取所有需要调度的任务配置"""
        async with AsyncSessionLocal() as db:
            configs = await crud_task_config.get_scheduled_configs(db)
            return [self._serialize_config(c) for c in configs]
    
    def _serialize_config(self, config: TaskConfig) -> Dict[str, Any]:
        """序列化任务配置"""
        return {
            'id': config.id,
            'name': config.name,
            'description': config.description,
            'task_type': config.task_type if hasattr(config.task_type, 'value') else config.task_type,
            'scheduler_type': config.scheduler_type.value if hasattr(config.scheduler_type, 'value') else config.scheduler_type,
            'status': config.status.value if hasattr(config.status, 'value') else config.status,
            'parameters': config.parameters or {},
            'schedule_config': config.schedule_config or {},
            'priority': config.priority,
            'created_at': config.created_at.isoformat() if config.created_at else None,
            'max_retries': config.max_retries or 0,
            'timeout_seconds': config.timeout_seconds,
            'updated_at': config.updated_at.isoformat() if config.updated_at else None,
        }
    
    async def _notify_scheduler_service(self, config: TaskConfig, action: str):
        """通知调度服务"""
        await self.redis_services.scheduler.register_task(config)
        
        await self.redis_services.history.add_history_event(
            config_id=config.id,
            event_data={
                "event": f"task_{action}d",
                "job_id": f"scheduled_task_{config.id}",
                "job_name": config.name,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    async def _notify_scheduler_service_remove(self, config_id: int):
        """通知调度服务移除任务"""
        await self.redis_services.scheduler.unregister_task(config_id)