"""
任务管理器 - 简化版，直接使用CRUD组件
"""
import logging
from typing import Dict, Any, List, Optional
import asyncio

from app.core.scheduler import scheduler
from app.core.task_dispatcher import TaskDispatcher
from app.core.task_registry import TaskType, TaskStatus, SchedulerType
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
        job_id: str,
        event_type: ScheduleEventType,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None
    ):
        """异步记录调度事件"""
        try:
            # 解析task_config_id
            task_config_id = None
            try:
                task_config_id = int(job_id)
            except (ValueError, TypeError):
                pass
            
            async with AsyncSessionLocal() as db:
                await crud_schedule_event.create(
                    db,
                    task_config_id=task_config_id,
                    job_id=job_id,
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
    
    async def get_task_config(self, config_id: int) -> Optional[Dict[str, Any]]:
        """获取任务配置详情"""
        try:
            async with AsyncSessionLocal() as db:
                config = await crud_task_config.get(db, config_id)
                if config:
                    return {
                        'id': config.id,
                        'name': config.name,
                        'task_type': config.task_type.value,
                        'status': config.status.value,
                        'description': config.description,
                        'task_params': config.parameters,
                        'schedule_config': config.schedule_config,
                        'priority': config.priority,
                        'max_retries': config.max_retries,
                        'timeout_seconds': config.timeout_seconds,
                        'created_at': config.created_at.isoformat() if config.created_at else None,
                        'updated_at': config.updated_at.isoformat() if config.updated_at else None
                    }
                return None
        except Exception as e:
            logger.error(f"获取任务配置失败 {config_id}: {e}")
            return None
    
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
                        'task_type': c.task_type.value,
                        'status': c.status.value,
                        'description': c.description,
                        'priority': c.priority
                    }
                    for c in configs
                ]
                
        except Exception as e:
            logger.error(f"列出任务配置失败: {e}")
            return []
    
    # === 任务调度管理功能 ===
    
    async def start_scheduled_task(self, config_id: int) -> bool:
        """启动任务调度"""
        try:
            success = await self.scheduler.reload_task_from_database(config_id, execute_scheduled_task)
            if success:
                logger.info(f"已启动任务调度: {config_id}")
            return success
        except Exception as e:
            logger.error(f"启动任务调度失败 {config_id}: {e}")
            return False
    
    def stop_scheduled_task(self, config_id: int) -> bool:
        """停止任务调度"""
        try:
            success = self.scheduler.remove_task_by_config_id(config_id)
            if success:
                logger.info(f"已停止任务调度: {config_id}")
            return success
        except Exception as e:
            logger.error(f"停止任务调度失败 {config_id}: {e}")
            return False
    
    def pause_scheduled_task(self, config_id: int) -> bool:
        """暂停任务调度"""
        return self.scheduler.pause_job(str(config_id))
    
    def resume_scheduled_task(self, config_id: int) -> bool:
        """恢复任务调度"""
        return self.scheduler.resume_job(str(config_id))
    
    async def reload_scheduled_task(self, config_id: int) -> bool:
        """重新加载任务调度"""
        try:
            return await self.scheduler.reload_task_from_database(config_id, execute_scheduled_task)
        except Exception as e:
            logger.error(f"重新加载任务调度失败 {config_id}: {e}")
            return False
    
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
                    'job_id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger),
                    'args': job.args,
                    'kwargs': job.kwargs
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
            
            async with AsyncSessionLocal() as db:
                config_stats = await crud_task_config.get_stats(db)
            
            return {
                "scheduler_running": self.scheduler.running,
                "total_scheduled_jobs": len(scheduled_jobs),
                "total_active_tasks": len(active_tasks),
                "config_stats": config_stats,
                "timestamp": get_current_time().isoformat()
            }
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {
                "scheduler_running": False,
                "error": str(e),
                "timestamp": get_current_time().isoformat()
            }


# 全局任务管理器实例
task_manager = TaskManager()