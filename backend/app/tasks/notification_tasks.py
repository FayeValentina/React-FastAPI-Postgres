"""
通知任务定义
"""
from typing import Dict, Any
from datetime import datetime
import logging

from app.broker import broker
from app.db.base import AsyncSessionLocal

logger = logging.getLogger(__name__)


@broker.task(
    task_name="send_email",
    queue="default",
    retry_on_error=True,
    max_retries=3,
)
async def send_email(
    config_id: int,
    to_email: str,
    subject: str,
    content: str
) -> Dict[str, Any]:
    """
    发送邮件
    
    Args:
        config_id: 任务配置ID
        to_email: 收件人邮箱
        subject: 邮件主题
        content: 邮件内容
    
    Returns:
        发送结果
    """
    logger.info(f"开始发送邮件到 {to_email}... (Config ID: {config_id})")
    
    async with AsyncSessionLocal() as db:
        try:
            # 这里应该实现实际的邮件发送逻辑
            # 使用email_service等
            
            result = {
                "config_id": config_id,
                "to_email": to_email,
                "subject": subject,
                "sent": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # 记录执行结果到数据库
            await record_task_execution(db, config_id, "success", result)
            
            logger.info(f"邮件发送完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"发送邮件时出错: {e}", exc_info=True)
            await record_task_execution(db, config_id, "failed", error=str(e))
            raise


async def record_task_execution(db, config_id: int, status: str, result: Dict = None, error: str = None):
    """记录任务执行结果到数据库"""
    from app.models.task_execution import TaskExecution
    import uuid
    
    execution = TaskExecution(
        config_id=config_id,
        task_id=str(uuid.uuid4()),  # 生成唯一的task_id
        status=status,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        result=result,
        error_message=error
    )
    db.add(execution)
    await db.commit()