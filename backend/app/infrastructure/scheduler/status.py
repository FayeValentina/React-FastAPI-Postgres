"""
调度状态与历史服务（schedule_id-only 版本）

Redis/TaskIQ 为运行时调度状态的唯一真实来源；所有状态、元数据、历史操作
均以 schedule_id 为主键，config_id 仅用于 Redis 索引映射。
"""
import logging
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
from enum import Enum

from app.infrastructure.redis.redis_base import RedisBase
from app.infrastructure.redis.keyspace import redis_keys

logger = logging.getLogger(__name__)


class ScheduleStatus(str, Enum):
    """调度状态枚举（运行时实例级别）"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class ScheduleHistoryRedisService(RedisBase):
    """
    schedule_id 为主键的统一调度状态与历史服务。

    职责：
    - schedule_id 级别状态管理
    - schedule_id 级别元数据存储
    - schedule_id 级别历史事件记录
    - config_id → {schedule_id...} 映射索引
    """

    def __init__(self):
        super().__init__(key_prefix="schedule:")
        self.max_history = 100
        self.default_ttl = 7 * 24 * 3600  # 7天过期（元数据/历史）

    # ========== 索引管理：config_id → {schedule_id...} ==========

    async def add_schedule_to_index(self, config_id: int, schedule_id: str) -> bool:
        try:
            added = await self.sadd(redis_keys.scheduler.config_index(config_id), schedule_id)
            return added > 0
        except Exception as e:
            logger.error(f"添加索引失败: config_id={config_id}, schedule_id={schedule_id}, err={e}")
            return False

    async def remove_schedule_from_index(self, config_id: int, schedule_id: str) -> bool:
        try:
            removed = await self.srem(redis_keys.scheduler.config_index(config_id), schedule_id)
            return removed > 0
        except Exception as e:
            logger.error(f"移除索引失败: config_id={config_id}, schedule_id={schedule_id}, err={e}")
            return False

    async def list_schedule_ids(self, config_id: int) -> List[str]:
        try:
            ids_set = await self.smembers(redis_keys.scheduler.config_index(config_id))
            if not ids_set:
                return []
            # decode_responses=True 下元素为 str，统一转为 str 以确保类型
            return [str(v) for v in ids_set]
        except Exception as e:
            logger.error(f"读取索引失败: config_id={config_id}, err={e}")
            return []

    # ========== 状态管理 ==========

    async def set_schedule_status(self, schedule_id: str, status: ScheduleStatus) -> bool:
        """设置调度实例状态（无TTL）。"""
        try:
            success = await self.set(redis_keys.scheduler.schedule_status(schedule_id), status.value)
            await self.add_schedule_history_event(schedule_id, {
                "event": "status_changed",
                "new_status": status.value,
                "timestamp": datetime.utcnow().isoformat(),
            })
            return success
        except Exception as e:
            logger.error(f"设置调度状态失败: schedule_id={schedule_id}, err={e}")
            return False

    async def get_schedule_status(self, schedule_id: str) -> ScheduleStatus:
        """获取调度实例状态。"""
        try:
            status_str = await self.get(redis_keys.scheduler.schedule_status(schedule_id))
            if status_str:
                return ScheduleStatus(status_str)
            return ScheduleStatus.INACTIVE
        except Exception as e:
            logger.error(f"获取调度状态失败: schedule_id={schedule_id}, err={e}")
            return ScheduleStatus.ERROR

    async def get_all_schedule_statuses(self) -> Dict[str, str]:
        """扫描所有 schedule 状态键，返回 {schedule_id: status}。"""
        try:
            # keys are like: status:{schedule_id}
            status_keys = await self.scan_keys(f"{redis_keys.scheduler.STATUS_PREFIX}*")
            statuses: Dict[str, str] = {}
            for key in status_keys:
                # strip prefix to get schedule_id
                schedule_id = key.replace(redis_keys.scheduler.STATUS_PREFIX, "")
                status = await self.get(key)
                if status:
                    statuses[schedule_id] = status
            return statuses
        except Exception as e:
            logger.error(f"获取所有调度状态失败: {e}")
            return {}

    async def get_schedules_by_status(self, status: ScheduleStatus) -> List[str]:
        try:
            all_statuses = await self.get_all_schedule_statuses()
            return [sid for sid, s in all_statuses.items() if s == status.value]
        except Exception as e:
            logger.error(f"按状态筛选失败: status={status}, err={e}")
            return []

    # ========== 元数据管理 ==========

    async def set_schedule_metadata(self, schedule_id: str, metadata: Dict[str, Any]) -> bool:
        try:
            metadata.setdefault("updated_at", datetime.utcnow().isoformat())
            return await self.set_json(redis_keys.scheduler.schedule_metadata(schedule_id), metadata, self.default_ttl)
        except Exception as e:
            logger.error(f"设置元数据失败: schedule_id={schedule_id}, err={e}")
            return False

    async def get_schedule_metadata(self, schedule_id: str) -> Dict[str, Any]:
        try:
            metadata = await self.get_json(redis_keys.scheduler.schedule_metadata(schedule_id))
            return metadata or {}
        except Exception as e:
            logger.error(f"获取元数据失败: schedule_id={schedule_id}, err={e}")
            return {}

    # ========== 历史事件 ==========

    async def add_schedule_history_event(self, schedule_id: str, event_data: Dict[str, Any]) -> bool:
        try:
            event_data.setdefault("timestamp", datetime.utcnow().isoformat())
            history_key = redis_keys.scheduler.schedule_history(schedule_id)
            async with self.pipeline() as pipe:
                pipe.lpush(self._make_key(history_key), json.dumps(event_data, ensure_ascii=False))
                pipe.ltrim(self._make_key(history_key), 0, self.max_history - 1)
                pipe.expire(self._make_key(history_key), self.default_ttl)
                results = await pipe.execute()
            return results[0] > 0
        except Exception as e:
            logger.error(f"添加历史事件失败: schedule_id={schedule_id}, err={e}")
            return False

    async def get_schedule_history(self, schedule_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            history_data = await self.lrange(redis_keys.scheduler.schedule_history(schedule_id), 0, limit - 1)
            return [json.loads(item) for item in history_data if item]
        except Exception as e:
            logger.error(f"获取历史记录失败: schedule_id={schedule_id}, err={e}")
            return []

    # ========== 综合查询 ==========

    async def get_schedule_full_info(self, schedule_id: str, history_limit: int = 5) -> Dict[str, Any]:
        try:
            status = await self.get_schedule_status(schedule_id)
            metadata = await self.get_schedule_metadata(schedule_id)
            recent_history = await self.get_schedule_history(schedule_id, limit=history_limit)
            return {
                "schedule_id": schedule_id,
                "status": status.value,
                "metadata": metadata,
                "recent_history": recent_history,
                "is_scheduled": status == ScheduleStatus.ACTIVE,
            }
        except Exception as e:
            logger.error(f"获取调度完整信息失败: schedule_id={schedule_id}, err={e}")
            return {
                "schedule_id": schedule_id,
                "status": ScheduleStatus.ERROR.value,
                "metadata": {},
                "recent_history": [],
                "is_scheduled": False,
                "error": str(e),
            }

    async def get_scheduler_summary(self) -> Dict[str, Any]:
        try:
            all_statuses = await self.get_all_schedule_statuses()
            summary = {
                "total_schedules": len(all_statuses),
                "active_schedules": 0,
                "paused_schedules": 0,
                "inactive_schedules": 0,
                "error_schedules": 0,
                "last_updated": datetime.utcnow().isoformat(),
            }
            for s in all_statuses.values():
                key = f"{s}_schedules"
                if key in summary:
                    summary[key] += 1
            return summary
        except Exception as e:
            logger.error(f"获取调度器摘要失败: {e}")
            return {
                "total_schedules": 0,
                "active_schedules": 0,
                "paused_schedules": 0,
                "inactive_schedules": 0,
                "error_schedules": 0,
                "error": str(e),
                "last_updated": datetime.utcnow().isoformat(),
            }

    # ========== 清理指定调度实例的所有痕迹 ==========

    async def purge_schedule_artifacts(self, schedule_id: str) -> Dict[str, int]:
        """彻底清理某个 schedule_id 的状态/元数据/历史/数据键。

        Returns: dict with per-kind deleted counts.
        """
        deleted = {"status": 0, "meta": 0, "history": 0, "stats": 0, "data": 0}
        try:
            # Build unprefixed subkeys; RedisBase.delete will apply key_prefix.
            keys = [
                redis_keys.scheduler.schedule_status(schedule_id),
                redis_keys.scheduler.schedule_metadata(schedule_id),
                redis_keys.scheduler.schedule_history(schedule_id),
                redis_keys.scheduler.schedule_stats(schedule_id),
                redis_keys.scheduler.schedule_data(schedule_id),
            ]
            # Try delete each individually to accumulate per-kind counts
            for kind, key in zip(list(deleted.keys()), keys):
                try:
                    cnt = await self.delete(key)
                    deleted[kind] += int(cnt or 0)
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"清理调度实例痕迹失败: schedule_id={schedule_id}, err={e}")
        return deleted

    # ========== 兼容性清理（一次性） ==========

    async def cleanup_legacy_config_scoped_keys(self) -> Dict[str, int]:
        """删除旧版基于 config_id 的状态/元数据/历史键。

        旧键形如：
        - status:{config_id}
        - meta:{config_id}
        - history:{config_id}

        新键形如：
        - status:scheduled_task:{config_id}:{uuid}
        
        策略：仅删除冒号后不再包含冒号的键（即 value 中不含冒号）。
        """
        removed = {"status": 0, "meta": 0, "history": 0}
        try:
            for kind, prefix in (
                ("status", redis_keys.scheduler.STATUS_PREFIX),
                ("meta", redis_keys.scheduler.META_PREFIX),
                ("history", redis_keys.scheduler.HISTORY_PREFIX),
            ):
                keys = await self.scan_keys(f"{prefix}*")
                legacy_keys: List[str] = []
                for k in keys:
                    # k looks like "status:<suffix>" with key_prefix trimmed
                    try:
                        _, suffix = k.split(":", 1)
                    except ValueError:
                        # no colon after prefix — treat as legacy
                        legacy_keys.append(k)
                        continue
                    # legacy if suffix has no further colon
                    if ":" not in suffix:
                        legacy_keys.append(k)
                if legacy_keys:
                    removed_count = await self.delete(*legacy_keys)
                    removed[kind] += int(removed_count or 0)
        except Exception as e:
            logger.error(f"清理旧版config范围键失败: {e}")
        return removed
