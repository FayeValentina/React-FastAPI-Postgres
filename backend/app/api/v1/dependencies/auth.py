from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from datetime import datetime

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """获取当前用户依赖项"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # TODO: 实现token验证和用户获取逻辑
    return {"user_id": 1, "username": "test_user"}

async def get_current_active_user(current_user = Depends(get_current_user)):
    """获取当前活跃用户依赖项"""
    if not current_user.get("is_active", True):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_optional_user(request: Request) -> Optional[dict]:
    """获取可选的用户信息依赖项"""
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None
    # TODO: 实现token验证和用户获取逻辑
    return {"user_id": 1, "username": "test_user"} 