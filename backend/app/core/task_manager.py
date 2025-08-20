"""
任务管理器
统一管理所有任务服务的入口
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.broker import broker
from app.implementation.tasks.config import TaskConfigService
from app.implementation.tasks.execution import TaskExecutionService
from app.implementation.tasks.scheduler import TaskSchedulerService
from app.implementation.tasks.monitor import TaskMonitorService
from app.schemas.task_config_schemas import TaskConfigQuery
from app.models.task_execution import TaskExecution
from app.db.base import AsyncSessionLocal

logger = logging.getLogger(__name__)


class TaskManager:
    """统一的任务管理器"""
    
    def __init__(self):
        self.broker = broker
        self._initialized = False
        
        # 初始化各个服务
        self.config_service = TaskConfigService()
        self.execution_service = TaskExecutionService()
        self.scheduler_service = TaskSchedulerService()
        self.monitor_service = TaskMonitorService()
    
    async def initialize(self):
        """初始化任务管理器"""
        if self._initialized:
            return
        
        try:
            # 初始化各个服务
            await self.config_service.initialize()
            await self.execution_service.initialize()
            await self.scheduler_service.initialize()
            await self.monitor_service.initialize()
            
            self._initialized = True
            logger.info("任务管理器初始化完成")
            
        except Exception as e:
            logger.error(f"任务管理器初始化失败: {e}")
            raise
    
    async def shutdown(self):
        """关闭任务管理器"""
        try:
            # 关闭各个服务
            await self.config_service.shutdown()
            await self.execution_service.shutdown()
            await self.scheduler_service.shutdown()
            await self.monitor_service.shutdown()
            
            self._initialized = False
            logger.info("任务管理器已关闭")
        except Exception as e:
            logger.error(f"任务管理器关闭失败: {e}")
    
    # ========== 配置管理委托方法 ==========
    
    async def create_task_config(self, **config_data) -> Optional[int]:
        """创建任务配置"""
        return await self.config_service.create_config(**config_data)
    
    async def update_task_config(self, config_id: int, update_data: Dict[str, Any]) -> bool:
        """更新任务配置"""
        return await self.config_service.update_config(config_id, update_data)
    
    async def delete_task_config(self, config_id: int) -> bool:
        """删除任务配置"""
        return await self.config_service.delete_config(config_id)
    
    async def get_task_config(
        self, 
        config_id: int,
        verify_scheduler_status: bool = False,
        include_stats: bool = False
    ) -> Optional[Dict[str, Any]]:
        """获取任务配置"""
        return await self.config_service.get_config(config_id, verify_scheduler_status, include_stats)
    
    async def list_task_configs(self, query: TaskConfigQuery) -> List[Dict[str, Any]]:
        """列出任务配置"""
        return await self.config_service.list_configs(query)
    
    # ========== 执行管理委托方法 ==========
    
    async def execute_task_immediately(self, config_id: int, **kwargs) -> Optional[str]:
        """立即执行任务"""
        return await self.execution_service.execute_immediately(config_id, **kwargs)
    
    async def execute_task_by_type(
        self,
        task_type: str,
        task_params: Dict[str, Any],
        queue: str = "default",
        **options
    ) -> Optional[str]:
        """根据类型执行任务"""
        return await self.execution_service.execute_by_type(task_type, task_params, queue, **options)
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        return await self.execution_service.get_task_status(task_id)
    
    async def list_active_tasks(self) -> List[Dict[str, Any]]:
        """列出活跃任务"""
        return await self.execution_service.list_active_tasks()
    
    # ========== 调度管理委托方法 ==========
    
    async def manage_scheduled_task(self, config_id: int, action: str) -> Dict[str, Any]:
        """管理调度任务"""
        return await self.scheduler_service.manage_scheduled_task(config_id, action)
    
    async def get_scheduled_jobs(self) -> List[Dict[str, Any]]:
        """获取调度的任务"""
        return await self.scheduler_service.get_scheduled_jobs()
    
    async def load_scheduled_tasks_from_db(self) -> Dict[str, int]:
        """从数据库加载调度任务"""
        return await self.scheduler_service.load_scheduled_tasks_from_db()
    
    # ========== 监控管理委托方法 ==========
    
    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return await self.monitor_service.get_system_status()
    
    async def get_execution_stats(
        self,
        config_id: Optional[int] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """获取执行统计"""
        return await self.monitor_service.get_execution_stats(config_id, days)
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        return await self.monitor_service.get_queue_stats()
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return await self.monitor_service.health_check()
    
    # ========== 静态方法 ==========
    
    @staticmethod
    async def record_task_execution(db, config_id: Optional[int], status: str, result: Dict = None, error: str = None):
        """记录任务执行结果到数据库"""
        from app.core.redis_manager import redis_services
        import uuid
        
        execution = TaskExecution(
            config_id=config_id,
            task_id=str(uuid.uuid4()),
            status=status,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            result=result,
            error_message=error
        )
        db.add(execution)
        await db.commit()
        
        # 记录到Redis历史
        await redis_services.history.add_history_event(
            config_id=config_id or 0,
            event_data={
                "event": "task_execution_recorded",
                "task_id": execution.task_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat()
            }
        )


# 全局任务管理器实例
task_manager = TaskManager()