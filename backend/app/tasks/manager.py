from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from apscheduler.job import Job
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
import logging

from app.models.task_execution import TaskExecution, ExecutionStatus

logger = logging.getLogger(__name__)


class TaskManager:
    """任务管理器 - 主要管理执行历史"""
    
    def __init__(self, scheduler):
        self.scheduler = scheduler
    
    async def record_execution(
        self,
        db: AsyncSession,
        job_id: str,
        job_name: str,
        status: ExecutionStatus,
        started_at: datetime,
        completed_at: Optional[datetime] = None,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None
    ) -> TaskExecution:
        """记录任务执行"""
        duration = None
        if completed_at and started_at:
            duration = (completed_at - started_at).total_seconds()
        
        execution = TaskExecution(
            job_id=job_id,
            job_name=job_name,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            result=result,
            error_message=error_message,
            error_traceback=error_traceback
        )
        
        db.add(execution)
        await db.commit()
        await db.refresh(execution)
        
        return execution
    
    async def get_job_executions(
        self,
        db: AsyncSession,
        job_id: str,
        limit: int = 50
    ) -> List[TaskExecution]:
        """获取任务的执行历史"""
        result = await db.execute(
            select(TaskExecution)
            .where(TaskExecution.job_id == job_id)
            .order_by(TaskExecution.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_job_stats(
        self,
        db: AsyncSession,
        job_id: str
    ) -> Dict[str, Any]:
        """获取任务执行统计"""
        # 总执行次数
        total_result = await db.execute(
            select(func.count(TaskExecution.id))
            .where(TaskExecution.job_id == job_id)
        )
        total_runs = total_result.scalar() or 0
        
        # 成功次数
        success_result = await db.execute(
            select(func.count(TaskExecution.id))
            .where(
                TaskExecution.job_id == job_id,
                TaskExecution.status == ExecutionStatus.SUCCESS
            )
        )
        successful_runs = success_result.scalar() or 0
        
        # 平均执行时间
        avg_duration_result = await db.execute(
            select(func.avg(TaskExecution.duration_seconds))
            .where(
                TaskExecution.job_id == job_id,
                TaskExecution.status == ExecutionStatus.SUCCESS
            )
        )
        avg_duration = avg_duration_result.scalar()
        
        return {
            'total_runs': total_runs,
            'successful_runs': successful_runs,
            'failed_runs': total_runs - successful_runs,
            'success_rate': (successful_runs / total_runs * 100) if total_runs > 0 else 0,
            'avg_duration_seconds': float(avg_duration) if avg_duration else 0
        }
    
    def get_all_jobs(self) -> List[Job]:
        """获取所有任务"""
        return self.scheduler.get_jobs()
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """获取单个任务"""
        return self.scheduler.get_job(job_id)
    
    async def cleanup_old_executions(
        self,
        db: AsyncSession,
        days_to_keep: int = 30
    ) -> int:
        """清理旧的执行记录"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        result = await db.execute(
            select(TaskExecution)
            .where(TaskExecution.created_at < cutoff_date)
        )
        old_executions = result.scalars().all()
        
        for execution in old_executions:
            await db.delete(execution)
        
        await db.commit()
        return len(old_executions)