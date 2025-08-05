from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete
from sqlalchemy.orm import selectinload

from app.models.schedule_event import ScheduleEvent, ScheduleEventType


class CRUDScheduleEvent:
    """调度事件CRUD操作"""
    
    @staticmethod
    async def get_events_by_job(
        db: AsyncSession,
        job_id: str,
        limit: int = 50
    ) -> List[ScheduleEvent]:
        """获取指定任务的事件历史"""
        result = await db.execute(
            select(ScheduleEvent)
            .where(ScheduleEvent.job_id == job_id)
            .order_by(ScheduleEvent.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_recent_events(
        db: AsyncSession,
        hours: int = 24,
        limit: int = 100
    ) -> List[ScheduleEvent]:
        """获取最近的调度事件"""
        start_time = datetime.utcnow() - timedelta(hours=hours)
        result = await db.execute(
            select(ScheduleEvent)
            .where(ScheduleEvent.created_at >= start_time)
            .order_by(ScheduleEvent.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_error_events(
        db: AsyncSession,
        days: int = 7,
        limit: int = 50
    ) -> List[ScheduleEvent]:
        """获取错误事件"""
        start_time = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(ScheduleEvent)
            .where(
                and_(
                    ScheduleEvent.created_at >= start_time,
                    ScheduleEvent.event_type == ScheduleEventType.ERROR
                )
            )
            .order_by(ScheduleEvent.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def cleanup_old_events(
        db: AsyncSession,
        days_to_keep: int = 30
    ) -> int:
        """清理旧的调度事件"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        result = await db.execute(
            select(ScheduleEvent.id)
            .where(ScheduleEvent.created_at < cutoff_date)
        )
        event_ids = [row[0] for row in result.all()]
        
        if event_ids:
            await db.execute(
                delete(ScheduleEvent)
                .where(ScheduleEvent.id.in_(event_ids))
            )
        
        await db.commit()
        return len(event_ids)
