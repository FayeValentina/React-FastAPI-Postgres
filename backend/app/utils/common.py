import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from starlette import status

logger = logging.getLogger(__name__)


def get_current_time() -> datetime:
    """获取当前UTC时间"""
    return datetime.now(timezone.utc)


def validate_page_size(
    page: int = 1,
    size: int = 10,
    max_size: int = 100
) -> tuple[int, int]:
    """
    验证分页参数
    :param page: 页码
    :param size: 每页数量
    :param max_size: 最大每页数量
    :return: (page, size)
    """
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page number must be greater than 0"
        )
    if size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page size must be greater than 0"
        )
    if size > max_size:
        size = max_size
    return page, size


def handle_error(error: Exception, custom_message: Optional[str] = None) -> None:
    """
    统一错误处理
    :param error: 异常
    :param custom_message: 自定义错误消息
    """
    logger.error(f"Error occurred: {str(error)}")
    if custom_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=custom_message
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(error)
    ) 