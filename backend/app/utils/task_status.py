from typing import Optional
from datetime import datetime
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
                
                # 如果最近的执行状态是RUNNING，则任务正在执行
                if latest_execution.status == ExecutionStatus.RUNNING:
                    return TaskStatus.RUNNING
                
                # 如果最近执行失败且没有下次运行时间，标记为失败
                if (latest_execution.status == ExecutionStatus.FAILED and 
                    next_run_time is None):
                    return TaskStatus.FAILED
        
        except Exception:
            # 如果查询执行历史失败，忽略错误，继续其他判断
            pass
        
        # 4. 有下次运行时间 - 已调度等待执行
        if next_run_time:
            return TaskStatus.SCHEDULED
        
        # 5. 默认状态 - 空闲
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