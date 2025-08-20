from typing import List, Dict, Any, Optional
import json
from datetime import datetime, timedelta
from app.core.redis import RedisBase

class ScheduleHistoryRedisService(RedisBase):
    """调度历史记录服务 - 使用新的连接池架构"""
    
    def __init__(self):
        super().__init__(key_prefix="schedule:")
        self.history_prefix = "history:"
        self.status_prefix = "status:"
        self.statistics_prefix = "stats:"
        self.max_history = 100  # 保留最近100条记录
        self.default_ttl = 7 * 24 * 3600  # 7天过期
    
    # ========== 历史事件管理 ==========
    
    async def add_history_event(
        self,
        config_id: int,
        event_data: Dict[str, Any]
    ) -> bool:
        """添加调度历史事件"""
        try:
            # 添加时间戳
            event_data.setdefault("timestamp", datetime.utcnow().isoformat())
            
            operations = [
                {
                    "method": "lpush",
                    "args": [f"{self.history_prefix}{config_id}", json.dumps(event_data, ensure_ascii=False)]
                },
                {
                    "method": "ltrim", 
                    "args": [f"{self.history_prefix}{config_id}", 0, self.max_history - 1]
                },
                {
                    "method": "expire",
                    "args": [f"{self.history_prefix}{config_id}", self.default_ttl]
                }
            ]
            
            results = await self.pipeline_execute(operations)
            return len(results) == 3 and results[0] > 0
            
        except Exception:
            return False
    
    async def get_history(self, config_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """获取调度历史"""
        try:
            history_data = await self.lrange(f"{self.history_prefix}{config_id}", 0, limit - 1)
            return [json.loads(item) for item in history_data if item]
        except Exception:
            return []
    
    async def get_recent_history(self, config_id: int, hours: int = 24) -> List[Dict[str, Any]]:
        """获取最近N小时的历史"""
        try:
            all_history = await self.get_history(config_id, self.max_history)
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            recent_history = []
            for event in all_history:
                try:
                    event_time = datetime.fromisoformat(event.get("timestamp", ""))
                    if event_time >= cutoff_time:
                        recent_history.append(event)
                except (ValueError, TypeError):
                    continue
            
            return recent_history
        except Exception:
            return []
    
    async def clear_history(self, config_id: int) -> bool:
        """清除指定配置的历史记录"""
        return await self.delete(f"{self.history_prefix}{config_id}") > 0
    
    # ========== 状态管理 ==========
    
    async def update_status(self, config_id: int, status: str, ttl: int = 3600) -> bool:
        """更新调度状态"""
        status_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        return await self.set_json(f"{self.status_prefix}{config_id}", status_data, ttl)
    
    async def get_status(self, config_id: int) -> Optional[Dict[str, Any]]:
        """获取调度状态"""
        return await self.get_json(f"{self.status_prefix}{config_id}")
    
    async def get_all_statuses(self) -> Dict[int, Dict[str, Any]]:
        """获取所有状态"""
        try:
            status_keys = await self.keys(f"{self.status_prefix}*")
            statuses = {}
            
            for key in status_keys:
                config_id_str = key.replace(self.status_prefix, "")
                try:
                    config_id = int(config_id_str)
                    status_data = await self.get_json(key)
                    if status_data:
                        statuses[config_id] = status_data
                except ValueError:
                    continue
            
            return statuses
        except Exception:
            return {}
    
    # ========== 统计信息 ==========
    
    async def update_statistics(self, config_id: int, stats: Dict[str, Any]) -> bool:
        """更新统计信息"""
        stats.setdefault("updated_at", datetime.utcnow().isoformat())
        return await self.set_json(f"{self.statistics_prefix}{config_id}", stats, self.default_ttl)
    
    async def get_statistics(self, config_id: int) -> Optional[Dict[str, Any]]:
        """获取统计信息"""
        return await self.get_json(f"{self.statistics_prefix}{config_id}")
    
    async def increment_counter(self, config_id: int, counter_name: str, increment: int = 1) -> int:
        """增加计数器"""
        try:
            async with self._connection_manager.get_connection() as client:
                counter_key = self._make_key(f"{self.statistics_prefix}{config_id}:{counter_name}")
                new_value = await client.incrby(counter_key, increment)
                await client.expire(counter_key, self.default_ttl)
                return new_value
        except Exception:
            return 0
    
    async def get_counter(self, config_id: int, counter_name: str) -> int:
        """获取计数器值"""
        try:
            counter_value = await self.get(f"{self.statistics_prefix}{config_id}:{counter_name}")
            return int(counter_value) if counter_value else 0
        except (ValueError, TypeError):
            return 0
    
    # ========== 批量操作 ==========
    
    async def get_multiple_histories(self, config_ids: List[int], limit: int = 10) -> Dict[int, List[Dict[str, Any]]]:
        """批量获取多个配置的历史"""
        histories = {}
        
        for config_id in config_ids:
            histories[config_id] = await self.get_history(config_id, limit)
        
        return histories
    
    async def add_bulk_events(self, events: List[Dict[str, Any]]) -> int:
        """批量添加事件"""
        success_count = 0
        
        for event in events:
            config_id = event.get("config_id")
            if config_id:
                if await self.add_history_event(config_id, event):
                    success_count += 1
        
        return success_count
    
    # ========== 清理操作 ==========
    
    async def cleanup_old_data(self, days: int = 7) -> Dict[str, int]:
        """清理旧数据"""
        try:
            cutoff_timestamp = datetime.utcnow() - timedelta(days=days)
            
            # 获取所有历史键
            history_keys = await self.keys(f"{self.history_prefix}*")
            status_keys = await self.keys(f"{self.status_prefix}*")
            stats_keys = await self.keys(f"{self.statistics_prefix}*")
            
            cleaned_count = {
                "history": 0,
                "status": 0,
                "statistics": 0
            }
            
            # 清理历史记录（这里简化为直接删除，实际可以基于时间戳过滤）
            for key in history_keys:
                if await self.delete(key.replace(self.key_prefix, "")) > 0:
                    cleaned_count["history"] += 1
            
            # 清理过期状态和统计
            for key in status_keys + stats_keys:
                key_type = "status" if self.status_prefix in key else "statistics"
                if await self.delete(key.replace(self.key_prefix, "")) > 0:
                    cleaned_count[key_type] += 1
            
            return cleaned_count
            
        except Exception:
            return {"history": 0, "status": 0, "statistics": 0}
    
    async def get_summary_stats(self) -> Dict[str, Any]:
        """获取汇总统计"""
        try:
            history_keys = await self.keys(f"{self.history_prefix}*")
            status_keys = await self.keys(f"{self.status_prefix}*")
            stats_keys = await self.keys(f"{self.statistics_prefix}*")
            
            return {
                "total_configs_with_history": len(history_keys),
                "total_configs_with_status": len(status_keys),
                "total_configs_with_stats": len(stats_keys),
                "last_updated": datetime.utcnow().isoformat()
            }
        except Exception:
            return {
                "total_configs_with_history": 0,
                "total_configs_with_status": 0,
                "total_configs_with_stats": 0,
                "last_updated": datetime.utcnow().isoformat()
            }