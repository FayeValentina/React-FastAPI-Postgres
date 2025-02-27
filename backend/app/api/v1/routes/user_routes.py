from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Annotated, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.schemas.user import (
    UserCreate, UserResponse, UserUpdateFull, UserUpdatePartial
)
from app.crud.user import user
from app.db.base import get_async_session
from app.models.user import User
from app.api.v1.dependencies.current_user import (
    get_current_active_user,
    get_current_superuser
)

router = APIRouter(prefix="/users", tags=["users"])

@router.post("", response_model=UserResponse)
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
        return await user.create(db, obj_in=user_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{user_id}", response_model=UserResponse)
async def update_user_full(
    user_id: int,
    user_update: UserUpdateFull,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    完整更新用户信息
    
    只能更新自己的信息或者超级管理员可以更新任何用户
    """
    try:
        # 检查权限：只能修改自己或者超级管理员可以修改任何人
        if current_user.id != user_id and not current_user.is_superuser:
            raise HTTPException(
                status_code=403, 
                detail="Not enough permissions to update other users"
            )
            
        db_user = await user.get(db, id=user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return await user.update(db, db_obj=db_user, obj_in=user_update)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user_partial(
    user_id: int,
    user_update: UserUpdatePartial,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    部分更新用户信息
    
    只能更新自己的信息或者超级管理员可以更新任何用户
    """
    try:
        # 检查权限：只能修改自己或者超级管理员可以修改任何人
        if current_user.id != user_id and not current_user.is_superuser:
            raise HTTPException(
                status_code=403, 
                detail="Not enough permissions to update other users"
            )
            
        db_user = await user.get(db, id=user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return await user.update(db, db_obj=db_user, obj_in=user_update)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("", response_model=List[UserResponse])
async def get_users(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),  # 只有已认证用户可以查看用户列表
    name: Annotated[str | None, Query(min_length=2, description="用户名")] = None,
    age: Annotated[int | None, Query(ge=0, le=150, description="年龄")] = None,
    sort_by: Annotated[List[str], Query(description="排序字段")] = ["created_at"]
) -> List[UserResponse]:
    """
    获取用户列表
    
    需要认证权限
    """
    # TODO: 实现用户列表查询功能，包括过滤和排序
    # 目前简单返回所有用户
    result = await db.execute(select(User))
    return result.scalars().all()

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
    # 如果查看自己的信息，直接返回当前用户
    if current_user.id == user_id:
        return current_user
        
    # 非超级用户不能查看其他用户详情
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions to view other user details"
        )
        
    db_user = await user.get(db, id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return db_user

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
    db_user = await user.get(db, id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # 不能删除自己
    if current_user.id == user_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own account"
        )
        
    return await user.delete(db, id=user_id) 