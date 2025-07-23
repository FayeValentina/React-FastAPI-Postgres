from fastapi import Request
from typing import Dict
from app.utils.common import get_current_time

async def request_context_dependency(request: Request) -> Dict:
    """
    提供请求上下文信息的全局依赖项
    
    从请求状态中获取信息，避免重复处理已由日志中间件处理的信息。
    
    Args:
        request: FastAPI 请求对象

    Returns:
        包含请求上下文信息的字典
    """
    # 使用已经由logging中间件设置的请求ID
    request_id = getattr(request.state, "request_id", None)
    
    # 获取用户信息（如果已认证）
    user_payload = getattr(request.state, "user_payload", None)
    username = user_payload.get("sub") if user_payload else None
    
    return {
        "client_host": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "request_id": request_id,
        "username": username,
        "timestamp": get_current_time()
    } 