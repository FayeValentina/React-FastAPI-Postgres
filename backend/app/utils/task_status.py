from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.task import TaskStatus
from app.models.task_execution import ExecutionStatus
from app.tasks.manager import TaskManager


class TaskStatusCalculator:
    """任务状态计算器"""
    
    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.manager = TaskManager(scheduler)
    
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
        
        # 2. 任务被暂停
        if pending:
            return TaskStatus.PAUSED
        
        # 3. 检查是否正在执行（查看最近的执行记录）
        try:
            latest_executions = await self.manager.get_job_executions(db, job_id, limit=1)
            if latest_executions:
                latest_execution = latest_executions[0]
                
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
        
        # 4. 有下次运行时间 - 已调度等待执行
        if next_run_time:
            return TaskStatus.SCHEDULED
        
        # 5. 默认状态 - 空闲（没有下次运行时间，也没有执行记录）
        return TaskStatus.IDLE


# 创建全局实例（延迟初始化）
_task_status_calculator: Optional[TaskStatusCalculator] = None


def get_task_status_calculator() -> TaskStatusCalculator:
    """获取任务状态计算器实例"""
    global _task_status_calculator
    if _task_status_calculator is None:
        from app.tasks.scheduler import task_scheduler
        _task_status_calculator = TaskStatusCalculator(task_scheduler.scheduler)
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