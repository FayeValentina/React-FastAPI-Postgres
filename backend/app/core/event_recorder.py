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
        task_config_id: Optional[int] = None,
        job_name: str = None,
        result: Any = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None
    ) -> bool:
        """
        记录调度事件到 ScheduleEvent 表
        """
        try:
            async with AsyncSessionLocal() as db:
                from app.crud.schedule_event import crud_schedule_event
                from app.models.schedule_event import ScheduleEventType

                event_type_map = {
                    'executed': ScheduleEventType.EXECUTED,
                    'error': ScheduleEventType.ERROR,
                    'missed': ScheduleEventType.MISSED,
                    'scheduled': ScheduleEventType.SCHEDULED,
                    'paused': ScheduleEventType.PAUSED,
                    'resumed': ScheduleEventType.RESUMED
                }
                event_type_enum = event_type_map.get(event_type, ScheduleEventType.EXECUTED)

                if task_config_id is None:
                    try:
                        task_config_id = int(job_id)
                    except (ValueError, TypeError):
                        task_config_id = None

                result_data = None
                if result is not None:
                    result_data = {'result': str(result)} if not isinstance(result, dict) else result

                if task_config_id is None:
                    logger.warning(f"无法为job_id {job_id} 关联task_config_id，跳过事件记录")
                    return False

                await crud_schedule_event.create(
                    db=db,
                    task_config_id=task_config_id,
                    job_id=job_id,
                    job_name=job_name or job_id,
                    event_type=event_type_enum,
                    result=result_data,
                    error_message=error_message,
                    error_traceback=error_traceback
                )

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
        task_config_id: Optional[int] = None,
        completed_at: Optional[datetime] = None,
        result: Any = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None
    ) -> bool:
        """
        记录任务执行到 TaskExecution 表
        """
        try:
            async with AsyncSessionLocal() as db:
                from app.crud.task_execution import crud_task_execution
                from app.models.task_execution import ExecutionStatus

                status_map = {
                    'SUCCESS': ExecutionStatus.SUCCESS,
                    'FAILED': ExecutionStatus.FAILED,
                    'TIMEOUT': ExecutionStatus.TIMEOUT,
                    'RUNNING': ExecutionStatus.RUNNING
                }
                status_enum = status_map.get(status, ExecutionStatus.FAILED)

                duration_seconds = (completed_at - started_at).total_seconds() if started_at and completed_at else None

                result_data = None
                if result is not None:
                    result_data = {'result': str(result)} if not isinstance(result, dict) else result

                if task_config_id is None:
                    logger.warning(f"无法为task_id {task_id} 关联task_config_id，跳过执行记录")
                    return False

                await crud_task_execution.create(
                    db=db,
                    task_config_id=task_config_id,
                    job_id=task_id,
                    job_name=job_name,
                    status=status_enum,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_seconds=duration_seconds,
                    result=result_data,
                    error_message=error_message,
                    error_traceback=error_traceback
                )

                logger.debug(f"已记录任务执行: {task_id} - {status}")
                return True

        except Exception as e:
            logger.error(f"记录任务执行失败 {task_id}: {e}")
            return False


# 全局事件记录器实例
event_recorder = EventRecorder()
