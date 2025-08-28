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

class CacheRedisService(RedisBase):
    """缓存Redis服务 - 简化版，配合装饰器使用"""
    
    def __init__(self):
        super().__init__(key_prefix="cache:")
        self.api_prefix = "api:"
        self.default_ttl = CacheConfig.DEFAULT_TTL
    
    # ========== 核心API缓存方法（供装饰器使用） ==========
    
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
    
    async def invalidate_api_cache_keys(self, cache_keys: List[str]) -> int:
        """根据精确的键列表批量清除API缓存 (使用 DEL)"""
        if not cache_keys:
            return 0
        # 注意：self.delete 方法内部会添加 key_prefix，所以这里只需要 api_prefix
        full_keys = [f"{self.api_prefix}{key}" for key in cache_keys]
        return await self.delete(*full_keys)

    async def invalidate_api_cache_pattern(self, pattern: str, scan_count: int = 500) -> int:
        """
        根据模式清除API缓存 (使用 SCAN 替代 KEYS，更安全)
        """
        # SCAN 需要完整的键模式，包括 key_prefix
        full_pattern = f"{self.key_prefix}{self.api_prefix}{pattern}"
        total_deleted = 0
        cursor = 0
        
        try:
            async with self._connection_manager.get_connection() as client:
                while True:
                    cursor, keys = await client.scan(cursor, match=full_pattern, count=scan_count)
                    if keys:
                        # 直接删除带前缀的键，不需要再添加前缀
                        deleted = await client.delete(*keys)
                        total_deleted += deleted
                    if cursor == 0:
                        break
            return total_deleted
        except Exception as e:
            logger.error(f"Redis scan pattern error (pattern={pattern}): {e}")
            return 0
    
    # ========== 缓存统计和管理 ==========
    
    async def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息 - 使用SCAN避免阻塞"""
        try:
            api_count = await self._scan_count_keys(f"{self.key_prefix}{self.api_prefix}*")
            total_count = await self._scan_count_keys(f"{self.key_prefix}*")
            
            return {
                "api_cache_count": api_count,
                "total_cache_count": total_count
            }
        except Exception as e:
            logger.warning(f"获取缓存统计失败: {e}")
            return {"api_cache_count": 0, "total_cache_count": 0}
    
    async def clear_all_cache(self) -> int:
        """清除所有缓存 - 使用SCAN分批删除（慎用）"""
        return await self._scan_delete_keys(f"{self.key_prefix}*")
    
    async def clear_api_cache(self) -> int:
        """清除所有API缓存 - 使用SCAN分批删除"""
        return await self._scan_delete_keys(f"{self.key_prefix}{self.api_prefix}*")
    
    # ========== 内部SCAN工具方法 ==========
    
    async def _scan_count_keys(self, pattern: str, scan_count: int = 1000) -> int:
        """使用SCAN统计匹配模式的键数量"""
        total_count = 0
        cursor = 0
        
        try:
            async with self._connection_manager.get_connection() as client:
                while True:
                    cursor, keys = await client.scan(cursor, match=pattern, count=scan_count)
                    total_count += len(keys)
                    if cursor == 0:
                        break
            return total_count
        except Exception as e:
            logger.error(f"Redis scan count error (pattern={pattern}): {e}")
            return 0
    
    async def _scan_delete_keys(self, pattern: str, scan_count: int = 500, batch_size: int = 100) -> int:
        """使用SCAN分批删除匹配模式的键"""
        total_deleted = 0
        cursor = 0
        keys_to_delete = []
        
        try:
            async with self._connection_manager.get_connection() as client:
                while True:
                    cursor, keys = await client.scan(cursor, match=pattern, count=scan_count)
                    
                    keys_to_delete.extend(keys)
                    
                    # 分批删除，避免单次删除过多键
                    while len(keys_to_delete) >= batch_size:
                        batch = keys_to_delete[:batch_size]
                        # 直接删除带前缀的键
                        deleted = await client.delete(*batch)
                        total_deleted += deleted
                        keys_to_delete = keys_to_delete[batch_size:]
                    
                    if cursor == 0:
                        break
                
                # 删除剩余的键
                if keys_to_delete:
                    deleted = await client.delete(*keys_to_delete)
                    total_deleted += deleted
                
            return total_deleted
        except Exception as e:
            logger.error(f"Redis scan delete error (pattern={pattern}): {e}")
            return 0