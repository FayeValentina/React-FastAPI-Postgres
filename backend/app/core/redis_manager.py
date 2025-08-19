# backend/app/services/redis_manager.py
from app.redis.auth_redis import AuthRedisService
from app.redis.cache_redis import CacheRedisService
from app.redis.schedule_history_redis import ScheduleHistoryRedisService
from app.redis.scheduler_redis import SchedulerRedisService

class RedisServiceManager:
    """Redis服务管理器"""
    
    def __init__(self):
        self.auth = AuthRedisService()
        self.cache = CacheRedisService()
        self.history = ScheduleHistoryRedisService()  # 调度历史记录服务
        self.scheduler = SchedulerRedisService()  # 真正的调度器服务
    
    async def initialize(self):
        """初始化所有服务"""
        # 初始化调度器
        await self.scheduler.initialize()
    
    async def close_all(self):
        """关闭所有Redis连接"""
        await self.auth.close()
        await self.cache.close()
        await self.history.close()
        await self.scheduler.shutdown()

# 全局实例
redis_services = RedisServiceManager()