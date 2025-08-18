import redis.asyncio as redis
import json
from typing import Any, Dict, Optional
from app.core.config import settings

class RedisBase:
    """Redis服务基类，复用现有配置"""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
    
    async def get_client(self) -> redis.Redis:
        """获取Redis客户端，复用现有配置"""
        if not self._client:
            self._client = redis.from_url(
                settings.redis.CONNECTION_URL,
                decode_responses=True,
                max_connections=10
            )
        return self._client
    
    async def close(self):
        """关闭Redis连接"""
        if self._client:
            await self._client.close()
            self._client = None
    
    async def set_json(self, key: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """存储JSON数据"""
        client = await self.get_client()
        try:
            result = await client.set(key, json.dumps(data), ex=ttl)
            return result is True
        except Exception:
            return False
    
    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """获取JSON数据"""
        client = await self.get_client()
        try:
            data = await client.get(key)
            return json.loads(data) if data else None
        except Exception:
            return None
    
    async def delete(self, key: str) -> bool:
        """删除键"""
        client = await self.get_client()
        try:
            result = await client.delete(key)
            return result > 0
        except Exception:
            return False