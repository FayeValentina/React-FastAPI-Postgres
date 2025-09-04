from fastapi import APIRouter, Depends, Query, Request
from typing import Annotated, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.schemas import (
    UserCreate, UserResponse, UserUpdate
)
from app.infrastructure.database.postgres_base import get_async_session
from app.modules.auth.models import User
from app.api.dependencies import (
    get_current_active_user,
    get_current_superuser
)
from app.infrastructure.utils.common import handle_error
from app.infrastructure.cache.cache_decorators import cache, invalidate
from app.constant.cache_tags import CacheTags
from app.modules.auth.service import auth_service

router = APIRouter(prefix="/users", tags=["users"])

@router.post("", response_model=UserResponse, status_code=201)
@invalidate([CacheTags.USER_LIST])
async def create_user(
    request: Request,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_superuser)  # 只有超级用户可以创建用户
):
    """
    创建新用户
    
    需要超级管理员权限
    """
    try:
        return await auth_service.create_user(db=db, user_data=user_data)
    except Exception as e:
        raise handle_error(e)

@router.patch("/{user_id}", response_model=UserResponse)
@invalidate([CacheTags.USER_PROFILE, CacheTags.USER_LIST])
async def update_user(
    request: Request,
    user_id: int,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    更新用户信息（支持部分更新）
    
    只能更新自己的信息或者超级管理员可以更新任何用户
    """
    try:
        return await auth_service.update_user(db=db, user_id=user_id, user_update=user_update, current_user=current_user)
    except Exception as e:
        raise handle_error(e)

@router.get("", response_model=List[UserResponse])
@cache([CacheTags.USER_LIST],exclude_params=["request","db","current_user"])
async def get_users(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),  # 只有已认证用户可以查看用户列表
    name: Annotated[str | None, Query(min_length=2, description="用户名或全名")] = None,
    email: Annotated[str | None, Query(description="邮箱地址")] = None,
    age: Annotated[int | None, Query(ge=0, le=150, description="年龄")] = None,
    is_active: Annotated[bool | None, Query(description="是否激活")] = None,
    sort_by: Annotated[List[str], Query(description="排序字段，前缀'-'表示降序")] = ["created_at"]
) -> List[UserResponse]:
    """
    获取用户列表
    
    需要认证权限。
    
    支持过滤条件：
    - name: 用户名或全名（模糊匹配）
    - email: 邮箱地址（模糊匹配）
    - age: 精确年龄匹配
    - is_active: 是否激活
    
    支持排序：
    - 默认按创建时间排序
    - 在字段名前加'-'表示降序排序，例如：-created_at
    - 支持多字段排序
    """
    try:
        return await auth_service.get_users(
            db=db,
            current_user=current_user,
            name=name,
            email=email,
            age=age,
            is_active=is_active,
            sort_by=sort_by,
        )
    except Exception as e:
        raise handle_error(e)

@router.get("/{user_id}", response_model=UserResponse)
@cache(tags=[CacheTags.USER_PROFILE],exclude_params=["request","db","current_user"])
async def get_user(
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    获取指定用户信息
    
    需要认证权限
    """
    try:
        return await auth_service.get_user(db=db, user_id=user_id, current_user=current_user)
    except Exception as e:
        raise handle_error(e)

@router.delete("/{user_id}", response_model=UserResponse)
@invalidate([CacheTags.USER_PROFILE, CacheTags.USER_LIST])
async def delete_user(
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_superuser)  # 只有超级用户可以删除用户
) -> UserResponse:
    """
    删除用户
    
    需要超级管理员权限
    """
    try:
        return await auth_service.delete_user(db=db, user_id=user_id, current_user=current_user)
    except Exception as e:
        raise handle_error(e)
