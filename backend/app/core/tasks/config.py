"""
任务配置相关的数据类和配置
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class TaskExecutionConfig:
    """任务执行配置"""
    max_retries: int = 3
    timeout_seconds: Optional[int] = None
    queue: str = "default"
    priority: int = 5
    
    
@dataclass
class TaskSystemConfig:
    """任务系统配置"""
    enable_monitoring: bool = True
    enable_history: bool = True
    history_retention_days: int = 30
    max_concurrent_tasks: int = 100
    

# 默认配置实例
default_execution_config = TaskExecutionConfig()
default_system_config = TaskSystemConfig()