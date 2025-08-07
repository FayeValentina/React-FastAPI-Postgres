"""
Tasks package - 重构后的任务管理系统
包含核心组件、调度器、发送器和任务定义
"""
# 核心组件
from app.core import scheduler, event_recorder, job_config_manager, task_dispatcher

# 任务定义
from . import (
    execute_bot_scraping_task,
    manual_scraping_task,
    batch_scraping_task,
    cleanup_old_sessions_task,
    auto_scraping_all_configs_task
)

__all__ = [
    # 核心组件
    "task_dispatcher", 
    "event_recorder",
    "job_config_manager",
    "scheduler", 
    # 任务定义
    "execute_bot_scraping_task",
    "manual_scraping_task", 
    "batch_scraping_task",
    "cleanup_old_sessions_task",
    "auto_scraping_all_configs_task"
]