import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi.responses import JSONResponse
# 导入需要的异常类，放在函数开头
from app.core.exceptions import AuthenticationError, ApiError

from fastapi import HTTPException
from starlette import status

from app.core.exceptions import (
    ApiError, 
    ValidationError,
    AuthenticationError
)

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
        raise ValidationError(detail="页码必须大于0")
    if size < 1:
        raise ValidationError(detail="每页数量必须大于0")
    if size > max_size:
        size = max_size
    return page, size


def handle_error(
    error: Exception, 
    custom_message: Optional[str] = None
) -> None:
    """
    统一错误处理
    
    将各种异常转换为HTTPException并抛出
    
    Args:
        error: 捕获的异常
        custom_message: 可选的自定义错误消息
    
    Raises:
        HTTPException: 转换后的HTTP异常
    """
    logger.error(f"错误发生: {str(error)}")
    
    # 如果已经是 ApiError，直接转换为 HTTPException
    if isinstance(error, ApiError):
        raise error.to_http_exception()
    
    # 否则，根据错误类型创建适当的 ApiError
    if isinstance(error, ValueError):
        detail = custom_message or str(error)
        raise ValidationError(detail=detail).to_http_exception()
    
    # 对于其他未处理的错误，返回通用服务器错误
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=custom_message or "服务器内部错误"
    )


def convert_exception_to_http_exception(
    error: Exception, 
    custom_message: Optional[str] = None
) -> HTTPException:
    """
    将各种异常转换为HTTPException但不抛出
    
    与handle_error不同，此函数返回HTTPException而不是抛出它
    
    Args:
        error: 捕获的异常
        custom_message: 可选的自定义错误消息
        
    Returns:
        HTTPException: 转换后的HTTP异常
    """
    # 记录错误
    logger.error(f"错误转换: {str(error)}")
    
    # 如果已经是 ApiError，直接转换
    if isinstance(error, ApiError):
        return error.to_http_exception()
    
    # 根据错误类型返回适当的异常
    if isinstance(error, ValueError):
        detail = custom_message or str(error)
        return ValidationError(detail=detail).to_http_exception()
        
    # 其他错误作为服务器内部错误处理
    detail = custom_message or "服务器内部错误"
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail
    )


def create_exception_handlers() -> Dict[Any, Any]:
    """
    创建全局异常处理程序字典
    
    返回可以直接传递给FastAPI应用或路由的异常处理程序字典
    
    Returns:
        Dict[Any, Any]: 异常处理程序字典
    """
    
    async def api_error_handler(request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    
    async def auth_error_handler(request, exc: AuthenticationError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers or {"WWW-Authenticate": "Bearer"}
        )
    
    return {
        ApiError: api_error_handler,
        AuthenticationError: auth_error_handler,
    } 