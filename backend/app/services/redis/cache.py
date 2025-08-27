from typing import Optional, Dict, Any, List
from app.core.redis import RedisBase

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
    
    async def invalidate_api_cache(self, cache_key: str) -> bool:
        """清除API缓存"""
        return await self.delete(f"{self.api_prefix}{cache_key}") > 0
    
    async def invalidate_api_cache_pattern(self, pattern: str) -> int:
        """根据模式清除API缓存"""
        api_keys = await self.keys(f"{self.api_prefix}{pattern}")
        if api_keys:
            return await self.delete(*api_keys)
        return 0
    
    # ========== 缓存统计和管理 ==========
    
    async def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        try:
            api_keys = await self.keys(f"{self.api_prefix}*")
            all_cache_keys = await self.keys("*")
            
            return {
                "api_cache_count": len(api_keys),
                "total_cache_count": len(all_cache_keys)
            }
        except Exception:
            return {"api_cache_count": 0, "total_cache_count": 0}
    
    async def clear_all_cache(self) -> int:
        """清除所有缓存（慎用）"""
        all_keys = await self.keys("*")
        if all_keys:
            return await self.delete(*all_keys)
        return 0