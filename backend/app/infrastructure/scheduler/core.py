"""
重构原backend/app/services/redis/scheduler.py文件
核心调度服务 - 只负责TaskIQ调度，不做状态管理
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from croniter import croniter

from taskiq import ScheduledTask
from app.modules.tasks.models import TaskConfig
from app.infrastructure.tasks.task_registry_decorators import SchedulerType
from app.infrastructure.tasks import task_registry_decorators as tr
from app.infrastructure.redis.keyspace import redis_keys
logger = logging.getLogger(__name__)


class SchedulerCoreService:
    """
    核心调度服务 - 只负责TaskIQ调度
    
    职责：
    - 管理TaskIQ调度器（使用独立连接，这是必需的）
    - 注册/注销任务
    - 查询调度信息
    
    不负责：
    - 状态管理（由增强的HistoryService负责）
    """
    
    def __init__(self):
        # 使用broker中的统一调度源实例，确保序列化一致性
        from app.broker import schedule_source
        self.schedule_source = schedule_source
        self._initialized = False
    
    async def initialize(self):
        """初始化调度器"""
        if self._initialized:
            return
        
        try:
            await self.schedule_source.startup()
            self._initialized = True
            logger.info("TaskIQ调度器初始化成功")
        except Exception as e:
            logger.error(f"调度器初始化失败: {e}")
            raise
    
    async def shutdown(self):
        """关闭调度器"""
        try:
            if self._initialized:
                await self.schedule_source.shutdown()
                self._initialized = False
                logger.info("TaskIQ调度器已关闭")
        except Exception as e:
            logger.error(f"调度器关闭失败: {e}")
    
    async def register_task(self, config: TaskConfig, schedule_id: Optional[str] = None) -> Optional[str]:
        """注册任务到TaskIQ调度器，返回 schedule_id（失败返回 None）。"""
        try:
            task_func = tr.get_function(config.task_type)
            if not task_func:
                logger.error(f"找不到任务类型 {config.task_type}")
                return None

            scheduled_task = self._build_scheduled_task(config, task_func, schedule_id=schedule_id)
            if not scheduled_task:
                return None

            await self.schedule_source.add_schedule(scheduled_task)
            logger.info(
                "成功注册调度任务: %s (config_id=%s, schedule_id=%s)",
                config.name, config.id, getattr(scheduled_task, 'schedule_id', 'unknown')
            )
            return getattr(scheduled_task, 'schedule_id', None)

        except Exception as e:
            logger.error(f"注册调度任务失败: {e}")
            return None
    
    async def unregister_task(self, schedule_id: str) -> bool:
        """从TaskIQ调度器注销任务（按 schedule_id）。"""
        try:
            await self.schedule_source.delete_schedule(schedule_id)
            logger.info(f"成功注销调度任务: schedule_id={schedule_id}")
            return True
        except Exception as e:
            logger.error(f"注销调度任务失败: {e}")
            return False
    
    async def get_all_schedules(self) -> List[Dict[str, Any]]:
        """获取所有TaskIQ调度任务"""
        try:
            schedules = await self.schedule_source.get_schedules()
            tasks = []
            for schedule in schedules:
                config_id = None
                if hasattr(schedule, 'labels') and schedule.labels:
                    config_id = schedule.labels.get("config_id")
                    if config_id:
                        config_id = int(config_id)
                
                task_info = {
                    "schedule_id": getattr(schedule, 'schedule_id', 'unknown'),
                    "task_name": schedule.task_name,
                    "config_id": config_id,
                    "schedule": getattr(schedule, 'cron', getattr(schedule, 'time', 'unknown')),
                    "labels": getattr(schedule, 'labels', {}),
                    "next_run": self._get_next_run_time(schedule),
                }
                tasks.append(task_info)
            
            return tasks
        except Exception as e:
            logger.error(f"获取调度任务列表失败: {e}")
            return []
    
    async def is_schedule_present(self, schedule_id: str) -> bool:
        """检查特定 schedule_id 是否存在于 TaskIQ 调度器中"""
        schedules = await self.get_all_schedules()
        return any(task.get("schedule_id") == schedule_id for task in schedules)
    
    def _build_scheduled_task(self, config: TaskConfig, task_func, schedule_id: Optional[str] = None) -> Optional[ScheduledTask]:
        """构建调度任务（支持自定义 schedule_id，用于恢复/恢复原实例）。"""
        try:
            args = [config.id]
            kwargs = config.parameters or {}

            # 参数校验：确保所有必填参数都已在配置中提供
            try:
                params = tr.get_parameters(config.task_type) or []
                required_names = [
                    p.get("name")
                    for p in params
                    if p.get("required") and p.get("name") not in ("config_id", "context")
                ]
                missing = [name for name in required_names if name not in kwargs or kwargs.get(name) in (None, "")]
                if missing:
                    logger.error(
                        "任务参数缺失，无法注册调度: task_type=%s, config_id=%s, missing=%s",
                        config.task_type,
                        config.id,
                        ",".join(missing),
                    )
                    return None
            except Exception as e:
                logger.warning("任务参数校验失败(忽略并继续): %s", e)
            
            # schedule_id: new format scheduled_task:{config_id}:{uuid}
            task_id = schedule_id or redis_keys.scheduler.build_schedule_id(config.id)
            
            labels = {
                "config_id": str(config.id),
                "task_type": config.task_type,
                "scheduler_type": config.scheduler_type.value,
            }
            
            if config.timeout_seconds:
                labels["timeout"] = config.timeout_seconds
            
            if config.priority:
                labels["priority"] = config.priority
            
            task_params = {
                "schedule_id": task_id,
                "task_name": task_func.task_name,
                "args": args,
                "kwargs": kwargs,
                "labels": labels
            }
            
            schedule_params = self._get_schedule_params(config.scheduler_type, config.schedule_config)
            if not schedule_params:
                return None
            
            task_params.update(schedule_params)
            return ScheduledTask(**task_params)
            
        except Exception as e:
            logger.error(f"构建调度任务失败: {e}")
            return None
    
    def _get_schedule_params(self, scheduler_type: SchedulerType, schedule_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """根据配置创建TaskIQ调度参数"""
        try:
            if scheduler_type == SchedulerType.CRON:
                if "cron_expression" in schedule_config:
                    return {"cron": schedule_config["cron_expression"]}
                else:
                    minute = schedule_config.get("minute", "*")
                    hour = schedule_config.get("hour", "*")
                    day = schedule_config.get("day", "*")
                    month = schedule_config.get("month", "*")
                    day_of_week = schedule_config.get("day_of_week", "*")
                    cron_expression = f"{minute} {hour} {day} {month} {day_of_week}"
                    return {"cron": cron_expression}
                    
            elif scheduler_type == SchedulerType.DATE:
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
            # 处理 CRON 类型任务
            if hasattr(scheduled_task, 'cron') and scheduled_task.cron:
                try:
                    cron = croniter(scheduled_task.cron, datetime.now())
                    next_run = cron.get_next(datetime)
                    return next_run.isoformat()
                except Exception as e:
                    logger.error(f"计算CRON下次运行时间失败: {e}, cron表达式: {scheduled_task.cron}")
                    return None
            
            # 处理 DATE 类型任务
            elif hasattr(scheduled_task, 'time') and scheduled_task.time:
                scheduled_time = scheduled_task.time
                # 如果是字符串，转换为datetime对象
                if isinstance(scheduled_time, str):
                    try:
                        scheduled_time = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                    except ValueError:
                        logger.error(f"无效的日期时间格式: {scheduled_time}")
                        return None
                
                # 只返回未来的时间
                if scheduled_time > datetime.now():
                    return scheduled_time.isoformat()
                else:
                    # 已过期的一次性任务
                    return None
            
            # MANUAL 类型或其他类型没有下次运行时间
            return None
            
        except Exception as e:
            logger.error(f"获取下次运行时间失败: {e}")
            return None
