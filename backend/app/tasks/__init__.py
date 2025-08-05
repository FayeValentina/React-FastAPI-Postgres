"""
Tasks package - 重构后的任务管理系统
包含核心组件、调度器、发送器和任务定义
"""
# 核心组件
from .core import TaskDispatcher, EventRecorder, JobConfigManager

# 调度器
from .schedulers import HybridScheduler, scheduler

# 发送器  
from .senders import MessageSender

# 任务定义
from .jobs import (
    execute_bot_scraping_task,
    manual_scraping_task,
    batch_scraping_task,
    cleanup_old_sessions_task,
    auto_scraping_all_configs_task
)

__all__ = [
    # 核心组件
    "TaskDispatcher",
    "EventRecorder", 
    "JobConfigManager",
    # 调度器
    "HybridScheduler",
    "scheduler", 
    # 发送器
    "MessageSender",
    # 任务定义
    "execute_bot_scraping_task",
    "manual_scraping_task", 
    "batch_scraping_task",
    "cleanup_old_sessions_task",
    "auto_scraping_all_configs_task"
]