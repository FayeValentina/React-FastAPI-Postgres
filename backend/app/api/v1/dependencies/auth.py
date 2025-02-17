from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import verify_token
from app.crud.user import user as crud_user
from app.db.base import get_async_session
from app.models.user import User

# Error messages
ERROR_INVALID_CREDENTIALS = "Could not validate credentials"
ERROR_INACTIVE_USER = "Inactive user"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ERROR_INVALID_CREDENTIALS,
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    is_valid, payload = verify_token(token)
    if not is_valid or not payload:
        raise credentials_exception
        
    username = payload.get("sub")
    if not username:
        raise credentials_exception
        
    user = await crud_user.get_by_email(db, email=username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_INACTIVE_USER
        )
    return current_user


async def get_optional_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_async_session)]
) -> Optional[User]:
    """获取可选的用户信息依赖项"""
    if not token:
        return None
        
    is_valid, payload = verify_token(token)
    if not is_valid or not payload:
        return None
            
    username = payload.get("sub")
    if not username:
        return None
            
    user = await crud_user.get_by_email(db, email=username)
    if user and user.is_active:
        return user
    
    return None 