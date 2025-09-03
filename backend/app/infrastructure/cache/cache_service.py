# backend/app/services/redis/cache.py (适配 v4.0 装饰器的最终版)

import logging
from typing import Optional, Dict, Any, List
from app.infrastructure.database.redis_base import RedisBase

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
            # 直接使用新的上下文管理器
            async with self.pipeline() as pipe:
            # ！！！注意：在 pipeline 中，命令不会立即执行，而是被添加到队列中
            # ！！！所以这里不需要 await
                pipe.sadd(self._make_key(tag_set_key), cache_key)
                pipe.expire(self._make_key(tag_set_key), CacheConfig.TAG_TTL)

                result = await pipe.execute()
            return result[0] > 0
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
