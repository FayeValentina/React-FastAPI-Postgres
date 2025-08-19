# backend/app/redis/cache.py
from typing import Optional, Dict, Any, List
from app.core.redis import RedisBase

class CacheRedisService(RedisBase):
    """缓存Redis服务 - 使用新的连接池架构"""
    
    def __init__(self):
        super().__init__(key_prefix="cache:")
        self.user_prefix = "user:"
        self.api_prefix = "api:"
        self.session_prefix = "session:"
        self.default_ttl = 300  # 5分钟
        self.long_ttl = 3600   # 1小时
    
    # ========== 用户缓存 ==========
    
    async def get_user_cache(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取用户缓存"""
        return await self.get_json(f"{self.user_prefix}{user_id}")
    
    async def set_user_cache(self, user_id: int, user_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """设置用户缓存"""
        return await self.set_json(
            f"{self.user_prefix}{user_id}",
            user_data,
            ttl=ttl or self.default_ttl
        )
    
    async def invalidate_user_cache(self, user_id: int) -> bool:
        """清除用户缓存"""
        return await self.delete(f"{self.user_prefix}{user_id}") > 0
    
    async def invalidate_all_user_caches(self) -> int:
        """清除所有用户缓存"""
        user_keys = await self.keys(f"{self.user_prefix}*")
        if user_keys:
            return await self.delete(*user_keys)
        return 0
    
    # ========== API缓存 ==========
    
    async def get_api_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取API缓存"""
        return await self.get_json(f"{self.api_prefix}{cache_key}")
    
    async def set_api_cache(self, cache_key: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """设置API缓存"""
        return await self.set_json(
            f"{self.api_prefix}{cache_key}",
            data,
            ttl=ttl or self.default_ttl
        )
    
    async def invalidate_api_cache(self, cache_key: str) -> bool:
        """清除API缓存"""
        return await self.delete(f"{self.api_prefix}{cache_key}") > 0
    
    async def invalidate_api_cache_pattern(self, pattern: str) -> int:
        """根据模式清除API缓存"""
        api_keys = await self.keys(f"{self.api_prefix}{pattern}")
        if api_keys:
            return await self.delete(*api_keys)
        return 0
    
    # ========== 会话缓存 ==========
    
    async def get_session_cache(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话缓存"""
        return await self.get_json(f"{self.session_prefix}{session_id}")
    
    async def set_session_cache(self, session_id: str, session_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """设置会话缓存"""
        return await self.set_json(
            f"{self.session_prefix}{session_id}",
            session_data,
            ttl=ttl or self.long_ttl
        )
    
    async def invalidate_session_cache(self, session_id: str) -> bool:
        """清除会话缓存"""
        return await self.delete(f"{self.session_prefix}{session_id}") > 0
    
    # ========== 通用缓存方法 ==========
    
    async def get_cache(self, key: str) -> Optional[str]:
        """获取通用缓存"""
        return await self.get(key)
    
    async def set_cache(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """设置通用缓存"""
        return await self.set(key, value, ttl or self.default_ttl)
    
    async def get_cache_json(self, key: str) -> Optional[Dict[str, Any]]:
        """获取JSON缓存"""
        return await self.get_json(key)
    
    async def set_cache_json(self, key: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """设置JSON缓存"""
        return await self.set_json(key, data, ttl or self.default_ttl)
    
    # ========== 批量操作 ==========
    
    async def mget_cache(self, keys: List[str]) -> List[Optional[str]]:
        """批量获取缓存"""
        try:
            async with self._connection_manager.get_connection() as client:
                prefixed_keys = [self._make_key(key) for key in keys]
                results = await client.mget(prefixed_keys)
                return results
        except Exception:
            return [None] * len(keys)
    
    async def mset_cache(self, mapping: Dict[str, str], ttl: Optional[int] = None) -> bool:
        """批量设置缓存"""
        if not mapping:
            return True
            
        operations = []
        for key, value in mapping.items():
            operations.append({
                "method": "set",
                "args": [key, value],
                "kwargs": {"ex": ttl or self.default_ttl}
            })
        
        results = await self.pipeline_execute(operations)
        return len(results) == len(mapping) and all(results)
    
    # ========== 缓存统计 ==========
    
    async def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        try:
            user_keys = await self.keys(f"{self.user_prefix}*")
            api_keys = await self.keys(f"{self.api_prefix}*")
            session_keys = await self.keys(f"{self.session_prefix}*")
            
            return {
                "user_cache_count": len(user_keys),
                "api_cache_count": len(api_keys), 
                "session_cache_count": len(session_keys),
                "total_cache_count": len(user_keys) + len(api_keys) + len(session_keys)
            }
        except Exception:
            return {"user_cache_count": 0, "api_cache_count": 0, "session_cache_count": 0, "total_cache_count": 0}
    
    async def clear_all_cache(self) -> int:
        """清除所有缓存（慎用）"""
        all_keys = await self.keys("*")
        if all_keys:
            return await self.delete(*all_keys)
        return 0