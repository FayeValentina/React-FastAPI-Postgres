from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete
from sqlalchemy.orm import selectinload

from app.models.schedule_event import ScheduleEvent, ScheduleEventType
from app.models.task_config import TaskConfig
from app.core.exceptions import DatabaseError


class CRUDScheduleEvent:
    """调度事件CRUD操作"""
    
    async def create(
        self,
        db: AsyncSession,
        task_config_id: int,
        job_id: str,
        job_name: str,
        event_type: ScheduleEventType,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None
    ) -> ScheduleEvent:
        """创建调度事件"""
        try:
            db_obj = ScheduleEvent(
                task_config_id=task_config_id,
                job_id=job_id,
                job_name=job_name,
                event_type=event_type,
                result=result,
                error_message=error_message,
                error_traceback=error_traceback
            )
            
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
            
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"创建调度事件时出错: {str(e)}")
    
    async def get_events_by_job(
        self,
        db: AsyncSession,
        job_id: str,
        limit: int = 50
    ) -> List[ScheduleEvent]:
        """获取指定任务的事件历史"""
        result = await db.execute(
            select(ScheduleEvent)
            .options(selectinload(ScheduleEvent.task_config))
            .where(ScheduleEvent.job_id == job_id)
            .order_by(ScheduleEvent.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_events_by_config(
        self,
        db: AsyncSession,
        task_config_id: int,
        limit: int = 50
    ) -> List[ScheduleEvent]:
        """根据任务配置ID获取事件历史"""
        result = await db.execute(
            select(ScheduleEvent)
            .where(ScheduleEvent.task_config_id == task_config_id)
            .order_by(ScheduleEvent.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_recent_events(
        self,
        db: AsyncSession,
        hours: int = 24,
        limit: int = 100
    ) -> List[ScheduleEvent]:
        """获取最近的调度事件"""
        start_time = datetime.utcnow() - timedelta(hours=hours)
        result = await db.execute(
            select(ScheduleEvent)
            .options(selectinload(ScheduleEvent.task_config))
            .where(ScheduleEvent.created_at >= start_time)
            .order_by(ScheduleEvent.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_error_events(
        self,
        db: AsyncSession,
        days: int = 7,
        limit: int = 50
    ) -> List[ScheduleEvent]:
        """获取错误事件"""
        start_time = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(ScheduleEvent)
            .options(selectinload(ScheduleEvent.task_config))
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
    
    async def get_events_stats(
        self,
        db: AsyncSession,
        task_config_id: Optional[int] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """获取事件统计信息"""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        # 构建基础查询
        base_query = select(ScheduleEvent.event_type, func.count(ScheduleEvent.id))
        if task_config_id:
            base_query = base_query.where(
                and_(
                    ScheduleEvent.task_config_id == task_config_id,
                    ScheduleEvent.created_at >= start_time
                )
            )
        else:
            base_query = base_query.where(ScheduleEvent.created_at >= start_time)
        
        base_query = base_query.group_by(ScheduleEvent.event_type)
        
        result = await db.execute(base_query)
        stats = {event_type.value: 0 for event_type in ScheduleEventType}
        
        for event_type, count in result.all():
            stats[event_type] = count
        
        # 计算总数和成功率
        total = sum(stats.values())
        success_rate = (stats.get("executed", 0) / total * 100) if total > 0 else 0.0
        
        return {
            "stats": stats,
            "total_events": total,
            "success_rate": success_rate,
            "period_days": days
        }
    
    async def cleanup_old_events(
        self,
        db: AsyncSession,
        days_to_keep: int = 30
    ) -> int:
        """清理旧的调度事件"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            result = await db.execute(
                delete(ScheduleEvent)
                .where(ScheduleEvent.created_at < cutoff_date)
            )
            
            await db.commit()
            return result.rowcount
            
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"清理调度事件时出错: {str(e)}")


# 全局CRUD实例
crud_schedule_event = CRUDScheduleEvent()
