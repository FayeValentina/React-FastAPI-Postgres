from typing import Annotated, Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_async_session
from app.crud.user import user as crud_user
from app.models.user import User

# Error messages
ERROR_USER_NOT_FOUND = "User not found"
ERROR_INACTIVE_USER = "Inactive user"
ERROR_NOT_AUTHENTICATED = "Not authenticated"

async def get_current_user_from_request(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_session)]
) -> User:
    """
    从请求状态中获取当前用户
    
    这个依赖项在AuthMiddleware之后使用，依赖中间件已经验证了令牌
    并将用户信息存储在request.state.user_payload中
    """
    if not hasattr(request.state, "user_payload"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_NOT_AUTHENTICATED,
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    payload = request.state.user_payload
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=ERROR_NOT_AUTHENTICATED
        )
    
    user = await crud_user.get_by_email(db, email=username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_USER_NOT_FOUND
        )
    
    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user_from_request)]
) -> User:
    """
    获取当前活跃用户
    
    验证用户是否处于活跃状态
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_INACTIVE_USER
        )
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
    except HTTPException:
        return None

async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    """
    获取当前超级用户
    
    验证用户是否为超级用户
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user 