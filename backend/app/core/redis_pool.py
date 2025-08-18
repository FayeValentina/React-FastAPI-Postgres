# backend/app/core/redis_pool.py
"""
Redis连接池管理器
统一管理所有Redis连接，避免创建多个连接实例
"""
import redis.asyncio as redis
from typing import Optional, AsyncGenerator
import logging
from contextlib import asynccontextmanager
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisConnectionManager:
    """Redis连接池管理器 - 单例模式"""
    _instance: Optional['RedisConnectionManager'] = None
    _pool: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_client(self) -> redis.Redis:
        """获取Redis客户端（使用连接池）"""
        if self._pool is None:
            self._pool = redis.from_url(
                settings.redis.CONNECTION_URL,
                decode_responses=True,
                max_connections=50,  # 连接池大小
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            logger.info("Redis连接池已创建")
        return self._pool
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[redis.Redis, None]:
        """上下文管理器方式获取Redis连接"""
        client = await self.get_client()
        try:
            yield client
        except Exception as e:
            logger.error(f"Redis连接操作失败: {e}")
            raise
        finally:
            # Redis连接池会自动管理连接回收，这里不需要手动关闭
            pass
    
    async def close(self):
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            await self._pool.connection_pool.disconnect()
            self._pool = None
            logger.info("Redis连接池已关闭")

# 全局连接管理器实例
redis_connection_manager = RedisConnectionManager()