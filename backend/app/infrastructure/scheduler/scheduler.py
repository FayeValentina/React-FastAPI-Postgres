"""
统一的调度服务（schedule_id-only）
"""
import logging
from typing import Tuple, Dict, Any, List, Optional
from datetime import datetime

from app.modules.tasks.models import TaskConfig
from .core import SchedulerCoreService
from .status import ScheduleHistoryRedisService, ScheduleStatus
from app.infrastructure.database.postgres_base import AsyncSessionLocal
from sqlalchemy import select

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    调度服务 — 运行时全部以 schedule_id 为主。

    - core: TaskIQ 调度器（独立连接）
    - state: Redis 状态/历史/索引（共享连接池）
    """

    def __init__(self):
        self.core = SchedulerCoreService()
        self.state = ScheduleHistoryRedisService()

    async def initialize(self):
        await self.core.initialize()

    async def shutdown(self):
        await self.core.shutdown()

    async def register_task(self, config: TaskConfig) -> Tuple[bool, str]:
        """注册一个新的调度实例（从模板创建），返回 (success, schedule_id or message)。"""
        try:
            schedule_id = await self.core.register_task(config)
            if not schedule_id:
                return False, "TaskIQ 注册失败"

            # 状态与元数据（存储足量快照以辅助恢复）
            await self.state.set_schedule_status(schedule_id, ScheduleStatus.ACTIVE)
            await self.state.set_schedule_metadata(schedule_id, {
                "config_id": config.id,
                "name": config.name,
                "task_type": config.task_type,
                "scheduler_type": config.scheduler_type.value,
                "timeout_seconds": config.timeout_seconds,
                "priority": getattr(config, 'priority', None),
                "parameters": config.parameters or {},
                "schedule_config": config.schedule_config or {},
                "registered_at": datetime.utcnow().isoformat(),
            })

            # 建立索引
            await self.state.add_schedule_to_index(config.id, schedule_id)

            # 历史
            await self.state.add_schedule_history_event(schedule_id, {
                "event": "task_registered",
                "task_name": config.name,
                "success": True,
            })

            return True, schedule_id

        except Exception as e:
            logger.error(f"注册任务失败: {e}")
            return False, str(e)

    async def unregister(self, schedule_id: str) -> Tuple[bool, str]:
        """按 schedule_id 注销调度实例。"""
        try:
            # 先读取元数据以便后续移除索引
            meta = await self.state.get_schedule_metadata(schedule_id)
            config_id = None
            try:
                config_id = int(meta.get("config_id")) if isinstance(meta, dict) and meta.get("config_id") is not None else None
            except Exception:
                config_id = None

            success = await self.core.unregister_task(schedule_id)
            if not success:
                return False, "TaskIQ 注销失败"

            # 从索引移除
            if config_id is not None:
                await self.state.remove_schedule_from_index(config_id, schedule_id)

            # 彻底清理该实例的状态/元数据/历史/数据
            await self.state.purge_schedule_artifacts(schedule_id)

            return True, "ok"
        except Exception as e:
            logger.error(f"注销任务失败: schedule_id={schedule_id}, err={e}")
            return False, str(e)

    async def pause(self, schedule_id: str) -> Tuple[bool, str]:
        """暂停调度实例（从 TaskIQ 移除调度，状态设为 PAUSED）。"""
        try:
            success = await self.core.unregister_task(schedule_id)
            if success:
                await self.state.set_schedule_status(schedule_id, ScheduleStatus.PAUSED)
                await self.state.add_schedule_history_event(schedule_id, {
                    "event": "task_paused",
                    "success": True,
                })
                return True, "ok"
            return False, "TaskIQ 暂停失败"
        except Exception as e:
            await self.state.add_schedule_history_event(schedule_id, {
                "event": "task_pause_error",
                "success": False,
                "error": str(e),
            })
            return False, str(e)

    async def resume(self, schedule_id: str) -> Tuple[bool, str]:
        """恢复调度实例（使用相同 schedule_id 重新注册）。"""
        try:
            # 读取元数据以获取 config_id
            meta = await self.state.get_schedule_metadata(schedule_id)
            config_id = meta.get("config_id") if isinstance(meta, dict) else None
            if config_id is None:
                return False, "缺少 config_id 元数据"

            # 从数据库加载模板（以模板为准）
            from app.modules.tasks.models import TaskConfig as TaskConfigModel
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(TaskConfigModel).where(TaskConfigModel.id == int(config_id)))
                config: Optional[TaskConfigModel] = result.scalar_one_or_none()
                if not config:
                    return False, "任务模板不存在，无法恢复"

            # 用相同 schedule_id 重新注册
            new_id = await self.core.register_task(config, schedule_id=schedule_id)
            if not new_id:
                return False, "TaskIQ 恢复失败"

            await self.state.set_schedule_status(schedule_id, ScheduleStatus.ACTIVE)
            await self.state.add_schedule_history_event(schedule_id, {
                "event": "task_resumed",
                "success": True,
            })
            return True, schedule_id
        except Exception as e:
            await self.state.add_schedule_history_event(schedule_id, {
                "event": "task_resume_error",
                "success": False,
                "error": str(e),
            })
            return False, str(e)

    # ========== 查询 ==========

    async def get_schedule_full_info(self, schedule_id: str) -> Dict[str, Any]:
        return await self.state.get_schedule_full_info(schedule_id)

    async def get_all_schedules(self) -> List[Dict[str, Any]]:
        return await self.core.get_all_schedules()

    async def get_scheduler_summary(self) -> Dict[str, Any]:
        return await self.state.get_scheduler_summary()

    async def list_config_schedules(self, config_id: int) -> List[str]:
        return await self.state.list_schedule_ids(config_id)

    # ========== 维护与清理 ==========

    async def find_orphan_schedule_ids(self) -> List[str]:
        """找出没有对应 TaskConfig 的调度实例。"""
        try:
            schedules = await self.core.get_all_schedules()
            orphan_ids: List[str] = []
            if not schedules:
                return orphan_ids

            from app.modules.tasks.models import TaskConfig as TaskConfigModel
            async with AsyncSessionLocal() as db:
                for s in schedules:
                    schedule_id = s.get("schedule_id")
                    cfg_id = s.get("config_id")
                    if not schedule_id:
                        continue
                    if cfg_id is None:
                        orphan_ids.append(schedule_id)
                        continue
                    # check DB existence
                    result = await db.execute(select(TaskConfigModel.id).where(TaskConfigModel.id == int(cfg_id)))
                    exists = result.scalar_one_or_none()
                    if not exists:
                        orphan_ids.append(schedule_id)
            return orphan_ids
        except Exception as e:
            logger.error(f"扫描孤儿调度实例失败: {e}")
            return []

    async def cleanup_orphan_schedules(self) -> Dict[str, Any]:
        """清理孤儿调度实例（无对应 TaskConfig）。"""
        summary = {"checked": 0, "removed": 0, "errors": 0, "ids": []}
        try:
            orphan_ids = await self.find_orphan_schedule_ids()
            summary["checked"] = len(orphan_ids)
            for sid in orphan_ids:
                ok, _ = await self.unregister(sid)
                if ok:
                    summary["removed"] += 1
                    summary["ids"].append(sid)
                else:
                    summary["errors"] += 1
        except Exception as e:
            logger.error(f"清理孤儿调度失败: {e}")
        return summary

    async def cleanup_legacy_artifacts(self) -> Dict[str, Any]:
        """清理遗留的旧键与旧格式调度ID (scheduled_task_123)。"""
        result: Dict[str, Any] = {"legacy_keys_removed": {}, "legacy_schedules_removed": 0}
        try:
            # 1) Remove legacy config-scoped keys
            removed = await self.state.cleanup_legacy_config_scoped_keys()
            result["legacy_keys_removed"] = removed

            # 2) Remove legacy scheduled ids in TaskIQ storage
            schedules = await self.core.get_all_schedules()
            removed_count = 0
            for s in schedules:
                sid = s.get("schedule_id", "")
                if isinstance(sid, str) and sid.startswith("scheduled_task_"):
                    if await self.core.unregister_task(sid):
                        removed_count += 1
            result["legacy_schedules_removed"] = removed_count
        except Exception as e:
            logger.error(f"清理遗留资源失败: {e}")
        return result

    async def ensure_default_instances(self) -> Dict[str, Any]:
        """为每个需要调度的 TaskConfig 确保至少存在一个调度实例。"""
        summary = {"configs": 0, "created": 0, "skipped": 0, "errors": 0}
        try:
            from app.modules.tasks.models import TaskConfig as TaskConfigModel
            from app.infrastructure.tasks.task_registry_decorators import SchedulerType as ST
            async with AsyncSessionLocal() as db:
                # 取所有配置
                res = await db.execute(select(TaskConfigModel))
                configs = list(res.scalars())
                summary["configs"] = len(configs)
                for cfg in configs:
                    if cfg.scheduler_type == ST.MANUAL:
                        summary["skipped"] += 1
                        continue
                    # 检查索引中是否已有实例
                    ids = await self.state.list_schedule_ids(cfg.id)
                    if ids:
                        summary["skipped"] += 1
                        continue
                    ok, sid_or_msg = await self.register_task(cfg)
                    if ok:
                        summary["created"] += 1
                    else:
                        summary["errors"] += 1
        except Exception as e:
            logger.error(f"确保默认实例失败: {e}")
        return summary


# 全局实例
scheduler_service = SchedulerService()
