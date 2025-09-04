"""
统一的调度服务 - 使用增强的历史服务，消除功能重叠
"""
import logging
from typing import Tuple, Dict, Any, List
from datetime import datetime
from app.modules.tasks.models import TaskConfig
from .core import SchedulerCoreService
from .status import ScheduleHistoryRedisService, ScheduleStatus

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    统一的调度服务 - 解决双重连接和功能重叠问题
    
    架构优化：
    - core: TaskIQ调度器（独立连接，必需）
    - state: 使用增强的HistoryService（统一连接池，消除重叠）
    """
    
    def __init__(self):
        self.core = SchedulerCoreService()               # TaskIQ调度器
        self.state = ScheduleHistoryRedisService()       # 增强的统一状态和历史服务
    
    async def initialize(self):
        """初始化所有服务"""
        await self.core.initialize()
        # state服务继承RedisBase，无需额外初始化
    
    async def shutdown(self):
        """关闭所有服务"""
        await self.core.shutdown()
    
    async def register_task(self, config: TaskConfig) -> Tuple[bool, str]:
        """注册任务（调度器 + 状态）"""
        try:
            # 1. 注册到TaskIQ调度器
            success = await self.core.register_task(config)
            
            if success:
                # 2. 更新状态和元数据（使用增强的history服务）
                await self.state.set_task_status(config.id, ScheduleStatus.ACTIVE)
                await self.state.set_task_metadata(config.id, {
                    "name": config.name,
                    "task_type": config.task_type,
                    "scheduler_type": config.scheduler_type.value,
                    "registered_at": datetime.utcnow().isoformat(),
                    "timeout_seconds": config.timeout_seconds
                })
                
                # 3. 记录历史事件
                await self.state.add_history_event(config.id, {
                    "event": "task_registered",
                    "task_name": config.name,
                    "success": True
                })
                
                return True, f"任务 {config.name} 注册成功"
            else:
                # 注册失败，记录错误状态
                await self.state.set_task_status(config.id, ScheduleStatus.ERROR)
                await self.state.add_history_event(config.id, {
                    "event": "task_register_failed",
                    "task_name": config.name,
                    "success": False,
                    "error": "TaskIQ注册失败"
                })
                
                return False, f"任务 {config.name} 注册失败"
                
        except Exception as e:
            error_msg = f"注册任务失败: {str(e)}"
            await self.state.set_task_status(config.id, ScheduleStatus.ERROR)
            await self.state.add_history_event(config.id, {
                "event": "task_register_error",
                "task_name": config.name,
                "success": False,
                "error": str(e)
            })
            return False, error_msg
    
    async def unregister_task(self, config_id: int) -> Tuple[bool, str]:
        """注销任务（调度器 + 状态）"""
        try:
            # 1. 从TaskIQ调度器注销
            success = await self.core.unregister_task(config_id)
            
            # 2. 更新状态（无论成功失败都设为inactive）
            await self.state.set_task_status(config_id, ScheduleStatus.INACTIVE)
            await self.state.add_history_event(config_id, {
                "event": "task_unregistered",
                "success": success
            })
            
            if success:
                return True, f"任务 {config_id} 注销成功"
            else:
                return False, f"任务 {config_id} 注销失败"
                
        except Exception as e:
            error_msg = f"注销任务失败: {str(e)}"
            await self.state.set_task_status(config_id, ScheduleStatus.ERROR)
            await self.state.add_history_event(config_id, {
                "event": "task_unregister_error",
                "success": False,
                "error": str(e)
            })
            return False, error_msg
    
    async def pause_task(self, config_id: int) -> Tuple[bool, str]:
        """暂停任务"""
        try:
            success = await self.core.unregister_task(config_id)
            
            if success:
                await self.state.set_task_status(config_id, ScheduleStatus.PAUSED)
                await self.state.add_history_event(config_id, {
                    "event": "task_paused",
                    "success": True
                })
                return True, f"任务 {config_id} 暂停成功"
            else:
                return False, f"任务 {config_id} 暂停失败"
                
        except Exception as e:
            error_msg = f"暂停任务失败: {str(e)}"
            await self.state.add_history_event(config_id, {
                "event": "task_pause_error",
                "success": False,
                "error": str(e)
            })
            return False, error_msg
    
    async def resume_task(self, config: TaskConfig) -> Tuple[bool, str]:
        """恢复任务"""
        current_status = await self.state.get_task_status(config.id)
        if current_status != ScheduleStatus.PAUSED:
            return False, f"任务当前状态为 {current_status.value}, 无法恢复"
        
        return await self.register_task(config)
    
    # ========== 委托给state服务的方法 ==========
    
    async def get_task_status(self, config_id: int) -> ScheduleStatus:
        """获取任务状态"""
        return await self.state.get_task_status(config_id)
    
    async def get_task_full_info(self, config_id: int) -> Dict[str, Any]:
        """获取任务完整信息"""
        # 先从state获取基础信息
        info = await self.state.get_task_full_info(config_id)
        
        # 验证与TaskIQ调度器的一致性
        is_actually_scheduled = await self.core.is_task_scheduled(config_id)
        info["is_actually_scheduled"] = is_actually_scheduled
        info["status_consistent"] = (info.get("is_scheduled", False)) == is_actually_scheduled
        
        return info
    
    async def get_all_schedules(self) -> List[Dict[str, Any]]:
        """获取所有调度任务"""
        return await self.core.get_all_schedules()
    
    async def get_scheduler_summary(self) -> Dict[str, Any]:
        """获取调度器摘要"""
        return await self.state.get_scheduler_summary()


# 全局实例
scheduler_service = SchedulerService()


def get_scheduler_service() -> SchedulerService:
    """FastAPI 依赖项：获取调度器服务"""
    return scheduler_service
