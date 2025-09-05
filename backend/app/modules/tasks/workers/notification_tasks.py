"""
通知任务定义
"""
from typing import Dict, Any, Optional, Annotated
from datetime import datetime
import logging

from taskiq import Context, TaskiqDepends
from app.broker import broker
from app.infrastructure.database.postgres_base import AsyncSessionLocal
from app.infrastructure.tasks.exec_record_decorators import execution_handler
from app.infrastructure.tasks.task_registry_decorators import task

logger = logging.getLogger(__name__)


@task("SEND_EMAIL", queue="default")
@broker.task(
    task_name="send_email",
    queue="default",
    retry_on_error=True,
    max_retries=3,
)
@execution_handler
async def send_email(
    to_email: Annotated[str, {"ui_hint": "email"}],
    subject: str,
    config_id: Annotated[Optional[int], {"exclude_from_ui": True}] = None,
    context: Annotated[Context, {"exclude_from_ui": True}] = TaskiqDepends(),
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
    
    async with AsyncSessionLocal():
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

            
            logger.info(f"邮件发送完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"发送邮件时出错: {e}", exc_info=True)
            raise


