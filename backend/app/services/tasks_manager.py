"""
任务管理器 - 简化版，直接使用CRUD组件
"""
import logging
from typing import Dict, Any, List, Optional
import asyncio

from app.core.scheduler import scheduler
from app.core.task_dispatcher import TaskDispatcher
from app.core.task_registry import TaskType, TaskStatus, SchedulerType, ScheduleAction, TaskRegistry
from app.crud.task_config import crud_task_config
from app.crud.schedule_event import crud_schedule_event
from app.schemas.task_config_schemas import TaskConfigCreate, TaskConfigUpdate
from app.utils.common import get_current_time
from app.models.schedule_event import ScheduleEventType
from app.db.base import AsyncSessionLocal

logger = logging.getLogger(__name__)


# 全局任务执行函数
async def execute_scheduled_task(task_config_id: int):
    """执行调度任务的通用包装函数"""
    dispatcher = TaskDispatcher()
    try:
        return await dispatcher.dispatch_by_config_id(task_config_id)
    except Exception as e:
        logger.error(f"执行调度任务失败 {task_config_id}: {e}")
        raise


class TaskManager:
    """任务管理器 - 提供完整的任务生命周期管理"""
    
    def __init__(self):
        self.scheduler = scheduler
        self.dispatcher = TaskDispatcher()
        self._setup_event_listeners()
    
    def _setup_event_listeners(self):
        """设置调度器事件监听器"""
        from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
        
        self.scheduler.add_event_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_event_listener(self._on_job_error, EVENT_JOB_ERROR)
        self.scheduler.add_event_listener(self._on_job_missed, EVENT_JOB_MISSED)
    
    def _on_job_executed(self, event):
        """任务执行成功事件处理"""
        asyncio.create_task(self._record_event_async(
            job_id=event.job_id,
            event_type=ScheduleEventType.EXECUTED,
            result={'retval': str(event.retval) if hasattr(event, 'retval') else None}
        ))
    
    def _on_job_error(self, event):
        """任务执行错误事件处理"""
        asyncio.create_task(self._record_event_async(
            job_id=event.job_id,
            event_type=ScheduleEventType.ERROR,
            error_message=str(event.exception),
            error_traceback=event.traceback if hasattr(event, 'traceback') else None
        ))
    
    def _on_job_missed(self, event):
        """任务错过执行事件处理"""
        asyncio.create_task(self._record_event_async(
            job_id=event.job_id,
            event_type=ScheduleEventType.MISSED
        ))
    
    async def _record_event_async(
        self,
        job_id: str,  # 现在是有意义的ID，如 "cleanup_tok_int_1"
        event_type: ScheduleEventType,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None
    ):
        """异步记录调度事件"""
        try:
            # 从job_id中提取task_config_id
            task_config_id = TaskRegistry.extract_config_id_from_job_id(job_id)
            
            if task_config_id is None:
                logger.warning(f"无法从job_id中提取config_id: {job_id}")
                return
            
            async with AsyncSessionLocal() as db:
                await crud_schedule_event.create(
                    db,
                    task_config_id=task_config_id,
                    job_id=job_id,  # 现在是真正的APScheduler job_id
                    job_name=f"Task-{job_id}",
                    event_type=event_type,
                    result=result,
                    error_message=error_message,
                    error_traceback=error_traceback
                )
        except Exception as e:
            logger.error(f"记录调度事件失败: {e}")
    
    
    # === 任务配置管理功能 ===
    
    async def create_task_config(self, **kwargs) -> Optional[int]:
        """创建新的任务配置"""
        try:
            async with AsyncSessionLocal() as db:
                # 确保scheduler_type存在
                if 'scheduler_type' not in kwargs and 'schedule_config' in kwargs:
                    schedule_config = kwargs['schedule_config']
                    if 'scheduler_type' in schedule_config:
                        kwargs['scheduler_type'] = SchedulerType(schedule_config['scheduler_type'])
                
                config_data = TaskConfigCreate(**kwargs)
                config = await crud_task_config.create(db, obj_in=config_data)
                logger.info(f"已创建任务配置: {config.id} - {config.name}")
                return config.id
                
        except Exception as e:
            logger.error(f"创建任务配置失败: {e}")
            raise
    
    async def update_task_config(self, config_id: int, updates: Dict[str, Any]) -> bool:
        """更新任务配置"""
        try:
            async with AsyncSessionLocal() as db:
                config = await crud_task_config.get(db, config_id)
                if not config:
                    logger.warning(f"任务配置不存在: {config_id}")
                    return False
                
                update_data = TaskConfigUpdate(**updates)
                updated_config = await crud_task_config.update(db, db_obj=config, obj_in=update_data)
                
                if updated_config:
                    logger.info(f"已更新任务配置: {config_id}")
                    # 如果任务正在调度中，重新加载
                    await self.reload_scheduled_task(config_id)
                    return True
                    
                return False
                
        except Exception as e:
            logger.error(f"更新任务配置失败 {config_id}: {e}")
            return False
    
    async def delete_task_config(self, config_id: int) -> bool:
        """删除任务配置"""
        try:
            # 先停止调度
            self.stop_scheduled_task(config_id)
            
            async with AsyncSessionLocal() as db:
                success = await crud_task_config.delete(db, config_id)
                if success:
                    logger.info(f"已删除任务配置: {config_id}")
                return success
                
        except Exception as e:
            logger.error(f"删除任务配置失败 {config_id}: {e}")
            return False
    
    async def get_task_config(self, config_id: int, verify_scheduler_status: bool = False) -> Optional[Dict[str, Any]]:
        """获取任务配置详情"""
        try:
            async with AsyncSessionLocal() as db:
                config = await crud_task_config.get(db, config_id)
                if config:
                    result = {
                        'id': config.id,
                        'name': config.name,
                        'task_type': config.task_type.value if hasattr(config.task_type, 'value') else config.task_type,
                        'scheduler_type': config.scheduler_type.value if hasattr(config.scheduler_type, 'value') else config.scheduler_type,
                        'status': config.status.value if hasattr(config.status, 'value') else config.status,
                        'description': config.description,
                        'parameters': config.parameters or {},
                        'schedule_config': config.schedule_config or {},
                        'max_retries': config.max_retries or 0,
                        'timeout_seconds': config.timeout_seconds,
                        'priority': config.priority or 5,
                        'created_at': config.created_at.isoformat() if config.created_at else None,
                        'updated_at': config.updated_at.isoformat() if config.updated_at else None
                    }
                    
                    # 可选：验证 APScheduler 的实际状态
                    if verify_scheduler_status:
                        scheduler_status = self._get_scheduler_status(config_id)
                        result['scheduler_status'] = scheduler_status
                        
                        # 如果发现状态不一致，记录警告
                        db_status = config.status.value if hasattr(config.status, 'value') else config.status
                        if scheduler_status != db_status:
                            logger.warning(f"任务 {config_id} 状态不一致 - 数据库: {db_status}, 调度器: {scheduler_status}")
                    
                    return result
                return None
        except Exception as e:
            logger.error(f"获取任务配置失败 {config_id}: {e}")
            return None
    
    def _get_scheduler_status(self, config_id: int) -> str:
        """获取 APScheduler 中任务的实际状态"""
        try:
            jobs = self.scheduler.get_all_jobs()
            for job in jobs:
                extracted_config_id = TaskRegistry.extract_config_id_from_job_id(job.id)
                if extracted_config_id == config_id:
                    # 检查 next_run_time 来确定是否暂停
                    if job.next_run_time is None:
                        return "paused"
                    else:
                        return "active"
            
            # 如果没有找到对应的调度任务
            return "inactive"
            
        except Exception as e:
            logger.error(f"获取调度器状态失败 {config_id}: {e}")
            return "unknown"
    
    async def list_task_configs(
        self,
        task_type: str = None,
        status: str = None
    ) -> List[Dict[str, Any]]:
        """列出任务配置"""
        try:
            async with AsyncSessionLocal() as db:
                if task_type:
                    configs = await crud_task_config.get_by_type(
                        db,
                        task_type=TaskType(task_type),
                        status=TaskStatus(status) if status else None
                    )
                else:
                    configs = await crud_task_config.get_multi(db)
                
                return [
                    {
                        'id': c.id,
                        'name': c.name,
                        'task_type': c.task_type.value if hasattr(c.task_type, 'value') else c.task_type,
                        'scheduler_type': c.scheduler_type.value if hasattr(c.scheduler_type, 'value') else c.scheduler_type,
                        'status': c.status.value if hasattr(c.status, 'value') else c.status,
                        'description': c.description,
                        'parameters': c.parameters or {},
                        'schedule_config': c.schedule_config or {},
                        'max_retries': c.max_retries or 0,
                        'timeout_seconds': c.timeout_seconds,
                        'priority': c.priority or 5,
                        'created_at': c.created_at.isoformat() if c.created_at else None,
                        'updated_at': c.updated_at.isoformat() if c.updated_at else None
                    }
                    for c in configs
                ]
                
        except Exception as e:
            logger.error(f"列出任务配置失败: {e}")
            return []
    
    # === 任务调度管理功能 ===    
    async def manage_scheduled_task(self, config_id: int, action: ScheduleAction) -> Dict[str, Any]:
        """统一的调度任务管理方法
        
        Args:
            config_id: 任务配置ID
            action: 调度操作类型
            
        Returns:
            操作结果字典，包含success, message, status等信息
        """
        try:
            result = {"success": False, "message": "", "action": action.value, "config_id": config_id}
            target_status = None
            operation_name = ""
            
            # 根据action类型执行对应的调度器操作（不处理状态同步）
            if action == ScheduleAction.START:
                success = await self._start_scheduler_task(config_id)
                target_status = TaskStatus.ACTIVE
                operation_name = "启动"
                
            elif action == ScheduleAction.STOP:
                success = self._stop_scheduler_task(config_id)
                target_status = TaskStatus.INACTIVE
                operation_name = "停止"
                
            elif action == ScheduleAction.PAUSE:
                success = self._pause_scheduler_task(config_id)
                target_status = TaskStatus.PAUSED
                operation_name = "暂停"
                
            elif action == ScheduleAction.RESUME:
                success = self._resume_scheduler_task(config_id)
                target_status = TaskStatus.ACTIVE
                operation_name = "恢复"
                
            elif action == ScheduleAction.RELOAD:
                success = await self._reload_scheduler_task(config_id)
                target_status = TaskStatus.ACTIVE
                operation_name = "重新加载"
                
            else:
                result["message"] = f"不支持的操作类型: {action.value}"
                logger.error(f"不支持的调度操作: {action.value}")
                return result
            
            # 统一处理状态同步
            if success:
                # 调度操作成功，同步更新数据库状态
                try:
                    async with AsyncSessionLocal() as db:
                        await crud_task_config.update_status(db, config_id, target_status)
                    
                    result["success"] = True
                    result["message"] = f"任务 {config_id} {operation_name}成功"
                    result["status"] = target_status.value
                    logger.info(f"任务 {config_id} {operation_name}成功，状态同步为: {target_status.value}")
                
                except Exception as e:
                    logger.error(f"任务 {config_id} {operation_name}成功但状态同步失败: {e}")
                    result["success"] = True  # 调度操作本身成功
                    result["message"] = f"任务 {config_id} {operation_name}成功，但状态同步失败"
                    result["status"] = target_status.value
            else:
                # 调度操作失败，设置状态为ERROR
                try:
                    async with AsyncSessionLocal() as db:
                        await crud_task_config.update_status(db, config_id, TaskStatus.ERROR)
                except Exception as e:
                    logger.error(f"更新任务 {config_id} 状态为ERROR失败: {e}")
                
                result["message"] = f"任务 {config_id} {operation_name}失败"
                result["status"] = TaskStatus.ERROR.value
                logger.warning(f"任务 {config_id} {operation_name}失败，状态设置为ERROR")
            
            return result
            
        except Exception as e:
            # 异常情况下设置ERROR状态
            logger.error(f"执行调度操作失败 {config_id}[{action.value}]: {e}")
            try:
                async with AsyncSessionLocal() as db:
                    await crud_task_config.update_status(db, config_id, TaskStatus.ERROR)
            except:
                pass  # 忽略状态更新失败
                
            return {
                "success": False,
                "message": f"任务 {config_id} {action.value} 操作异常: {str(e)}",
                "action": action.value,
                "config_id": config_id,
                "status": TaskStatus.ERROR.value
            }
    
    # === 私有调度器操作方法（仅负责调度器操作，不处理状态同步）===
    
    async def _start_scheduler_task(self, config_id: int) -> bool:
        """启动调度器中的任务（不处理状态同步）"""
        try:
            return await self.scheduler.reload_task_from_database(config_id, execute_scheduled_task)
        except Exception as e:
            logger.error(f"启动调度器任务失败 {config_id}: {e}")
            return False
    
    def _stop_scheduler_task(self, config_id: int) -> bool:
        """停止调度器中的任务（不处理状态同步）"""
        try:
            return self.scheduler.remove_task_by_config_id(config_id)
        except Exception as e:
            logger.error(f"停止调度器任务失败 {config_id}: {e}")
            return False
    
    def _pause_scheduler_task(self, config_id: int) -> bool:
        """暂停调度器中的任务（不处理状态同步）"""
        try:
            jobs = self.scheduler.get_all_jobs()
            for job in jobs:
                extracted_config_id = TaskRegistry.extract_config_id_from_job_id(job.id)
                if extracted_config_id == config_id:
                    return self.scheduler.pause_job(job.id)
            logger.warning(f"未找到任务配置 {config_id} 的调度任务")
            return False
        except Exception as e:
            logger.error(f"暂停调度器任务失败 {config_id}: {e}")
            return False
    
    def _resume_scheduler_task(self, config_id: int) -> bool:
        """恢复调度器中的任务（不处理状态同步）"""
        try:
            jobs = self.scheduler.get_all_jobs()
            for job in jobs:
                extracted_config_id = TaskRegistry.extract_config_id_from_job_id(job.id)
                if extracted_config_id == config_id:
                    return self.scheduler.resume_job(job.id)
            logger.warning(f"未找到任务配置 {config_id} 的调度任务")
            return False
        except Exception as e:
            logger.error(f"恢复调度器任务失败 {config_id}: {e}")
            return False
    
    async def _reload_scheduler_task(self, config_id: int) -> bool:
        """重新加载调度器中的任务（不处理状态同步）"""
        try:
            return await self.scheduler.reload_task_from_database(config_id, execute_scheduled_task)
        except Exception as e:
            logger.error(f"重新加载调度器任务失败 {config_id}: {e}")
            return False
    
    # === 向后兼容的公共方法（已被manage_scheduled_task替代，但保留以兼容旧代码）===
    
    async def start_scheduled_task(self, config_id: int) -> bool:
        """启动任务调度（为了向后兼容保留）"""
        result = await self.manage_scheduled_task(config_id, ScheduleAction.START)
        return result["success"]
    
    def stop_scheduled_task(self, config_id: int) -> bool:
        """停止任务调度（为了向后兼容保留）"""
        result = asyncio.create_task(self.manage_scheduled_task(config_id, ScheduleAction.STOP))
        return result.result()["success"]
    
    async def pause_scheduled_task(self, config_id: int) -> bool:
        """暂停任务调度（为了向后兼容保留）"""
        result = await self.manage_scheduled_task(config_id, ScheduleAction.PAUSE)
        return result["success"]
    
    async def resume_scheduled_task(self, config_id: int) -> bool:
        """恢复任务调度（为了向后兼容保留）"""
        result = await self.manage_scheduled_task(config_id, ScheduleAction.RESUME)
        return result["success"]
    
    async def reload_scheduled_task(self, config_id: int) -> bool:
        """重新加载任务调度（为了向后兼容保留）"""
        result = await self.manage_scheduled_task(config_id, ScheduleAction.RELOAD)
        return result["success"]
    
    # === 任务执行功能 ===
    
    async def execute_task_immediately(self, config_id: int, **options) -> Optional[str]:
        """立即执行任务"""
        try:
            task_id = await self.dispatcher.dispatch_by_config_id(config_id, **options)
            logger.info(f"已立即执行任务 {config_id}，任务ID: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"立即执行任务失败 {config_id}: {e}")
            return None
    
    async def execute_task_by_type(
        self,
        task_type: str,
        task_params: Dict = None,
        queue: str = 'default',
        **options
    ) -> Optional[str]:
        """根据任务类型直接执行任务（不使用数据库配置）"""
        try:
            task_id = await self.dispatcher.dispatch_by_task_type(
                task_type=task_type,
                task_params=task_params,
                queue=queue,
                **options
            )
            logger.info(f"已执行 {task_type} 类型任务，任务ID: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"执行 {task_type} 类型任务失败: {e}")
            return None
    
    async def execute_multiple_configs(
        self,
        config_ids: List[int],
        **options
    ) -> List[str]:
        """批量执行多个任务配置"""
        try:
            task_ids = await self.dispatcher.dispatch_multiple_configs(config_ids, **options)
            logger.info(f"已批量执行 {len(config_ids)} 个任务配置，成功: {len(task_ids)}")
            return task_ids
        except Exception as e:
            logger.error(f"批量执行任务配置失败: {e}")
            return []
    
    async def execute_batch_by_task_type(
        self,
        task_type: str,
        **options
    ) -> List[str]:
        """批量执行指定类型的所有活跃任务配置"""
        try:
            task_ids = await self.dispatcher.dispatch_by_task_type_batch(task_type, **options)
            logger.info(f"已批量执行 {task_type} 类型任务，成功: {len(task_ids)}")
            return task_ids
        except Exception as e:
            logger.error(f"批量执行 {task_type} 类型任务失败: {e}")
            return []
    
    def get_scheduled_jobs(self) -> List[Dict[str, Any]]:
        """获取所有调度中的任务"""
        try:
            jobs = self.scheduler.get_all_jobs()
            result = []
            
            for job in jobs:
                result.append({
                    'id': job.id,
                    'name': job.name or f"Task-{job.id}",
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger),
                    'pending': job.next_run_time is not None,
                    'func': getattr(job.func, '__name__', str(job.func)) if job.func else None,
                    'args': list(job.args) if job.args else [],
                    'kwargs': dict(job.kwargs) if job.kwargs else {}
                })
            
            return result
            
        except Exception as e:
            logger.error(f"获取调度任务列表失败: {e}")
            return []
    
    # === 任务状态和队列管理 ===
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        return self.dispatcher.get_task_status(task_id)
    
    def get_queue_length(self, queue_name: str) -> int:
        """获取队列长度"""
        return self.dispatcher.get_queue_length(queue_name)
    
    def revoke_task(self, task_id: str, terminate: bool = False) -> Dict[str, Any]:
        """撤销任务"""
        return self.dispatcher.revoke_task(task_id, terminate)
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """获取活跃任务列表"""
        return self.dispatcher.get_active_tasks()
    
    def get_supported_task_types(self) -> Dict[str, str]:
        """获取支持的任务类型映射"""
        return self.dispatcher.get_supported_task_types()
    
    def is_task_type_supported(self, task_type: str) -> bool:
        """检查是否支持指定的任务类型"""
        return self.dispatcher.is_task_type_supported(task_type)
    
    # === 系统管理 ===
    
    async def start(self):
        """启动任务管理器"""
        self.scheduler.start()
        await self.scheduler.register_tasks_from_database(execute_scheduled_task)
        logger.info("任务管理器已启动")
    
    def shutdown(self):
        """关闭任务管理器"""
        self.scheduler.shutdown()
        logger.info("任务管理器已关闭")
    
    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            scheduled_jobs = self.scheduler.get_all_jobs()
            active_tasks = self.dispatcher.get_active_tasks()
            
            # 获取队列状态
            queues = {"default", "cleanup", "scraping", "high_priority", "low_priority"}
            queue_status = {}
            for queue in queues:
                try:
                    length = self.dispatcher.get_queue_length(queue)
                    queue_status[queue] = {"length": length, "status": "active"}
                except Exception:
                    queue_status[queue] = {"length": 0, "status": "unknown"}
            
            # 获取配置统计
            try:
                async with AsyncSessionLocal() as db:
                    config_stats = await crud_task_config.get_stats(db)
            except Exception as e:
                logger.warning(f"获取配置统计失败: {e}")
                config_stats = {"total": 0, "active": 0, "inactive": 0}
            
            return {
                "scheduler_running": self.scheduler.running,
                "total_scheduled_jobs": len(scheduled_jobs),
                "total_active_tasks": len(active_tasks),
                "timestamp": get_current_time().isoformat(),
                "scheduler": {
                    "running": self.scheduler.running,
                    "job_count": len(scheduled_jobs),
                    "uptime": "N/A"  # 可以后续添加启动时间跟踪
                },
                "celery": {
                    "active_tasks": len(active_tasks),
                    "broker_status": "connected",  # 简化版本
                    "workers": "N/A"  # 可以后续添加worker信息
                },
                "queues": queue_status
            }
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {
                "scheduler_running": False,
                "total_scheduled_jobs": 0,
                "total_active_tasks": 0,
                "timestamp": get_current_time().isoformat(),
                "scheduler": {
                    "running": False,
                    "job_count": 0,
                    "error": str(e)
                },
                "celery": {
                    "active_tasks": 0,
                    "error": str(e)
                },
                "queues": {}
            }


# 全局任务管理器实例
task_manager = TaskManager()