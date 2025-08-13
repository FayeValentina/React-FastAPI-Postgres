"""
TaskIQ Scheduler 配置
管理定时任务和调度
"""
from datetime import datetime, timedelta
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import RedisScheduleSource

from app.broker import broker
from app.core.config import settings
from app.db.base import AsyncSessionLocal
from app.models.task_config import TaskConfig
from app.crud.task_config import crud_task_config
from app.core.task_registry import TaskType, SchedulerType


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


async def initialize_scheduler():
    """初始化调度器"""
    await redis_schedule_source.startup()


async def load_schedules_from_db():
    """从数据库加载任务调度配置"""
    async with AsyncSessionLocal() as db:
        # 使用CRUD方法查询所有需要调度的任务配置
        configs = await crud_task_config.get_scheduled_configs(db)
        
        for config in configs:
            await register_scheduled_task(config)


async def register_scheduled_task(config: TaskConfig):
    """注册单个调度任务"""
    task_func = get_task_function(config.task_type)
    if not task_func:
        return
    
    schedule_config = config.schedule_config
    args = [config.id] if config.parameters is None else [config.id]
    kwargs = config.parameters or {}
    
    try:
        if config.scheduler_type == SchedulerType.INTERVAL:
            # 间隔任务 - 转换为时间点调度
            next_run = datetime.now() + timedelta(
                days=schedule_config.get("days", 0),
                hours=schedule_config.get("hours", 0),
                minutes=schedule_config.get("minutes", 0),
                seconds=schedule_config.get("seconds", 0),
            )
            await task_func.schedule_by_time(
                redis_schedule_source,
                next_run,
                *args,
                **kwargs
            )
        elif config.scheduler_type == SchedulerType.CRON:
            # Cron 任务
            cron_expression = schedule_config.get("cron_expression")
            if cron_expression:
                await task_func.schedule_by_cron(
                    redis_schedule_source,
                    cron_expression,
                    *args,
                    **kwargs
                )
        elif config.scheduler_type == SchedulerType.DATE:
            # 一次性任务
            run_date = datetime.fromisoformat(schedule_config.get("run_date"))
            await task_func.schedule_by_time(
                redis_schedule_source,
                run_date,
                *args,
                **kwargs
            )
    except Exception as e:
        print(f"Failed to register scheduled task {config.name}: {e}")


def get_task_function(task_type: TaskType):
    """根据任务类型获取任务函数"""
    # 动态导入避免循环导入
    from app.tasks import cleanup_tasks, notification_tasks, data_tasks
    
    task_mapping = {
        TaskType.CLEANUP_TOKENS: cleanup_tasks.cleanup_expired_tokens,
        TaskType.CLEANUP_CONTENT: cleanup_tasks.cleanup_old_content,
        TaskType.SEND_EMAIL: notification_tasks.send_email,
        TaskType.DATA_EXPORT: data_tasks.export_data,
        # 添加其他任务映射
    }
    return task_mapping.get(task_type)