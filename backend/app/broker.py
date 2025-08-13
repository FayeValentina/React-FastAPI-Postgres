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


# 配置 RabbitMQ broker
broker = AioPikaBroker(
    url=settings.rabbitmq.URL,
).with_id_generator(lambda: str(uuid.uuid4()))

# 配置 Redis 作为结果后端
broker = broker.with_result_backend(
    RedisAsyncResultBackend(
        redis_url=settings.redis.CONNECTION_URL,
        result_ex_time=settings.taskiq.RESULT_EX_TIME,  # 结果过期时间（秒）
    )
)


# 配置任务事件监听器
@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def on_worker_startup(state: dict) -> None:
    """Worker 启动时的初始化"""
    # 初始化数据库连接等
    pass


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def on_worker_shutdown(state: dict) -> None:
    """Worker 关闭时的清理"""
    # 关闭数据库连接等
    pass