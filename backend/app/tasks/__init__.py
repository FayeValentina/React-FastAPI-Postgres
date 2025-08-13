"""
TaskIQ 任务定义
所有异步任务都在这里定义
"""
from app.broker import broker

# 导入所有任务模块
from app.tasks import cleanup_tasks
from app.tasks import notification_tasks
from app.tasks import data_tasks

__all__ = [
    "cleanup_tasks",
    "notification_tasks", 
    "data_tasks",
]