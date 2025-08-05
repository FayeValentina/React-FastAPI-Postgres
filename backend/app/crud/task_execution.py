from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete
from app.models.task_execution import TaskExecution, ExecutionStatus


class CRUDTaskExecution:
    """任务执行CRUD操作"""
    
    @staticmethod
    async def get_recent_executions(
        db: AsyncSession,
        hours: int = 24,
        limit: int = 100
    ) -> List[TaskExecution]:
        """获取最近的任务执行记录"""
        start_time = datetime.utcnow() - timedelta(hours=hours)
        result = await db.execute(
            select(TaskExecution)
            .where(TaskExecution.started_at >= start_time)
            .order_by(TaskExecution.started_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_execution_stats(
        db: AsyncSession,
        days: int = 7
    ) -> Dict[str, Any]:
        """获取执行统计"""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        # 总执行次数
        total_result = await db.execute(
            select(func.count(TaskExecution.id))
            .where(TaskExecution.started_at >= start_time)
        )
        total = total_result.scalar() or 0
        
        # 成功次数
        success_result = await db.execute(
            select(func.count(TaskExecution.id))
            .where(
                and_(
                    TaskExecution.started_at >= start_time,
                    TaskExecution.status == ExecutionStatus.SUCCESS
                )
            )
        )
        success = success_result.scalar() or 0
        
        # 平均执行时间
        avg_duration = await db.execute(
            select(func.avg(TaskExecution.duration_seconds))
            .where(
                and_(
                    TaskExecution.started_at >= start_time,
                    TaskExecution.status == ExecutionStatus.SUCCESS
                )
            )
        )
        
        return {
            "total_executions": total,
            "successful_executions": success,
            "failed_executions": total - success,
            "success_rate": (success / total * 100) if total > 0 else 0,
            "avg_duration_seconds": float(avg_duration.scalar() or 0)
        }
