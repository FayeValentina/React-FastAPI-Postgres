from celery import Celery
from kombu import Queue, Exchange

# 使用轻量级配置函数避免循环导入
from app.core.config import get_celery_config

# 获取 Celery 配置
celery_config = get_celery_config()

# 创建Celery应用实例
celery_app = Celery(
    "backend_worker",
    broker=celery_config['broker_url'],
    backend=celery_config['result_backend'],
    include=[
        'app.tasks.celery_tasks',
    ]
)

# Celery配置
celery_app.conf.update(
    # 任务序列化
    task_serializer=celery_config['task_serializer'],
    accept_content=celery_config['accept_content'],
    result_serializer=celery_config['result_serializer'],
    
    # 时区设置
    timezone=celery_config['timezone'],
    enable_utc=celery_config['enable_utc'],
    
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
    task_acks_late=celery_config['task_acks_late'],
    task_reject_on_worker_lost=celery_config['task_reject_on_worker_lost'],
    
    # 结果存储设置
    result_expires=celery_config['result_expires'],
    result_persistent=celery_config['result_persistent'],
    
    # Worker设置
    worker_prefetch_multiplier=celery_config['worker_prefetch_multiplier'],
    worker_max_tasks_per_child=celery_config['worker_max_tasks_per_child'],
    
    # 监控设置
    worker_send_task_events=celery_config['worker_send_task_events'],
    task_send_sent_event=celery_config['task_send_sent_event'],
    
    # 任务超时设置
    task_time_limit=celery_config['task_time_limit'],
    task_soft_time_limit=celery_config['task_soft_time_limit'],
    
    # 任务重试设置
    task_default_retry_delay=celery_config['task_default_retry_delay'],
    task_max_retries=celery_config['task_max_retries'],
)

# 任务自动发现
celery_app.autodiscover_tasks(['app.tasks'])

if __name__ == '__main__':
    celery_app.start()
