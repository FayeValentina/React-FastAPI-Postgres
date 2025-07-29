from typing import Annotated, Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.base import get_async_session
from app.crud.user import user as crud_user
from app.models.user import User
from app.core.exceptions import (
    AuthenticationError, 
    UserNotFoundError, 
    InactiveUserError,
    InsufficientPermissionsError
)

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
    
    # 获取用户信息
    user = await crud_user.get(db, id=user_id)
    if not user:
        # 记录这种情况，因为这意味着有效的令牌但用户不存在
        logger.warning(f"有效令牌但找不到用户ID: {user_id}")
        raise UserNotFoundError()
    
    # 将完整用户对象设置到请求状态中，以便后续使用
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