"""
Redis连接池管理器
提供统一的Redis连接管理，支持上下文管理器和健康检查
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import redis.asyncio as redis
from redis import ConnectionError, TimeoutError

from app.core.config import settings
from .config import RedisPoolConfig, default_pool_config

logger = logging.getLogger(__name__)


class RedisConnectionManager:
    """Redis连接池管理器 - 单例模式"""
    
    _instance: Optional['RedisConnectionManager'] = None
    _pool: Optional[redis.Redis] = None
    _config: RedisPoolConfig = default_pool_config
    _last_health_check: Optional[datetime] = None
    _is_healthy: bool = True
    _health_check_lock: asyncio.Lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._health_check_lock = asyncio.Lock()
        return cls._instance
    
    async def initialize(self, config: Optional[RedisPoolConfig] = None) -> None:
        """初始化连接池"""
        if config:
            self._config = config
            
        if self._pool is None:
            try:
                # 简化Redis连接配置，移除可能有问题的参数
                self._pool = redis.from_url(
                    settings.redis.CONNECTION_URL,
                    max_connections=self._config.max_connections,
                    socket_connect_timeout=self._config.socket_connect_timeout,
                    socket_timeout=self._config.socket_timeout,
                    decode_responses=self._config.decode_responses,
                    encoding=self._config.encoding
                )
                
                # 测试连接
                await self._health_check()
                logger.info(f"Redis连接池已创建 (max_connections={self._config.max_connections})")
                
            except Exception as e:
                logger.error(f"Redis连接池创建失败: {e}")
                self._is_healthy = False
                raise
    
    async def get_client(self) -> redis.Redis:
        """获取Redis客户端"""
        if self._pool is None:
            await self.initialize()
        
        # 定期健康检查
        await self._periodic_health_check()
        
        if not self._is_healthy:
            raise ConnectionError("Redis连接不健康")
            
        return self._pool
    
    @asynccontextmanager
    async def get_connection(self):
        """上下文管理器方式获取连接"""
        client = None
        try:
            client = await self.get_client()
            yield client
        except Exception as e:
            logger.error(f"Redis连接错误: {e}")
            # 标记为不健康，触发重连
            self._is_healthy = False
            raise
        finally:
            # Redis连接池会自动管理连接，这里不需要手动关闭单个连接
            pass
    
    async def _health_check(self) -> bool:
        """执行健康检查"""
        try:
            if self._pool:
                # 使用ping命令检查连接
                try:
                    pong = await asyncio.wait_for(
                        self._pool.ping(),
                        timeout=self._config.health_check_timeout
                    )
                    
                    if pong:
                        self._is_healthy = True
                        self._last_health_check = datetime.utcnow()
                        return True
                except (asyncio.TimeoutError, OSError, ConnectionError, TimeoutError) as e:
                    logger.warning(f"Redis ping超时或连接错误: {e}")
                except Exception as e:
                    logger.warning(f"Redis ping未知错误: {e}")
                    
        except Exception as e:
            logger.warning(f"Redis健康检查失败: {e}")
            
        self._is_healthy = False
        return False
    
    async def _periodic_health_check(self) -> None:
        """定期健康检查"""
        now = datetime.utcnow()
        
        # 如果距离上次检查超过间隔时间，执行检查
        if (self._last_health_check is None or 
            now - self._last_health_check > timedelta(seconds=self._config.health_check_interval)):
            
            async with self._health_check_lock:
                # 双重检查，避免并发重复检查
                if (self._last_health_check is None or 
                    now - self._last_health_check > timedelta(seconds=self._config.health_check_interval)):
                    await self._health_check()
    
    async def get_pool_info(self) -> Dict[str, Any]:
        """获取连接池信息"""
        if not self._pool:
            return {"status": "not_initialized"}
            
        try:
            connection_pool = self._pool.connection_pool
            info = {
                "status": "healthy" if self._is_healthy else "unhealthy",
                "max_connections": self._config.max_connections,
                "created_connections": getattr(connection_pool, 'created_connections', 0),
                "available_connections": len(getattr(connection_pool, '_available_connections', [])),
                "in_use_connections": len(getattr(connection_pool, '_in_use_connections', {})),
                "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
                "config": {
                    "socket_timeout": self._config.socket_timeout,
                    "socket_connect_timeout": self._config.socket_connect_timeout,
                    "health_check_interval": self._config.health_check_interval
                }
            }
            return info
        except Exception as e:
            logger.error(f"获取连接池信息失败: {e}")
            return {"status": "error", "error": str(e)}
    
    async def reset_pool(self) -> None:
        """重置连接池"""
        logger.info("重置Redis连接池")
        await self.close()
        self._pool = None
        self._is_healthy = True
        self._last_health_check = None
        await self.initialize()
    
    async def close(self) -> None:
        """关闭连接池"""
        if self._pool:
            try:
                await self._pool.close()
                await self._pool.connection_pool.disconnect()
                logger.info("Redis连接池已关闭")
            except Exception as e:
                logger.error(f"关闭Redis连接池失败: {e}")
            finally:
                self._pool = None
                self._is_healthy = False
                self._last_health_check = None


# 全局连接管理器实例
redis_connection_manager = RedisConnectionManager()