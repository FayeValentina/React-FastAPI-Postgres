"""
TaskIQ Broker 配置
统一管理任务队列和调度器
"""
import uuid
import os
from typing import Optional
from taskiq import TaskiqEvents
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend

from app.core.config import settings
from app.core.redis_timeout_store import redis_timeout_store  # 导入Redis存储

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

# 配置任务事件监听器
@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def on_worker_startup(state: dict) -> None:
    """Worker 启动时的初始化"""
    # 连接Redis超时存储
    await redis_timeout_store.connect()


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def on_worker_shutdown(state: dict) -> None:
    """Worker 关闭时的清理"""
    # 断开Redis超时存储
    await redis_timeout_store.disconnect()