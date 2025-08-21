"""
任务核心模块 - 重构后的架构
提供任务服务的基础设施
"""
from .registry import (
    # 注册系统
    task, get_worker_name, get_queue, get_function, all_queues, is_supported,
    make_job_id, extract_config_id, auto_discover_tasks,
    # 枚举（已删除ConfigStatus和ExecutionStatus）
    SchedulerType, ScheduleAction,
    # 全局注册表
    TASKS
)
from .decorators import execution_handler, create_execution_record
__all__ = [
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
    
    # 枚举（保留）
    'SchedulerType',
    'ScheduleAction',
    
    'execution_handler',
    'create_execution_record',
]