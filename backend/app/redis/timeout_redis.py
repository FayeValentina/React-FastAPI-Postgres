# backend/app/services/timeout_redis.py
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from app.core.redis_core import RedisBase
from app.utils.common import get_current_time

class TimeoutRedisService(RedisBase):
    """超时监控Redis服务，替换现有的redis_timeout_store"""
    
    def __init__(self):
        super().__init__()
        self.tasks_hash_key = "timeout:tasks"  # 存储任务详细信息
        self.index_key = "timeout:index"       # 按过期时间排序的索引
    
    async def add_task(
        self,
        task_id: str,
        config_id: int,
        timeout_seconds: int,
        started_at: datetime
    ) -> bool:
        """添加任务到超时监控"""
        client = await self.get_client()
        
        try:
            deadline = started_at.timestamp() + timeout_seconds
            
            task_data = {
                "task_id": task_id,
                "config_id": config_id,
                "timeout_seconds": timeout_seconds,
                "started_at": started_at.isoformat(),
                "deadline": deadline
            }
            
            pipe = client.pipeline()
            # 存储任务详细信息到Hash
            pipe.hset(self.tasks_hash_key, task_id, json.dumps(task_data))
            # 添加到过期时间索引（Sorted Set，按deadline排序）
            pipe.zadd(self.index_key, {task_id: deadline})
            
            await pipe.execute()
            return True
        except Exception:
            return False
    
    async def remove_task(self, task_id: str) -> bool:
        """移除任务（任务完成或取消时调用）"""
        client = await self.get_client()
        
        try:
            pipe = client.pipeline()
            pipe.hdel(self.tasks_hash_key, task_id)
            pipe.zrem(self.index_key, task_id)
            await pipe.execute()
            return True
        except Exception:
            return False
    
    async def get_expired_tasks(self) -> List[Dict[str, Any]]:
        """获取所有超时的任务，使用高效的Redis操作"""
        client = await self.get_client()
        
        try:
            current_timestamp = get_current_time().timestamp()
            
            # 使用ZRANGEBYSCORE获取所有deadline小于当前时间的任务ID
            expired_task_ids = await client.zrangebyscore(
                self.index_key,
                min=0,
                max=current_timestamp
            )
            
            if not expired_task_ids:
                return []
            
            # 批量获取任务详细信息
            task_data_list = await client.hmget(self.tasks_hash_key, *expired_task_ids)
            
            expired_tasks = []
            for task_data_str in task_data_list:
                if task_data_str:
                    try:
                        task_data = json.loads(task_data_str)
                        expired_tasks.append(task_data)
                    except json.JSONDecodeError:
                        continue
            
            return expired_tasks
        except Exception:
            return []
    
    async def get_all_tasks(self) -> List[Dict[str, Any]]:
        """获取所有监控中的任务（用于调试和清理）"""
        client = await self.get_client()
        
        try:
            all_task_data = await client.hgetall(self.tasks_hash_key)
            
            tasks = []
            for task_id, task_data_str in all_task_data.items():
                try:
                    task_data = json.loads(task_data_str)
                    tasks.append(task_data)
                except json.JSONDecodeError:
                    continue
            
            return tasks
        except Exception:
            return []
    
    async def cleanup_completed_tasks(self, task_ids: List[str]) -> int:
        """批量清理已完成的任务"""
        if not task_ids:
            return 0
        
        client = await self.get_client()
        
        try:
            pipe = client.pipeline()
            for task_id in task_ids:
                pipe.hdel(self.tasks_hash_key, task_id)
                pipe.zrem(self.index_key, task_id)
            
            results = await pipe.execute()
            
            # 计算实际删除的数量（每个任务两个操作）
            deleted_count = sum(1 for i in range(0, len(results), 2) if results[i])
            return deleted_count
        except Exception:
            return 0