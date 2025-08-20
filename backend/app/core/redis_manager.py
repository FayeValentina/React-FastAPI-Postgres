# backend/app/core/redis_manager.py
"""
Redis服务管理器 - 使用新的连接池架构
"""
import logging
from typing import Dict, Any
from app.implementation.redis import (
    AuthRedisService,
    CacheRedisService, 
    ScheduleHistoryRedisService,
    SchedulerRedisService
)
from app.core.redis import redis_connection_manager

logger = logging.getLogger(__name__)


class RedisServiceManager:
    """Redis服务管理器 - 使用共享连接池"""
    
    def __init__(self):
        self.auth = AuthRedisService()
        self.cache = CacheRedisService()
        self.history = ScheduleHistoryRedisService()
        self.scheduler = SchedulerRedisService()
        self._connection_manager = redis_connection_manager
        self._initialized = False
    
    async def initialize(self):
        """初始化所有服务"""
        if self._initialized:
            return
            
        try:
            # 初始化连接池
            await self._connection_manager.initialize()
            
            # 确保所有服务连接正常
            await self.auth.ensure_connection()
            await self.cache.ensure_connection()
            await self.history.ensure_connection()
            
            # 初始化调度器
            await self.scheduler.initialize()
            
            self._initialized = True
            logger.info("Redis服务管理器初始化成功")
            
        except Exception as e:
            logger.error(f"Redis服务管理器初始化失败: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health_status = {
            "connection_pool": "unknown",
            "auth_service": "unknown", 
            "cache_service": "unknown",
            "history_service": "unknown",
            "scheduler_service": "unknown",
            "overall": "unknown"
        }
        
        try:
            # 检查连接池
            pool_info = await self._connection_manager.get_pool_info()
            health_status["connection_pool"] = pool_info.get("status", "unknown")
            
            # 检查各个服务
            auth_ok = await self.auth.ping()
            health_status["auth_service"] = "healthy" if auth_ok else "unhealthy"
            
            cache_ok = await self.cache.ping()
            health_status["cache_service"] = "healthy" if cache_ok else "unhealthy"
            
            history_ok = await self.history.ping()
            health_status["history_service"] = "healthy" if history_ok else "unhealthy"
            
            scheduler_status = await self.scheduler.get_scheduler_status()
            health_status["scheduler_service"] = scheduler_status.get("status", "unknown")
            
            # 整体状态
            all_healthy = all(
                status == "healthy" 
                for key, status in health_status.items() 
                if key != "overall"
            )
            health_status["overall"] = "healthy" if all_healthy else "degraded"
            
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            health_status["overall"] = "error"
            health_status["error"] = str(e)
        
        return health_status
    
    async def get_service_stats(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        try:
            stats = {
                "connection_pool": await self._connection_manager.get_pool_info(),
                "cache_stats": await self.cache.get_cache_stats(),
                "history_stats": await self.history.get_summary_stats(),
                "scheduler_stats": await self.scheduler.get_scheduler_status(),
                "initialized": self._initialized
            }
            return stats
        except Exception as e:
            logger.error(f"获取服务统计失败: {e}")
            return {"error": str(e), "initialized": self._initialized}
    
    async def reset_connections(self):
        """重置所有连接"""
        try:
            logger.info("重置Redis连接")
            
            # 关闭调度器
            await self.scheduler.shutdown()
            
            # 重置连接池
            await self._connection_manager.reset_pool()
            
            # 重新初始化
            self._initialized = False
            await self.initialize()
            
            logger.info("Redis连接重置完成")
            
        except Exception as e:
            logger.error(f"重置Redis连接失败: {e}")
            raise
    
    async def close_all(self):
        """关闭所有Redis连接"""
        try:
            logger.info("关闭所有Redis服务")
            
            # 关闭调度器
            await self.scheduler.shutdown()
            
            # 关闭连接池（所有服务共享）
            await self._connection_manager.close()
            
            self._initialized = False
            logger.info("所有Redis服务已关闭")
            
        except Exception as e:
            logger.error(f"关闭Redis服务失败: {e}")


# 全局实例
redis_services = RedisServiceManager()