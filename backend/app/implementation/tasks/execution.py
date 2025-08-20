import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.core.tasks.base import TaskServiceBase
from app.core.tasks.executor import TaskExecutor
from app.db.base import AsyncSessionLocal
from app.crud.task_config import crud_task_config
from app.crud.task_execution import crud_task_execution
from app.core.tasks.registry import ExecutionStatus
from app.core.tasks import registry as tr

logger = logging.getLogger(__name__)


class TaskExecutionService(TaskServiceBase):
    """任务执行服务"""
    
    def __init__(self):
        super().__init__(service_name="TaskExecutionService")
        self.executor = TaskExecutor()
        self._active_tasks = {}  # 缓存活跃任务
    
    async def execute_immediately(self, config_id: int, **kwargs) -> Optional[str]:
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
                
                # 生成任务ID
                task_id = self.executor.generate_task_id()
                task_params['task_id'] = task_id
                
                # 发送任务到队列
                task = await task_func.kiq(config_id, **task_params)
                
                # 记录任务执行
                await self.executor.create_execution_record(
                    config_id=config_id,
                    task_id=task.task_id,
                    status=ExecutionStatus.RUNNING
                )
                
                # 记录执行事件
                await self._record_execution_event(config_id, task.task_id, "executed")
                
                # 更新状态
                await self.redis_services.history.update_status(config_id, "running")
                
                logger.info(f"已立即执行任务 {config_id}，任务ID: {task.task_id}")
                return task.task_id
                
            except Exception as e:
                logger.error(f"立即执行任务失败: {e}")
                await self._record_execution_event(config_id, None, "execution_failed", str(e))
                return None
    
    async def execute_by_type(
        self, 
        task_type: str,
        task_params: Dict[str, Any],
        queue: str = "default",
        **options
    ) -> Optional[str]:
        """根据类型直接执行任务"""
        try:
            # 获取任务函数
            task_func = tr.get_function(task_type)
            if not task_func:
                raise ValueError(f"Task type {task_type} not implemented")
            
            # 添加默认参数
            task_params_with_defaults = {
                "config_id": None,
                **task_params
            }
            
            # 执行任务
            task = await task_func.kiq(**task_params_with_defaults, **options)
            
            # 创建执行记录
            await self.executor.create_execution_record(
                config_id=None,
                task_id=task.task_id,
                status=ExecutionStatus.RUNNING
            )
            
            logger.info(f"已执行任务类型 {task_type}，任务ID: {task.task_id}")
            return task.task_id
            
        except Exception as e:
            logger.error(f"执行任务类型 {task_type} 失败: {e}")
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
                await self._update_execution_status(task_id, result)
                
                return status_info
            else:
                # 任务还在执行中或不存在
                return await self._get_pending_task_status(task_id)
                
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
            
            tasks = []
            for e in executions:
                # 获取实时状态
                status = await self.get_task_status(e.task_id)
                
                # 获取任务配置以获取队列信息
                config = await crud_task_config.get(db, e.config_id)
                queue_name = "default"
                
                if config and config.task_type:
                    try:
                        queue_name = tr.get_queue(config.task_type)
                    except Exception:
                        queue_name = "default"
                
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
    
    async def _record_execution_event(
        self, 
        config_id: int,
        task_id: Optional[str],
        event_type: str,
        error: Optional[str] = None
    ):
        """记录执行事件"""
        event_data = {
            "event": f"task_{event_type}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if task_id:
            event_data["task_id"] = task_id
        if error:
            event_data["error"] = error
        
        await self.redis_services.history.add_history_event(
            config_id=config_id,
            event_data=event_data
        )
    
    async def _update_execution_status(self, task_id: str, result):
        """更新执行状态"""
        # 使用TaskExecutor的封装方法更新数据库记录并获取执行记录
        execution = await self.executor.update_execution_record(
            task_id=task_id,
            status=ExecutionStatus.SUCCESS if result.is_err is False else ExecutionStatus.FAILED,
            result={"return_value": result.return_value} if result.is_err is False else None,
            error=str(result.error) if result.is_err else None
        )
        
        # 单独处理Redis状态更新，使用返回的execution记录避免重复查询
        if execution and execution.config_id:
            status = "success" if result.is_err is False else "failed"
            await self.redis_services.history.update_status(execution.config_id, status)
    
    async def _get_pending_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取待处理任务状态"""
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
                    "status": "pending",
                    "result": None,
                    "error": None,
                }