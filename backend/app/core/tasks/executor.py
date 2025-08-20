"""
任务执行器基础设施
提供任务执行的核心功能
"""
import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskExecutor:
    """任务执行器"""
    
    @staticmethod
    async def create_execution_record(
        config_id: Optional[int],
        task_id: str,
        status = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        error_message: Optional[str] = None
    ) -> None:
        """创建任务执行记录"""
        from app.db.base import AsyncSessionLocal
        from app.crud.task_execution import crud_task_execution
        from app.core.tasks.registry import ExecutionStatus
        
        if status is None:
            status = ExecutionStatus.RUNNING
            
        async with AsyncSessionLocal() as db:
            await crud_task_execution.create(
                db=db,
                config_id=config_id,
                task_id=task_id,
                status=status,
                started_at=started_at or datetime.utcnow(),
                completed_at=completed_at,
                error_message=error_message
            )
    
    @staticmethod
    async def update_execution_record(
        task_id: str,
        status,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        completed_at: Optional[datetime] = None
    ) -> Optional[Any]:
        """更新任务执行记录并返回执行记录"""
        from app.db.base import AsyncSessionLocal
        from app.crud.task_execution import crud_task_execution
        
        async with AsyncSessionLocal() as db:
            execution = await crud_task_execution.get_by_task_id(db, task_id)
            if execution:
                await crud_task_execution.update_status(
                    db=db,
                    execution_id=execution.id,
                    status=status,
                    completed_at=completed_at or datetime.utcnow(),
                    result=result,
                    error_message=error
                )
                return execution
            return None
    
    @staticmethod
    def generate_task_id() -> str:
        """生成任务ID"""
        return str(uuid.uuid4())