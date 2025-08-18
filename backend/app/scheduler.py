# backend/app/scheduler.py
"""
TaskIQ Scheduler 配置
使用Redis服务管理器中的调度器
"""
import logging
from taskiq import TaskiqScheduler

from app.broker import broker
from app.core.redis_manager import redis_services

logger = logging.getLogger(__name__)

# 创建调度器，使用Redis服务管理器中的调度源
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        redis_services.scheduler.schedule_source,
    ],
)

# 导出简化的接口函数
async def register_scheduled_task(config):
    """注册调度任务"""
    return await redis_services.scheduler.register_task(config)

async def unregister_scheduled_task(config_id):
    """取消注册调度任务"""
    return await redis_services.scheduler.unregister_task(config_id)

async def update_scheduled_task(config):
    """更新调度任务"""
    return await redis_services.scheduler.update_task(config)

async def get_scheduled_tasks():
    """获取所有调度任务"""
    return await redis_services.scheduler.get_all_schedules()

async def pause_scheduled_task(config_id):
    """暂停调度任务"""
    return await redis_services.scheduler.pause_task(config_id)

async def resume_scheduled_task(config):
    """恢复调度任务"""
    return await redis_services.scheduler.resume_task(config)

async def initialize_scheduler():
    """初始化调度器"""
    await redis_services.scheduler.initialize()

async def shutdown_scheduler():
    """关闭调度器"""
    await redis_services.scheduler.shutdown()