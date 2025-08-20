"""
任务核心模块
提供任务服务的基础设施
"""

# from .base import TaskServiceBase  # 避免循环导入，需要时直接导入
from .config import TaskExecutionConfig, TaskSystemConfig, default_execution_config, default_system_config
from .executor import TaskExecutor
from .registry import (
    # 注册系统
    task, get_worker_name, get_queue, get_function, all_queues, is_supported,
    make_job_id, extract_config_id, auto_discover_tasks,
    # 枚举
    ConfigStatus, SchedulerType, ScheduleAction, ExecutionStatus,
    # 全局注册表
    TASKS
)
from .decorators import with_timeout_handling
__all__ = [
    # 'TaskServiceBase',  # 避免循环导入
    'TaskExecutionConfig',
    'TaskSystemConfig',
    'default_execution_config',
    'default_system_config',
    'TaskExecutor',
    
    'task',
    'get_worker_name',
    'get_queue',
    'get_function',
    'all_queues',
    'is_supported',
    'make_job_id',
    'extract_config_id',
    'auto_discover_tasks',
    'TASKS',
    
    # 枚举
    'ConfigStatus',
    'SchedulerType',
    'ScheduleAction',
    'ExecutionStatus',
    
    'with_timeout_handling',
]