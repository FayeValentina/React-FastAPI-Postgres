import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.tasks.base import TaskServiceBase
from app.db.base import AsyncSessionLocal
from app.crud.task_config import crud_task_config
from app.crud.task_execution import crud_task_execution

logger = logging.getLogger(__name__)

class TaskMonitorService(TaskServiceBase):
    """系统监控服务"""
    
    def __init__(self):
        super().__init__(service_name="TaskMonitorService")
    
    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            # 检查各组件状态
            broker_connected = await self._check_broker_connection()
            scheduled_count = await self._get_scheduled_jobs_count()
            active_tasks = await self._get_active_tasks_summary()
            
            # 获取任务配置统计
            async with AsyncSessionLocal() as db:
                stats = await crud_task_config.get_stats(db)
            
            # 从Redis获取最近的调度历史
            recent_history = await self._get_recent_history()
            
            return {
                "broker_connected": broker_connected,
                "scheduler_running": self._initialized,
                "total_configs": stats.get("total_configs", 0),
                "active_configs": stats.get("active_configs", 0),
                "total_scheduled_jobs": scheduled_count,
                "total_active_tasks": active_tasks.get("count", 0),
                "timestamp": datetime.utcnow().isoformat(),
                "scheduler": {
                    "initialized": self._initialized,
                    "scheduled_tasks": scheduled_count,
                    "redis_connected": self.redis_services.scheduler._initialized
                },
                "worker": {
                    "broker_connected": broker_connected,
                    "active_tasks": active_tasks.get("count", 0),
                    "queues": active_tasks.get("by_queue", {})
                },
                "queues": await self._get_queue_stats(),
                "recent_events": recent_history[:5]
            }
            
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return self._get_error_status(str(e))
    
    async def get_execution_stats(
        self, 
        config_id: Optional[int] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """获取执行统计"""
        async with AsyncSessionLocal() as db:
            if config_id:
                return await crud_task_execution.get_stats_by_config(db, config_id, days)
            else:
                return await crud_task_execution.get_global_stats(db, days)
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        from app.core.tasks import registry as tr
        
        queues = tr.all_queues()
        stats = {}
        
        # 初始化所有队列
        for queue_name in queues:
            stats[queue_name] = {
                "length": 0,
                "status": "active"
            }
        
        # 获取活跃任务信息
        async with AsyncSessionLocal() as db:
            active_tasks = await crud_task_execution.get_running_executions(db)
            
            for task in active_tasks:
                config = await crud_task_config.get(db, task.config_id)
                if config:
                    try:
                        queue_name = tr.get_queue(config.task_type)
                    except:
                        queue_name = "default"
                    
                    if queue_name not in stats:
                        stats[queue_name] = {"length": 0, "status": "active"}
                    
                    stats[queue_name]["length"] += 1
        
        return {
            "queues": stats,
            "total_tasks": sum(q["length"] for q in stats.values())
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health_status = {
            "status": "unknown",
            "checks": {}
        }
        
        try:
            # 检查broker连接
            health_status["checks"]["broker"] = await self._check_broker_connection()
            
            # 检查Redis连接
            redis_health = await self.redis_services.health_check()
            health_status["checks"]["redis"] = redis_health.get("overall") == "healthy"
            
            # 检查数据库连接
            health_status["checks"]["database"] = await self._check_database_connection()
            
            # 整体状态
            all_healthy = all(health_status["checks"].values())
            health_status["status"] = "healthy" if all_healthy else "degraded"
            
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            health_status["status"] = "error"
            health_status["error"] = str(e)
        
        return health_status
    
    async def _check_broker_connection(self) -> bool:
        """检查broker连接状态"""
        try:
            if self.broker.result_backend:
                test_task_id = "connection_test_" + str(datetime.utcnow().timestamp())
                await self.broker.result_backend.is_result_ready(test_task_id)
            return True
        except Exception as e:
            logger.warning(f"Broker连接检查失败: {e}")
            return False
    
    async def _check_database_connection(self) -> bool:
        """检查数据库连接"""
        try:
            async with AsyncSessionLocal() as db:
                await crud_task_config.get_total_count(db)
            return True
        except Exception as e:
            logger.warning(f"数据库连接检查失败: {e}")
            return False
    
    async def _get_scheduled_jobs_count(self) -> int:
        """获取已调度的任务数量"""
        try:
            tasks = await self.redis_services.scheduler.get_all_schedules()
            return len(tasks)
        except Exception as e:
            logger.warning(f"获取调度任务数量失败: {e}")
            return 0
    
    async def _get_active_tasks_summary(self) -> Dict[str, Any]:
        """获取活跃任务摘要"""
        try:
            async with AsyncSessionLocal() as db:
                executions = await crud_task_execution.get_running_executions(db)
                
                by_queue = {}
                for e in executions:
                    config = await crud_task_config.get(db, e.config_id)
                    if config:
                        from app.core.tasks import registry as tr
                        try:
                            queue_name = tr.get_queue(config.task_type)
                        except:
                            queue_name = "default"
                        
                        by_queue[queue_name] = by_queue.get(queue_name, 0) + 1
                
                return {
                    "count": len(executions),
                    "by_queue": by_queue
                }
        except Exception as e:
            logger.warning(f"获取活跃任务摘要失败: {e}")
            return {"count": 0, "by_queue": {}}
    
    async def _get_recent_history(self) -> List[Dict[str, Any]]:
        """获取最近的历史事件"""
        recent_history = []
        try:
            async with AsyncSessionLocal() as db:
                stats = await crud_task_config.get_stats(db)
                
                for config_id in range(1, min(6, stats.get("total_configs", 0) + 1)):
                    history = await self.redis_services.history.get_history(config_id, limit=1)
                    if history:
                        recent_history.extend(history)
        except:
            pass
        
        return recent_history
    
    async def _get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        return await self.get_queue_stats()
    
    def _get_error_status(self, error: str) -> Dict[str, Any]:
        """获取错误状态"""
        return {
            "broker_connected": False,
            "scheduler_running": False,
            "total_configs": 0,
            "active_configs": 0,
            "total_scheduled_jobs": 0,
            "total_active_tasks": 0,
            "timestamp": datetime.utcnow().isoformat(),
            "scheduler": {"initialized": False, "error": error},
            "worker": {"broker_connected": False, "error": error},
            "queues": {},
            "error": error
        }