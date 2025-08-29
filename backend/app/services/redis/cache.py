# backend/app/services/redis/cache.py (适配 v4.0 装饰器的最终版)

import logging
from typing import Optional, Dict, Any, List, Iterable
from app.core.redis import RedisBase
from app.constant.cache_tags import CacheTags

logger = logging.getLogger(__name__)

class CacheConfig:
    """缓存配置常量 - 与装饰器共享"""
    # 基础TTL配置
    DEFAULT_TTL = 300           # 5分钟 - 默认
    SHORT_TTL = 60              # 1分钟 - 实时数据
    MEDIUM_TTL = 300            # 5分钟 - 半实时数据
    LONG_TTL = 1800             # 30分钟 - 相对静态数据
    STATIC_TTL = 3600           # 1小时 - 静态数据
    
    # 特定类型TTL
    USER_CACHE_TTL = 300        # 用户信息
    API_LIST_TTL = 180          # API列表数据
    STATS_CACHE_TTL = 600       # 统计数据
    SYSTEM_INFO_TTL = 1800      # 系统信息
    ENUM_CACHE_TTL = 3600       # 枚举值


class CacheRedisService(RedisBase):
    """
    缓存Redis服务 - v4.0 简化版
    该服务现在是一个轻量级封装，所有复杂的Key生成逻辑都已移至 cache_decorators.py 中的 CacheKeyFactory。
    """
    
    def __init__(self):
        # 这个服务只负责为所有缓存键添加 "cache:" 命名空间。
        super().__init__(key_prefix="cache:")
        self.default_ttl = CacheConfig.DEFAULT_TTL
    
    # ========== 核心API缓存方法（供装饰器使用） ==========
    
    async def get_api_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        获取API缓存。
        cache_key 是由 CacheKeyFactory 生成的完整键。
        """
        # 直接使用 cache_key，self.get_json 会自动添加 "cache:" 前缀。
        return await self.get_json(cache_key)
    
    async def set_api_cache(self, cache_key: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        设置API缓存。
        cache_key 是由 CacheKeyFactory 生成的完整键。
        """
        # 直接使用 cache_key，self.set_json 会自动添加 "cache:" 前缀。
        return await self.set_json(
            cache_key,
            data,
            ttl=ttl or self.default_ttl
        )
    
    async def invalidate_api_cache_keys(self, cache_keys: List[str]) -> int:
        """
        根据精确的键列表批量清除API缓存 (使用 DEL)。
        cache_keys 是由 CacheKeyFactory 生成的完整键列表。
        """
        if not cache_keys:
            return 0
        # self.delete 会自动为列表中的每个key添加 "cache:" 前缀。
        return await self.delete(*cache_keys)

    async def invalidate_api_cache_pattern(self, pattern: str) -> int:
        """
        根据模式清除API缓存 (使用 SCAN 和 DEL，非阻塞)。
        pattern 是由装饰器生成的模式，例如 "user_list*"。
        """
        if not pattern:
            return 0
        # self.scan_delete 会自动为 pattern 添加 "cache:" 前缀。
        return await self.scan_delete(pattern)

    # ========== Tag-based caching for v2 decorators ==========

    def _tag_key(self, tag_name: str) -> str:
        return f"tag:{tag_name}"

    async def get_cache(self, cache_key: str) -> Optional[bytes]:
        """Retrieve raw cached bytes by key."""
        try:
            async with self._connection_manager.get_connection() as client:
                return await client.get(self._make_key(cache_key))
        except Exception as e:
            logger.error(f"Redis get_cache error (key={cache_key}): {e}")
            return None

    async def set_cache(
        self,
        cache_key: str,
        data: bytes,
        tags: Iterable[str | CacheTags],
        ttl: Optional[int] = None,
    ) -> bool:
        """Store cache entry and record its key under provided tags."""
        ttl_value = ttl or self.default_ttl
        try:
            async with self._connection_manager.get_connection() as client:
                await client.set(self._make_key(cache_key), data, ex=ttl_value)
                for tag in tags:
                    tag_name = tag.value if isinstance(tag, CacheTags) else str(tag)
                    tag_key = self._make_key(self._tag_key(tag_name))
                    await client.sadd(tag_key, cache_key)
                    await client.expire(tag_key, ttl_value)
            return True
        except Exception as e:
            logger.error(f"Redis set_cache error (key={cache_key}): {e}")
            return False

    async def invalidate_tags(self, tags: Iterable[str | CacheTags]) -> int:
        """Invalidate all cache entries associated with the given tags."""
        keys_to_delete = set()
        try:
            async with self._connection_manager.get_connection() as client:
                for tag in tags:
                    tag_name = tag.value if isinstance(tag, CacheTags) else str(tag)
                    tag_key = self._make_key(f"tag:{tag_name}")
                    members = await client.smembers(tag_key)
                    if members:
                        keys_to_delete.update(members)
                    await client.delete(tag_key)
                if keys_to_delete:
                    delete_keys = [
                        self._make_key(k.decode() if isinstance(k, bytes) else k)
                        for k in keys_to_delete
                    ]
                    return await client.delete(*delete_keys)
            return 0
        except Exception as e:
            logger.error(f"Redis invalidate_tags error (tags={tags}): {e}")
            return 0
