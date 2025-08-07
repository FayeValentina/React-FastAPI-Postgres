"""
纯事件记录器 - 只负责记录事件到数据库
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from app.db.base import AsyncSessionLocal

logger = logging.getLogger(__name__)


class EventRecorder:
    """纯事件记录器 - 只负责将事件写入数据库"""
    
    @staticmethod
    async def record_schedule_event(
        job_id: str,
        event_type: str,  # 'executed', 'error', 'missed', 'scheduled'
        job_name: str = None,
        result: Any = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None
    ) -> bool:
        """
        记录调度事件到 ScheduleEvent 表
        
        Args:
            job_id: 任务ID
            event_type: 事件类型
            job_name: 任务名称
            result: 执行结果
            error_message: 错误信息
            error_traceback: 错误堆栈
            
        Returns:
            bool: 记录是否成功
        """
        try:
            async with AsyncSessionLocal() as db:
                from app.models.schedule_event import ScheduleEvent, ScheduleEventType
                
                # 映射事件类型
                event_type_map = {
                    'executed': ScheduleEventType.EXECUTED,
                    'error': ScheduleEventType.ERROR,
                    'missed': ScheduleEventType.MISSED,
                    'scheduled': ScheduleEventType.SCHEDULED,
                    'paused': ScheduleEventType.PAUSED,
                    'resumed': ScheduleEventType.RESUMED
                }
                
                event_type_enum = event_type_map.get(event_type, ScheduleEventType.EXECUTED)
                
                # 处理结果数据
                result_data = None
                if result is not None:
                    if isinstance(result, dict):
                        result_data = result
                    else:
                        result_data = {'result': str(result)}
                
                # 创建事件记录
                event = ScheduleEvent(
                    job_id=job_id,
                    job_name=job_name or job_id,
                    event_type=event_type_enum,
                    result=result_data,
                    error_message=error_message,
                    error_traceback=error_traceback
                )
                
                db.add(event)
                await db.commit()
                
                logger.debug(f"已记录调度事件: {job_id} - {event_type}")
                return True
                
        except Exception as e:
            logger.error(f"记录调度事件失败 {job_id}: {e}")
            return False
    
    @staticmethod
    async def record_task_execution(
        task_id: str,
        job_name: str,
        status: str,  # 'SUCCESS', 'FAILED', 'TIMEOUT', 'RUNNING'
        started_at: datetime,
        completed_at: Optional[datetime] = None,
        result: Any = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None
    ) -> bool:
        """
        记录任务执行到 TaskExecution 表
        
        Args:
            task_id: Celery任务ID
            job_name: 任务名称
            status: 执行状态
            started_at: 开始时间
            completed_at: 完成时间
            result: 执行结果
            error_message: 错误信息
            error_traceback: 错误堆栈
            
        Returns:
            bool: 记录是否成功
        """
        try:
            async with AsyncSessionLocal() as db:
                from app.models.task_execution import TaskExecution, ExecutionStatus
                
                # 映射状态
                status_map = {
                    'SUCCESS': ExecutionStatus.SUCCESS,
                    'FAILED': ExecutionStatus.FAILED,
                    'TIMEOUT': ExecutionStatus.TIMEOUT,
                    'RUNNING': ExecutionStatus.RUNNING
                }
                
                status_enum = status_map.get(status, ExecutionStatus.FAILED)
                
                # 计算执行时间
                duration_seconds = None
                if started_at and completed_at:
                    duration_seconds = (completed_at - started_at).total_seconds()
                
                # 处理结果数据
                result_data = None
                if result is not None:
                    if isinstance(result, dict):
                        result_data = result
                    else:
                        result_data = {'result': str(result)}
                
                # 创建执行记录
                execution = TaskExecution(
                    job_id=task_id,
                    job_name=job_name,
                    status=status_enum,
                    started_at=started_at,
                    completed_at=completed_at or datetime.utcnow(),
                    duration_seconds=duration_seconds,
                    result=result_data,
                    error_message=error_message,
                    error_traceback=error_traceback
                )
                
                db.add(execution)
                await db.commit()
                
                logger.debug(f"已记录任务执行: {task_id} - {status}")
                return True
                
        except Exception as e:
            logger.error(f"记录任务执行失败 {task_id}: {e}")
            return False


# 全局事件记录器实例
event_recorder = EventRecorder()