"""
增强的调度状态和历史服务 - 统一管理所有调度相关数据
"""
import logging
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
from enum import Enum

from app.infrastructure.database.redis_base import RedisBase

logger = logging.getLogger(__name__)


class ScheduleStatus(str, Enum):
    """调度状态枚举"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class ScheduleHistoryRedisService(RedisBase):
    """
    统一的调度状态和历史服务 - 使用统一连接池
    
    职责：
    - 调度状态管理
    - 任务元数据存储  
    - 历史事件记录
    - 统计信息管理
    
    这个服务是状态管理的唯一真实来源，消除了功能重叠
    """
    
    def __init__(self):
        super().__init__(key_prefix="schedule:")
        self.status_prefix = "status:"
        self.metadata_prefix = "meta:"
        self.history_prefix = "history:"
        self.statistics_prefix = "stats:"
        self.max_history = 100
        self.default_ttl = 7 * 24 * 3600  # 7天过期
    
    # ========== 状态管理（核心功能，消除重叠）==========
    
    async def set_task_status(self, config_id: int, status: ScheduleStatus) -> bool:
        """设置任务调度状态"""
        try:
            success = await self.set(f"{self.status_prefix}{config_id}", status.value)
            
            # 同时记录状态变更事件
            await self.add_history_event(
                config_id=config_id,
                event_data={
                    "event": "status_changed",
                    "new_status": status.value,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return success
        except Exception as e:
            logger.error(f"设置任务状态失败: {e}")
            return False
    
    async def get_task_status(self, config_id: int) -> ScheduleStatus:
        """获取任务调度状态"""
        try:
            status_str = await self.get(f"{self.status_prefix}{config_id}")
            if status_str:
                return ScheduleStatus(status_str)
            return ScheduleStatus.INACTIVE
        except Exception as e:
            logger.error(f"获取任务状态失败: {e}")
            return ScheduleStatus.ERROR
    
    async def get_all_task_statuses(self) -> Dict[int, str]:
        """获取所有任务状态"""
        try:
            status_keys = await self.scan_keys(f"{self.status_prefix}*")
            statuses = {}
            
            for key in status_keys:
                config_id_str = key.replace(self.status_prefix, "")
                try:
                    config_id = int(config_id_str)
                    status = await self.get(key)
                    if status:
                        statuses[config_id] = status
                except ValueError:
                    continue
            
            return statuses
        except Exception as e:
            logger.error(f"获取所有任务状态失败: {e}")
            return {}
    
    async def get_tasks_by_status(self, status: ScheduleStatus) -> List[int]:
        """根据状态获取任务ID列表"""
        all_statuses = await self.get_all_task_statuses()
        return [
            config_id for config_id, task_status in all_statuses.items()
            if task_status == status.value
        ]
    
    # ========== 元数据管理 ==========
    
    async def set_task_metadata(self, config_id: int, metadata: Dict[str, Any]) -> bool:
        """设置任务元数据"""
        try:
            metadata.setdefault("updated_at", datetime.utcnow().isoformat())
            return await self.set_json(f"{self.metadata_prefix}{config_id}", metadata, self.default_ttl)
        except Exception as e:
            logger.error(f"设置任务元数据失败: {e}")
            return False
    
    async def get_task_metadata(self, config_id: int) -> Dict[str, Any]:
        """获取任务元数据"""
        try:
            metadata = await self.get_json(f"{self.metadata_prefix}{config_id}")
            return metadata or {}
        except Exception as e:
            logger.error(f"获取任务元数据失败: {e}")
            return {}
    
    # ========== 历史事件管理（保留原有功能）==========
    
    async def add_history_event(self, config_id: int, event_data: Dict[str, Any]) -> bool:
        """添加调度历史事件 (使用新的 pipeline 上下文管理器)"""
        try:
            event_data.setdefault("timestamp", datetime.utcnow().isoformat())
            history_key = f"{self.history_prefix}{config_id}"
            
            async with self.pipeline() as pipe:
                # 1. 将新事件推入列表左侧
                pipe.lpush(self._make_key(history_key), json.dumps(event_data, ensure_ascii=False))
                # 2.修建列表，只保留最新的 max_history 条记录
                pipe.ltrim(self._make_key(history_key), 0, self.max_history - 1)
                # 3. 为列表续期
                pipe.expire(self._make_key(history_key), self.default_ttl)
                
                results = await pipe.execute()
            
            # 检查 LPUSH 操作是否成功（返回列表的新长度 > 0）
            return results[0] > 0
            
        except Exception as e:
            logger.error(f"添加历史事件失败: {e}")
            return False
    
    async def get_history(self, config_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """获取调度历史"""
        try:
            history_data = await self.lrange(f"{self.history_prefix}{config_id}", 0, limit - 1)
            return [json.loads(item) for item in history_data if item]
        except Exception as e:
            logger.error(f"获取历史记录失败: {e}")
            return []
    
    # ========== 综合查询接口 ==========
    
    async def get_task_full_info(self, config_id: int, history_limit: int = 5) -> Dict[str, Any]:
        """获取任务完整信息（状态+元数据+最近历史）"""
        try:
            status = await self.get_task_status(config_id)
            metadata = await self.get_task_metadata(config_id)
            recent_history = await self.get_history(config_id, limit=history_limit)
            
            return {
                "config_id": config_id,
                "status": status.value,
                "metadata": metadata,
                "recent_history": recent_history,
                "is_scheduled": status == ScheduleStatus.ACTIVE
            }
        except Exception as e:
            logger.error(f"获取任务完整信息失败: {e}")
            return {
                "config_id": config_id,
                "status": ScheduleStatus.ERROR.value,
                "metadata": {},
                "recent_history": [],
                "is_scheduled": False,
                "error": str(e)
            }
    
    async def get_scheduler_summary(self) -> Dict[str, Any]:
        """获取调度器状态摘要"""
        try:
            all_statuses = await self.get_all_task_statuses()
            
            summary = {
                "total_tasks": len(all_statuses),
                "active_tasks": 0,
                "paused_tasks": 0,
                "inactive_tasks": 0,
                "error_tasks": 0,
                "last_updated": datetime.utcnow().isoformat()
            }
            
            for status in all_statuses.values():
                summary[f"{status}_tasks"] += 1
            
            return summary
        except Exception as e:
            logger.error(f"获取调度器摘要失败: {e}")
            return {
                "total_tasks": 0,
                "active_tasks": 0,
                "paused_tasks": 0,
                "inactive_tasks": 0,
                "error_tasks": 0,
                "error": str(e),
                "last_updated": datetime.utcnow().isoformat()
            }