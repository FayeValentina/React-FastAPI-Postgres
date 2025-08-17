"""
任务管理服务
统一管理任务的创建、调度、执行和监控
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from app.broker import broker
from app.scheduler import (
    scheduler, 
    register_scheduled_task,
    unregister_scheduled_task,
    update_scheduled_task,
    get_scheduled_tasks,
    pause_scheduled_task,
    resume_scheduled_task,
    initialize_scheduler as init_scheduler,
    shutdown_scheduler
)
from app.db.base import AsyncSessionLocal
from app.models.task_config import TaskConfig
from app.schemas.task_config_schemas import TaskConfigCreate, TaskConfigUpdate, TaskConfigQuery
from app.crud.task_config import crud_task_config
from app.crud.task_execution import crud_task_execution
from app.crud.schedule_event import crud_schedule_event
from app.constant.task_registry import TaskType, ConfigStatus, SchedulerType, TaskRegistry
from app.models.schedule_event import ScheduleEventType
from app.models.task_execution import TaskExecution, ExecutionStatus
import uuid

logger = logging.getLogger(__name__)


class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self.broker = broker
        self.scheduler = scheduler
        self._initialized = False
        self._active_tasks = {}  # 缓存活跃任务
    
    async def initialize(self):
        """初始化任务管理器"""
        if self._initialized:
            return
        
        try:
            # 初始化调度器
            await init_scheduler()
            
            # 标记为已初始化
            self._initialized = True
            logger.info("任务管理器初始化完成")
            
        except Exception as e:
            logger.error(f"任务管理器初始化失败: {e}")
            raise
    
    async def shutdown(self):
        """关闭任务管理器"""
        try:
            await shutdown_scheduler()
            self._initialized = False
            logger.info("任务管理器已关闭")
        except Exception as e:
            logger.error(f"任务管理器关闭失败: {e}")
    
    async def create_task_config(self, **config_data) -> Optional[int]:
        """创建任务配置"""
        async with AsyncSessionLocal() as db:
            try:
                # 创建配置对象
                config_obj = TaskConfigCreate(**config_data)
                config = await crud_task_config.create(db, config_obj)
                
                # 如果是调度任务且状态为活跃，注册到调度器
                if (config.scheduler_type != SchedulerType.MANUAL and 
                    config.status == ConfigStatus.ACTIVE):
                    await register_scheduled_task(config)
                    
                    # 记录调度事件
                    await crud_schedule_event.create(
                        db=db,
                        config_id=config.id,
                        job_id=f"{TaskRegistry.SCHEDULED_TASK_PREFIX}{config.id}",
                        job_name=config.name,
                        event_type=ScheduleEventType.SCHEDULED
                    )
                
                logger.info(f"已创建任务配置: {config.id} - {config.name}")
                return config.id
                
            except Exception as e:
                logger.error(f"创建任务配置失败: {e}")
                return None
    
    async def update_task_config(self, config_id: int, update_data: Dict[str, Any]) -> bool:
        """更新任务配置"""
        async with AsyncSessionLocal() as db:
            try:
                config = await crud_task_config.get(db, config_id)
                if not config:
                    return False
                
                # 创建更新对象
                update_obj = TaskConfigUpdate(**update_data)
                updated_config = await crud_task_config.update(db, config, update_obj)
                
                # 更新调度器中的任务
                if updated_config.scheduler_type != SchedulerType.MANUAL:
                    await update_scheduled_task(updated_config)
                
                logger.info(f"已更新任务配置: {config_id}")
                return True
                
            except Exception as e:
                logger.error(f"更新任务配置失败: {e}")
                return False
    
    async def delete_task_config(self, config_id: int) -> bool:
        """删除任务配置"""
        async with AsyncSessionLocal() as db:
            try:
                # 先从调度器中移除
                await unregister_scheduled_task(config_id)
                
                # 从数据库删除
                success = await crud_task_config.delete(db, config_id)
                
                if success:
                    logger.info(f"已删除任务配置: {config_id}")
                    
                return success
                
            except Exception as e:
                logger.error(f"删除任务配置失败: {e}")
                return False
    
    async def execute_task_immediately(self, config_id: int, **kwargs) -> Optional[str]:
        """立即执行任务"""
        async with AsyncSessionLocal() as db:
            try:
                config = await crud_task_config.get(db, config_id)
                if not config:
                    raise ValueError(f"任务配置不存在: {config_id}")
                
                # 获取任务函数
                task_func = self._get_task_function(config.task_type)
                if not task_func:
                    raise ValueError(f"不支持的任务类型: {config.task_type}")
                
                # 合并参数
                task_params = {**(config.parameters or {}), **kwargs}
                
                # 发送任务到队列
                task = await task_func.kiq(config_id, **task_params)
                
                # 记录任务执行
                await crud_task_execution.create(
                    db=db,
                    config_id=config_id,
                    task_id=task.task_id,
                    status=ExecutionStatus.RUNNING,
                    started_at=datetime.utcnow()
                )
                
                logger.info(f"已立即执行任务 {config_id}，任务ID: {task.task_id}")
                return task.task_id
                
            except Exception as e:
                logger.error(f"立即执行任务失败: {e}")
                return None
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        try:
            # 先尝试从活跃任务缓存获取
            if task_id in self._active_tasks:
                return self._active_tasks[task_id]
            
            # 从Redis结果后端获取任务状态
            is_ready = await self.broker.result_backend.is_result_ready(task_id)
            
            if is_ready:
                result = await self.broker.result_backend.get_result(task_id)
                
                status_info = {
                    "task_id": task_id,
                    "status": ExecutionStatus.SUCCESS.value if result.is_err is False else ExecutionStatus.FAILED.value,
                    "result": result.return_value if result.is_err is False else None,
                    "error": str(result.error) if result.is_err and result.error else None,
                    "execution_time": result.execution_time if hasattr(result, 'execution_time') else None
                }
                
                # 更新数据库中的执行记录
                async with AsyncSessionLocal() as db:
                    execution = await crud_task_execution.get_by_task_id(db, task_id)
                    if execution:
                        await crud_task_execution.update_status(
                            db=db,
                            execution_id=execution.id,
                            status=ExecutionStatus.SUCCESS if result.is_err is False else ExecutionStatus.FAILED,
                            completed_at=datetime.utcnow(),
                            result={"return_value": result.return_value} if result.is_err is False else None,
                            error_message=str(result.error) if result.is_err else None
                        )
                
                return status_info
            else:
                # 任务还在执行中或不存在
                async with AsyncSessionLocal() as db:
                    execution = await crud_task_execution.get_by_task_id(db, task_id)
                    
                    if execution:
                        return {
                            "task_id": task_id,
                            "status": execution.status,
                            "result": execution.result,
                            "error": execution.error_message,
                            "started_at": execution.started_at.isoformat() if execution.started_at else None,
                            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                        }
                    else:
                        return {
                            "task_id": task_id,
                            "status": TaskRegistry.TASK_STATUS_PENDING,
                            "result": None,
                            "error": None,
                        }
                        
        except Exception as e:
            logger.error(f"获取任务状态失败 {task_id}: {e}")
            return {
                "task_id": task_id,
                "status": TaskRegistry.TASK_STATUS_ERROR,
                "result": None,
                "error": str(e),
            }
    
    async def manage_scheduled_task(self, config_id: int, action: str) -> Dict[str, Any]:
        """
        管理调度任务（启动、停止、暂停、恢复、重载）
        
        Args:
            config_id: 任务配置ID
            action: 操作类型
            
        Returns:
            操作结果
        """
        async with AsyncSessionLocal() as db:
            try:
                config = await crud_task_config.get(db, config_id)
                if not config:
                    return {
                        "success": False,
                        "message": f"任务配置 {config_id} 不存在",
                        "config_id": config_id
                    }
                
                success = False
                new_status = config.status
                
                if action == "start":
                    # 启动任务调度
                    if config.scheduler_type != SchedulerType.MANUAL:
                        success = await register_scheduled_task(config)
                        new_status = ConfigStatus.ACTIVE if success else ConfigStatus.ERROR
                    
                elif action == "stop":
                    # 停止任务调度
                    success = await unregister_scheduled_task(config_id)
                    new_status = ConfigStatus.INACTIVE if success else ConfigStatus.ERROR
                    
                elif action == "pause":
                    # 暂停任务调度
                    success = await pause_scheduled_task(config_id)
                    new_status = ConfigStatus.PAUSED if success else ConfigStatus.ERROR
                    
                elif action == "resume":
                    # 恢复任务调度
                    success = await resume_scheduled_task(config)
                    new_status = ConfigStatus.ACTIVE if success else ConfigStatus.ERROR
                    
                elif action == "reload":
                    # 重新加载任务调度
                    success = await update_scheduled_task(config)
                    new_status = ConfigStatus.ACTIVE if success else ConfigStatus.ERROR
                
                # 更新数据库状态
                if new_status != config.status:
                    await crud_task_config.update_status(db, config_id, new_status)
                
                # 记录调度事件
                event_type_map = {
                    "start": ScheduleEventType.SCHEDULED,
                    "stop": ScheduleEventType.PAUSED,
                    "pause": ScheduleEventType.PAUSED,
                    "resume": ScheduleEventType.RESUMED,
                    "reload": ScheduleEventType.SCHEDULED
                }
                
                await crud_schedule_event.create(
                    db=db,
                    config_id=config_id,
                    job_id=f"{TaskRegistry.SCHEDULED_TASK_PREFIX}{config_id}",
                    job_name=config.name,
                    event_type=event_type_map.get(action, ScheduleEventType.EXECUTED),
                    result={"action": action, "success": success}
                )
                
                return {
                    "success": success,
                    "message": f"任务 {config_id} {action} {'成功' if success else '失败'}",
                    "action": action,
                    "config_id": config_id,
                    "status": new_status.value
                }
                
            except Exception as e:
                logger.error(f"管理调度任务失败 {config_id}: {e}")
                return {
                    "success": False,
                    "message": f"操作失败: {str(e)}",
                    "action": action,
                    "config_id": config_id,
                    "status": "error"
                }
    
    async def list_active_tasks(self) -> List[Dict[str, Any]]:
        """列出活跃的任务执行记录"""
        from app.constant.task_registry import TaskRegistry
        
        async with AsyncSessionLocal() as db:
            executions = await crud_task_execution.get_running_executions(db)
            
            tasks = []
            for e in executions:
                # 获取实时状态
                status = await self.get_task_status(e.task_id)
                
                # 获取任务配置以获取队列信息
                config = await crud_task_config.get(db, e.config_id)
                queue_name = TaskRegistry.DEFAULT_QUEUE  # 默认队列
                
                if config and config.task_type:
                    try:
                        queue_name = TaskRegistry.get_queue_name(config.task_type)
                    except Exception:
                        queue_name = TaskRegistry.DEFAULT_QUEUE
                
                tasks.append({
                    "task_id": e.task_id,
                    "config_id": e.config_id,
                    "config_name": config.name if config else None,
                    "status": status.get("status", e.status.value if hasattr(e.status, 'value') else e.status),
                    "started_at": e.started_at.isoformat() if e.started_at else None,
                    "queue": queue_name,
                    "task_type": config.task_type.value if config and config.task_type else None,
                    "parameters": config.parameters if config else {},
                })
            
            return tasks
    
    async def _check_broker_connection(self) -> bool:
        """检查broker连接状态"""
        try:
            # 检查 result backend (Redis) 连接
            if self.broker.result_backend:
                test_task_id = "connection_test_" + str(datetime.utcnow().timestamp())
                # 这里只是检查Redis连接，如果成功说明至少result backend可用
                await self.broker.result_backend.is_result_ready(test_task_id)
            
            # 检查broker本身是否可用（这里返回True表示基本配置正常）
            # 注意：真正的连接检查需要worker运行时才能确定
            return True
            
        except Exception as e:
            logger.warning(f"Broker连接检查失败: {e}")
            return False
    
    async def _get_scheduled_jobs_count(self) -> int:
        """获取已调度的任务数量"""
        try:
            tasks = await get_scheduled_tasks()
            return len(tasks)
        except Exception as e:
            logger.warning(f"获取调度任务数量失败: {e}")
            return 0
    
    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            # 检查各组件状态
            broker_connected = await self._check_broker_connection()
            scheduled_count = await self._get_scheduled_jobs_count()
            active_tasks = await self.list_active_tasks()
            
            # 获取任务配置统计
            async with AsyncSessionLocal() as db:
                stats = await crud_task_config.get_stats(db)
            
            return {
                "broker_connected": broker_connected,
                "scheduler_running": self._initialized,
                "total_configs": stats.get("total_configs", 0),
                "active_configs": stats.get("active_configs", 0),
                "total_scheduled_jobs": scheduled_count,
                "total_active_tasks": len(active_tasks),
                "timestamp": datetime.utcnow().isoformat(),
                "scheduler": {
                    "initialized": self._initialized,
                    "scheduled_tasks": scheduled_count
                },
                "worker": {
                    "broker_connected": broker_connected,
                    "active_tasks": len(active_tasks)
                },
                "queues": {
                    TaskRegistry.DEFAULT_QUEUE: {"status": TaskRegistry.QUEUE_STATUS_ACTIVE if broker_connected else TaskRegistry.QUEUE_STATUS_DISCONNECTED}
                }
            }
            
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            # 返回符合schema的完整结构
            return {
                "broker_connected": False,
                "scheduler_running": False,
                "total_configs": 0,
                "active_configs": 0,
                "total_scheduled_jobs": 0,
                "total_active_tasks": 0,
                "timestamp": datetime.utcnow().isoformat(),
                "scheduler": {"initialized": False, "scheduled_tasks": 0, "error": str(e)},
                "worker": {"broker_connected": False, "active_tasks": 0, "error": str(e)},
                "queues": {}
            }
    
    def _get_task_function(self, task_type: TaskType):
        """根据任务类型获取任务函数"""
        from app.constant.task_registry import get_task_function
        return get_task_function(task_type)
    
    async def get_task_config(self, config_id: int, verify_scheduler_status: Optional[bool] = False, include_stats: Optional[bool] = False) -> Optional[Dict[str, Any]]:
        """获取任务配置详情"""
        async with AsyncSessionLocal() as db:
            config = await crud_task_config.get_with_relations(db, config_id)
            if not config:
                return None
            
            result = {
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
                'priority': config.priority,
                'created_at': config.created_at.isoformat() if config.created_at else None,
                'updated_at': config.updated_at.isoformat() if config.updated_at else None
            }
            
            # 验证调度器中的状态
            if verify_scheduler_status:
                scheduled_tasks = await get_scheduled_tasks()
                task_id = f"{TaskRegistry.SCHEDULED_TASK_PREFIX}{config_id}"
                is_scheduled = any(t.get("task_id") == task_id for t in scheduled_tasks)
                result['scheduler_status'] = "scheduled" if is_scheduled else "not_scheduled"
            
            # 包含执行统计数据
            if include_stats:
                stats = await crud_task_config.get_execution_stats(db, config_id)
                result["stats"] = stats
            
            return result
    
    async def list_task_configs(self, query: TaskConfigQuery) -> List[Dict[str, Any]]:
        """列出任务配置"""
        async with AsyncSessionLocal() as db:
            configs, _ = await crud_task_config.get_by_query(db, query)
            
            results = []
            
            for c in configs:
                config_dict = {
                    'id': c.id,
                    'name': c.name,
                    'description': c.description,
                    'task_type': c.task_type.value if hasattr(c.task_type, 'value') else c.task_type,
                    'scheduler_type': c.scheduler_type.value if hasattr(c.scheduler_type, 'value') else c.scheduler_type,
                    'status': c.status.value if hasattr(c.status, 'value') else c.status,
                    'parameters': c.parameters or {},
                    'schedule_config': c.schedule_config or {},
                    'priority': c.priority,
                    'created_at': c.created_at.isoformat() if c.created_at else None,
                    
                    # 添加缺少的必需字段
                    'max_retries': c.max_retries or 0,
                    'timeout_seconds': c.timeout_seconds,
                    'updated_at': c.updated_at.isoformat() if c.updated_at else None,
                    
                    # 添加可选字段（设为None，符合schema定义）
                    'scheduler_status': None,  # 在列表视图中不包含调度器状态（性能考虑）
                    'stats': None  # 在列表视图中不包含统计信息（性能考虑）
                }
                results.append(config_dict)
            return results

    @staticmethod
    async def record_task_execution(db, config_id: Optional[int], status: str, result: Dict = None, error: str = None):
        """记录任务执行结果到数据库"""
        execution = TaskExecution(
            config_id=config_id,
            task_id=str(uuid.uuid4()),  # 生成唯一的task_id
            status=status,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            result=result,
            error_message=error
        )
        db.add(execution)
        await db.commit()


# 全局任务管理器实例
task_manager = TaskManager()