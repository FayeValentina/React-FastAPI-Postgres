import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from taskiq import ScheduledTask
from taskiq_redis import RedisScheduleSource

from app.core.config import settings
from app.models.task_config import TaskConfig
from app.core.tasks.registry import ConfigStatus, SchedulerType
from app.core.tasks import registry as tr

logger = logging.getLogger(__name__)


class SchedulerRedisService:
    """基于RedisScheduleSource的分布式调度器服务 - 使用新的连接池架构"""
    
    def __init__(self):
        # 使用与连接池相同的Redis URL
        self.schedule_source = RedisScheduleSource(url=settings.redis.CONNECTION_URL)
        self._initialized = False
    
    async def initialize(self):
        """初始化调度器"""
        if self._initialized:
            return
        
        try:
            await self.schedule_source.startup()
            self._initialized = True
            logger.info("Redis调度源初始化成功")
        except Exception as e:
            logger.error(f"Redis调度源初始化失败: {e}")
            raise
    
    async def shutdown(self):
        """关闭调度器"""
        try:
            if self._initialized:
                await self.schedule_source.shutdown()
                self._initialized = False
                logger.info("Redis调度源已关闭")
        except Exception as e:
            logger.error(f"Redis调度源关闭失败: {e}")
    
    async def register_task(self, config: TaskConfig) -> bool:
        """注册调度任务到Redis"""
        try:
            # 确保调度器已初始化
            await self.initialize()
            
            # 获取任务函数
            task_func = tr.get_function(config.task_type)
            if not task_func:
                logger.error(f"找不到任务类型 {config.task_type} 对应的任务函数")
                return False
            
            # 准备任务参数
            args = [config.id]
            kwargs = config.parameters or {}
            
            # 生成唯一的任务ID
            task_id = f"scheduled_task_{config.id}"
            
            # 准备 labels，包含超时时间
            labels = {
                "config_id": str(config.id),
                "task_type": config.task_type,
                "scheduler_type": config.scheduler_type.value,
            }
            
            # 添加超时时间到 labels（TaskIQ 会使用这个值）
            if config.timeout_seconds:
                labels["timeout"] = config.timeout_seconds
                logger.info(f"为定时任务 {config.name} 设置超时: {config.timeout_seconds}秒")
        
            # 创建调度任务参数
            task_params = {
                "schedule_id": task_id,
                "task_name": task_func.task_name,
                "args": args,
                "kwargs": kwargs,
                "labels": labels
            }
            
            # 根据调度类型添加调度参数
            schedule_params = self._get_schedule_params(config.scheduler_type, config.schedule_config)
            if not schedule_params:
                logger.error(f"无法创建调度参数: {config.scheduler_type} - {config.schedule_config}")
                return False
            
            task_params.update(schedule_params)
            
            # 创建调度任务
            scheduled_task = ScheduledTask(**task_params)
            
            logger.info(f"即将注册的调度任务 (字典格式): {scheduled_task.model_dump()}")
            
            # 添加到Redis调度源
            await self.schedule_source.add_schedule(scheduled_task)
            
            logger.info(f"成功注册调度任务: {config.name} (ID: {config.id})")
            return True
            
        except Exception as e:
            logger.error(f"注册调度任务失败 {config.name}: {e}")
            return False
    
    async def unregister_task(self, config_id: int) -> bool:
        """取消注册调度任务"""
        try:
            await self.initialize()
            task_id = f"scheduled_task_{config_id}"
            await self.schedule_source.delete_schedule(task_id)
            logger.info(f"成功取消调度任务: config_id={config_id}")
            return True
        except Exception as e:
            logger.error(f"取消调度任务失败 config_id={config_id}: {e}")
            return False
    
    async def update_task(self, config: TaskConfig) -> bool:
        """更新调度任务"""
        try:
            # 先取消旧的调度
            await self.unregister_task(config.id)
            
            # 如果任务仍然是活跃的，重新注册
            if config.status == ConfigStatus.ACTIVE and config.scheduler_type != SchedulerType.MANUAL:
                return await self.register_task(config)
            
            return True
        except Exception as e:
            logger.error(f"更新调度任务失败 {config.id}: {e}")
            return False
    
    async def get_all_schedules(self) -> List[Dict[str, Any]]:
        """获取所有调度任务"""
        try:
            await self.initialize()
            schedules = await self.schedule_source.get_schedules()
            
            tasks = []
            for schedule in schedules:
                task_info = {
                    "task_id": getattr(schedule, 'schedule_id', 'unknown'),
                    "task_name": schedule.task_name,
                    "schedule": getattr(schedule, 'cron', getattr(schedule, 'time', 'unknown')),
                    "labels": schedule.labels,
                    "next_run": self._get_next_run_time(schedule)
                }
                tasks.append(task_info)
            
            return tasks
        except Exception as e:
            logger.error(f"获取调度任务列表失败: {e}")
            return []
    
    async def pause_task(self, config_id: int) -> bool:
        """暂停调度任务（通过删除调度实现）"""
        return await self.unregister_task(config_id)
    
    async def resume_task(self, config: TaskConfig) -> bool:
        """恢复调度任务（通过重新注册实现）"""
        return await self.register_task(config)
    
    async def get_scheduler_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        try:
            schedules = await self.get_all_schedules()
            return {
                "initialized": self._initialized,
                "total_schedules": len(schedules),
                "redis_url": settings.redis.CONNECTION_URL,
                "status": "healthy" if self._initialized else "not_initialized"
            }
        except Exception as e:
            logger.error(f"获取调度器状态失败: {e}")
            return {
                "initialized": self._initialized,
                "total_schedules": 0,
                "redis_url": settings.redis.CONNECTION_URL,
                "status": "error",
                "error": str(e)
            }
    
    def _get_schedule_params(self, scheduler_type: SchedulerType, schedule_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """根据配置创建TaskIQ调度参数"""
        try:
            if scheduler_type == SchedulerType.CRON:
                # Cron调度
                if "cron_expression" in schedule_config:
                    cron_expression = schedule_config["cron_expression"]
                else:
                    minute = schedule_config.get("minute", "*")
                    hour = schedule_config.get("hour", "*")
                    day = schedule_config.get("day", "*")
                    month = schedule_config.get("month", "*")
                    day_of_week = schedule_config.get("day_of_week", "*")
                    cron_expression = f"{minute} {hour} {day} {month} {day_of_week}"
                
                return {"cron": cron_expression}
                
            elif scheduler_type == SchedulerType.DATE:
                # 一次性调度
                run_date = schedule_config.get("run_date")
                if isinstance(run_date, str):
                    run_date = datetime.fromisoformat(run_date)
                return {"time": run_date}
                
            else:
                logger.warning(f"不支持的调度类型: {scheduler_type}")
                return None
                
        except Exception as e:
            logger.error(f"创建调度参数失败: {e}")
            return None
    
    def _get_next_run_time(self, scheduled_task) -> Optional[str]:
        """获取下次运行时间"""
        try:
            from datetime import timedelta
            if hasattr(scheduled_task, 'cron') and scheduled_task.cron:
                # 简化实现：返回当前时间加1分钟
                next_time = datetime.now() + timedelta(minutes=1)
                return next_time.isoformat()
            elif hasattr(scheduled_task, 'time') and scheduled_task.time:
                return scheduled_task.time.isoformat()
        except:
            pass
        return None