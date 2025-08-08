"""
纯配置管理器 - 使用数据库管理任务配置信息
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.db.base import AsyncSessionLocal

logger = logging.getLogger(__name__)


class JobConfigManager:
    """纯配置管理器 - 使用数据库存储和管理任务配置"""
    
    def __init__(self):
        pass  # 不再使用内存存储
    
    async def create_config(
        self, 
        name: str,
        task_type: str,
        description: str = None,
        parameters: Dict[str, Any] = None,
        schedule_config: Dict[str, Any] = None,
        **kwargs
    ) -> Optional[int]:
        """
        创建新的任务配置
        
        Args:
            name: 任务名称
            task_type: 任务类型
            description: 任务描述
            task_params: 任务参数
            schedule_config: 调度配置
            **kwargs: 其他配置参数
            
        Returns:
            Optional[int]: 创建的配置ID，失败时返回None
        """
        try:
            async with AsyncSessionLocal() as db:
                from app.crud.task_config import crud_task_config
                from app.schemas.task_config import TaskConfigCreate
                from app.core.task_type import TaskType
                
                config_data = TaskConfigCreate(
                    name=name,
                    task_type=TaskType(task_type),
                    description=description,
                    parameters=parameters or {},
                    schedule_config=schedule_config,
                    **kwargs
                )
                
                config = await crud_task_config.create(db, obj_in=config_data)
                logger.info(f"已创建任务配置: {config.id} - {name}")
                return config.id
                
        except Exception as e:
            logger.error(f"创建任务配置失败 {name}: {e}")
            return None
    
    async def get_config(self, config_id: int) -> Optional[Dict[str, Any]]:
        """
        获取任务配置
        
        Args:
            config_id: 配置ID
            
        Returns:
            Optional[Dict]: 配置信息，不存在时返回None
        """
        try:
            async with AsyncSessionLocal() as db:
                from app.crud.task_config import crud_task_config
                
                config = await crud_task_config.get(db, id=config_id)
                if not config:
                    return None
                
                return {
                    'id': config.id,
                    'name': config.name,
                    'task_type': config.task_type.value,
                    'description': config.description,
                    'status': config.status.value,
                    'parameters': config.parameters,
                    'schedule_config': config.schedule_config,
                    'max_instances': config.max_instances,
                    'timeout_seconds': config.timeout_seconds,
                    'max_retries': config.max_retries,
                    'priority': config.priority,
                    'created_at': config.created_at.isoformat() if config.created_at else None,
                    'updated_at': config.updated_at.isoformat() if config.updated_at else None
                }
                
        except Exception as e:
            logger.error(f"获取任务配置失败 {config_id}: {e}")
            return None
    
    async def update_config(self, config_id: int, updates: Dict[str, Any]) -> bool:
        """
        更新任务配置
        
        Args:
            config_id: 配置ID
            updates: 要更新的配置项
            
        Returns:
            bool: 更新是否成功
        """
        try:
            async with AsyncSessionLocal() as db:
                from app.crud.task_config import crud_task_config
                from app.schemas.task_config import TaskConfigUpdate
                
                # 检查配置是否存在
                config = await crud_task_config.get(db, id=config_id)
                if not config:
                    logger.warning(f"尝试更新不存在的任务配置: {config_id}")
                    return False
                
                # 创建更新数据
                update_data = TaskConfigUpdate(**updates)
                
                # 执行更新
                await crud_task_config.update(db, db_obj=config, obj_in=update_data)
                logger.debug(f"已更新任务配置: {config_id}")
                return True
            
        except Exception as e:
            logger.error(f"更新任务配置失败 {config_id}: {e}")
            return False
    
    async def remove_config(self, config_id: int) -> bool:
        """
        移除任务配置
        
        Args:
            config_id: 配置ID
            
        Returns:
            bool: 移除是否成功
        """
        try:
            async with AsyncSessionLocal() as db:
                from app.crud.task_config import crud_task_config
                
                # 检查配置是否存在
                config = await crud_task_config.get(db, id=config_id)
                if not config:
                    logger.warning(f"尝试移除不存在的任务配置: {config_id}")
                    return False
                
                # 删除配置
                await crud_task_config.remove(db, id=config_id)
                logger.debug(f"已移除任务配置: {config_id}")
                return True
            
        except Exception as e:
            logger.error(f"移除任务配置失败 {config_id}: {e}")
            return False
    
    async def get_all_configs(self) -> List[Dict[str, Any]]:
        """获取所有任务配置"""
        try:
            async with AsyncSessionLocal() as db:
                from app.crud.task_config import crud_task_config
                
                configs = await crud_task_config.get_multi(db)
                
                result = []
                for config in configs:
                    result.append({
                        'id': config.id,
                        'name': config.name,
                        'task_type': config.task_type.value,
                        'description': config.description,
                        'status': config.status.value,
                        'parameters': config.parameters,
                        'schedule_config': config.schedule_config,
                        'max_instances': config.max_instances,
                        'timeout_seconds': config.timeout_seconds,
                        'max_retries': config.max_retries,
                        'priority': config.priority,
                        'created_at': config.created_at.isoformat() if config.created_at else None,
                        'updated_at': config.updated_at.isoformat() if config.updated_at else None
                    })
                
                return result
                
        except Exception as e:
            logger.error(f"获取所有任务配置失败: {e}")
            return []
    
    async def get_configs_by_type(self, task_type: str) -> List[Dict[str, Any]]:
        """
        根据类型获取任务配置
        
        Args:
            task_type: 任务类型
            
        Returns:
            List[Dict]: 匹配类型的配置列表
        """
        try:
            async with AsyncSessionLocal() as db:
                from app.crud.task_config import crud_task_config
                from app.core.task_type import TaskType
                
                configs = await crud_task_config.get_by_type_and_status(
                    db,
                    task_type=TaskType(task_type)
                )
                
                result = []
                for config in configs:
                    result.append({
                        'id': config.id,
                        'name': config.name,
                        'task_type': config.task_type.value,
                        'description': config.description,
                        'status': config.status.value,
                        'parameters': config.parameters,
                        'schedule_config': config.schedule_config,
                        'max_instances': config.max_instances,
                        'timeout_seconds': config.timeout_seconds,
                        'max_retries': config.max_retries,
                        'priority': config.priority
                    })
                
                return result
                
        except Exception as e:
            logger.error(f"按类型获取任务配置失败 {task_type}: {e}")
            return []
    
    async def get_active_configs(self) -> List[Dict[str, Any]]:
        """获取所有活跃的任务配置"""
        try:
            async with AsyncSessionLocal() as db:
                from app.crud.task_config import crud_task_config
                
                configs = await crud_task_config.get_active_configs(db)
                
                result = []
                for config in configs:
                    result.append({
                        'id': config.id,
                        'name': config.name,
                        'task_type': config.task_type.value,
                        'description': config.description,
                        'status': config.status.value,
                        'parameters': config.parameters,
                        'schedule_config': config.schedule_config,
                        'max_instances': config.max_instances,
                        'timeout_seconds': config.timeout_seconds,
                        'max_retries': config.max_retries,
                        'priority': config.priority
                    })
                
                return result
                
        except Exception as e:
            logger.error(f"获取活跃任务配置失败: {e}")
            return []
    
    async def has_config(self, config_id: int) -> bool:
        """检查是否存在指定配置"""
        try:
            async with AsyncSessionLocal() as db:
                from app.crud.task_config import crud_task_config
                
                config = await crud_task_config.get(db, id=config_id)
                return config is not None
                
        except Exception as e:
            logger.error(f"检查任务配置失败 {config_id}: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取配置统计信息"""
        try:
            async with AsyncSessionLocal() as db:
                from app.crud.task_config import crud_task_config
                
                stats = await crud_task_config.get_stats(db)
                return stats
                
        except Exception as e:
            logger.error(f"获取配置统计失败: {e}")
            return {'total_configs': 0, 'config_types': {}, 'status_distribution': {}}


# 全局配置管理器实例
job_config_manager = JobConfigManager()