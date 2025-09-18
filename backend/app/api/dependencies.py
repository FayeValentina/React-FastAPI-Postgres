from typing import Annotated, Optional
from fastapi import Depends, Header, HTTPException, Request, WebSocket, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.infrastructure.database.postgres_base import get_async_session
from app.modules.auth.repository import crud_user
from app.modules.auth.models import User
from app.core.exceptions import (
    AuthenticationError, 
    UserNotFoundError, 
    InactiveUserError,
    InsufficientPermissionsError
)
from app.core.security import verify_token
from app.core.config import settings

logger = logging.getLogger(__name__)

async def get_current_user_from_request(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_session)]
) -> User:
    """
    从请求状态中获取当前用户
    
    这个依赖项在AuthMiddleware之后使用，依赖中间件已经验证了令牌
    并将用户信息存储在request.state.user_payload中
    
    抛出:
        AuthenticationError: 如果用户未认证
        UserNotFoundError: 如果找不到对应的用户
    """
    # 检查请求状态中是否有用户payload
    if not hasattr(request.state, "user_payload"):
        raise AuthenticationError("未认证")
    
    payload = request.state.user_payload
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError("无效的令牌载荷")
    
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise AuthenticationError("无效的用户ID格式")
    
    # 从数据库查询用户信息
    user = await crud_user.get(db, id=user_id)
    if not user:
        logger.warning(f"有效令牌但找不到用户ID: {user_id}")
        raise UserNotFoundError()
    
    request.state.current_user = user
    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user_from_request)]
) -> User:
    """
    获取当前活跃用户
    
    验证用户是否处于活跃状态
    """
    if not current_user.is_active:
        raise InactiveUserError()
    return current_user

async def get_optional_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_session)]
) -> Optional[User]:
    """
    尝试获取当前用户，但如果用户未认证则返回None
    
    这个依赖项对于同时支持认证和非认证用户的端点很有用
    """
    try:
        return await get_current_user_from_request(request, db)
    except (AuthenticationError, UserNotFoundError, InactiveUserError):
        return None

async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    """
    获取当前超级用户
    
    验证用户是否为超级用户
    """
    if not current_user.is_superuser:
        raise InsufficientPermissionsError("权限不足")
    return current_user 


async def get_current_user_from_ws(
    ws: WebSocket,
    db: Annotated[AsyncSession, Depends(get_async_session)]
) -> User:
    """
    从 WebSocket 查询参数或 Authorization 头中获取并验证当前用户。

    - 优先从查询参数 `?token=` 读取访问令牌
    - 其次从 `Authorization: Bearer <token>` 读取
    - 验证失败时关闭连接并抛出认证错误
    """
    # 获取 token
    token: Optional[str] = None
    try:
        # query_params 在 Starlette 的 WebSocket 对象上可用
        token = ws.query_params.get("token")  # type: ignore[attr-defined]
    except Exception:
        token = None

    if not token:
        auth_header = ws.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(None, 1)[1]

    if not token:
        try:
            await ws.close(code=1008)
        finally:
            pass
        raise AuthenticationError("未提供认证凭据")

    is_valid, payload, _ = verify_token(token)
    if not is_valid or payload is None or payload.get("type") != "access_token":
        try:
            await ws.close(code=1008)
        finally:
            pass
        raise AuthenticationError("无效或过期的访问令牌")

    user_id_str = payload.get("sub")
    try:
        user_id = int(user_id_str)
    except (TypeError, ValueError):
        await ws.close(code=1008)
        raise AuthenticationError("无效的用户ID")

    user = await crud_user.get(db, id=user_id)
    if not user:
        await ws.close(code=1008)
        raise UserNotFoundError()
    if not user.is_active:
        await ws.close(code=1008)
        raise InactiveUserError()

    return user

    
async def verify_internal_access(
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
) -> None:
    """Ensure the request presents the expected internal API secret header."""
    expected = getattr(settings, "INTERNAL_API_SECRET", "")

    if not expected:
        logger.warning("INTERNAL_API_SECRET is not configured; denying internal access request")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Internal access required")

    if not x_internal_secret or x_internal_secret != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Internal access required")
