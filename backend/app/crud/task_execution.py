from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete
from sqlalchemy.orm import selectinload

from app.models.task_execution import TaskExecution
from app.models.task_config import TaskConfig
from app.core.exceptions import DatabaseError
from app.utils.common import get_current_time


class CRUDTaskExecution:
    """任务执行CRUD操作"""
    
    async def create(
        self,
        db: AsyncSession,
        config_id: int,
        task_id: str,
        is_success: bool,
        started_at: datetime,
        completed_at: datetime,
        duration_seconds: Optional[float] = None,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None
    ) -> TaskExecution:
        """创建任务执行记录"""
        try:
            db_obj = TaskExecution(
                config_id=config_id,
                task_id=task_id,
                is_success=is_success,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
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
            raise DatabaseError(f"创建任务执行记录时出错: {str(e)}")
    
    
    async def get_by_task_id(
        self,
        db: AsyncSession,
        task_id: str
    ) -> Optional[TaskExecution]:
        """通过task_id获取执行记录"""
        result = await db.execute(
            select(TaskExecution)
            .options(selectinload(TaskExecution.task_config))
            .where(TaskExecution.task_id == task_id)
        )
        return result.scalar_one_or_none()
    
    async def get_latest_by_task_id(
        self,
        db: AsyncSession,
        task_id: str
    ) -> Optional[TaskExecution]:
        """通过task_id获取最新的执行记录"""
        result = await db.execute(
            select(TaskExecution)
            .where(TaskExecution.task_id == task_id)
            .order_by(TaskExecution.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_executions_by_config(
        self,
        db: AsyncSession,
        config_id: int,
        limit: int = 50
    ) -> List[TaskExecution]:
        """根据任务配置ID获取执行记录"""
        result = await db.execute(
            select(TaskExecution)
            .where(TaskExecution.config_id == config_id)
            .order_by(TaskExecution.started_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_recent_executions(
        self,
        db: AsyncSession,
        hours: int = 24,
        limit: int = 100
    ) -> List[TaskExecution]:
        """获取最近的任务执行记录"""
        start_time = get_current_time() - timedelta(hours=hours)
        result = await db.execute(
            select(TaskExecution)
            .options(selectinload(TaskExecution.task_config))
            .where(TaskExecution.started_at >= start_time)
            .order_by(TaskExecution.started_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_failed_executions(
        self,
        db: AsyncSession,
        days: int = 7,
        limit: int = 50
    ) -> List[TaskExecution]:
        """获取失败的执行记录"""
        start_time = get_current_time() - timedelta(days=days)
        result = await db.execute(
            select(TaskExecution)
            .options(selectinload(TaskExecution.task_config))
            .where(
                and_(
                    TaskExecution.started_at >= start_time,
                    TaskExecution.is_success == False
                )
            )
            .order_by(TaskExecution.started_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    
    async def cleanup_old_executions(
        self,
        db: AsyncSession,
        days_to_keep: int = 90
    ) -> int:
        """清理旧的执行记录"""
        try:
            cutoff_date = get_current_time() - timedelta(days=days_to_keep)
            
            result = await db.execute(
                delete(TaskExecution)
                .where(TaskExecution.created_at < cutoff_date)
            )
            
            await db.commit()
            return result.rowcount
            
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"清理任务执行记录时出错: {str(e)}")
    
    async def get_global_stats(
        self,
        db: AsyncSession,
        days: int = 30
    ) -> Dict[str, Any]:
        """获取全局统计数据"""
        try:
            start_time = get_current_time() - timedelta(days=days)
            
            # 总执行次数
            total_result = await db.execute(
                select(func.count(TaskExecution.id))
                .where(TaskExecution.started_at >= start_time)
            )
            total_executions = total_result.scalar() or 0
            
            # 成功和失败统计
            success_result = await db.execute(
                select(func.count(TaskExecution.id))
                .where(and_(
                    TaskExecution.started_at >= start_time,
                    TaskExecution.is_success == True
                ))
            )
            success_count = success_result.scalar() or 0
            
            failed_result = await db.execute(
                select(func.count(TaskExecution.id))
                .where(and_(
                    TaskExecution.started_at >= start_time,
                    TaskExecution.is_success == False
                ))
            )
            failed_count = failed_result.scalar() or 0
            
            # 按任务类型统计
            type_result = await db.execute(
                select(TaskConfig.task_type, func.count(TaskExecution.id))
                .join(TaskConfig, TaskExecution.config_id == TaskConfig.id)
                .where(TaskExecution.started_at >= start_time)
                .group_by(TaskConfig.task_type)
            )
            
            type_stats = {}
            for task_type, count in type_result.all():
                type_stats[str(task_type)] = count
            
            # 平均执行时间
            avg_duration_result = await db.execute(
                select(func.avg(TaskExecution.duration_seconds))
                .where(
                    and_(
                        TaskExecution.started_at >= start_time,
                        TaskExecution.is_success == True,
                        TaskExecution.duration_seconds.isnot(None)
                    )
                )
            )
            avg_duration = float(avg_duration_result.scalar() or 0.0)
            
            # 成功率和失败率
            success_rate = (success_count / total_executions * 100) if total_executions > 0 else 0.0
            failure_rate = (failed_count / total_executions * 100) if total_executions > 0 else 0.0
            
            return {
                "period_days": days,
                "total_executions": total_executions,
                "success_count": success_count,
                "failed_count": failed_count,
                "type_breakdown": type_stats,
                "success_rate": success_rate,
                "failure_rate": failure_rate,
                "avg_duration_seconds": avg_duration,
                "timestamp": get_current_time().isoformat()
            }
            
        except Exception as e:
            raise DatabaseError(f"获取全局统计数据时出错: {str(e)}")
    
    async def get_stats_by_config(
        self,
        db: AsyncSession,
        config_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """获取特定任务配置的执行统计数据"""
        try:
            start_time = get_current_time() - timedelta(days=days)
            
            # 总执行次数
            total_result = await db.execute(
                select(func.count(TaskExecution.id))
                .where(
                    and_(
                        TaskExecution.config_id == config_id,
                        TaskExecution.started_at >= start_time
                    )
                )
            )
            total_executions = total_result.scalar() or 0
            
            # 成功和失败统计
            success_result = await db.execute(
                select(func.count(TaskExecution.id))
                .where(
                    and_(
                        TaskExecution.config_id == config_id,
                        TaskExecution.started_at >= start_time,
                        TaskExecution.is_success == True
                    )
                )
            )
            success_count = success_result.scalar() or 0
            
            failed_result = await db.execute(
                select(func.count(TaskExecution.id))
                .where(
                    and_(
                        TaskExecution.config_id == config_id,
                        TaskExecution.started_at >= start_time,
                        TaskExecution.is_success == False
                    )
                )
            )
            failed_count = failed_result.scalar() or 0
            
            # 平均执行时间
            avg_duration_result = await db.execute(
                select(func.avg(TaskExecution.duration_seconds))
                .where(
                    and_(
                        TaskExecution.config_id == config_id,
                        TaskExecution.started_at >= start_time,
                        TaskExecution.is_success == True,
                        TaskExecution.duration_seconds.isnot(None)
                    )
                )
            )
            avg_duration = float(avg_duration_result.scalar() or 0.0)
            
            # 成功率和失败率
            success_rate = (success_count / total_executions * 100) if total_executions > 0 else 0.0
            failure_rate = (failed_count / total_executions * 100) if total_executions > 0 else 0.0
            
            return {
                "config_id": config_id,
                "period_days": days,
                "total_executions": total_executions,
                "success_count": success_count,
                "failed_count": failed_count,
                "success_rate": success_rate,
                "failure_rate": failure_rate,
                "avg_duration_seconds": avg_duration,
                "timestamp": get_current_time().isoformat()
            }
            
        except Exception as e:
            raise DatabaseError(f"获取任务配置 {config_id} 的执行统计数据时出错: {str(e)}")


# 全局CRUD实例
crud_task_execution = CRUDTaskExecution()
