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
).with_id_generator(
    lambda: str(uuid.uuid4())
).with_result_backend(
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
    # 启动超时监控器
    from app.core.timeout_monitor_engine import timeout_monitor
    await timeout_monitor.start_monitor()


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def on_worker_shutdown(state: dict) -> None:
    """Worker 关闭时的清理"""
    # 关闭超时监控器
    from app.core.timeout_monitor_engine import timeout_monitor
    await timeout_monitor.stop_monitor()
    # 关闭数据库连接等


# 注意：TaskIQ 0.11.x 版本只有 WORKER_STARTUP, WORKER_SHUTDOWN, CLIENT_STARTUP, CLIENT_SHUTDOWN 事件
# 没有任务级别的事件如 TASK_START, TASK_SUCCESS, TASK_ERROR
# 任务状态更新需要在任务内部或通过其他机制处理