"""
任务模块 - 导出所有Celery任务
"""

# 导入爬取相关任务
from .scraping_jobs import (
    execute_bot_scraping_task,
    manual_scraping_task,
    batch_scraping_task,
    auto_scraping_all_configs_task
)

# 导入清理相关任务
from .cleanup_jobs import (
    cleanup_old_sessions_task,
    cleanup_expired_tokens_task,
    cleanup_old_content_task,
    cleanup_schedule_events_task
)

# 导入共享工具
from .common import run_async_task, record_task_execution

__all__ = [
    # 爬取任务
    "execute_bot_scraping_task",
    "manual_scraping_task", 
    "batch_scraping_task",
    "auto_scraping_all_configs_task",
    
    # 清理任务
    "cleanup_old_sessions_task",
    "cleanup_expired_tokens_task",
    "cleanup_old_content_task", 
    "cleanup_schedule_events_task",
    
    # 共享工具
    "run_async_task",
    "record_task_execution"
]