"""
Redis核心模块
提供统一的Redis连接管理和基础操作
"""

from .pool import redis_connection_manager, RedisConnectionManager
from .config import RedisPoolConfig, default_pool_config
from .base import RedisBase

__all__ = [
    'redis_connection_manager',
    'RedisConnectionManager', 
    'RedisPoolConfig',
    'default_pool_config',
    'RedisBase'
]