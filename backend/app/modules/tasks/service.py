import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.modules.tasks.schemas import (
    TaskConfigCreate,
    TaskConfigUpdate,
    TaskConfigQuery,
)
from app.modules.tasks.repository import crud_task_config, crud_task_execution
from app.infrastructure.scheduler.scheduler import scheduler_service
from app.infrastructure.tasks.task_registry_decorators import SchedulerType, ScheduleAction
import app.infrastructure.tasks.task_registry_decorators as tr

logger = logging.getLogger(__name__)


class TaskService:
    """Business logic for task and scheduler management."""

    async def create_task_config(self, db: AsyncSession, config: TaskConfigCreate, auto_schedule: bool) -> Dict[str, Any]:
        try:
            db_config = await crud_task_config.create(db, config)
            if auto_schedule and config.scheduler_type != SchedulerType.MANUAL:
                success, message = await scheduler_service.register_task(db_config)
                if not success:
                    logger.warning(f"自动启动调度失败: {message}")
            schedule_info = await self._aggregate_config_status(db_config.id)
            return {
                'id': db_config.id,
                'name': db_config.name,
                'description': db_config.description,
                'task_type': db_config.task_type,
                'scheduler_type': db_config.scheduler_type.value,
                'parameters': db_config.parameters,
                'schedule_config': db_config.schedule_config,
                'max_retries': db_config.max_retries,
                'timeout_seconds': db_config.timeout_seconds,
                'priority': db_config.priority,
                'created_at': db_config.created_at,
                'updated_at': db_config.updated_at,
                'schedule_status': schedule_info.get('status'),
                'is_scheduled': schedule_info.get('is_scheduled', False),
                'status_consistent': schedule_info.get('status_consistent', True),
                'recent_history': schedule_info.get('recent_history', []),
            }
        except Exception as e:
            logger.error(f"创建任务配置失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def list_task_configs(self, db: AsyncSession, query: TaskConfigQuery) -> Dict[str, Any]:
        try:
            configs, total = await crud_task_config.get_by_query(db, query)
            results = []
            for config in configs:
                schedule_info = await self._aggregate_config_status(config.id)
                results.append({
                    'id': config.id,
                    'name': config.name,
                    'description': config.description,
                    'task_type': config.task_type,
                    'scheduler_type': config.scheduler_type.value,
                    'parameters': config.parameters,
                    'schedule_config': config.schedule_config,
                    'max_retries': config.max_retries,
                    'timeout_seconds': config.timeout_seconds,
                    'priority': config.priority,
                    'created_at': config.created_at,
                    'updated_at': config.updated_at,
                    'schedule_status': schedule_info.get('status'),
                    'is_scheduled': schedule_info.get('is_scheduled', False),
                    'status_consistent': schedule_info.get('status_consistent', True),
                })
            return {
                'items': results,
                'total': total,
                'page': query.page,
                'page_size': query.page_size,
                'pages': (total + query.page_size - 1) // query.page_size,
            }
        except Exception as e:
            logger.error(f"获取任务配置列表失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def get_task_config(self, db: AsyncSession, config_id: int, include_stats: bool) -> Dict[str, Any]:
        try:
            config = await crud_task_config.get(db, config_id)
            if not config:
                raise HTTPException(status_code=404, detail="配置不存在")
            schedule_info = await self._aggregate_config_status(config_id)
            result = {
                'id': config.id,
                'name': config.name,
                'description': config.description,
                'task_type': config.task_type,
                'scheduler_type': config.scheduler_type.value,
                'parameters': config.parameters,
                'schedule_config': config.schedule_config,
                'max_retries': config.max_retries,
                'timeout_seconds': config.timeout_seconds,
                'priority': config.priority,
                'created_at': config.created_at,
                'updated_at': config.updated_at,
                'schedule_status': schedule_info.get('status'),
                'is_scheduled': schedule_info.get('is_scheduled', False),
                'status_consistent': schedule_info.get('status_consistent', True),
                'recent_history': schedule_info.get('recent_history', []),
            }
            if include_stats:
                stats = await crud_task_config.get_execution_stats(db, config_id)
                result['stats'] = stats
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取配置详情失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def update_task_config(self, db: AsyncSession, config_id: int, update_data: TaskConfigUpdate) -> Dict[str, Any]:
        try:
            config = await crud_task_config.get(db, config_id)
            if not config:
                raise HTTPException(status_code=404, detail="配置不存在")
            updated_config = await crud_task_config.update(db, config, update_data)
            schedule_info = await self._aggregate_config_status(config_id)
            return {
                'id': updated_config.id,
                'name': updated_config.name,
                'description': updated_config.description,
                'task_type': updated_config.task_type,
                'scheduler_type': updated_config.scheduler_type.value,
                'parameters': updated_config.parameters,
                'schedule_config': updated_config.schedule_config,
                'max_retries': updated_config.max_retries,
                'timeout_seconds': updated_config.timeout_seconds,
                'priority': updated_config.priority,
                'created_at': updated_config.created_at,
                'updated_at': updated_config.updated_at,
                'schedule_status': schedule_info.get('status'),
                'is_scheduled': schedule_info.get('is_scheduled', False),
                'status_consistent': schedule_info.get('status_consistent', True),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"更新配置失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def delete_task_config(self, db: AsyncSession, config_id: int) -> Dict[str, Any]:
        try:
            config = await crud_task_config.get(db, config_id)
            if not config:
                raise HTTPException(status_code=404, detail="配置不存在")
            # 取消所有与该配置关联的调度实例
            try:
                schedule_ids = await scheduler_service.list_config_schedules(config_id)
                for sid in schedule_ids:
                    await scheduler_service.unregister(sid)
            except Exception as e:
                logger.warning(f"删除配置前注销调度失败: config_id={config_id}, err={e}")
            success = await crud_task_config.delete(db, config_id)
            if success:
                return {"success": True, "message": f"配置 {config.name} 删除成功"}
            raise HTTPException(status_code=500, detail="删除失败")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"删除配置失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    # Schedule management
    async def create_schedule_instance(self, db: AsyncSession, config_id: int) -> Dict[str, Any]:
        try:
            config = await crud_task_config.get(db, config_id)
            if not config:
                raise HTTPException(status_code=404, detail="配置不存在")
            success, schedule_id_or_msg = await scheduler_service.register_task(config)
            return {
                "success": success,
                "message": "created" if success else schedule_id_or_msg,
                "schedule_id": schedule_id_or_msg if success else None,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"创建调度实例失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def unregister_schedule(self, schedule_id: str) -> Dict[str, Any]:
        try:
            success, message = await scheduler_service.unregister(schedule_id)
            return {"success": success, "message": message, "schedule_id": schedule_id}
        except Exception as e:
            logger.error(f"注销调度实例失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def pause_schedule(self, schedule_id: str) -> Dict[str, Any]:
        try:
            success, message = await scheduler_service.pause(schedule_id)
            return {"success": success, "message": message, "schedule_id": schedule_id}
        except Exception as e:
            logger.error(f"暂停调度实例失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def resume_schedule(self, schedule_id: str) -> Dict[str, Any]:
        try:
            success, message = await scheduler_service.resume(schedule_id)
            return {"success": success, "message": message, "schedule_id": schedule_id}
        except Exception as e:
            logger.error(f"恢复调度实例失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def get_all_schedules(self) -> Dict[str, Any]:
        try:
            schedules = await scheduler_service.get_all_schedules()
            return {"schedules": schedules, "total": len(schedules)}
        except Exception as e:
            logger.error(f"获取调度列表失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def get_schedule_history(self, schedule_id: str, limit: int) -> Dict[str, Any]:
        try:
            history = await scheduler_service.state.get_schedule_history(schedule_id, limit)
            return {"schedule_id": schedule_id, "history": history, "count": len(history)}
        except Exception as e:
            logger.error(f"获取调度历史失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def get_schedule_summary(self) -> Dict[str, Any]:
        try:
            return await scheduler_service.get_scheduler_summary()
        except Exception as e:
            logger.error(f"获取调度摘要失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    # New schedule_id-first helpers
    async def list_config_schedules(self, config_id: int) -> Dict[str, Any]:
        try:
            schedule_ids = await scheduler_service.list_config_schedules(config_id)
            return {"config_id": config_id, "schedule_ids": schedule_ids}
        except Exception as e:
            logger.error(f"获取配置的调度实例失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def get_schedule_info(self, schedule_id: str) -> Dict[str, Any]:
        try:
            info = await scheduler_service.get_schedule_full_info(schedule_id)
            return info
        except Exception as e:
            logger.error(f"获取调度实例信息失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    # Aggregation helper used by config responses
    async def _aggregate_config_status(self, config_id: int) -> Dict[str, Any]:
        try:
            schedule_ids = await scheduler_service.list_config_schedules(config_id)
            if not schedule_ids:
                return {
                    "status": "inactive",
                    "is_scheduled": False,
                    "status_consistent": True,
                    "recent_history": [],
                }
            statuses = []
            recent_history: List[Dict[str, Any]] = []
            for sid in schedule_ids:
                st = await scheduler_service.state.get_schedule_status(sid)
                statuses.append(st.value)
                hist = await scheduler_service.state.get_schedule_history(sid, limit=2)
                recent_history.extend(hist)
            is_active = any(s == "active" for s in statuses)
            status = "active" if is_active else ("paused" if any(s == "paused" for s in statuses) else "inactive")
            # sort recent_history by timestamp desc if present
            try:
                recent_history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            except Exception:
                pass
            return {
                "status": status,
                "is_scheduled": is_active,
                "status_consistent": True,
                "recent_history": recent_history[:5],
            }
        except Exception as e:
            logger.warning(f"聚合配置状态失败: config_id={config_id}, err={e}")
            return {
                "status": "error",
                "is_scheduled": False,
                "status_consistent": False,
                "recent_history": [],
            }

    # Execution management
    async def get_config_executions(self, db: AsyncSession, config_id: int, limit: int) -> Dict[str, Any]:
        try:
            executions = await crud_task_execution.get_executions_by_config(db, config_id, limit)
            results = []
            for execution in executions:
                results.append({
                    'id': execution.id,
                    'task_id': execution.task_id,
                    'config_id': execution.config_id,
                    'is_success': execution.is_success,
                    'started_at': execution.started_at,
                    'completed_at': execution.completed_at,
                    'duration_seconds': execution.duration_seconds,
                    'result': execution.result,
                    'error_message': execution.error_message,
                    'created_at': execution.created_at,
                })
            return {"config_id": config_id, "executions": results, "count": len(results)}
        except Exception as e:
            logger.error(f"获取配置执行记录失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def get_recent_executions(self, db: AsyncSession, hours: int, limit: int) -> Dict[str, Any]:
        try:
            executions = await crud_task_execution.get_recent_executions(db, hours, limit)
            results = []
            for execution in executions:
                results.append({
                    'id': execution.id,
                    'task_id': execution.task_id,
                    'config_id': execution.config_id,
                    'config_name': execution.task_config.name if execution.task_config else None,
                    'task_type': execution.task_config.task_type if execution.task_config else None,
                    'is_success': execution.is_success,
                    'started_at': execution.started_at,
                    'completed_at': execution.completed_at,
                    'duration_seconds': execution.duration_seconds,
                    'error_message': execution.error_message,
                    'created_at': execution.created_at,
                })
            return {"hours": hours, "executions": results, "count": len(results)}
        except Exception as e:
            logger.error(f"获取最近执行记录失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def get_execution_stats(self, db: AsyncSession, config_id: Optional[int], days: int) -> Dict[str, Any]:
        try:
            if config_id:
                return await crud_task_execution.get_stats_by_config(db, config_id, days)
            return await crud_task_execution.get_global_stats(db, days)
        except Exception as e:
            logger.error(f"获取执行统计失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def get_failed_executions(self, db: AsyncSession, days: int, limit: int) -> Dict[str, Any]:
        try:
            executions = await crud_task_execution.get_failed_executions(db, days, limit)
            results = []
            for execution in executions:
                results.append({
                    'id': execution.id,
                    'task_id': execution.task_id,
                    'config_id': execution.config_id,
                    'config_name': execution.task_config.name if execution.task_config else None,
                    'task_type': execution.task_config.task_type if execution.task_config else None,
                    'started_at': execution.started_at,
                    'completed_at': execution.completed_at,
                    'duration_seconds': execution.duration_seconds,
                    'error_message': execution.error_message,
                    'created_at': execution.created_at,
                })
            return {"days": days, "failed_executions": results, "count": len(results)}
        except Exception as e:
            logger.error(f"获取失败执行记录失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def get_execution_detail(self, db: AsyncSession, execution_id: int) -> Dict[str, Any]:
        try:
            execution = await crud_task_execution.get(db, execution_id)
            if not execution:
                raise HTTPException(status_code=404, detail="执行记录不存在")
            return {
                'id': execution.id,
                'task_id': execution.task_id,
                'config_id': execution.config_id,
                'is_success': execution.is_success,
                'started_at': execution.started_at,
                'completed_at': execution.completed_at,
                'duration_seconds': execution.duration_seconds,
                'result': execution.result,
                'error_message': execution.error_message,
                'created_at': execution.created_at,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取执行详情失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def get_execution_by_task_id(self, db: AsyncSession, task_id: str) -> Dict[str, Any]:
        try:
            execution = await crud_task_execution.get_by_task_id(db, task_id)
            if not execution:
                raise HTTPException(status_code=404, detail="执行记录不存在")
            return {
                'id': execution.id,
                'task_id': execution.task_id,
                'config_id': execution.config_id,
                'config_name': execution.task_config.name if execution.task_config else None,
                'task_type': execution.task_config.task_type if execution.task_config else None,
                'is_success': execution.is_success,
                'started_at': execution.started_at,
                'completed_at': execution.completed_at,
                'duration_seconds': execution.duration_seconds,
                'result': execution.result,
                'error_message': execution.error_message,
                'error_traceback': execution.error_traceback,
                'created_at': execution.created_at,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"查询执行记录失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def cleanup_execution_history(self, db: AsyncSession, days_to_keep: int) -> Dict[str, Any]:
        try:
            deleted = await crud_task_execution.cleanup_old_executions(db, days_to_keep)
            return {
                "success": True,
                "deleted_count": deleted,
                "message": f"清理了 {deleted} 条超过 {days_to_keep} 天的执行记录",
            }
        except Exception as e:
            logger.error(f"清理执行历史失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    # System operations
    async def get_system_status(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            config_stats = await crud_task_config.get_stats(db)
            schedule_summary = await scheduler_service.get_scheduler_summary()
            execution_stats = await crud_task_execution.get_global_stats(db, days=7)
            return {
                "system_time": datetime.utcnow().isoformat(),
                "scheduler_status": "运行中",
                "database_status": "正常",
                "redis_status": "正常",
                "config_stats": config_stats,
                "schedule_summary": schedule_summary,
                "execution_stats": execution_stats,
            }
        except Exception as e:
            logger.error(f"获取系统状态失败: {str(e)}")
            raise HTTPException(status_code=503, detail=str(e))

    async def get_system_health(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            health_status = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {},
            }
            try:
                await crud_task_config.get_total_count(db)
                health_status["components"]["database"] = {"status": "healthy", "message": "连接正常"}
            except Exception as e:
                health_status["components"]["database"] = {"status": "unhealthy", "message": str(e)}
                health_status["status"] = "degraded"
            try:
                summary = await scheduler_service.get_scheduler_summary()
                if "error" in summary:
                    health_status["components"]["redis"] = {"status": "unhealthy", "message": summary["error"]}
                    health_status["status"] = "degraded"
                else:
                    health_status["components"]["redis"] = {"status": "healthy", "message": "连接正常"}
            except Exception as e:
                health_status["components"]["redis"] = {"status": "unhealthy", "message": str(e)}
                health_status["status"] = "degraded"
            try:
                schedules = await scheduler_service.get_all_schedules()
                health_status["components"]["scheduler"] = {
                    "status": "healthy",
                    "message": f"调度任务: {len(schedules)} 个",
                }
            except Exception as e:
                health_status["components"]["scheduler"] = {"status": "unhealthy", "message": str(e)}
                health_status["status"] = "degraded"
            return health_status
        except Exception as e:
            logger.error(f"健康检查失败: {str(e)}")
            return {"status": "unhealthy", "timestamp": datetime.utcnow().isoformat(), "error": str(e)}

    async def get_system_enums(self) -> Dict[str, Any]:
        try:
            return {
                "scheduler_types": [t.value for t in SchedulerType],
                "schedule_actions": [a.value for a in ScheduleAction],
                "task_types": list(tr.TASKS.keys()),
                "schedule_statuses": ["active", "inactive", "paused", "error"],
            }
        except Exception as e:
            logger.error(f"获取枚举值失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def get_task_info(self) -> Dict[str, Any]:
        try:
            tasks_info = tr.list_all_tasks()
            return {
                "tasks": tasks_info,
                "total_count": len(tasks_info),
                "generated_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"获取任务信息失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def get_system_dashboard(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            config_stats = await crud_task_config.get_stats(db)
            schedule_summary = await scheduler_service.get_scheduler_summary()
            stats_7d = await crud_task_execution.get_global_stats(db, days=7)
            stats_30d = await crud_task_execution.get_global_stats(db, days=30)
            return {
                "dashboard": {
                    "config_stats": config_stats,
                    "schedule_summary": schedule_summary,
                    "execution_stats": {
                        "last_7_days": stats_7d,
                        "last_30_days": stats_30d,
                    },
                    "generated_at": datetime.utcnow().isoformat(),
                }
            }
        except Exception as e:
            logger.error(f"获取仪表板数据失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    # Admin maintenance utilities
    async def list_orphans(self) -> Dict[str, Any]:
        try:
            ids = await scheduler_service.find_orphan_schedule_ids()
            return {"orphan_schedule_ids": ids, "count": len(ids)}
        except Exception as e:
            logger.error(f"获取孤儿调度实例失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def cleanup_orphans(self) -> Dict[str, Any]:
        try:
            result = await scheduler_service.cleanup_orphan_schedules()
            return result
        except Exception as e:
            logger.error(f"清理孤儿调度实例失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    async def cleanup_legacy(self) -> Dict[str, Any]:
        try:
            result = await scheduler_service.cleanup_legacy_artifacts()
            return result
        except Exception as e:
            logger.error(f"清理遗留资源失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))


task_service = TaskService()
