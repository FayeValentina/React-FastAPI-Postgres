"""
调度管理服务
提供统一的调度管理接口和业务逻辑
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from app.tasks import (
    HybridScheduler, TaskDispatcher, EventRecorder, 
    JobConfigManager, MessageSender
)
from app.tasks.schedulers import scheduler as global_scheduler

logger = logging.getLogger(__name__)


class ScheduleManager:
    """调度管理器 - 业务逻辑层，专注于高级业务操作和跨组件协调"""
    
    def __init__(self):
        """初始化调度管理器，注入所需依赖"""
        self.scheduler = global_scheduler  # 使用全局调度器实例
        self.task_dispatcher = TaskDispatcher()
        self.message_sender = MessageSender(self.task_dispatcher)
        self.event_recorder = EventRecorder()
        self.config_manager = JobConfigManager()
        
        logger.info("ScheduleManager initialized with refactored components")
    
    # === 高级业务操作 ===
    
    async def create_bot_schedule_with_validation(
        self, db, bot_config_id: int, bot_config_name: str, interval_hours: int
    ) -> str:
        """创建调度前验证Bot配置"""
        # 业务逻辑：验证配置有效性
        from app.crud.bot_config import CRUDBotConfig
        
        config = await CRUDBotConfig.get_bot_configs(db, config_id=bot_config_id)
        if not config or not config.is_active:
            raise ValueError(f"Bot配置 {bot_config_id} 无效或未激活")
            
        if not config.auto_scrape_enabled:
            raise ValueError(f"Bot配置 {bot_config_id} 未启用自动爬取")
        
        # 记录操作事件
        await self.event_recorder.record_execution_event(
            task_id=f"create_schedule_{bot_config_id}_{datetime.now().timestamp()}",
            task_name="create_bot_schedule",
            status="STARTED"
        )
        
        try:
            job_id = self.scheduler.add_bot_scraping_schedule(
                bot_config_id, bot_config_name, interval_hours
            )
            logger.info(f"已创建Bot {bot_config_id} 的调度，任务ID: {job_id}")
            
            # 记录成功事件
            await self.event_recorder.record_execution_event(
                task_id=f"create_schedule_{bot_config_id}_{datetime.now().timestamp()}",
                task_name="create_bot_schedule",
                status="SUCCESS",
                result={"job_id": job_id}
            )
            
            return job_id
        except Exception as e:
            logger.error(f"创建Bot调度失败: {e}")
            
            # 记录失败事件
            await self.event_recorder.record_execution_event(
                task_id=f"create_schedule_{bot_config_id}_{datetime.now().timestamp()}",
                task_name="create_bot_schedule",
                status="FAILURE",
                error=str(e)
            )
            raise
    
    def manage_bot_schedule(
        self,
        bot_config_id: int,
        action: str,  # 'create', 'update', 'remove', 'pause', 'resume'
        **params
    ) -> Dict[str, Any]:
        """统一的Bot调度管理接口"""
        job_id = f'bot_scraping_{bot_config_id}'
        
        try:
            if action == 'create':
                result = self.scheduler.add_bot_scraping_schedule(
                    bot_config_id, params.get('bot_config_name', ''), 
                    params.get('interval_hours', 24)
                )
            elif action == 'update':
                result = self.scheduler.update_bot_scraping_schedule(
                    bot_config_id, params.get('bot_config_name', ''), 
                    params.get('interval_hours', 24)
                )
            elif action == 'remove':
                result = self.scheduler.remove_bot_scraping_schedule(bot_config_id)
            elif action == 'pause':
                result = self.scheduler.pause_schedule(job_id)
            elif action == 'resume':
                result = self.scheduler.resume_schedule(job_id)
            else:
                raise ValueError(f"不支持的操作: {action}")
            
            logger.info(f"Bot {bot_config_id} 调度操作 '{action}' 完成: {result}")
            return {"success": True, "result": result, "action": action}
            
        except Exception as e:
            logger.error(f"Bot调度操作失败: {e}")
            return {"success": False, "error": str(e), "action": action}
    
    async def trigger_scraping_with_limits(
        self, 
        db,
        bot_config_ids: List[int],
        session_type: str = "manual",
        validate_configs: bool = True
    ) -> Dict[str, Any]:
        """带限制检查的爬取触发（支持单个和批量）"""
        results = []
        
        if validate_configs:
            # 验证所有配置是否存在和激活
            from app.crud.bot_config import CRUDBotConfig
            for bot_config_id in bot_config_ids:
                config = await CRUDBotConfig.get_bot_configs(db, config_id=bot_config_id)
                if not config or not config.is_active:
                    raise ValueError(f"Bot配置 {bot_config_id} 无效或未激活")
        
        # 检查是否为单个任务
        if len(bot_config_ids) == 1:
            # 直接使用TaskDispatcher发送单个任务
            task_id = self.task_dispatcher.dispatch_manual_scraping(
                bot_config_ids[0], session_type
            )
            logger.info(f"已触发单个Bot {bot_config_ids[0]} 爬取任务，任务ID: {task_id}")
            return {"success": True, "task_ids": [task_id], "type": "single"}
        else:
            # 发送批量任务
            task_id = self.task_dispatcher.dispatch_batch_scraping(
                bot_config_ids, session_type
            )
            logger.info(f"已触发批量爬取任务，Bot数量: {len(bot_config_ids)}, 任务ID: {task_id}")
            return {"success": True, "task_ids": [task_id], "type": "batch"}
    
    def trigger_cleanup_with_validation(self, days_old: int = 30) -> str:
        """带验证的清理任务触发"""
        if days_old < 1:
            raise ValueError("清理天数必须大于0")
        if days_old > 365:
            raise ValueError("清理天数不能超过365天")
            
        # 直接使用TaskDispatcher
        task_id = self.task_dispatcher.dispatch_cleanup(days_old)
        logger.info(f"已触发清理任务，清理天数: {days_old}, 任务ID: {task_id}")
        return task_id
    
    # === 系统健康检查和监控 ===
    
    def get_system_health(self) -> Dict[str, Any]:
        """系统健康状态（增强版）"""
        try:
            # 整合多个组件的状态
            scheduler_health = self._check_scheduler_health()
            queue_health = self._check_queue_health()
            task_health = self._check_task_health()
            
            # 生成健康建议
            recommendations = self._generate_health_recommendations(
                scheduler_health, queue_health, task_health
            )
            
            return {
                "scheduler_health": scheduler_health,
                "queue_health": queue_health,
                "task_health": task_health,
                "recommendations": recommendations,
                "overall_status": self._calculate_overall_health(
                    scheduler_health, queue_health, task_health
                ),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"获取系统健康状态失败: {e}")
            return {
                "error": str(e),
                "overall_status": "ERROR",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _check_scheduler_health(self) -> Dict[str, Any]:
        """检查调度器健康状态"""
        all_schedules = self.scheduler.get_all_schedules()
        active_schedules = len([s for s in all_schedules if s.next_run_time])
        
        return {
            "status": "healthy" if self.scheduler._running else "stopped",
            "total_schedules": len(all_schedules),
            "active_schedules": active_schedules,
            "running": self.scheduler._running
        }
    
    def _check_queue_health(self) -> Dict[str, Any]:
        """检查队列健康状态"""
        scraping_length = self.message_sender.get_queue_length('scraping')
        cleanup_length = self.message_sender.get_queue_length('cleanup')
        default_length = self.message_sender.get_queue_length('default')
        
        return {
            "scraping_queue": {
                "length": scraping_length,
                "status": "overloaded" if scraping_length > 100 else "healthy"
            },
            "cleanup_queue": {
                "length": cleanup_length,
                "status": "overloaded" if cleanup_length > 50 else "healthy"
            },
            "default_queue": {
                "length": default_length,
                "status": "overloaded" if default_length > 50 else "healthy"
            }
        }
    
    def _check_task_health(self) -> Dict[str, Any]:
        """检查任务健康状态"""
        active_tasks = self.message_sender.get_active_tasks()
        
        return {
            "active_task_count": len(active_tasks),
            "status": "overloaded" if len(active_tasks) > 50 else "healthy",
            "tasks": active_tasks[:10]  # 只返回前10个任务的详情
        }
    
    def _generate_health_recommendations(
        self, scheduler_health: Dict, queue_health: Dict, task_health: Dict
    ) -> List[str]:
        """生成健康建议"""
        recommendations = []
        
        if not scheduler_health.get("running"):
            recommendations.append("调度器未运行，请检查调度器状态")
        
        if queue_health["scraping_queue"]["status"] == "overloaded":
            recommendations.append("爬取队列过载，建议增加worker或优化任务")
        
        if task_health["status"] == "overloaded":
            recommendations.append("活跃任务过多，建议检查任务执行效率")
        
        if scheduler_health["active_schedules"] == 0:
            recommendations.append("没有激活的调度任务，请检查调度配置")
        
        return recommendations
    
    def _calculate_overall_health(
        self, scheduler_health: Dict, queue_health: Dict, task_health: Dict
    ) -> str:
        """计算整体健康状态"""
        if not scheduler_health.get("running"):
            return "CRITICAL"
        
        issues = 0
        if queue_health["scraping_queue"]["status"] == "overloaded":
            issues += 1
        if task_health["status"] == "overloaded":
            issues += 1
        
        if issues >= 2:
            return "CRITICAL"
        elif issues == 1:
            return "WARNING"
        else:
            return "HEALTHY"
    
    async def bulk_update_schedules(
        self, db, updates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """批量更新调度（业务逻辑）"""
        results = []
        failed_updates = []
        
        for update in updates:
            try:
                bot_config_id = update["bot_config_id"]
                action = update.get("action", "update")
                
                # 如果是创建或更新，先验证配置
                if action in ["create", "update"]:
                    from app.crud.bot_config import CRUDBotConfig
                    config = await CRUDBotConfig.get_bot_configs(db, config_id=bot_config_id)
                    if not config or not config.is_active:
                        failed_updates.append({
                            "bot_config_id": bot_config_id,
                            "error": "配置无效或未激活"
                        })
                        continue
                
                # 执行操作
                result = self.manage_bot_schedule(
                    bot_config_id, action, **update
                )
                results.append(result)
                
            except Exception as e:
                failed_updates.append({
                    "bot_config_id": update.get("bot_config_id"),
                    "error": str(e)
                })
        
        return {
            "success_count": len(results),
            "failed_count": len(failed_updates),
            "results": results,
            "failed_updates": failed_updates
        }
    
    async def optimize_schedule_distribution(self) -> Dict[str, Any]:
        """优化调度分布（避免任务集中）"""
        all_schedules = self.scheduler.get_all_schedules()
        bot_schedules = [s for s in all_schedules if s.id.startswith('bot_scraping_')]
        
        # 分析当前调度分布
        time_distribution = {}
        for schedule in bot_schedules:
            if schedule.next_run_time:
                hour = schedule.next_run_time.hour
                time_distribution[hour] = time_distribution.get(hour, 0) + 1
        
        # 识别高峰时段（增加边界条件检查）
        distribution_values = list(time_distribution.values())
        max_tasks_per_hour = max(distribution_values) if distribution_values else 0
        peak_hours = [h for h, count in time_distribution.items() 
                      if count >= max_tasks_per_hour * 0.8] if max_tasks_per_hour > 0 else []
        
        return {
            "total_bot_schedules": len(bot_schedules),
            "time_distribution": time_distribution,
            "peak_hours": peak_hours,
            "max_tasks_per_hour": max_tasks_per_hour,
            "optimization_needed": max_tasks_per_hour > 10,
            "recommendations": self._generate_distribution_recommendations(
                time_distribution, peak_hours
            )
        }
    
    def _generate_distribution_recommendations(
        self, time_distribution: Dict, peak_hours: List
    ) -> List[str]:
        """生成调度分布优化建议"""
        recommendations = []
        
        if peak_hours:
            recommendations.append(f"建议将部分任务从高峰时段({peak_hours})分散到其他时间")
        
        max_hourly_tasks = max(time_distribution.values()) if time_distribution else 0
        if max_hourly_tasks > 20:
            recommendations.append("单小时任务数过多，建议增加调度间隔或分批执行")
        
        return recommendations
    
    def manage_cleanup_schedule(
        self,
        action: str,  # 'create', 'update', 'remove'
        schedule_id: str = "cleanup_old_sessions",
        days_old: int = 30,
        cron_expression: str = "0 2 * * *"
    ) -> Dict[str, Any]:
        """统一的清理任务调度管理"""
        try:
            if action == 'create':
                job_id = self.scheduler.add_cleanup_schedule(
                    schedule_id, days_old, cron_expression
                )
                result = {"job_id": job_id}
            elif action == 'update':
                # 先移除旧的，再添加新的
                self.scheduler.remove_schedule(schedule_id)
                job_id = self.scheduler.add_cleanup_schedule(
                    schedule_id, days_old, cron_expression
                )
                result = {"job_id": job_id}
            elif action == 'remove':
                success = self.scheduler.remove_schedule(schedule_id)
                result = {"success": success}
            else:
                raise ValueError(f"不支持的操作: {action}")
            
            logger.info(f"清理任务调度操作 '{action}' 完成: {result}")
            return {"success": True, "result": result, "action": action}
            
        except Exception as e:
            logger.error(f"清理任务调度操作失败: {e}")
            return {"success": False, "error": str(e), "action": action}
    
    # === 直接暴露底层功能（避免不必要的包装） ===
    
    @property
    def scheduler_instance(self) -> HybridScheduler:
        """直接访问调度器实例"""
        return self.scheduler
    
    @property
    def task_dispatcher_instance(self) -> TaskDispatcher:
        """直接访问任务分发器实例"""
        return self.task_dispatcher
    
    @property
    def message_sender_instance(self) -> MessageSender:
        """直接访问消息发送器实例"""
        return self.message_sender
    
    @property
    def event_recorder_instance(self) -> EventRecorder:
        """直接访问事件记录器实例"""
        return self.event_recorder
    
    @property
    def config_manager_instance(self) -> JobConfigManager:
        """直接访问配置管理器实例"""
        return self.config_manager