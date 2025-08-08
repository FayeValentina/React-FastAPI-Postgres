"""
通用任务管理器 - 协调4个核心组件，提供统一的任务管理接口
"""
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from app.core.scheduler import scheduler
from app.core.event_recorder import event_recorder
from app.core.task_dispatcher import task_dispatcher
from app.core.job_config_manager import job_config_manager
from app.core.task_type import TaskType, TaskStatus
from app.schemas.task_config import TaskConfigCreate, TaskConfigUpdate

logger = logging.getLogger(__name__)


# 通用调度任务的包装函数（避免序列化问题）
async def execute_scheduled_task(task_config_id: int):
    """执行调度任务的通用包装函数"""
    try:
        return await task_dispatcher.dispatch_by_config_id(task_config_id)
    except Exception as e:
        logger.error(f"执行调度任务失败 {task_config_id}: {e}")
        raise


class TaskManager:
    """通用任务管理器 - 提供完整的任务生命周期管理"""

    def __init__(self):
        # 设置事件监听器
        self._setup_event_listeners()

    def _setup_event_listeners(self):
        """设置调度器事件监听器"""
        from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED

        scheduler.add_event_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        scheduler.add_event_listener(self._on_job_error, EVENT_JOB_ERROR)
        scheduler.add_event_listener(self._on_job_missed, EVENT_JOB_MISSED)

    def _on_job_executed(self, event):
        """任务执行成功事件处理"""
        # 解析task_config_id
        try:
            task_config_id = int(event.job_id)
        except (ValueError, TypeError):
            task_config_id = None

        # 异步记录事件（不阻塞调度器）
        import asyncio
        asyncio.create_task(event_recorder.record_schedule_event(
            job_id=event.job_id,
            event_type='executed',
            task_config_id=task_config_id,
            job_name=event.job_id,
            result=event.retval if hasattr(event, 'retval') else None
        ))

    def _on_job_error(self, event):
        """任务执行错误事件处理"""
        # 解析task_config_id
        try:
            task_config_id = int(event.job_id)
        except (ValueError, TypeError):
            task_config_id = None

        # 异步记录事件
        import asyncio
        asyncio.create_task(event_recorder.record_schedule_event(
            job_id=event.job_id,
            event_type='error',
            task_config_id=task_config_id,
            job_name=event.job_id,
            error_message=str(event.exception),
            error_traceback=event.traceback if hasattr(event, 'traceback') else None
        ))

    def _on_job_missed(self, event):
        """任务错过执行事件处理"""
        # 解析task_config_id
        try:
            task_config_id = int(event.job_id)
        except (ValueError, TypeError):
            task_config_id = None

        # 异步记录事件
        import asyncio
        asyncio.create_task(event_recorder.record_schedule_event(
            job_id=event.job_id,
            event_type='missed',
            task_config_id=task_config_id,
            job_name=event.job_id
        ))

    # === 任务配置管理功能 ===

    async def create_task_config(
        self,
        name: str,
        task_type: Union[str, TaskType],
        scheduler_type: str,
        description: str = None,
        parameters: Dict[str, Any] = None,
        schedule_config: Dict[str, Any] = None,
        **kwargs
    ) -> Optional[int]:
        """
        创建新的任务配置
        """
        try:
            # Note: The scheduler_type parameter was added here in a previous step,
            # but it was missing from the job_config_manager.create_config call.
            # This is now corrected.
            config_id = await job_config_manager.create_config(
                name=name,
                task_type=task_type,
                scheduler_type=scheduler_type,
                description=description,
                parameters=parameters or {},
                schedule_config=schedule_config,
                **kwargs
            )

            if config_id:
                logger.info(f"已创建任务配置: {config_id} - {name}")

            return config_id

        except Exception as e:
            logger.error(f"创建任务配置失败 {name}: {e}")
            raise

    async def update_task_config(
        self,
        config_id: int,
        updates: Dict[str, Any]
    ) -> bool:
        """
        更新任务配置
        """
        try:
            success = await job_config_manager.update_config(config_id, updates)

            if success:
                logger.info(f"已更新任务配置: {config_id}")
                # 如果任务正在调度中，重新加载
                await self.reload_scheduled_task(config_id)

            return success

        except Exception as e:
            logger.error(f"更新任务配置失败 {config_id}: {e}")
            return False

    async def delete_task_config(self, config_id: int) -> bool:
        """
        删除任务配置
        """
        try:
            # 先停止调度
            self.stop_scheduled_task(config_id)

            # 删除配置
            success = await job_config_manager.remove_config(config_id)

            if success:
                logger.info(f"已删除任务配置: {config_id}")

            return success

        except Exception as e:
            logger.error(f"删除任务配置失败 {config_id}: {e}")
            return False

    async def get_task_config(self, config_id: int) -> Optional[Dict[str, Any]]:
        """获取任务配置详情"""
        try:
            # This now returns an ORM object, but the method signature still says Dict.
            # This is acceptable for now as the caller is what matters.
            return await job_config_manager.get_config(config_id)
        except Exception as e:
            logger.error(f"获取任务配置失败 {config_id}: {e}")
            return None

    async def list_task_configs(
        self,
        task_type: str = None,
        status: str = None
    ) -> List[Dict[str, Any]]:
        """
        列出任务配置
        """
        try:
            if task_type:
                return await job_config_manager.get_configs_by_type(task_type)
            else:
                return await job_config_manager.get_all_configs()

        except Exception as e:
            logger.error(f"列出任务配置失败: {e}")
            return []

    # === 任务调度管理功能 ===

    async def start_scheduled_task(self, config_id: int) -> bool:
        """
        启动任务调度
        """
        try:
            # 从数据库重新加载任务配置并启动调度
            success = await scheduler.reload_task_from_database(config_id, execute_scheduled_task)

            if success:
                logger.info(f"已启动任务调度: {config_id}")

            return success

        except Exception as e:
            logger.error(f"启动任务调度失败 {config_id}: {e}")
            return False

    def stop_scheduled_task(self, config_id: int) -> bool:
        """
        停止任务调度
        """
        try:
            success = scheduler.remove_task_by_config_id(config_id)

            if success:
                logger.info(f"已停止任务调度: {config_id}")

            return success

        except Exception as e:
            logger.error(f"停止任务调度失败 {config_id}: {e}")
            return False

    def pause_scheduled_task(self, config_id: int) -> bool:
        """
        暂停任务调度
        """
        try:
            success = scheduler.pause_job(str(config_id))

            if success:
                logger.info(f"已暂停任务调度: {config_id}")

            return success

        except Exception as e:
            logger.error(f"暂停任务调度失败 {config_id}: {e}")
            return False

    def resume_scheduled_task(self, config_id: int) -> bool:
        """
        恢复任务调度
        """
        try:
            success = scheduler.resume_job(str(config_id))

            if success:
                logger.info(f"已恢复任务调度: {config_id}")

            return success

        except Exception as e:
            logger.error(f"恢复任务调度失败 {config_id}: {e}")
            return False

    async def reload_scheduled_task(self, config_id: int) -> bool:
        """
        重新加载任务调度（用于配置更新后刷新调度）
        """
        try:
            success = await scheduler.reload_task_from_database(config_id, execute_scheduled_task)

            if success:
                logger.info(f"已重新加载任务调度: {config_id}")

            return success

        except Exception as e:
            logger.error(f"重新加载任务调度失败 {config_id}: {e}")
            return False

    # === 批量执行和状态监控功能 ===

    async def execute_task_immediately(
        self,
        config_id: int,
        **options
    ) -> Optional[str]:
        """
        立即执行单个任务
        """
        try:
            task_id = await task_dispatcher.dispatch_by_config_id(config_id, **options)
            logger.info(f"已立即执行任务 {config_id}，任务ID: {task_id}")
            return task_id

        except Exception as e:
            logger.error(f"立即执行任务失败 {config_id}: {e}")
            return None

    async def execute_multiple_tasks(
        self,
        config_ids: List[int],
        **options
    ) -> List[str]:
        """
        批量立即执行多个任务
        """
        try:
            task_ids = await task_dispatcher.dispatch_multiple_configs(config_ids, **options)
            logger.info(f"已批量执行 {len(task_ids)}/{len(config_ids)} 个任务")
            return task_ids

        except Exception as e:
            logger.error(f"批量执行任务失败: {e}")
            return []

    async def execute_tasks_by_type(
        self,
        task_type: str,
        **options
    ) -> List[str]:
        """
        按任务类型批量执行所有活跃任务
        """
        try:
            task_ids = await task_dispatcher.dispatch_by_task_type_batch(task_type, **options)
            logger.info(f"已按类型 {task_type} 批量执行 {len(task_ids)} 个任务")
            return task_ids

        except Exception as e:
            logger.error(f"按类型批量执行任务失败 {task_type}: {e}")
            return []

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取Celery任务状态"""
        try:
            return task_dispatcher.get_task_status(task_id)
        except Exception as e:
            logger.error(f"获取任务状态失败 {task_id}: {e}")
            return {"task_id": task_id, "status": "UNKNOWN", "error": str(e)}

    def get_active_celery_tasks(self) -> List[Dict[str, Any]]:
        """获取所有活跃的Celery任务"""
        try:
            return task_dispatcher.get_active_tasks()
        except Exception as e:
            logger.error(f"获取活跃任务列表失败: {e}")
            return []

    def get_scheduled_jobs(self) -> List[Dict[str, Any]]:
        """获取所有调度中的任务"""
        try:
            jobs = scheduler.get_all_jobs()
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

    # === 系统管理 ===

    async def start(self):
        """启动任务管理器"""
        # 启动调度器
        scheduler.start()

        # 从数据库加载所有活跃的任务配置到调度器
        await scheduler.register_tasks_from_database(execute_scheduled_task)

        logger.info("任务管理器已启动")

    def shutdown(self):
        """关闭任务管理器"""
        scheduler.shutdown()
        logger.info("任务管理器已关闭")

    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            # 获取基础状态
            scheduled_jobs = scheduler.get_all_jobs()
            active_tasks = task_dispatcher.get_active_tasks()

            # 获取配置统计
            config_stats = await job_config_manager.get_stats()

            return {
                "scheduler_running": scheduler.running,
                "total_scheduled_jobs": len(scheduled_jobs),
                "total_active_tasks": len(active_tasks),
                "config_stats": config_stats,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {
                "scheduler_running": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    # === 任务健康度和统计功能 ===

    async def get_task_health_report(self, config_id: int = None) -> Dict[str, Any]:
        """
        获取任务健康度报告
        """
        try:
            from app.db.base import AsyncSessionLocal
            from app.crud.schedule_event import crud_schedule_event
            from app.crud.task_execution import crud_task_execution

            async with AsyncSessionLocal() as db:
                if config_id:
                    # 单个任务的健康度报告
                    config = await job_config_manager.get_config(config_id)
                    if not config:
                        return {"error": f"任务配置不存在: {config_id}"}

                    schedule_stats = await crud_schedule_event.get_events_stats(db, task_config_id=config_id)
                    execution_stats = await crud_task_execution.get_execution_stats(db, task_config_id=config_id)

                    return {
                        "config_id": config_id,
                        "config_name": config['name'],
                        "task_type": config['task_type'],
                        "status": config['status'],
                        "schedule_stats": schedule_stats,
                        "execution_stats": execution_stats,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    # 全局健康度报告
                    all_configs = await job_config_manager.get_all_configs()

                    total_configs = len(all_configs)
                    active_configs = len([c for c in all_configs if c.get('status') == TaskStatus.ACTIVE.value])

                    type_stats = {}
                    for config in all_configs:
                        task_type = config.get('task_type', 'unknown')
                        if task_type not in type_stats:
                            type_stats[task_type] = {'total': 0, 'active': 0}
                        type_stats[task_type]['total'] += 1
                        if config.get('status') == 'active':
                            type_stats[task_type]['active'] += 1

                    global_execution_stats = await crud_task_execution.get_execution_stats(db)
                    global_schedule_stats = await crud_schedule_event.get_events_stats(db)

                    return {
                        "total_configs": total_configs,
                        "active_configs": active_configs,
                        "type_distribution": type_stats,
                        "global_schedule_stats": global_schedule_stats,
                        "global_execution_stats": global_execution_stats,
                        "timestamp": datetime.utcnow().isoformat()
                    }

        except Exception as e:
            logger.error(f"获取健康度报告失败: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

    async def get_task_execution_history(
        self,
        config_id: int = None,
        limit: int = 100,
        status_filter: str = None
    ) -> List[Dict[str, Any]]:
        """
        获取任务执行历史
        """
        try:
            from app.db.base import AsyncSessionLocal
            from app.crud.task_execution import crud_task_execution

            async with AsyncSessionLocal() as db:
                if config_id:
                    executions = await crud_task_execution.get_executions_by_config(
                        db,
                        task_config_id=config_id,
                        limit=limit
                    )
                else:
                    executions = await crud_task_execution.get_recent_executions(
                        db,
                        limit=limit
                    )

                result = []
                for execution in executions:
                    if status_filter and execution.status.value != status_filter:
                        continue

                    result.append({
                        "id": execution.id,
                        "task_config_id": execution.task_config_id,
                        "job_id": execution.job_id,
                        "job_name": execution.job_name,
                        "status": execution.status.value,
                        "started_at": execution.started_at.isoformat() if execution.started_at else None,
                        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                        "duration_seconds": execution.duration_seconds,
                        "result": execution.result,
                        "error_message": execution.error_message
                    })

                return result

        except Exception as e:
            logger.error(f"获取执行历史失败: {e}")
            return []

    async def get_task_schedule_events(
        self,
        config_id: int = None,
        limit: int = 100,
        event_type_filter: str = None
    ) -> List[Dict[str, Any]]:
        """
        获取任务调度事件
        """
        try:
            from app.db.base import AsyncSessionLocal
            from app.crud.schedule_event import crud_schedule_event

            async with AsyncSessionLocal() as db:
                if config_id:
                    events = await crud_schedule_event.get_events_by_config(
                        db,
                        task_config_id=config_id,
                        limit=limit
                    )
                else:
                    events = await crud_schedule_event.get_recent_events(
                        db,
                        limit=limit
                    )

                result = []
                for event in events:
                    if event_type_filter and event.event_type.value != event_type_filter:
                        continue

                    result.append({
                        "id": event.id,
                        "task_config_id": event.task_config_id,
                        "job_id": event.job_id,
                        "job_name": event.job_name,
                        "event_type": event.event_type.value,
                        "created_at": event.created_at.isoformat() if event.created_at else None,
                        "result": event.result,
                        "error_message": event.error_message
                    })

                return result

        except Exception as e:
            logger.error(f"获取调度事件失败: {e}")
            return []


# 全局任务管理器实例
task_manager = TaskManager()
