# 缓存 Redis 服务（配合基于标签的缓存装饰器使用）

import logging
from typing import Optional, Dict, Any, List
from app.infrastructure.redis.redis_base import RedisBase
from app.infrastructure.redis.keyspace import redis_keys
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
    缓存Redis服务（轻量封装）。
    复杂的缓存键生成逻辑位于 cache_decorators.py 中的 _generate_cache_key。
    """
    
    def __init__(self):
        # 这个服务只负责为所有缓存键添加 "cache:" 命名空间。
        super().__init__(key_prefix="cache:")
    
    # ========== 标签化缓存新方法 ==========
    
    async def get_binary_data(self, cache_key: str) -> Optional[str]:
        """获取缓存数据（decode_responses=True 环境下返回 str）"""
        try:
            data = await self.get(cache_key)
            if data is None:
                return None
            # 连接池 decode_responses=True，直接返回 str
            if isinstance(data, (str, bytes)):
                # 若底层返回 bytes（罕见），也统一解码
                return data.decode('utf-8') if isinstance(data, bytes) else data
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
            tag_set_key = redis_keys.cache.tag(tag)
            # 直接使用新的上下文管理器
            async with self.pipeline() as pipe:
            # ！！！注意：在 pipeline 中，命令不会立即执行，而是被添加到队列中
            # ！！！所以这里不需要 await
                pipe.sadd(self._make_key(tag_set_key), cache_key)
                pipe.expire(self._make_key(tag_set_key), CacheConfig.TAG_TTL)

                await pipe.execute()
            # 幂等语义：只要执行成功（无异常），即视为确保已关联
            return True
        except Exception as e:
            logger.error(f"添加键到标签失败 (tag={tag}, key={cache_key}): {e}")
            return False
    
    async def invalidate_by_tag(self, tag: str) -> int:
        """根据标签失效所有相关缓存"""
        try:

            tag_set_key = redis_keys.cache.tag(tag)
            
            # 获取标签下的所有缓存键（decode_responses=True 下为 str 集合）
            cache_keys = await self.smembers(tag_set_key)
            if not cache_keys:
                return 0
            
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


# 全局实例和依赖提供函数
cache_redis_service = CacheRedisService()
