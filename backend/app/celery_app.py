from celery import Celery
from kombu import Queue, Exchange

from app.core.config import settings

# 导入 Worker 初始化钩子（重要！）
import app.tasks.worker_init  # 这会注册信号处理器

# 创建Celery应用实例
celery_app = Celery(
    "backend_worker",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend_url,
    include=[
        'app.tasks.cleanup_jobs',
    ]
)

# Celery配置
celery_app.conf.update(
    # 任务序列化
    task_serializer=settings.celery.TASK_SERIALIZER,
    accept_content=settings.celery.ACCEPT_CONTENT,
    result_serializer=settings.celery.RESULT_SERIALIZER,
    
    # 时区设置
    timezone=settings.celery.TIMEZONE,
    enable_utc=settings.celery.ENABLE_UTC,
    
    # 任务路由和队列
    task_routes={
        'app.tasks.cleanup_jobs.cleanup_expired_tokens_task': {'queue': 'cleanup'},
        'app.tasks.cleanup_jobs.cleanup_old_content_task': {'queue': 'cleanup'},
        'app.tasks.cleanup_jobs.cleanup_schedule_events_task': {'queue': 'cleanup'},
    },
    
    # 队列定义
    task_queues=(
        Queue('default', Exchange('default'), routing_key='default'),
        Queue('scraping', Exchange('scraping'), routing_key='scraping'),
        Queue('cleanup', Exchange('cleanup'), routing_key='cleanup'),
    ),
    
    # 任务重试设置
    task_acks_late=settings.celery.TASK_ACKS_LATE,
    task_reject_on_worker_lost=settings.celery.TASK_REJECT_ON_WORKER_LOST,
    
    # 结果存储设置
    result_expires=settings.celery.RESULT_EXPIRES,
    result_persistent=settings.celery.RESULT_PERSISTENT,
    
    # Worker设置 - 重要配置
    worker_prefetch_multiplier=settings.celery.WORKER_PREFETCH_MULTIPLIER,
    worker_max_tasks_per_child=settings.celery.WORKER_MAX_TASKS_PER_CHILD,
    
    # 添加 Worker 池配置
    worker_pool=settings.celery.WORKER_POOL,  # 从配置读取 worker 池类型
    worker_concurrency=settings.celery.WORKER_CONCURRENCY,  # 从配置读取并发数
    
    # 监控设置
    worker_send_task_events=settings.celery.WORKER_SEND_TASK_EVENTS,
    task_send_sent_event=settings.celery.TASK_SEND_SENT_EVENT,
    
    # 任务超时设置
    task_time_limit=settings.celery.TASK_TIME_LIMIT,
    task_soft_time_limit=settings.celery.TASK_SOFT_TIME_LIMIT,
    
    # 任务重试设置
    task_default_retry_delay=settings.celery.TASK_DEFAULT_RETRY_DELAY,
    task_max_retries=settings.celery.TASK_MAX_RETRIES,
)

# 任务自动发现
celery_app.autodiscover_tasks(['app.tasks'])

if __name__ == '__main__':
    celery_app.start()
