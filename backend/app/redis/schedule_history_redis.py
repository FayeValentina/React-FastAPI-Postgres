# backend/app/services/schedule_history_redis.py
from typing import List, Dict, Any, Optional
import json
from app.core.redis_core import RedisBase

class ScheduleHistoryRedisService(RedisBase):
    """调度历史记录服务 - 记录任务执行历史和状态"""
    
    def __init__(self):
        super().__init__()
        self.history_prefix = "schedule:history:"
        self.status_prefix = "schedule:status:"
        self.max_history = 100  # 保留最近100条记录
    
    async def add_history_event(
        self,
        config_id: int,
        event_data: Dict[str, Any]
    ) -> bool:
        """添加调度历史事件"""
        client = await self.get_client()
        
        try:
            pipe = client.pipeline()
            # 添加到历史列表头部
            pipe.lpush(f"{self.history_prefix}{config_id}", json.dumps(event_data))
            # 保持列表长度
            pipe.ltrim(f"{self.history_prefix}{config_id}", 0, self.max_history - 1)
            await pipe.execute()
            return True
        except Exception:
            return False
    
    async def get_history(self, config_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """获取调度历史"""
        client = await self.get_client()
        
        try:
            history_data = await client.lrange(f"{self.history_prefix}{config_id}", 0, limit - 1)
            return [json.loads(item) for item in history_data]
        except Exception:
            return []
    
    async def update_status(self, config_id: int, status: str) -> bool:
        """更新调度状态"""
        client = await self.get_client()
        
        try:
            await client.set(f"{self.status_prefix}{config_id}", status, ex=3600)  # 1小时过期
            return True
        except Exception:
            return False