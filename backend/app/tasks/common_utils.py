"""
任务共享工具模块
"""
import asyncio
import logging
from datetime import datetime
from app.db.base import AsyncSessionLocal
from app.models.task_execution import TaskExecution, ExecutionStatus

logger = logging.getLogger(__name__)


def run_async_task(coro):
    """在Celery任务中运行异步函数的辅助函数"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


async def record_task_execution(
    task_id: str,
    job_name: str,
    start_time: datetime,
    status: ExecutionStatus,
    result=None,
    error=None,
    task_config_id=None
):
    """记录任务执行到数据库的通用函数"""
    try:
        async with AsyncSessionLocal() as db:
            execution = TaskExecution(
                task_config_id=task_config_id,
                job_id=task_id,
                job_name=job_name,
                status=status,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                result=result,
                error_message=str(error) if error else None
            )
            db.add(execution)
            await db.commit()
    except Exception as e:
        logger.error(f"记录任务执行失败: {e}")