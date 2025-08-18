# backend/app/services/cache_redis.py
from typing import Optional, Dict, Any
from app.core.redis_core import RedisBase

class CacheRedisService(RedisBase):
    """用户缓存Redis服务"""
    
    def __init__(self):
        super().__init__()
        self.user_prefix = "cache:user:"
        self.default_ttl = 300  # 5分钟
    
    async def get_user_cache(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取用户缓存"""
        return await self.get_json(f"{self.user_prefix}{user_id}")
    
    async def set_user_cache(self, user_id: int, user_data: Dict[str, Any]) -> bool:
        """设置用户缓存"""
        return await self.set_json(
            f"{self.user_prefix}{user_id}",
            user_data,
            ttl=self.default_ttl
        )
    
    async def invalidate_user_cache(self, user_id: int) -> bool:
        """清除用户缓存"""
        return await self.delete(f"{self.user_prefix}{user_id}")