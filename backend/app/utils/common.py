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