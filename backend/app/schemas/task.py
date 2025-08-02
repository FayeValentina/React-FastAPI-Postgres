from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.task_execution import ExecutionStatus


class JobInfo(BaseModel):
    """任务信息"""
    id: str
    name: str
    trigger: str
    next_run_time: Optional[datetime] = None
    pending: bool = False
    
    # 详细信息（可选）
    func: Optional[str] = None
    args: Optional[List[Any]] = None
    kwargs: Optional[Dict[str, Any]] = None
    executor: Optional[str] = None
    max_instances: Optional[int] = None
    misfire_grace_time: Optional[int] = None
    coalesce: Optional[bool] = None


class TaskExecutionResponse(BaseModel):
    """任务执行历史响应"""
    id: int
    job_id: str
    job_name: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class JobStatsResponse(BaseModel):
    """任务统计响应"""
    total_runs: int
    successful_runs: int
    failed_runs: int
    success_rate: float
    avg_duration_seconds: float