"""
TaskIQ Scheduler 配置
管理定时任务和调度
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import RedisScheduleSource
from taskiq import ScheduledTask
# Schedule classes not needed in taskiq 0.11.x - schedules are defined directly in ScheduledTask

from app.broker import broker
from app.core.config import settings
from app.db.base import AsyncSessionLocal
from app.models.task_config import TaskConfig
from app.crud.task_config import crud_task_config
from app.constant.task_registry import TaskType, ConfigStatus, SchedulerType, TaskRegistry

logger = logging.getLogger(__name__)

# 创建Redis调度源
redis_schedule_source = RedisScheduleSource(url=settings.redis.CONNECTION_URL)

# 创建调度器
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        redis_schedule_source,
    ],
)


async def initialize_scheduler():
    """初始化调度器"""
    try:
        # 启动Redis调度源
        await redis_schedule_source.startup()
        logger.info("Redis调度源初始化成功")
        
        # 从数据库加载调度配置
        await load_schedules_from_db()
        logger.info("调度器初始化完成")
        
    except Exception as e:
        logger.error(f"调度器初始化失败: {e}")
        raise


async def shutdown_scheduler():
    """关闭调度器"""
    try:
        await redis_schedule_source.shutdown()
        logger.info("调度器已关闭")
    except Exception as e:
        logger.error(f"调度器关闭失败: {e}")


async def load_schedules_from_db():
    """从数据库加载任务调度配置"""
    try:
        async with AsyncSessionLocal() as db:
            # 获取所有需要调度的活跃任务配置
            configs = await crud_task_config.get_scheduled_configs(db)
            
            loaded_count = 0
            failed_count = 0
            
            for config in configs:
                try:
                    success = await register_scheduled_task(config)
                    if success:
                        loaded_count += 1
                        logger.debug(f"成功加载调度任务: {config.name} (ID: {config.id})")
                    else:
                        failed_count += 1
                        logger.warning(f"加载调度任务失败: {config.name} (ID: {config.id})")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"加载任务 {config.name} (ID: {config.id}) 时出错: {e}")
            
            logger.info(f"从数据库加载调度任务完成: 成功 {loaded_count} 个, 失败 {failed_count} 个")
            return loaded_count, failed_count
            
    except Exception as e:
        logger.error(f"从数据库加载调度任务失败: {e}")
        return 0, 0


async def register_scheduled_task(config: TaskConfig) -> bool:
    """
    注册单个调度任务到TaskIQ
    
    Args:
        config: 任务配置对象
        
    Returns:
        是否注册成功
    """
    try:
        from app.constant.task_registry import get_task_function
        # 获取任务函数
        task_func = get_task_function(config.task_type)
        if not task_func:
            logger.error(f"找不到任务类型 {config.task_type} 对应的任务函数")
            return False
        
        # 准备任务参数
        args = [config.id]  # 第一个参数总是config_id
        kwargs = config.parameters or {}
        
        # 生成唯一的任务ID
        task_id = f"{TaskRegistry.SCHEDULED_TASK_PREFIX}{config.id}"
        
        # 创建调度任务参数
        task_params = {
            "schedule_id": task_id,
            "task_name": task_func.task_name,
            "args": args,
            "kwargs": kwargs,
            "labels": {
                "config_id": str(config.id),
                "task_type": config.task_type.value,
                "scheduler_type": config.scheduler_type.value,
            }
        }
        
        # 根据调度类型添加调度参数
        schedule_params = _get_schedule_params(config.scheduler_type, config.schedule_config)
        if not schedule_params:
            logger.error(f"无法创建调度参数: {config.scheduler_type} - {config.schedule_config}")
            return False
        
        task_params.update(schedule_params)
        
        # 创建调度任务
        scheduled_task = ScheduledTask(**task_params)
        
        # 添加到Redis调度源
        await redis_schedule_source.add_schedule(scheduled_task)
        
        logger.info(f"成功注册调度任务: {config.name} (ID: {config.id}, 调度类型: {config.scheduler_type.value})")
        return True
        
    except Exception as e:
        logger.error(f"注册调度任务失败 {config.name} (ID: {config.id}): {e}")
        return False


async def unregister_scheduled_task(config_id: int) -> bool:
    """
    取消注册调度任务
    
    Args:
        config_id: 任务配置ID
        
    Returns:
        是否取消成功
    """
    try:
        task_id = f"{TaskRegistry.SCHEDULED_TASK_PREFIX}{config_id}"
        await redis_schedule_source.delete_schedule(task_id)
        logger.info(f"成功取消调度任务: config_id={config_id}")
        return True
    except Exception as e:
        logger.error(f"取消调度任务失败 config_id={config_id}: {e}")
        return False


async def update_scheduled_task(config: TaskConfig) -> bool:
    """
    更新调度任务
    
    Args:
        config: 更新后的任务配置
        
    Returns:
        是否更新成功
    """
    try:
        # 先取消旧的调度
        await unregister_scheduled_task(config.id)
        
        # 如果任务仍然是活跃的，重新注册
        if config.status == ConfigStatus.ACTIVE and config.scheduler_type != SchedulerType.MANUAL:
            return await register_scheduled_task(config)
        
        return True
    except Exception as e:
        logger.error(f"更新调度任务失败 {config.id}: {e}")
        return False


async def get_scheduled_tasks() -> list:
    """获取所有调度任务"""
    try:
        tasks = []
        # 从Redis获取所有调度任务
        all_schedules = await redis_schedule_source.get_schedules()
        
        for schedule in all_schedules:
            task_info = {
                "task_id": getattr(schedule, 'schedule_id', TaskRegistry.UNKNOWN_VALUE),
                "task_name": schedule.task_name,
                "schedule": getattr(schedule, 'cron', getattr(schedule, 'time', TaskRegistry.UNKNOWN_VALUE)),
                "labels": schedule.labels,
                "next_run": _get_next_run_time(schedule)
            }
            tasks.append(task_info)
        
        return tasks
    except Exception as e:
        logger.error(f"获取调度任务列表失败: {e}")
        return []


def _get_schedule_params(scheduler_type: SchedulerType, schedule_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    根据配置创建TaskIQ调度参数
    
    Args:
        scheduler_type: 调度类型
        schedule_config: 调度配置
        
    Returns:
        调度参数字典
    """
    try:
        if scheduler_type == SchedulerType.CRON:
            # Cron调度 - 支持两种格式
            if "cron_expression" in schedule_config:
                # 格式1: 直接的cron表达式
                cron_expression = schedule_config["cron_expression"]
            else:
                # 格式2: 分离的cron字段
                minute = schedule_config.get("minute", TaskRegistry.CRON_WILDCARD)
                hour = schedule_config.get("hour", TaskRegistry.CRON_WILDCARD)
                day = schedule_config.get("day", TaskRegistry.CRON_WILDCARD)
                month = schedule_config.get("month", TaskRegistry.CRON_WILDCARD)
                day_of_week = schedule_config.get("day_of_week", TaskRegistry.CRON_WILDCARD)
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


def _get_next_run_time(scheduled_task) -> Optional[str]:
    """获取下次运行时间"""
    try:
        # 对于cron任务，可以使用pycron计算下次运行时间
        if hasattr(scheduled_task, 'cron') and scheduled_task.cron:
            from pycron import is_now
            # 简化实现：返回当前时间加1分钟
            next_time = datetime.now() + timedelta(minutes=1)
            return next_time.isoformat()
        elif hasattr(scheduled_task, 'time') and scheduled_task.time:
            return scheduled_task.time.isoformat()
    except:
        pass
    return None


async def pause_scheduled_task(config_id: int) -> bool:
    """暂停调度任务（通过删除调度实现）"""
    return await unregister_scheduled_task(config_id)


async def resume_scheduled_task(config: TaskConfig) -> bool:
    """恢复调度任务（通过重新注册实现）"""
    return await register_scheduled_task(config)