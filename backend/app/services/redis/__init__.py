# backend/app/services/redis/__init__.py
"""
Redis服务模块 - 重构后的架构
提供各种Redis相关的服务实现
"""

from .auth import AuthRedisService
from .cache import CacheRedisService
from .history import ScheduleHistoryRedisService  # 增强版，包含状态管理
from .scheduler_core import SchedulerCoreService
from .scheduler import SchedulerService, scheduler_service

__all__ = [
    'AuthRedisService',
    'CacheRedisService', 
    'ScheduleHistoryRedisService',  # 统一的状态和历史服务，消除重叠
    'SchedulerCoreService',
    'SchedulerService',
    'scheduler_service'
]