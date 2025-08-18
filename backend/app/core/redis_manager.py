# backend/app/core/redis_manager.py
from app.redis.auth_redis import AuthRedisService
from app.redis.cache_redis import CacheRedisService
from app.redis.schedule_history_redis import ScheduleHistoryRedisService
from app.redis.scheduler_redis import SchedulerRedisService
# from app.redis.timeout_redis import TimeoutRedisService  # 移除，使用TaskIQ原生超时
from app.core.redis_pool import redis_connection_manager

class RedisServiceManager:
    """Redis服务管理器"""
    
    def __init__(self):
        self.auth = AuthRedisService()
        self.cache = CacheRedisService()
        self.history = ScheduleHistoryRedisService()
        self.scheduler = SchedulerRedisService()
        # self.timeout = TimeoutRedisService()  # 移除，使用TaskIQ原生超时
        self._connection_manager = redis_connection_manager
    
    async def initialize(self):
        """初始化所有服务"""
        # 初始化连接池
        await self._connection_manager.get_client()
        # 初始化调度器
        await self.scheduler.initialize()
    
    async def close_all(self):
        """关闭所有Redis连接"""
        await self.scheduler.shutdown()
        # 关闭共享连接池
        await self._connection_manager.close()

# 全局实例
redis_services = RedisServiceManager()