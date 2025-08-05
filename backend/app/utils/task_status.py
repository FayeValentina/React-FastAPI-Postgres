from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.task import TaskStatus
from app.models.task_execution import ExecutionStatus


class TaskStatusCalculator:
    """任务状态计算器"""
    
    def __init__(self, scheduler):
        self.scheduler = scheduler
    
    async def calculate_job_status(
        self, 
        db: AsyncSession, 
        job_id: str, 
        pending: bool,
        next_run_time: Optional[datetime],
        scheduler_running: bool
    ) -> TaskStatus:
        """计算任务的综合状态"""
        
        # 1. 调度器未运行 - 所有任务都是停止状态
        if not scheduler_running:
            return TaskStatus.STOPPED
        
        # 2. 检查任务是否被暂停
        # APScheduler 通过将 next_run_time 设置为 None 来暂停任务
        if next_run_time is None:
            try:
                job = self.scheduler.get_job(job_id)
                if job and hasattr(job, 'trigger') and job.trigger:
                    # 有触发器但 next_run_time 为 None，说明是暂停状态
                    return TaskStatus.PAUSED
            except Exception:
                pass
        
        # 3. pending 为 True 表示任务还在等待被添加到作业存储
        # 这通常发生在调度器还未启动时
        if pending:
            return TaskStatus.IDLE
        
        # 4. 检查是否正在执行（查看最近的执行记录）
        try:
            from app.crud.task_execution import CRUDTaskExecution
            latest_executions = await CRUDTaskExecution.get_recent_executions(db, hours=1, limit=1)
            # 过滤出当前job的执行记录
            job_executions = [e for e in latest_executions if e.job_id == job_id]
            if job_executions:
                latest_execution = job_executions[0]
                
                # 如果最近的执行状态是RUNNING
                if latest_execution.status == ExecutionStatus.RUNNING:
                    # 检查是否超时（比如运行超过1小时可能是异常）
                    if latest_execution.started_at:
                        running_duration = (datetime.utcnow() - latest_execution.started_at).total_seconds()
                        # 可以根据不同任务类型设置不同的超时时间
                        if running_duration > 3600:  # 1小时
                            return TaskStatus.TIMEOUT
                    return TaskStatus.RUNNING
                
                # 检查是否处于misfire状态（错过了执行时间）
                if next_run_time and next_run_time < datetime.now(timezone.utc):
                    # 如果下次运行时间已经过去，可能是misfire
                    time_diff = (datetime.now(timezone.utc) - next_run_time).total_seconds()
                    if time_diff > 60:  # 超过1分钟
                        return TaskStatus.MISFIRED
                
                # 如果最近执行失败
                if latest_execution.status == ExecutionStatus.FAILED:
                    # 对于有重复调度的任务（有next_run_time），即使失败也是SCHEDULED
                    if next_run_time:
                        return TaskStatus.SCHEDULED
                    # 对于一次性任务，失败就是失败
                    return TaskStatus.FAILED
        
        except Exception as e:
            # 记录错误但不影响状态判断
            import logging
            logging.error(f"获取任务执行历史失败: {e}")
        
        # 5. 有下次运行时间 - 已调度等待执行
        if next_run_time:
            return TaskStatus.SCHEDULED
        
        # 6. 默认状态 - 空闲
        # 没有下次运行时间，可能是一次性任务已完成或是其他情况
        return TaskStatus.IDLE
    
    async def get_job_execution_summary(self, db: AsyncSession, job_id: str, hours: int = 24):
        """获取任务执行摘要"""
        from app.crud.task_execution import CRUDTaskExecution
        from app.schemas.task import JobExecutionSummary
        
        executions = await CRUDTaskExecution.get_recent_executions(db, hours)
        job_executions = [e for e in executions if e.job_id == job_id]
        
        if not job_executions:
            return JobExecutionSummary(
                total_runs=0,
                successful_runs=0,
                failed_runs=0,
                success_rate=0.0,
                avg_duration=0.0,
                last_run=None,
                last_status=None,
                last_error=None
            )
        
        # 计算统计信息
        total = len(job_executions)
        successful = len([e for e in job_executions if e.status == ExecutionStatus.SUCCESS])
        durations = [e.duration_seconds for e in job_executions if e.duration_seconds]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        
        latest = max(job_executions, key=lambda x: x.started_at)
        
        return JobExecutionSummary(
            total_runs=total,
            successful_runs=successful,
            failed_runs=total - successful,
            success_rate=(successful / total * 100) if total > 0 else 0.0,
            avg_duration=avg_duration,
            last_run=latest.started_at.isoformat() if latest.started_at else None,
            last_status=latest.status.value if latest.status else None,
            last_error=latest.error_message if latest.error_message else None
        )
    
    async def get_job_recent_events(self, db: AsyncSession, job_id: str, limit: int = 10):
        """获取任务最近的事件"""
        from app.crud.schedule_event import CRUDScheduleEvent
        from app.schemas.task import ScheduleEventInfo
        
        events = await CRUDScheduleEvent.get_events_by_job(db, job_id, limit)
        
        return [
            ScheduleEventInfo(
                event_type=event.event_type.value,
                created_at=event.created_at.isoformat(),
                error_message=event.error_message,
                result=event.result
            )
            for event in events
        ]


# 创建全局实例（延迟初始化）
_task_status_calculator: Optional[TaskStatusCalculator] = None


def get_task_status_calculator() -> TaskStatusCalculator:
    """获取任务状态计算器实例"""
    global _task_status_calculator
    if _task_status_calculator is None:
        from app.tasks.schedulers import scheduler
        _task_status_calculator = TaskStatusCalculator(scheduler.scheduler)
    return _task_status_calculator


async def calculate_job_status(
    db: AsyncSession,
    job_id: str,
    pending: bool,
    next_run_time: Optional[datetime],
    scheduler_running: bool
) -> TaskStatus:
    """计算任务状态的便捷函数"""
    calculator = get_task_status_calculator()
    return await calculator.calculate_job_status(
        db, job_id, pending, next_run_time, scheduler_running
    )
