from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete
from sqlalchemy.orm import selectinload

from app.models.schedule_event import ScheduleEvent, ScheduleEventType
from app.models.task_config import TaskConfig
from app.core.exceptions import DatabaseError
from app.utils.common import get_current_time


class CRUDScheduleEvent:
    """调度事件CRUD操作"""
    
    async def create(
        self,
        db: AsyncSession,
        config_id: int,
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
                config_id=config_id,
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
        config_id: int,
        limit: int = 50
    ) -> List[ScheduleEvent]:
        """根据任务配置ID获取事件历史"""
        result = await db.execute(
            select(ScheduleEvent)
            .where(ScheduleEvent.config_id == config_id)
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
        start_time = get_current_time() - timedelta(hours=hours)
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
        start_time = get_current_time() - timedelta(days=days)
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
        config_id: Optional[int] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """获取事件统计信息"""
        start_time = get_current_time() - timedelta(days=days)
        
        # 构建基础查询
        base_query = select(ScheduleEvent.event_type, func.count(ScheduleEvent.id))
        if config_id:
            base_query = base_query.where(
                and_(
                    ScheduleEvent.config_id == config_id,
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
            cutoff_date = get_current_time() - timedelta(days=days_to_keep)
            
            result = await db.execute(
                delete(ScheduleEvent)
                .where(ScheduleEvent.created_at < cutoff_date)
            )
            
            await db.commit()
            return result.rowcount
            
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"清理调度事件时出错: {str(e)}")
    
    async def get_global_stats(
        self,
        db: AsyncSession,
        days: int = 30
    ) -> Dict[str, Any]:
        """获取全局调度事件统计"""
        try:
            start_time = get_current_time() - timedelta(days=days)
            
            # 总事件数
            total_result = await db.execute(
                select(func.count(ScheduleEvent.id))
                .where(ScheduleEvent.created_at >= start_time)
            )
            total_events = total_result.scalar() or 0
            
            # 各类型统计
            type_result = await db.execute(
                select(ScheduleEvent.event_type, func.count(ScheduleEvent.id))
                .where(ScheduleEvent.created_at >= start_time)
                .group_by(ScheduleEvent.event_type)
            )
            
            type_stats = {}
            for event_type, count in type_result.all():
                type_stats[event_type.value] = count
            
            # 按任务配置统计
            config_result = await db.execute(
                select(TaskConfig.task_type, func.count(ScheduleEvent.id))
                .join(TaskConfig, ScheduleEvent.config_id == TaskConfig.id)
                .where(ScheduleEvent.created_at >= start_time)
                .group_by(TaskConfig.task_type)
            )
            
            config_stats = {}
            for task_type, count in config_result.all():
                config_stats[task_type.value] = count
            
            # 成功率
            success_count = type_stats.get("executed", 0)
            success_rate = (success_count / total_events * 100) if total_events > 0 else 0.0
            
            # 错误率
            error_count = type_stats.get("error", 0)
            error_rate = (error_count / total_events * 100) if total_events > 0 else 0.0
            
            return {
                "period_days": days,
                "total_events": total_events,
                "type_breakdown": type_stats,
                "config_breakdown": config_stats,
                "success_rate": success_rate,
                "error_rate": error_rate,
                "timestamp": get_current_time().isoformat()
            }
            
        except Exception as e:
            raise DatabaseError(f"获取全局调度统计数据时出错: {str(e)}")
    
    async def get_stats_by_config(
        self,
        db: AsyncSession,
        config_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """获取特定任务配置的调度事件统计"""
        try:
            start_time = get_current_time() - timedelta(days=days)
            
            # 总事件数
            total_result = await db.execute(
                select(func.count(ScheduleEvent.id))
                .where(
                    and_(
                        ScheduleEvent.config_id == config_id,
                        ScheduleEvent.created_at >= start_time
                    )
                )
            )
            total_events = total_result.scalar() or 0
            
            # 各类型统计
            type_result = await db.execute(
                select(ScheduleEvent.event_type, func.count(ScheduleEvent.id))
                .where(
                    and_(
                        ScheduleEvent.config_id == config_id,
                        ScheduleEvent.created_at >= start_time
                    )
                )
                .group_by(ScheduleEvent.event_type)
            )
            
            type_stats = {}
            for event_type, count in type_result.all():
                type_stats[event_type.value] = count
            
            # 成功率
            success_count = type_stats.get("executed", 0)
            success_rate = (success_count / total_events * 100) if total_events > 0 else 0.0
            
            # 错误率
            error_count = type_stats.get("error", 0) + type_stats.get("missed", 0)
            error_rate = (error_count / total_events * 100) if total_events > 0 else 0.0
            
            return {
                "config_id": config_id,
                "period_days": days,
                "total_events": total_events,
                "type_breakdown": type_stats,
                "success_rate": success_rate,
                "error_rate": error_rate,
                "timestamp": get_current_time().isoformat()
            }
            
        except Exception as e:
            raise DatabaseError(f"获取任务配置 {config_id} 的统计数据时出错: {str(e)}")
    
    async def get_events_by_job_pattern(
        self,
        db: AsyncSession,
        task_type_pattern: str = None,
        scheduler_type_pattern: str = None,
        limit: int = 50
    ) -> List[ScheduleEvent]:
        """根据job_id模式查询事件"""
        query = select(ScheduleEvent).options(selectinload(ScheduleEvent.task_config)).order_by(ScheduleEvent.created_at.desc())
        
        if task_type_pattern:
            # 例如: task_type_pattern = "cleanup" 匹配所有清理任务
            query = query.where(ScheduleEvent.job_id.like(f"{task_type_pattern}%"))
        
        if scheduler_type_pattern:
            # 例如: scheduler_type_pattern = "_cron_" 匹配所有cron任务
            query = query.where(ScheduleEvent.job_id.like(f"%{scheduler_type_pattern}%"))
        
        query = query.limit(limit)
        result = await db.execute(query)
        return result.scalars().all()


# 全局CRUD实例
crud_schedule_event = CRUDScheduleEvent()
