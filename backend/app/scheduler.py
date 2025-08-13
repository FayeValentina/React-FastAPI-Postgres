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
from app.core.task_registry import TaskType, ConfigStatus, SchedulerType

logger = logging.getLogger(__name__)

# 创建Redis调度源
redis_schedule_source = RedisScheduleSource(url=settings.redis.CONNECTION_URL)

# 创建调度器
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        redis_schedule_source,
        # 使用基于标签的调度（开发环境）
        LabelScheduleSource(broker=broker),
    ],
)

# 全局任务函数映射缓存
_task_function_cache: Dict[TaskType, Callable] = {}


async def initialize_scheduler():
    """初始化调度器"""
    try:
        # 启动Redis调度源
        await redis_schedule_source.startup()
        logger.info("Redis调度源初始化成功")
        
        # 加载所有任务函数到缓存
        _load_task_functions()
        
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
        # 获取任务函数
        task_func = get_task_function(config.task_type)
        if not task_func:
            logger.error(f"找不到任务类型 {config.task_type} 对应的任务函数")
            return False
        
        # 准备任务参数
        args = [config.id]  # 第一个参数总是config_id
        kwargs = config.parameters or {}
        
        # 生成唯一的任务ID
        task_id = f"scheduled_task_{config.id}"
        
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
        task_id = f"scheduled_task_{config_id}"
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
                "task_id": getattr(schedule, 'schedule_id', 'unknown'),
                "task_name": schedule.task_name,
                "schedule": getattr(schedule, 'cron', getattr(schedule, 'time', 'unknown')),
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
            # Cron调度
            cron_expression = schedule_config.get("cron_expression", "* * * * *")
            return {"cron": cron_expression}
            
        elif scheduler_type == SchedulerType.DATE:
            # 一次性调度
            run_date = schedule_config.get("run_date")
            if isinstance(run_date, str):
                run_date = datetime.fromisoformat(run_date)
            return {"time": run_date}
            
        elif scheduler_type == SchedulerType.INTERVAL:
            # 间隔调度 - 转换为cron表达式
            # TaskIQ 0.11.x 不直接支持间隔调度，需要转换为cron
            interval_seconds = (
                schedule_config.get("days", 0) * 86400 +
                schedule_config.get("hours", 0) * 3600 +
                schedule_config.get("minutes", 0) * 60 +
                schedule_config.get("seconds", 0)
            )
            
            if interval_seconds <= 0:
                logger.warning("间隔调度时间必须大于0")
                return None
                
            # 简单转换：如果是分钟间隔，转换为cron
            if interval_seconds % 60 == 0:
                minutes = interval_seconds // 60
                if minutes < 60:
                    return {"cron": f"*/{minutes} * * * *"}
                else:
                    hours = minutes // 60
                    if hours < 24:
                        return {"cron": f"0 */{hours} * * *"}
            
            # 对于其他间隔，使用每分钟检查的cron
            logger.warning(f"间隔调度 {interval_seconds}秒 转换为每分钟检查")
            return {"cron": "* * * * *"}
            
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


def _load_task_functions():
    """加载所有任务函数到缓存"""
    global _task_function_cache
    
    # 动态导入避免循环导入
    from app.tasks import cleanup_tasks, notification_tasks, data_tasks
    
    # 构建任务函数映射
    _task_function_cache = {
        TaskType.CLEANUP_TOKENS: cleanup_tasks.cleanup_expired_tokens,
        TaskType.CLEANUP_CONTENT: cleanup_tasks.cleanup_old_content,
        TaskType.CLEANUP_EVENTS: cleanup_tasks.cleanup_schedule_events,
        TaskType.SEND_EMAIL: notification_tasks.send_email,
        TaskType.DATA_EXPORT: data_tasks.export_data,
        TaskType.DATA_BACKUP: data_tasks.backup_data,
        # 为将来的任务类型预留
        # TaskType.BOT_SCRAPING: scraping_tasks.bot_scraping,
        # TaskType.MANUAL_SCRAPING: scraping_tasks.manual_scraping,
    }
    
    logger.info(f"已加载 {len(_task_function_cache)} 个任务函数")


def get_task_function(task_type: TaskType) -> Optional[Callable]:
    """
    根据任务类型获取任务函数
    
    Args:
        task_type: 任务类型
        
    Returns:
        对应的任务函数，如果不存在返回None
    """
    if not _task_function_cache:
        _load_task_functions()
    
    return _task_function_cache.get(task_type)


async def pause_scheduled_task(config_id: int) -> bool:
    """暂停调度任务（通过删除调度实现）"""
    return await unregister_scheduled_task(config_id)


async def resume_scheduled_task(config: TaskConfig) -> bool:
    """恢复调度任务（通过重新注册实现）"""
    return await register_scheduled_task(config)