# backend/app/services/redis/cache.py (适配 v4.0 装饰器的最终版)

import logging
from typing import Optional, Dict, Any, List
from app.core.redis import RedisBase

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
    
    # 标签集合的TTL (24小时，比缓存项TTL更长)
    TAG_TTL = 86400  # 24 * 60 * 60

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
    
    # ========== 标签化缓存新方法 ==========
    
    async def get_binary_data(self, cache_key: str) -> Optional[bytes]:
        """获取二进制缓存数据"""
        try:
            data = await self.get(cache_key)
            if data is None:
                return None
            
            # 如果Redis客户端返回bytes，直接返回
            if isinstance(data, bytes):
                return data
            
            # 如果返回str，编码为bytes（兼容性处理）
            if isinstance(data, str):
                return data.encode('utf-8')
                
            return None
        except Exception as e:
            logger.error(f"获取二进制缓存失败 (key={cache_key}): {e}")
            return None
    
    async def set_binary_data(self, cache_key: str, data: bytes, ttl: Optional[int] = None) -> bool:
        """设置二进制缓存数据"""
        try:
            # 直接存储bytes数据，让Redis客户端处理
            return await self.set(cache_key, data, ttl)
        except Exception as e:
            logger.error(f"设置二进制缓存失败 (key={cache_key}): {e}")
            return False
    
    async def add_key_to_tag(self, tag: str, cache_key: str) -> bool:
        """将缓存键关联到标签，并为标签集合续期"""
        try:
            tag_set_key = f"tag:{tag}"
            # 简单的连续操作，Redis处理极快，风险很低
            result = await self.sadd(tag_set_key, cache_key)
            # 为标签集合设置过期时间，防止内存泄漏
            await self.expire(tag_set_key, CacheConfig.TAG_TTL)
            return result > 0
        except Exception as e:
            logger.error(f"添加键到标签失败 (tag={tag}, key={cache_key}): {e}")
            return False
    
    async def invalidate_by_tag(self, tag: str) -> int:
        """根据标签失效所有相关缓存"""
        try:
            tag_set_key = f"tag:{tag}"
            
            # 获取标签下的所有缓存键 (可能返回 bytes)
            cache_keys_raw = await self.smembers(tag_set_key)
            if not cache_keys_raw:
                return 0
            
            # ⭐ 核心修复：将 bytes 解码为 str
            cache_keys = [key.decode('utf-8') if isinstance(key, bytes) else key for key in cache_keys_raw]
            
            # 删除所有关联的缓存键
            deleted_count = 0
            if cache_keys:
                deleted_count = await self.delete(*cache_keys)
                # 清理标签集合
                await self.delete(tag_set_key)
            
            logger.info(f"标签 {tag} 失效了 {deleted_count} 个缓存键")
            return deleted_count
            
        except Exception as e:
            logger.error(f"根据标签失效缓存失败 (tag={tag}): {e}")
            return 0
