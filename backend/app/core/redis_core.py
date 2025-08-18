import logging
import redis.asyncio as redis
import json
from typing import Any, Dict, Optional
from app.core.redis_pool import redis_connection_manager

logger = logging.getLogger(__name__)

class RedisBase:
    """Redis服务基类，使用共享连接池"""
    
    async def get_client(self):
        """获取Redis客户端，使用共享连接池"""
        return await redis_connection_manager.get_client()
    
    async def close(self):
        """关闭连接（实际上不需要关闭，因为使用共享池）"""
        # 不再需要关闭单个连接
        pass
    
    async def set_json(self, key: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """存储JSON数据"""
        try:
            async with redis_connection_manager.get_connection() as client:
                result = await client.set(key, json.dumps(data), ex=ttl)
                return result is True
        except Exception as e:
            logger.error(f"Redis set_json error: {e}")
            return False
    
    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """获取JSON数据"""
        try:
            async with redis_connection_manager.get_connection() as client:
                data = await client.get(key)
                return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Redis get_json error: {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        """删除键"""
        try:
            async with redis_connection_manager.get_connection() as client:
                result = await client.delete(key)
                return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False