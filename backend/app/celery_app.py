from celery import Celery
from kombu import Queue, Exchange
from app.core.celery_config import celery_config

# 创建Celery应用实例
celery_app = Celery(
    "backend_worker",
    broker=celery_config.broker_url,
    backend=celery_config.result_backend,
    include=[
        'app.tasks.celery_tasks',
    ]
)

# Celery配置
celery_app.conf.update(
    # 任务序列化
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # 时区设置
    timezone='UTC',
    enable_utc=True,
    
    # 任务路由和队列
    task_routes={
        'app.tasks.celery_tasks.execute_bot_scraping_task': {'queue': 'scraping'},
        'app.tasks.celery_tasks.cleanup_old_sessions_task': {'queue': 'cleanup'},
        'app.tasks.celery_tasks.batch_scraping_task': {'queue': 'scraping'},
    },
    
    # 队列定义
    task_queues=(
        Queue('default', Exchange('default'), routing_key='default'),
        Queue('scraping', Exchange('scraping'), routing_key='scraping'),
        Queue('cleanup', Exchange('cleanup'), routing_key='cleanup'),
    ),
    
    # 任务重试设置
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # 结果存储设置
    result_expires=3600 * 24,  # 结果保留24小时
    result_persistent=True,
    
    # Worker设置
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # 监控设置
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # 任务超时设置
    task_time_limit=30 * 60,  # 硬超时30分钟
    task_soft_time_limit=25 * 60,  # 软超时25分钟
    
    # 任务重试设置
    task_default_retry_delay=60,  # 默认重试延迟60秒
    task_max_retries=3,  # 默认最大重试3次
)

# 任务自动发现
celery_app.autodiscover_tasks(['app.tasks'])

if __name__ == '__main__':
    celery_app.start()
