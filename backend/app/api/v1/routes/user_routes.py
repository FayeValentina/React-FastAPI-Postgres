from fastapi import APIRouter, Depends, Query
from typing import Annotated, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, desc, asc

from app.schemas.user import (
    UserCreate, UserResponse, UserUpdate
)
from app.crud.user import user
from app.db.base import get_async_session
from app.models.user import User
from app.dependencies.current_user import (
    get_current_active_user,
    get_current_superuser
)
from app.core.exceptions import (
    UserNotFoundError,
    InsufficientPermissionsError
)
from app.utils.common import handle_error

router = APIRouter(prefix="/users", tags=["users"])

@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    user_data: UserCreate, 
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_superuser)  # 只有超级用户可以创建用户
):
    """
    创建新用户
    
    需要超级管理员权限
    """
    try:
        return await user.create_with_validation(db, obj_in=user_data)
    except Exception as e:
        raise handle_error(e)

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
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
        # 检查权限：只能修改自己或者超级管理员可以修改任何人
        if current_user.id != user_id and not current_user.is_superuser:
            raise InsufficientPermissionsError("没有足够权限更新其他用户")
            
        db_user = await user.get(db, id=user_id)
        if not db_user:
            raise UserNotFoundError()
        
        return await user.update(db, db_obj=db_user, obj_in=user_update)
    except Exception as e:
        raise handle_error(e)

@router.get("", response_model=List[UserResponse])
async def get_users(
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
    # 构建查询
    query = select(User)
    
    # 应用过滤条件
    filters = []
    if name:
        filters.append(or_(
            User.username.ilike(f"%{name}%"),
            User.full_name.ilike(f"%{name}%")
        ))
    
    if email:
        filters.append(User.email.ilike(f"%{email}%"))
    
    if age is not None:
        filters.append(User.age == age)
    
    if is_active is not None:
        filters.append(User.is_active == is_active)
    else:
        # 非超级用户默认只能看到已激活用户
        if not current_user.is_superuser:
            filters.append(User.is_active == True)
    
    if filters:
        query = query.where(and_(*filters))
    
    # 应用排序
    for sort_field in sort_by:
        # 检查是否是降序排序（字段名前有'-'符号）
        if sort_field.startswith('-'):
            field_name = sort_field[1:]
            # 确保字段存在于User模型中
            if hasattr(User, field_name):
                query = query.order_by(desc(getattr(User, field_name)))
        else:
            # 确保字段存在于User模型中
            if hasattr(User, sort_field):
                query = query.order_by(asc(getattr(User, sort_field)))
    
    # 执行查询
    result = await db.execute(query)
    users = result.scalars().all()
    
    return users

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    获取指定用户信息
    
    需要认证权限
    """
    try:
        # 如果查看自己的信息，直接返回当前用户
        if current_user.id == user_id:
            return current_user
            
        # 非超级用户不能查看其他用户详情
        if not current_user.is_superuser:
            raise InsufficientPermissionsError("没有足够权限查看其他用户详情")
            
        db_user = await user.get(db, id=user_id)
        if not db_user:
            raise UserNotFoundError()
            
        return db_user
    except Exception as e:
        raise handle_error(e)

@router.delete("/{user_id}", response_model=UserResponse)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_superuser)  # 只有超级用户可以删除用户
) -> UserResponse:
    """
    删除用户
    
    需要超级管理员权限
    """
    try:
        db_user = await user.get(db, id=user_id)
        if not db_user:
            raise UserNotFoundError()
            
        # 不能删除自己
        if current_user.id == user_id:
            raise ValueError("不能删除自己的账户")
            
        return await user.delete(db, id=user_id)
    except Exception as e:
        raise handle_error(e) 