"""
Redis超时监控存储
使用Redis作为中央存储，支持跨进程的超时监控
"""
import json
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
import redis.asyncio as redis

from app.core.config import settings
from app.utils.common import get_current_time

logger = logging.getLogger(__name__)


class RedisTimeoutStore:
    """Redis超时任务存储"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.key_prefix = "timeout_monitor"
        self.task_hash_key = f"{self.key_prefix}:tasks"  # Hash存储所有任务
        self.index_key = f"{self.key_prefix}:index"      # Sorted Set索引
        
    async def connect(self):
        """连接Redis"""
        if not self.redis_client:
            self.redis_client = redis.from_url(
                settings.redis.CONNECTION_URL,
                decode_responses=True,
                max_connections=10  # 使用连接池
            )
            logger.info("Redis超时存储已连接")
    
    async def disconnect(self):
        """断开Redis连接"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            logger.info("Redis超时存储已断开")
    
    async def register_task(
        self,
        task_id: str,
        config_id: int,
        timeout_seconds: int,
        started_at: datetime
    ) -> bool:
        """
        注册任务到Redis
        
        Args:
            task_id: 任务ID
            config_id: 配置ID
            timeout_seconds: 超时秒数
            started_at: 开始时间
        """
        
        
        try:
            task_data = {
                "task_id": task_id,
                "config_id": config_id,
                "timeout_seconds": timeout_seconds,
                "started_at": started_at.isoformat(),
                "deadline": (started_at.timestamp() + timeout_seconds)
            }
            
            # 使用pipeline提高性能
            pipe = self.redis_client.pipeline()
            
            # 1. 存储任务数据到Hash
            pipe.hset(self.task_hash_key, task_id, json.dumps(task_data))
            
            # 2. 添加到索引（按deadline排序）
            pipe.zadd(self.index_key, {task_id: task_data["deadline"]})
            
            # 移除了无效的expire命令
            
            await pipe.execute()
            
            logger.debug(f"任务 {task_id} 已注册到Redis超时监控")
            return True
            
        except Exception as e:
            logger.error(f"注册任务到Redis失败: {e}")
            return False
    
    async def unregister_task(self, task_id: str) -> bool:
        """
        从Redis注销任务
        
        Args:
            task_id: 任务ID
        """
        
        
        try:
            pipe = self.redis_client.pipeline()
            
            # 1. 从Hash中删除
            pipe.hdel(self.task_hash_key, task_id)
            
            # 2. 从索引中删除
            pipe.zrem(self.index_key, task_id)
            
            await pipe.execute()
            
            logger.debug(f"任务 {task_id} 已从Redis超时监控注销")
            return True
            
        except Exception as e:
            logger.error(f"从Redis注销任务失败: {e}")
            return False
    
    async def get_timeout_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有超时的任务
        
        Returns:
            超时任务列表
        """
        
        
        try:
            current_timestamp = get_current_time().timestamp()
            
            # 获取所有deadline小于当前时间的任务ID
            timeout_task_ids = await self.redis_client.zrangebyscore(
                self.index_key,
                min=0,
                max=current_timestamp
            )
            
            if not timeout_task_ids:
                return []
            
            # 批量获取任务数据
            pipe = self.redis_client.pipeline()
            for task_id in timeout_task_ids:
                pipe.hget(self.task_hash_key, task_id)
            
            task_data_list = await pipe.execute()
            
            # 解析任务数据
            timeout_tasks = []
            for task_data_str in task_data_list:
                if task_data_str:
                    try:
                        task_data = json.loads(task_data_str)
                        timeout_tasks.append(task_data)
                    except json.JSONDecodeError:
                        logger.warning(f"无法解析任务数据: {task_data_str}")
            
            return timeout_tasks
            
        except Exception as e:
            logger.error(f"获取超时任务失败: {e}")
            return []
    
    async def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有监控中的任务（用于调试和清理）
        
        Returns:
            所有任务列表
        """
        
        
        try:
            # 获取所有任务数据
            all_tasks_data = await self.redis_client.hgetall(self.task_hash_key)
            
            tasks = []
            for task_id, task_data_str in all_tasks_data.items():
                try:
                    task_data = json.loads(task_data_str)
                    tasks.append(task_data)
                except json.JSONDecodeError:
                    logger.warning(f"无法解析任务数据: {task_data_str}")
            
            return tasks
            
        except Exception as e:
            logger.error(f"获取所有任务失败: {e}")
            return []
    
    async def cleanup_completed_tasks(self, task_ids: List[str]) -> int:
        """
        批量清理已完成的任务
        
        Args:
            task_ids: 要清理的任务ID列表
            
        Returns:
            清理的任务数量
        """
        if not task_ids:
            return 0
            
        
        
        try:
            pipe = self.redis_client.pipeline()
            
            for task_id in task_ids:
                pipe.hdel(self.task_hash_key, task_id)
                pipe.zrem(self.index_key, task_id)
            
            results = await pipe.execute()
            
            # 计算实际删除的数量
            deleted_count = sum(1 for i in range(0, len(results), 2) if results[i])
            
            logger.info(f"清理了 {deleted_count} 个已完成的任务")
            return deleted_count
            
        except Exception as e:
            logger.error(f"清理任务失败: {e}")
            return 0


# 全局单例
redis_timeout_store = RedisTimeoutStore()