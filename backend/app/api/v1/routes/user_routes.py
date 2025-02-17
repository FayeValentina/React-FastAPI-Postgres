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

router = APIRouter(prefix="/users", tags=["users"])

@router.post("", response_model=UserResponse)
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_async_session)):
    """创建新用户"""
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
    db: AsyncSession = Depends(get_async_session)
) -> UserResponse:
    """完整更新用户信息"""
    try:
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
    db: AsyncSession = Depends(get_async_session)
) -> UserResponse:
    """部分更新用户信息"""
    try:
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
    name: Annotated[str | None, Query(min_length=2, description="用户名")] = None,
    age: Annotated[int | None, Query(ge=0, le=150, description="年龄")] = None,
    sort_by: Annotated[List[str], Query(description="排序字段")] = ["created_at"]
) -> List[UserResponse]:
    """获取用户列表"""
    # TODO: 实现用户列表查询功能，包括过滤和排序
    # 目前简单返回所有用户
    result = await db.execute(select(User))
    return result.scalars().all() 