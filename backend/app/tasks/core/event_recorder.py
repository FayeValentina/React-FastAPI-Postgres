"""
事件记录器 - 独立的调度和执行事件记录组件
从HybridScheduler中提取出来，专注于事件记录功能
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from app.db.base import AsyncSessionLocal

logger = logging.getLogger(__name__)


class EventRecorder:
    """事件记录器，负责记录调度和执行事件到数据库"""
    
    @staticmethod
    async def record_schedule_event(
        job_id: str,
        event_type: str,
        job_config: Optional[Dict[str, Any]] = None,
        result: Any = None,
        error: Optional[str] = None,
        traceback: Optional[str] = None
    ) -> bool:
        """
        记录调度事件到数据库
        
        Args:
            job_id: 任务ID
            event_type: 事件类型 ('scheduled', 'schedule_error', 'missed')
            job_config: 任务配置信息
            result: 执行结果
            error: 错误信息
            traceback: 错误堆栈
            
        Returns:
            bool: 记录是否成功
        """
        try:
            async with AsyncSessionLocal() as db:
                from app.models.schedule_event import ScheduleEvent, ScheduleEventType
                
                # 生成任务名称
                job_name = EventRecorder._generate_job_name(job_id, job_config or {})
                
                # 映射事件类型
                event_type_map = {
                    'scheduled': ScheduleEventType.SCHEDULED,
                    'schedule_error': ScheduleEventType.ERROR,
                    'missed': ScheduleEventType.MISSED,
                    'executed': ScheduleEventType.EXECUTED
                }
                
                event_type_enum = event_type_map.get(event_type, ScheduleEventType.EXECUTED)
                
                # 处理结果数据
                result_data = None
                if result is not None:
                    if isinstance(result, dict):
                        result_data = result
                    else:
                        result_data = {'result': str(result)}
                
                # 创建调度事件记录
                event = ScheduleEvent(
                    job_id=job_id,
                    job_name=job_name,
                    event_type=event_type_enum,
                    result=result_data,
                    error_message=error,
                    error_traceback=traceback
                )
                
                db.add(event)
                await db.commit()
                
                logger.info(f"事件记录器已记录调度事件: {job_id} - {event_type}")
                return True
                
        except Exception as e:
            logger.error(f"记录调度事件失败 {job_id}: {e}")
            return False
    
    @staticmethod
    async def record_execution_event(
        task_id: str,
        task_name: str,
        status: str,
        result: Any = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None
    ) -> bool:
        """
        记录任务执行事件
        
        Args:
            task_id: Celery任务ID
            task_name: 任务名称
            status: 执行状态
            result: 执行结果
            error: 错误信息
            started_at: 开始时间
            finished_at: 结束时间
            
        Returns:
            bool: 记录是否成功
        """
        try:
            async with AsyncSessionLocal() as db:
                from app.models.schedule_event import ScheduleEvent, ScheduleEventType
                
                # 映射状态到事件类型
                status_map = {
                    'SUCCESS': ScheduleEventType.EXECUTED,
                    'FAILURE': ScheduleEventType.ERROR,  
                    'RETRY': ScheduleEventType.ERROR,
                    'REVOKED': ScheduleEventType.ERROR
                }
                
                event_type = status_map.get(status, ScheduleEventType.EXECUTED)
                
                # 处理结果数据
                result_data = None
                if result is not None:
                    if isinstance(result, dict):
                        result_data = result
                    else:
                        result_data = {'result': str(result), 'status': status}
                elif status:
                    result_data = {'status': status}
                
                # 创建执行事件记录
                event = ScheduleEvent(
                    job_id=task_id,
                    job_name=f"执行任务: {task_name}",
                    event_type=event_type,
                    result=result_data,
                    error_message=error,
                    created_at=started_at or datetime.utcnow()
                )
                
                db.add(event)
                await db.commit()
                
                logger.info(f"事件记录器已记录执行事件: {task_id} - {status}")
                return True
                
        except Exception as e:
            logger.error(f"记录执行事件失败 {task_id}: {e}")
            return False
    
    @staticmethod
    def _generate_job_name(job_id: str, job_config: Dict[str, Any]) -> str:
        """根据任务配置生成友好的任务名称"""
        job_type = job_config.get('type', 'unknown')
        
        if job_type == 'bot_scraping':
            bot_name = job_config.get('bot_config_name', 'Unknown') 
            return f"Bot自动爬取: {bot_name}"
        elif job_type == 'cleanup':
            days_old = job_config.get('days_old', 30)
            return f"数据清理: {days_old}天前"
        elif job_type == 'custom':
            task_name = job_config.get('celery_task_name', 'custom_task')
            return f"自定义任务: {task_name}"
        else:
            return f"调度任务: {job_id}"
    
    @staticmethod
    def record_schedule_event_sync(
        job_id: str,
        event_type: str,
        job_config: Optional[Dict[str, Any]] = None,
        result: Any = None,
        error: Optional[str] = None,
        traceback: Optional[str] = None
    ):
        """
        同步版本的调度事件记录，用于事件监听器
        """
        asyncio.create_task(EventRecorder.record_schedule_event(
            job_id, event_type, job_config, result, error, traceback
        ))
    
    @staticmethod
    def record_execution_event_sync(
        task_id: str,
        task_name: str,
        status: str,
        result: Any = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None
    ):
        """
        同步版本的执行事件记录
        """
        asyncio.create_task(EventRecorder.record_execution_event(
            task_id, task_name, status, result, error, started_at, finished_at
        ))