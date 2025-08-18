"""
TaskIQ Broker 配置
统一管理任务队列和调度器
"""
import uuid
import os
from typing import Optional
from taskiq import TaskiqEvents, TaskiqScheduler
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend

from app.core.config import settings
from app.core.redis_manager import redis_services

# 配置 RabbitMQ broker
broker = AioPikaBroker(
    url=settings.rabbitmq.URL,
).with_id_generator(
    lambda: str(uuid.uuid4())
).with_result_backend(
    RedisAsyncResultBackend(
        redis_url=settings.redis.CONNECTION_URL,
        result_ex_time=settings.taskiq.RESULT_EX_TIME,
    )
)

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        redis_services.scheduler.schedule_source,
    ],
)

# 配置任务事件监听器
@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def on_worker_startup(state: dict) -> None:
    """Worker 启动时的初始化"""
    # 注意：不再需要在这里连接Redis超时存储
    # Redis服务的初始化已经移到了main.py的lifespan中
    pass


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def on_worker_shutdown(state: dict) -> None:
    """Worker 关闭时的清理"""
    # 注意：不再需要在这里断开Redis超时存储
    # Redis服务的清理已经移到了main.py的lifespan中
    pass