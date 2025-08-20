import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.core.tasks.base import TaskServiceBase
from app.db.base import AsyncSessionLocal
from app.crud.task_config import crud_task_config
from app.core.tasks.registry import ConfigStatus, SchedulerType

logger = logging.getLogger(__name__)


class TaskSchedulerService(TaskServiceBase):
    """任务调度服务"""
    
    def __init__(self):
        super().__init__(service_name="TaskSchedulerService")
    
    async def manage_scheduled_task(self, config_id: int, action: str) -> Dict[str, Any]:
        """
        管理调度任务（启动、停止、暂停、恢复、重载）
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
                    success = await self._start_task(config)
                    new_status = ConfigStatus.ACTIVE if success else ConfigStatus.ERROR
                    
                elif action == "stop":
                    success = await self._stop_task(config_id)
                    new_status = ConfigStatus.INACTIVE if success else ConfigStatus.ERROR
                    
                elif action == "pause":
                    success = await self._pause_task(config_id)
                    new_status = ConfigStatus.PAUSED if success else ConfigStatus.ERROR
                    
                elif action == "resume":
                    success = await self._resume_task(config)
                    new_status = ConfigStatus.ACTIVE if success else ConfigStatus.ERROR
                    
                elif action == "reload":
                    success = await self._reload_task(config)
                    new_status = ConfigStatus.ACTIVE if success else ConfigStatus.ERROR
                
                # 更新数据库状态
                if new_status != config.status:
                    await crud_task_config.update_status(db, config_id, new_status)
                
                # 记录调度事件
                await self._record_schedule_event(config_id, action, success, new_status)
                
                return {
                    "success": success,
                    "message": f"任务 {config_id} {action} {'成功' if success else '失败'}",
                    "action": action,
                    "config_id": config_id,
                    "status": new_status.value
                }
                
            except Exception as e:
                logger.error(f"管理调度任务失败 {config_id}: {e}")
                
                await self._record_schedule_event(
                    config_id, action, False, ConfigStatus.ERROR, str(e)
                )
                
                return {
                    "success": False,
                    "message": f"操作失败: {str(e)}",
                    "action": action,
                    "config_id": config_id,
                    "status": "error"
                }
    
    async def get_scheduled_jobs(self) -> List[Dict[str, Any]]:
        """获取所有调度的任务"""
        try:
            tasks = await self.redis_services.scheduler.get_all_schedules()
            
            jobs = []
            for task in tasks:
                job_info = {
                    "id": task.get("task_id", ""),
                    "name": task.get("task_name", ""),
                    "next_run_time": task.get("next_run"),
                    "trigger": str(task.get("schedule", "")),
                    "pending": task.get("next_run") is not None,
                    "func": task.get("task_name"),
                    "args": [],
                    "kwargs": {}
                }
                jobs.append(job_info)
            
            return jobs
        except Exception as e:
            logger.error(f"获取调度任务失败: {e}")
            return []
    
    async def load_scheduled_tasks_from_db(self) -> Dict[str, int]:
        """从数据库加载调度任务"""
        loaded_count = 0
        failed_count = 0
        
        async with AsyncSessionLocal() as db:
            configs = await crud_task_config.get_scheduled_configs(db)
            
            for config in configs:
                try:
                    success = await self.redis_services.scheduler.register_task(config)
                    if success:
                        loaded_count += 1
                        logger.debug(f"成功加载调度任务: {config.name} (ID: {config.id})")
                        
                        await self._record_schedule_event(
                            config.id, "loaded", True, config.status
                        )
                    else:
                        failed_count += 1
                        logger.warning(f"加载调度任务失败: {config.name} (ID: {config.id})")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"加载任务 {config.name} (ID: {config.id}) 时出错: {e}")
        
        logger.info(f"从数据库加载调度任务完成: 成功 {loaded_count} 个, 失败 {failed_count} 个")
        
        return {
            "loaded": loaded_count,
            "failed": failed_count,
            "total": loaded_count + failed_count
        }
    
    async def _start_task(self, config) -> bool:
        """启动任务调度"""
        if config.scheduler_type != SchedulerType.MANUAL:
            return await self.redis_services.scheduler.register_task(config)
        return False
    
    async def _stop_task(self, config_id: int) -> bool:
        """停止任务调度"""
        return await self.redis_services.scheduler.unregister_task(config_id)
    
    async def _pause_task(self, config_id: int) -> bool:
        """暂停任务调度"""
        return await self.redis_services.scheduler.pause_task(config_id)
    
    async def _resume_task(self, config) -> bool:
        """恢复任务调度"""
        return await self.redis_services.scheduler.resume_task(config)
    
    async def _reload_task(self, config) -> bool:
        """重新加载任务调度"""
        return await self.redis_services.scheduler.update_task(config)
    
    async def _record_schedule_event(
        self,
        config_id: int,
        action: str,
        success: bool,
        status: ConfigStatus,
        error: Optional[str] = None
    ):
        """记录调度事件"""
        event_type_map = {
            "start": "task_started",
            "stop": "task_stopped",
            "pause": "task_paused",
            "resume": "task_resumed",
            "reload": "task_reloaded",
            "loaded": "task_loaded"
        }
        
        event_data = {
            "event": event_type_map.get(action, "task_action"),
            "action": action,
            "success": success,
            "new_status": status.value,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if error:
            event_data["error"] = error
        
        await self.redis_services.history.add_history_event(
            config_id=config_id,
            event_data=event_data
        )
        
        # 更新Redis中的状态
        await self.redis_services.history.update_status(config_id, status.value)